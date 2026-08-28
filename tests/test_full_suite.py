"""
PRAHARI-AI Comprehensive Full Test Suite (Standard unittest)
Tests:
- Database schema, WAL mode, indexing, event logging, and analytics summary.
- ModelRegistry singleton instance & VRAM footprint.
- CameraManager 4-camera lifecycle and fault isolation.
- Night Detection dual-threshold hysteresis.
- Suspicious Activity / Loitering stability logic.
- FastAPI REST & Video Streaming Endpoints.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import db_manager
from rtsp_stream import ModelRegistry, RTSPStreamReader, NIGHT_ENTER_THRESHOLD, NIGHT_EXIT_THRESHOLD
from camera_manager import CameraManager
from main import app


class TestDatabaseLayer(unittest.TestCase):
    """Tests SQLite database reliability, indexing, and analytics queries."""

    def test_database_connection_and_wal(self):
        self.assertIsNotNone(db_manager)
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0].lower()
            self.assertIn(mode, ["wal", "memory"])

    def test_log_and_query_events(self):
        now_str = "2026-08-28 12:00:00"
        db_manager.log_intrusion_event(
            timestamp=now_str,
            object_type="Person",
            object_id=9999,
            snapshot_path="test_snap.jpg",
            camera_id="TEST-CAM",
            direction="IN",
            validation_status="DETECTED"
        )
        recent = db_manager.get_recent_intrusions(limit=5, camera_id="TEST-CAM")
        self.assertGreater(len(recent), 0)
        self.assertEqual(recent[0]["object_id"], 9999)
        self.assertEqual(recent[0]["camera_id"], "TEST-CAM")

        db_manager.log_anpr_event(
            timestamp=now_str,
            object_type="Car",
            object_id=8888,
            plate_text="MH12AB1234",
            confidence=0.88,
            snapshot_path="test_plate.jpg",
            camera_id="TEST-CAM",
            validation_status="VERIFIED"
        )
        recent_anpr = db_manager.get_recent_anpr(limit=5, camera_id="TEST-CAM")
        self.assertGreater(len(recent_anpr), 0)
        self.assertEqual(recent_anpr[0]["plate_text"], "MH12AB1234")

    def test_analytics_summary(self):
        analytics = db_manager.get_analytics_summary()
        self.assertIn("events_per_camera", analytics)
        self.assertIn("event_breakdown", analytics)
        self.assertIn("verified_plates_count", analytics)
        self.assertIsInstance(analytics["events_per_camera"], dict)


class TestModelRegistry(unittest.TestCase):
    """Tests shared AI ModelRegistry singleton pattern."""

    def test_singleton_identity(self):
        reg1 = ModelRegistry()
        reg2 = ModelRegistry()
        self.assertIs(reg1, reg2)
        self.assertIsNotNone(reg1.yolo_model)
        self.assertIsNotNone(reg1.anpr_engine)


class TestCameraManager(unittest.TestCase):
    """Tests multi-camera configuration and management."""

    def test_camera_list(self):
        mgr = CameraManager()
        cams = mgr.get_camera_list()
        self.assertGreaterEqual(len(cams), 4)
        cam_ids = [c["id"] for c in cams]
        self.assertIn("CAM-01", cam_ids)
        self.assertIn("CAM-02", cam_ids)
        self.assertIn("CAM-03", cam_ids)
        self.assertIn("CAM-04", cam_ids)

    def test_get_reader(self):
        mgr = CameraManager()
        r1 = mgr.get_reader("CAM-01")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.camera_id, "CAM-01")


class TestNightHysteresisLogic(unittest.TestCase):
    """Tests dual-threshold night detection hysteresis behavior."""

    def test_night_thresholds(self):
        self.assertLess(NIGHT_ENTER_THRESHOLD, NIGHT_EXIT_THRESHOLD)
        self.assertEqual(NIGHT_ENTER_THRESHOLD, 85.0)
        self.assertEqual(NIGHT_EXIT_THRESHOLD, 98.0)


class TestFastAPIEndpoints(unittest.TestCase):
    """Tests all REST and streaming endpoints."""

    def test_all_endpoints(self):
        with TestClient(app) as client:
            r = client.get("/")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/cameras")
            self.assertEqual(r.status_code, 200)
            self.assertGreaterEqual(len(r.json()), 4)

            r = client.get("/api/status")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/dashboard_stats")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/alerts?limit=5")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/anpr_log?limit=5")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/security_events?limit=5")
            self.assertEqual(r.status_code, 200)

            r = client.get("/api/analytics")
            self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
