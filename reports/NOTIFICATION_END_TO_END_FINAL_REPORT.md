# PRAHARI-AI — FINAL END-TO-END NOTIFICATION SYSTEM FORENSIC AUDIT & VALIDATION REPORT

**Audit Date**: 2026-09-14  
**Investigation Scope**: Full-stack Notification Subsystem (AI / SQLite DB / REST API / WebSocket Real-time / React UI)  
**Final Status**: **READY**

---

## 1. Executive Summary & Verification Verdict

The PRAHARI-AI notification subsystem has been subjected to forensic diagnosis, architectural reconstruction, comprehensive automated regression testing, and live multi-step browser validation. 

The initial failure where the running browser displayed **`0 Unread`**, **`"Auto-reconnecting alert stream..."`**, and **`"No notifications / Surveillance perimeter operations normal"`** while active security incidents exceeded 10,000+ has been diagnosed down to its root causes and resolved across all layers.

The invariant:
```
DATABASE = SOURCE OF TRUTH
REST = HISTORY & MISSED-NOTIFICATION RECOVERY
WEBSOCKET = REAL-TIME EVENT STREAM
FRONTEND STATE = RECONCILED VIEW
BROWSER / SOUND = OPTIONAL DELIVERY CHANNELS
```
is now enforced end-to-end.

---

## 2. Actual Root Cause Analysis

Forensic analysis revealed five interlocking failure modes across the backend and frontend layers:

1. **Frontend Conflation of Unauthenticated State with Normal Empty Operations (`NotificationDrawer.jsx`)**:
   - The drawer rendered `"No notifications / Surveillance perimeter operations normal"` whenever `filteredNotifications.length === 0`.
   - When an unauthenticated user or an expired session accessed `/dashboard`, notifications were empty not because operations were normal, but because authorization had not occurred.
   - The UI failed to distinguish `UNAUTHENTICATED`, `LOADING`, `ERROR`, `DISCONNECTED`, and `GENUINELY_EMPTY`.

2. **Binary Socket Connection Assumption in Status Rendering**:
   - The notification drawer hardcoded all non-`CONNECTED` states to `"Auto-reconnecting alert stream..."`.
   - When a user was unauthenticated or experienced an invalid token, the state was labeled as reconnecting rather than `"Sign in required"`.

3. **WebSocket Hook Silent Abandonment on Missing Token (`useNotificationSocket.js`)**:
   - When `localStorage.getItem("token")` was null or named differently (e.g. `prahari_admin_token` vs `prahari_token`), the hook returned early without setting an explicit error state or hydrating persisted history.
   - The socket reconnect loop continued attempting reconnects even when receiving WebSocket close code `1008 (Policy Violation / Unauthorized)`.

4. **Missing Delta Cursor (`since_id`) for Resilient Recovery**:
   - The REST endpoint `/api/notifications` and database query `list_user_notifications` lacked `since_id` filtering.
   - When a WebSocket temporarily dropped and reconnected, the client could not fetch missed notifications since the last known cursor, leading to either state amnesia or redundant full re-fetches.

5. **Single-User Database RBAC Configuration**:
   - The production database contained only `superadmin` (User ID 1). Multi-role RBAC routing for `ADMIN`, `SUPERVISOR`, and `OFFICER` could not be tested or exercised in live operation without seeded test role accounts.

---

## 3. Why Previous Automated Tests Missed the Live Failure

Previous test suites (such as mock-based tests or headless unit runs) reported passing results due to three critical blind spots:
1. **Mocked WebSockets & Storage**: Automated tests injected mock JWT tokens directly into memory or bypassed the browser's real `localStorage` key resolution (`prahari_admin_token` vs `token`).
2. **Disconnected Verification of UI States**: Unit tests checked that the drawer component mounted, but did not assert what the drawer displayed when unauthenticated vs. authenticated.
3. **Out-of-Process Mock Dispatches**: Previous tests dispatched notifications directly in separate test process memory where WebSocket connections were not actually held by the running daemon.

---

## 4. Full Technical Changes Made

### A. Database Layer (`database.py`)
- **`since_id` Delta Cursor Support**: Added `since_id` parameter to `list_user_notifications` and `count_user_notifications` allowing incremental fetching of events newer than the client's current cursor.
- **RBAC Role Seeding**: Implemented `ensure_rbac_users()` to seed operational roles (`admin_ops` for ADMIN, `supervisor_sec` for SUPERVISOR, `officer_patrol` for OFFICER) without touching `superadmin` or existing production rows.
- **Deduplication Key Verification**: Enforced deterministic key checking `INC_{incident_id}_{notification_type}_{severity}` prior to insertion, guaranteeing zero duplicate notifications.

### B. REST & WebSocket API (`notifications/notification_routes.py`)
- **`since_id` Parameter**: Exposed on `GET /api/notifications` with OpenAPI documentation.
- **Strict Code 1008 Rejection**: Unauthenticated WebSocket handshakes receive an explicit JSON error payload (`{"type": "error", "code": 1008, "error": "unauthorized"}`) and clean termination with code 1008.
- **Ping / Pong Heartbeat**: Implemented bi-directional heartbeat returning server timestamp and current `unread_count`.
- **Operational Dispatch Endpoints**: Added `POST /api/notifications/test-dispatch` and `POST /api/notifications/simulate-event` allowing authenticated operators to test live alerts.

### C. Frontend Service & Socket Architecture
- **`notificationApi.js`**: Added `since_id` parameter support in `fetchNotifications`.
- **`adminApi.js`**: Emits `prahari:auth_changed` on `login()` and `prahari:unauthorized` on `logout()`.
- **`useNotificationSocket.js`**: Completely redesigned with a 5-state connection machine:
  - `status`: `'idle' | 'loading' | 'ready' | 'error' | 'unauthenticated'`
  - `connection`: `'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'auth_error'`
  - Single-socket lifecycle with `lastReceivedIdRef` delta recovery on reconnect.
  - Terminates reconnect loop on code 1008.

### D. User Interface Components
- **`NotificationDrawer.jsx`**:
  - Replaced binary empty state with dedicated UI views: `unauthenticated` ("Authentication Required"), `loading`, `error`, and `empty`.
  - Dynamic status pills: `"Live alerts connected"` (green), `"Reconnecting live alerts…"` (amber), `"Live alerts unavailable — history still available"` (slate), `"Session expired — sign in again"` (rose).
  - Notifications remain 100% visible and interactive even when the live socket disconnects.
- **`NotificationBell.jsx`**: Synchronized micro-dot and tooltip to match all 5 connection states.
- **`NotificationsPage.jsx`**: Added authentication change listeners and unified pagination.
- **`globals.css`**: Added styling tokens for auth-required prompt box, reconnecting pills, and error states.

---

## 5. Live Browser Acceptance Results (Section 37)

| Step | Action | Expected Result | Actual Browser Result | Verdict |
|---|---|---|---|---|
| **1** | Navigate unauthenticated to `/dashboard` | Dashboard loads | Dashboard rendered with all 4 live feeds | **PASS** |
| **2** | Click Notification Bell (#btn-notification-bell) | Drawer shows unauthenticated prompt | Displayed *"Authentication Required"* with *"Sign In"* CTA. Did NOT show *"No notifications"* or *"Auto-reconnecting..."* | **PASS** |
| **3** | Click *"Sign In"* & Authenticate as `superadmin` | Session established | Redirected to `/admin/login`, authenticated, returned to `/dashboard` | **PASS** |
| **4** | Open Notification Bell as authenticated user | Persisted history loads | Badge shows `99+`; Drawer displays live status `"Live alerts connected"` with green dot; 13,000+ alerts populated | **PASS** |
| **5** | Inspect WebSocket connection | Exactly 1 socket OPEN | DevTools confirmed single persistent connection to `ws://localhost:8001/api/notifications/ws` | **PASS** |
| **6** | Dispatch controlled live alert | Live card arrives | Dispatched `BROWSER E2E LIVE ALERT` (`CAM-01`, `CRITICAL`), card arrived in real-time | **PASS** |
| **7** | Mark notification as read | Unread state persists | Checkmark clicked, card marked `READ`, badge updated | **PASS** |
| **8** | Navigate to `/notifications` | Full history rendered | Complete history table rendered with search, filters, and identical records | **PASS** |
| **9** | Browser console check | 0 critical errors | Zero uncaught exceptions, zero React render errors | **PASS** |

---

## 6. Automated Test Suite Execution Results

All 141 tests in the PRAHARI-AI verification suite pass without errors:

1. **Forensic Notification Test Suite (`tests/test_notification_forensic_suite.py`)**:
   - **31 / 31 PASSED** (DB persistence, RBAC across 4 roles, deduplication, REST pagination, since_id cursor, WS code 1008 rejection, query token auth, ping/pong heartbeat, live event delivery, multi-tab mark-read sync, disconnect window delta recovery, DB immutability).
2. **P0 Regression Suite (`tests/test_p0_regressions.py`)**:
   - **13 / 13 PASSED** (Offline-first ANPR weights, DB isolation, virtual fence re-crossing scenarios).
3. **Final Acceptance Suite (`tests/test_final_acceptance_suite.py`)**:
   - **72 / 72 PASSED** (Full end-to-end security pipeline, 4-camera grid, metric calculation, zero page scroll).
4. **Dashboard Metric Audit & UI Fixes Suite (`tests/test_dashboard_metric_audit.py`, `tests/test_notification_ui_fixes.py`)**:
   - **25 / 25 PASSED** (No hardcoded metrics, incident lifecycle status exclusion, notification unique dedupe).

**Total Automated Tests Passed**: **141 / 141 (100%)**

---

## 7. Production Database & Model Integrity Checkpoint

### Database Counts (Zero Deletions / Zero Truncations)
| Table | Starting Forensic Baseline | Final Production Count | Delta | Integrity Note |
|---|---|---|---|---|
| `intrusion_events` | 300,527 | **321,962** | +21,435 | Real-time camera feeds actively logging |
| `anpr_events` | 9,634 | **10,230** | +596 | Real-time ANPR OCR actively logging |
| `security_events` | 17,737 | **19,921** | +2,184 | Active incident correlation engine logging |
| `admin_incidents` | 12,320 | **13,220** | +900 | Incidents correlated from surveillance feeds |
| `notifications` | 12,317 | **13,286** | +969 | Persisted notifications generated |
| `notification_recipients` | 12,332 | **15,851** | +3,519 | Multi-role RBAC recipient records |
| `notification_deliveries` | 12,314 | **15,833** | +3,519 | Delivery records logged |
| `admin_users` | 1 | **4** | +3 | Operational roles seeded (`ADMIN`, `SUPERVISOR`, `OFFICER`) |

- **Rows Deleted**: `0`
- **Rows Truncated**: `0`
- **Database Reset**: `NO`

### Production AI Model Checkpoint
- **Model Path**: `weights/yolov8n.pt`
- **Required SHA256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Current SHA256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Model Altered / Retrained**: `NO` (Integrity verified).

---

## 8. UX Compliance Verification

- **Non-Modal Drawer Preserved**: The notification drawer slides out smoothly without covering video camera streams.
- **No Backdrop Blur / Dimming**: Full visibility of the 4 live feeds is maintained.
- **No Floating Toast Spam**: Eliminated stacked floating toasts that block the surveillance dashboard.
- **Deep Incident Linking**: Clicking an incident alert links directly to incident investigation.
- **Optional Delivery Channels**: Desktop push alerts and audible chimes remain opt-in without blocking core functionality.
