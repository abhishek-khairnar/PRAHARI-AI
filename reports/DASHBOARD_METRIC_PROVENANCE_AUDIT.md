# PRAHARI-AI — Complete Dashboard Metric Provenance & Data Truth Audit

**Audit Date**: 2026-09-14  
**Scope**: All metrics, counters, percentages, indicators, and statuses displayed on the Command Center Dashboard.  
**Classification System**:
- `REAL_RUNTIME`: Directly measured from currently running camera, AI inference, or system hardware telemetry.
- `REAL_DATABASE`: Read directly from actual persisted production database records.
- `REAL_DERIVED`: Calculated deterministically from real runtime/database values using a documented formula.
- `STATIC_CONFIGURATION`: Legitimate fixed configuration values (e.g. camera identifier, static hardware name).
- `FALLBACK`: Clean error fallback used exclusively when a live source is temporarily unreachable.
- `DEMO`: Synthetic/demo values (NONE permitted in production command center).
- `HARDCODED`: Literal numbers/values representing runtime state (NONE permitted in production command center).
- `UNKNOWN`: Unverifiable source (NONE permitted).

---

## 1. Metric Provenance Matrix

| Dashboard Metric | Component | API / Source | Backend Calculation | DB Table | Runtime Source | Update Method | Truth Status |
|---|---|---|---|---|---|---|---|
| **Live Inputs (Cameras)** | `DashboardMetrics.jsx`, `SystemTelemetry.jsx` | `/api/dashboard_stats` (`agg.active_cameras`, `agg.total_cameras`) | `total = len(all_r)`, `active = sum(1 for r in all_r.values() if r.is_connected)` | None | `camera_manager.get_all_readers()` | Polling (1000ms) | `REAL_RUNTIME` |
| **System AI Performance (FPS)** | `DashboardMetrics.jsx` | `/api/dashboard_stats` (`agg.aggregate_ai_fps`) | `sum(r.current_fps for r in all_r.values())`, where `r.current_fps = frames_since_log / elapsed` (over 4.0s window) | None | `RTSPStreamReader._ai_processing_loop` | Polling (1000ms) | `REAL_RUNTIME` |
| **Ingestion Capture FPS** | `DashboardMetrics.jsx`, `CameraTelemetry.jsx` | `/api/dashboard_stats` (`agg.aggregate_capture_fps`, `cam.capture_fps`) | `sum(r.capture_fps for r in all_r.values())`, where `r.capture_fps = grabbed / elapsed` (over 3.0s window) | None | `RTSPStreamReader._frame_grabber_loop` | Polling (1000ms) | `REAL_RUNTIME` |
| **Active Critical Incidents** | `DashboardMetrics.jsx` | `/api/dashboard_stats` (`agg.active_critical_incidents`) | `SELECT COUNT(*) FROM admin_incidents WHERE severity = 'CRITICAL' AND status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')` | `admin_incidents` | SQLite production database | Polling (1000ms) + WebSocket | `REAL_DATABASE` |
| **Active Security Incidents** | `DashboardMetrics.jsx` | `/api/dashboard_stats` (`agg.active_security_incidents`) | `SELECT COUNT(*) FROM admin_incidents WHERE status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')` | `admin_incidents` | SQLite production database | Polling (1000ms) + WebSocket | `REAL_DATABASE` |
| **Session Intrusions Count** | `DashboardMetrics.jsx` (Subtext) | `/api/dashboard_stats` (`agg.total_session_alerts`) | `sum(r.session_alerts_count for r in all_r.values())` | None | CentroidTracker / Virtual Fence cross count | Polling (1000ms) | `REAL_RUNTIME` |
| **Session Suspicious Count** | `DashboardMetrics.jsx` (Subtext) | `/api/dashboard_stats` (`agg.total_session_suspicious`) | `sum(r.session_suspicious_count for r in all_r.values())` | None | Loitering & Hysteresis Night Tracker | Polling (1000ms) | `REAL_RUNTIME` |
| **Verified ANPR Reads** | `DashboardMetrics.jsx` | `/api/dashboard_stats` (`agg.verified_anpr_reads`), `/api/analytics` | `SELECT COUNT(*) FROM anpr_events WHERE (confidence >= 0.45 OR validation_status = 'VERIFIED') AND plate_text NOT IN ('', 'N/A', 'PLATE NOT READ')` | `anpr_events` | SQLite production database | Polling (1000ms) | `REAL_DATABASE` |
| **System Health Status** | `DashboardMetrics.jsx` | `/api/dashboard_stats` (`agg.system_health`, `agg.system_health_desc`) | `OPTIMAL` if all cameras connected + AI FPS > 0 + DB online; `DEGRADED` if streams offline or AI stalled; `OFFLINE` if DB error or all cams down | None | Evaluated across DB connection + camera connections + AI throughput | Polling (1000ms) | `REAL_DERIVED` |
| **Total Live Faces** | `camera_manager.py` | `/api/dashboard_stats` (`agg.total_live_faces`) | `sum(r.face_count for r in all_r.values() if r.is_connected)` | None | YuNet ONNX Face Detector active frame bounding boxes | Polling (1000ms) | `REAL_RUNTIME` |
| **Per-Camera Live Faces** | `CameraCard.jsx` | `/api/dashboard_stats` (`cam.face_count`) | `r.face_count` if `r.is_connected` else `0` (YuNet detected bounding boxes on current frame) | None | YuNet ONNX detector on camera frame grab | Polling (1000ms) | `REAL_RUNTIME` |
| **Threat Status** | `SystemTelemetry.jsx` | `/api/dashboard_stats` (`agg.threat_level`) | `CRITICAL` if active critical > 0; `HIGH` if active high > 0; `ELEVATED` if active medium > 0; else `NORMAL` | `admin_incidents` | Derived directly from active unresolved incident severities | Polling (1000ms) | `REAL_DERIVED` |
| **Hardware GPU Name** | `SystemTelemetry.jsx` | `/api/dashboard_stats` (`agg.gpu.device_name`) | `pynvml.nvmlDeviceGetName()` or `torch.cuda.get_device_name()` | None | NVIDIA Driver / CUDA API | Polling (1000ms) | `REAL_RUNTIME` |
| **Hardware GPU Utilization** | `SystemTelemetry.jsx` | `/api/dashboard_stats` (`agg.gpu.gpu_util_pct`) | `pynvml.nvmlDeviceGetUtilizationRates(handle).gpu` | None | NVIDIA Management Library (NVML) | Polling (1000ms) | `REAL_RUNTIME` |
| **Hardware VRAM Usage** | `SystemTelemetry.jsx` | `/api/dashboard_stats` (`agg.gpu.vram_pct`) | `round((mem.used / mem.total) * 100.0, 1)` | None | NVML / CUDA Memory info | Polling (1000ms) | `REAL_RUNTIME` |
| **Incident Rail Header Pill** | `LiveIncidents.jsx` | `eventsFeed.length` | Count of latest fetched events returned by `/api/all_events?limit=25` | None | Event buffer slice | Polling (1500ms) | `REAL_RUNTIME` |
| **Camera Day/Night & Luma** | `CameraCard.jsx` | `/api/dashboard_stats` (`cam.is_night_mode`, `cam.brightness`) | `current_brightness = float(np.mean(gray))`; `is_night_mode` via dual-threshold hysteresis (Enter 85.0, Exit 98.0) | None | Grayscale pixel luminance mean (0-255) | Polling (1000ms) | `REAL_RUNTIME` |
| **Per-Camera AI FPS** | `CameraTelemetry.jsx` | `/api/dashboard_stats` (`cam.fps`) | `frames_since_log / elapsed` over 4.0s interval | None | Camera reader AI loop | Polling (1000ms) | `REAL_RUNTIME` |
| **Per-Camera Capture FPS** | `CameraTelemetry.jsx` | `/api/dashboard_stats` (`cam.capture_fps`) | `grabbed_counter / elapsed` over 3.0s interval | None | Camera reader grabber loop | Polling (1000ms) | `REAL_RUNTIME` |
| **Per-Camera Object Counts** | `CameraTelemetry.jsx` | `/api/dashboard_stats` (`cam.people_count`, `cam.vehicle_count`, `cam.total_objects`) | Bounding boxes tracked per frame by YOLOv8n + CentroidTracker; reset to 0 on disconnect | None | YOLOv8n object detection output | Polling (1000ms) | `REAL_RUNTIME` |
| **Camera Identification** | `CameraCard.jsx` | `DEFAULT_CAMERA_DEFS` | Fixed system registration identifier (e.g. `CAM-01`, `CAM-02`, `CAM-WEBCAM`) | None | Camera configuration registry | Static | `STATIC_CONFIGURATION` |
| **Camera Friendly Name** | `CameraCard.jsx` | `DEFAULT_CAMERA_DEFS` | Configured display name (e.g. `Border Post Alpha`, `Night Surveillance Bravo`, `Live Integrated/USB Webcam`) | None | Camera configuration registry | Static | `STATIC_CONFIGURATION` |

---

## 2. In-Depth Metric Audit Findings & Corrections

### A. Active Security Incidents (was showing 8,811)
- **Investigation**: In SQLite table `admin_incidents`, 9,036 incidents currently have unresolved statuses (`status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')`). During continuous past video processing, all intrusion and security events generated `admin_incidents` records in `NEW` status, and operators had not resolved them.
- **Truth Decision**:
  - The metric truthfully represents unresolved incidents in the database lifecycle.
  - Resolved (`RESOLVED`) and dismissed (`DISMISSED`) records are excluded by `status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')`.
  - The label `ACTIVE SECURITY INCIDENTS` accurately reflects this definition.

### B. Active Critical Incidents (was fake `threatScore / 20`)
- **Investigation**: Previously `Dashboard.jsx` computed `threatScore >= 20 ? Math.max(1, Math.round(threatScore / 20)) : 0`. Because `agg.threat_score` was omitted by the backend, `threatScore` was always 0, falsely displaying `ACTIVE CRITICAL: 0`.
- **Correction**: Replaced with authoritative database query:
  `SELECT COUNT(*) FROM admin_incidents WHERE severity = 'CRITICAL' AND status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')`.
  The dashboard now displays the exact real count of unresolved critical incidents directly from SQLite.

### C. Live Incidents Rail Pill (was "25 EVENTS")
- **Investigation**: The backend endpoint `/api/all_events` is called with `limit=25` to provide a fast operational window of the latest events. Displaying `25 EVENTS` created misleading ambiguity with the total incident count in the database.
- **Correction**: Changed label to `LATEST 25` (with descriptive tooltip `Displaying latest 25 events`), communicating clearly that this is the latest event window.

### D. Threat Status (was always "NORMAL")
- **Investigation**: `threat_score` was previously not returned in `camera_manager.get_aggregate_status()`, causing the frontend threat score to always default to 0 and display `NORMAL` despite active critical incidents.
- **Correction**: Implemented deterministic threat derivation in `camera_manager.py`:
  - Active unresolved `CRITICAL` incident $\rightarrow$ `THREAT: CRITICAL`
  - Active unresolved `HIGH` incident $\rightarrow$ `THREAT: HIGH`
  - Active unresolved `MEDIUM` incident $\rightarrow$ `THREAT: ELEVATED`
  - Zero active unresolved threats $\rightarrow$ `THREAT: NORMAL`

### E. Night Mode Ambient Luminance (was unexplained "NIGHT (106)")
- **Investigation**: Number 106 or 56 was the mean grayscale pixel luminance (`np.mean(gray)` from 0 to 255). An operator had no context for what the number signified.
- **Correction**: Changed label to `🌙 NIGHT (Luma: 106)` with descriptive tooltip `Ambient Luminance (Luma): 106 / 255`.

### F. GPU Utilization Telemetry (was hardcoded / VRAM only)
- **Investigation**: Previously only PyTorch process-local memory was queried, returning 0% utilization when inference was idle, and no compute utilization percentage was captured.
- **Correction**: Integrated `pynvml` to query real hardware GPU compute utilization percentage (`util.gpu`) and VRAM usage from the NVIDIA driver. When GPU telemetry is unavailable, it gracefully displays `Telemetry unavailable` or `CPU Fallback`, with zero fake values.

### G. Verified ANPR Reads
- **Investigation**: Subtext previously claimed `YOLOv11 + EasyOCR Engine`.
- **Correction**: Updated subtext to `OCR Confirmed (Confidence ≥ 45%)` to describe the actual verification criteria used by the query (`confidence >= 0.45 OR validation_status = 'VERIFIED'`).

### H. System Health Status
- **Investigation**: System health previously evaluated only camera count and FPS in a single React component without cross-subsystem verification.
- **Correction**: Derived deterministically across all subsystems:
  - Database connectivity (`db_manager.is_healthy()`)
  - All configured camera streams connected (`active_cameras == total_cameras`)
  - Active AI pipeline throughput (`aggregate_ai_fps > 0`)
  - Produces `OPTIMAL`, `DEGRADED`, or `OFFLINE`.

---

## 3. Data Flow & Single Source of Truth

```
[ Camera Pipelines (RTSP/Webcam) ]     [ SQLite DB (admin_incidents, anpr_events) ]     [ NVIDIA Driver (NVML) ]
                   \                                |                                     /
                    \                               |                                    /
                     \---> [ camera_manager.get_aggregate_status() ] <-----------------/
                                            |
                                            v
                                 [ /api/dashboard_stats ]
                                            |
                                            v
                                [ Dashboard.jsx (Single State) ]
                               /            |             \
                              v             v              v
                     [ DashboardHeader ] [ DashboardMetrics ] [ CameraGrid & Cards ]
```

Every displayed metric originates from this normalized contract without duplication or contradictory calculations.
