# PRAHARI-AI — Final Dashboard Correction, 5-Input Webcam Layout & Complete Real-Time Data Truth Report

**Report Date**: 2026-09-14  
**Project**: PRAHARI-AI Multi-Camera Intelligent Defense Platform  
**Status**: READY FOR DEPLOYMENT  

---

## Executive Summary
This document provides the definitive verification of the PRAHARI-AI command center dashboard layout correction and complete real-time data-truth provenance audit. All requirements specified in the project mandate were fulfilled without modifying AI model weights, retraining, resetting the database, altering notification architectures, or touching external streaming infrastructure (`mediamtx/`, `ffmpeg/`, `test.mp4`).

---

## 1. Webcam Layout Implementation
When the USB/integrated webcam is enabled by the operator, the workspace transitions from the default 4-source grid into a balanced 5-source command center layout. All original 4 camera streams (`CAM-01`, `CAM-02`, `CAM-03`, `CAM-04`) remain continuously visible with zero card collapsing or layout breaking. The right-hand Live Incidents rail remains aligned outside the camera workspace.

```
┌───────────────────────────────────────────────────┬─────────────┐
│ CAM-01          CAM-02          CAM-03            │             │
│ (span 2, r1)    (span 2, r1)    (span 2, r1)      │             │
├───────────────────────────────────────────────────┤ INCIDENTS   │
│ CAM-04                    CAM-WEBCAM              │ (340px)     │
│ (span 3, r2)              (span 3, r2)            │             │
└───────────────────────────────────────────────────┴─────────────┘
```

---

## 2. 4-Camera Behavior (Webcam OFF)
When the webcam is disconnected or turned off:
- The camera workspace uses a 2×2 deterministic grid:
  `grid-template-columns: repeat(2, minmax(0, 1fr));`
  `grid-template-rows: repeat(2, minmax(0, 1fr));`
- `CAM-01` and `CAM-02` occupy Row 1; `CAM-03` and `CAM-04` occupy Row 2.
- The `CAM-WEBCAM` card is cleanly removed from the DOM.
- No blank placeholder remains, no layout collapse occurs, and no page-level scrollbars are triggered.

---

## 3. 5-Input Behavior (Webcam ON)
When the webcam is connected:
- The camera workspace uses a 6-column logical grid:
  `grid-template-columns: repeat(6, minmax(0, 1fr));`
  `grid-template-rows: repeat(2, minmax(0, 1fr));`
- Balanced column distribution:
  - Row 1: $2 + 2 + 2 = 6$ columns (`CAM-01`, `CAM-02`, `CAM-03` each span 2).
  - Row 2: $3 + 3 = 6$ columns (`CAM-04` and `CAM-WEBCAM` each span 3).
- All 5 feeds maintain synchronized live video streaming, AI telemetry bars, focus buttons, and fullscreen toggles.

---

## 4. Exact Files Changed
1. `d:\PRAHARI-AI\frontend\src\styles\dashboard.css`
   - Added `.cc-camera-grid.has-webcam` 6-column grid with deterministic placement spans.
   - Enforced `min-width: 0`, `min-height: 0` on camera grid and cards.
2. `d:\PRAHARI-AI\frontend\src\components\dashboard\CameraGrid.jsx`
   - Added dynamic `has-webcam` class on `.cc-camera-grid`.
3. `d:\PRAHARI-AI\frontend\src\components\dashboard\CameraCard.jsx`
   - Added deterministic camera placement class `cc-cam-card-${cameraId.toLowerCase()}`.
   - Fixed face count to 0 when disconnected.
   - Labeled ambient luminance clearly as `🌙 NIGHT (Luma: ${brightness})`.
4. `d:\PRAHARI-AI\frontend\src\components\dashboard\Dashboard.jsx`
   - Replaced synthetic heuristics with authoritative backend contract data (`active_critical_incidents`, `active_security_incidents`, `threat_level`, `system_health`).
5. `d:\PRAHARI-AI\frontend\src\components\dashboard\DashboardMetrics.jsx`
   - Updated operational KPI cards (`LIVE INPUTS`, `ACTIVE CRITICAL`, `ACTIVE SECURITY INCIDENTS`, `VERIFIED ANPR READS` subtext: `OCR Confirmed (Confidence ≥ 45%)`, `SYSTEM HEALTH`).
6. `d:\PRAHARI-AI\frontend\src\components\dashboard\SystemTelemetry.jsx`
   - Display real hardware GPU compute utilization or fallback `N/A`, and authoritative `threatLevel`.
7. `d:\PRAHARI-AI\frontend\src\components\dashboard\DashboardHeader.jsx`
   - Passed authoritative `threatLevel` down to `SystemTelemetry`.
8. `d:\PRAHARI-AI\frontend\src\components\dashboard\LiveIncidents.jsx`
   - Labeled header event pill as `LATEST {filteredEvents.length}`.
9. `d:\PRAHARI-AI\database.py`
   - Added active severity breakdown to `count_admin_incidents_summary()`.
   - Added `get_verified_anpr_count()` and `is_healthy()`.
10. `d:\PRAHARI-AI\camera_manager.py`
    - Integrated real GPU hardware telemetry via `pynvml` (`rates.gpu`, `mem.used/mem.total`), active unresolved incident summary, verified ANPR reads, deterministic threat level, and system health.
11. `d:\PRAHARI-AI\rtsp_stream.py`
    - Reset `face_count`, `people_count`, `vehicle_count`, `total_objects` to 0 on disconnect.
12. `d:\PRAHARI-AI\main.py`
    - Included unified telemetry payload in `/api/dashboard_stats`.
13. `d:\PRAHARI-AI\tests\test_notification_comprehensive_suite.py`
    - Restored `orig_db_path` in `tearDownClass`.
14. `d:\PRAHARI-AI\tests\test_dashboard_metric_audit.py`
    - Automated test suite covering all 22 required audit scenarios.

---

## 5. Exact CSS Grid Strategy
```css
.cc-camera-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  height: 100%;
  min-height: 0;
  flex: 1 1 auto;
}

.cc-camera-grid.has-webcam {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  height: 100%;
  min-height: 0;
  flex: 1 1 auto;
}

.cc-camera-grid.has-webcam .cc-cam-card-cam-01 { grid-column: span 2; grid-row: 1; }
.cc-camera-grid.has-webcam .cc-cam-card-cam-02 { grid-column: span 2; grid-row: 1; }
.cc-camera-grid.has-webcam .cc-cam-card-cam-03 { grid-column: span 2; grid-row: 1; }
.cc-camera-grid.has-webcam .cc-cam-card-cam-04 { grid-column: span 3; grid-row: 2; }
.cc-camera-grid.has-webcam .cc-cam-card-cam-webcam { grid-column: span 3; grid-row: 2; }
```

---

## 6–11. Metric Provenance Matrix & Sources
Documented in complete detail in [`reports/DASHBOARD_METRIC_PROVENANCE_AUDIT.md`](file:///d:/PRAHARI-AI/reports/DASHBOARD_METRIC_PROVENANCE_AUDIT.md).
All 21 metrics classified strictly as `REAL_RUNTIME`, `REAL_DATABASE`, `REAL_DERIVED`, or `STATIC_CONFIGURATION`.

---

## 12–13. Fake / Demo Values Discovered and Removed
1. **Synthetic Active Critical Count**:
   - Discovered: `Dashboard.jsx` was calculating `threatScore >= 20 ? Math.max(1, Math.round(threatScore / 20)) : 0`.
   - Action: Completely removed. Replaced with actual SQLite query:
     `SELECT COUNT(*) FROM admin_incidents WHERE severity = 'CRITICAL' AND status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')`.
2. **Ambiguous Incident Rail Pill**:
   - Discovered: Displayed `25 EVENTS` which was merely the client query limit (`limit=25`).
   - Action: Changed to `LATEST {filteredEvents.length}`.
3. **Unexplained Night Number**:
   - Discovered: Displayed `🌙 NIGHT (106)` or `(56)` without explanation.
   - Action: Identified as average grayscale luminance ($0-255$) and labeled as `🌙 NIGHT (Luma: 106)`.
4. **Static Threat Status**:
   - Discovered: `agg.threat_score` was omitted by the backend, causing threat status to always default to `NORMAL`.
   - Action: Derived deterministically in backend from open incident severities.
5. **GPU Percentage**:
   - Discovered: Only process-local allocated PyTorch memory was queried.
   - Action: Integrated `pynvml` to provide real hardware GPU compute utilization.

---

## 14. Active Incident Calculation
```python
cursor.execute("SELECT COUNT(*) FROM admin_incidents WHERE status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')")
open_count = cursor.fetchone()[0]
```
Incidents in `RESOLVED` and `DISMISSED` statuses are strictly excluded.

---

## 15. Threat Status Calculation
```python
if active_critical > 0:
    threat_level = "CRITICAL"
elif active_high > 0:
    threat_level = "HIGH"
elif active_medium > 0:
    threat_level = "ELEVATED"
else:
    threat_level = "NORMAL"
```

---

## 16. AI FPS Calculation
Measured in `RTSPStreamReader._ai_processing_loop` over rolling `fps_log_interval = 4.0s`:
$$\text{AI FPS} = \frac{\text{completed inference frames}}{\text{elapsed time}}$$
Aggregated across all active readers in `camera_manager.get_aggregate_status()`.

---

## 17. Capture FPS Calculation
Measured in `RTSPStreamReader._frame_grabber_loop` over rolling $3.0\text{s}$ interval:
$$\text{Capture FPS} = \frac{\text{grabbed frames}}{\text{elapsed time}}$$

---

## 18. ANPR Calculation
$$\text{Verified Reads} = \text{COUNT}(\text{anpr\_events where } (\text{confidence} \ge 0.45 \lor \text{validation\_status} = \text{'VERIFIED'}) \land \text{plate\_text} \notin \{\text{''}, \text{'N/A'}, \text{'PLATE NOT READ'}\})$$

---

## 19. Face Count Calculation
Real-time detected face bounding boxes produced by YuNet ONNX detector on current video frames.
When a camera is disconnected or offline, its face count is automatically reset to 0.

---

## 20. GPU Calculation
Queried directly from hardware via `pynvml.nvmlDeviceGetUtilizationRates(handle).gpu`.
Returns integer utilization percentage $[0-100\%]$ or `N/A` if telemetry is unavailable.

---

## 21. System Health Calculation
- `OPTIMAL`: Database online, all cameras connected, AI FPS $> 0$.
- `DEGRADED`: Database online, but $\ge 1$ camera offline or AI FPS $= 0$.
- `OFFLINE`: Database offline or 0 cameras connected.

---

## 22–24. Real-Time Update Mechanism & Staleness
- Operational Telemetry Polling: $1000\text{ms}$ bounded interval.
- Events Feed Polling: $1500\text{ms}$ bounded interval.
- Server Timestamp: Telemetry includes `server_timestamp` for client staleness detection ($>5\text{s}$ indicates stale).
- Notifications & Incident Alerting: Real-time single WebSocket connection (`/ws/notifications`).

---

## 25–26. E2E Verification Results
- 4 Cameras Default (2×2): Verified CAM-01..CAM-04 visible, zero scroll.
- Webcam Enabled (3+2): Verified CAM-01..CAM-03 top, CAM-04 + CAM-WEBCAM bottom, all 5 active.
- Webcam Disconnected: Reverted cleanly to 2×2 without page reload.
- Viewport Responsiveness: Tested and confirmed across 1920×1080, 1600×900, 1440×900, 1366×768, 1280×720.

---

## 27–30. Automated Regression & Test Results
- P0 Regressions (`tests/test_p0_regressions.py`): 13/13 PASSED
- Comprehensive Notification Suite (`tests/test_notification_comprehensive_suite.py`): 10/10 PASSED
- Dashboard Metric Audit Suite (`tests/test_dashboard_metric_audit.py`): 22/22 PASSED
- Total Test Suite: 45/45 PASSED
- Frontend Build (`npm run build`): SUCCESS (0 errors, 1.53s)
- Browser Console Errors: 0

---

## 31. Model SHA256 Verification
- Expected Hash: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- Measured Hash: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- Status: **IDENTICAL (100% UNTOUCHED)**

---

## 32. Database Integrity
- Existing historical incident records ($9,036$) preserved.
- No database reset, no data wiped, no schema modifications.

---

## 33. Final Decision
**READY FOR PRODUCTION DEPLOYMENT**
