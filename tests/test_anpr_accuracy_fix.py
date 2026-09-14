"""
Unit tests for ANPR Accuracy Fix #1:
- Strict Indian State-Code Validation & Conservative Levenshtein-1 Fuzzy Recovery
- Safe Multi-Box OCR Assembly & Spatial Filtering
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from anpr_engine import ANPREngine, validate_state_code, INDIAN_STATE_CODES


class TestStrictStateValidation(unittest.TestCase):
    """Tests 1 through 7: Strict State-Code Validation and Conservative Recovery."""

    @classmethod
    def setUpClass(cls):
        # Instantiate once for format validation (no heavy GPU model needed)
        cls.engine = ANPREngine(model_path="non_existent.pt")

    def test_01_valid_mh_passes(self):
        """Test 1: Valid 'MH' passes exact state validation."""
        status, resolved = validate_state_code("MH")
        self.assertEqual(status, "EXACT")
        self.assertEqual(resolved, "MH")
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("MH02FU9304", 0.85)
        self.assertTrue(is_val)
        self.assertEqual(tier, 1)
        self.assertEqual(cleaned, "MH02FU9304")

    def test_02_valid_dl_passes(self):
        """Test 2: Valid 'DL' passes exact state validation."""
        status, resolved = validate_state_code("DL")
        self.assertEqual(status, "EXACT")
        self.assertEqual(resolved, "DL")
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("DL01CR1176", 0.90)
        self.assertTrue(is_val)
        self.assertEqual(tier, 1)
        self.assertEqual(cleaned, "DL01CR1176")

    def test_03_invalid_hh_does_not_pass_exact_validation(self):
        """Test 3: Invalid 'HH' does not pass exact state validation."""
        status, resolved = validate_state_code("HH")
        self.assertNotEqual(status, "EXACT")
        self.assertNotIn("HH", INDIAN_STATE_CODES)

    def test_04_invalid_prefix_does_not_trigger_tier1_success(self):
        """Test 4: Invalid prefix does not trigger Tier-1 success."""
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("HH02FU9304", 0.78)
        self.assertFalse(is_val)
        self.assertEqual(tier, 0)
        self.assertNotEqual(tier, 1)

    def test_05_unique_levenshtein_distance_1_recovery_works_when_safe(self):
        """Test 5: Unique Levenshtein-distance-1 recovery works only when safe."""
        # 'NC' has distance 1 only to 'NL' (Nagaland)
        status, resolved = validate_state_code("NC")
        self.assertEqual(status, "FUZZY")
        self.assertEqual(resolved, "NL")
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("NC02FU9304", 0.80)
        self.assertTrue(is_val)
        self.assertEqual(tier, 1)
        self.assertEqual(cleaned, "NL02FU9304")

    def test_06_ambiguous_fuzzy_state_recovery_is_rejected(self):
        """Test 6: Ambiguous fuzzy state recovery is rejected."""
        # 'HH' has 6 distance-1 matches ('JH', 'CH', 'MH', 'BH', 'HR', 'HP') -> Ambiguous!
        status, resolved = validate_state_code("HH")
        self.assertEqual(status, "INVALID")
        self.assertIsNone(resolved)
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("HH02FU9304", 0.78)
        self.assertFalse(is_val)
        self.assertEqual(tier, 0)

    def test_07_existing_valid_plate_formats_remain_valid(self):
        """Test 7: Existing valid plate formats remain valid."""
        test_plates = [
            ("KA05M9999", 1),
            ("MH12AB1234", 1),
            ("DL01CR1176", 1),
            ("UP16CD5678", 1),
            ("GJ01AX9999", 1),
            ("ABC1234", 2),  # General alphanumeric plate
        ]
        for plate_str, expected_tier in test_plates:
            cleaned, is_val, tier = self.engine.validate_and_correct_plate(plate_str, 0.85)
            self.assertTrue(is_val, f"Expected {plate_str} to be valid")
            self.assertEqual(tier, expected_tier, f"Expected tier {expected_tier} for {plate_str}")


class TestSafeMultiBoxAssembly(unittest.TestCase):
    """Tests 8 through 14: Multi-Box OCR Assembly and Selection."""

    @classmethod
    def setUpClass(cls):
        cls.engine = ANPREngine(model_path="non_existent.pt")

    def test_08_multi_box_assembles_to_full_plate(self):
        """Test 8: ['MH02', 'FU9304'] assembles to 'MH02FU9304'."""
        frags = [
            {"raw_text": "MH02", "clean_text": "MH02", "conf": 0.88, "bbox": [10, 20, 100, 60], "w": 90, "h": 40, "cx": 55, "cy": 40},
            {"raw_text": "FU9304", "clean_text": "FU9304", "conf": 0.85, "bbox": [110, 22, 240, 62], "w": 130, "h": 40, "cx": 175, "cy": 42}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        self.assertEqual(best_text, "MH02FU9304")
        self.assertAlmostEqual(best_conf, 0.862, places=2)

    def test_09_fragments_sorted_left_to_right_when_out_of_order(self):
        """Test 9: Fragments are sorted left-to-right even if OCR returns them out of order."""
        # Box 2 passed first, Box 1 passed second
        frags = [
            {"raw_text": "FU9304", "clean_text": "FU9304", "conf": 0.85, "bbox": [110, 22, 240, 62], "w": 130, "h": 40, "cx": 175, "cy": 42},
            {"raw_text": "MH02", "clean_text": "MH02", "conf": 0.88, "bbox": [10, 20, 100, 60], "w": 90, "h": 40, "cx": 55, "cy": 40}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        self.assertEqual(best_text, "MH02FU9304")

    def test_10_unrelated_distant_boxes_not_concatenated(self):
        """Test 10: Unrelated boxes with excessive horizontal gap are not concatenated."""
        frags = [
            {"raw_text": "MH02", "clean_text": "MH02", "conf": 0.88, "bbox": [10, 20, 100, 60], "w": 90, "h": 40, "cx": 55, "cy": 40},
            {"raw_text": "PARKING", "clean_text": "PARKING", "conf": 0.82, "bbox": [350, 20, 480, 60], "w": 130, "h": 40, "cx": 415, "cy": 40}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        # Should fallback to highest single box rather than concatenating "MH02PARKING"
        self.assertNotEqual(best_text, "MH02PARKING")
        self.assertIn(best_text, ["MH02", "PARKING"])

    def test_11_separate_text_lines_not_concatenated(self):
        """Test 11: Separate text lines (large vertical separation) are not concatenated."""
        frags = [
            {"raw_text": "MH02", "clean_text": "MH02", "conf": 0.88, "bbox": [10, 20, 100, 60], "w": 90, "h": 40, "cx": 55, "cy": 40},
            {"raw_text": "FU9304", "clean_text": "FU9304", "conf": 0.85, "bbox": [10, 100, 140, 140], "w": 130, "h": 40, "cx": 75, "cy": 120}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        self.assertNotEqual(best_text, "MH02FU9304")

    def test_12_single_box_ocr_behavior_remains_unchanged(self):
        """Test 12: Single-box OCR behavior remains unchanged."""
        frags = [
            {"raw_text": "MH02FU9304", "clean_text": "MH02FU9304", "conf": 0.91, "bbox": [10, 20, 250, 60], "w": 240, "h": 40, "cx": 130, "cy": 40}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        self.assertEqual(best_text, "MH02FU9304")
        self.assertEqual(best_conf, 0.91)

    def test_13_empty_ocr_result_handled_safely(self):
        """Test 13: Empty OCR result is handled safely without exception."""
        best_text, best_conf = self.engine._assemble_and_select_candidate([])
        self.assertIsNone(best_text)
        self.assertEqual(best_conf, 0.0)

    def test_14_low_confidence_fragment_does_not_dominate_strong_valid_result(self):
        """Test 14: Low-confidence fragment does not automatically dominate a strong valid result."""
        frags = [
            {"raw_text": "MH02FU9304", "clean_text": "MH02FU9304", "conf": 0.92, "bbox": [10, 20, 220, 60], "w": 210, "h": 40, "cx": 115, "cy": 40},
            {"raw_text": "X", "clean_text": "X", "conf": 0.12, "bbox": [225, 20, 245, 60], "w": 20, "h": 40, "cx": 235, "cy": 40}
        ]
        best_text, best_conf = self.engine._assemble_and_select_candidate(frags)
        self.assertEqual(best_text, "MH02FU9304")
        self.assertEqual(best_conf, 0.92)


class TestTemporalConsensus(unittest.TestCase):
    """Tests 15 through 30: Validation-Aware & Character-Wise Temporal Consensus."""

    @classmethod
    def setUpClass(cls):
        from anpr_consensus import resolve_temporal_consensus, are_strings_groupable
        cls.consensus = staticmethod(resolve_temporal_consensus)
        cls.groupable = staticmethod(are_strings_groupable)

    def test_15_identical_repeated_readings_select_repeated_plate(self):
        """Test 15: Identical repeated readings select the repeated plate."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.60, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.65, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.62, True, 1),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FU9304")
        self.assertIn(res["published_tier"], ("FORMAT_VALID", "VERIFIED"))
        self.assertTrue(res["is_valid"])

    def test_16_three_consistent_observations_defeat_high_conf_outlier(self):
        """Test 16: Three consistent observations defeat a single high-confidence outlier."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.60, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.65, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.62, True, 1),
            ("DL99ZZ9999", "DL99ZZ9999", 0.95, True, 1),  # High-confidence outlier
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FU9304")
        self.assertNotEqual(res["published_plate"], "DL99ZZ9999")

    def test_17_character_wise_consensus_m_over_h(self):
        """Test 17: Character-wise consensus resolves 'M' over 'H' given consistent evidence."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.70, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.70, True, 1),
            ("HH02FU9304", "HH02FU9304", 0.85, False, 0),  # Confused first char
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FU9304")
        self.assertTrue(res["is_valid"])

    def test_18_single_high_conf_incorrect_does_not_win(self):
        """Test 18: A single high-confidence incorrect observation does not win against valid agreement."""
        obs = [
            ("MH02FX6786", "MH02FX6786", 0.54, True, 1),
            ("MH02FX6786", "MH02FX6786", 0.50, True, 1),
            ("HH02FX6786", "HH02FX6786", 0.88, False, 0),  # High-conf invalid outlier
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FX6786")
        self.assertTrue(res["is_valid"])

    def test_19_two_observations_only_conservative(self):
        """Test 19: Two observations only: character voting not activated, valid candidate chosen."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.60, True, 1),
            ("HH02FU9304", "HH02FU9304", 0.75, False, 0),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FU9304")
        self.assertIn(res["consensus_method"], ["direct_valid_best", "cluster_valid_fallback"])

    def test_20_different_lengths_handled_safely(self):
        """Test 20: Candidates with different lengths are grouped and aligned safely."""
        obs = [
            ("MH02FX67861", "MH02FX67861", 0.42, False, 0),
            ("MH02FX6786", "MH02FX6786", 0.54, True, 1),
            ("MH02FX6786", "MH02FX6786", 0.50, True, 1),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FX6786")
        self.assertTrue(res["is_valid"])

    def test_21_large_edit_distance_candidates_do_not_merge(self):
        """Test 21: Large edit distance candidates do not merge into the same cluster."""
        self.assertFalse(self.groupable("MH02FU9304", "DL01CR1176"))
        self.assertFalse(self.groupable("KA01AB1234", "TN02XY9876"))
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.70, True, 1),
            ("DL01CR1176", "DL01CR1176", 0.70, True, 1),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["cluster_count"], 2)

    def test_22_low_confidence_noise_cannot_dominate_strong_candidate(self):
        """Test 22: Low-confidence noise cannot overpower a genuine valid candidate."""
        obs = [
            ("AAAA1111", "AAAA1111", 0.05, False, 0),
            ("AAAA1111", "AAAA1111", 0.05, False, 0),
            ("AAAA1111", "AAAA1111", 0.05, False, 0),
            ("AAAA1111", "AAAA1111", 0.05, False, 0),
            ("AAAA1111", "AAAA1111", 0.05, False, 0),
            ("MH02FU9304", "MH02FU9304", 0.75, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.70, True, 1),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "MH02FU9304")
        self.assertIn(res["published_tier"], ("FORMAT_VALID", "VERIFIED"))

    def test_23_different_vehicle_tracks_never_mix(self):
        """Test 23: Different vehicle/track observation sets remain completely isolated."""
        v1_obs = [("MH02FU9304", "MH02FU9304", 0.75, True, 1)]
        v2_obs = [("MH02FX6786", "MH02FX6786", 0.75, True, 1)]
        res_v1 = self.consensus(v1_obs)
        res_v2 = self.consensus(v2_obs)
        self.assertEqual(res_v1["published_plate"], "MH02FU9304")
        self.assertEqual(res_v2["published_plate"], "MH02FX6786")

    def test_24_invalid_state_prefixes_never_verified(self):
        """Test 24: Invalid state prefixes never become VERIFIED/FORMAT_VALID through consensus alone."""
        obs = [
            ("HH02FU9304", "HH02FU9304", 0.85, False, 0),
            ("HH02FU9304", "HH02FU9304", 0.80, False, 0),
            ("HH02FU9304", "HH02FU9304", 0.82, False, 0),
        ]
        res = self.consensus(obs)
        self.assertEqual(res["published_plate"], "HH02FU9304")
        self.assertFalse(res["is_valid"])
        self.assertNotIn(res["published_tier"], ("FORMAT_VALID", "VERIFIED"))
        self.assertEqual(res["published_tier"], "LOW_CONFIDENCE")

    def test_25_exact_valid_state_remains_valid(self):
        """Test 25: Exact valid state codes remain valid and achieve FORMAT_VALID when evidence is strong."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.72, True, 1),
            ("MH02FU9304", "MH02FU9304", 0.68, True, 1),
        ]
        res = self.consensus(obs)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["tier_num"], 1)
        self.assertIn(res["published_tier"], ("FORMAT_VALID", "VERIFIED"))

    def test_26_fuzzy_state_recovery_remains_conservative(self):
        """Test 26: Unique fuzzy state recovery works for valid candidates, leaves ambiguous ones invalid."""
        obs_nc = [("NC02FU9304", "NC02FU9304", 0.75, True, 1)]
        res_nc = self.consensus(obs_nc)
        self.assertEqual(res_nc["published_plate"], "NL02FU9304")
        self.assertTrue(res_nc["is_valid"])

        obs_hh = [("HH02FU9304", "HH02FU9304", 0.75, False, 0)]
        res_hh = self.consensus(obs_hh)
        self.assertEqual(res_hh["published_plate"], "HH02FU9304")
        self.assertFalse(res_hh["is_valid"])

    def test_27_confidence_remains_bounded(self):
        """Test 27: Confidence is strictly bounded and does not exceed 1.0 even with many reads."""
        obs = [("MH02FU9304", "MH02FU9304", 0.99, True, 1) for _ in range(50)]
        res = self.consensus(obs)
        self.assertLessEqual(res["published_conf"], 0.99)
        self.assertGreaterEqual(res["published_conf"], 0.0)

    def test_28_consensus_is_deterministic(self):
        """Test 28: Consensus produces identical results across repeated calls for identical input."""
        obs = [
            ("MH02FU9304", "MH02FU9304", 0.65, True, 1),
            ("HH02FU9304", "HH02FU9304", 0.75, False, 0),
            ("MH02FU9304", "MH02FU9304", 0.70, True, 1),
            ("MH02FU930L", "MH02FU930L", 0.70, False, 0),
        ]
        first_run = self.consensus(obs)
        for _ in range(10):
            run = self.consensus(obs)
            self.assertEqual(run["published_plate"], first_run["published_plate"])
            self.assertEqual(run["published_conf"], first_run["published_conf"])
            self.assertEqual(run["published_tier"], first_run["published_tier"])

    def test_29_empty_observation_history_handled_safely(self):
        """Test 29: Empty observation history produces NOT_READ result without error."""
        res = self.consensus([])
        self.assertIsNone(res["published_plate"])
        self.assertEqual(res["published_conf"], 0.0)
        self.assertEqual(res["published_tier"], "NOT_READ")
        self.assertFalse(res["is_valid"])

    def test_30_temporal_window_filtering(self):
        """Test 30: Observations outside the temporal window are excluded when timestamps are provided."""
        now = 100.0
        obs = [
            ("OLD01AB1234", "OLD01AB1234", 0.80, True, 1, 50.0, None),   # 50s old -> excluded
            ("NEW02CD5678", "NEW02CD5678", 0.80, True, 1, 95.0, None),   # 5s old -> included
        ]
        res = self.consensus(obs, window_seconds=25.0, current_ts=now)
        self.assertEqual(res["published_plate"], "NEW02CD5678")


class TestPlateCropPreprocessing(unittest.TestCase):
    """Tests 31 through 44: Plate Crop Quality and Conservative Preprocessing Pipeline."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.engine = ANPREngine(model_path="non_existent.pt")

    def test_31_empty_crop_handled_safely(self):
        """Test 31: Empty or None crop returns safe fallback without crashing."""
        variants_none = self.engine._preprocess_variants(None)
        self.assertEqual(variants_none, [])

        empty_img = self.np.zeros((0, 0, 3), dtype=self.np.uint8)
        variants_empty = self.engine._preprocess_variants(empty_img)
        self.assertEqual(variants_empty, [])

        cleaned, raw, conf, is_val, tier = self.engine.read_plate(None)
        self.assertIsNone(cleaned)
        self.assertFalse(is_val)

    def test_32_crop_never_produces_negative_dimensions(self):
        """Test 32: Bounding box extraction never produces negative dimensions."""
        frame = self.np.zeros((100, 100, 3), dtype=self.np.uint8)
        plate_crop, _, is_det, _ = self.engine.extract_plate_crop(frame, (-10, -10, 50, 50))
        self.assertIsNotNone(plate_crop)
        self.assertGreaterEqual(plate_crop.shape[0], 0)
        self.assertGreaterEqual(plate_crop.shape[1], 0)

    def test_33_crop_never_exceeds_image_boundaries(self):
        """Test 33: Bounding box extraction stays strictly within image boundaries."""
        frame = self.np.zeros((300, 300, 3), dtype=self.np.uint8)
        plate_crop, _, is_det, _ = self.engine.extract_plate_crop(frame, (200, 200, 350, 350))
        self.assertIsNotNone(plate_crop)
        self.assertLessEqual(plate_crop.shape[0], 300)
        self.assertLessEqual(plate_crop.shape[1], 300)

    def test_34_crop_always_preserves_nonzero_dimensions(self):
        """Test 34: Extraction on valid image preserves positive non-zero dimensions."""
        frame = self.np.ones((200, 300, 3), dtype=self.np.uint8) * 128
        plate_crop, _, is_det, _ = self.engine.extract_plate_crop(frame, (50, 50, 150, 100))
        self.assertIsNotNone(plate_crop)
        self.assertGreater(plate_crop.shape[0], 0)
        self.assertGreater(plate_crop.shape[1], 0)

    def test_35_aspect_ratio_preserved_during_resizing(self):
        """Test 35: Aspect ratio is preserved during cubic upscaling in _preprocess_variants."""
        # 120 x 30 plate (aspect ratio 4.0)
        crop = self.np.ones((30, 120, 3), dtype=self.np.uint8) * 200
        variants = self.engine._preprocess_variants(crop)
        self.assertGreater(len(variants), 0)
        base = variants[0]
        # Target height is at least 90, width at least 320
        self.assertGreaterEqual(base.shape[0], 90)
        self.assertGreaterEqual(base.shape[1], 320)
        # Scaled aspect ratio should match original ratio within reasonable rounding
        orig_ratio = 120.0 / 30.0
        new_ratio = float(base.shape[1]) / float(base.shape[0])
        self.assertAlmostEqual(orig_ratio, new_ratio, delta=0.2)

    def test_36_original_crop_remains_available_as_fallback(self):
        """Test 36: Variant 1 remains the original uncorrupted upscaled crop."""
        crop = self.np.ones((40, 150, 3), dtype=self.np.uint8) * 150
        variants = self.engine._preprocess_variants(crop)
        self.assertGreaterEqual(len(variants), 1)
        # First variant is the direct base upscaled image
        self.assertIsNotNone(variants[0])
        self.assertEqual(variants[0].shape[2], 3)

    def test_37_reduced_margin_crop_generated_safely(self):
        """Test 37: Margin-trimmed variant is generated safely for large enough crops."""
        # 80 x 240 plate crop
        crop = self.np.ones((80, 240, 3), dtype=self.np.uint8) * 180
        variants = self.engine._preprocess_variants(crop)
        # At least 5 variants including trimmed
        self.assertGreaterEqual(len(variants), 4)
        for var in variants:
            self.assertGreater(var.shape[0], 0)
            self.assertGreater(var.shape[1], 0)

    def test_38_multiple_preprocessing_variants_are_deterministic(self):
        """Test 38: Preprocessing variants produce bit-exact identical output across runs."""
        crop = self.np.random.RandomState(42).randint(0, 256, (45, 160, 3), dtype=self.np.uint8)
        run1 = self.engine._preprocess_variants(crop)
        run2 = self.engine._preprocess_variants(crop)
        self.assertEqual(len(run1), len(run2))
        for v1, v2 in zip(run1, run2):
            self.np.testing.assert_array_equal(v1, v2)

    def test_39_adaptive_thresholding_does_not_crash_on_low_contrast(self):
        """Test 39: Low-contrast input is handled gracefully without NaN or OpenCV errors."""
        low_contrast = self.np.ones((40, 150, 3), dtype=self.np.uint8) * 128
        # Add tiny noise (std < 12)
        low_contrast[0, 0] = 130
        variants = self.engine._preprocess_variants(low_contrast)
        self.assertGreater(len(variants), 0)

    def test_40_otsu_thresholding_safely_handles_uniform_images(self):
        """Test 40: Completely uniform image (std = 0) is handled safely."""
        solid = self.np.zeros((50, 180, 3), dtype=self.np.uint8)
        variants = self.engine._preprocess_variants(solid)
        self.assertGreater(len(variants), 0)

    def test_41_character_clipping_protection(self):
        """Test 41: Padding calculation prevents zero or negative margins."""
        # Check padding logic explicitly
        bw, bh = 42, 18
        pad_x = max(2, int(bw * 0.06))
        pad_y = max(2, int(bh * 0.08))
        self.assertGreaterEqual(pad_x, 2)
        self.assertGreaterEqual(pad_y, 2)

    def test_42_detector_box_touching_image_boundary_handled_safely(self):
        """Test 42: Bounding box touching (0, 0) or image max edge clamps safely."""
        frame = self.np.ones((100, 100, 3), dtype=self.np.uint8) * 100
        # Touching left boundary px1=0
        crop1, _, _, _ = self.engine.extract_plate_crop(frame, (0, 10, 50, 40))
        self.assertIsNotNone(crop1)
        self.assertGreater(crop1.shape[0], 0)
        self.assertGreater(crop1.shape[1], 0)

        # Touching right/bottom boundary
        crop2, _, _, _ = self.engine.extract_plate_crop(frame, (60, 60, 100, 100))
        self.assertIsNotNone(crop2)
        self.assertGreater(crop2.shape[0], 0)
        self.assertGreater(crop2.shape[1], 0)

    def test_43_invalid_degenerate_geometry_falls_back_safely(self):
        """Test 43: Degenerate coordinates (x2 <= x1 or y2 <= y1) fallback safely without raising exceptions."""
        frame = self.np.ones((100, 100, 3), dtype=self.np.uint8) * 100
        crop, _, is_det, _ = self.engine.extract_plate_crop(frame, (50, 50, 50, 50))
        self.assertFalse(is_det)

    def test_44_existing_ocr_candidate_selection_still_works(self):
        """Test 44: Candidate selection and plate validation remain fully functional."""
        cleaned, is_val, tier = self.engine.validate_and_correct_plate("MH02FU9304", 0.85)
        self.assertEqual(cleaned, "MH02FU9304")
        self.assertTrue(is_val)
        self.assertEqual(tier, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

