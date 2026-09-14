"""
PRAHARI-AI Notification REST & WebSocket Routes
Mounted at /api/notifications for querying notifications, managing read state,
updating user preferences, and maintaining real-time WebSocket connection.
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status
)
from database import db_manager
from admin.auth import get_current_user, decode_access_token, require_role
from .notification_models import (
    NotificationItem,
    NotificationListResponse,
    UnreadCountResponse,
    PreferencesUpdateRequest,
    PreferencesResponse,
    MarkReadResponse,
    MarkAllReadResponse,
    PushSubscriptionRequest
)
from .notification_realtime import ws_manager
from .notification_service import notification_service

logger = logging.getLogger("PRAHARI-NOTIF-ROUTES")

class TestDispatchIncidentRequest(BaseModel):
    incident_id: Optional[int] = None
    camera_id: str = "CAM-01"
    event_type: str = "intrusion"
    severity: str = "CRITICAL"
    title: Optional[str] = None
    message: Optional[str] = None

class SimulateEventRequest(BaseModel):
    event_type: str = "intrusion"
    camera_id: str = "CAM-01"
    severity: str = "CRITICAL"
    details: Optional[str] = "Simulated security event for live validation"

notification_router = APIRouter(prefix="/api/notifications", tags=["Security Notifications"])


# ─── REST ENDPOINTS ───

@notification_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    since_id: Optional[int] = Query(None, description="Cursor: only return notifications newer than this notification ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve paginated notifications for the authenticated user."""
    user_id = current_user["id"]
    items_raw = db_manager.list_user_notifications(
        user_id=user_id,
        is_read=is_read,
        severity=severity,
        limit=limit,
        offset=offset,
        since_id=since_id
    )
    total = db_manager.count_user_notifications(
        user_id=user_id,
        is_read=is_read,
        severity=severity,
        since_id=since_id
    )
    unread = db_manager.get_user_unread_count(user_id)
    try:
        active_incidents = db_manager.count_admin_incidents_summary().get("open", 0)
    except Exception:
        active_incidents = 0

    items = []
    for r in items_raw:
        items.append(NotificationItem(
            id=r["id"],
            incident_id=r.get("incident_id"),
            source_event_id=r.get("source_event_id"),
            source_event_table=r.get("source_event_table"),
            camera_id=r.get("camera_id"),
            notification_type=r.get("notification_type", "INCIDENT_CREATED"),
            severity=r.get("severity", "HIGH"),
            title=r.get("title", ""),
            message=r.get("message", ""),
            metadata=r.get("metadata"),
            dedupe_key=r.get("dedupe_key"),
            created_at=r.get("created_at", ""),
            is_read=bool(r.get("is_read", 0)),
            read_at=r.get("read_at")
        ))

    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread,
        active_incidents_count=active_incidents,
        limit=limit,
        offset=offset
    )


@notification_router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch accurate unread notification count for badge display."""
    user_id = current_user["id"]
    unread = db_manager.get_user_unread_count(user_id)
    try:
        active_incidents = db_manager.count_admin_incidents_summary().get("open", 0)
    except Exception:
        active_incidents = 0
    return UnreadCountResponse(unread_count=unread, active_incidents_count=active_incidents)


@notification_router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark a specific notification as read for the current user."""
    user_id = current_user["id"]
    success = db_manager.mark_notification_read(notification_id, user_id)
    new_unread = db_manager.get_user_unread_count(user_id)

    # Sync real-time count across open tabs of this user
    await ws_manager.send_to_user(user_id, {
        "type": "notification.read",
        "notification_id": notification_id,
        "unread_count": new_unread
    })

    return MarkReadResponse(
        success=success,
        notification_id=notification_id,
        unread_count=new_unread
    )


@notification_router.post("/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_read(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Mark all unread notifications as read for current user."""
    user_id = current_user["id"]
    affected = db_manager.mark_all_notifications_read(user_id)
    new_unread = db_manager.get_user_unread_count(user_id)

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="NOTIFICATION_MARKED_READ",
        resource_type="NOTIFICATION",
        resource_id="ALL",
        result="SUCCESS",
        description=f"Marked {affected} notifications as read",
        actor_user_id=user_id
    )

    # Sync real-time count across open tabs of this user
    await ws_manager.send_to_user(user_id, {
        "type": "notification.count",
        "unread_count": new_unread
    })

    return MarkAllReadResponse(
        success=True,
        affected_count=affected,
        unread_count=new_unread
    )


@notification_router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch notification preferences for the authenticated user."""
    user_id = current_user["id"]
    prefs = db_manager.get_user_notification_preferences(user_id)
    return PreferencesResponse(
        user_id=user_id,
        critical_enabled=bool(prefs.get("critical_enabled", 1)),
        high_enabled=bool(prefs.get("high_enabled", 1)),
        medium_enabled=bool(prefs.get("medium_enabled", 1)),
        low_enabled=bool(prefs.get("low_enabled", 0)),
        sound_enabled=bool(prefs.get("sound_enabled", 1)),
        browser_enabled=bool(prefs.get("browser_enabled", 0)),
        web_push_enabled=bool(prefs.get("web_push_enabled", 0)),
        updated_at=prefs.get("updated_at", "")
    )


@notification_router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    req: PreferencesUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user notification delivery and severity preferences."""
    user_id = current_user["id"]
    success = db_manager.update_user_notification_preferences(
        user_id=user_id,
        critical_enabled=1 if req.critical_enabled is True else (0 if req.critical_enabled is False else None),
        high_enabled=1 if req.high_enabled is True else (0 if req.high_enabled is False else None),
        medium_enabled=1 if req.medium_enabled is True else (0 if req.medium_enabled is False else None),
        low_enabled=1 if req.low_enabled is True else (0 if req.low_enabled is False else None),
        sound_enabled=1 if req.sound_enabled is True else (0 if req.sound_enabled is False else None),
        browser_enabled=1 if req.browser_enabled is True else (0 if req.browser_enabled is False else None),
        web_push_enabled=1 if req.web_push_enabled is True else (0 if req.web_push_enabled is False else None)
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="NOTIFICATION_PREFERENCES_UPDATED",
        resource_type="PREFERENCES",
        resource_id=str(user_id),
        result="SUCCESS",
        description="User updated notification preferences",
        actor_user_id=user_id
    )

    prefs = db_manager.get_user_notification_preferences(user_id)
    return PreferencesResponse(
        user_id=user_id,
        critical_enabled=bool(prefs.get("critical_enabled", 1)),
        high_enabled=bool(prefs.get("high_enabled", 1)),
        medium_enabled=bool(prefs.get("medium_enabled", 1)),
        low_enabled=bool(prefs.get("low_enabled", 0)),
        sound_enabled=bool(prefs.get("sound_enabled", 1)),
        browser_enabled=bool(prefs.get("browser_enabled", 0)),
        web_push_enabled=bool(prefs.get("web_push_enabled", 0)),
        updated_at=prefs.get("updated_at", "")
    )


@notification_router.get("/push/vapid-key")
async def get_vapid_key():
    """Returns VAPID public key if Web Push is configured, or disabled status."""
    return {
        "enabled": notification_service.webpush_enabled,
        "publicKey": notification_service.vapid_public_key if notification_service.webpush_enabled else None
    }


@notification_router.post("/test-dispatch")
async def test_dispatch_incident(
    req: TestDispatchIncidentRequest,
    current_user: Dict[str, Any] = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """
    Triggers a live incident notification through the notification service on the running server process.
    Guarantees threadsafe WebSocket delivery across all active client sockets.
    """
    inc_id = req.incident_id or int(datetime.now().strftime("%y%m%d%H%M%S"))
    notif_id = notification_service.dispatch_incident_notification(
        incident_id=inc_id,
        camera_id=req.camera_id,
        event_type=req.event_type,
        severity=req.severity,
        title=req.title,
        message=req.message
    )
    if not notif_id:
        raise HTTPException(status_code=400, detail="Notification deduplicated or creation failed")

    return {
        "status": "success",
        "notification_id": notif_id,
        "incident_id": inc_id,
        "severity": req.severity,
        "camera_id": req.camera_id
    }


@notification_router.post("/simulate-event")
async def simulate_security_event(
    req: SimulateEventRequest,
    current_user: Dict[str, Any] = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """
    Simulates a full end-to-end security pipeline event on the server:
    Security Event -> evaluate_incident_policy -> admin_incidents -> notification -> recipients -> WebSocket dispatch.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if req.event_type in ("intrusion", "perimeter_breach"):
        evt_id = db_manager.log_intrusion_event(
            camera_id=req.camera_id,
            zone_name="Perimeter Zone A",
            object_type="Person",
            confidence=0.96,
            bbox=[100, 100, 200, 300],
            severity=req.severity,
            image_path=""
        )
    else:
        evt_id = db_manager.log_security_event(
            timestamp=now_str,
            event_type=req.event_type,
            camera_id=req.camera_id,
            object_type="Person",
            object_id=999,
            confidence=0.95,
            snapshot_path="",
            details=req.details or "Controlled test event",
            validation_status="DETECTED"
        )
    return {
        "status": "success",
        "event_id": evt_id,
        "event_type": req.event_type,
        "camera_id": req.camera_id
    }


# ─── REAL-TIME WEBSOCKET ENDPOINT ───

@notification_router.websocket("/ws")
async def notification_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Authenticated real-time notification delivery WebSocket.
    Authenticates via ?token=<jwt> or initial JSON frame within 0.5s.
    Rejects unauthenticated connections with code 1008.
    """
    await websocket.accept()

    auth_token = token
    user = None

    if auth_token:
        payload = decode_access_token(auth_token)
        if payload and "sub" in payload:
            db_user = db_manager.get_admin_user_by_username(payload["sub"])
            if db_user and db_user.get("is_active", 1):
                user = db_user

    if not user:
        # Give client up to 0.5 second to send auth frame: {"type": "auth", "token": "..."}
        try:
            import asyncio
            raw_msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
            data = json.loads(raw_msg)
            if data.get("type") == "auth" and data.get("token"):
                payload = decode_access_token(data["token"])
                if payload and "sub" in payload:
                    db_user = db_manager.get_admin_user_by_username(payload["sub"])
                    if db_user and db_user.get("is_active", 1):
                        user = db_user
        except Exception:
            pass

    if not user:
        logger.warning("[NotifWS] Rejecting unauthenticated WebSocket connection (code 1008).")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": "unauthorized",
                "code": 1008,
                "message": "Authentication required. Please provide a valid JWT."
            }))
            await websocket.close(code=1008, reason="Unauthorized")
        except Exception:
            pass
        return

    user_id = user["id"]
    connected = await ws_manager.connect(websocket, user_id)
    if not connected:
        return

    try:
        # Send initial connection acknowledgment with current unread count
        unread = db_manager.get_user_unread_count(user_id)
        await websocket.send_text(json.dumps({
            "type": "connection.ack",
            "status": "connected",
            "unread_count": unread
        }))

        # Message loop for ping/pong & client acknowledgments
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                msg_type = msg.get("type")
                if msg_type == "ping":
                    import time
                    unread_now = db_manager.get_user_unread_count(user_id)
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": time.time(),
                        "unread_count": unread_now
                    }))
                elif msg_type == "mark_read" and msg.get("notification_id"):
                    notif_id = int(msg["notification_id"])
                    db_manager.mark_notification_read(notif_id, user_id)
                    new_cnt = db_manager.get_user_unread_count(user_id)
                    await ws_manager.send_to_user(user_id, {
                        "type": "notification.read",
                        "notification_id": notif_id,
                        "unread_count": new_cnt
                    })
            except Exception as json_err:
                logger.debug(f"[NotifWS] Non-critical message processing error: {json_err}")

    except WebSocketDisconnect:
        logger.info(f"[NotifWS] Client disconnected normally for user {user_id}")
    except Exception as ex:
        logger.warning(f"[NotifWS] WebSocket session terminated: {ex}")
    finally:
        ws_manager.disconnect(websocket)
