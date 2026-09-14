# PRAHARI-AI Notification System Architecture

## 1. Architectural Overview & Design Philosophy

The PRAHARI-AI Notification System is an **additive, decoupled, role-aware, persistent, and real-time security alerting subsystem**. It provides end-to-end event dissemination from camera edge ingestion to security command-center browser operators without compromising the throughput, latency, or stability of the core AI surveillance pipeline.

### Core Architecture Flow
```
+-----------------------------------------------------------------------------+
|                             SURVEILLANCE PIPELINE                           |
|                                                                             |
|  [RTSP/Video Stream] (CAM-01 .. CAM-04)                                     |
|           |                                                                 |
|           v                                                                 |
|  [YOLOv8 Detection & Tracking] (Person, Vehicle, ANPR, Loitering)           |
|           |                                                                 |
|           v                                                                 |
|  [Security Event Creation] (log_security_event / log_intrusion_event)       |
+-----------------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------------+
|                          INCIDENT EVALUATION ENGINE                         |
|                                                                             |
|  [Alert Rule Policy Check] (get_alert_rules: enabled, severity, cooldown)   |
|           |                                                                 |
|           v                                                                 |
|  [Incident Creation / Correlation] (create_or_update_incident)              |
|     - Generates/Updates Incident Code (e.g., INC-20260913-0001)             |
|     - Enforces Deduplication & Cooldown                                     |
+-----------------------------------------------------------------------------+
                                    |
                                    v (downstream trigger)
+-----------------------------------------------------------------------------+
|                         NOTIFICATION CORE SERVICE                           |
|                                                                             |
|  [NotificationService.notify_incident_event]                                |
|     1. Check Rule / Policy (Enabled status, severity mapping)               |
|     2. Deduplication Check (incident_id & cooldown window)                  |
|     3. Recipient Resolution (RBAC: SUPER_ADMIN, ADMIN, SUPERVISOR, OFFICER) |
|     4. Database Persistence (notifications & notification_recipients)       |
|     5. Audit Logging (Audit logs recorded for security compliance)          |
+-----------------------------------------------------------------------------+
                                    |
                                    v (async non-blocking dispatch)
+-----------------------------------------------------------------------------+
|                       REAL-TIME DISPATCH & WEBSOCKET                        |
|                                                                             |
|  [NotificationConnectionManager]                                            |
|     - Authenticated WebSocket Session Registry                              |
|     - User-scoped message dispatch (no global unauthenticated broadcast)    |
|     - Non-blocking async queue delivery (AI inference never waits on socket)|
|     - Heartbeat ping/pong & graceful disconnect handling                    |
+-----------------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------------+
|                      COMMAND CENTER FRONTEND OPERATORS                      |
|                                                                             |
|  [useNotificationSocket Hook]                                               |
|     - Auto-reconnect with exponential backoff                               |
|     - Missed notification sync upon reconnection (GET /api/notifications)   |
|     - Tab synchronization via localStorage / BroadcastChannel               |
|                                                                             |
|  [UI Indicators & Multi-Modal Alerts]                                       |
|     - Notification Bell & Live Micro-Dot Status                             |
|     - Unread Badge Count                                                    |
|     - Slide-out Command Center Drawer with Severity Filters                 |
|     - Actionable Real-Time Toasts (Critical/High) with direct navigation   |
|     - Synthesized Web Audio Alerts (Autoplay safe, no external MP3 dependency)
|     - Native Desktop Browser Notifications (User-permission opt-in)         |
|     - Full History Page (/notifications) with Pagination & Search           |
+-----------------------------------------------------------------------------+
```

---

## 2. Strict Downstream Isolation & AI Protection

A primary architectural guarantee of PRAHARI-AI is:
> **The AI surveillance pipeline must continue working independently of notification delivery.**

1. **Downstream Coupling Only:**
   - Notifications are **never** triggered directly from raw YOLO detection loops, tracking bboxes, or per-frame inferences.
   - A notification is created **only after** an incident is formally established or escalated in `admin_incidents` via the existing security rule engine.
2. **Asynchronous Non-Blocking Dispatch:**
   - Database writes for notifications use SQLite WAL mode with Python reentrant locking (`RLock`) to prevent contention with frame logging.
   - Real-time WebSocket broadcasting occurs via asynchronous tasks (`asyncio.create_task` or non-blocking coroutines). If a network client is slow or drops, AI video capture and model inference are completely unaffected.
3. **Graceful Multi-Layer Degradation:**
   - If WebSocket is down: Notifications remain persisted in the SQLite database and are recovered via REST polling upon reconnect.
   - If audio playback is blocked by browser policy: Silent failure without throwing exceptions.
   - If Web Push / VAPID is unconfigured: System operates in standard real-time WebSocket + REST mode without error.

---

## 3. Database Schema Design

The notification subsystem introduces 4 dedicated tables in `prahari_events.db`, respecting the existing schema conventions and indexes:

### 3.1 `notifications`
Stores canonical notification events downstream of security incidents.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `incident_id` (INTEGER, FOREIGN KEY -> admin_incidents.id)
- `source_event_id` (INTEGER, nullable)
- `camera_id` (TEXT NOT NULL)
- `notification_type` (TEXT NOT NULL, default 'INCIDENT')
- `severity` (TEXT NOT NULL: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
- `title` (TEXT NOT NULL)
- `message` (TEXT NOT NULL)
- `created_at` (TEXT NOT NULL, ISO-8601)
- `dedupe_key` (TEXT NOT NULL)
- `expires_at` (TEXT, nullable)

*Indexes:*
- `idx_notifications_created_at` (`created_at`)
- `idx_notifications_incident_id` (`incident_id`)
- `idx_notifications_severity` (`severity`)
- `idx_notifications_dedupe` (`dedupe_key`, `created_at`)

### 3.2 `notification_recipients`
Maintains per-user receipt and read status, ensuring multi-user isolation.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `notification_id` (INTEGER NOT NULL, FOREIGN KEY -> notifications.id)
- `user_id` (INTEGER NOT NULL, FOREIGN KEY -> admin_users.id)
- `read_at` (TEXT, nullable)

*Indexes:*
- `idx_notif_recipients_user_read` (`user_id`, `read_at`)
- `idx_notif_recipients_notification_id` (`notification_id`)

### 3.3 `notification_preferences`
Stores user-configurable notification channels and severity thresholds.
- `user_id` (INTEGER PRIMARY KEY, FOREIGN KEY -> admin_users.id)
- `critical_enabled` (BOOLEAN DEFAULT 1)
- `high_enabled` (BOOLEAN DEFAULT 1)
- `medium_enabled` (BOOLEAN DEFAULT 1)
- `low_enabled` (BOOLEAN DEFAULT 1)
- `sound_enabled` (BOOLEAN DEFAULT 1)
- `browser_enabled` (BOOLEAN DEFAULT 1)
- `web_push_enabled` (BOOLEAN DEFAULT 0)

### 3.4 `notification_deliveries`
Audits delivery channels (websocket, browser, webpush) and status.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `notification_id` (INTEGER NOT NULL, FOREIGN KEY -> notifications.id)
- `user_id` (INTEGER NOT NULL)
- `channel` (TEXT NOT NULL)
- `status` (TEXT NOT NULL: 'delivered', 'failed', 'pending')
- `created_at` (TEXT NOT NULL)
- `delivered_at` (TEXT, nullable)
- `failure_at` (TEXT, nullable)
- `error` (TEXT, nullable)

*Index:*
- `idx_notif_deliveries_lookup` (`notification_id`, `user_id`, `channel`)

---

## 4. Deduplication & Incident Correlation

Surveillance cameras produce continuous detections while an unauthorized object or person remains in a restricted zone. Emitting a notification for every frame would cause severe operator fatigue.

### Deduplication Strategy:
1. **Incident-Centric Keying:**
   The deterministic deduplication key is constructed as:
   `dedupe_key = f"INCIDENT:{incident_id}:{severity}"`
2. **Time-Window Enforced Guard:**
   When an incident is created or updated, `NotificationService` verifies whether a notification with the matching `dedupe_key` was created within the incident correlation window (e.g., 60 seconds).
3. **Escalation Exception:**
   If an existing incident escalates in severity (e.g., from `MEDIUM` loitering to `CRITICAL` perimeter breach), the change in severity produces a distinct deduplication key, ensuring critical escalations are never silenced.

---

## 5. Security & RBAC Routing

1. **Authentication Enforcement:**
   - REST endpoints require a valid JWT token via `admin/auth.py` (`get_current_active_user`).
   - WebSocket connections authenticate either via `Authorization: Bearer <token>` header or `?token=<jwt>` query parameter during the HTTP handshake before upgrading the socket.
2. **Server-Side Identity Trust:**
   - The user ID is strictly extracted from the validated server-side session/JWT payload.
   - Client-supplied `user_id` parameters are ignored to prevent unauthorized notification access.
3. **Role-Aware Audience Resolution:**
   - `CRITICAL` and `HIGH` severity notifications are routed to `SUPER_ADMIN`, `ADMIN`, `SUPERVISOR`, and `OFFICER`.
   - Administrative and system health notifications are restricted to `SUPER_ADMIN` and `ADMIN`.
   - Multi-tenant isolation guarantees that `GET /api/notifications` returns only rows joined through `notification_recipients` where `user_id = current_user.id`.

---

## 6. Frontend Command Center Architecture

The frontend integrates into the PRAHARI-AI Operations Dashboard and Admin Panel through modular React components and hooks:

1. **`useNotificationSocket` Hook:**
   - Establishes and manages authenticated WebSocket connection to `/api/notifications/ws`.
   - Automatically handles reconnects using exponential backoff (1s, 2s, 4s, ... max 30s).
   - Syncs state with REST API upon reconnection to capture notifications generated during network disconnects.
2. **Multi-Modal Alerting:**
   - **Visual:** Real-time toasts for `CRITICAL` and `HIGH` events with direct "Investigate Incident" deep links.
   - **Auditory:** `soundAlert.js` uses Web Audio API dual-tone synthesis (OscillatorNode) with no external MP3 dependencies, adhering strictly to browser autoplay policies by requiring user interaction before arming.
   - **System Desktop:** Native browser `Notification` API with explicit user opt-in control.
3. **Persistent History & Drawer:**
   - `NotificationBell` with live unread badge and status pulse indicator.
   - Slide-out `NotificationDrawer` with severity-filtered tabs and "Mark All as Read".
   - Dedicated `/notifications` history page supporting full pagination and severity filtering.
