# PRAHARI-AI — Notification UX Redesign: Phase 0 Safe Checkpoint Report

- **Timestamp**: 2026-09-13T18:10:00+05:30
- **Git Branch**: `feature/real-working-notifications`
- **Current HEAD Commit**: `7c6676e` (`feat(admin): complete data-truth, live incident pipeline and camera telemetry hardening`)
- **Working Tree Cleanliness**: Core files clean; working feature branch with full tracking.

---

## 1. Production Model Checksums (SHA256)

| Model File | SHA256 Hash | Status |
| :--- | :--- | :--- |
| `weights/yolov8n.pt` | `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` | **LOCKED & VERIFIED** |
| `weights/license-plate-finetune-v1n.pt` | `0AEC75976C56EB6F26DFB274C430620EC65137915FF1AE47C3A48C7AF8AFB7B2` | **LOCKED & VERIFIED** |
| `yolo26n.pt` | `9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF` | **LOCKED & VERIFIED** |

*Production Safety Rule Verified: AI weights are strictly locked and untouched.*

---

## 2. Production Database Truth Counts (`prahari_events.db`)

| Table Name | Row Count | Integrity Note |
| :--- | :--- | :--- |
| `intrusion_events` | 118,718 | Production historical detections preserved |
| `anpr_events` | 6,091 | Production license plate events preserved |
| `security_events` | 10,192 | Production security telemetry preserved |
| `system_events` | 356 | System logs preserved |
| `admin_incidents` | 2,639 | Production security incidents preserved |
| `notifications` | 2,635 | Production notification records preserved |
| `notification_recipients` | 2,635 | Production recipient bindings preserved |
| `notification_deliveries` | 2,635 | Real-time dispatch records preserved |
| `admin_users` | 1 | Administrator account preserved |
| `admin_zones` | 4 | Zone configurations preserved |
| `admin_alert_rules` | 7 | Alert policies preserved |
| `admin_audit_logs` | 34 | Audit trail preserved |
| `admin_camera_config` | 4 | 4 camera definitions preserved |

---

## 3. Current Notification Table Forensic Counts

- **Total Notification Rows**: 2,635
- **Total Recipient Rows**: 2,635
- **Unread Count**: 2,635
- **Read Count**: 0
- **Unique Notification IDs**: 2,635 (100% unique)
- **Unique Incident IDs**: 2,635 (100% unique)
- **Incident Linkage**: 100% of notifications link directly to valid records in `admin_incidents` (`missing_incidents = 0`).
- **Duplicates by Dedupe Key**: 0
- **Duplicates by Incident ID**: 0
- **Breakdown by Severity**:
  - `CRITICAL`: 1,757 (66.7%)
  - `HIGH`: 878 (33.3%)
  - `MEDIUM`: 0
  - `LOW`: 0
- **Breakdown by Camera**:
  - `CAM-01`: 699
  - `CAM-02`: 756
  - `CAM-03`: 386
  - `CAM-04`: 794
- **Event Source Tables**:
  - `intrusion_events`: 1,757
  - `security_events`: 878
- **Time Range**: `2026-09-13 15:13:33` to `2026-09-13 17:56:29`
- **Data Classification**: **LEGITIMATE**. Every notification was created 1-to-1 from authentic live surveillance incidents generated during operations and verification sessions earlier today. Zero synthetic duplicates.

---

## 4. Frontend Build Baseline

Command: `npm --prefix frontend run build`
Result: **SUCCESS (Exit Code 0)**
- Modules transformed: 1,621
- Build time: 12.68s
- Assets generated:
  - `dist/index.html` (0.80 kB)
  - `dist/assets/index-vsR8qgLT.css` (51.10 kB)
  - `dist/assets/index-BcM7uIiW.js` (295.06 kB)

---

## 5. Automated Backend Test Baseline

Command: `python -m pytest tests/test_notification_comprehensive_suite.py tests/admin/test_notification_system.py tests/test_notification_ui_fixes.py`
Result: **20 passed in 14.03s (100% PASS)**

---

## 6. Current Application Routes

- `/` / `/dashboard`: Full 4-camera real-time surveillance operations dashboard.
- `/login`: Admin authentication view.
- `/admin` / `/admin/overview`: System administration overview dashboard.
- `/admin/users`: User and RBAC management.
- `/admin/cameras`: Camera hardware & stream configuration.
- `/admin/zones`: Virtual fence and boundary zone configuration.
- `/admin/alerts`: Incident escalation and alert rule policies.
- `/admin/incidents`: Incident triage and investigation log.
- `/admin/notifications`: Notification & alert settings.
- `/admin/system`: System hardware, GPU, and worker health.
- `/admin/audit`: Administrative audit log.
- `/notifications`: Full standalone incident notification center.

---

## 7. Files Inspected & Audit Findings

1. `frontend/src/hooks/useNotificationSocket.js`:
   - Identified root cause of floating toast popups: Line 238 `addToast(notif)` executes unconditionally for every `notification.created` event over WebSocket.
   - Solution: Remove security incidents from `addToast()`. Only allow non-security `SYSTEM_FEEDBACK` (e.g., settings saved, password updated).
2. `frontend/src/components/notifications/NotificationBell.jsx`:
   - Currently renders `unreadCount` badge with pulse, but without compact formatting (shows raw count instead of `99+` for large values) and lacks active severity attention signal dispatch.
3. `frontend/src/components/notifications/NotificationDrawer.jsx`:
   - Contains a full-screen `.notif-drawer-overlay` with `pointer-events: auto` that blocks interaction with the operations dashboard when open.
   - Solution: Remove the blocking overlay; convert drawer into an operator-friendly right-side command panel (`role="region"`, `width: 420px`, `z-index: var(--z-drawer)`), keeping the background dashboard 100% visible and interactive.
4. `frontend/src/components/notifications/ToastContainer.jsx`:
   - Currently mounts floating security incident alert cards with auto-dismiss timers.
   - Solution: Repurpose exclusively for `SYSTEM_FEEDBACK` toasts or suppress when not needed.
5. `frontend/src/components/admin/AdminNotifications.jsx` & `frontend/src/styles/globals.css`:
   - Contrast defect identified: CSS classes at lines 3120-3180 hardcoded `#f8fafc` (slate-50 off-white) and `#94a3b8` inside cards with `#FFFFFF` background. Contrast ratio was 1.05:1 (failing WCAG AA).
   - Solution: Implement explicit WCAG AA/AAA compliant tokens (`#111827`, `#475569`, `#334155`) and integrate tabs `[ Notification Center ] [ Settings ]` with Notification Center as default.
