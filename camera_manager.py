"""
PRAHARI-AI Multi-Camera Manager
Lightweight foundation for managing multiple RTSP camera streams.
Each camera gets its own RTSPStreamReader with independent detection pipeline.
"""

import logging
from rtsp_stream import RTSPStreamReader

logger = logging.getLogger("CameraManager")

# ─── Multi-Camera Configuration ───
# Add cameras here. Each entry gets an independent processing pipeline.
# For development/demo, the same RTSP source can be used for multiple cameras.
CAMERAS = [
    {"id": "CAM-01", "name": "Border Post Alpha", "url": "rtsp://localhost:8554/mystream", "enabled": True},
    # Uncomment below to enable second camera (doubles GPU load):
    # {"id": "CAM-02", "name": "Border Post Bravo", "url": "rtsp://localhost:8554/mystream", "enabled": True},
]


class CameraManager:
    """Manages multiple RTSPStreamReader instances, one per configured camera."""

    def __init__(self, camera_configs: list = None):
        self.configs = camera_configs or CAMERAS
        self.readers = {}  # camera_id -> RTSPStreamReader

        for cam in self.configs:
            if not cam.get("enabled", True):
                logger.info(f"Camera {cam['id']} ({cam.get('name', '')}) is disabled, skipping.")
                continue

            reader = RTSPStreamReader(rtsp_url=cam["url"], fps_log_interval=3.0)
            reader.camera_id = cam["id"]
            self.readers[cam["id"]] = reader
            logger.info(f"Camera {cam['id']} ({cam.get('name', '')}) registered with URL: {cam['url']}")

    def start_all(self):
        """Start all enabled camera readers."""
        for cam_id, reader in self.readers.items():
            reader.start()
            logger.info(f"Camera {cam_id} started.")

    def stop_all(self):
        """Stop all camera readers."""
        for cam_id, reader in self.readers.items():
            reader.stop()
            logger.info(f"Camera {cam_id} stopped.")

    def get_reader(self, camera_id: str = None) -> RTSPStreamReader:
        """Get a specific camera reader. Defaults to first available camera."""
        if camera_id and camera_id in self.readers:
            return self.readers[camera_id]
        # Default: return first reader
        if self.readers:
            return next(iter(self.readers.values()))
        return None

    def get_all_status(self) -> list:
        """Returns status for all cameras."""
        statuses = []
        for cam_id, reader in self.readers.items():
            config = next((c for c in self.configs if c["id"] == cam_id), {})
            status = reader.get_status()
            status["camera_name"] = config.get("name", cam_id)
            statuses.append(status)
        return statuses

    def get_camera_list(self) -> list:
        """Returns list of all configured cameras with their status."""
        result = []
        for cam in self.configs:
            cam_info = {
                "id": cam["id"],
                "name": cam.get("name", cam["id"]),
                "url": cam.get("url", ""),
                "enabled": cam.get("enabled", True),
                "active": cam["id"] in self.readers,
            }
            if cam["id"] in self.readers:
                reader = self.readers[cam["id"]]
                cam_info["connected"] = reader.is_connected
                cam_info["fps"] = reader.current_fps
            result.append(cam_info)
        return result
