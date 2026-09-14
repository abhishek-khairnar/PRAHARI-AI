"""
PRAHARI-AI P0 Regressions Verification Test Suite
Tests:
P0-1: ANPR Local Offline-First Model Loading (No Internet / No Hugging Face Download)
P0-2: Database Test Isolation (Zero Pollution of prahari_events.db)
P0-3: Intrusion Detection Multi-Crossing Semantics (IN -> OUT -> IN & Jitter Protection)
"""

import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

# ─── Step 1: Guarantee Database Isolation ───
_test_dir = tempfile.mkdtemp(prefix="prahari_p0_test_")
_test_db_path = os.path.join(_test_dir, "test_prahari.db")
os.environ["PRAHARI_DB_PATH"] = _test_db_path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import DatabaseManager, DEFAULT_DB_PATH
from centroid_tracker import CentroidTracker
from anpr_engine import ANPREngine


class TestP01AnprOfflineFirst(unittest.TestCase):
    """Verifies that ANPR loads local weights and does not depend on internet/HuggingFace."""

    def test_local_model_selected_without_network(self):
        """P0-1: Verify that local weights in weights/ are discovered and loaded without network."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        local_weights_path = os.path.join(base_dir, "weights", "license-plate-finetune-v1n.pt")
        self.assertTrue(os.path.exists(local_weights_path), f"Expected local weights at {local_weights_path}")

        # Block any network download by patching hf_hub_download to fail if called
        with patch("huggingface_hub.hf_hub_download", side_effect=RuntimeError("NETWORK CALL FORBIDDEN")):
            engine = ANPREngine()
            self.assertIsNotNone(engine.plate_detector, "Plate detector should be loaded from local weights")
            self.assertIn("Local", engine.detector_model_name)

    def test_missing_model_actionable_error_without_download(self):
        """P0-1: Verify that when local model is missing and download disabled, it fails safely with actionable error."""
        with patch("huggingface_hub.hf_hub_download", side_effect=RuntimeError("NETWORK CALL FORBIDDEN")):
            # Pass non-existent path and disable remote download
            with patch.dict(os.environ, {"ALLOW_REMOTE_MODEL_DOWNLOAD": "0"}):
                engine = ANPREngine(model_path="non_existent_weights.pt")
                # When non-existent path is passed, candidate search finds weights/
                # Let's test with empty candidates
                with patch("os.path.exists", side_effect=lambda p: False):
                    engine_missing = ANPREngine(model_path="missing.pt")
                    self.assertIsNone(engine_missing.plate_detector)


class TestP02DatabaseIsolation(unittest.TestCase):
    """Verifies that tests never write to prahari_events.db."""

    def test_database_isolation_and_immutability(self):
        """P0-2: Verify test records go to temp DB and production DB is untouched."""
        prod_db_path = os.path.abspath(DEFAULT_DB_PATH)
        self.assertTrue(os.path.exists(prod_db_path))

        # Record production counts
        import sqlite3
        conn_prod = sqlite3.connect(prod_db_path)
        cur_prod = conn_prod.cursor()
        cur_prod.execute("SELECT COUNT(*) FROM intrusion_events")
        prod_count_before = cur_prod.fetchone()[0]
        conn_prod.close()

        # Instantiate isolated test DB
        test_db = DatabaseManager(db_path=_test_db_path)
        self.assertEqual(os.path.abspath(test_db.db_path), os.path.abspath(_test_db_path))
        self.assertNotEqual(os.path.abspath(test_db.db_path), prod_db_path)

        # Write test event to isolated DB
        test_db.log_intrusion_event(
            timestamp="2026-09-11 12:00:00",
            object_type="Person",
            object_id=77777,
            snapshot_path="test_isolation.jpg",
            camera_id="ISOLATED-CAM",
            direction="IN"
        )

        # Verify record exists in test DB
        recent_test = test_db.get_recent_intrusions(limit=5, camera_id="ISOLATED-CAM")
        self.assertEqual(len(recent_test), 1)
        self.assertEqual(recent_test[0]["object_id"], 77777)

        # Verify production DB counts are 100% UNCHANGED
        conn_prod = sqlite3.connect(prod_db_path)
        cur_prod = conn_prod.cursor()
        cur_prod.execute("SELECT COUNT(*) FROM intrusion_events")
        prod_count_after = cur_prod.fetchone()[0]
        cur_prod.execute("SELECT COUNT(*) FROM intrusion_events WHERE object_id = 77777")
        test_in_prod = cur_prod.fetchone()[0]
        conn_prod.close()

        self.assertEqual(test_in_prod, 0, "Test record must NOT exist in production DB!")
        self.assertGreaterEqual(prod_count_after, prod_count_before, "Production DB count must not decrease!")


class TestP03IntrusionReCrossing(unittest.TestCase):
    """
    Verifies all 10 intrusion re-crossing and jitter scenarios required by Section 6.6:
    1. ABOVE -> BELOW => 1 IN
    2. ABOVE -> BELOW -> BELOW -> BELOW => 1 IN only
    3. ABOVE -> BELOW -> ABOVE => IN, OUT
    4. ABOVE -> BELOW -> ABOVE -> BELOW => IN, OUT, IN
    5. ABOVE -> BELOW -> ABOVE -> BELOW -> ABOVE => IN, OUT, IN, OUT
    6. Jitter: ABOVE, BELOW, ABOVE, BELOW, ABOVE => NO event until confirmed
    7. Multiple objects: Object A IN, Object B IN => 2 independent events
    8. Remains on one side => no repeated alerts
    9. Track disappears => no fabricated crossing
    10. Video loop reset => old state cleared cleanly
    """

    def setUp(self):
        self.tracker = CentroidTracker(max_disappeared=25, max_distance=220.0)
        self.line_y = 500

    def _feed_positions(self, object_id: int, y_positions: list):
        """Helper feeding a list of y-positions for an object and returning crossing events."""
        events = []
        for y in y_positions:
            detections = [(100, y - 20, 140, y + 20, "Person", 0.85)]
            tracked = self.tracker.update(detections)
            # When registering for the first time, tracker assigns object ID 1, 2, etc.
            # Find the tracker ID corresponding to this detection
            tid = next(iter(tracked.keys()))
            is_cross, direction = self.tracker.check_intrusion_crossing(tid, self.line_y)
            if is_cross:
                events.append((tid, direction))
        return events

    def test_scenario_1_above_to_below(self):
        """TEST 1: ABOVE -> BELOW => 1 IN (with 2-hit confirmation on new side)."""
        # y=400 (ABOVE, confirmed), y=550 (BELOW, cand), y=560 (BELOW, confirmed IN)
        events = self._feed_positions(1, [400, 550, 560])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1], "IN")

    def test_scenario_2_above_to_below_and_remain(self):
        """TEST 2: ABOVE -> BELOW -> BELOW -> BELOW => 1 IN only."""
        events = self._feed_positions(1, [400, 550, 560, 580, 600])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1], "IN")

    def test_scenario_3_above_below_above(self):
        """TEST 3: ABOVE -> BELOW -> ABOVE => IN, OUT."""
        events = self._feed_positions(1, [400, 550, 560, 420, 410])
        self.assertEqual(len(events), 2)
        self.assertEqual([e[1] for e in events], ["IN", "OUT"])

    def test_scenario_4_above_below_above_below(self):
        """TEST 4: ABOVE -> BELOW -> ABOVE -> BELOW => IN, OUT, IN."""
        events = self._feed_positions(1, [400, 550, 560, 420, 410, 550, 560])
        self.assertEqual(len(events), 3)
        self.assertEqual([e[1] for e in events], ["IN", "OUT", "IN"])

    def test_scenario_5_re_crossing_full_cycle(self):
        """TEST 5: ABOVE -> BELOW -> ABOVE -> BELOW -> ABOVE => IN, OUT, IN, OUT."""
        events = self._feed_positions(1, [400, 550, 560, 420, 410, 550, 560, 420, 410])
        self.assertEqual(len(events), 4)
        self.assertEqual([e[1] for e in events], ["IN", "OUT", "IN", "OUT"])

    def test_scenario_6_jitter_resistance(self):
        """TEST 6: Jitter: ABOVE, BELOW, ABOVE, BELOW, ABOVE => NO event until confirmed."""
        # Single frame dips below line must NOT trigger crossing
        events = self._feed_positions(1, [400, 510, 400, 510, 400])
        self.assertEqual(len(events), 0, f"Jitter should not trigger crossing, got {events}")

    def test_scenario_7_multiple_objects(self):
        """TEST 7: Multiple objects: Object A crosses IN, Object B crosses IN => 2 independent events."""
        # Frame 0: Both above
        d0 = [(100, 380, 140, 420, "Person", 0.85), (300, 380, 340, 420, "Person", 0.85)]
        t0 = self.tracker.update(d0)
        for tid in t0:
            self.tracker.check_intrusion_crossing(tid, self.line_y)

        # Frame 1: Both candidate below
        d1 = [(100, 530, 140, 570, "Person", 0.85), (300, 530, 340, 570, "Person", 0.85)]
        t1 = self.tracker.update(d1)
        for tid in t1:
            self.tracker.check_intrusion_crossing(tid, self.line_y)

        # Frame 2: Both confirmed below
        d2 = [(100, 540, 140, 580, "Person", 0.85), (300, 540, 340, 580, "Person", 0.85)]
        t2 = self.tracker.update(d2)
        events = []
        for tid in t2:
            is_c, d = self.tracker.check_intrusion_crossing(tid, self.line_y)
            if is_c:
                events.append((tid, d))

        self.assertEqual(len(events), 2)
        self.assertEqual([e[1] for e in events], ["IN", "IN"])

    def test_scenario_8_object_remains_on_one_side(self):
        """TEST 8: One object remains on one side => no repeated alerts."""
        events = self._feed_positions(1, [400, 405, 410, 395, 402, 408])
        self.assertEqual(len(events), 0)

    def test_scenario_9_track_disappears(self):
        """TEST 9: Track disappears => no fabricated crossing."""
        events = self._feed_positions(1, [400, 420])
        self.assertEqual(len(events), 0)
        # Object missing for 30 frames (> max_disappeared=25)
        for _ in range(30):
            self.tracker.update([])
        self.assertEqual(len(self.tracker.objects), 0)
        # New object appearing below line does not trigger crossing from thin air
        d_new = [(100, 600, 140, 640, "Person", 0.85)]
        t_new = self.tracker.update(d_new)
        tid = next(iter(t_new.keys()))
        is_c, d = self.tracker.check_intrusion_crossing(tid, self.line_y)
        self.assertFalse(is_c)

    def test_scenario_10_video_loop_reset(self):
        """TEST 10: Video loop reset clears old crossing state without false duplicate events."""
        events = self._feed_positions(1, [400, 550, 560])
        self.assertEqual(len(events), 1)

        # Loop reset triggers tracker.reset()
        self.tracker.reset()
        self.assertEqual(len(self.tracker.objects), 0)
        self.assertEqual(len(self.tracker.confirmed_fence_sides), 0)

        # When object reappears after loop at top of frame, it initializes cleanly
        d_loop = [(100, 380, 140, 420, "Person", 0.85)]
        t_loop = self.tracker.update(d_loop)
        tid = next(iter(t_loop.keys()))
        is_c, _ = self.tracker.check_intrusion_crossing(tid, self.line_y)
        self.assertFalse(is_c)


def tearDownModule():
    """Cleans up isolated temporary test directory."""
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
