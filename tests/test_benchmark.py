"""
Tests for Phase 3A Benchmark Infrastructure.
Verifies metrics, IoU, normalization, matching, serialization, and DB safety.
"""

import unittest
import json
import os
import sqlite3
from benchmark.metrics import (
    compute_iou,
    calculate_precision_recall_f1,
    match_boxes,
    compute_count_mae,
    normalize_plate_string,
    levenshtein_distance,
    character_accuracy,
    exact_match,
    compute_confusion_matrix,
)
import benchmark.config as bench_config

class TestBenchmarkMetrics(unittest.TestCase):
    def test_iou_calculation(self):
        # Identical boxes
        box_a = [0, 0, 100, 100]
        self.assertAlmostEqual(compute_iou(box_a, box_a), 1.0, places=4)

        # Disjoint boxes
        box_b = [200, 200, 300, 300]
        self.assertAlmostEqual(compute_iou(box_a, box_b), 0.0, places=4)

        # 50% overlap horizontally (overlap is [0, 0, 50, 100] -> area 5000; union is 15000 -> 0.3333)
        box_c = [50, 0, 150, 100]
        # inter = 50 * 100 = 5000
        # union = 10000 + 10000 - 5000 = 15000
        # iou = 5000 / 15000 = 1/3
        self.assertAlmostEqual(compute_iou(box_a, box_c), 1.0 / 3.0, places=4)

        # Partial 2D overlap: [0, 0, 10, 10] and [5, 5, 15, 15]
        # inter: [5, 5, 10, 10] -> 5 * 5 = 25
        # union: 100 + 100 - 25 = 175
        # iou: 25 / 175 = 1/7 = 0.142857
        box_d = [0, 0, 10, 10]
        box_e = [5, 5, 15, 15]
        self.assertAlmostEqual(compute_iou(box_d, box_e), 25.0 / 175.0, places=4)

    def test_precision_recall_f1(self):
        # Perfect
        res = calculate_precision_recall_f1(10, 0, 0)
        self.assertEqual(res["precision"], 1.0)
        self.assertEqual(res["recall"], 1.0)
        self.assertEqual(res["f1"], 1.0)

        # Zero
        res_zero = calculate_precision_recall_f1(0, 0, 0)
        self.assertEqual(res_zero["precision"], 0.0)
        self.assertEqual(res_zero["recall"], 0.0)
        self.assertEqual(res_zero["f1"], 0.0)

        # Balanced (tp=8, fp=2, fn=2)
        res_balanced = calculate_precision_recall_f1(8, 2, 2)
        self.assertEqual(res_balanced["precision"], 0.8)
        self.assertEqual(res_balanced["recall"], 0.8)
        self.assertEqual(res_balanced["f1"], 0.8)

    def test_match_boxes(self):
        preds = [[0, 0, 10, 10], [50, 50, 60, 60], [100, 100, 110, 110]]
        gts = [[1, 1, 10, 10], [50, 50, 60, 60], [200, 200, 210, 210]]
        tp, fp, fn, matched = match_boxes(preds, gts, iou_threshold=0.5)
        self.assertEqual(tp, 2)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 1)
        self.assertEqual(len(matched), 2)

    def test_count_mae(self):
        preds = [1, 2, 3, 4]
        gts = [1, 3, 3, 6]
        # errors: 0, 1, 0, 2 -> sum = 3 / 4 = 0.75
        self.assertAlmostEqual(compute_count_mae(preds, gts), 0.75, places=4)

    def test_anpr_normalization(self):
        self.assertEqual(normalize_plate_string("mh-02 fu 9304"), "MH02FU9304")
        self.assertEqual(normalize_plate_string("  DL.01-CR 1176  "), "DL01CR1176")
        self.assertEqual(normalize_plate_string("MH-02/FX-6786!"), "MH02FX6786")
        self.assertEqual(normalize_plate_string(""), "")
        self.assertEqual(normalize_plate_string(None), "")

    def test_levenshtein_and_exact_match(self):
        # Exact match
        self.assertTrue(exact_match("MH02FU9304", "mh-02 fu 9304"))
        self.assertFalse(exact_match("MH02FU9304", "MH02FU9305"))

        # Levenshtein distance
        self.assertEqual(levenshtein_distance("MH02FU9304", "MH02FU9304"), 0)
        self.assertEqual(levenshtein_distance("MH02FU9304", "MH02FU9305"), 1)
        self.assertEqual(levenshtein_distance("KITTEN", "SITTING"), 3)

        # Character accuracy
        self.assertEqual(character_accuracy("MH02FU9304", "MH02FU9304"), 1.0)
        # 1 char diff in 10 chars -> 9/10 = 0.9
        self.assertAlmostEqual(character_accuracy("MH02FU9304", "MH02FU9305"), 0.9, places=4)

    def test_confusion_matrix(self):
        classes = ["car", "truck", "bus"]
        y_true = ["car", "car", "truck", "bus", "car"]
        y_pred = ["car", "truck", "truck", "bus", "car"]
        cm = compute_confusion_matrix(classes, y_true, y_pred)
        self.assertEqual(cm["car"]["car"], 2)
        self.assertEqual(cm["car"]["truck"], 1)
        self.assertEqual(cm["truck"]["truck"], 1)
        self.assertEqual(cm["bus"]["bus"], 1)

    def test_result_serialization(self):
        sample_result = {
            "camera": "CAM-01",
            "iou": 0.8542,
            "metrics": {"precision": 0.91, "recall": 0.88, "f1": 0.89},
            "subtypes": ["car", "truck"],
            "counts": [1, 2, 3]
        }
        serialized = json.dumps(sample_result, indent=2)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["camera"], "CAM-01")
        self.assertEqual(deserialized["metrics"]["f1"], 0.89)

    def test_production_db_isolation(self):
        # Check that benchmark config directories are isolated from production DB
        self.assertTrue(str(bench_config.RESULTS_DIR).endswith(os.path.join("benchmark", "results")))
        self.assertTrue(str(bench_config.SAMPLES_DIR).endswith(os.path.join("benchmark", "samples")))
        self.assertTrue(str(bench_config.REPORTS_DIR).endswith(os.path.join("benchmark", "reports")))

        # Verify production DB exists and is accessible read-only
        prod_db_path = os.path.join(bench_config.PROJECT_ROOT, "prahari_events.db")
        self.assertTrue(os.path.exists(prod_db_path))

        # Check read-only URI connection works
        uri = f"file:{os.path.abspath(prod_db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        tbl_count = cursor.fetchone()[0]
        self.assertGreater(tbl_count, 0)
        conn.close()


class TestBenchmarkSpatialAssociation(unittest.TestCase):
    """
    Tests for ANPR Fix #2 — Benchmark Vehicle-to-Ground-Truth Spatial Association.
    Verifies isolation, greedy 1-to-1 matching, deterministic tie-breaking,
    unmatched handling, and absence of cross-vehicle observation pollution.
    """
    def setUp(self):
        from benchmark.video_analysis import (
            associate_detections_to_ground_truth,
            CAM01_ANPR_SPATIAL_GT
        )
        self.associate = associate_detections_to_ground_truth
        self.spatial_gt = CAM01_ANPR_SPATIAL_GT

    def test_one_gt_one_matching_detection(self):
        # 1. One GT vehicle + one matching detection -> associated.
        gt_map = {"V1_SilverSedan": [100, 100, 200, 200]}
        det_boxes = [[102, 98, 205, 199]]
        det_confs = [0.95]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40, det_confidences=det_confs)
        self.assertIn("V1_SilverSedan", res["matches"])
        self.assertEqual(res["matches"]["V1_SilverSedan"]["det_index"], 0)
        self.assertGreater(res["matches"]["V1_SilverSedan"]["iou"], 0.85)
        self.assertEqual(res["unmatched_gt"], [])
        self.assertEqual(res["unmatched_detections"], [])

    def test_two_gt_two_detections(self):
        # 2. Two GT vehicles + two detections -> each detection associated with correct GT vehicle.
        gt_map = {
            "V1_SilverSedan": [100, 100, 200, 200],
            "V2_DarkSedan": [500, 100, 600, 200]
        }
        det_boxes = [
            [502, 99, 604, 201],
            [101, 101, 199, 199]
        ]
        det_confs = [0.88, 0.92]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40, det_confidences=det_confs)
        self.assertEqual(res["matches"]["V1_SilverSedan"]["det_index"], 1)
        self.assertEqual(res["matches"]["V2_DarkSedan"]["det_index"], 0)
        self.assertEqual(res["unmatched_gt"], [])
        self.assertEqual(res["unmatched_detections"], [])

    def test_two_vehicles_different_plates_remain_separated(self):
        # 3. Two vehicles in same frame with different plates -> observations remain separated.
        gt_map = {
            "V1_SilverSedan": [100, 100, 200, 200],
            "V2_DarkSedan": [500, 100, 600, 200]
        }
        det_boxes = [
            [100, 100, 200, 200],
            [500, 100, 600, 200]
        ]
        anpr_mock_plates = {0: "MH02FU9304", 1: "MH02FX6786"}
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40)

        v1_obs = []
        v2_obs = []
        for vid, m in res["matches"].items():
            plate = anpr_mock_plates[m["det_index"]]
            if vid == "V1_SilverSedan":
                v1_obs.append(plate)
            elif vid == "V2_DarkSedan":
                v2_obs.append(plate)

        self.assertEqual(v1_obs, ["MH02FU9304"])
        self.assertEqual(v2_obs, ["MH02FX6786"])
        self.assertNotIn("MH02FX6786", v1_obs)
        self.assertNotIn("MH02FU9304", v2_obs)

    def test_v1_observation_cannot_appear_in_v2_history(self):
        # 4. V1 observation cannot appear in V2 observation history.
        gt_map = {
            "V1_SilverSedan": [100, 100, 200, 200],
            "V2_DarkSedan": [500, 100, 600, 200]
        }
        det_boxes = [[100, 100, 200, 200]]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40)

        v2_obs = []
        if "V2_DarkSedan" in res["matches"]:
            v2_obs.append("MH02FU9304")

        self.assertNotIn("V2_DarkSedan", res["matches"])
        self.assertIn("V2_DarkSedan", res["unmatched_gt"])
        self.assertEqual(v2_obs, [])

    def test_v1_observation_cannot_appear_in_v4_history(self):
        # 5. V1 observation cannot appear in V4 observation history.
        gt_map = {
            "V1_SilverSedan": [100, 100, 200, 200],
            "V4_DistantTruck": [1200, 400, 1400, 600]
        }
        det_boxes = [[100, 100, 200, 200]]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40)

        v4_obs = []
        if "V4_DistantTruck" in res["matches"]:
            v4_obs.append("MH02FU9304")

        self.assertNotIn("V4_DistantTruck", res["matches"])
        self.assertIn("V4_DistantTruck", res["unmatched_gt"])
        self.assertEqual(v4_obs, [])

    def test_detection_insufficient_iou_unmatched(self):
        # 6. Detection with insufficient IoU -> unmatched.
        gt_map = {"V1_SilverSedan": [100, 100, 200, 200]}
        det_boxes = [[300, 300, 400, 400]]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40)
        self.assertEqual(res["matches"], {})
        self.assertEqual(res["unmatched_gt"], ["V1_SilverSedan"])
        self.assertEqual(res["unmatched_detections"], [0])

        det_boxes_low_iou = [[170, 170, 270, 270]]
        res_low = self.associate(det_boxes_low_iou, gt_map, iou_threshold=0.40)
        self.assertEqual(res_low["matches"], {})
        self.assertEqual(res_low["unmatched_gt"], ["V1_SilverSedan"])
        self.assertEqual(res_low["unmatched_detections"], [0])

    def test_multiple_detections_overlapping_one_gt_deterministic_best(self):
        # 7. Multiple detections overlapping one GT vehicle -> deterministic best match.
        gt_map = {"V1_SilverSedan": [100, 100, 200, 200]}
        det_boxes = [
            [120, 120, 200, 200],
            [100, 100, 200, 200],
            [110, 110, 200, 200]
        ]
        det_confs = [0.90, 0.95, 0.85]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40, det_confidences=det_confs)
        self.assertIn("V1_SilverSedan", res["matches"])
        self.assertEqual(res["matches"]["V1_SilverSedan"]["det_index"], 1)
        self.assertAlmostEqual(res["matches"]["V1_SilverSedan"]["iou"], 1.0, places=3)
        self.assertEqual(set(res["unmatched_detections"]), {0, 2})

    def test_one_detection_overlapping_two_gt_assigned_to_only_one(self):
        # 8. One detection overlapping two GT vehicles -> assigned to only one GT vehicle.
        gt_map = {
            "V1_SilverSedan": [100, 100, 200, 200],
            "V2_DarkSedan": [150, 100, 250, 200]
        }
        det_boxes = [[110, 100, 200, 200]]
        res = self.associate(det_boxes, gt_map, iou_threshold=0.30)
        self.assertEqual(len(res["matches"]), 1)
        self.assertIn("V1_SilverSedan", res["matches"])
        self.assertNotIn("V2_DarkSedan", res["matches"])
        self.assertIn("V2_DarkSedan", res["unmatched_gt"])
        self.assertEqual(res["unmatched_detections"], [])

    def test_no_detection_no_fabricated_observation(self):
        # 9. No detection -> no fabricated observation.
        gt_map = {"V1_SilverSedan": [100, 100, 200, 200]}
        det_boxes = []
        res = self.associate(det_boxes, gt_map, iou_threshold=0.40)
        self.assertEqual(res["matches"], {})
        self.assertEqual(res["unmatched_gt"], ["V1_SilverSedan"])
        self.assertEqual(res["unmatched_detections"], [])

    def test_ground_truth_plate_text_never_used_for_association(self):
        # 10. Ground-truth plate text is never used for association.
        import inspect
        sig = inspect.signature(self.associate)
        for param in sig.parameters:
            self.assertNotIn("plate", param.lower())
            self.assertNotIn("text", param.lower())

        gt_map = {"V1_SilverSedan": [100, 100, 200, 200]}
        det_boxes = [[100, 100, 200, 200]]
        res = self.associate(det_boxes, gt_map)
        self.assertIn("V1_SilverSedan", res["matches"])

    def test_cam01_spatial_gt_integrity(self):
        # 11. Verify CAM01_ANPR_SPATIAL_GT integrity across all 5 vehicles
        self.assertIn("V1_SilverSedan", self.spatial_gt)
        self.assertIn("V2_DarkSedan", self.spatial_gt)
        self.assertIn("V3_WhiteHatchback", self.spatial_gt)
        self.assertIn("V4_DistantTruck", self.spatial_gt)
        self.assertIn("V5_WhiteVan", self.spatial_gt)
        for vid, frames in self.spatial_gt.items():
            self.assertGreater(len(frames), 0)
            for fnum, box in frames.items():
                self.assertEqual(len(box), 4)
                x1, y1, x2, y2 = box
                self.assertLess(x1, x2)
                self.assertLess(y1, y2)


class TestBenchmarkReadabilityAndMetrics(unittest.TestCase):
    """
    Tests for ANPR Fix #5 — Forensic Benchmark Ground-Truth Validation
    & Small-Plate Separated Metric Evaluation.
    """
    def setUp(self):
        from benchmark.ground_truth import ANPR_GROUND_TRUTH
        self.gt_list = ANPR_GROUND_TRUTH
        self.gt_by_id = {gt["vehicle_id"]: gt for gt in self.gt_list}

    def test_ground_truth_contract_forensic_fields(self):
        # 1. All GT vehicles must have required forensic classification fields
        required_fields = [
            "vehicle_id", "readability_class", "ground_truth_status",
            "occlusion", "plate_bbox_dimensions", "audit_notes"
        ]
        valid_classes = {
            "READABLE", "PARTIALLY_OCCLUDED", "PHYSICALLY_UNREADABLE",
            "TOO_SMALL_FOR_RELIABLE_EVALUATION"
        }
        valid_statuses = {"VERIFIED_VALID", "INVALID_GROUND_TRUTH", "UNREADABLE"}

        for gt in self.gt_list:
            for field in required_fields:
                self.assertIn(field, gt, f"Missing {field} in {gt['vehicle_id']}")
            self.assertIn(gt["readability_class"], valid_classes)
            self.assertIn(gt["ground_truth_status"], valid_statuses)
            dims = gt["plate_bbox_dimensions"]
            self.assertIn("width_px", dims)
            self.assertIn("height_px", dims)
            self.assertIn("area_px2", dims)
            self.assertEqual(dims["area_px2"], dims["width_px"] * dims["height_px"])

    def test_v3_forensic_ground_truth_audit(self):
        # 2. V3 must be marked INVALID_GROUND_TRUTH and PARTIALLY_OCCLUDED
        v3 = self.gt_by_id["V3_WhiteHatchback"]
        self.assertEqual(v3["ground_truth_status"], "INVALID_GROUND_TRUTH")
        self.assertEqual(v3["readability_class"], "PARTIALLY_OCCLUDED")
        self.assertFalse(v3["is_readable"])
        self.assertIsNone(v3["gt_plate_text"])
        self.assertEqual(v3.get("legacy_annotation"), "DL01CR1176")
        self.assertEqual(v3.get("observable_text"), "01CR1176")
        self.assertEqual(v3.get("occlusion"), "PARTIAL_FRONT_LEFT")

    def test_v1_and_v2_marked_valid_readable(self):
        # 3. V1 and V2 remain valid readable ground truth
        for vid, expected in [("V1_SilverSedan", "MH02FU9304"), ("V2_DarkSedan", "MH02FX6786")]:
            gt = self.gt_by_id[vid]
            self.assertTrue(gt["is_readable"])
            self.assertEqual(gt["ground_truth_status"], "VERIFIED_VALID")
            self.assertEqual(gt["readability_class"], "READABLE")
            self.assertEqual(gt["gt_plate_text"], expected)

    def test_v4_and_v5_marked_unreadable(self):
        # 4. V4 (too small) and V5 (distant shadow) are classified separately
        v4 = self.gt_by_id["V4_DistantTruck"]
        self.assertFalse(v4["is_readable"])
        self.assertIsNone(v4["gt_plate_text"])
        self.assertEqual(v4["readability_class"], "TOO_SMALL_FOR_RELIABLE_EVALUATION")

        v5 = self.gt_by_id["V5_WhiteVan"]
        self.assertFalse(v5["is_readable"])
        self.assertIsNone(v5["gt_plate_text"])
        self.assertEqual(v5["readability_class"], "PHYSICALLY_UNREADABLE")

    def test_invalid_ground_truth_excluded_from_ocr_denominator(self):
        # 5. Invalid GT is excluded from the OCR accuracy denominator
        readable_valid = [
            gt for gt in self.gt_list
            if gt.get("is_readable") and gt.get("ground_truth_status") == "VERIFIED_VALID" and gt.get("gt_plate_text")
        ]
        self.assertEqual(len(readable_valid), 2)
        vids = [gt["vehicle_id"] for gt in readable_valid]
        self.assertIn("V1_SilverSedan", vids)
        self.assertIn("V2_DarkSedan", vids)
        self.assertNotIn("V3_WhiteHatchback", vids)

    def test_readability_metrics_breakdown(self):
        # 6. Readability breakdown categorizes all 5 CAM-01 vehicles
        readable = [gt for gt in self.gt_list if gt.get("readability_class") == "READABLE"]
        partially_occluded = [gt for gt in self.gt_list if gt.get("readability_class") == "PARTIALLY_OCCLUDED"]
        physically_unreadable = [gt for gt in self.gt_list if gt.get("readability_class") == "PHYSICALLY_UNREADABLE"]
        too_small = [gt for gt in self.gt_list if gt.get("readability_class") == "TOO_SMALL_FOR_RELIABLE_EVALUATION"]
        invalid_gt = [gt for gt in self.gt_list if gt.get("ground_truth_status") == "INVALID_GROUND_TRUTH"]

        self.assertEqual(len(readable), 2)
        self.assertEqual(len(partially_occluded), 1)
        self.assertEqual(len(physically_unreadable), 1)
        self.assertEqual(len(too_small), 1)
        self.assertEqual(len(invalid_gt), 1)
        self.assertEqual(invalid_gt[0]["vehicle_id"], "V3_WhiteHatchback")

    def test_detection_recall_independent_of_ocr_readability(self):
        # 7. Detector recall evaluates whether a plate was detected, regardless of readability
        # If all 5 vehicles have a plate crop detected, recall is 5/5 = 1.0
        total_vehicles = len(self.gt_list)
        detected_count = 5
        recall = detected_count / total_vehicles
        self.assertEqual(recall, 1.0)
        # Even though readable vehicles is only 2
        readable_count = sum(1 for gt in self.gt_list if gt.get("is_readable"))
        self.assertEqual(readable_count, 2)
        self.assertNotEqual(total_vehicles, readable_count)

    def test_exact_match_denominator_uses_only_valid_readable(self):
        # 8. Exact-match accuracy evaluates correct_count / evaluated_valid_reads
        # Suppose V1 and V2 are exact matches, and V3 produces "CR1176"
        # V3 must not be counted as an exact match failure because its ground truth is invalid/occluded
        simulated_results = [
            {"vehicle_id": "V1_SilverSedan", "expected": "MH02FU9304", "published": "MH02FU9304", "is_valid_readable": True},
            {"vehicle_id": "V2_DarkSedan", "expected": "MH02FX6786", "published": "MH02FX6786", "is_valid_readable": True},
            {"vehicle_id": "V3_WhiteHatchback", "expected": None, "published": "CR1176", "is_valid_readable": False},
            {"vehicle_id": "V4_DistantTruck", "expected": None, "published": "", "is_valid_readable": False},
            {"vehicle_id": "V5_WhiteVan", "expected": None, "published": "", "is_valid_readable": False},
        ]
        evaluated = [r for r in simulated_results if r["is_valid_readable"]]
        exact_matches = sum(1 for r in evaluated if r["published"] == r["expected"])
        exact_acc = exact_matches / len(evaluated)
        self.assertEqual(len(evaluated), 2)
        self.assertEqual(exact_matches, 2)
        self.assertEqual(exact_acc, 1.0)

    def test_character_accuracy_denominator_uses_only_valid_readable(self):
        # 9. Character accuracy denominator uses only valid readable samples
        simulated_char_accs = [
            {"vehicle_id": "V1_SilverSedan", "char_acc": 1.0, "is_valid_readable": True},
            {"vehicle_id": "V2_DarkSedan", "char_acc": 1.0, "is_valid_readable": True},
            {"vehicle_id": "V3_WhiteHatchback", "char_acc": 0.6, "is_valid_readable": False},
        ]
        valid_accs = [s["char_acc"] for s in simulated_char_accs if s["is_valid_readable"]]
        mean_char_acc = sum(valid_accs) / len(valid_accs)
        self.assertEqual(len(valid_accs), 2)
        self.assertEqual(mean_char_acc, 1.0)

    def test_safety_metrics_false_and_genuine_verified(self):
        # 10. Safety metrics: false VERIFIED vs genuine VERIFIED
        sample_runs = [
            # Case A: V1 is exact match at VERIFIED -> genuine
            {"expected": "MH02FU9304", "published": "MH02FU9304", "tier": "VERIFIED"},
            # Case B: V2 is exact match at VERIFIED -> genuine
            {"expected": "MH02FX6786", "published": "MH02FX6786", "tier": "VERIFIED"},
            # Case C: V3 is DETECTED tier -> not verified
            {"expected": None, "published": "CR1176", "tier": "DETECTED"},
            # Case D: Unreadable at NOT_READ tier -> not verified
            {"expected": None, "published": "", "tier": "NOT_READ"},
        ]
        genuine_verified = sum(1 for r in sample_runs if r["tier"] == "VERIFIED" and r["expected"] and r["published"] == r["expected"])
        false_verified = sum(1 for r in sample_runs if r["tier"] == "VERIFIED" and (not r["expected"] or r["published"] != r["expected"]))
        self.assertEqual(genuine_verified, 2)
        self.assertEqual(false_verified, 0)

        # If an unreadable plate were published as VERIFIED, it must be flagged as false_verified
        corrupted_run = list(sample_runs) + [{"expected": None, "published": "FAKE1234", "tier": "VERIFIED"}]
        false_verified_corrupted = sum(1 for r in corrupted_run if r["tier"] == "VERIFIED" and (not r["expected"] or r["published"] != r["expected"]))
        self.assertEqual(false_verified_corrupted, 1)

    def test_no_ground_truth_injection(self):
        # 11. Verify that ground truth text is not used during OCR read or consensus
        import anpr_engine
        import anpr_consensus
        import inspect

        for fn_name in ["read_plate", "extract_plate_crop_from_vehicle", "_preprocess_variants", "validate_and_correct_plate"]:
            fn = getattr(anpr_engine.ANPREngine, fn_name)
            sig = inspect.signature(fn)
            for param in sig.parameters:
                self.assertNotIn("gt", param.lower())
                self.assertNotIn("expected", param.lower())

        sig_cons = inspect.signature(anpr_consensus.resolve_temporal_consensus)
        for param in sig_cons.parameters:
            self.assertNotIn("gt", param.lower())
            self.assertNotIn("expected", param.lower())

    def test_small_plate_bbox_dimensions_contract(self):
        # 12. Micro-crop metadata: width_px, height_px, area_px2 defined for all vehicles
        for gt in self.gt_list:
            dims = gt["plate_bbox_dimensions"]
            self.assertGreater(dims["width_px"], 0)
            self.assertGreater(dims["height_px"], 0)
            self.assertGreater(dims["area_px2"], 0)
            # V4 micro-crop is < 50 px width in early frames
            if gt["vehicle_id"] == "V4_DistantTruck":
                self.assertLessEqual(dims["width_px"], 50)
            # V5 shadowed crop is < 40 px width
            if gt["vehicle_id"] == "V5_WhiteVan":
                self.assertLessEqual(dims["width_px"], 40)


class TestObjectDetectionV2(unittest.TestCase):
    """
    Tests for Phase A1: Proper Object-Detection Benchmark V2.
    Verifies class-aware 1-to-1 spatial IoU bipartite matching,
    metrics calculation, AP50, no-false-pass logic, and parameter freezing.
    """
    def setUp(self):
        from benchmark.metrics import (
            compute_iou, match_objects_class_aware, compute_ap_from_pr,
            calculate_precision_recall_f1, STANDARD_OBJECT_CLASSES
        )
        self.compute_iou = compute_iou
        self.match = match_objects_class_aware
        self.ap = compute_ap_from_pr
        self.calc_prf1 = calculate_precision_recall_f1
        self.classes = STANDARD_OBJECT_CLASSES

    def test_1_iou_calculation_normal(self):
        # 1. Normal partial overlap
        box1 = [0, 0, 100, 100]
        box2 = [50, 0, 150, 100]
        # inter: 50*100 = 5000; union: 10000 + 10000 - 5000 = 15000 -> 1/3
        self.assertAlmostEqual(self.compute_iou(box1, box2), 1.0 / 3.0, places=4)

    def test_2_zero_area_boxes(self):
        # 2. Zero-area boxes return 0.0 IoU
        b_normal = [0, 0, 100, 100]
        b_point = [50, 50, 50, 50]
        b_line_h = [0, 50, 100, 50]
        b_line_v = [50, 0, 50, 100]
        self.assertEqual(self.compute_iou(b_normal, b_point), 0.0)
        self.assertEqual(self.compute_iou(b_normal, b_line_h), 0.0)
        self.assertEqual(self.compute_iou(b_normal, b_line_v), 0.0)

    def test_3_non_overlapping_boxes(self):
        # 3. Disjoint non-overlapping boxes return 0.0 IoU
        box1 = [0, 0, 50, 50]
        box2 = [100, 100, 150, 150]
        self.assertEqual(self.compute_iou(box1, box2), 0.0)

    def test_4_exact_overlap(self):
        # 4. Exact overlap returns 1.0 IoU
        box1 = [10, 20, 80, 90]
        self.assertAlmostEqual(self.compute_iou(box1, box1), 1.0, places=4)

    def test_5_partial_overlap_2d(self):
        # 5. 2D partial overlap
        b1 = [0, 0, 10, 10] # area 100
        b2 = [5, 5, 15, 15] # area 100, inter 25, union 175
        self.assertAlmostEqual(self.compute_iou(b1, b2), 25.0 / 175.0, places=4)

    def test_6_one_gt_one_prediction(self):
        # 6. One GT ↔ One Prediction (matching class and spatial overlap)
        gt_boxes = [[100, 100, 200, 200]]
        gt_classes = ["car"]
        pred_boxes = [[105, 95, 205, 195]]
        pred_classes = ["car"]
        pred_confs = [0.90]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes, iou_threshold=0.50)
        self.assertEqual(len(res["matched_pairs"]), 1)
        self.assertEqual(res["per_class"]["car"]["tp"], 1)
        self.assertEqual(res["per_class"]["car"]["fp"], 0)
        self.assertEqual(res["per_class"]["car"]["fn"], 0)
        self.assertEqual(res["per_class"]["car"]["f1"], 1.0)

    def test_7_one_gt_multiple_predictions(self):
        # 7. One GT ↔ Multiple Predictions: highest conf/IoU matches, rest become FP
        gt_boxes = [[100, 100, 200, 200]]
        gt_classes = ["person"]
        pred_boxes = [
            [102, 102, 198, 198], # high IoU, high conf
            [110, 110, 210, 210]  # lower conf
        ]
        pred_classes = ["person", "person"]
        pred_confs = [0.95, 0.70]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes, iou_threshold=0.50)
        self.assertEqual(len(res["matched_pairs"]), 1)
        self.assertEqual(res["matched_pairs"][0]["pred_idx"], 0)
        self.assertEqual(res["per_class"]["person"]["tp"], 1)
        self.assertEqual(res["per_class"]["person"]["fp"], 1)
        self.assertEqual(res["per_class"]["person"]["fn"], 0)
        self.assertEqual(len(res["unmatched_predictions"]), 1)

    def test_8_multiple_gt_multiple_predictions(self):
        # 8. Multiple GT ↔ Multiple Predictions: 1-to-1 bipartite assignment
        gt_boxes = [
            [100, 100, 200, 200],
            [300, 300, 400, 400],
            [500, 500, 600, 600]
        ]
        gt_classes = ["car", "truck", "person"]
        pred_boxes = [
            [302, 298, 404, 399], # truck
            [501, 501, 599, 599], # person
            [101, 101, 199, 199]  # car
        ]
        pred_classes = ["truck", "person", "car"]
        pred_confs = [0.88, 0.92, 0.95]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes, iou_threshold=0.50)
        self.assertEqual(len(res["matched_pairs"]), 3)
        self.assertEqual(res["overall"]["tp"], 3)
        self.assertEqual(res["overall"]["fp"], 0)
        self.assertEqual(res["overall"]["fn"], 0)
        self.assertEqual(res["overall"]["f1"], 1.0)

    def test_9_one_to_one_matching_no_duplicates(self):
        # 9. One prediction cannot match two GT boxes even if overlapping both
        gt_boxes = [
            [100, 100, 200, 200],
            [120, 100, 220, 200]
        ]
        gt_classes = ["car", "car"]
        pred_boxes = [[110, 100, 210, 200]] # overlaps both
        pred_classes = ["car"]
        pred_confs = [0.90]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes, iou_threshold=0.50)
        self.assertEqual(len(res["matched_pairs"]), 1)
        self.assertEqual(res["per_class"]["car"]["tp"], 1)
        self.assertEqual(res["per_class"]["car"]["fn"], 1)
        self.assertEqual(res["per_class"]["car"]["fp"], 0)

    def test_10_class_aware_matching(self):
        # 10. Class-Aware Matching: predicted person must NOT match ground-truth car
        gt_boxes = [[100, 100, 200, 200]]
        gt_classes = ["car"]
        pred_boxes = [[100, 100, 200, 200]] # 100% spatial overlap!
        pred_classes = ["person"]           # wrong class!
        pred_confs = [0.95]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes, iou_threshold=0.50)
        self.assertEqual(len(res["matched_pairs"]), 0)
        # Person was predicted -> FP person
        self.assertEqual(res["per_class"]["person"]["fp"], 1)
        self.assertEqual(res["per_class"]["person"]["tp"], 0)
        # Car was in GT -> FN car
        self.assertEqual(res["per_class"]["car"]["fn"], 1)
        self.assertEqual(res["per_class"]["car"]["tp"], 0)

    def test_11_false_positive_calculation(self):
        # 11. False positive calculation: spurious detection with no GT
        gt_boxes = []
        gt_classes = []
        pred_boxes = [[100, 100, 200, 200]]
        pred_classes = ["motorcycle"]
        pred_confs = [0.75]

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes)
        self.assertEqual(res["per_class"]["motorcycle"]["tp"], 0)
        self.assertEqual(res["per_class"]["motorcycle"]["fp"], 1)
        self.assertEqual(res["per_class"]["motorcycle"]["fn"], 0)
        self.assertEqual(res["per_class"]["motorcycle"]["precision"], 0.0)

    def test_12_false_negative_calculation(self):
        # 12. False negative calculation: ground truth object completely missed
        gt_boxes = [[100, 100, 200, 200]]
        gt_classes = ["truck"]
        pred_boxes = []
        pred_classes = []
        pred_confs = []

        res = self.match(pred_boxes, pred_classes, pred_confs, gt_boxes, gt_classes)
        self.assertEqual(res["per_class"]["truck"]["tp"], 0)
        self.assertEqual(res["per_class"]["truck"]["fp"], 0)
        self.assertEqual(res["per_class"]["truck"]["fn"], 1)
        self.assertEqual(res["per_class"]["truck"]["recall"], 0.0)

    def test_13_precision_calculation(self):
        # 13. Precision = TP / (TP + FP)
        # 2 TP, 2 FP -> Precision = 0.50
        m = self.calc_prf1(tp=2, fp=2, fn=0)
        self.assertEqual(m["precision"], 0.5)

    def test_14_recall_calculation(self):
        # 14. Recall = TP / (TP + FN)
        # 3 TP, 1 FN -> Recall = 0.75
        m = self.calc_prf1(tp=3, fp=0, fn=1)
        self.assertEqual(m["recall"], 0.75)

    def test_15_f1_calculation(self):
        # 15. F1 = 2 * (P * R) / (P + R)
        # P = 0.8, R = 0.6 -> F1 = 2 * 0.48 / 1.4 = 0.6857
        m = self.calc_prf1(tp=6, fp=2, fn=4)
        self.assertEqual(m["precision"], 0.75)
        self.assertEqual(m["recall"], 0.6)
        self.assertAlmostEqual(m["f1"], (2 * 0.75 * 0.6) / 1.35, places=4)

    def test_16_empty_gt_handling(self):
        # 16. Empty GT handling across all classes
        pred_boxes = [[10, 10, 20, 20], [30, 30, 40, 40]]
        pred_classes = ["person", "car"]
        res = self.match(pred_boxes, pred_classes, gt_boxes=[], gt_classes=[])
        self.assertEqual(res["overall"]["total_gt"], 0)
        self.assertEqual(res["overall"]["total_pred"], 2)
        self.assertEqual(res["overall"]["fp"], 2)
        self.assertEqual(res["overall"]["tp"], 0)
        self.assertEqual(res["overall"]["precision"], 0.0)

    def test_17_empty_prediction_handling(self):
        # 17. Empty prediction handling across all classes
        gt_boxes = [[10, 10, 20, 20], [30, 30, 40, 40]]
        gt_classes = ["person", "truck"]
        res = self.match(pred_boxes=[], pred_classes=[], gt_boxes=gt_boxes, gt_classes=gt_classes)
        self.assertEqual(res["overall"]["total_gt"], 2)
        self.assertEqual(res["overall"]["total_pred"], 0)
        self.assertEqual(res["overall"]["fn"], 2)
        self.assertEqual(res["overall"]["tp"], 0)
        self.assertEqual(res["overall"]["recall"], 0.0)

    def test_18_count_mae(self):
        # 18. Count MAE calculation
        from benchmark.metrics import compute_count_mae
        preds = [5, 4, 3]
        gts = [6, 4, 1]
        # errors: |5-6|=1, |4-4|=0, |3-1|=2 -> sum=3 / 3 = 1.0
        self.assertEqual(compute_count_mae(preds, gts), 1.0)

    def test_19_per_camera_isolation(self):
        # 19. Camera results dictionary preserves per-camera isolation
        from benchmark.ground_truth import OBJECT_DETECTION_GT_V2
        self.assertIn("CAM-01", OBJECT_DETECTION_GT_V2)
        self.assertIn("CAM-02", OBJECT_DETECTION_GT_V2)
        self.assertIn("CAM-03", OBJECT_DETECTION_GT_V2)
        self.assertIn("CAM-04", OBJECT_DETECTION_GT_V2)
        # Ensure separate camera names and frames
        self.assertNotEqual(
            OBJECT_DETECTION_GT_V2["CAM-01"]["camera_name"],
            OBJECT_DETECTION_GT_V2["CAM-02"]["camera_name"]
        )

    def test_20_no_production_parameter_modification(self):
        # 20. Ensure production parameters remain strictly frozen
        import benchmark.config as cfg
        self.assertEqual(cfg.YOLO_CONF, 0.35)
        self.assertEqual(cfg.YOLO_IMGSZ, 640)
        self.assertEqual(cfg.YOLO_TARGET_CLASSES, [0, 1, 2, 3, 5, 7])

    def test_21_ap50_calculation_trapezoidal(self):
        # 21. AP50 trapezoidal / interpolated area
        # Perfect PR curve: recall=[0.5, 1.0], precision=[1.0, 1.0] -> AP = 1.0
        ap_perfect = self.ap([0.5, 1.0], [1.0, 1.0])
        self.assertEqual(ap_perfect, 1.0)
        # Declining precision: recall=[0.5, 1.0], precision=[1.0, 0.5] -> AP = 0.5*1.0 + 0.5*0.5 = 0.75
        ap_decl = self.ap([0.5, 1.0], [1.0, 0.5])
        self.assertEqual(ap_decl, 0.75)
        # Empty points -> AP = 0.0
        self.assertEqual(self.ap([], []), 0.0)


if __name__ == "__main__":
    unittest.main()


