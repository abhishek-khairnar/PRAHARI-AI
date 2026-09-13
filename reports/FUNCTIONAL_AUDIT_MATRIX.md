# PRAHARI-AI — Complete Functional Audit Matrix

| ID  | Module      | Test                   | Result  | Evidence | Error |
| --- | ----------- | ---------------------- | ------- | -------- | ----- |
| T01 | Environment | Python/dependencies    | PASS    | `reports/functional_audit/environment.txt` (Python 3.11.9, Torch 2.5.1+cu121, CUDA RTX 3050, Node v22.14.0, all packages present) | None |
| T02 | Model       | YOLO loading           | PASS    | `reports/functional_audit/model_test.json` (SHA256 F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36 verified, CUDA & CPU inference successful) | None |
| T03 | Camera      | CAM-01                 | PASS    | `reports/functional_audit/camera_test.json` (1920x1080 @ 30fps, 401 frames, decoded cleanly) | None |
| T04 | Camera      | CAM-02                 | PASS    | `reports/functional_audit/camera_test.json` (720x1280 @ 30fps, 300 frames, decoded cleanly) | None |
| T05 | Camera      | CAM-03                 | PASS    | `reports/functional_audit/camera_test.json` (1920x1080 @ 24fps, 515 frames, decoded cleanly) | None |
| T06 | Camera      | CAM-04                 | PASS    | `reports/functional_audit/camera_test.json` (1280x720 @ 29.97fps, 271 frames, decoded cleanly) | None |
| T07 | Detection   | Person                 | PASS    | `reports/functional_audit/detection_test.json` (1419 detections, max conf 0.942 in CAM-01) | None |
| T08 | Detection   | Car                    | PASS    | `reports/functional_audit/detection_test.json` (1349 detections, max conf 0.958 in CAM-02) | None |
| T09 | Detection   | Motorcycle             | PASS    | `reports/functional_audit/detection_test.json` (425 detections, max conf 0.909 in CAM-04) | None |
| T10 | Detection   | Truck                  | PASS    | `reports/functional_audit/detection_test.json` (185 detections, max conf 0.807 in CAM-04) | None |
| T11 | Detection   | Bus                    | PASS    | `reports/functional_audit/detection_test.json` (136 detections, max conf 0.634 in CAM-01) | None |
| T12 | Tracking    | CentroidTracker        | PASS    | `reports/functional_audit/tracking_test.json` (Unit tests pass, 66 unique tracks across real video runs) | None |
| T13 | Tracking    | ID persistence         | PASS    | `reports/functional_audit/tracking_test.json` (Average track lifespan 87.36 frames, 65/66 tracks persisted >10 frames) | None |
| T14 | Intrusion   | Fence configuration    | PASS    | `reports/functional_audit/intrusion_test.json` (All 4 cameras configured with valid ratios: 0.70, 0.65, 0.60, 0.70) | None |
| T15 | Intrusion   | IN crossing            | PASS    | `reports/functional_audit/intrusion_test.json` (2-hit hysteresis confirmed crossing above -> below fence) | None |
| T16 | Intrusion   | OUT crossing           | PASS    | `reports/functional_audit/intrusion_test.json` (2-hit hysteresis confirmed crossing below -> above fence) | None |
| T17 | Loitering   | Detection              | PARTIAL | `reports/functional_audit/loitering_test.json` (Dwell calculation verified; demo videos lack >20s stationary dwell scenario) | Scenario ground truth unavailable in demo data |
| T18 | Night Mode  | Detection              | PASS    | `reports/functional_audit/night_mode_test.json` (CAM-01 avg 108.55 Day; CAM-02 avg 83.13 enters Night with 169 frames; hysteresis hold verified) | None |
| T19 | ANPR        | Plate detection        | PASS    | `reports/functional_audit/anpr_test.json` (YOLOv11n detected plates in CCTV vehicle crops, conf 0.481) | None |
| T20 | ANPR        | OCR                    | PASS    | `reports/functional_audit/anpr_test.json` (EasyOCR on CUDA, MH1ZAB1234 normalized to MH12AB1234, format verified, conf 0.95) | None |
| T21 | Database    | Connection             | PASS    | `reports/functional_audit/database_test.json` (SQLite WAL mode verified, all 4 required tables present) | None |
| T22 | Database    | Insert                 | PASS    | `reports/functional_audit/database_test.json` (Isolated test record insertion successful) | None |
| T23 | Database    | Read                   | PASS    | `reports/functional_audit/database_test.json` (Test record retrieved with full field match) | None |
| T24 | Database    | Event integrity        | PASS    | `reports/functional_audit/database_test.json` (Fields verified, test record safely cleaned up without altering production records) | None |
| T25 | Backend     | Startup                | PASS    | `reports/functional_audit/backend_test.json` (FastAPI loaded 30 routes, shared models on CUDA, 4 cameras initialized, clean shutdown) | None |
| T26 | API         | `/api/cameras`         | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 3.38ms latency, valid 4-camera schema) | None |
| T27 | API         | `/api/status`          | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 38.08ms latency, aggregate & primary telemetry) | None |
| T28 | API         | `/api/dashboard_stats` | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 31.62ms latency, aggregate stats, cameras, night mode, face) | None |
| T29 | API         | `/api/analytics`       | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 8.78ms latency, database summary schema) | None |
| T30 | API         | `/api/alerts`          | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 6.43ms latency, list of intrusion alert dicts) | None |
| T31 | API         | `/api/anpr_log`        | PASS    | `reports/functional_audit/api_test.json` (HTTP 200, 8.38ms latency, list of ANPR read dicts) | None |
| T32 | Frontend    | Build                  | PASS    | `reports/functional_audit/frontend_test.json` (Vite 6.4.3 built production bundle in 12.91s, 0 errors) | None |
| T33 | Frontend    | Startup                | PASS    | `reports/functional_audit/dashboard_test.json` (FastAPI serves `dist/index.html` at root with HTTP 200) | None |
| T34 | Dashboard   | Camera display         | PASS    | `reports/functional_audit/streaming_test.json` & `dashboard_test.json` (All 4 cameras rendered in grid, live feeds online) | None |
| T35 | Dashboard   | Detection overlay      | PASS    | `reports/functional_audit/streaming_test.json` (MJPEG frames stream with annotated bboxes, class labels, and fence lines) | None |
| T36 | Dashboard   | Alerts                 | PASS    | `reports/functional_audit/dashboard_test.json` & `alert_test.json` (ActivityFeed displays live intrusion snapshots and metadata) | None |
| T37 | Dashboard   | Analytics              | PASS    | `reports/functional_audit/dashboard_test.json` & `analytics_test.json` (AnalyticsDrawer displays events breakdown and camera charts) | None |
| T38 | Dashboard   | ANPR display           | PASS    | `reports/functional_audit/dashboard_test.json` (ActivityFeed ANPR tab renders plate strings, confidence, verification badges) | None |
| T39 | Integration | Camera → AI            | PASS    | `reports/functional_audit/integration_test.json` (4 concurrent video sources ingested into shared ModelRegistry) | None |
| T40 | Integration | AI → Tracking          | PASS    | `reports/functional_audit/integration_test.json` (Detections forwarded to CentroidTracker without dropped frames) | None |
| T41 | Integration | Tracking → Events      | PASS    | `reports/functional_audit/integration_test.json` (Fence crossing logic triggers intrusion & ANPR events) | None |
| T42 | Integration | Events → DB            | PASS    | `reports/functional_audit/integration_test.json` (ThreadPoolExecutor persists events to SQLite tables) | None |
| T43 | Integration | DB → API               | PASS    | `reports/functional_audit/integration_test.json` (APIs query SQLite and return matching event records) | None |
| T44 | Integration | API → Dashboard        | PASS    | `reports/functional_audit/dashboard_test.json` (Frontend polling services successfully receive JSON payloads) | None |
| T45 | Integration | Complete pipeline      | PASS    | `reports/functional_audit/integration_test.json` (338 frames processed across 4 streams in 10s benchmark, 0 pipeline crashes) | None |
