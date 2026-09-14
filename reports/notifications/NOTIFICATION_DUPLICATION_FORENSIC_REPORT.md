# Forensic Notification Duplication Audit Report

**Date:** 2026-09-13  
**Auditor:** PRAHARI-AI Advanced Diagnostic Agent  
**Status:** Completed Forensic Audit (No code modified yet)

---

## Executive Summary

A comprehensive, forensic lifecycle audit was conducted across the backend database, notification dispatch pipeline, WebSocket delivery manager, and frontend React state/toast hierarchy to identify the root causes of notification duplication and stacked toast alerts (specifically cases such as `INC-1326` and `INC-1336`).

The forensic analysis reveals:
- **Database Duplication:** **NONE.** No duplicate records exist in `notifications` or `notification_recipients`. `INC-1326` has exactly 1 notification row (`id=1322`) and `INC-1336` has exactly 1 notification row (`id=1332`).
- **Unread Notification Count:** The count (1,364) is database-authentic, representing 1,364 legitimate unread security incidents created during multi-camera test sessions.
- **Duplication Root Causes Identified:**
  1. **React Re-render / Effect Re-triggering:** In `App.jsx`, `useNotificationSocket({ onOpenIncident: (incidentId) => { navigateTo('admin', 'incidents'); } })` is called with an **unmemoized inline function**. Because `App` re-renders every 1,000ms (telemetry polling) and 1,500ms (events polling), the `useEffect` in `useNotificationSocket` re-executes continuously.
  2. **Multiple Active WebSockets per User:** During rapid component re-renders, the previous WebSocket is marked for closing asynchronously (`ws.close()`), but remains in `ws_manager._user_connections` until TCP teardown. Up to `MAX_CONNECTIONS_PER_USER = 5` simultaneous sockets exist for the single user.
  3. **Multi-Socket Broadcast Multiplier:** When `ws_manager.send_to_user(uid, payload)` executes, it sends the notification to **all active sockets** belonging to that user.
  4. **Client-Side Toast Identity Absence:** `addToast` in `useNotificationSocket.js` generated a random ID (`toast-${Date.now()}-${Math.random()}`) rather than checking `notification.id`. When all open sockets received the message, each socket invoked `addToast`, creating 3–4 stacked toast cards for the exact same notification.
  5. **Lack of Backend Unique Constraint:** While no duplicate rows currently exist, `dedupe_key` on the `notifications` table has a non-unique index (`idx_notif_dedupe`), and `_create_and_dispatch_incident_notification_internal` does an unconditional `INSERT` without checking `dedupe_key`.

---

## 1. Database Duplication Analysis

### Summary Statistics
| Metric | Value |
|---|---|
| Total Notifications | 1,364 |
| Total Unread Recipient Rows | 1,364 |
| CRITICAL Notifications | 907 |
| HIGH Notifications | 457 |
| Duplicate `dedupe_key` Count | **0** |
| Duplicate `incident_id` in Notifications | **0** |

### Deep-Dive on Observed Live Incidents
- **Incident INC-1326:**
  - `id`: 1326 | `incident_code`: INC-1326 | `event_type`: suspicious_activity | `camera_id`: CAM-04 | `severity`: HIGH
  - `created_at`: 2026-09-13 16:40:54
  - Linked notifications in DB: **Exactly 1** (`id=1322`, `dedupe_key=INC_1326_INCIDENT_CREATED_HIGH`)
- **Incident INC-1336:**
  - `id`: 1336 | `incident_code`: INC-1336 | `event_type`: border_intrusion | `camera_id`: CAM-03 | `severity`: CRITICAL
  - `created_at`: 2026-09-13 16:41:13
  - Linked notifications in DB: **Exactly 1** (`id=1332`, `dedupe_key=INC_1336_INCIDENT_CREATED_CRITICAL`)

### Conclusion on DB
No database duplication occurred. The backend did not create duplicate rows for `INC-1326` or `INC-1336`. The duplication was created entirely in the transport/delivery and client rendering layers.

---

## 2. WebSocket Delivery Audit

In `notifications/notification_realtime.py`:
- `WebSocketManager` tracks `self._user_connections[user_id]` (a set of WebSockets).
- `MAX_CONNECTIONS_PER_USER` is configured to 5.
- When `send_to_user(user_id, payload)` is executed:
  ```python
  sockets = list(self._user_connections.get(user_id, []))
  for ws in sockets:
      await ws.send_text(json_data)
  ```
If a single browser tab has re-connected 3 times before prior TCP sockets fully drop, all 3 sockets receive the message frame.

---

## 3. React Listener & Effect Lifecycle Audit

In `frontend/src/App.jsx`:
```javascript
// Line 116
const notif = useNotificationSocket({
  onOpenIncident: (incidentId) => {  // <-- Inline function recreated on EVERY render
    navigateTo('admin', 'incidents');
  }
});
```
In `frontend/src/hooks/useNotificationSocket.js`:
```javascript
// Line 268
useEffect(() => {
  ...
  connectWs();
  ...
}, [refreshNotifications, addToast, onOpenIncident]); // <-- onOpenIncident changes every render!
```
Because `App.jsx` polls telemetry every 1000ms (`setDashboardData`), `App` re-renders every second.
On each render:
1. `onOpenIncident` is a newly allocated function.
2. `useNotificationSocket`'s `useEffect` triggers cleanup (`socket.close()`) and runs again (`new WebSocket()`).
3. During the asynchronous socket teardown/handshake, multiple concurrent sockets remain open in `ws_manager`.
4. Multiple `ws.onmessage` handlers receive the broadcast simultaneously.

---

## 4. Recovery Replay Semantics

When `refreshNotifications()` is called on connection/reconnect:
- It calls `GET /api/notifications` and `GET /api/notifications/unread-count`.
- It populates `setNotifications(listRes.items)` and `setUnreadCount(countRes.unread_count)`.
- It does **not** generate toasts directly from history.
- However, when a reconnect fires right after an incident, both the WebSocket broadcast and the initial synchronization run concurrently.

---

## 5. Toast Deduplication & Lifecycle Audit

In `frontend/src/hooks/useNotificationSocket.js`:
```javascript
const addToast = useCallback((notif) => {
  const sev = (notif.severity || 'HIGH').toUpperCase();
  if (sev === 'LOW' || sev === 'INFO') return;

  const toastId = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
  const newToast = {
    id: toastId,
    notification: notif,
    createdAt: Date.now()
  };

  setToasts((prev) => [newToast, ...prev.slice(0, 4)]);
  ...
}, [dismissToast]);
```
Vulnerabilities:
1. **No deduplication by `notification.id`**: Every time `addToast` is called, it assigns a random ID and pushes the toast into state.
2. **No recent-ID suppression**: If 3 socket connections deliver the same `notif.id = 1322` within 20ms of each other, 3 separate toasts are placed in `toasts`.
3. **No queue/collapse logic**: Duplicate alerts pile up to the max toast limit.

---

## 6. Root Cause Summary Matrix

| Defect Area | Identified Root Cause | Severity |
|---|---|---|
| **Frontend Socket Hook** | Unmemoized `onOpenIncident` prop in `App.jsx` triggers constant socket reconnects | **HIGH** |
| **Frontend Toast Logic** | `addToast` uses random IDs instead of deduplicating on `notification.id` with bounded recent cache | **CRITICAL** |
| **Backend WebSocket** | Broadcasts to all sockets of a user without connection deduplication/debouncing | **MEDIUM** |
| **Database Schema** | `notifications.dedupe_key` lacks a UNIQUE constraint/index and `_create_and_dispatch_incident_notification_internal` lacks dedupe check | **MEDIUM** |

---

## 7. Next Actions
Proceed with Phase 3 through Phase 8 to resolve backend idempotency, WebSocket lifecycle, hook memoization, and client-side bounded toast deduplication.
