import os

BENCHMARK_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BENCHMARK_DIR, ".."))

# Directories
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")
SAMPLES_DIR = os.path.join(BENCHMARK_DIR, "samples")
REPORTS_DIR = os.path.join(BENCHMARK_DIR, "reports")

# Production Model Weights (Read-Only)
YOLO_MODEL_PATH = os.path.join(PROJECT_ROOT, "weights", "yolov8n.pt")
ANPR_MODEL_PATH = os.path.join(PROJECT_ROOT, "weights", "license-plate-finetune-v1n.pt")
YUNET_MODEL_PATH = os.path.join(PROJECT_ROOT, "weights", "face_detection_yunet_2023mar.onnx")

# Video Configurations
DEMO_VIDEOS = {
    "CAM-01": {
        "name": "Border Post Alpha",
        "path": os.path.join(PROJECT_ROOT, "demo_videos", "border_demo.mp4"),
        "line_y_ratio": 0.70
    },
    "CAM-02": {
        "name": "Night Surveillance Bravo",
        "path": os.path.join(PROJECT_ROOT, "demo_videos", "night_demo.mp4"),
        "line_y_ratio": 0.65
    },
    "CAM-03": {
        "name": "Perimeter Activity Charlie",
        "path": os.path.join(PROJECT_ROOT, "demo_videos", "activity-demo.mp4"),
        "line_y_ratio": 0.60
    },
    "CAM-04": {
        "name": "Urban Facility Delta",
        "path": os.path.join(PROJECT_ROOT, "demo_videos", "cctv_demo.mp4"),
        "line_y_ratio": 0.70
    }
}

# Production AI Parameters (Exact source-of-truth)
YOLO_CONF = 0.35
YOLO_IMGSZ = 640
YOLO_TARGET_CLASSES = [0, 1, 2, 3, 5, 7]
VEHICLE_SUBTYPE_CONF = 0.40

TRACKER_MAX_DISAPPEARED = 25
TRACKER_MAX_DISTANCE = 220.0

YUNET_CONSTRUCTOR_CONF = 0.45
YUNET_FILTER_CONF = 0.35
YUNET_INTERVAL = 8

NIGHT_ENTER_THRESHOLD = 85.0
NIGHT_EXIT_THRESHOLD = 98.0
NIGHT_CONFIRM_FRAMES = 25
NIGHT_MOVEMENT_PIXELS = 15
NIGHT_COOLDOWN = 30

LOITERING_TIME_SECONDS = 20
LOITERING_RADIUS_PIXELS = 100
LOITERING_MIN_HITS = 10
LOITERING_COOLDOWN = 30

ANPR_CONF_THRESHOLD = 0.15
ANPR_CONSENSUS_WINDOW = 25.0
ANPR_LEVENSHTEIN_TOLERANCE = 1

# Evaluation Thresholds
IOU_THRESHOLD = 0.50

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
