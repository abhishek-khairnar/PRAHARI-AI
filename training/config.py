"""
PRAHARI-AI — Phase A2 Training Configuration
Reproducible training configuration for domain-specific candidate model evaluation.
"""

import os

# Base paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_YAML = os.path.join(PROJECT_ROOT, "dataset", "data.yaml")
CANDIDATE_WEIGHTS_DIR = os.path.join(PROJECT_ROOT, "weights", "candidates")
BASE_MODEL_PATH = os.path.join(CANDIDATE_WEIGHTS_DIR, "yolov8s.pt")

# Training Hyperparameters
EXPERIMENT_NAME = "prahari_yolov8s_v1"
RANDOM_SEED = 42
IMAGE_SIZE = 640
BATCH_SIZE = 8
EPOCHS = 15
LEARNING_RATE_INIT = 0.005
OPTIMIZER = "AdamW"
WEIGHT_DECAY = 0.0005
PATIENCE = 10
WORKERS = 2
DEVICE = 0  # CUDA device 0 (RTX 3050 6GB)

# Dataset Class Definition
CLASS_NAMES = {
    0: "person",
    1: "car",
    2: "motorcycle",
    3: "truck",
    4: "bus"
}

# Augmentation Strategy for Perimeter Surveillance
AUGMENTATION_CONFIG = {
    "hsv_h": 0.015,
    "hsv_s": 0.4,
    "hsv_v": 0.3,
    "degrees": 0.0,
    "translate": 0.05,
    "scale": 0.2,
    "shear": 0.0,
    "perspective": 0.0,
    "flipud": 0.0,
    "fliplr": 0.5,
    "mosaic": 0.5,
    "mixup": 0.0
}
