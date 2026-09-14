"""
PRAHARI-AI Security Notification Service
Central orchestrator for persistent notification generation, RBAC recipient filtering,
user preference enforcement, deduplication, and asynchronous multi-channel delivery.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from database import db_manager
from .notification_realtime import ws_manager

logger = logging.getLogger("PRAHARI-NOTIF-SVC")


class NotificationService:
    def __init__(self):
        self.webpush_enabled = os.getenv("PRAHARI_WEBPUSH_ENABLED", "false").lower() in ("true", "1", "yes")
        self.vapid_public_key = os.getenv("PRAHARI_VAPID_PUBLIC_KEY", "")
        self.vapid_private_key = os.getenv("PRAHARI_VAPID_PRIVATE_KEY", "")
        self.vapid_subject = os.getenv("PRAHARI_VAPID_SUBJECT", "mailto:security@prahari.local")

    def _get_eligible_recipient_user_ids(self, severity: str, event_type: str = "") -> List[int]:
        """
        Calculates eligible user IDs according to RBAC policy and user preferences.
        Roles:
        - SUPER_ADMIN: All notifications
        - ADMIN: All operational & administrative notifications
        - SUPERVISOR: All operational security notifications (CRITICAL, HIGH, MEDIUM)
        - OFFICER: High-priority operational alerts (CRITICAL, HIGH)
        """
        try:
            users = db_manager.list_admin_users(is_active=1)
            eligible_ids = []
            sev_upper = severity.upper()

            for u in users:
                uid = u["id"]
                role = u.get("role", "OFFICER")

                # RBAC gate
                role_allowed = False
                if role in ("SUPER_ADMIN", "ADMIN"):
                    role_allowed = True
                elif role == "SUPERVISOR":
                    role_allowed = sev_upper in ("CRITICAL", "HIGH", "MEDIUM")
                elif role == "OFFICER":
                    role_allowed = sev_upper in ("CRITICAL", "HIGH")
                else:
                    role_allowed = False

                if not role_allowed:
                    continue

                # User preference gate
                prefs = db_manager.get_user_notification_preferences(uid)
                if sev_upper == "CRITICAL" and not prefs.get("critical_enabled", 1):
                    continue
                if sev_upper == "HIGH" and not prefs.get("high_enabled", 1):
                    continue
                if sev_upper == "MEDIUM" and not prefs.get("medium_enabled", 1):
                    continue
                if sev_upper in ("LOW", "INFO") and not prefs.get("low_enabled", 0):
                    continue

                eligible_ids.append(uid)

            return eligible_ids
        except Exception as e:
            logger.error(f"[NotificationService] Error determining recipients: {e}")
            return []

    def dispatch_incident_notification(
        self,
        incident_id: int,
        camera_id: str,
        event_type: str,
        severity: str,
        title: Optional[str] = None,
        message: Optional[str] = None,
        source_event_id: Optional[int] = None,
        source_event_table: Optional[str] = "security_events",
        is_escalation: bool = False
    ) -> Optional[int]:
        """
        Creates and dispatches a persistent notification from an authentic incident.
        Guaranteed non-blocking for AI inference threads.
        """
        try:
            notification_type = "INCIDENT_ESCALATED" if is_escalation else "INCIDENT_CREATED"
            dedupe_key = f"INC_{incident_id}_{notification_type}_{severity.upper()}"

            # 1. Deduplication: deterministic dedupe key check
            # Format title & message if not explicitly provided
            clean_event = event_type.replace('_', ' ').title()
            if not title:
                title = f"{severity.upper()} SECURITY ALERT"
            if not message:
                message = f"{clean_event} detected on {camera_id} (Incident #{incident_id})"

            meta = json.dumps({
                "incident_id": incident_id,
                "camera_id": camera_id,
                "event_type": event_type,
                "severity": severity,
                "source_event_id": source_event_id,
                "source_event_table": source_event_table
            })

            # 2. Persist notification to database
            notif_id = db_manager.create_notification(
                incident_id=incident_id,
                source_event_id=source_event_id,
                source_event_table=source_event_table,
                camera_id=camera_id,
                notification_type=notification_type,
                severity=severity,
                title=title,
                message=message,
                metadata=meta,
                dedupe_key=dedupe_key
            )

            if not notif_id:
                logger.info(f"[NotificationService] Notification creation suppressed by deduplication: {dedupe_key}")
                return None

            # 3. Determine recipients based on RBAC & preferences
            recipient_ids = self._get_eligible_recipient_user_ids(severity=severity, event_type=event_type)
            if recipient_ids:
                db_manager.add_notification_recipients(notif_id, recipient_ids)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 4. Multi-channel delivery: In-App Real-Time WebSocket broadcast
            for uid in recipient_ids:
                unread = db_manager.get_user_unread_count(uid)
                payload = {
                    "type": "notification.created",
                    "notification": {
                        "id": notif_id,
                        "incident_id": incident_id,
                        "camera_id": camera_id,
                        "notification_type": notification_type,
                        "severity": severity,
                        "title": title,
                        "message": message,
                        "metadata": meta,
                        "dedupe_key": dedupe_key,
                        "created_at": now_str,
                        "is_read": False,
                        "read_at": None
                    },
                    "unread_count": unread
                }
                ws_manager.dispatch_payload_threadsafe([uid], payload)
                db_manager.log_notification_delivery(notif_id, uid, "IN_APP", "DELIVERED")

            logger.info(f"🔔 [NOTIFICATION {notif_id}] Dispatched to {len(recipient_ids)} recipients for Incident #{incident_id} ({severity})")
            return notif_id

        except Exception as ex:
            logger.error(f"[NotificationService] Error dispatching incident notification: {ex}", exc_info=True)
            return None


notification_service = NotificationService()
