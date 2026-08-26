import os
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

# Set up clean logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RTSPStreamReader")

# Configurable Virtual Fence line position as a percentage of frame height (0.7 = 70% down frame)
FENCE_LINE_PERCENT = 0.7

# ─── Suspicious Activity / Loitering Detection Configuration ───
LOITERING_ENABLED = True
LOITERING_TIME_SECONDS = 20            # Time threshold to trigger loitering alert
LOITERING_RADIUS_PIXELS = 100          # Max displacement from anchor to still count as loitering
LOITERING_ALERT_COOLDOWN_SECONDS = 30  # Cooldown before re-alerting same object

# ─── Night-Time Movement Detection Configuration ───
NIGHT_DETECTION_ENABLED = True
NIGHT_BRIGHTNESS_THRESHOLD = 45        # Grayscale mean below this = low-light
NIGHT_CONFIRM_FRAMES = 30              # Consecutive frames needed to confirm night/day state
NIGHT_ALERT_COOLDOWN_SECONDS = 30      # Cooldown per-object for night movement alerts
NIGHT_MOVEMENT_THRESHOLD_PIXELS = 15   # Minimum centroid movement (px) to count as "moving" at night

# ─── Face Detection Configuration ───
FACE_DETECTION_ENABLED = True
FACE_DETECTION_INTERVAL = 8            # Run face detection every N frames (amortized overhead <2ms)


class RTSPStreamReader:
    PERSON_CLASS = 0
    VEHICLE_CLASSES = {
        1: "vehicle",     # Bicycle / two-wheeler
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }
    # COCO class IDs for person and all road vehicles
    TARGET_CLASS_IDS = [0, 1, 2, 3, 5, 7]
    VEHICLE_SUBTYPE_CONFIDENCE_THRESHOLD = 0.40

    def __init__(
        self,
        rtsp_url: str = "rtsp://localhost:8554/mystream",
        fps_log_interval: float = 3.0,
        model_name: str = "yolov8n.pt",
        line_y_ratio: float = None,
        vehicle_subtype_conf: float = 0.40
    ):
        self.rtsp_url = rtsp_url
        self.fps_log_interval = fps_log_interval
        self.line_y_ratio = line_y_ratio if line_y_ratio is not None else FENCE_LINE_PERCENT
        self.vehicle_subtype_conf = vehicle_subtype_conf
        
        self.is_connected = False
        self.running = False
        self.latest_jpeg = None
        self.frame_count = 0
        self.current_fps = 0.0
        self.capture_fps = 0.0
        
        # Detection metrics
        self.people_count = 0
        self.vehicle_count = 0
        self.total_objects = 0
        
        # Persistent Database Manager
        self.db = db_manager

        # Virtual Fence & Intrusion Alerts storage (Hydrated from persistent SQLite DB)
        self.tracker = CentroidTracker(max_disappeared=25, max_distance=220.0)
        self.alerted_object_ids = set()
        self.alerts = self.db.get_recent_intrusions(50)
        self.total_alerts_count = len(self.alerts)
        self.recent_alerts = []  # List of (cx, cy, timestamp_float)
        
        # ANPR License Plate Recognition Engine & storage (Hydrated from persistent SQLite DB)
        self.anpr_engine = ANPREngine()
        self.anpr_logs = self.db.get_recent_anpr(50)
        self.anpr_cooldowns = {}
        self.total_anpr_count = len(self.anpr_logs)
        self.anpr_queue = queue.Queue(maxsize=10)
        self.anpr_queued_ids = set()
        self.anpr_in_progress = set()
        self.db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DB-Worker")
        self._anpr_worker_thread = None
        
        # Per-Track Temporal Vehicle Frame Buffer (maxlen=10 observations per track)
        self.vehicle_frame_buffer = collections.defaultdict(lambda: collections.deque(maxlen=10))
        
        # ANPR Temporal Consensus State
        self.vehicle_ocr_history = collections.defaultdict(list)
        self.vehicle_published_plate = {}
        
        # ANPR Debug candidate crop storage
        self.anpr_debug_crops = []
        self.anpr_attempt_cooldowns = {}
        self.total_anpr_debug_count = 0
        
        # Real-time Profiling Metrics
        self.total_anpr_detector_calls = 0
        self.total_anpr_ocr_calls = 0
        self.last_profile_time = time.time()
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
        
        # ─── Live Session Counters ───
        self.session_alerts_count = 0
        self.session_anpr_count = 0
        self.session_suspicious_count = 0
        self.session_night_count = 0

        # ─── Loitering / Suspicious Activity State ───
        self.loitering_state = {}
        self.suspicious_alerts = []
        self.total_suspicious_count = 0
        
        # ─── Night-Time Detection State ───
        self.is_night_mode = False
        self.night_brightness_history = collections.deque(maxlen=NIGHT_CONFIRM_FRAMES)
        self.night_alerted_ids = {}
        self.total_night_alerts = 0
        self.current_brightness = 0.0
        
        # ─── Face Detection State (YuNet Local Model) ───
        self.face_count = 0
        self.face_frame_counter = 0
        self.face_rects_cache = []
        self.face_detector = None
        if FACE_DETECTION_ENABLED:
            yunet_model_path = os.path.join(os.path.dirname(__file__), "weights", "face_detection_yunet_2023mar.onnx")
            if os.path.exists(yunet_model_path):
                try:
                    self.face_detector = cv2.FaceDetectorYN_create(
                        yunet_model_path, "", (640, 360), 0.45, 0.3, 5000
                    )
                    logger.info(f"Face Detection: Local YuNet model loaded from {yunet_model_path}")
                except Exception as e:
                    logger.warning(f"Face Detection: Could not load YuNet ({e}) — disabled")
            else:
                logger.warning(f"Face Detection: Model not found at {yunet_model_path}")
        
        # ─── Stream Loop & Scene Discontinuity Detection State ───
        self._prev_gray_thumb = None
        self._loop_cooldown = 0.0
        self._cross_loop_signatures = {}
        self._last_anpr_dispatch = 0.0

        # ─── Camera ID ───
        self.camera_id = "CAM-01"
        
        # Snapshot Directories
        self.alerts_dir = os.path.join(os.path.dirname(__file__), "static", "alerts")
        os.makedirs(self.alerts_dir, exist_ok=True)
        
        self.anpr_dir = os.path.join(os.path.dirname(__file__), "static", "anpr")
        os.makedirs(self.anpr_dir, exist_ok=True)
        
        self.anpr_debug_dir = os.path.join(os.path.dirname(__file__), "static", "anpr_debug")
        os.makedirs(self.anpr_debug_dir, exist_ok=True)
        
        # Device auto-detection: GPU (CUDA)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing YOLO AI Model ({model_name}) on device: {self.device.upper()}")
        
        try:
            self.model = YOLO(model_name)
            if self.device == "cuda":
                self.model.to("cuda")
                # Warmup inference
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                with torch.inference_mode():
                    _ = self.model.predict(source=dummy, imgsz=640, device="cuda", verbose=False)
                torch.cuda.synchronize()
        except Exception as e:
            logger.warning(f"Error loading {model_name}, falling back to yolov8n.pt: {e}")
            self.model = YOLO("yolov8n.pt")
            if self.device == "cuda":
                self.model.to("cuda")

        # ─── Separate Dedicated Locks for Frame Streaming & State Data ───
        self._raw_frame_lock = threading.Lock()
        self.raw_frame = None
        self.raw_frame_id = 0
        self.raw_frame_res = None
        
        self._frame_lock = threading.Lock()  # Exclusively for latest_jpeg pointer swap
        self._state_lock = threading.Lock()  # Exclusively for state lists & metrics
        
        self._grabber_thread = None
        self._ai_thread = None
        self._anpr_worker_thread = None
        self._sync_thread = None

    def start(self):
        """Starts the background frame grabber, AI processing, ANPR worker, and sync threads."""
        if self.running:
            return
        self.running = True
        self.db.log_system_event("app_started", f"RTSP Reader started on {self.rtsp_url}")
        self._grabber_thread = threading.Thread(target=self._frame_grabber_loop, daemon=True, name="RTSP-Grabber")
        self._ai_thread = threading.Thread(target=self._ai_processing_loop, daemon=True, name="AI-Processor")
        self._anpr_worker_thread = threading.Thread(target=self._anpr_worker_loop, daemon=True, name="ANPR-Worker")
        self._sync_thread = threading.Thread(target=self._sync_worker_loop, daemon=True, name="Offline-Sync-Worker")
        self._grabber_thread.start()
        self._ai_thread.start()
        self._anpr_worker_thread.start()
        self._sync_thread.start()
        logger.info(f"RTSP AI Detection Reader started (Latest-Frame Architecture Active). Target stream: {self.rtsp_url}")

    def stop(self):
        """Stops the background worker threads cleanly."""
        self.running = False
        self.db.log_system_event("app_stopped", "RTSP Reader stopped")
        if self._grabber_thread and self._grabber_thread.is_alive():
            self._grabber_thread.join(timeout=2.0)
        if self._ai_thread and self._ai_thread.is_alive():
            self._ai_thread.join(timeout=2.0)
        if self._anpr_worker_thread and self._anpr_worker_thread.is_alive():
            self._anpr_worker_thread.join(timeout=2.0)
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)
        try:
            self.db_executor.shutdown(wait=False)
        except Exception:
            pass
        logger.info("RTSP AI Reader stopped.")

    def _sync_worker_loop(self):
        """Background daemon running offline-first sync periodically every 30 seconds."""
        while self.running:
            time.sleep(30.0)
            try:
                self.db.sync_pending_events()
            except Exception as e:
                logger.error(f"Error in background sync worker loop: {e}")

    def _create_placeholder_frame(self, text: str) -> bytes:
        """Generates a dark placeholder image with custom text encoded as JPEG."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            img, text, (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2, cv2.LINE_AA
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
        filename = f"intrusion_{safe_ts}_id{object_id}.jpg"
        filepath = os.path.join(self.alerts_dir, filename)

        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # 1. Draw Red Virtual Fence line
        if line_y is not None:
            cv2.line(annotated, (0, line_y), (w, line_y), (0, 0, 255), 2)
            fence_txt = f"VIRTUAL FENCE LINE (Y={line_y})"
            cv2.putText(annotated, fence_txt, (15, max(20, line_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        # 2. Highlight intruding object bounding box and centroid
        if bbox:
            x1, y1, x2, y2 = bbox
            color = (0, 230, 115) if object_type == "Person" else (0, 165, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
            if centroid:
                cv2.circle(annotated, centroid, 6, (0, 0, 255), -1)

            badge_text = f"BREACH: ID #{object_id} {object_type} [{direction}]"
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), (0, 0, 200), -1)
            cv2.putText(annotated, badge_text, (x1 + 4, max(th + 2, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        # 3. Top telemetry header bar
        header = f"PRAHARI-AI | INTRUSION EVENT | {object_type.upper()} ID #{object_id} [{direction}] | {timestamp_str}"
        (hw, hh), _ = cv2.getTextSize(header, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(annotated, (0, 0), (w, hh + 16), (15, 23, 42), -1)
        cv2.putText(annotated, header, (15, hh + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 229, 255), 2, cv2.LINE_AA)

        self.db_executor.submit(cv2.imwrite, filepath, annotated)
        return filename

    def _save_anpr_snapshot(self, plate_crop, object_id: int, timestamp_str: str) -> str:
        """Saves cropped license plate image to static/anpr/."""
        safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
        filename = f"plate_{safe_ts}_id{object_id}.jpg"
        filepath = os.path.join(self.anpr_dir, filename)
        cv2.imwrite(filepath, plate_crop)
        return filename

    def _save_anpr_debug_crop(self, plate_crop, object_id: int, timestamp_str: str, is_detected: bool = True) -> str:
        """Saves cropped plate region detected by the YOLO plate detector for visual debugging."""
        safe_ts = timestamp_str.replace(":", "-").replace(" ", "_")
        crop_type = "plate_detected" if is_detected else "candidate"
        self.total_anpr_debug_count += 1
        filename = f"crop_{safe_ts}_id{object_id}_#{self.total_anpr_debug_count}_{crop_type}.jpg"
        filepath = os.path.join(self.anpr_debug_dir, filename)
        cv2.imwrite(filepath, plate_crop)

        debug_record = {
            "id": self.total_anpr_debug_count,
            "vehicle_id": object_id,
            "crop_type": crop_type,
            "timestamp": timestamp_str,
            "snapshot_url": f"/anpr_debug/{filename}",
            "snapshot_filename": filename
        }

        with self._state_lock:
            self.anpr_debug_crops.append(debug_record)
            if len(self.anpr_debug_crops) > 100:
                oldest = self.anpr_debug_crops.pop(0)
                old_path = os.path.join(self.anpr_debug_dir, oldest["snapshot_filename"])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass

        logger.debug(
            f"🔍 [ANPR DEBUG] Saved plate detector crop for Vehicle #{object_id} -> static/anpr_debug/{filename}"
        )
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
                logger.error(f"Error in ANPR worker loop for vehicle #{obj_id}: {e}")
            finally:
                with self._state_lock:
                    self.anpr_queued_ids.discard(obj_id)
                self.anpr_queue.task_done()

    def _enqueue_anpr_job(self, obj_id: int, cls_name: str, candidate_crops: list, now_str: str, now_ts: float):
        """Enqueues an ANPR task into the bounded queue with track-level deduplication and oldest-drop on saturation."""
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
        """
        Asynchronously processes multiple candidate crops from the vehicle's rolling frame buffer,
        runs YOLO plate detection, Lanczos aspect-ratio upscaling, multi-variant OCR,
        format validation, temporal voting consensus across frames, and links back to the intrusion event.
        """
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

                # Step 1: Detect license plate region within vehicle crop (with outward padding expansion)
                plate_crop, is_detected, det_conf = self.anpr_engine.extract_plate_crop_from_vehicle(v_crop, conf_threshold=0.15)
                if not is_detected or plate_crop is None:
                    continue

                self._save_anpr_debug_crop(plate_crop, obj_id, now_str, is_detected=True)

                # Step 2: Run Multi-Variant OCR + Indian Format Validation
                self.total_anpr_ocr_calls += 1
                self.profile_accum["ocr_calls"] += 1
                cleaned_text, raw_text, ocr_conf, is_valid_fmt, tier = self.anpr_engine.read_plate(plate_crop)

                if cleaned_text and len(cleaned_text) >= 4:
                    self.vehicle_ocr_history[obj_id].append((cleaned_text, raw_text, ocr_conf, is_valid_fmt, tier, c_ts, plate_crop))

            # Step 3: Temporal Consensus across all recent observations for this vehicle track
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

            # Step 4: Evaluate Publication & Intrusion Linkage
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
                        is_verified = (best_conf_found >= 0.45 and best_valid_found)

                        with self._state_lock:
                            self.total_anpr_count += 1
                            self.session_anpr_count += 1
                            anpr_record = {
                                "id": self.total_anpr_count,
                                "vehicle_id": obj_id,
                                "vehicle_type": cls_name,
                                "plate_text": best_plate_found,
                                "confidence": best_conf_found,
                                "is_verified": is_verified,
                                "timestamp": now_str,
                                "snapshot_url": plate_url,
                                "snapshot_filename": plate_fn
                            }
                            self.anpr_logs.append(anpr_record)
                            if len(self.anpr_logs) > 50:
                                self.anpr_logs.pop(0)

                            # Link to matching Intrusion Record in memory
                            status_str = "VERIFIED" if is_verified else "DETECTED"
                            for alert in reversed(self.alerts):
                                if alert.get("object_id") == obj_id:
                                    alert["plate_text"] = best_plate_found
                                    alert["plate_confidence"] = best_conf_found
                                    alert["anpr_status"] = status_str
                                    break

                        self.db_executor.submit(
                            self.db.log_anpr_event,
                            now_str,
                            cls_name,
                            obj_id,
                            best_plate_found,
                            best_conf_found,
                            plate_fn
                        )
                        self.db_executor.submit(
                            self.db.update_intrusion_anpr,
                            obj_id,
                            best_plate_found,
                            best_conf_found,
                            status_str
                        )

                        status_tag = "VERIFIED" if is_verified else "LOW CONFIDENCE READ"
                        logger.info(
                            f"🚘 [ANPR READ SUCCESS] Vehicle #{obj_id} ({cls_name}) -> Plate: '{best_plate_found}' (Conf: {best_conf_found*100:.0f}% | {status_tag}) Linked to Intrusion Alert!"
                        )
            else:
                # ANPR attempted across buffered frames but no readable plate found
                with self._state_lock:
                    for alert in reversed(self.alerts):
                        if alert.get("object_id") == obj_id and alert.get("plate_text") == "ANALYZING...":
                            alert["plate_text"] = "PLATE NOT READ"
                            alert["anpr_status"] = "UNREADABLE"
                            break
                self.db_executor.submit(
                    self.db.update_intrusion_anpr,
                    obj_id,
                    "PLATE NOT READ",
                    0.0,
                    "UNREADABLE"
                )
                logger.debug(
                    f"🔍 [ANPR RESULT] Vehicle #{obj_id} ({cls_name}) -> PLATE NOT READ across {len(candidate_crops)} buffered frames"
                )
        except Exception as e:
            logger.error(f"Error in async ANPR OCR worker for vehicle #{obj_id}: {e}")
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

        # Clean cross-loop signatures and temporal OCR history older than 45 seconds
        self._cross_loop_signatures = {k: v for k, v in self._cross_loop_signatures.items() if (now_ts - v) <= 45.0}
        for vid in list(self.vehicle_ocr_history.keys()):
            self.vehicle_ocr_history[vid] = [obs for obs in self.vehicle_ocr_history[vid] if (now_ts - obs[5]) <= 45.0]
            if len(self.vehicle_ocr_history[vid]) == 0:
                del self.vehicle_ocr_history[vid]

        # ─── 0a. Stream Loop & Scene Discontinuity Detection ───
        gray_for_brightness = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_thumb = cv2.resize(gray_for_brightness, (64, 36))
        if self._prev_gray_thumb is not None and (now_ts - self._loop_cooldown) > 10.0:
            diff = cv2.absdiff(gray_thumb, self._prev_gray_thumb)
            mean_diff = float(cv2.mean(diff)[0])
            if mean_diff > 85.0:  # Real video loop discontinuity
                logger.info(f"🔄 [VIDEO LOOP DETECTED] Scene discontinuity diff={mean_diff:.1f}. Resetting active tracking state.")
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

        # ─── 0b. Night-Time Brightness Detection ───
        t0_night = time.perf_counter()
        if NIGHT_DETECTION_ENABLED:
            mean_brightness = cv2.mean(gray_for_brightness)[0]
            self.current_brightness = round(mean_brightness, 1)
            self.night_brightness_history.append(mean_brightness)
            
            if len(self.night_brightness_history) >= NIGHT_CONFIRM_FRAMES:
                if all(b <= NIGHT_BRIGHTNESS_THRESHOLD for b in self.night_brightness_history):
                    self.is_night_mode = True
                elif all(b > NIGHT_BRIGHTNESS_THRESHOLD for b in self.night_brightness_history):
                    self.is_night_mode = False
        t_night = (time.perf_counter() - t0_night) * 1000.0

        # ─── 1. Run YOLO inference on CUDA GPU ───
        t0 = time.perf_counter()
        with torch.inference_mode():
            results = self.model.predict(
                source=frame,
                imgsz=640,
                classes=self.TARGET_CLASS_IDS,
                conf=0.35,
                device=self.device,
                verbose=False
            )
        t_detect = (time.perf_counter() - t0) * 1000.0

        detections = []
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

        # ─── 2. Update Centroid Tracker & Vehicle Temporal Frame Buffer ───
        t0 = time.perf_counter()
        tracked_objects = self.tracker.update(detections)

        p_count = 0
        v_count = 0

        # Clean recent alerts older than 4.0 seconds
        self.recent_alerts = [(ax, ay, at) for (ax, ay, at) in self.recent_alerts if (now_ts - at) <= 4.0]

        active_ids = set(tracked_objects.keys())
        
        # Clean loitering, night, and vehicle temporal frame buffer state
        stale_loiter_ids = [oid for oid in self.loitering_state if oid not in active_ids]
        for oid in stale_loiter_ids:
            del self.loitering_state[oid]
        stale_night_ids = [oid for oid in self.night_alerted_ids if oid not in active_ids]
        for oid in stale_night_ids:
            del self.night_alerted_ids[oid]
        stale_buffer_ids = [vid for vid in list(self.vehicle_frame_buffer.keys()) if vid not in active_ids]
        for vid in stale_buffer_ids:
            del self.vehicle_frame_buffer[vid]

        # Populate Per-Track Temporal Vehicle Ring Buffer (Efficient Sampling)
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

        # ─── 3. Strict Centroid-Based Virtual Fence Intrusion Evaluation ───
        for obj_id, obj in tracked_objects.items():
            cls_name = obj["class"]
            conf = obj["confidence"]
            (x1, y1, x2, y2) = obj["bbox"]
            (cx, cy) = obj["centroid"]

            if cls_name == "Person":
                p_count += 1
            else:
                v_count += 1

            is_new_intrusion, direction = self.tracker.check_intrusion_crossing(obj_id, line_y)

            if is_new_intrusion and (obj_id not in self.alerted_object_ids):
                self.alerted_object_ids.add(obj_id)
                self.recent_alerts.append((cx, cy, now_ts))
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Save Guaranteed Annotated Intrusion Snapshot
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
                    "object_id": obj_id,
                    "object_type": cls_name,
                    "direction": direction,
                    "plate_text": init_plate,
                    "plate_confidence": 0.0,
                    "anpr_status": init_status,
                    "timestamp": now_str,
                    "snapshot_url": snapshot_url,
                    "snapshot_filename": snapshot_fn
                }

                with self._state_lock:
                    self.alerts.append(alert_record)
                    if len(self.alerts) > 50:
                        self.alerts.pop(0)

                self.db_executor.submit(
                    self.db.log_intrusion_event,
                    now_str,
                    cls_name,
                    obj_id,
                    snapshot_fn,
                    direction,
                    init_plate,
                    0.0,
                    init_status
                )

                logger.warning(
                    f"🚨 [INTRUSION ALERT] #{self.total_alerts_count} | ID #{obj_id} ({cls_name}) crossed virtual fence [Direction: {direction}] at {now_str}!"
                )

                # If vehicle, trigger immediate asynchronous multi-frame ANPR evaluation
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

        # ─── 3b. Suspicious Activity / Loitering Detection ───
        t0_loiter = time.perf_counter()
        loitering_triggered_ids = set()
        if LOITERING_ENABLED:
            for obj_id, obj in tracked_objects.items():
                cls_name = obj["class"]
                if cls_name != "Person":
                    continue

                (cx, cy) = obj["centroid"]

                if obj_id not in self.loitering_state:
                    self.loitering_state[obj_id] = {
                        "first_seen": now_ts,
                        "anchor": (cx, cy),
                        "alerted": False,
                        "last_alert_time": 0.0
                    }
                    continue

                state = self.loitering_state[obj_id]
                anchor_cx, anchor_cy = state["anchor"]
                displacement = math.hypot(cx - anchor_cx, cy - anchor_cy)

                if displacement > LOITERING_RADIUS_PIXELS:
                    state["anchor"] = (cx, cy)
                    state["first_seen"] = now_ts
                    state["alerted"] = False
                    continue

                dwell_time = now_ts - state["first_seen"]

                if dwell_time >= LOITERING_TIME_SECONDS:
                    if state["alerted"] and (now_ts - state["last_alert_time"]) < LOITERING_ALERT_COOLDOWN_SECONDS:
                        loitering_triggered_ids.add(obj_id)
                        continue

                    is_loiter_duplicate = any(
                        k[0] == "loitering" and k[1] == cls_name and math.hypot(k[2] - anchor_cx, k[3] - anchor_cy) <= 150.0 and (now_ts - ts) < 30.0
                        for k, ts in self._cross_loop_signatures.items()
                    )
                    if is_loiter_duplicate:
                        state["alerted"] = True
                        state["last_alert_time"] = now_ts
                        loitering_triggered_ids.add(obj_id)
                        continue

                    state["alerted"] = True
                    state["last_alert_time"] = now_ts
                    self._cross_loop_signatures[("loitering", cls_name, anchor_cx, anchor_cy)] = now_ts
                    loitering_triggered_ids.add(obj_id)

                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    snapshot_fn = self._save_alert_snapshot(clean_frame.copy(), obj_id, cls_name, now_str)

                    self.total_suspicious_count += 1
                    self.session_suspicious_count += 1
                    
                    suspicious_record = {
                        "id": self.total_suspicious_count,
                        "event_type": "suspicious_activity",
                        "object_id": obj_id,
                        "object_type": cls_name,
                        "timestamp": now_str,
                        "details": f"{cls_name} ID #{obj_id} loitering for {dwell_time:.0f}s within {LOITERING_RADIUS_PIXELS}px",
                        "snapshot_url": f"/alerts/{snapshot_fn}",
                        "snapshot_filename": snapshot_fn
                    }

                    with self._state_lock:
                        self.suspicious_alerts.append(suspicious_record)
                        if len(self.suspicious_alerts) > 50:
                            self.suspicious_alerts.pop(0)

                    self.db_executor.submit(
                        self.db.log_security_event,
                        now_str,
                        "suspicious_activity",
                        self.camera_id,
                        cls_name,
                        obj_id,
                        None,
                        snapshot_fn,
                        f"Loitering {dwell_time:.0f}s within {LOITERING_RADIUS_PIXELS}px"
                    )

                    logger.warning(
                        f"⚠️ [SUSPICIOUS ACTIVITY] #{self.total_suspicious_count} | Person ID #{obj_id} loitering for {dwell_time:.0f}s at {now_str}"
                    )
        t_loiter = (time.perf_counter() - t0_loiter) * 1000.0

        # ─── 3c. Night-Time Movement Alerts ───
        if NIGHT_DETECTION_ENABLED and self.is_night_mode and self.current_brightness <= NIGHT_BRIGHTNESS_THRESHOLD:
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

                self.db_executor.submit(
                    self.db.log_security_event,
                    now_str,
                    "night_movement",
                    self.camera_id,
                    cls_name,
                    obj_id,
                    None,
                    snapshot_fn,
                    f"Movement detected at night (brightness={self.current_brightness}, displacement={movement:.0f}px)"
                )
        t_anpr = 0.0

        # ─── 4. Rate-Limited Multi-Frame Asynchronous ANPR Dispatch ───
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

        # ─── 5. Face Detection (High-Resolution Upper-Body/Head Crops + Global Fallback) ───
        t0_face = time.perf_counter()
        if FACE_DETECTION_ENABLED and self.face_detector is not None:
            self.face_frame_counter += 1
            if self.face_frame_counter >= FACE_DETECTION_INTERVAL:
                self.face_frame_counter = 0
                try:
                    new_faces = []
                    # 1. Target detected persons: inspect high-res head/upper-body crop (top 2 closest/largest persons)
                    person_targets = [
                        obj["bbox"] for obj in tracked_objects.values()
                        if obj["class"] == "Person" and (obj["bbox"][3] - obj["bbox"][1]) >= 60
                    ]
                    person_targets.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
                    
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
                                self.face_detector.setInputSize((crop_w, crop_h))
                                _, faces = self.face_detector.detect(head_crop)
                                if faces is not None and len(faces) > 0:
                                    for face in faces:
                                        conf = float(face[-1]) if len(face) > 14 else 0.8
                                        if conf >= 0.35:
                                            fx = head_x1 + int(face[0])
                                            fy = head_y1 + int(face[1])
                                            fw_f = int(face[2])
                                            fh_f = int(face[3])
                                            new_faces.append((fx, fy, fw_f, fh_f, round(conf, 2)))

                    # 2. If no tracked persons exist in frame, run global downscaled pass
                    elif not person_targets:
                        det_w, det_h = 640, 360
                        small_frame = cv2.resize(clean_frame, (det_w, det_h))
                        self.face_detector.setInputSize((det_w, det_h))
                        _, faces = self.face_detector.detect(small_frame)
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

        # ─── 6. Draw overlays on display frame ───
        t0_draw = time.perf_counter()
        display_frame = clean_frame.copy()
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

            if obj_id in loitering_triggered_ids:
                loiter_label = "!! LOITERING"
                (lw, lh), _ = cv2.getTextSize(loiter_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(display_frame, (x1, y2 + 2), (x1 + lw + 6, y2 + lh + 8), (0, 0, 180), -1)
                cv2.putText(display_frame, loiter_label, (x1 + 3, y2 + lh + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

        if len(self.face_rects_cache) > 0:
            for item in self.face_rects_cache:
                fx, fy, fw_f, fh_f = item[0], item[1], item[2], item[3]
                f_conf = item[4] if len(item) > 4 else 0.8
                cv2.rectangle(display_frame, (fx, fy), (fx + fw_f, fy + fh_f), (255, 215, 0), 2)
                f_lbl = f"Face {f_conf:.2f}"
                (ftw, fth), _ = cv2.getTextSize(f_lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(display_frame, (fx, fy - fth - 5), (fx + ftw + 4, fy), (255, 215, 0), -1)
                cv2.putText(display_frame, f_lbl, (fx + 2, fy - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 20, 40), 1, cv2.LINE_AA)

        # Draw Red Virtual Fence Line
        cv2.line(display_frame, (0, line_y), (w, line_y), (0, 0, 255), 2)
        fence_label = f"VIRTUAL FENCE - INTRUSION ZONE (Y={line_y})"
        (fw, fh), _ = cv2.getTextSize(fence_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(display_frame, (10, line_y - fh - 8), (10 + fw + 10, line_y - 2), (0, 0, 200), -1)
        cv2.putText(display_frame, fence_label, (15, line_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        if NIGHT_DETECTION_ENABLED and self.is_night_mode:
            night_label = f"NIGHT MODE (Brightness: {self.current_brightness})"
            (nw, nh), _ = cv2.getTextSize(night_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(display_frame, (w - nw - 20, 8), (w - 5, nh + 16), (80, 40, 0), -1)
            cv2.putText(display_frame, night_label, (w - nw - 15, nh + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 255), 2, cv2.LINE_AA)
        t_draw = (time.perf_counter() - t0_draw) * 1000.0

        # Accumulate profiling stats
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
        """Dedicated high-speed frame-grabber thread continuously reading RTSP stream into shared raw_frame buffer."""
        grabbed_counter = 0
        last_calc_time = time.time()

        while self.running:
            logger.info(f"Connecting to RTSP stream at {self.rtsp_url}...")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                logger.warning(f"Failed to open RTSP stream at {self.rtsp_url}. Retrying in 2 seconds...")
                with self._frame_lock:
                    self.is_connected = False
                    self.latest_jpeg = self._create_placeholder_frame("Connecting to RTSP Stream...")
                    self.current_fps = 0.0
                time.sleep(2.0)
                continue

            with self._frame_lock:
                self.is_connected = True
                logger.info(f"Successfully connected to RTSP stream: {self.rtsp_url}")

            resolution_logged = False
            while self.running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    logger.warning("RTSP frame grab failed or stream ended. Reconnecting...")
                    break

                grabbed_counter += 1
                now = time.time()
                if (now - last_calc_time) >= 3.0:
                    self.capture_fps = round(grabbed_counter / (now - last_calc_time), 1)
                    grabbed_counter = 0
                    last_calc_time = now

                if not resolution_logged:
                    fh, fw = frame.shape[:2]
                    fence_y_px = int(fh * self.line_y_ratio)
                    aspect = "Landscape" if fw >= fh else "Portrait"
                    logger.info(
                        f"📐 [STREAM RESOLUTION DETECTED] Frame size: {fw}x{fh} ({aspect}) | Virtual Fence line set at {int(self.line_y_ratio*100)}% down frame (Pixel Y = {fence_y_px}px)"
                    )
                    resolution_logged = True

                with self._raw_frame_lock:
                    self.raw_frame = frame
                    self.raw_frame_id += 1
                    self.raw_frame_res = frame.shape[:2]

            cap.release()
            with self._frame_lock:
                self.is_connected = False
                self.current_fps = 0.0
                self.latest_jpeg = self._create_placeholder_frame("Reconnecting to RTSP Stream...")
            time.sleep(1.0)

    def _ai_processing_loop(self):
        """Dedicated high-speed AI processing thread reading newest grabbed frame without pipeline stalls."""
        fps_timer_start = time.time()
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
                logger.error(f"Error in _process_frame_ai: {e}")
                processed_frame = frame_to_process
                p_cnt = 0
                v_cnt = 0

            # JPEG Compression for MJPEG stream
            t0_enc = time.perf_counter()
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
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
                avg_face = self.profile_accum["face_ms"] / f_count
                avg_draw = self.profile_accum["draw_ms"] / f_count
                avg_enc = self.profile_accum["encode_ms"] / f_count
                avg_total = avg_detect + avg_track + avg_face + avg_draw + avg_enc

                det_rate = self.profile_accum["detector_calls"] / elapsed
                ocr_rate = self.profile_accum["ocr_calls"] / elapsed

                logger.info(
                    f"⏱️ [PROFILING] AI FPS: {fps:.1f} (Capture: {self.capture_fps:.1f} FPS) | Frame AI Avg: {avg_total:.1f}ms "
                    f"(YOLO: {avg_detect:.1f}ms | Track: {avg_track:.1f}ms | Face: {avg_face:.1f}ms | Draw: {avg_draw:.1f}ms | Encode: {avg_enc:.1f}ms) | "
                    f"ANPR Det/sec: {det_rate:.2f} | OCR/sec: {ocr_rate:.2f} | Detections -> People: {p_cnt}, Vehicles: {v_cnt} | Total Alerts: {self.session_alerts_count}"
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
                return self._create_placeholder_frame("Initializing Feed...")
            return self.latest_jpeg

    def get_status(self) -> dict:
        """Returns stream status dictionary including AI object counts, intrusion alerts, and new feature metrics."""
        now = time.time()
        if not hasattr(self, "_cached_db_totals") or (now - getattr(self, "_last_db_totals_time", 0)) > 5.0:
            try:
                self._cached_db_totals = self.db.get_total_counts() if hasattr(self.db, "get_total_counts") else {"total_intrusions": self.total_alerts_count, "total_anpr": self.total_anpr_count, "total_security": 0}
                self._last_db_totals_time = now
            except Exception:
                self._cached_db_totals = getattr(self, "_cached_db_totals", {"total_intrusions": self.total_alerts_count, "total_anpr": self.total_anpr_count, "total_security": 0})

        db_totals = self._cached_db_totals
        with self._state_lock:
            return {
                "connected": self.is_connected,
                "fps": self.current_fps,
                "capture_fps": self.capture_fps,
                "total_frames": self.frame_count,
                "rtsp_url": self.rtsp_url,
                "device": self.device,
                "camera_id": self.camera_id,
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
                "night_alert_count": self.session_night_count,
                "brightness": self.current_brightness,
                "face_count": self.face_count,
                "anpr_queue_size": self.anpr_queue.qsize() if hasattr(self, "anpr_queue") else 0,
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
            "is_night_mode": self.is_night_mode,
            "brightness": self.current_brightness,
            "threshold": NIGHT_BRIGHTNESS_THRESHOLD,
            "night_alert_count": self.total_night_alerts
        }

    def get_face_stats(self) -> dict:
        """Returns face detection statistics."""
        return {
            "face_count": self.face_count,
            "face_detection_enabled": FACE_DETECTION_ENABLED and self.face_detector is not None,
            "detection_interval": FACE_DETECTION_INTERVAL
        }
