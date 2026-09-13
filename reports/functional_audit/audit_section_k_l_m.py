import os
import sys
import time
import json
import tempfile
import asyncio
import cv2
import numpy as np

# ─── CRITICAL: Isolated Test Database Override BEFORE any imports ───
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, base_dir)

test_db_dir = tempfile.mkdtemp(prefix="prahari_audit_klm_")
test_db_path = os.path.join(test_db_dir, "test_klm_events.db")
os.environ["PRAHARI_DB_PATH"] = test_db_path

from fastapi.testclient import TestClient
from main import app, camera_manager, video_feed_by_camera
from rtsp_stream import model_registry

def run_audit_klm():
    # ─── SECTION K: Backend Startup Audit ───
    backend_report = {
        "database_isolated": True,
        "test_db_path": test_db_path,
        "fastapi_app_loaded": app is not None,
        "routes_registered_count": len(app.routes),
        "routes_registered": [r.path for r in app.routes],
        "models_initialized": False,
        "device": None,
        "camera_configs_loaded": 0,
        "cameras": {},
        "startup_exceptions": None,
        "shutdown_clean": False,
        "status": "FAIL"
    }

    try:
        camera_manager.start_all()
        # Allow cameras 3 seconds to spin up capture threads and process initial frames
        time.sleep(3.0)

        backend_report["models_initialized"] = (model_registry.yolo_model is not None)
        backend_report["device"] = model_registry.device
        backend_report["camera_configs_loaded"] = len(camera_manager.readers)
        for cid, reader in camera_manager.readers.items():
            backend_report["cameras"][cid] = {
                "name": reader.camera_name,
                "source": reader.rtsp_url,
                "source_type": reader.source_type,
                "is_connected": reader.is_connected,
                "status": reader.status,
                "frame_count": reader.frame_count
            }
        
        all_connected = all(r.is_connected for r in camera_manager.readers.values())
        backend_report["status"] = "PASS" if (backend_report["models_initialized"] and all_connected) else "PARTIAL"
    except Exception as e:
        backend_report["startup_exceptions"] = str(e)
        backend_report["status"] = "FAIL"

    # ─── SECTION L: REST API Audit ───
    api_report = {
        "endpoints": {},
        "error_handling": {},
        "overall_status": "PASS"
    }

    with TestClient(app) as client:
        endpoints_to_test = [
            {
                "url": "/api/cameras",
                "name": "Camera Registry API",
                "required_keys": ["id", "name", "status"]
            },
            {
                "url": "/api/status",
                "name": "System & Aggregate Status API",
                "required_keys": ["aggregate", "total_cameras", "active_cameras"]
            },
            {
                "url": "/api/dashboard_stats",
                "name": "Dashboard Aggregated Stats API",
                "required_keys": ["aggregate", "cameras", "suspicious_activity_count", "night_mode"]
            },
            {
                "url": "/api/analytics",
                "name": "Database Analytics API",
                "required_keys": ["total_detections", "total_intrusions", "hourly_distribution", "class_breakdown"]
            },
            {
                "url": "/api/alerts",
                "name": "Recent Intrusion Alerts API",
                "is_list": True
            },
            {
                "url": "/api/anpr_log",
                "name": "Recent ANPR Logs API",
                "is_list": True
            }
        ]

        for ep in endpoints_to_test:
            url = ep["url"]
            t0 = time.perf_counter()
            resp = client.get(url)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

            res = {
                "name": ep["name"],
                "url": url,
                "status_code": resp.status_code,
                "response_time_ms": elapsed_ms,
                "content_type": resp.headers.get("content-type", ""),
                "schema_valid": False,
                "sample_data": None
            }

            if resp.status_code == 200 and "application/json" in res["content_type"]:
                data = resp.json()
                if ep.get("is_list"):
                    res["schema_valid"] = isinstance(data, list)
                    res["sample_data"] = f"List containing {len(data)} items"
                elif "required_keys" in ep:
                    if isinstance(data, list) and len(data) > 0:
                        res["schema_valid"] = all(k in data[0] for k in ep["required_keys"])
                        res["sample_data"] = f"List of {len(data)} dicts; sample keys: {list(data[0].keys())[:5]}"
                    elif isinstance(data, dict):
                        res["schema_valid"] = all(k in data for k in ep["required_keys"])
                        res["sample_data"] = f"Dict with keys: {list(data.keys())[:6]}"
            api_report["endpoints"][url] = res

        # Error behavior: invalid camera ID
        t0 = time.perf_counter()
        resp_err = client.get("/api/status/INVALID_CAM_999")
        api_report["error_handling"]["/api/status/INVALID_CAM_999"] = {
            "status_code": resp_err.status_code,
            "response_time_ms": round((time.perf_counter() - t0) * 1000, 2),
            "expected_404": (resp_err.status_code == 404),
            "error_body": resp_err.json() if "application/json" in resp_err.headers.get("content-type", "") else resp_err.text
        }

    api_report["overall_status"] = "PASS" if all(ep["schema_valid"] for ep in api_report["endpoints"].values()) else "PARTIAL"

    # ─── SECTION M: Bounded Video Streaming Audit ───
    streaming_report = {
        "method": "Bounded Async Stream Sampling (single frame extraction & validation per camera)",
        "cameras": {},
        "overall_status": "PASS"
    }

    async def test_all_streams():
        for cid in ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]:
            t0 = time.perf_counter()
            s_res = {
                "camera_id": cid,
                "url": f"/video_feed/{cid}",
                "status_code": 200,
                "media_type": None,
                "frame_bytes_len": 0,
                "jpeg_delimiters_valid": False,
                "decoded_image_valid": False,
                "image_width": 0,
                "image_height": 0,
                "latency_ms": 0.0,
                "status": "FAIL"
            }
            try:
                resp = await video_feed_by_camera(cid)
                s_res["media_type"] = resp.media_type
                
                # Fetch first frame chunk from async generator body iterator
                first_chunk = await anext(resp.body_iterator)
                await resp.body_iterator.aclose()
                s_res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                s_res["frame_bytes_len"] = len(first_chunk)

                # Find JPEG SOI (\xff\xd8) and EOI (\xff\xd9)
                soi = first_chunk.find(b"\xff\xd8")
                eoi = first_chunk.find(b"\xff\xd9", soi + 2) if soi != -1 else -1
                if soi != -1 and eoi != -1:
                    jpeg_bytes = first_chunk[soi : eoi + 2]
                    s_res["jpeg_delimiters_valid"] = True

                    # Verify actual image decode
                    img = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if img is not None and img.size > 0:
                        s_res["decoded_image_valid"] = True
                        s_res["image_height"], s_res["image_width"] = img.shape[:2]
                        s_res["status"] = "PASS"
            except Exception as e:
                s_res["error"] = str(e)

            streaming_report["cameras"][cid] = s_res

    asyncio.run(test_all_streams())

    # Shutdown backend cleanly
    try:
        camera_manager.stop_all()
        backend_report["shutdown_clean"] = True
    except Exception as e:
        backend_report["shutdown_error"] = str(e)

    streaming_report["overall_status"] = "PASS" if all(c["status"] == "PASS" for c in streaming_report["cameras"].values()) else "PARTIAL"

    # Save test artifacts
    with open(os.path.join(os.path.dirname(__file__), "backend_test.json"), "w", encoding="utf-8") as f:
        json.dump(backend_report, f, indent=2)

    with open(os.path.join(os.path.dirname(__file__), "api_test.json"), "w", encoding="utf-8") as f:
        json.dump(api_report, f, indent=2)

    with open(os.path.join(os.path.dirname(__file__), "streaming_test.json"), "w", encoding="utf-8") as f:
        json.dump(streaming_report, f, indent=2)

    print("Sections K, L, M successfully audited and saved!")

if __name__ == "__main__":
    run_audit_klm()
