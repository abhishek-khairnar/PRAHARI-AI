"""
PRAHARI-AI Multi-Camera & Source Manager
Manages simultaneous video streams (RTSP, local video files, USB/integrated webcams).
Maintains isolated RTSPStreamReader instances per camera with independent tracking,
intrusion boundaries, ANPR, suspicious activity, and night detection states.
"""

import os
import sys
import time
import logging
import psutil
import torch
import cv2
from rtsp_stream import RTSPStreamReader

logger = logging.getLogger("CameraManager")

# ─── Default Multi-Camera Configuration ───
# Supports 4 simultaneous video feeds + optional webcam
DEFAULT_CAMERAS = [
    {
        "id": "CAM-01",
        "name": "Border Post Alpha",
        "type": "video_file",
        "url": "demo_videos/border_demo.mp4",
        "enabled": True,
        "line_y_ratio": 0.70
    },
    {
        "id": "CAM-02",
        "name": "Night Surveillance Bravo",
        "type": "video_file",
        "url": "demo_videos/night_demo.mp4",
        "enabled": True,
        "line_y_ratio": 0.65
    },
    {
        "id": "CAM-03",
        "name": "Perimeter Activity Charlie",
        "type": "video_file",
        "url": "demo_videos/activity-demo.mp4",
        "enabled": True,
        "line_y_ratio": 0.60
    },
    {
        "id": "CAM-04",
        "name": "Urban Facility Delta",
        "type": "video_file",
        "url": "demo_videos/cctv_demo.mp4",
        "enabled": True,
        "line_y_ratio": 0.70
    },
]

# Backward compatibility alias
CAMERAS = DEFAULT_CAMERAS


class CameraManager:
    """Central manager for all active surveillance camera readers."""

    def __init__(self, camera_configs: list = None):
        self.configs = camera_configs or DEFAULT_CAMERAS
        self.readers = {}  # camera_id -> RTSPStreamReader
        self.webcam_reader = None

        for cam in self.configs:
            if not cam.get("enabled", True):
                logger.info(f"Camera {cam['id']} ({cam.get('name', '')}) is disabled, skipping.")
                continue

            try:
                # Check if an active zone configuration exists in SQLite for this camera
                initial_line_ratio = cam.get("line_y_ratio", 0.70)
                try:
                    from database import db_manager
                    cam_zones = db_manager.list_admin_zones(camera_id=cam["id"], is_enabled=1)
                    if cam_zones and cam_zones[0].get("fence_ratio") is not None:
                        initial_line_ratio = float(cam_zones[0]["fence_ratio"])
                        logger.info(f"Loaded persistent zone fence ratio for [{cam['id']}]: {initial_line_ratio}")
                except Exception:
                    pass

                reader = RTSPStreamReader(
                    rtsp_url=cam["url"],
                    camera_id=cam["id"],
                    camera_name=cam.get("name", cam["id"]),
                    source_type=cam.get("type", "video_file"),
                    line_y_ratio=initial_line_ratio,
                    fps_log_interval=4.0
                )
                self.readers[cam["id"]] = reader
                logger.info(f"Registered Camera [{cam['id']}] ({cam.get('name', '')}) -> Source: {cam['url']}")
            except Exception as e:
                logger.error(f"Error registering camera {cam.get('id')}: {e}")

    def start_all(self):
        """Starts all configured camera readers."""
        for cam_id, reader in self.readers.items():
            try:
                reader.start()
                logger.info(f"Started camera pipeline: {cam_id}")
            except Exception as e:
                logger.error(f"Failed to start camera {cam_id}: {e}")

    def stop_all(self):
        """Stops all active camera readers."""
        for cam_id, reader in self.readers.items():
            try:
                reader.stop()
                logger.info(f"Stopped camera pipeline: {cam_id}")
            except Exception as e:
                logger.error(f"Error stopping camera {cam_id}: {e}")

        if self.webcam_reader:
            try:
                self.webcam_reader.stop()
            except Exception:
                pass
            self.webcam_reader = None

    def start_camera(self, camera_id: str) -> bool:
        """Starts an individual camera if present and not already running."""
        if camera_id in self.readers:
            self.readers[camera_id].start()
            return True
        return False

    def stop_camera(self, camera_id: str) -> bool:
        """Stops an individual camera reader."""
        if camera_id in self.readers:
            self.readers[camera_id].stop()
            return True
        return False

    def get_reader(self, camera_id: str = None) -> RTSPStreamReader:
        """Returns specific camera reader. Defaults to CAM-01 or first available."""
        if camera_id:
            if camera_id in self.readers:
                return self.readers[camera_id]
            if camera_id == "CAM-WEBCAM" and self.webcam_reader:
                return self.webcam_reader

        # Default fallback
        if "CAM-01" in self.readers:
            return self.readers["CAM-01"]
        if self.readers:
            return next(iter(self.readers.values()))
        return None

    def get_all_readers(self) -> dict:
        """Returns dictionary of all active readers."""
        all_r = dict(self.readers)
        if self.webcam_reader:
            all_r["CAM-WEBCAM"] = self.webcam_reader
        return all_r

    def get_all_status(self) -> list:
        """Returns status list for all configured and dynamic cameras."""
        statuses = []
        for cam_id, reader in self.readers.items():
            st = reader.get_status()
            statuses.append(st)

        if self.webcam_reader:
            statuses.append(self.webcam_reader.get_status())

        return statuses

    def get_camera_list(self) -> list:
        """Returns formatted list of cameras for API and UI rendering."""
        result = []
        for cam in self.configs:
            cam_id = cam["id"]
            cam_info = {
                "id": cam_id,
                "name": cam.get("name", cam_id),
                "url": str(cam.get("url", "")),
                "type": cam.get("type", "video_file"),
                "enabled": cam.get("enabled", True),
                "active": cam_id in self.readers and self.readers[cam_id].running,
            }
            if cam_id in self.readers:
                reader = self.readers[cam_id]
                cam_info["connected"] = reader.is_connected
                cam_info["status"] = reader.status
                cam_info["fps"] = reader.current_fps
                cam_info["capture_fps"] = reader.capture_fps
                cam_info["night_mode"] = reader.is_night_mode
                cam_info["night_state"] = reader.night_state_str
                cam_info["brightness"] = reader.current_brightness
                cam_info["face_count"] = reader.face_count
                cam_info["people_count"] = reader.people_count
                cam_info["vehicle_count"] = reader.vehicle_count
                cam_info["total_objects"] = reader.total_objects
                cam_info["detected_objects"] = {
                    "people_count": reader.people_count,
                    "vehicle_count": reader.vehicle_count,
                    "total_objects": reader.total_objects
                }
                cam_info["session_alerts"] = reader.session_alerts_count
            result.append(cam_info)

        if self.webcam_reader:
            w_st = self.webcam_reader.get_status()
            result.append({
                "id": "CAM-WEBCAM",
                "name": "Live Integrated/USB Webcam",
                "url": "0",
                "type": "webcam",
                "enabled": True,
                "active": self.webcam_reader.running,
                "connected": self.webcam_reader.is_connected,
                "status": self.webcam_reader.status,
                "fps": self.webcam_reader.current_fps,
                "capture_fps": self.webcam_reader.capture_fps,
                "night_mode": self.webcam_reader.is_night_mode,
                "night_state": self.webcam_reader.night_state_str,
                "brightness": self.webcam_reader.current_brightness,
                "face_count": self.webcam_reader.face_count,
                "people_count": self.webcam_reader.people_count,
                "vehicle_count": self.webcam_reader.vehicle_count,
                "total_objects": self.webcam_reader.total_objects,
                "detected_objects": {
                    "people_count": self.webcam_reader.people_count,
                    "vehicle_count": self.webcam_reader.vehicle_count,
                    "total_objects": self.webcam_reader.total_objects
                },
                "session_alerts": self.webcam_reader.session_alerts_count
            })

        return result

    def get_aggregate_status(self) -> dict:
        """Computes system-wide aggregate telemetry including GPU, CPU, AI throughput, and incident metrics."""
        all_r = self.get_all_readers()
        total_ai_fps = sum(r.current_fps for r in all_r.values())
        total_capture_fps = sum(r.capture_fps for r in all_r.values())
        total_people = sum(r.people_count for r in all_r.values())
        total_vehicles = sum(r.vehicle_count for r in all_r.values())
        total_session_alerts = sum(r.session_alerts_count for r in all_r.values())
        total_session_anpr = sum(r.session_anpr_count for r in all_r.values())
        total_session_suspicious = sum(r.session_suspicious_count for r in all_r.values())
        total_session_night = sum(r.session_night_count for r in all_r.values())

        # GPU metrics via pynvml (real hardware telemetry) / PyTorch CUDA
        gpu_info = {
            "available": False,
            "name": "CPU Fallback",
            "device_name": "CPU Fallback",
            "gpu_util_pct": None,
            "vram_used_mb": 0,
            "vram_total_mb": 0,
            "vram_pct": None
        }
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(gpu_name, bytes):
                gpu_name = gpu_name.decode("utf-8")
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_used = round(mem.used / (1024 * 1024), 1)
            vram_total = round(mem.total / (1024 * 1024), 1)
            vram_pct = round((mem.used / mem.total) * 100.0, 1) if mem.total > 0 else 0.0
            gpu_info = {
                "available": True,
                "name": gpu_name,
                "device_name": gpu_name,
                "gpu_util_pct": int(util.gpu),
                "vram_used_mb": vram_used,
                "vram_total_mb": vram_total,
                "vram_pct": vram_pct
            }
        except Exception:
            if torch.cuda.is_available():
                try:
                    dev = 0
                    gpu_name = torch.cuda.get_device_name(dev)
                    total_vram = torch.cuda.get_device_properties(dev).total_memory / (1024 * 1024)
                    allocated = torch.cuda.memory_allocated(dev) / (1024 * 1024)
                    reserved = torch.cuda.memory_reserved(dev) / (1024 * 1024)
                    used_vram = max(allocated, reserved)
                    vram_pct = (used_vram / total_vram * 100.0) if total_vram > 0 else 0.0
                    gpu_info = {
                        "available": True,
                        "name": gpu_name,
                        "device_name": gpu_name,
                        "gpu_util_pct": None,
                        "vram_used_mb": round(used_vram, 1),
                        "vram_total_mb": round(total_vram, 1),
                        "vram_pct": round(vram_pct, 1)
                    }
                except Exception:
                    pass

        # CPU & RAM
        cpu_pct = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        # Face count only from currently connected cameras
        total_faces = sum(getattr(r, "face_count", 0) for r in all_r.values() if getattr(r, "is_connected", False))

        # Persisted database metrics (cached with 1.0s throttle for efficiency)
        now = time.time()
        if not hasattr(self, "_cached_db_incident_summary") or (now - getattr(self, "_last_db_summary_time", 0)) > 1.0:
            try:
                from database import db_manager
                self._cached_db_incident_summary = db_manager.count_admin_incidents_summary()
                self._cached_verified_anpr = db_manager.get_verified_anpr_count()
                self._cached_db_healthy = db_manager.is_healthy()
                self._last_db_summary_time = now
            except Exception as e:
                logger.error(f"Error refreshing database aggregate metrics: {e}")
                self._cached_db_incident_summary = {"open": 0, "active_critical": 0, "active_high": 0, "active_medium": 0}
                self._cached_verified_anpr = 0
                self._cached_db_healthy = False

        inc_summary = getattr(self, "_cached_db_incident_summary", {})
        active_incidents = inc_summary.get("open", 0)
        active_critical = inc_summary.get("active_critical", 0)
        active_high = inc_summary.get("active_high", 0)
        active_medium = inc_summary.get("active_medium", 0)
        verified_anpr = getattr(self, "_cached_verified_anpr", 0)
        db_healthy = getattr(self, "_cached_db_healthy", True)

        # Threat Status derivation from active unresolved incidents
        if active_critical > 0:
            threat_level = "CRITICAL"
            threat_score = 25
        elif active_high > 0:
            threat_level = "HIGH"
            threat_score = 15
        elif active_medium > 0:
            threat_level = "ELEVATED"
            threat_score = 8
        else:
            threat_level = "NORMAL"
            threat_score = 0

        # System Health derivation: all cameras connected + AI inference active + DB online
        active_cams = sum(1 for r in all_r.values() if r.is_connected)
        total_cams = len(all_r)
        all_cams_online = (active_cams >= total_cams and total_cams > 0)
        ai_healthy = (total_ai_fps > 0.0)

        if not db_healthy or active_cams == 0:
            system_health = "OFFLINE"
            system_health_desc = "Critical subsystem failure"
        elif all_cams_online and ai_healthy:
            system_health = "OPTIMAL"
            system_health_desc = "All pipelines nominal"
        else:
            system_health = "DEGRADED"
            system_health_desc = f"{total_cams - active_cams} channel(s) offline" if not all_cams_online else "AI inference degraded"

        return {
            "total_cameras": total_cams,
            "active_cameras": active_cams,
            "aggregate_ai_fps": round(total_ai_fps, 1),
            "aggregate_capture_fps": round(total_capture_fps, 1),
            "total_people_detected": total_people,
            "total_vehicles_detected": total_vehicles,
            "total_live_faces": total_faces,
            "total_session_alerts": total_session_alerts,
            "total_session_anpr": total_session_anpr,
            "total_session_suspicious": total_session_suspicious,
            "total_session_night": total_session_night,
            "gpu": gpu_info,
            "cpu_percent": cpu_pct,
            "ram_used_gb": round((ram.total - ram.available) / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_percent": ram.percent,
            "active_security_incidents": active_incidents,
            "active_critical_incidents": active_critical,
            "active_incidents_count": active_incidents,
            "active_critical_count": active_critical,
            "verified_anpr_reads": verified_anpr,
            "threat_level": threat_level,
            "threat_score": threat_score,
            "system_health": system_health,
            "system_health_desc": system_health_desc,
            "server_timestamp": now,
        }

    def enable_webcam(self, device_index: int = 0) -> dict:
        """Starts live webcam input as CAM-WEBCAM."""
        if self.webcam_reader and self.webcam_reader.running:
            return {"status": "already_running", "camera_id": "CAM-WEBCAM"}

        try:
            self.webcam_reader = RTSPStreamReader(
                rtsp_url=int(device_index),
                camera_id="CAM-WEBCAM",
                camera_name="Live Integrated/USB Webcam",
                source_type="webcam",
                fps_log_interval=4.0
            )
            self.webcam_reader.start()
            logger.info(f"Webcam CAM-WEBCAM started on device index {device_index}")
            return {"status": "started", "camera_id": "CAM-WEBCAM"}
        except Exception as e:
            logger.error(f"Failed to start webcam: {e}")
            return {"status": "error", "error": str(e)}

    def disable_webcam(self) -> dict:
        """Stops and removes CAM-WEBCAM."""
        if self.webcam_reader:
            try:
                self.webcam_reader.stop()
            except Exception as e:
                logger.error(f"Error stopping webcam: {e}")
            self.webcam_reader = None
            return {"status": "stopped", "camera_id": "CAM-WEBCAM"}
        return {"status": "not_active"}

    @staticmethod
    def enumerate_webcams(max_probe: int = 3) -> list:
        """Safely probes for available webcam device indices on the system."""
        available = []
        for i in range(max_probe):
            try:
                if sys.platform == "win32":
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        available.append({"index": i, "name": f"Webcam Device #{i} ({w}x{h})"})
                    cap.release()
            except Exception:
                pass
        return available


# Global Singleton Camera Manager Instance
camera_manager = CameraManager()
