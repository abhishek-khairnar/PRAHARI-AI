"""
PRAHARI-AI — Phase A3.1 Dataset V2 Test Suite
Validates:
1. Dataset V2 directory structure and data.yaml
2. Class ontology mapping (5 classes: person, car, motorcycle, truck, bus)
3. Zero missing images or missing labels
4. Bounding box coordinates normalization and boundaries [0.0, 1.0]
5. Class ID validity [0..4]
6. Strict sequence-level leakage verification (zero split overlap)
7. Hard-negative integrity (substantial collection of empty label files)
8. Priority class distributions (person focus, vehicle representation)
9. Production model SHA256 integrity
10. Production parameters remain frozen
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

import unittest
import hashlib
import yaml
from dataset_v2.validate_dataset import validate_dataset_v2, CLASS_NAMES
from benchmark.config import (
    YOLO_MODEL_PATH,
    YOLO_CONF,
    YOLO_IMGSZ,
    YOLO_TARGET_CLASSES
)

CANONICAL_YOLOV8N_HASH = "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"

def get_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

@unittest.skipUnless(os.path.exists("dataset_v2"), "Local training dataset v2 not present in clone")
class TestDatasetV2Pipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists("dataset_v2"):
            return
        cls.report = validate_dataset_v2("dataset_v2")

    # 1. Dataset structure
    def test_01_dataset_structure(self):
        self.assertTrue(os.path.exists("dataset_v2"), "dataset_v2 directory missing")
        self.assertTrue(os.path.exists("dataset_v2/data.yaml"), "dataset_v2/data.yaml missing")
        self.assertTrue(os.path.exists("dataset_v2/metadata.json"), "dataset_v2/metadata.json missing")
        for split in ["train", "val", "test"]:
            self.assertTrue(os.path.exists(f"dataset_v2/images/{split}"), f"images/{split} missing")
            self.assertTrue(os.path.exists(f"dataset_v2/labels/{split}"), f"labels/{split} missing")

    # 2. Class ontology
    def test_02_class_ontology(self):
        with open("dataset_v2/data.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        names = cfg.get("names", {})
        self.assertEqual(len(names), 5, "Must have exactly 5 classes")
        self.assertEqual(names[0], "person")
        self.assertEqual(names[1], "car")
        self.assertEqual(names[2], "motorcycle")
        self.assertEqual(names[3], "truck")
        self.assertEqual(names[4], "bus")

    # 3. Zero missing images or labels
    def test_03_zero_missing_images_or_labels(self):
        self.assertEqual(self.report["status"], "PASS")
        self.assertEqual(len(self.report["errors"]), 0, f"Errors found: {self.report['errors']}")

    # 4. Total image volume satisfies target (300 - 1000)
    def test_04_target_image_volume(self):
        total_imgs = self.report["total_images"]
        self.assertGreaterEqual(total_imgs, 300, f"Total images {total_imgs} must be >= 300")
        self.assertLessEqual(total_imgs, 1000, f"Total images {total_imgs} must be <= 1000")

    # 5. Strict Sequence Leakage
    def test_05_strict_sequence_leakage(self):
        leakage_info = self.report["sequence_leakage"]
        self.assertFalse(leakage_info["leakage_detected"], "Sequence leakage detected across splits!")
        train_s = set(leakage_info["train_sequences"])
        val_s = set(leakage_info["val_sequences"])
        test_s = set(leakage_info["test_sequences"])
        self.assertEqual(len(train_s.intersection(val_s)), 0, "Train and Val sequence overlap!")
        self.assertEqual(len(train_s.intersection(test_s)), 0, "Train and Test sequence overlap!")
        self.assertEqual(len(val_s.intersection(test_s)), 0, "Val and Test sequence overlap!")

    # 6. Hard-Negative Collection
    def test_06_hard_negative_integrity(self):
        hard_negs = self.report["hard_negatives"]
        self.assertGreaterEqual(hard_negs, 50, f"Hard negatives count {hard_negs} must be >= 50")
        for split in ["train", "val", "test"]:
            lbl_dir = f"dataset_v2/labels/{split}"
            for f in os.listdir(lbl_dir):
                if "hardneg" in f:
                    size = os.path.getsize(os.path.join(lbl_dir, f))
                    self.assertEqual(size, 0, f"Hard negative label {f} must be empty (0 bytes)")

    # 7. Person Priority Focus
    def test_07_person_priority_focus(self):
        class_dist = self.report["class_distribution"]
        self.assertIn("person", class_dist)
        self.assertGreaterEqual(class_dist["person"], 300, "Person instances must be >= 300")
        # Person should be the most represented class
        for c, cnt in class_dist.items():
            if c != "person":
                self.assertGreaterEqual(class_dist["person"], cnt, f"Person ({class_dist['person']}) should exceed {c} ({cnt})")

    # 8. Vehicle Diversity
    def test_08_vehicle_diversity(self):
        class_dist = self.report["class_distribution"]
        self.assertIn("car", class_dist)
        self.assertIn("truck", class_dist)
        self.assertIn("motorcycle", class_dist)
        self.assertGreaterEqual(class_dist["car"], 100, "Car instances must be >= 100")
        self.assertGreaterEqual(class_dist["truck"], 50, "Truck instances must be >= 50")
        self.assertGreaterEqual(class_dist["motorcycle"], 30, "Motorcycle instances must be >= 30")

    # 9. Production Model Integrity
    def test_09_production_model_unchanged(self):
        self.assertTrue(os.path.exists(YOLO_MODEL_PATH), "Production model missing")
        actual_hash = get_file_sha256(YOLO_MODEL_PATH)
        self.assertEqual(actual_hash, CANONICAL_YOLOV8N_HASH, "Production model hash modified!")

    # 10. Production Parameters Frozen
    def test_10_production_parameters_frozen(self):
        self.assertEqual(YOLO_CONF, 0.35, "Production conf must remain 0.35")
        self.assertEqual(YOLO_IMGSZ, 640, "Production imgsz must remain 640")
        self.assertEqual(YOLO_TARGET_CLASSES, [0, 1, 2, 3, 5, 7], "Production classes must remain [0, 1, 2, 3, 5, 7]")

if __name__ == "__main__":
    unittest.main()
