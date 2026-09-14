# PRAHARI-AI — Notification System Forensic Audit & Starting Report

**Timestamp**: 2026-09-14 13:13:00  
**Audit Phase**: Baseline Forensic Diagnosis & Failure Reproduction  
**Model SHA256**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` (`weights/yolov8n.pt` — 100% UNCHANGED)

---

## 1. Executive Summary & Observed Live Failure

The PRAHARI-AI notification subsystem exhibits a major data-flow and state representation failure on `http://localhost:8001/dashboard`. 

### The Live Inconsistency:
- **Operations Dashboard Metrics**:
  - `THREAT: CRITICAL`
  - `ACTIVE CRITICAL: 7,997+`
  - `ACTIVE SECURITY INCIDENTS: 11,883+` (Intrusions: 57,199+, Suspicious: 758)
  - `VALIDATED ANPR: 7,636`
- **Simultaneous Notification Center / Drawer State**:
  - `Security Notifications`
  - `0 Unread`
  - `● Auto-reconnecting alert stream...`
  - `All (0)` | `Unread (0)` | `Critical` | `High` | `Medium`
  - `No notifications`
  - `Surveillance perimeter operations normal`

### Reproduced Screenshot:
The failure was reproduced live in the active Chromium browser session.  
Screenshot artifact: `brain/212f4062-1601-4233-8644-446ffe4c3274/notification_drawer_open_1789370858478.png`

---

## 2. Forensic Identity & Live State (Section 2 Checklist A–T)

| Metric / Item | Live Diagnostic Value | Notes |
| :--- | :--- | :--- |
| **A. Current Logged-in User** | `superadmin` (when token present) / `null` (when unauthenticated visitor on `/dashboard`) | `/dashboard` is accessible without login, but notifications require auth |
| **B. User ID** | `1` (for `superadmin`) | Sole user in `admin_users` table |
| **C. User Role** | `SUPER_ADMIN` | Configured with full RBAC access |
| **D. JWT Authentication State** | Valid HS256 JWT when authenticated; `null` or expired when anonymous or unauthenticated | Tokens expire after 12h |
| **E. Notification REST API (With Auth)** | `HTTP 200 OK` (Total: 12,315 notifications, returns valid items) | Authoritative database is actively populated |
| **E. Notification REST API (Without Auth)**| `HTTP 401 Unauthorized` (`{"detail":"Authentication required. Please provide a valid Bearer token."}`) | Protected endpoint |
| **F. Notification Unread API** | `HTTP 200 OK` (`unread_count: 8306`, `active_incidents_count: 12318`) | Returns true server-side counts |
| **G. WebSocket URL** | `ws://localhost:8001/api/notifications/ws?token=<jwt>` | Auth via query param or initial JSON frame |
| **H. WebSocket Connection State (With Auth)** | `OPEN / CONNECTED` (receives `connection.ack`, responds to `ping`, streams `notification.created`) | Works when valid token is supplied |
| **H. WebSocket Connection State (No Auth)** | `REJECTED (Code 1008)` after error message `{"type":"error","error":"unauthorized"}` | Cleanly rejected by backend |
| **I. WebSocket Close Code** | `1008` (Policy Violation / Unauthorized) | Code returned on auth failure |
| **J. WebSocket Close Reason** | `"Authentication failed"` | Reason sent before closure |
| **K. WebSocket Auth Result** | Rejected on unauthenticated/expired; Accepted on valid JWT | Backend enforcement verified |
| **L. Browser Console Errors** | Empty on dashboard; silent failure because `try/catch` in `useNotificationSocket.js` swallows errors | Silent failure hides state from operator |
| **M. Network Errors** | `401 Unauthorized` when token absent or expired; WebSocket close `1008` | Expected backend behavior, improperly handled on frontend |
| **N. Notification DB Row Count** | `12,311` rows | In `prahari_events.db` |
| **O. Notification Recipients Row Count** | `12,311` rows | In `prahari_events.db` |
| **P. Notifications for Current User (id=1)** | `12,311` rows | All notifications mapped to `superadmin` |
| **Q. Unread Notifications for Current User**| `8,302` rows | Verified in `notification_recipients` (`is_read = 0`) |
| **R. Latest Notification Timestamp** | `2026-09-14 13:12:08` | Pipeline actively inserting new records in real time |
| **S. Latest Incident Timestamp** | `2026-09-14 13:12:08` | Correlation pipeline actively functioning |
| **T. Latest Recipient Timestamp** | `2026-09-14 13:12:08` | Recipient assignment actively functioning |

---

## 3. Database Forensic Audit (Section 3 Checklist 1–16)

1. **Total Notification Rows**: 12,311
2. **Total Recipient Rows**: 12,311
3. **Unread Recipient Rows**: 8,302
4. **Notifications by Severity**:
   - `CRITICAL`: 8,289
   - `HIGH`: 4,022
   - `MEDIUM`: 0
   - `LOW`: 0
5. **Created At Range**: `2026-09-13 15:13:33` to `2026-09-14 13:12:08`
6. **Incident IDs Range**: Mapped 1-to-1 with `admin_incidents` (`11331` through `12320+`)
7. **Dedupe Keys**: Valid format `INC_{incident_id}_{type}_{severity}` (0 duplicates)
8. **Recipient User ID Matching Current User (1)**: 12,311 (100%)
9. **Notifications for Other Users**: 0 (only `user_id = 1` exists in `admin_users`)
10. **Foreign Key Integrity**: 0 orphan recipients (all FKs point to valid `notifications.id`)
11. **Orphan Deliveries**: 0 orphan deliveries
12. **Duplicate Notification IDs**: None
13. **Duplicate Incident Notification Keys**: None
14. **Read/Unread Fields**: Properly indexed `is_read` INTEGER (0/1), `read_at` timestamp
15. **Timestamps**: Consistent ISO / SQLite format strings
16. **Transaction Visibility**: WAL mode active; rows immediately visible to API connections

---

## 4. Root Cause Analysis — Layer by Layer

### Root Cause A: Frontend Treats All Non-Connected States as "Auto-Reconnecting"
In `frontend/src/components/notifications/NotificationDrawer.jsx`:
```jsx
const isConnected = connectionStatus === 'connected';
...
<span>
  {isConnected ? 'Real-Time Delivery Active' : 'Auto-reconnecting alert stream...'}
</span>
```
If `connectionStatus` is `'disconnected'`, `'auth_error'`, or `'unauthenticated'`, the UI misleadingly claims it is `Auto-reconnecting alert stream...`.

### Root Cause B: Binary "Empty State" Masking Failure and Auth Requirements
In `NotificationDrawer.jsx`:
```jsx
{filteredNotifications.length === 0 ? (
  <div className="notif-empty-state">
    <AlertTriangle style={{ width: 32, height: 32, opacity: 0.4 }} />
    <p>No {filter !== 'all' ? filter : ''} notifications</p>
    <span>Surveillance perimeter operations normal</span>
  </div>
) : ( ... )
```
There are no distinct states for:
- `LOADING` (fetching REST notifications from DB)
- `ERROR` (REST fetch failed)
- `AUTH_REQUIRED / SESSION_EXPIRED` (user not logged in or token expired)
- `DISCONNECTED` (WebSocket down, but persisted REST notifications visible)
- `GENUINELY_EMPTY` (user is authenticated, query succeeded, and genuinely 0 alerts exist)

Whenever `notifications` is empty (such as during unauthenticated dashboard viewing, during token expiration, or before initial fetch), it falsely tells the user: `"Surveillance perimeter operations normal"` while critical incidents are raging!

### Root Cause C: Incomplete Hydration Lifecycle in `useNotificationSocket`
In `frontend/src/hooks/useNotificationSocket.js`:
```javascript
useEffect(() => {
  isMountedRef.current = true;
  const token = getAuthToken();

  if (!token) {
    setConnectionStatus('disconnected');
    return;
  }
  ...
```
When an operator visits `/dashboard` without an active session (or if `getAuthToken()` returns null):
1. `useNotificationSocket` sets `connectionStatus('disconnected')`.
2. It completely halts; `refreshNotifications()` is never called.
3. State remains `notifications: []`, `unreadCount: 0`.
4. Drawer defaults to "No notifications / Surveillance perimeter operations normal" + "Auto-reconnecting alert stream...".

### Root Cause D: Reconnection State Machine Deficiencies
1. When a WebSocket is rejected with 1008 (Unauthorized / token expired), `onclose` currently schedules another reconnect attempt, creating a futile reconnect loop instead of transitioning to `AUTH_ERROR`.
2. Reconnect state is not differentiated from disconnect state.
3. Missed notifications during a disconnection window are not reliably reconciled via cursor-based delta retrieval.

### Root Cause E: RBAC User Population & Multi-User Verification
Currently, only `superadmin` exists in `admin_users`. There are no records for `ADMIN`, `SUPERVISOR`, or `OFFICER`, so RBAC recipient isolation has only been tested in synthetic test mocks rather than the real database.

---

## 5. Proposed Architectural Resolution

1. **Explicit 6-State Machine in Frontend**:
   - `status`: `idle` | `loading` | `ready` | `error` | `auth_required`
   - `connection`: `connecting` | `connected` | `reconnecting` | `disconnected` | `auth_error`
2. **REST as Authoritative History Hydration**:
   - Always load persisted notifications via REST when authenticated.
   - If not authenticated, clearly render "Authentication Required — Sign In to View Notifications".
   - If REST fails, render "Unable to load notification history" with a Retry action.
   - Never show "Surveillance perimeter operations normal" unless the server genuinely returns 0 notifications for the user.
3. **Separation of Connection Status from Notification Data**:
   - WebSocket status badge clearly reflects `connected`, `reconnecting`, `disconnected`, or `auth_error`.
   - Disconnected WebSocket preserves all persisted notification items in the drawer and notification history page.
4. **Resilient Reconnection & Delta Reconciliation**:
   - Exponential backoff with jitter.
   - Halt reconnects on 1008 / `auth_error`.
   - On reconnect, fetch delta notifications since last known ID / timestamp and merge cleanly without duplicates.
5. **Single Authoritative Connection**:
   - Maintain exactly one active WebSocket instance.
   - Clean up on unmount, logout, or session expiry.
6. **Multi-User RBAC Testing**:
   - Seed/test `admin`, `supervisor`, `officer` accounts and verify strict notification recipient routing.
