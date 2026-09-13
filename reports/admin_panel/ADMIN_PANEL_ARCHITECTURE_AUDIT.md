# PRAHARI-AI — Admin Panel Architecture Audit (Phase 1)

## 1. Executive Overview
This document represents the read-only architectural audit of the PRAHARI-AI surveillance system prior to designing and implementing the **Admin Panel**. The objective is to identify existing patterns, modules, database structures, and frontend layouts to ensure seamless, non-destructive integration without impacting the verified four-camera AI surveillance pipeline.

---

## 2. Backend Architecture

### 2.1 Entry Point & Lifecycle
- **Entry Point**: `main.py`
- **Application Instance**: `FastAPI(title="PRAHARI-AI Multi-Camera Intelligent Surveillance Platform", lifespan=lifespan)`
- **Lifecycle Management**: `@asynccontextmanager async def lifespan(app: FastAPI)`
  - Startup: Calls `camera_manager.start_all()` which initializes background reader threads for all configured feeds.
  - Shutdown: Calls `camera_manager.stop_all()` to cleanly join background threads and stop ThreadPoolExecutors.

### 2.2 Existing Endpoints & Routing
All routes are currently registered directly on the `app` instance in `main.py` without separate APIRouters:
- **Static Mounts**:
  - `/alerts` -> `static/alerts`
  - `/anpr` -> `static/anpr`
  - `/anpr_debug` -> `static/anpr_debug`
  - `/assets` -> `frontend/dist/assets`
- **Core Operations**:
  - `GET /`: Serves `frontend/dist/index.html` (or fallback build instructions).
  - `GET /video_feed`: MJPEG stream (defaults to CAM-01).
  - `GET /video_feed/{camera_id}`: Dedicated MJPEG stream for specific camera.
- **Telemetry & Camera Management**:
  - `GET /api/cameras`: Configured & active cameras list with real-time status.
  - `GET /api/status`: Aggregate telemetry + primary camera metrics.
  - `GET /api/status/{camera_id}`: Status for a specific camera (defaults to CAM-01 fallback if not found).
  - `GET /api/dashboard_stats`: Combined aggregate, per-camera, night mode, face telemetry.
  - `GET /api/analytics`: Calculated historical stats from SQLite DB.
- **Event APIs**:
  - `GET /api/alerts`: Recent intrusion alerts.
  - `GET /api/anpr_log`: Recent ANPR license plate reads.
  - `GET /api/anpr_debug`: Candidate debug crops.
  - `GET /api/security_events`: Security events (suspicious activity, night movement).
  - `GET /api/suspicious_alerts`: In-memory recent suspicious activity alerts.
  - `GET /api/night_status`: Night mode status and luminance for camera.
  - `GET /api/face_stats`: Face detection counts and status.
  - `GET /api/events/all`: Paginated combined events from database.
  - `GET /api/sync_status`: Offline sync engine metrics.
- **Webcam Control**:
  - `GET /api/webcams/available`
  - `POST /api/webcam/start`
  - `POST /api/webcam/stop`

### 2.3 Existing Middleware
- Currently **zero custom middleware** is configured (no CORS middleware, no auth middleware, no session middleware).

---

## 3. Database Layer (`database.py`)

### 3.1 Connection & Lifecycle
- **Database Engine**: SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`).
- **Path Resolution**: `os.getenv("PRAHARI_DB_PATH", os.path.join(os.path.dirname(__file__), "prahari_events.db"))`.
- **Concurrency**: Thread-safe with `threading.Lock()` across connection transactions, `check_same_thread=False`, and `row_factory = sqlite3.Row`.
- **Global Singleton**: `db_manager = DatabaseManager()`.

### 3.2 Existing Tables
1. **`intrusion_events`**:
   - Columns: `id` (PK), `timestamp`, `camera_id`, `object_type`, `object_id`, `direction`, `plate_text`, `plate_confidence`, `anpr_status`, `validation_status`, `snapshot_path`, `synced`.
   - Indexes: `idx_intrusion_ts`, `idx_intrusion_cam`, `idx_intrusion_synced`.
2. **`anpr_events`**:
   - Columns: `id` (PK), `timestamp`, `camera_id`, `object_type`, `object_id`, `plate_text`, `confidence`, `validation_status`, `snapshot_path`, `synced`.
   - Indexes: `idx_anpr_ts`, `idx_anpr_cam`, `idx_anpr_synced`.
3. **`system_events`**:
   - Columns: `id` (PK), `timestamp`, `event_type`, `details`.
4. **`security_events`**:
   - Columns: `id` (PK), `timestamp`, `camera_id`, `event_type`, `object_type`, `object_id`, `confidence`, `validation_status`, `snapshot_path`, `details`, `synced`.
   - Indexes: `idx_security_ts`, `idx_security_cam`, `idx_security_type`, `idx_security_synced`.

---

## 4. Existing Security State

An exhaustive audit of the entire codebase confirms:
- **Authentication**: **NONE**. There is currently no login endpoint, token issuer, session cookie, or credential verification.
- **Password Hashing**: **NONE** in application code (however, `bcrypt 5.0.0` and Python standard `hashlib` are installed in the Python runtime).
- **JWT**: **NONE** in application code (however, `pyjwt 2.12.1` is installed in the runtime).
- **User Model**: **NONE**. No `users` table, no user schemas, no account management.
- **Authorization / RBAC**: **NONE**. All existing APIs are completely public and unauthenticated.
- **Role Handling**: **NONE**.

---

## 5. Frontend Architecture (`frontend/`)

### 5.1 Dependencies & Tools
- **Build Tool**: Vite 6.1.0 / 6.4.3 (`npm run build` outputs to `frontend/dist/`).
- **Libraries**:
  - `react` 18.3.1
  - `react-dom` 18.3.1
  - `lucide-react` 0.475.0 (modern clean icon set)
  - No CSS frameworks (Tailwind is absent; pure CSS variables and custom utility classes).
  - No `react-router-dom` is installed.

### 5.2 Application Layout & Component Tree
- **Entry**: `frontend/src/main.jsx` mounts `<App />` into `#root`.
- **Top-Level**: `frontend/src/App.jsx`:
  - Uses custom hook `usePolling` for telemetry (1000ms), events feed (1500ms), and analytics (5000ms).
  - Maintains state for modal dialogs: `FocusModal` (camera expanded view), `AnalyticsDrawer`, `Lightbox` (snapshot preview).
- **Components**:
  - `Header.jsx`: Branding, system clock, webcam toggle, Analytics Drawer toggle button.
  - `SystemStatus.jsx`: Header KPI chips (Aggregate FPS, GPU status, active cameras, people/vehicle counters).
  - `CameraGrid.jsx` & `CameraCard.jsx`: 2x2 multi-feed grid rendering `/video_feed/{camera_id}` with live overlay badges.
  - `ActivityFeed.jsx`: Right-hand sidebar with tabbed live feeds ('all', 'intrusions', 'anpr', 'suspicious').
  - `AnalyticsDrawer.jsx`: Slide-out analytics panel with camera breakdown and event trends.
  - `Lightbox.jsx`: Snapshot inspection overlay.
- **Styling System**:
  - `frontend/src/styles/globals.css` defines a unified military/command-center design system using CSS variables:
    - Base: `--bg-base: #F4F1EC`, `--bg-card: #FFFFFF`, `--border-subtle: #E3DED7`, `--text-main: #20242B`.
    - Accents: `--accent-teal: #16B8C9`, `--accent-blue: #2563EB`, `--status-live: #2FAE7B`, `--status-warn: #E9A23B`, `--status-danger: #D95757`, `--status-night: #7C5CFC`.

---

## 6. Camera & AI Pipeline Architecture

- **Camera Manager**: `camera_manager.py` manages `DEFAULT_CAMERAS`:
  - `CAM-01`: Border Post Alpha (`demo_videos/border_demo.mp4`, ratio: 0.70)
  - `CAM-02`: Night Surveillance Bravo (`demo_videos/night_demo.mp4`, ratio: 0.65)
  - `CAM-03`: Perimeter Activity Charlie (`demo_videos/activity-demo.mp4`, ratio: 0.60)
  - `CAM-04`: Urban Facility Delta (`demo_videos/cctv_demo.mp4`, ratio: 0.70)
- **Shared Model Registry**: `rtsp_stream.py` defines `ModelRegistry` singleton:
  - Shared `YOLOv8n` on CUDA (`weights/yolov8n.pt`)
  - Shared `ANPREngine` with local fine-tuned YOLOv11n plate detector (`weights/license-plate-finetune-v1n.pt`) + EasyOCR
  - Shared YuNet Face Detector (`weights/face_detection_yunet_2023mar.onnx`)
- **Isolation Principle**:
  - The entire camera ingestion, YOLO inference, centroid tracking, virtual fence calculation, and ANPR extraction runs in background daemon threads (`_frame_grabber_loop`, `_ai_processing_loop`, `_anpr_worker_loop`).
  - **The AI pipeline MUST NOT be modified or coupled with synchronous administrative tasks.**

---

## 7. Architectural Requirements for Admin Panel

1. **Backend Integration**:
   - Modularize admin code into a dedicated package `admin/` (or routers: `auth_router.py`, `admin_router.py`) to avoid cluttering `main.py`.
   - Mount under `/api/auth/*` and `/api/admin/*`.
   - Implement JWT-based bearer authentication using installed `pyjwt` and password verification with `bcrypt`.
   - Implement RBAC dependency: `require_role(["SUPER_ADMIN", "ADMIN", ...])`.
2. **Database Schema Additions**:
   - Safely extend `database.py` with tables:
     - `admin_users`: id, username, password_hash, full_name, role, is_active, created_at, last_login.
     - `admin_zones`: id, zone_name, camera_id, zone_type, severity, is_enabled, created_at, updated_at.
     - `admin_alert_rules`: id, event_type, severity, cooldown_seconds, is_enabled, description, updated_at.
     - `admin_incidents`: id, event_id, event_type, camera_id, zone_id, severity, status, assigned_to_user_id, evidence_snapshot, notes, created_at, updated_at, resolved_at.
     - `admin_audit_logs`: id, timestamp, actor_user_id, actor_username, role, action, resource_type, resource_id, result, description.
3. **Frontend Integration**:
   - Because `react-router-dom` is not currently in `package.json`, lightweight view state routing (`view: 'dashboard' | 'admin' | 'login'`) or standard path navigation can be implemented cleanly, preserving 100% of the existing Dashboard UI.
   - Admin UI components should share `globals.css` design tokens (`--bg-base`, `--bg-card`, `--accent-teal`, etc.) for seamless visual cohesion.
   - Add a subtle, professional navigation link in the `<Header />` (`[Operations Dashboard] [Admin Panel]`).

---

*Audit completed: 2026-09-13. Ready for Implementation Plan.*
