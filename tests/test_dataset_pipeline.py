"""
PRAHARI-AI — Phase A2 Dataset & Candidate Pipeline Test Suite
Validates:
1. Dataset structure
2. Class mapping definitions
3. Invalid box detection
4. Boundary validation
5. Unknown class detection
6. Missing image detection
7. Missing label detection
8. Train/val/test leakage detection
9. Dataset statistics
10. Reproducible configuration
11. Candidate model artifact verification
12. Benchmark compatibility
13. Production model remains untouched
14. Production parameters remain unchanged
15. Candidate evaluation uses same IoU methodology
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

import unittest
import hashlib
import tempfile
import yaml
import shutil
from ultralytics import YOLO

from dataset.validate_dataset import validate_dataset, CLASS_NAMES
from training.config import (
    DATASET_YAML,
    CANDIDATE_WEIGHTS_DIR,
    BASE_MODEL_PATH,
    IMAGE_SIZE,
    BATCH_SIZE,
    EPOCHS,
    RANDOM_SEED
)
from benchmark.config import (
    YOLO_MODEL_PATH,
    YOLO_CONF,
    YOLO_IMGSZ,
    YOLO_TARGET_CLASSES
)
from benchmark.metrics import match_objects_class_aware, compute_iou

CANONICAL_YOLOV8N_HASH = "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"

def get_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

@unittest.skipUnless(os.path.exists("dataset"), "Local training dataset not present in clone")
class TestDatasetPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists("dataset"):
            return
        cls.dataset_report = validate_dataset("dataset")

    # 1. Dataset structure
    def test_01_dataset_structure(self):
        self.assertTrue(os.path.exists("dataset"), "dataset directory missing")
        self.assertTrue(os.path.exists("dataset/data.yaml"), "dataset/data.yaml missing")
        for split in ["train", "val", "test"]:
            self.assertTrue(os.path.exists(f"dataset/images/{split}"), f"images/{split} missing")
            self.assertTrue(os.path.exists(f"dataset/labels/{split}"), f"labels/{split} missing")

    # 2. Class mapping
    def test_02_class_mapping(self):
        expected = {0: "person", 1: "car", 2: "motorcycle", 3: "truck", 4: "bus"}
        self.assertEqual(CLASS_NAMES, expected)
        with open("dataset/data.yaml", "r") as f:
            y = yaml.safe_load(f)
        self.assertEqual(y["names"], expected)

    # 3. Invalid box detection
    def test_03_invalid_box_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "images", "train"))
            os.makedirs(os.path.join(tmpdir, "labels", "train"))
            # Dummy image
            import cv2
            import numpy as np
            cv2.imwrite(os.path.join(tmpdir, "images", "train", "bad.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
            # Invalid box w=0, h=-0.1
            with open(os.path.join(tmpdir, "labels", "train", "bad.txt"), "w") as f:
                f.write("0 0.5 0.5 0.0 -0.1\n")
            with open(os.path.join(tmpdir, "data.yaml"), "w") as f:
                yaml.dump({"names": CLASS_NAMES}, f)

            rep = validate_dataset(tmpdir)
            self.assertEqual(rep["status"], "FAIL")
            self.assertTrue(any("Invalid box dimensions" in e for e in rep["errors"]))

    # 4. Boundary validation
    def test_04_boundary_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "images", "train"))
            os.makedirs(os.path.join(tmpdir, "labels", "train"))
            import cv2, numpy as np
            cv2.imwrite(os.path.join(tmpdir, "images", "train", "out.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
            # Center > 1.0
            with open(os.path.join(tmpdir, "labels", "train", "out.txt"), "w") as f:
                f.write("0 1.5 0.5 0.2 0.2\n")
            with open(os.path.join(tmpdir, "data.yaml"), "w") as f:
                yaml.dump({"names": CLASS_NAMES}, f)

            rep = validate_dataset(tmpdir)
            self.assertEqual(rep["status"], "FAIL")
            self.assertTrue(any("out of bounds" in e for e in rep["errors"]))

    # 5. Unknown class detection
    def test_05_unknown_class_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "images", "train"))
            os.makedirs(os.path.join(tmpdir, "labels", "train"))
            import cv2, numpy as np
            cv2.imwrite(os.path.join(tmpdir, "images", "train", "unk.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
            # Class 99
            with open(os.path.join(tmpdir, "labels", "train", "unk.txt"), "w") as f:
                f.write("99 0.5 0.5 0.2 0.2\n")
            with open(os.path.join(tmpdir, "data.yaml"), "w") as f:
                yaml.dump({"names": CLASS_NAMES}, f)

            rep = validate_dataset(tmpdir)
            self.assertEqual(rep["status"], "FAIL")
            self.assertTrue(any("Unknown class ID" in e for e in rep["errors"]))

    # 6. Missing image detection
    def test_06_missing_image_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "images", "train"))
            os.makedirs(os.path.join(tmpdir, "labels", "train"))
            # Label without image
            with open(os.path.join(tmpdir, "labels", "train", "orphan.txt"), "w") as f:
                f.write("0 0.5 0.5 0.2 0.2\n")
            with open(os.path.join(tmpdir, "data.yaml"), "w") as f:
                yaml.dump({"names": CLASS_NAMES}, f)

            rep = validate_dataset(tmpdir)
            self.assertEqual(rep["status"], "FAIL")
            self.assertTrue(any("no corresponding image file" in e for e in rep["errors"]))

    # 7. Missing label detection
    def test_07_missing_label_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "images", "train"))
            os.makedirs(os.path.join(tmpdir, "labels", "train"))
            import cv2, numpy as np
            cv2.imwrite(os.path.join(tmpdir, "images", "train", "nolabel.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
            with open(os.path.join(tmpdir, "data.yaml"), "w") as f:
                yaml.dump({"names": CLASS_NAMES}, f)

            rep = validate_dataset(tmpdir)
            self.assertEqual(rep["status"], "FAIL")
            self.assertTrue(any("no corresponding label file" in e for e in rep["errors"]))

    # 8. Train/val/test leakage detection
    def test_08_leakage_detection(self):
        # The true dataset must have zero leakage between train and test
        self.assertEqual(self.dataset_report["status"], "PASS")
        self.assertFalse(any("DATA LEAKAGE DETECTED" in e for e in self.dataset_report["errors"]))

    # 9. Dataset statistics
    def test_09_dataset_statistics(self):
        self.assertGreaterEqual(self.dataset_report["total_images"], 30)
        self.assertGreaterEqual(self.dataset_report["total_objects"], 50)
        self.assertGreaterEqual(self.dataset_report["hard_negatives"], 5)
        for cls_name in ["person", "car", "truck", "motorcycle"]:
            self.assertIn(cls_name, self.dataset_report["class_distribution"])
            self.assertGreater(self.dataset_report["class_distribution"][cls_name], 0)

    # 10. Reproducible configuration
    def test_10_reproducible_configuration(self):
        self.assertEqual(RANDOM_SEED, 42)
        self.assertEqual(IMAGE_SIZE, 640)
        self.assertGreater(BATCH_SIZE, 0)
        self.assertGreater(EPOCHS, 0)
        self.assertTrue(os.path.exists(DATASET_YAML))

    # 11. Candidate model artifact verification
    def test_11_candidate_model_artifact(self):
        cand_path = os.path.join(CANDIDATE_WEIGHTS_DIR, "yolov8s.pt")
        self.assertTrue(os.path.exists(cand_path), f"Candidate model missing at {cand_path}")
        self.assertGreater(os.path.getsize(cand_path), 10_000_000, "Candidate weights file unusually small")

    # 12. Benchmark compatibility
    def test_12_benchmark_compatibility(self):
        # Candidate model loads cleanly in YOLO and can run infer on 640x640 dummy image
        cand_path = os.path.join(CANDIDATE_WEIGHTS_DIR, "yolov8s.pt")
        model = YOLO(cand_path)
        import numpy as np
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        res = model(dummy, conf=0.35, imgsz=640, verbose=False)
        self.assertIsNotNone(res)

    # 13. Production model remains untouched
    def test_13_production_model_untouched(self):
        current_hash = get_file_sha256(YOLO_MODEL_PATH)
        self.assertEqual(current_hash, CANONICAL_YOLOV8N_HASH, "CRITICAL: weights/yolov8n.pt hash mismatch!")

    # 14. Production parameters remain unchanged
    def test_14_production_parameters_unchanged(self):
        self.assertEqual(YOLO_CONF, 0.35)
        self.assertEqual(YOLO_IMGSZ, 640)
        self.assertEqual(YOLO_TARGET_CLASSES, [0, 1, 2, 3, 5, 7])

    # 15. Candidate evaluation uses same IoU methodology
    def test_15_same_iou_methodology(self):
        # Verify match_objects_class_aware handles candidate boxes with strict IoU >= 0.50
        pred_boxes = [[10, 10, 50, 50]]
        gt_boxes = [[10, 10, 50, 50]]
        res = match_objects_class_aware(
            pred_boxes=pred_boxes,
            pred_classes=["truck"],
            pred_confs=[0.8],
            gt_boxes=gt_boxes,
            gt_classes=["truck"],
            iou_threshold=0.50
        )
        self.assertEqual(res["per_class"]["truck"]["tp"], 1)
        self.assertEqual(res["per_class"]["truck"]["f1"], 1.0)

if __name__ == "__main__":
    unittest.main()
