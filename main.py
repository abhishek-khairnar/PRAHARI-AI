import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from rtsp_stream import RTSPStreamReader

# Read RTSP URL from environment variable or default to localhost:8554/mystream
RTSP_URL = os.getenv("RTSP_URL", "rtsp://localhost:8554/mystream")

# Instantiate RTSP Stream Reader with Virtual Fence Intrusion Detection
rtsp_reader = RTSPStreamReader(rtsp_url=RTSP_URL, fps_log_interval=3.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start RTSP Reader thread
    rtsp_reader.start()
    yield
    # Shutdown: Stop RTSP Reader thread
    rtsp_reader.stop()


app = FastAPI(
    title="RTSP Live Surveillance Streamer with Intrusion Detection",
    description="RTSP to MJPEG HTTP streaming server with OpenCV, YOLO AI, and Virtual Fence Intrusion Alerts",
    lifespan=lifespan
)

# Mount static directory to serve snapshot images via /alerts/{filename}
alerts_dir = os.path.join(os.path.dirname(__file__), "static", "alerts")
os.makedirs(alerts_dir, exist_ok=True)
app.mount("/alerts", StaticFiles(directory=alerts_dir), name="alerts")

anpr_dir = os.path.join(os.path.dirname(__file__), "static", "anpr")
os.makedirs(anpr_dir, exist_ok=True)
app.mount("/anpr", StaticFiles(directory=anpr_dir), name="anpr")

anpr_debug_dir = os.path.join(os.path.dirname(__file__), "static", "anpr_debug")
os.makedirs(anpr_debug_dir, exist_ok=True)
app.mount("/anpr_debug", StaticFiles(directory=anpr_debug_dir), name="anpr_debug")


def mjpeg_generator():
    """Generator function yielding multipart JPEG frames for HTTP MJPEG streaming."""
    while True:
        frame_bytes = rtsp_reader.get_latest_frame()
        if frame_bytes and len(frame_bytes) > 0:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n' +
                frame_bytes + b'\r\n'
            )
        time.sleep(0.025)  # Non-blocking stream transmission cap (~40 FPS)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serves the live video surveillance web interface."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>RTSP Monitor</h1><p>index.html template not found.</p>")


@app.get("/video_feed")
async def video_feed():
    """MJPEG Video Streaming Endpoint."""
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/status")
async def status():
    """JSON API endpoint returning connection state, current FPS, AI metrics, and total alerts."""
    return JSONResponse(content=rtsp_reader.get_status())


@app.get("/api/alerts")
async def alerts():
    """JSON API endpoint returning recent intrusion alerts with snapshot URLs."""
    return JSONResponse(content=rtsp_reader.get_alerts())


@app.get("/api/anpr_log")
async def anpr_log():
    """JSON API endpoint returning recent ANPR license plate reads with plate crops."""
    return JSONResponse(content=rtsp_reader.get_anpr_logs())


@app.get("/api/anpr_debug")
async def anpr_debug():
    """JSON API endpoint returning recent ANPR candidate debug crops."""
    return JSONResponse(content=rtsp_reader.get_anpr_debug_crops())


@app.get("/api/events/all")
async def get_all_events(limit: int = 50, offset: int = 0):
    """JSON API endpoint returning paginated full historical event logs from SQLite database."""
    from database import db_manager
    return JSONResponse(content=db_manager.get_all_events(limit=limit, offset=offset))


@app.get("/api/sync_status")
async def get_sync_status():
    """JSON API endpoint returning offline-first sync engine metrics and pending status."""
    from database import db_manager
    return JSONResponse(content=db_manager.get_sync_status())


@app.get("/api/security_events")
async def get_security_events(event_type: str = None, limit: int = 50):
    """JSON API endpoint returning recent security events with optional event_type filter."""
    from database import db_manager
    return JSONResponse(content=db_manager.get_recent_security_events(event_type=event_type, limit=limit))


@app.get("/api/suspicious_alerts")
async def get_suspicious_alerts():
    """JSON API endpoint returning recent suspicious activity / loitering alerts."""
    return JSONResponse(content=rtsp_reader.get_suspicious_alerts())


@app.get("/api/night_status")
async def get_night_status():
    """JSON API endpoint returning current night mode status and brightness."""
    return JSONResponse(content=rtsp_reader.get_night_status())


@app.get("/api/face_stats")
async def get_face_stats():
    """JSON API endpoint returning face detection statistics."""
    return JSONResponse(content=rtsp_reader.get_face_stats())


@app.get("/api/dashboard_stats")
async def get_dashboard_stats():
    """JSON API endpoint returning combined stats for dashboard polling."""
    status = rtsp_reader.get_status()
    night = rtsp_reader.get_night_status()
    face = rtsp_reader.get_face_stats()
    return JSONResponse(content={
        "suspicious_activity_count": status.get("suspicious_activity_count", 0),
        "night_mode": night,
        "face": face,
        "night_alert_count": status.get("night_alert_count", 0),
    })


@app.get("/api/cameras")
async def get_cameras():
    """JSON API endpoint returning list of configured cameras and their status."""
    from camera_manager import CAMERAS
    camera_list = []
    for cam in CAMERAS:
        cam_info = {
            "id": cam["id"],
            "name": cam.get("name", cam["id"]),
            "url": cam.get("url", ""),
            "enabled": cam.get("enabled", True),
            "active": cam["id"] == "CAM-01",  # Current single-camera mode
        }
        if cam["id"] == "CAM-01":
            cam_info["connected"] = rtsp_reader.is_connected
            cam_info["fps"] = rtsp_reader.current_fps
        camera_list.append(cam_info)
    return JSONResponse(content=camera_list)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import uvicorn
    PORT = int(os.getenv("PORT", 8001))
    device_name = rtsp_reader.device.upper()
    gpu_status = "CUDA GPU Accelerated" if rtsp_reader.device == "cuda" else "CPU (Fallback)"
    print("\n" + "="*65)
    print(" Starting RTSP Surveillance Analytics Server...")
    print(f" Target RTSP Stream: {RTSP_URL}")
    print(f" AI Inference Device:{device_name} ({gpu_status})")
    print(f" Web Interface:       http://localhost:{PORT}")
    print(f" Video Feed Endpoint: http://localhost:{PORT}/video_feed")
    print(f" Intrusion Alerts API:http://localhost:{PORT}/api/alerts")
    print(f" ANPR License Plates: http://localhost:{PORT}/api/anpr_log")
    print("="*65 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
