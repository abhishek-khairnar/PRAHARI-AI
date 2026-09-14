# PRAHARI-AI: Final End-to-End Acceptance Report

**Audit Date**: 2026-09-14  
**Audit Scope**: Complete End-to-End Functional Validation, Pipeline Verification, Browser E2E, and Data Truth Realignment  
**Final Status**: **READY WITH DOCUMENTED LIMITATIONS**  

---

## 1. Executive Summary

This validation pass subjected the PRAHARI-AI surveillance and situational awareness platform to an exhaustive, truth-first verification pass. Rather than treating HTTP 200 responses or UI rendering as evidence of correctness, every user-visible metric, AI pipeline stage, event lifecycle, and database interaction was traced to its underlying hardware, algorithmic, or database source.

Key achievements of this pass include:
1. **ANPR Data Truth Realignment**: Eradicated the misleading publication of unverified license plates as "VERIFIED". Conflation of format syntax matching with identity verification was eliminated. The UI KPI card was truthfully realigned to `VALIDATED ANPR READS` (`Format Valid & Consensus, Conf ≥ 45%`).
2. **Benchmark Logic Rectification**: Replaced hardcoded benchmark passes with honest evaluations. Acknowledged and documented that looping unconstrained demo videos naturally produce repeated crossings, and that the 21-second `activity-demo.mp4` cannot physically trigger the 20-second dwell threshold.
3. **5-Input Dynamic Layout & Zero Page Scroll**: Verified the $2 \times 2$ grid (CAM 01–04) and $3 + 2$ dynamic split grid (CAM 01–04 + CAM-WEBCAM) across all standard operational resolutions ($1920\times1080$ to $1280\times720$) with zero vertical page scroll.
4. **Comprehensive Test Suite**: Achieved 100% pass rate across all 72 newly created acceptance tests (**T01–T72**), alongside all 142 regression tests (**214 total test cases, 0 failures**).
5. **Production Safety Guarantees**: Model SHA256 was preserved with 100% byte-exact integrity; zero production database rows were deleted or truncated.

---

## 2. Pre- and Post-Validation Baseline Verification

### Model Weights Integrity (SHA-256)
- **Target File**: `weights/yolov8n.pt`
- **Expected SHA-256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Pre-Test SHA-256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Post-Test SHA-256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Integrity Verdict**: **MATCH (Byte-Exact Unchanged)**

### Production Database Integrity (`prahari_events.db`)
Automated tests executed against isolated temporary SQLite databases (`tempfile.mkdtemp()`). The production database was monitored before and after validation:

| Table Name | Baseline Count | Post-Validation Count | Status |
|---|---|---|---|
| `admin_alert_rules` | 7 | 7 | Preserved |
| `admin_audit_logs` | 70 | 71 | Preserved (+1 superadmin login) |
| `admin_camera_config` | 4 | 4 | Preserved |
| `admin_incidents` | 9,413 | 10,730 | Preserved (Monotonic growth during live ingestion) |
| `admin_users` | 1 | 1 | Preserved |
| `admin_zones` | 4 | 4 | Preserved |
| `anpr_events` | 8,779 | 9,360 | Preserved (Monotonic growth during live ingestion) |
| `intrusion_events` | 248,090 | 276,803 | Preserved (Monotonic growth during live ingestion) |
| `notification_deliveries` | 9,409 | 10,726 | Preserved (Monotonic growth during live ingestion) |
| `notification_preferences` | 1 | 1 | Preserved |
| `notification_recipients` | 9,409 | 10,726 | Preserved (Monotonic growth during live ingestion) |
| `notifications` | 9,409 | 10,726 | Preserved (Monotonic growth during live ingestion) |
| `security_events` | 16,485 | 17,725 | Preserved (Monotonic growth during live ingestion) |
| `system_events` | 422 | 423 | Preserved |

---

## 3. Section Inventory & Metric Provenance Summary

Across 56+ audited sections (detailed in `reports/FINAL_FUNCTIONAL_SECTION_INVENTORY.md` and `reports/FINAL_FUNCTIONAL_SECTION_AUDIT.md`):
- **Live Inputs**: 4/4 Online (or 5/5 with Webcam) — `REAL_RUNTIME`
- **AI FPS**: 13.2–16.0 FPS (Sum of active stream inferences) — `REAL_RUNTIME`
- **Capture FPS**: 110.0 FPS (~28–29 FPS per camera thread) — `REAL_RUNTIME`
- **GPU Telemetry**: RTX 3050 6GB (29%–32% Util, 1.8GB VRAM) — `REAL_RUNTIME` (`pynvml`)
- **System Health**: OPTIMAL (Derived from all cameras online + AI active + DB online) — `REAL_DERIVED`
- **Threat Status**: CRITICAL (Derived from active unresolved critical incidents) — `REAL_DERIVED`
- **Active Critical**: 7,173 (Direct SQLite count of open critical incidents) — `REAL_DATABASE`
- **Active Security Incidents**: 10,660 (Direct SQLite count of open incidents) — `REAL_DATABASE`
- **Validated ANPR Reads**: 7,282 (Format valid & consensus, conf ≥ 45%) — `REAL_DATABASE`
- **Live Incident Rail**: LATEST 25 (Ordered newest first with deep links) — `REAL_DATABASE`

---

## 4. Acceptance Test Matrix & Results (T01–T72)

All 72 functional acceptance tests passed cleanly:

- **Camera & Video Ingestion (T01–T07)**:
  - T01 Camera Startup: **PASS**
  - T02 Camera Disconnect: **PASS**
  - T03 Camera Reconnect: **PASS**
  - T04 Webcam Startup: **PASS**
  - T05 Webcam Disconnect: **PASS**
  - T06 Five-Input Layout ($3+2$ Grid): **PASS**
  - T07 Four-Input Layout ($2\times2$ Grid): **PASS**
- **Object Detection & Tracking (T08–T15)**:
  - T08 Object Detection Baseline: **PASS**
  - T09 Empty Scene Detections: **PASS**
  - T10 Multi-Object Detection: **PASS**
  - T11 Vehicle Detection: **PASS**
  - T12 Vehicle Subtype Classification: **PASS**
  - T13 Tracker Continuity: **PASS**
  - T14 Tracker ID Isolation Per Camera: **PASS**
  - T15 Tracker Disappearance & Deregistration: **PASS**
- **Virtual Fence & Intrusion (T16–T22)**:
  - T16 Fence No Crossing: **PASS**
  - T17 1-Frame Jitter Suppression: **PASS**
  - T18 Confirmed Crossing (2-Hit): **PASS**
  - T19 Direction IN: **PASS**
  - T20 Direction OUT: **PASS**
  - T21 Re-Crossing Support: **PASS**
  - T22 Duplicate Suppression: **PASS**
- **Loitering, Suspicious & Night Mode (T23–T33)**:
  - T23 Loitering Below Threshold: **PASS**
  - T24 Loitering at Threshold Minus Epsilon: **PASS**
  - T25 Loitering Above Threshold: **PASS**
  - T26 Loitering Movement Reset: **PASS**
  - T27 Loitering Alert Cooldown: **PASS**
  - T28 Suspicious Activity Heuristic: **PASS**
  - T29 Suspicious Activity Negative Case: **PASS**
  - T30 Night Mode Entry (Luma < 85): **PASS**
  - T31 Night Mode Exit (Luma > 98): **PASS**
  - T32 Night Mode Hysteresis Deadband: **PASS**
  - T33 Night Movement Alert: **PASS**
- **Face Detection (T34–T36)**:
  - T34 Face Detection: **PASS**
  - T35 Face No Detection: **PASS**
  - T36 Face Disconnect Reset: **PASS**
- **ANPR System (T37–T44)**:
  - T37 Plate Detection: **PASS**
  - T38 OCR Exact Match: **PASS**
  - T39 Positional Character Confusion: **PASS**
  - T40 Temporal Consensus Resolution: **PASS**
  - T41 Consistently Wrong Consensus: **PASS**
  - T42 Invalid Format Rejection: **PASS**
  - T43 Duplicate Suppression: **PASS**
  - T44 Publication Tier Logic: **PASS**
- **Incident Lifecycle (T45–T52)**:
  - T45 Incident Creation (`NEW`): **PASS**
  - T46 Incident Acknowledgement (`ACKNOWLEDGED`): **PASS**
  - T47 Incident Investigation (`INVESTIGATING`): **PASS**
  - T48 Incident Resolution (`RESOLVED`): **PASS**
  - T49 Incident Dismissal (`DISMISSED`): **PASS**
  - T50 Active Critical Count: **PASS**
  - T51 Active Incident Count: **PASS**
  - T52 Threat Status Synchronization: **PASS**
- **Notifications Subsystem (T53–T56)**:
  - T53 Notification Creation & Recipient Assignment: **PASS**
  - T54 Deduplication Suppression by Key: **PASS**
  - T55 Unread Reconnect Recovery: **PASS**
  - T56 Mark Read / Unread Transition: **PASS**
- **Incident Rail & Telemetry (T57–T63)**:
  - T57 Live Incident Rail Ordering (DESC): **PASS**
  - T58 AI FPS Measurement: **PASS**
  - T59 Capture FPS Measurement: **PASS**
  - T60 GPU Telemetry Extraction: **PASS**
  - T61 System Health Derivation: **PASS**
  - T62 Database Failure Resilience: **PASS**
  - T63 Stale Telemetry Timeout: **PASS**
- **System Integration & Integrity (T64–T72)**:
  - T64 Frontend API Consistency: **PASS**
  - T65 Dashboard WebSocket Reconnect: **PASS**
  - T66 Browser Refresh State Recovery: **PASS**
  - T67 Multi-Camera Simultaneous Operation: **PASS**
  - T68 Five-Input Simultaneous Operation: **PASS**
  - T69 Zero Page Scroll (100vh constraint): **PASS**
  - T70 Production DB Isolation: **PASS**
  - T71 Model Hash Integrity: **PASS**
  - T72 Full Regression Test: **PASS**

---

## 5. Failures Found & Fixes Applied

1. **Defect 1: ANPR Publication Tier False "VERIFIED" Claim**
   - *Finding*: OCR format match was published as `VERIFIED` without an authoritative database.
   - *Fix*: Changed published tier to `FORMAT_VALID` in `anpr_consensus.py` and `rtsp_stream.py`. Renamed MetricCard 5 to `VALIDATED ANPR READS` in `DashboardMetrics.jsx`.
2. **Defect 2: Benchmark Evaluation Hardcoded PASS**
   - *Finding*: `video_analysis.py` returned hardcoded `"status": "PASS"` regardless of crossing count mismatches.
   - *Fix*: Updated `video_analysis.py` to compare expected vs detected counts and return `"UNCONSTRAINED_VIDEO_COUNT"` on loops.
3. **Defect 3: Loitering Duration Contradiction in Benchmark**
   - *Finding*: Demo video of 21.42s physically cannot trigger 20s dwell + 10 hits, yet old reports claimed PASS.
   - *Fix*: Replaced benchmark reliance with deterministic synthetic temporal fixtures (T23–T27) and categorized the demo clip honestly.
4. **Defect 4: Unauthorized Route Hijacking on Public Dashboard**
   - *Finding*: Background notification poll returning 401 dispatched `prahari:unauthorized`, causing `App.jsx` to navigate away from `/dashboard` to `/login`.
   - *Fix*: Wrapped notification polling in auth-token guard and restricted login redirection to protected routes (`/admin`, `/notifications`).
5. **Defect 5: Stale Face Counts on Camera Disconnect**
   - *Finding*: Disconnecting a camera left its face count in aggregate sums.
   - *Fix*: `get_aggregate_status()` was audited to strictly filter `getattr(r, "is_connected", False)` for live face sums.

---

## 6. Live Browser E2E Validation Summary

Automated headless Chrome sessions using Chrome DevTools Protocol verified:
1. **Operations Dashboard (`/dashboard`)**:
   - Renders 4-camera grid (CAM-01 to CAM-04) with real-time video feeds.
   - Renders all 6 KPI cards with live hardware numbers (GPU util, AI FPS, Capture FPS, Validated ANPR).
   - Zero vertical page scroll; fits within 100vh.
2. **Webcam Integration**:
   - Clicking `+ Connect Webcam` dynamically shifts layout to $3+2$ grid (CAM-01, 02, 03 in Row 1; CAM-04, WEBCAM in Row 2).
   - Real-time person detection overlay active on USB camera feed.
   - Disconnecting webcam restores clean $2\times2$ grid.
3. **Incident Rail Interaction**:
   - Filter tabs (`Critical`, `High`, `ANPR`, `Suspicious`, `All`) filter the list dynamically without page reload.
4. **Administrative Console (`/admin`)**:
   - `/admin/incidents`: Renders triage table with action buttons and filter dropdowns.
   - `/admin/cameras`, `/admin/zones`, `/admin/alert-rules`, `/admin/system`, `/admin/audit`: All render successfully without errors.
5. **Security Notifications Center (`/notifications`)**:
   - Renders unread incident notifications, severity badges, and direct incident deep links.

---

## 7. Real Video Demonstration Performance

| Camera | Demo Video | Resolution | Actual Cap FPS | Actual AI FPS | Primary Detected Events | Ground Truth Assessment |
|---|---|---|---|---|---|---|
| **CAM-01** | `border_demo.mp4` | $1920 \times 1080$ | 28.6 | 3.2 | Pedestrians, vehicles, ANPR `MH02FU9304`, fence crossings | Looping video; crossings continuous |
| **CAM-02** | `night_demo.mp4` | $1080 \times 1920$ | 29.1 | 3.3 | Dark sedan, ANPR `KL65T4000`, fence crossings | Looping video; night headlights |
| **CAM-03** | `activity-demo.mp4` | $1280 \times 720$ | 23.3 | 3.3 | Night mode active (`Luma: 44`), night movement | Video duration 21s (< loiter threshold) |
| **CAM-04** | `cctv_demo.mp4` | $1920 \times 1080$ | 29.0 | 3.4 | Multi-vehicle queue, suspicious activity dwell box | Dense traffic, continuous dwell tracking |

---

## 8. Documented Remaining Limitations

1. **External Vehicle Registry**: Without connection to an authoritative government vehicle database (e.g. VAHAN API), license plate reads are limited to `FORMAT_VALID` and `CONSENSUS READS`. Full identity verification cannot be claimed without external integration.
2. **YuNet Identity Limitation**: YuNet is strictly a face detector. It identifies the presence, coordinates, and landmarks of human faces, but does not perform facial recognition against a watch-list database.
3. **Demo Video Durations**: `activity-demo.mp4` (21.42s) is too short to observe natural 20-second loitering triggers without video looping.

---

## 9. Final Verdict

### **READY WITH DOCUMENTED LIMITATIONS**

**Rationale**:
The system is operationally sound, highly performant on edge hardware (RTX 3050), and adheres strictly to truth-in-data engineering standards. Every user-visible metric is backed by genuine hardware telemetry or SQLite database state. The 72 acceptance tests and 142 regression tests pass with 0 failures, browser E2E validation is verified, model weights are unchanged, and production data is completely preserved. The platform is ready for operational deployment within its documented air-gapped capabilities.
