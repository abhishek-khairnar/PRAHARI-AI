"""
PRAHARI-AI Unified Surveillance Stream Engine
Supports multi-source video ingestion (RTSP Streams, Local Video Loops, USB/Integrated Webcams),
Shared GPU Model Registry (YOLOv8n, YuNet Face Detector, ANPR Engine) for bounded VRAM usage,
Independent per-camera tracking, intrusion detection, ANPR, hysteresis night detection,
and robust explainable suspicious activity/loitering detection.
"""

import os
import sys
import math
import time
import datetime
import logging
import threading
import queue
import collections
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from centroid_tracker import CentroidTracker
from anpr_engine import ANPREngine
from database import db_manager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RTSPStreamReader")

# Configurable Virtual Fence line position as percentage of frame height (0.7 = 70% down frame)
FENCE_LINE_PERCENT = 0.7

# ─── Suspicious Activity / Loitering Detection Configuration ───
LOITERING_ENABLED = True
LOITERING_TIME_SECONDS = 20            # Dwell time threshold in seconds to trigger loitering alert
LOITERING_RADIUS_PIXELS = 100          # Max displacement from moving anchor to count as loitering
LOITERING_ALERT_COOLDOWN_SECONDS = 30  # Cooldown per track ID before re-alerting
LOITERING_MIN_HITS = 10                # Minimum consecutive hits required before evaluating dwell

# ─── Night-Time Detection Configuration (Dual-Threshold Hysteresis) ───
NIGHT_DETECTION_ENABLED = True
NIGHT_ENTER_THRESHOLD = 85.0           # Grayscale ambient luminance below this triggers Night mode
NIGHT_EXIT_THRESHOLD = 98.0            # Grayscale ambient luminance above this triggers Day mode
NIGHT_CONFIRM_FRAMES = 25              # Consecutive frames required for state confirmation
NIGHT_ALERT_COOLDOWN_SECONDS = 30      # Cooldown per object for night movement alerts
NIGHT_MOVEMENT_THRESHOLD_PIXELS = 15   # Minimum centroid displacement to count as moving at night

# ─── Face Detection Configuration ───
FACE_DETECTION_ENABLED = True
FACE_DETECTION_INTERVAL = 8            # Run face detection every N frames (amortized <2ms overhead)


class ModelRegistry:
    """
    Singleton AI Model Registry to share model weights in GPU VRAM across multiple camera instances.
    Guarantees that 4+ cameras use ~250MB total VRAM without duplicating model instances.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelRegistry, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.yolo_model = None
        self.yolo_infer_lock = threading.Lock()
        self.anpr_engine = None
        self.face_detector = None
        self.face_infer_lock = threading.Lock()
        self._init_models()
        self._initialized = True

    def _init_models(self):
        logger.info(f"[ModelRegistry] Initializing shared AI models on device: {self.device.upper()}")
        if self.device == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
        
        # 1. Shared YOLO Object Detector
        try:
            model_path = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
            if not os.path.exists(model_path):
                model_path = "yolov8n.pt"
            self.yolo_model = YOLO(model_path)
            logger.info(f"[ModelRegistry] Shared YOLOv8n detector loaded successfully on {self.device.upper()}")
        except Exception as e:
            logger.error(f"[ModelRegistry] Error loading YOLO model: {e}")
            try:
                self.yolo_model = YOLO("yolov8n.pt")
            except Exception as e2:
                logger.error(f"[ModelRegistry] Fallback YOLO loading failed: {e2}")

        # 2. Shared ANPR Engine
        try:
            self.anpr_engine = ANPREngine()
            logger.info("[ModelRegistry] Shared ANPR Engine initialized successfully")
        except Exception as e:
            logger.error(f"[ModelRegistry] Error loading ANPR Engine: {e}")

        # 3. Shared YuNet Face Detector
        if FACE_DETECTION_ENABLED:
            yunet_model_path = os.path.join(os.path.dirname(__file__), "weights", "face_detection_yunet_2023mar.onnx")
            if os.path.exists(yunet_model_path):
                try:
                    self.face_detector = cv2.FaceDetectorYN_create(
                        yunet_model_path, "", (640, 360), 0.45, 0.3, 5000
                    )
                    logger.info(f"[ModelRegistry] Shared YuNet Face Detector loaded from {yunet_model_path}")
                except Exception as e:
                    logger.warning(f"[ModelRegistry] YuNet loading failed: {e}")
            else:
                logger.warning(f"[ModelRegistry] YuNet model file not found at {yunet_model_path}")


# Global Singleton Model Registry
model_registry = ModelRegistry()


class RTSPStreamReader:
    """
    High-Performance, Isolated Stream Ingestion & AI Pipeline for a single camera source.
    Supports RTSP streams, local video files (with seamless loop), and live webcams.
    """
    PERSON_CLASS = 0
    VEHICLE_CLASSES = {
        1: "vehicle",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }
    TARGET_CLASS_IDS = [0, 1, 2, 3, 5, 7]
    VEHICLE_SUBTYPE_CONFIDENCE_THRESHOLD = 0.40

    def __init__(
        self,
        rtsp_url: str = "rtsp://localhost:8554/mystream",
        camera_id: str = "CAM-01",
        camera_name: str = "Border Post Alpha",
        source_type: str = None,
        fps_log_interval: float = 3.0,
        model_name: str = "yolov8n.pt",
        line_y_ratio: float = None,
        vehicle_subtype_conf: float = 0.40
    ):
        self.rtsp_url = rtsp_url
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.fps_log_interval = fps_log_interval
        self.line_y_ratio = line_y_ratio if line_y_ratio is not None else FENCE_LINE_PERCENT
        self.vehicle_subtype_conf = vehicle_subtype_conf

        # Auto-detect source type if not explicitly supplied
        if source_type is not None:
            self.source_type = source_type
        else:
            url_str = str(rtsp_url).strip()
            if isinstance(rtsp_url, int) or url_str.isdigit():
                self.source_type = "webcam"
            elif url_str.startswith(("rtsp://", "http://", "https://")):
                self.source_type = "rtsp"
            else:
                self.source_type = "video_file"

        self.is_connected = False
        self.status = "INITIALIZING"
        self.running = False
        self.latest_jpeg = None
        self.frame_count = 0
        self.current_fps = 0.0
        self.capture_fps = 0.0
        self.error_state = None
        self.last_frame_time = 0.0

        # Detection metrics
        self.people_count = 0
        self.vehicle_count = 0
        self.total_objects = 0

        # Database Manager
        self.db = db_manager

        # Shared Models
        self.registry = model_registry
        self.device = self.registry.device

        # Per-Camera Isolated Centroid Tracker
        self.tracker = CentroidTracker(max_disappeared=25, max_distance=220.0)
        self.alerted_object_ids = set()
        self.alerts = self.db.get_recent_intrusions(limit=50, camera_id=self.camera_id)
        self.total_alerts_count = len(self.alerts)
        self.recent_alerts = []  # List of (cx, cy, timestamp_float)

        # Per-Camera ANPR State
        self.anpr_logs = self.db.get_recent_anpr(limit=50, camera_id=self.camera_id)
        self.anpr_cooldowns = {}
        self.total_anpr_count = len(self.anpr_logs)
        self.anpr_queue = queue.Queue(maxsize=10)
        self.anpr_queued_ids = set()
        self.anpr_in_progress = set()
        self.db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"DB-{self.camera_id}")
        self._anpr_worker_thread = None

        # Per-Track Temporal Vehicle Ring Buffer
        self.vehicle_frame_buffer = collections.defaultdict(lambda: collections.deque(maxlen=10))
        self.vehicle_ocr_history = collections.defaultdict(list)
        self.vehicle_published_plate = {}

        # ANPR Debug candidate crop storage
        self.anpr_debug_crops = []
        self.anpr_attempt_cooldowns = {}
        self.total_anpr_debug_count = 0

        # Profiling Metrics
        self.total_anpr_detector_calls = 0
        self.total_anpr_ocr_calls = 0
        self.profile_accum = {
            "detect_ms": 0.0,
            "track_ms": 0.0,
            "anpr_ms": 0.0,
            "face_ms": 0.0,
            "loiter_ms": 0.0,
            "night_ms": 0.0,
            "draw_ms": 0.0,
            "encode_ms": 0.0,
            "frames": 0,
            "detector_calls": 0,
            "ocr_calls": 0
        }

        # Live Session Counters
        self.session_alerts_count = 0
        self.session_anpr_count = 0
        self.session_suspicious_count = 0
        self.session_night_count = 0

        # Loitering / Suspicious Activity State
        self.loitering_state = {}
        self.suspicious_alerts = []
        self.total_suspicious_count = 0

        # Night Detection State (Hysteresis)
        self.is_night_mode = False
        self.night_state_str = "DAY"
        self.night_brightness_history = collections.deque(maxlen=NIGHT_CONFIRM_FRAMES)
        self.night_alerted_ids = {}
        self.total_night_alerts = 0
        self.current_brightness = 0.0

        # Face Detection State
        self.face_count = 0
        self.face_frame_counter = 0
        self.face_rects_cache = []

        # Video Loop & Scene Discontinuity Detection
        self._prev_gray_thumb = None
        self._loop_cooldown = 0.0
        self._cross_loop_signatures = {}

        # Snapshot Directories
        self.alerts_dir = os.path.join(os.path.dirname(__file__), "static", "alerts")
        os.makedirs(self.alerts_dir, exist_ok=True)
        self.anpr_dir = os.path.join(os.path.dirname(__file__), "static", "anpr")
        os.makedirs(self.anpr_dir, exist_ok=True)
        self.anpr_debug_dir = os.path.join(os.path.dirname(__file__), "static", "anpr_debug")
        os.makedirs(self.anpr_debug_dir, exist_ok=True)

        # Thread Locks
        self._raw_frame_lock = threading.Lock()
        self.raw_frame = None
        self.raw_frame_id = 0
        self.raw_frame_res = None

        self._frame_lock = threading.Lock()  # Exclusively for latest_jpeg swap
        self._state_lock = threading.Lock()  # Exclusively for state lists & metrics

        self._grabber_thread = None
        self._ai_thread = None
        self._anpr_worker_thread = None

    def start(self):
        """Starts the background frame grabber, AI processing, and ANPR worker threads."""
        if self.running:
            return
        self.running = True
        self.status = "CONNECTING"
        
        # Ensure fresh db executor on startup/restart
        if self.db_executor is None or getattr(self.db_executor, "_shutdown", False):
            self.db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"DB-{self.camera_id}")

        self._safe_db_submit(self.db.log_system_event, "camera_started", f"Camera {self.camera_id} ({self.camera_name}) started on {self.rtsp_url}")
        
        self._grabber_thread = threading.Thread(target=self._frame_grabber_loop, daemon=True, name=f"Grabber-{self.camera_id}")
        self._ai_thread = threading.Thread(target=self._ai_processing_loop, daemon=True, name=f"AI-{self.camera_id}")
        self._anpr_worker_thread = threading.Thread(target=self._anpr_worker_loop, daemon=True, name=f"ANPR-{self.camera_id}")

        self._grabber_thread.start()
        self._ai_thread.start()
        self._anpr_worker_thread.start()
        logger.info(f"Camera [{self.camera_id}] ({self.camera_name}) started. Source: {self.source_type} ({self.rtsp_url})")

    def _safe_db_submit(self, fn, *args):
        """Safely submits a database write task to the thread pool executor without raising on shutdown."""
        if not self.running:
            return
        try:
            if self.db_executor and not getattr(self.db_executor, "_shutdown", False):
                self.db_executor.submit(fn, *args)
        except Exception:
            pass

    def stop(self):
        """Stops the camera reader cleanly."""
        self.running = False
        self.status = "OFFLINE"
        self.is_connected = False
        self._safe_db_submit(self.db.log_system_event, "camera_stopped", f"Camera {self.camera_id} stopped")
        
        # Stop worker threads first before shutting down executor
        if self._anpr_worker_thread and self._anpr_worker_thread.is_alive():
            self._anpr_worker_thread.join(timeout=1.5)
        if self._grabber_thread and self._grabber_thread.is_alive():
            self._grabber_thread.join(timeout=1.5)
        if self._ai_thread and self._ai_thread.is_alive():
            self._ai_thread.join(timeout=1.5)
        try:
            self.db_executor.shutdown(wait=False)
        except Exception:
            pass
        logger.info(f"Camera [{self.camera_id}] stopped.")

    def _resolve_source_path(self, source_path: str) -> str:
        """Resolves relative file paths, including fallback aliases (e.g. activity-demo vs activity_demo)."""
        if os.path.isabs(source_path) and os.path.exists(source_path):
            return source_path

        base_dir = os.path.dirname(__file__)
        candidate = os.path.join(base_dir, source_path)
        if os.path.exists(candidate):
            return candidate

        # Try looking inside demo_videos
        demo_candidate = os.path.join(base_dir, "demo_videos", os.path.basename(source_path))
        if os.path.exists(demo_candidate):
            return demo_candidate

        # Try hyphen / underscore substitutions
        alt_name = os.path.basename(source_path).replace("_", "-")
        alt_candidate = os.path.join(base_dir, "demo_videos", alt_name)
        if os.path.exists(alt_candidate):
            return alt_candidate

        alt_name2 = os.path.basename(source_path).replace("-", "_")
        alt_candidate2 = os.path.join(base_dir, "demo_videos", alt_name2)
        if os.path.exists(alt_candidate2):
            return alt_candidate2

        return source_path

    def _create_placeholder_frame(self, text: str) -> bytes:
        """Generates a dark placeholder image with custom text encoded as JPEG."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Header banner
        cv2.rectangle(img, (0, 0), (640, 40), (15, 23, 42), -1)
        cv2.putText(img, f"PRAHARI-AI | {self.camera_id} - {self.camera_name}", (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 229, 255), 1, cv2.LINE_AA)
        
        # Center message
        cv2.putText(
            img, text, (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 165, 255), 2, cv2.LINE_AA
        )
        ret, jpeg = cv2.imencode('.jpg', img)
        return jpeg.tobytes() if ret else b''

    def _save_alert_snapshot(
        self,
        frame: np.ndarray,
        object_id: int,
        object_type: str,
        timestamp_str: str,
        direction: str = "IN",
        bbox: tuple = None,
        centroid: tuple = None,
        line_y: int = None
    ) -> str:
        """Saves high-quality annotated frame snapshot image asynchronously when an alert occurs."""
        safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
        filename = f"{self.camera_id}_intrusion_{safe_ts}_id{object_id}.jpg"
        filepath = os.path.join(self.alerts_dir, filename)

        annotated = frame.copy()
        h, w = annotated.shape[:2]

        if line_y is not None:
            cv2.line(annotated, (0, line_y), (w, line_y), (0, 0, 255), 2)
            fence_txt = f"{self.camera_id} VIRTUAL FENCE LINE (Y={line_y})"
            cv2.putText(annotated, fence_txt, (15, max(20, line_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        if bbox:
            x1, y1, x2, y2 = bbox
            color = (0, 230, 115) if object_type == "Person" else (0, 165, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
            if centroid:
                cv2.circle(annotated, centroid, 6, (0, 0, 255), -1)

            badge_text = f"BREACH: {self.camera_id} ID #{object_id} {object_type} [{direction}]"
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), (0, 0, 200), -1)
            cv2.putText(annotated, badge_text, (x1 + 4, max(th + 2, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        header = f"PRAHARI-AI | {self.camera_id} | INTRUSION EVENT | {object_type.upper()} ID #{object_id} [{direction}] | {timestamp_str}"
        (hw, hh), _ = cv2.getTextSize(header, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(annotated, (0, 0), (w, hh + 16), (15, 23, 42), -1)
        cv2.putText(annotated, header, (15, hh + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 229, 255), 2, cv2.LINE_AA)

        self._safe_db_submit(cv2.imwrite, filepath, annotated)
        return filename

    def _save_anpr_snapshot(self, plate_crop, object_id: int, timestamp_str: str) -> str:
        """Saves cropped license plate image to static/anpr/."""
        safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
        filename = f"{self.camera_id}_plate_{safe_ts}_id{object_id}.jpg"
        filepath = os.path.join(self.anpr_dir, filename)
        cv2.imwrite(filepath, plate_crop)
        return filename

    def _save_anpr_debug_crop(self, plate_crop, object_id: int, timestamp_str: str, is_detected: bool = True) -> str:
        """Saves cropped plate region detected by the YOLO plate detector for visual debugging."""
        safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
        crop_type = "plate_detected" if is_detected else "candidate"
        self.total_anpr_debug_count += 1
        filename = f"{self.camera_id}_crop_{safe_ts}_id{object_id}_#{self.total_anpr_debug_count}_{crop_type}.jpg"
        filepath = os.path.join(self.anpr_debug_dir, filename)
        cv2.imwrite(filepath, plate_crop)

        debug_record = {
            "id": self.total_anpr_debug_count,
            "camera_id": self.camera_id,
            "vehicle_id": object_id,
            "crop_type": crop_type,
            "timestamp": timestamp_str,
            "snapshot_url": f"/anpr_debug/{filename}",
            "snapshot_filename": filename
        }

        with self._state_lock:
            self.anpr_debug_crops.append(debug_record)
            if len(self.anpr_debug_crops) > 50:
                oldest = self.anpr_debug_crops.pop(0)
                old_path = os.path.join(self.anpr_debug_dir, oldest["snapshot_filename"])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
        return filename

    def _anpr_worker_loop(self):
        """Dedicated single background worker daemon processing ANPR from bounded queue without starving AI loop."""
        while self.running:
            try:
                job = self.anpr_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if job is None:
                continue

            obj_id, cls_name, candidate_crops, now_str, now_ts = job
            try:
                self._async_anpr_ocr_worker(obj_id, cls_name, candidate_crops, now_str, now_ts)
            except Exception as e:
                logger.error(f"[{self.camera_id}] Error in ANPR worker for vehicle #{obj_id}: {e}")
            finally:
                with self._state_lock:
                    self.anpr_queued_ids.discard(obj_id)
                self.anpr_queue.task_done()

    def _enqueue_anpr_job(self, obj_id: int, cls_name: str, candidate_crops: list, now_str: str, now_ts: float):
        """Enqueues an ANPR task into bounded queue with track-level deduplication and oldest-drop on saturation."""
        with self._state_lock:
            if obj_id in self.anpr_queued_ids or obj_id in self.anpr_in_progress:
                return
            self.anpr_queued_ids.add(obj_id)

        try:
            self.anpr_queue.put_nowait((obj_id, cls_name, candidate_crops, now_str, now_ts))
        except queue.Full:
            try:
                dropped = self.anpr_queue.get_nowait()
                with self._state_lock:
                    self.anpr_queued_ids.discard(dropped[0])
                self.anpr_queue.put_nowait((obj_id, cls_name, candidate_crops, now_str, now_ts))
            except Exception:
                with self._state_lock:
                    self.anpr_queued_ids.discard(obj_id)

    def _async_anpr_ocr_worker(self, obj_id: int, cls_name: str, candidate_crops: list, now_str: str, now_ts: float):
        """Asynchronously processes plate candidates, OCR variants, consensus, and links to intrusion alert."""
        if not self.registry.anpr_engine:
            return

        self.anpr_in_progress.add(obj_id)
        try:
            best_plate_found = None
            best_conf_found = 0.0
            best_valid_found = False
            best_tier_found = 0
            best_crop_found = None

            for item in candidate_crops:
                v_crop = item[0]
                c_ts = item[4] if len(item) > 4 else now_ts

                self.total_anpr_detector_calls += 1
                self.profile_accum["detector_calls"] += 1

                plate_crop, is_detected, det_conf = self.registry.anpr_engine.extract_plate_crop_from_vehicle(v_crop, conf_threshold=0.15)
                if not is_detected or plate_crop is None:
                    continue

                self._save_anpr_debug_crop(plate_crop, obj_id, now_str, is_detected=True)

                self.total_anpr_ocr_calls += 1
                self.profile_accum["ocr_calls"] += 1
                cleaned_text, raw_text, ocr_conf, is_valid_fmt, tier = self.registry.anpr_engine.read_plate(plate_crop)

                if cleaned_text and len(cleaned_text) >= 4:
                    self.vehicle_ocr_history[obj_id].append((cleaned_text, raw_text, ocr_conf, is_valid_fmt, tier, c_ts, plate_crop))

            # Temporal Consensus across observations
            recent_obs = [obs for obs in self.vehicle_ocr_history[obj_id] if (now_ts - obs[5]) <= 25.0]
            if recent_obs:
                candidate_groups = {}
                for obs in recent_obs:
                    c_text, r_text, conf, valid, t_tier, ts, p_crop = obs
                    found_group = False
                    for g_key in list(candidate_groups.keys()):
                        if c_text == g_key or (len(c_text) == len(g_key) and sum(1 for a, b in zip(c_text, g_key) if a != b) <= 1):
                            candidate_groups[g_key].append(obs)
                            found_group = True
                            break
                    if not found_group:
                        candidate_groups[c_text] = [obs]

                best_group_key = None
                best_group_score = 0.0
                for g_key, g_obs in candidate_groups.items():
                    score = sum(obs[2] * (1.6 if obs[3] else 0.8) for obs in g_obs)
                    if score > best_group_score:
                        best_group_score = score
                        best_group_key = g_key

                if best_group_key and best_group_score > 0.0:
                    group_obs = candidate_groups[best_group_key]
                    best_obs = max(group_obs, key=lambda o: o[2])
                    best_plate_found = best_obs[0]
                    best_conf_found = best_obs[2]
                    best_valid_found = best_obs[3]
                    best_tier_found = best_obs[4]
                    best_crop_found = best_obs[6]

            # Publication & Database linkage
            if best_plate_found and best_conf_found >= 0.25:
                prev_pub = self.vehicle_published_plate.get(obj_id)
                should_publish = False
                if prev_pub is None:
                    should_publish = True
                else:
                    prev_text, prev_conf = prev_pub
                    if best_conf_found > (prev_conf + 0.15) and best_valid_found:
                        should_publish = True

                if should_publish:
                    is_loop_duplicate = any(
                        k[0] == "anpr" and k[1] == best_plate_found and (now_ts - ts) < 25.0
                        for k, ts in self._cross_loop_signatures.items()
                    )
                    self.vehicle_published_plate[obj_id] = (best_plate_found, best_conf_found)
                    self.anpr_cooldowns[obj_id] = now_ts
                    self._cross_loop_signatures[("anpr", best_plate_found)] = now_ts

                    if not is_loop_duplicate:
                        plate_fn = self._save_anpr_snapshot(best_crop_found, obj_id, now_str)
                        plate_url = f"/anpr/{plate_fn}"
                        if best_valid_found and best_conf_found >= 0.45:
                            val_status = "VERIFIED"
                            is_verified = True
                        elif best_valid_found and best_conf_found >= 0.30:
                            val_status = "DETECTED"
                            is_verified = False
                        elif best_conf_found >= 0.20:
                            val_status = "LOW_CONFIDENCE"
                            is_verified = False
                        else:
                            val_status = "NOT_READ"
                            is_verified = False

                        with self._state_lock:
                            self.total_anpr_count += 1
                            self.session_anpr_count += 1
                            anpr_record = {
                                "id": self.total_anpr_count,
                                "event_type": "anpr",
                                "camera_id": self.camera_id,
                                "vehicle_id": obj_id,
                                "object_id": obj_id,
                                "vehicle_type": cls_name,
                                "object_type": cls_name,
                                "plate_text": best_plate_found,
                                "confidence": round(float(best_conf_found), 2),
                                "is_verified": is_verified,
                                "validation_status": val_status,
                                "timestamp": now_str,
                                "snapshot_url": plate_url,
                                "snapshot_filename": plate_fn
                            }
                            self.anpr_logs.append(anpr_record)
                            if len(self.anpr_logs) > 50:
                                self.anpr_logs.pop(0)

                            # Link to matching Intrusion Record
                            for alert in reversed(self.alerts):
                                if alert.get("object_id") == obj_id:
                                    alert["plate_text"] = best_plate_found
                                    alert["plate_confidence"] = best_conf_found
                                    alert["anpr_status"] = val_status
                                    alert["validation_status"] = val_status
                                    break

                        self._safe_db_submit(
                            self.db.log_anpr_event,
                            now_str,
                            cls_name,
                            obj_id,
                            best_plate_found,
                            best_conf_found,
                            plate_fn,
                            self.camera_id,
                            val_status
                        )
                        self._safe_db_submit(
                            self.db.update_intrusion_anpr,
                            obj_id,
                            best_plate_found,
                            best_conf_found,
                            val_status,
                            self.camera_id
                        )

                        status_tag = val_status
                        logger.info(
                            f"🚘 [{self.camera_id} ANPR] Vehicle #{obj_id} ({cls_name}) -> Plate: '{best_plate_found}' (Conf: {best_conf_found*100:.0f}% | {status_tag})"
                        )
            else:
                with self._state_lock:
                    for alert in reversed(self.alerts):
                        if alert.get("object_id") == obj_id and alert.get("plate_text") == "ANALYZING...":
                            alert["plate_text"] = "PLATE NOT READ"
                            alert["anpr_status"] = "NOT_READ"
                            alert["validation_status"] = "NOT_READ"
                            break
                self._safe_db_submit(
                    self.db.update_intrusion_anpr,
                    obj_id,
                    "PLATE NOT READ",
                    0.0,
                    "NOT_READ",
                    self.camera_id
                )
        except Exception as e:
            logger.error(f"[{self.camera_id}] Error in async ANPR OCR worker for vehicle #{obj_id}: {e}")
        finally:
            self.anpr_in_progress.discard(obj_id)

    def _process_frame_ai(self, frame):
        """Runs YOLO object detection, centroid tracking, line-crossing check, loitering, night detection, face detection, and visual overlays."""
        if frame.shape[1] > 1920 or frame.shape[0] > 1080:
            scale = min(1920.0 / frame.shape[1], 1080.0 / frame.shape[0])
            frame = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)

        clean_frame = frame
        h, w = frame.shape[:2]
        line_y = int(h * self.line_y_ratio)
        now_ts = time.time()

        # Clean cross-loop signatures and temporal history
        self._cross_loop_signatures = {k: v for k, v in self._cross_loop_signatures.items() if (now_ts - v) <= 45.0}
        for vid in list(self.vehicle_ocr_history.keys()):
            self.vehicle_ocr_history[vid] = [obs for obs in self.vehicle_ocr_history[vid] if (now_ts - obs[5]) <= 45.0]
            if len(self.vehicle_ocr_history[vid]) == 0:
                del self.vehicle_ocr_history[vid]

        # ─── 0a. Scene Discontinuity & Video Loop Detection ───
        gray_for_brightness = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_thumb = cv2.resize(gray_for_brightness, (64, 36))
        if self._prev_gray_thumb is not None and (now_ts - self._loop_cooldown) > 8.0:
            diff = cv2.absdiff(gray_thumb, self._prev_gray_thumb)
            mean_diff = float(cv2.mean(diff)[0])
            if mean_diff > 85.0:
                logger.info(f"🔄 [{self.camera_id} LOOP DETECTED] Scene discontinuity diff={mean_diff:.1f}. Resetting active tracking state.")
                self.tracker.reset()
                self.alerted_object_ids.clear()
                self.recent_alerts.clear()
                self.loitering_state.clear()
                self.night_alerted_ids.clear()
                self.face_rects_cache.clear()
                for sig in list(self._cross_loop_signatures.keys()):
                    self._cross_loop_signatures[sig] = now_ts
                self._loop_cooldown = now_ts
        self._prev_gray_thumb = gray_thumb

        # ─── 0b. Night-Time Brightness Detection (Dual-Threshold Hysteresis) ───
        t0_night = time.perf_counter()
        if NIGHT_DETECTION_ENABLED:
            mean_b = float(cv2.mean(gray_thumb)[0])
            med_b = float(np.median(gray_thumb))
            effective_brightness = round(0.5 * mean_b + 0.5 * med_b, 1)
            self.current_brightness = effective_brightness
            self.night_brightness_history.append(effective_brightness)

            if len(self.night_brightness_history) >= 15:
                avg_b = sum(self.night_brightness_history) / len(self.night_brightness_history)
                if not self.is_night_mode and avg_b <= NIGHT_ENTER_THRESHOLD:
                    self.is_night_mode = True
                    self.night_state_str = "NIGHT"
                elif self.is_night_mode and avg_b >= NIGHT_EXIT_THRESHOLD:
                    self.is_night_mode = False
                    self.night_state_str = "DAY"
                else:
                    self.night_state_str = "NIGHT" if self.is_night_mode else "DAY"
        t_night = (time.perf_counter() - t0_night) * 1000.0

        # ─── 1. Run YOLO inference on Shared Model Registry ───
        t0 = time.perf_counter()
        detections = []
        if self.registry.yolo_model is not None:
            with self.registry.yolo_infer_lock:
                with torch.inference_mode():
                    results = self.registry.yolo_model.predict(
                        source=frame,
                        imgsz=640,
                        classes=self.TARGET_CLASS_IDS,
                        conf=0.35,
                        device=self.device,
                        verbose=False
                    )

            if results and len(results) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                    if cls_id == self.PERSON_CLASS:
                        cls_name = "Person"
                    elif cls_id in self.VEHICLE_CLASSES:
                        if conf >= self.vehicle_subtype_conf:
                            cls_name = self.VEHICLE_CLASSES[cls_id].capitalize()
                        else:
                            cls_name = "Vehicle"
                    else:
                        cls_name = "Vehicle"

                    detections.append((x1, y1, x2, y2, cls_name, conf))
        t_detect = (time.perf_counter() - t0) * 1000.0

        # ─── 2. Update Centroid Tracker & State ───
        t0 = time.perf_counter()
        tracked_objects = self.tracker.update(detections)

        # Real-time object count strictly derived from valid current-frame detections
        p_count = sum(1 for d in detections if d[4] == "Person")
        v_count = sum(1 for d in detections if d[4] != "Person")

        with self._state_lock:
            self.people_count = p_count
            self.vehicle_count = v_count
            self.total_objects = p_count + v_count

        self.recent_alerts = [(ax, ay, at) for (ax, ay, at) in self.recent_alerts if (now_ts - at) <= 4.0]
        active_ids = set(tracked_objects.keys())

        stale_loiter_ids = [oid for oid in self.loitering_state if oid not in active_ids]
        for oid in stale_loiter_ids:
            del self.loitering_state[oid]
        stale_night_ids = [oid for oid in self.night_alerted_ids if oid not in active_ids]
        for oid in stale_night_ids:
            del self.night_alerted_ids[oid]
        stale_buffer_ids = [vid for vid in list(self.vehicle_frame_buffer.keys()) if vid not in active_ids]
        for vid in stale_buffer_ids:
            del self.vehicle_frame_buffer[vid]

        # Vehicle frame buffer sampling
        for obj_id, obj in tracked_objects.items():
            cls_name = obj["class"]
            (x1, y1, x2, y2) = obj["bbox"]
            bw = x2 - x1
            bh = y2 - y1
            if cls_name != "Person" and bw >= 30 and bh >= 20:
                buf = self.vehicle_frame_buffer[obj_id]
                if len(buf) < 3 or (self.frame_count % 3 == 0):
                    pad_x = max(10, int(bw * 0.12))
                    pad_y = max(8, int(bh * 0.15))
                    cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
                    cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
                    v_crop = clean_frame[cy1:cy2, cx1:cx2].copy()
                    gray_c = cv2.cvtColor(v_crop, cv2.COLOR_BGR2GRAY)
                    sharp = float(cv2.Laplacian(gray_c, cv2.CV_16S).var())
                    buf.append((v_crop, (x1, y1, x2, y2), obj["confidence"], sharp, now_ts))

        # ─── 3. Intrusion Evaluation ───
        for obj_id, obj in tracked_objects.items():
            cls_name = obj["class"]
            conf = obj["confidence"]
            (x1, y1, x2, y2) = obj["bbox"]
            (cx, cy) = obj["centroid"]

            is_new_intrusion, direction = self.tracker.check_intrusion_crossing(obj_id, line_y)

            if is_new_intrusion and (obj_id not in self.alerted_object_ids):
                self.alerted_object_ids.add(obj_id)
                self.recent_alerts.append((cx, cy, now_ts))
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                snapshot_fn = self._save_alert_snapshot(
                    clean_frame, obj_id, cls_name, now_str, direction=direction, bbox=(x1, y1, x2, y2), centroid=(cx, cy), line_y=line_y
                )
                snapshot_url = f"/alerts/{snapshot_fn}"

                self.total_alerts_count += 1
                self.session_alerts_count += 1

                init_plate = "ANALYZING..." if cls_name != "Person" else "N/A"
                init_status = "PENDING" if cls_name != "Person" else "NOT_APPLICABLE"

                alert_record = {
                    "id": self.total_alerts_count,
                    "event_type": "intrusion",
                    "camera_id": self.camera_id,
                    "object_id": obj_id,
                    "object_type": cls_name,
                    "direction": direction,
                    "plate_text": init_plate,
                    "plate_confidence": 0.0,
                    "anpr_status": init_status,
                    "validation_status": "DETECTED",
                    "timestamp": now_str,
                    "snapshot_url": snapshot_url,
                    "snapshot_filename": snapshot_fn
                }

                with self._state_lock:
                    self.alerts.append(alert_record)
                    if len(self.alerts) > 50:
                        self.alerts.pop(0)

                self._safe_db_submit(
                    self.db.log_intrusion_event,
                    now_str,
                    cls_name,
                    obj_id,
                    snapshot_fn,
                    self.camera_id,
                    direction,
                    init_plate,
                    0.0,
                    init_status,
                    "DETECTED"
                )

                logger.warning(
                    f"🚨 [{self.camera_id} INTRUSION] ID #{obj_id} ({cls_name}) crossed virtual fence [{direction}] at {now_str}"
                )

                if cls_name != "Person":
                    buf = list(self.vehicle_frame_buffer.get(obj_id, []))
                    if buf:
                        candidate_crops = sorted(buf, key=lambda x: x[3], reverse=True)[:2]
                        self.anpr_attempt_cooldowns[obj_id] = now_ts
                        self._enqueue_anpr_job(
                            obj_id,
                            cls_name,
                            candidate_crops,
                            now_str,
                            now_ts
                        )
        t_track = (time.perf_counter() - t0) * 1000.0

        # ─── 3b. Robust Suspicious Activity / Loitering Detection ───
        t0_loiter = time.perf_counter()
        loitering_triggered_dwells = {}  # obj_id -> dwell_time
        if LOITERING_ENABLED:
            for obj_id, obj in tracked_objects.items():
                cls_name = obj["class"]
                if cls_name != "Person":
                    continue

                (cx, cy) = obj["centroid"]
                hits = obj.get("hits", 1)

                if hits < LOITERING_MIN_HITS:
                    continue

                if obj_id not in self.loitering_state:
                    self.loitering_state[obj_id] = {
                        "first_seen": now_ts,
                        "anchor": (cx, cy),
                        "alerted": False,
                        "last_alert_time": 0.0,
                        "dwell_frames": 1
                    }
                    continue

                state = self.loitering_state[obj_id]
                state["dwell_frames"] += 1
                anchor_cx, anchor_cy = state["anchor"]
                displacement = math.hypot(cx - anchor_cx, cy - anchor_cy)

                # Smooth anchor towards person if moving slowly
                if displacement > LOITERING_RADIUS_PIXELS:
                    state["anchor"] = (cx, cy)
                    state["first_seen"] = now_ts
                    state["dwell_frames"] = 1
                    state["alerted"] = False
                    continue
                else:
                    # Exponential moving average anchor to resist bounding box jitter
                    state["anchor"] = (0.95 * anchor_cx + 0.05 * cx, 0.95 * anchor_cy + 0.05 * cy)

                dwell_time = now_ts - state["first_seen"]

                if dwell_time >= LOITERING_TIME_SECONDS:
                    if state["alerted"] and (now_ts - state["last_alert_time"]) < LOITERING_ALERT_COOLDOWN_SECONDS:
                        loitering_triggered_dwells[obj_id] = dwell_time
                        continue

                    is_loiter_duplicate = any(
                        k[0] == "loitering" and k[1] == cls_name and math.hypot(k[2] - anchor_cx, k[3] - anchor_cy) <= 150.0 and (now_ts - ts) < 30.0
                        for k, ts in self._cross_loop_signatures.items()
                    )
                    if is_loiter_duplicate:
                        state["alerted"] = True
                        state["last_alert_time"] = now_ts
                        loitering_triggered_dwells[obj_id] = dwell_time
                        continue

                    state["alerted"] = True
                    state["last_alert_time"] = now_ts
                    self._cross_loop_signatures[("loitering", cls_name, anchor_cx, anchor_cy)] = now_ts
                    loitering_triggered_dwells[obj_id] = dwell_time

                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    snapshot_fn = self._save_alert_snapshot(clean_frame.copy(), obj_id, cls_name, now_str)

                    self.total_suspicious_count += 1
                    self.session_suspicious_count += 1

                    details_msg = f"{cls_name} ID #{obj_id} loitering for {dwell_time:.0f}s (displacement: {displacement:.0f}px)"
                    suspicious_record = {
                        "id": self.total_suspicious_count,
                        "camera_id": self.camera_id,
                        "event_type": "suspicious_activity",
                        "object_id": obj_id,
                        "object_type": cls_name,
                        "timestamp": now_str,
                        "details": details_msg,
                        "validation_status": "DETECTED",
                        "snapshot_url": f"/alerts/{snapshot_fn}",
                        "snapshot_filename": snapshot_fn
                    }

                    with self._state_lock:
                        self.suspicious_alerts.append(suspicious_record)
                        if len(self.suspicious_alerts) > 50:
                            self.suspicious_alerts.pop(0)

                    self._safe_db_submit(
                        self.db.log_security_event,
                        now_str,
                        "suspicious_activity",
                        self.camera_id,
                        cls_name,
                        obj_id,
                        None,
                        snapshot_fn,
                        details_msg,
                        "DETECTED"
                    )

                    logger.warning(
                        f"⚠️ [{self.camera_id} SUSPICIOUS ACTIVITY] Person ID #{obj_id} loitering for {dwell_time:.0f}s at {now_str}"
                    )
        t_loiter = (time.perf_counter() - t0_loiter) * 1000.0

        # ─── 3c. Night-Time Movement Detection ───
        if NIGHT_DETECTION_ENABLED and self.is_night_mode and self.current_brightness <= NIGHT_ENTER_THRESHOLD + 5.0:
            for obj_id, obj in tracked_objects.items():
                cls_name = obj["class"]
                (cx, cy) = obj["centroid"]
                (prev_cx, prev_cy) = obj["prev_centroid"]
                movement = math.hypot(cx - prev_cx, cy - prev_cy)

                if movement < NIGHT_MOVEMENT_THRESHOLD_PIXELS:
                    continue

                last_night_alert = self.night_alerted_ids.get(obj_id, 0.0)
                if (now_ts - last_night_alert) < NIGHT_ALERT_COOLDOWN_SECONDS:
                    continue

                self.night_alerted_ids[obj_id] = now_ts
                self.total_night_alerts += 1
                self.session_night_count += 1
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                snapshot_fn = self._save_alert_snapshot(clean_frame.copy(), obj_id, cls_name, now_str)

                details_msg = f"Night movement detected ({cls_name} ID #{obj_id}, brightness={self.current_brightness}, disp={movement:.0f}px)"
                self._safe_db_submit(
                    self.db.log_security_event,
                    now_str,
                    "night_movement",
                    self.camera_id,
                    cls_name,
                    obj_id,
                    None,
                    snapshot_fn,
                    details_msg,
                    "DETECTED"
                )

        # ─── 4. Rate-Limited ANPR Dispatch ───
        t0 = time.perf_counter()
        for obj_id, obj in tracked_objects.items():
            cls_name = obj["class"]
            if cls_name != "Person":
                in_attempt_cd = (obj_id in self.anpr_attempt_cooldowns) and ((now_ts - self.anpr_attempt_cooldowns[obj_id]) < 4.0)
                in_read_cd = (obj_id in self.anpr_cooldowns) and ((now_ts - self.anpr_cooldowns[obj_id]) < 5.0)
                buf = list(self.vehicle_frame_buffer.get(obj_id, []))

                if (obj_id not in self.anpr_queued_ids) and (obj_id not in self.anpr_in_progress) and (not in_attempt_cd) and (not in_read_cd) and len(buf) >= 2:
                    self.anpr_attempt_cooldowns[obj_id] = now_ts
                    candidate_crops = sorted(buf, key=lambda x: x[3], reverse=True)[:2]
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    self._enqueue_anpr_job(
                        obj_id,
                        cls_name,
                        candidate_crops,
                        now_str,
                        now_ts
                    )
        t_anpr = (time.perf_counter() - t0) * 1000.0

        # ─── 5. Face Detection on Shared YuNet Model ───
        t0_face = time.perf_counter()
        if FACE_DETECTION_ENABLED and self.registry.face_detector is not None:
            self.face_frame_counter += 1
            if self.face_frame_counter >= FACE_DETECTION_INTERVAL:
                self.face_frame_counter = 0
                try:
                    new_faces = []
                    person_targets = [
                        obj["bbox"] for obj in tracked_objects.values()
                        if obj["class"] == "Person" and (obj["bbox"][3] - obj["bbox"][1]) >= 60
                    ]
                    person_targets.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)

                    with self.registry.face_infer_lock:
                        if person_targets:
                            for p_bbox in person_targets[:2]:
                                px1, py1, px2, py2 = p_bbox
                                head_y1 = max(0, py1 - 10)
                                head_y2 = min(h, py1 + int((py2 - py1) * 0.45))
                                head_x1 = max(0, px1 - 10)
                                head_x2 = min(w, px2 + 10)
                                crop_w = head_x2 - head_x1
                                crop_h = head_y2 - head_y1

                                if crop_w >= 32 and crop_h >= 32:
                                    head_crop = clean_frame[head_y1:head_y2, head_x1:head_x2]
                                    self.registry.face_detector.setInputSize((crop_w, crop_h))
                                    _, faces = self.registry.face_detector.detect(head_crop)
                                    if faces is not None and len(faces) > 0:
                                        for face in faces:
                                            conf = float(face[-1]) if len(face) > 14 else 0.8
                                            if conf >= 0.35:
                                                fx = head_x1 + int(face[0])
                                                fy = head_y1 + int(face[1])
                                                fw_f = int(face[2])
                                                fh_f = int(face[3])
                                                new_faces.append((fx, fy, fw_f, fh_f, round(conf, 2)))
                        elif not person_targets:
                            det_w, det_h = 640, 360
                            small_frame = cv2.resize(clean_frame, (det_w, det_h))
                            self.registry.face_detector.setInputSize((det_w, det_h))
                            _, faces = self.registry.face_detector.detect(small_frame)
                            if faces is not None and len(faces) > 0:
                                scale_x = w / det_w
                                scale_y = h / det_h
                                for face in faces:
                                    conf = float(face[-1]) if len(face) > 14 else 0.8
                                    if conf >= 0.35:
                                        fx = max(0, int(face[0] * scale_x))
                                        fy = max(0, int(face[1] * scale_y))
                                        fw_f = int(face[2] * scale_x)
                                        fh_f = int(face[3] * scale_y)
                                        new_faces.append((fx, fy, fw_f, fh_f, round(conf, 2)))

                    self.face_rects_cache = new_faces
                    self.face_count = len(self.face_rects_cache)
                except Exception:
                    pass
        t_face = (time.perf_counter() - t0_face) * 1000.0

        # ─── 6. Render Overlays on Display Frame ───
        t0_draw = time.perf_counter()
        display_frame = clean_frame.copy()

        # Camera watermark badge
        cam_tag = f"[{self.camera_id}] {self.camera_name}"
        cv2.putText(display_frame, cam_tag, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 229, 255), 2, cv2.LINE_AA)

        for obj_id, obj in tracked_objects.items():
            cls_name = obj["class"]
            conf = obj["confidence"]
            (x1, y1, x2, y2) = obj["bbox"]
            (cx, cy) = obj["centroid"]
            direction = obj.get("direction")
            color = (0, 230, 115) if cls_name == "Person" else (255, 178, 51)

            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(display_frame, (cx, cy), 5, (0, 0, 255), -1)

            dir_str = f" [{direction}]" if direction else ""
            label = f"ID #{obj_id} {cls_name} {conf:.2f}{dir_str}"
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(display_frame, (x1, y1 - text_h - 6), (x1 + text_w + 6, y1), color, -1)
            cv2.putText(display_frame, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

            if obj_id in loitering_triggered_dwells:
                dwell_sec = loitering_triggered_dwells[obj_id]
                loiter_label = f"SUSPICIOUS ACTIVITY (ID #{obj_id} | Dwell: {dwell_sec:.1f}s)"
                (lw, lh), _ = cv2.getTextSize(loiter_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(display_frame, (x1, y2 + 2), (x1 + lw + 6, y2 + lh + 7), (0, 140, 255), -1)
                cv2.putText(display_frame, loiter_label, (x1 + 3, y2 + lh + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        if len(self.face_rects_cache) > 0:
            for item in self.face_rects_cache:
                fx, fy, fw_f, fh_f = item[0], item[1], item[2], item[3]
                f_conf = item[4] if len(item) > 4 else 0.8
                cv2.rectangle(display_frame, (fx, fy), (fx + fw_f, fy + fh_f), (255, 215, 0), 2)
                f_lbl = f"Face {f_conf:.2f}"
                (ftw, fth), _ = cv2.getTextSize(f_lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(display_frame, (fx, fy - fth - 5), (fx + ftw + 4, fy), (255, 215, 0), -1)
                cv2.putText(display_frame, f_lbl, (fx + 2, fy - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 20, 40), 1, cv2.LINE_AA)

        # Virtual Fence Line
        cv2.line(display_frame, (0, line_y), (w, line_y), (0, 0, 255), 2)
        fence_label = f"VIRTUAL FENCE - INTRUSION ZONE (Y={line_y})"
        (fw, fh), _ = cv2.getTextSize(fence_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(display_frame, (10, line_y - fh - 8), (10 + fw + 10, line_y - 2), (0, 0, 200), -1)
        cv2.putText(display_frame, fence_label, (15, line_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        if NIGHT_DETECTION_ENABLED and self.is_night_mode:
            night_label = f"NIGHT MODE (Lum: {self.current_brightness:.0f})"
            (nw, nh), _ = cv2.getTextSize(night_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(display_frame, (w - nw - 20, 8), (w - 5, nh + 16), (80, 40, 0), -1)
            cv2.putText(display_frame, night_label, (w - nw - 15, nh + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 255), 2, cv2.LINE_AA)
        t_draw = (time.perf_counter() - t0_draw) * 1000.0

        self.profile_accum["detect_ms"] += t_detect
        self.profile_accum["track_ms"] += t_track
        self.profile_accum["anpr_ms"] += t_anpr
        self.profile_accum["face_ms"] += t_face
        self.profile_accum["loiter_ms"] += t_loiter
        self.profile_accum["night_ms"] += t_night
        self.profile_accum["draw_ms"] += t_draw
        self.profile_accum["frames"] += 1

        return display_frame, p_count, v_count

    def _frame_grabber_loop(self):
        """Dedicated high-speed frame grabber supporting video looping, RTSP, and webcams."""
        grabbed_counter = 0
        last_calc_time = time.time()

        while self.running:
            target_source = self.rtsp_url
            if self.source_type == "video_file":
                target_source = self._resolve_source_path(str(self.rtsp_url))
                logger.info(f"[{self.camera_id}] Opening Video File: {target_source}")
                cap = cv2.VideoCapture(target_source)
            elif self.source_type == "webcam":
                cam_idx = int(self.rtsp_url) if str(self.rtsp_url).isdigit() else 0
                logger.info(f"[{self.camera_id}] Opening Webcam device #{cam_idx}...")
                if sys.platform == "win32":
                    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(cam_idx)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                logger.info(f"[{self.camera_id}] Connecting to RTSP stream: {self.rtsp_url}")
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
                cap = cv2.VideoCapture(str(self.rtsp_url), cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                self.error_state = f"Failed to open source ({self.source_type})"
                self.status = "OFFLINE"
                with self._frame_lock:
                    self.is_connected = False
                    self.current_fps = 0.0
                    self.latest_jpeg = self._create_placeholder_frame(f"{self.camera_id}: Connecting...")
                time.sleep(2.0)
                continue

            # Connection success
            with self._frame_lock:
                self.is_connected = True
                self.status = "ONLINE"
                self.error_state = None

            video_native_fps = cap.get(cv2.CAP_PROP_FPS)
            if not video_native_fps or video_native_fps <= 0 or math.isnan(video_native_fps):
                video_native_fps = 30.0
            frame_delay = 1.0 / max(10.0, min(video_native_fps, 30.0))

            resolution_logged = False
            while self.running:
                t_frame_start = time.time()
                ret, frame = cap.read()

                if not ret or frame is None:
                    if self.source_type == "video_file":
                        # Seamless video file looping
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            logger.info(f"[{self.camera_id}] Video loop reached end, re-opening file...")
                            break
                    else:
                        logger.warning(f"[{self.camera_id}] Stream disconnected or frame grab failed. Reconnecting...")
                        break

                self.last_frame_time = time.time()
                grabbed_counter += 1
                now = time.time()
                if (now - last_calc_time) >= 3.0:
                    self.capture_fps = round(grabbed_counter / (now - last_calc_time), 1)
                    grabbed_counter = 0
                    last_calc_time = now

                if not resolution_logged:
                    fh, fw = frame.shape[:2]
                    fence_y_px = int(fh * self.line_y_ratio)
                    logger.info(f"📐 [{self.camera_id} STREAM READY] Resolution: {fw}x{fh} | Fence Line: {fence_y_px}px ({int(self.line_y_ratio*100)}%)")
                    resolution_logged = True

                with self._raw_frame_lock:
                    self.raw_frame = frame
                    self.raw_frame_id += 1
                    self.raw_frame_res = frame.shape[:2]

                # If local video file, pace grabber according to native FPS
                if self.source_type == "video_file":
                    elapsed = time.time() - t_frame_start
                    sleep_time = frame_delay - elapsed
                    if sleep_time > 0.001:
                        time.sleep(sleep_time)

            cap.release()
            with self._frame_lock:
                self.is_connected = False
                self.status = "OFFLINE"
                self.current_fps = 0.0
                self.latest_jpeg = self._create_placeholder_frame(f"{self.camera_id}: Reconnecting...")
            time.sleep(1.0)

    def _ai_processing_loop(self):
        """Dedicated high-speed AI processing thread reading newest grabbed frame without pipeline stalls."""
        last_processed_frame_id = -1
        frames_since_log = 0
        last_log_time = time.time()

        while self.running:
            frame_to_process = None
            with self._raw_frame_lock:
                if self.raw_frame is not None and self.raw_frame_id != last_processed_frame_id:
                    frame_to_process = self.raw_frame
                    last_processed_frame_id = self.raw_frame_id

            if frame_to_process is None:
                time.sleep(0.003)
                continue

            try:
                processed_frame, p_cnt, v_cnt = self._process_frame_ai(frame_to_process)
            except Exception as e:
                logger.error(f"[{self.camera_id}] Error in _process_frame_ai: {e}")
                processed_frame = frame_to_process
                p_cnt = 0
                v_cnt = 0

            # JPEG Compression
            t0_enc = time.perf_counter()
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
            ret, jpeg = cv2.imencode('.jpg', processed_frame, encode_params)
            t_enc = (time.perf_counter() - t0_enc) * 1000.0
            self.profile_accum["encode_ms"] += t_enc

            if ret:
                jpeg_bytes = jpeg.tobytes()
                with self._frame_lock:
                    self.latest_jpeg = jpeg_bytes

                with self._state_lock:
                    self.frame_count += 1
                    self.people_count = p_cnt
                    self.vehicle_count = v_cnt
                    self.total_objects = p_cnt + v_cnt

            frames_since_log += 1
            now = time.time()
            elapsed = now - last_log_time

            if elapsed >= self.fps_log_interval:
                fps = frames_since_log / elapsed
                self.current_fps = round(fps, 1)

                f_count = max(1, self.profile_accum["frames"])
                avg_detect = self.profile_accum["detect_ms"] / f_count
                avg_track = self.profile_accum["track_ms"] / f_count
                avg_draw = self.profile_accum["draw_ms"] / f_count
                avg_enc = self.profile_accum["encode_ms"] / f_count
                avg_total = avg_detect + avg_track + avg_draw + avg_enc

                logger.info(
                    f"⏱️ [{self.camera_id}] AI FPS: {fps:.1f} (Cap: {self.capture_fps:.1f}) | Avg: {avg_total:.1f}ms "
                    f"(YOLO: {avg_detect:.1f}ms | Track: {avg_track:.1f}ms | Draw: {avg_draw:.1f}ms | Enc: {avg_enc:.1f}ms) | "
                    f"People: {p_cnt}, Veh: {v_cnt} | Night: {self.night_state_str}"
                )

                self.profile_accum = {
                    "detect_ms": 0.0,
                    "track_ms": 0.0,
                    "anpr_ms": 0.0,
                    "face_ms": 0.0,
                    "loiter_ms": 0.0,
                    "night_ms": 0.0,
                    "draw_ms": 0.0,
                    "encode_ms": 0.0,
                    "frames": 0,
                    "detector_calls": 0,
                    "ocr_calls": 0
                }
                frames_since_log = 0
                last_log_time = now

    def get_latest_frame(self) -> bytes:
        """Returns the latest JPEG frame buffer safely with dedicated non-blocking lock."""
        with self._frame_lock:
            if self.latest_jpeg is None:
                return self._create_placeholder_frame(f"{self.camera_id}: Initializing Feed...")
            return self.latest_jpeg

    def get_status(self) -> dict:
        """Returns stream status dictionary including AI object counts, intrusion alerts, and metrics."""
        now = time.time()
        if not hasattr(self, "_cached_db_totals") or (now - getattr(self, "_last_db_totals_time", 0)) > 5.0:
            try:
                self._cached_db_totals = self.db.get_total_counts(camera_id=self.camera_id)
                self._last_db_totals_time = now
            except Exception:
                self._cached_db_totals = {"total_intrusions": self.total_alerts_count, "total_anpr": self.total_anpr_count, "total_security": 0}

        db_totals = self._cached_db_totals
        with self._state_lock:
            return {
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "source_type": self.source_type,
                "status": "ONLINE" if self.is_connected else self.status,
                "connected": self.is_connected,
                "fps": self.current_fps,
                "capture_fps": self.capture_fps,
                "total_frames": self.frame_count,
                "rtsp_url": str(self.rtsp_url),
                "device": self.device,
                "error_state": self.error_state,
                "last_frame_time": self.last_frame_time,
                "total_alerts": self.session_alerts_count,
                "session_alerts": self.session_alerts_count,
                "session_anpr": self.session_anpr_count,
                "session_suspicious": self.session_suspicious_count,
                "session_night": self.session_night_count,
                "db_total_alerts": db_totals.get("total_intrusions", self.total_alerts_count),
                "db_total_anpr": db_totals.get("total_anpr", self.total_anpr_count),
                "db_total_security": db_totals.get("total_security", 0),
                "suspicious_activity_count": self.session_suspicious_count,
                "night_mode": self.is_night_mode,
                "is_night_mode": self.is_night_mode,
                "night_state": self.night_state_str,
                "night_alert_count": self.session_night_count,
                "brightness": self.current_brightness,
                "face_count": self.face_count,
                "anpr_queue_size": self.anpr_queue.qsize() if hasattr(self, "anpr_queue") else 0,
                "people_count": self.people_count,
                "vehicle_count": self.vehicle_count,
                "total_objects": self.total_objects,
                "detected_objects": {
                    "people_count": self.people_count,
                    "vehicle_count": self.vehicle_count,
                    "total_objects": self.total_objects
                }
            }

    def get_alerts(self) -> list:
        """Returns recent intrusion alerts (most recent first)."""
        with self._state_lock:
            return list(reversed(self.alerts))

    def get_suspicious_alerts(self) -> list:
        """Returns recent suspicious activity / loitering alerts (most recent first)."""
        with self._state_lock:
            return list(reversed(self.suspicious_alerts))

    def get_anpr_logs(self) -> list:
        """Returns recent ANPR license plate reads (most recent first)."""
        with self._state_lock:
            return list(reversed(self.anpr_logs))

    def get_anpr_debug_crops(self) -> list:
        """Returns recent ANPR candidate debug crops (most recent first)."""
        with self._state_lock:
            return list(reversed(self.anpr_debug_crops))

    def get_night_status(self) -> dict:
        """Returns current night mode status and brightness."""
        return {
            "camera_id": self.camera_id,
            "is_night_mode": self.is_night_mode,
            "night_state": self.night_state_str,
            "brightness": self.current_brightness,
            "threshold_enter": NIGHT_ENTER_THRESHOLD,
            "threshold_exit": NIGHT_EXIT_THRESHOLD,
            "night_alert_count": self.total_night_alerts
        }

    def get_face_stats(self) -> dict:
        """Returns face detection statistics."""
        return {
            "camera_id": self.camera_id,
            "face_count": self.face_count,
            "face_detection_enabled": FACE_DETECTION_ENABLED and self.registry.face_detector is not None,
            "detection_interval": FACE_DETECTION_INTERVAL
        }
