"""
PRAHARI-AI Multi-Camera & Source Manager
Manages simultaneous video streams (RTSP, local video files, USB/integrated webcams).
Maintains isolated RTSPStreamReader instances per camera with independent tracking,
intrusion boundaries, ANPR, suspicious activity, and night detection states.
"""

import os
import sys
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
                reader = RTSPStreamReader(
                    rtsp_url=cam["url"],
                    camera_id=cam["id"],
                    camera_name=cam.get("name", cam["id"]),
                    source_type=cam.get("type", "video_file"),
                    line_y_ratio=cam.get("line_y_ratio", 0.70),
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
        """Computes system-wide aggregate telemetry including GPU, CPU, and AI throughput."""
        all_r = self.get_all_readers()
        total_ai_fps = sum(r.current_fps for r in all_r.values())
        total_capture_fps = sum(r.capture_fps for r in all_r.values())
        total_people = sum(r.people_count for r in all_r.values())
        total_vehicles = sum(r.vehicle_count for r in all_r.values())
        total_session_alerts = sum(r.session_alerts_count for r in all_r.values())
        total_session_anpr = sum(r.session_anpr_count for r in all_r.values())
        total_session_suspicious = sum(r.session_suspicious_count for r in all_r.values())
        total_session_night = sum(r.session_night_count for r in all_r.values())

        # GPU metrics via PyTorch / CUDA
        gpu_info = {"available": torch.cuda.is_available(), "name": "CPU Fallback", "device_name": "CPU Fallback", "vram_used_mb": 0, "vram_total_mb": 0, "vram_pct": 0.0}
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
                    "vram_used_mb": round(used_vram, 1),
                    "vram_total_mb": round(total_vram, 1),
                    "vram_pct": round(vram_pct, 1)
                }
            except Exception:
                pass

        # CPU & RAM
        cpu_pct = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        total_faces = sum(getattr(r, "face_count", 0) for r in all_r.values())

        return {
            "total_cameras": len(all_r),
            "active_cameras": sum(1 for r in all_r.values() if r.is_connected),
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
            "ram_percent": ram.percent
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
