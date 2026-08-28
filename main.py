"""
PRAHARI-AI Multi-Camera Surveillance Server
FastAPI HTTP & MJPEG streaming server with multi-source video ingestion,
independent AI analytics per camera feed, and real-time command center APIs.
"""

import os
import time
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from camera_manager import camera_manager
from database import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start all configured camera pipelines
    camera_manager.start_all()
    yield
    # Shutdown: Stop all camera pipelines cleanly
    camera_manager.stop_all()


app = FastAPI(
    title="PRAHARI-AI Multi-Camera Intelligent Surveillance Platform",
    description="Multi-Camera Real-Time AI Surveillance with Virtual Fence, ANPR, YuNet Face, Loitering, and Night Detection",
    lifespan=lifespan
)

# Mount static snapshot directories
alerts_dir = os.path.join(os.path.dirname(__file__), "static", "alerts")
os.makedirs(alerts_dir, exist_ok=True)
app.mount("/alerts", StaticFiles(directory=alerts_dir), name="alerts")

anpr_dir = os.path.join(os.path.dirname(__file__), "static", "anpr")
os.makedirs(anpr_dir, exist_ok=True)
app.mount("/anpr", StaticFiles(directory=anpr_dir), name="anpr")

anpr_debug_dir = os.path.join(os.path.dirname(__file__), "static", "anpr_debug")
os.makedirs(anpr_debug_dir, exist_ok=True)
app.mount("/anpr_debug", StaticFiles(directory=anpr_debug_dir), name="anpr_debug")


def mjpeg_generator(camera_id: str = None):
    """Generator yielding multipart JPEG frames for HTTP MJPEG streaming for a given camera."""
    while True:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            frame_bytes = reader.get_latest_frame()
            if frame_bytes and len(frame_bytes) > 0:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n' +
                    frame_bytes + b'\r\n'
                )
        time.sleep(0.033)  # Transmission cap (~30 FPS)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serves the live multi-camera video surveillance command center web interface."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>PRAHARI-AI Command Center</h1><p>index.html template not found.</p>")


# ─── Live Video Streaming Endpoints ───

@app.get("/video_feed")
async def video_feed(camera_id: Optional[str] = None):
    """MJPEG Video Streaming Endpoint (Defaults to CAM-01 for backward compatibility)."""
    return StreamingResponse(
        mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/video_feed/{camera_id}")
async def video_feed_by_camera(camera_id: str):
    """Dedicated MJPEG Video Streaming Endpoint for a specific camera (e.g. CAM-01, CAM-02, CAM-WEBCAM)."""
    return StreamingResponse(
        mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ─── Telemetry & Camera Management APIs ───

@app.get("/api/cameras")
async def get_cameras():
    """Returns list of configured and active cameras with real-time status and telemetry."""
    return JSONResponse(content=camera_manager.get_camera_list())


@app.get("/api/status")
async def status(camera_id: Optional[str] = None):
    """
    Returns system status. If camera_id provided, returns that camera's status;
    otherwise returns aggregate system metrics + primary camera telemetry.
    """
    if camera_id:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            return JSONResponse(content=reader.get_status())
        return JSONResponse(status_code=404, content={"error": f"Camera {camera_id} not found"})

    primary_reader = camera_manager.get_reader("CAM-01")
    primary_status = primary_reader.get_status() if primary_reader else {}
    aggregate = camera_manager.get_aggregate_status()

    # Combine aggregate and primary status for 100% backward compatibility
    combined = dict(primary_status)
    combined["aggregate"] = aggregate
    combined["total_cameras"] = aggregate["total_cameras"]
    combined["active_cameras"] = aggregate["active_cameras"]
    combined["aggregate_ai_fps"] = aggregate["aggregate_ai_fps"]
    combined["aggregate_capture_fps"] = aggregate["aggregate_capture_fps"]
    combined["gpu_telemetry"] = aggregate["gpu"]
    return JSONResponse(content=combined)


@app.get("/api/status/{camera_id}")
async def status_by_camera(camera_id: str):
    """Returns status dictionary for a specific camera."""
    reader = camera_manager.get_reader(camera_id)
    if reader:
        return JSONResponse(content=reader.get_status())
    return JSONResponse(status_code=404, content={"error": f"Camera {camera_id} not found"})


@app.get("/api/dashboard_stats")
async def get_dashboard_stats():
    """Returns combined stats for dashboard polling."""
    aggregate = camera_manager.get_aggregate_status()
    all_statuses = camera_manager.get_all_status()
    
    primary = camera_manager.get_reader("CAM-01")
    night = primary.get_night_status() if primary else {"is_night_mode": False, "brightness": 0.0}
    face = primary.get_face_stats() if primary else {"face_count": 0}

    return JSONResponse(content={
        "aggregate": aggregate,
        "cameras": all_statuses,
        "suspicious_activity_count": aggregate["total_session_suspicious"],
        "night_mode": night,
        "face": face,
        "night_alert_count": aggregate["total_session_night"],
    })


@app.get("/api/analytics")
async def get_analytics():
    """Returns calculated historical statistical data directly from the SQLite database."""
    return JSONResponse(content=db_manager.get_analytics_summary())


# ─── Alert & Event Endpoints ───

@app.get("/api/alerts")
async def alerts(camera_id: Optional[str] = None, limit: int = 50):
    """Returns recent intrusion alerts with snapshot URLs (Filterable by camera_id)."""
    if camera_id:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            return JSONResponse(content=reader.get_alerts()[:limit])
        return JSONResponse(content=db_manager.get_recent_intrusions(limit=limit, camera_id=camera_id))

    # All cameras: combine recent alerts from active readers or DB
    all_alerts = []
    for r in camera_manager.get_all_readers().values():
        all_alerts.extend(r.get_alerts())
    all_alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    if not all_alerts:
        all_alerts = db_manager.get_recent_intrusions(limit=limit)
    return JSONResponse(content=all_alerts[:limit])


@app.get("/api/anpr_log")
async def anpr_log(camera_id: Optional[str] = None, limit: int = 50):
    """Returns recent ANPR license plate reads with plate crops (Filterable by camera_id)."""
    if camera_id:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            return JSONResponse(content=reader.get_anpr_logs()[:limit])
        return JSONResponse(content=db_manager.get_recent_anpr(limit=limit, camera_id=camera_id))

    all_anpr = []
    for r in camera_manager.get_all_readers().values():
        all_anpr.extend(r.get_anpr_logs())
    all_anpr.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    if not all_anpr:
        all_anpr = db_manager.get_recent_anpr(limit=limit)
    return JSONResponse(content=all_anpr[:limit])


@app.get("/api/anpr_debug")
async def anpr_debug(camera_id: Optional[str] = None, limit: int = 50):
    """Returns recent ANPR candidate debug crops (Filterable by camera_id)."""
    if camera_id:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            return JSONResponse(content=reader.get_anpr_debug_crops()[:limit])
        return JSONResponse(content=[])

    all_debug = []
    for r in camera_manager.get_all_readers().values():
        all_debug.extend(r.get_anpr_debug_crops())
    all_debug.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    return JSONResponse(content=all_debug[:limit])


@app.get("/api/security_events")
async def get_security_events(event_type: Optional[str] = None, camera_id: Optional[str] = None, limit: int = 50):
    """Returns recent security events (suspicious activity, night movement) from SQLite database."""
    return JSONResponse(content=db_manager.get_recent_security_events(event_type=event_type, camera_id=camera_id, limit=limit))


@app.get("/api/suspicious_alerts")
async def get_suspicious_alerts(camera_id: Optional[str] = None):
    """Returns recent suspicious activity / loitering alerts."""
    if camera_id:
        reader = camera_manager.get_reader(camera_id)
        if reader:
            return JSONResponse(content=reader.get_suspicious_alerts())
        return JSONResponse(content=[])

    all_suspicious = []
    for r in camera_manager.get_all_readers().values():
        all_suspicious.extend(r.get_suspicious_alerts())
    all_suspicious.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    return JSONResponse(content=all_suspicious)


@app.get("/api/night_status")
async def get_night_status(camera_id: Optional[str] = None):
    """Returns current night mode status and brightness for a specific camera or primary camera."""
    reader = camera_manager.get_reader(camera_id)
    if reader:
        return JSONResponse(content=reader.get_night_status())
    return JSONResponse(content={"is_night_mode": False, "brightness": 0.0})


@app.get("/api/face_stats")
async def get_face_stats(camera_id: Optional[str] = None):
    """Returns face detection statistics."""
    reader = camera_manager.get_reader(camera_id)
    if reader:
        return JSONResponse(content=reader.get_face_stats())
    return JSONResponse(content={"face_count": 0, "face_detection_enabled": True})


@app.get("/api/events/all")
async def get_all_events(limit: int = 50, offset: int = 0, camera_id: Optional[str] = None):
    """Paginated historical events from SQLite database."""
    return JSONResponse(content=db_manager.get_all_events(limit=limit, offset=offset, camera_id=camera_id))


@app.get("/api/sync_status")
async def get_sync_status():
    """Returns offline-first sync engine metrics and pending status."""
    return JSONResponse(content=db_manager.get_sync_status())


# ─── Dynamic Webcam Control Endpoints ───

@app.get("/api/webcams/available")
async def get_available_webcams():
    """Probes system for connected webcams."""
    return JSONResponse(content=camera_manager.enumerate_webcams())


@app.get("/api/webcam/start")
@app.post("/api/webcam/start")
async def start_webcam(device_index: int = 0):
    """Starts USB / integrated webcam as CAM-WEBCAM."""
    res = camera_manager.enable_webcam(device_index=device_index)
    return JSONResponse(content=res)


@app.get("/api/webcam/stop")
@app.post("/api/webcam/stop")
async def stop_webcam():
    """Stops CAM-WEBCAM."""
    res = camera_manager.disable_webcam()
    return JSONResponse(content=res)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import uvicorn
    PORT = int(os.getenv("PORT", 8001))
    
    primary = camera_manager.get_reader("CAM-01")
    device_name = primary.device.upper() if primary else "CUDA"
    gpu_status = "CUDA GPU Accelerated" if device_name == "CUDA" else "CPU (Fallback)"
    
    print("\n" + "=" * 70)
    print(" PRAHARI-AI Multi-Camera Intelligent Surveillance Server")
    print("=" * 70)
    print(f" AI Inference Device:  {device_name} ({gpu_status})")
    print(f" Configured Cameras:   {len(camera_manager.configs)} streams registered")
    print(f" Web Interface:        http://localhost:{PORT}")
    print(f" Multi-Feed Grid:      http://localhost:{PORT}/")
    print(f" Video Feed (CAM-01):  http://localhost:{PORT}/video_feed/CAM-01")
    print(f" Video Feed (CAM-02):  http://localhost:{PORT}/video_feed/CAM-02")
    print(f" Video Feed (CAM-03):  http://localhost:{PORT}/video_feed/CAM-03")
    print(f" Video Feed (CAM-04):  http://localhost:{PORT}/video_feed/CAM-04")
    print("=" * 70 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
