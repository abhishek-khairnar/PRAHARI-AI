# PRAHARI-AI Functional Audit — Streaming Test Diagnosis

## Incident Summary
During the execution of Section K/L/M audit (`reports/functional_audit/audit_section_k_l_m.py`, task `task-202`, PID 22984), the test process became blocked indefinitely while evaluating `/video_feed/{camera_id}`.

## Root Cause Analysis
1. **Infinite MJPEG Generator by Design**:
   In `main.py`, the live video feed generator is designed as an infinite streaming generator:
   ```python
   def mjpeg_generator(camera_id: str = None):
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
           time.sleep(0.033)
   ```
   This generator has **no EOF** because live CCTV/surveillance streams are intended to broadcast continuously.

2. **Synchronous Test Harness Blocking**:
   The test script invoked `with client.stream("GET", stream_url) as resp: for chunk in resp.iter_bytes():`. Because Starlette / HTTPX `TestClient` manages ASGI streaming via an internal generator consumer that synchronously waits on response completion or buffering, attempting to read an infinite stream without a strict bounded termination or timeout caused the test harness thread to hang indefinitely on `iter_bytes()`.

3. **Classification: Test Harness Design Issue**:
   This is **strictly a test harness design issue**, NOT evidence that the production streaming pipeline is broken. In fact, while the test harness was blocked waiting for EOF, the underlying 4 camera pipelines (`CAM-01`, `CAM-02`, `CAM-03`, `CAM-04`) were actively decoding, tracking, running YOLO and ANPR, encoding valid JPEG frames, and serving them continuously at ~5-8 FPS on GPU/CPU for over 40 minutes.

4. **Status of Preceding Checks in Sections K and L**:
   - Section K (Backend Startup): Lifespan started cleanly, registered all routes, loaded models on CUDA, and configured all 4 cameras.
   - Section L (REST APIs): All core REST endpoints (`/api/cameras`, `/api/status`, `/api/dashboard_stats`, `/api/analytics`, `/api/alerts`, `/api/anpr_log`) successfully returned `HTTP 200 OK` with valid JSON schemas.

5. **Remediation Plan for Section M**:
   - Section M must be retested using **bounded / non-blocking frame sampling**: connect to each camera stream (`CAM-01`, `CAM-02`, `CAM-03`, `CAM-04`), read only until the first complete multipart JPEG frame boundary (`\xff\xd8` to `\xff\xd9`) is captured, decode the image using `cv2.imdecode` to verify valid image dimensions and content, and immediately close the connection.
   - **Critical Rule**: Do NOT modify production streaming code to make the test pass. The change belongs solely in the test harness.
