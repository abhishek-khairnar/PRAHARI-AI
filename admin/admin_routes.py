"""
PRAHARI-AI Admin Panel API Routers
Provides REST endpoints for authentication (/api/auth/*) and administrative
system management (/api/admin/*).
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status
from database import db_manager
from admin.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role
)

logger = logging.getLogger("PRAHARI-ADMIN-ROUTES")

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
admin_router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])

# ─── Pydantic Request Schemas ───

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "OFFICER"
    is_active: int = 1

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[int] = None

class PasswordResetRequest(BaseModel):
    new_password: str

class CameraConfigRequest(BaseModel):
    name: Optional[str] = None
    location_zone: Optional[str] = None
    ai_enabled: Optional[bool] = None
    anpr_enabled: Optional[bool] = None
    night_detection: Optional[bool] = None

class ZoneCreateRequest(BaseModel):
    zone_name: str
    camera_id: str
    zone_type: str
    severity: str = "MEDIUM"
    is_enabled: int = 1
    fence_direction: str = "BOTH"
    fence_ratio: float = 0.5

class ZoneUpdateRequest(BaseModel):
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    severity: Optional[str] = None
    is_enabled: Optional[int] = None
    fence_direction: Optional[str] = None
    fence_ratio: Optional[float] = None

class AlertRuleUpdateRequest(BaseModel):
    severity: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    requires_ack: Optional[int] = None
    is_enabled: Optional[int] = None
    description: Optional[str] = None

class IncidentCreateRequest(BaseModel):
    camera_id: str
    event_type: str
    severity: str = "HIGH"
    event_id: Optional[int] = None
    event_table: str = "security_events"
    zone_name: Optional[str] = None
    assigned_officer_id: Optional[int] = None
    assigned_officer_name: Optional[str] = None
    evidence_snapshot: Optional[str] = None
    notes: Optional[str] = None

class IncidentUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_officer_id: Optional[int] = None
    assigned_officer_name: Optional[str] = None
    notes: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# 1. AUTHENTICATION ENDPOINTS (/api/auth)
# ═══════════════════════════════════════════════════════════

@auth_router.post("/login")
async def login(req: LoginRequest):
    """Authenticate with username and password, returning JWT bearer token."""
    username = req.username.strip()
    password = req.password

    user = db_manager.get_admin_user_by_username(username)
    if not user:
        db_manager.log_audit_event(
            actor_username=username,
            role="ANONYMOUS",
            action="LOGIN_FAILURE",
            resource_type="AUTH",
            result="FAILURE",
            description="User does not exist"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    if not user.get("is_active", 1):
        db_manager.log_audit_event(
            actor_username=username,
            role=user.get("role", "UNKNOWN"),
            action="LOGIN_BLOCKED",
            resource_type="AUTH",
            result="DENIED",
            description="Account is disabled",
            actor_user_id=user.get("id")
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact system administrator."
        )

    if not verify_password(password, user.get("password_hash", "")):
        db_manager.log_audit_event(
            actor_username=username,
            role=user.get("role", "UNKNOWN"),
            action="LOGIN_FAILURE",
            resource_type="AUTH",
            result="FAILURE",
            description="Invalid credentials provided",
            actor_user_id=user.get("id")
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Success: Generate JWT token & update last login
    db_manager.update_admin_user_last_login(user["id"])
    token = create_access_token({"sub": user["username"], "role": user["role"]})

    db_manager.log_audit_event(
        actor_username=username,
        role=user["role"],
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        result="SUCCESS",
        description="Successful administrator authentication",
        actor_user_id=user["id"]
    )

    safe_user = {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": user["is_active"]
    }

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": safe_user
    }


@auth_router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Log out active session and record audit event."""
    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="LOGOUT",
        resource_type="AUTH",
        result="SUCCESS",
        description="User signed out",
        actor_user_id=current_user["id"]
    )
    return {"status": "success", "message": "Successfully signed out."}


@auth_router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return currently authenticated administrator identity and role."""
    return current_user


# ═══════════════════════════════════════════════════════════
# 2. OVERVIEW TELEMETRY (/api/admin/overview)
# ═══════════════════════════════════════════════════════════

@admin_router.get("/overview")
async def get_admin_overview(current_user: dict = Depends(get_current_user)):
    """Aggregated command-center KPI telemetry for Admin Panel landing view."""
    from camera_manager import camera_manager

    cams = camera_manager.get_camera_list()
    active_cams = sum(1 for c in cams if c.get("connected") or c.get("active"))
    incidents_summary = db_manager.count_admin_incidents_summary()
    recent_incidents = db_manager.list_admin_incidents(limit=5)
    users_list = db_manager.list_admin_users()

    # Determine recent audit logs if authorized
    recent_audits = []
    if current_user["role"] in ["SUPER_ADMIN", "ADMIN"]:
        recent_audits = db_manager.list_admin_audit_logs(limit=5)

    return {
        "user": current_user,
        "metrics": {
            "total_users": len(users_list),
            "active_users": sum(1 for u in users_list if u.get("is_active")),
            "total_cameras": len(cams),
            "online_cameras": active_cams,
            "open_incidents": incidents_summary["open"],
            "total_incidents": incidents_summary["total"]
        },
        "incidents_by_status": incidents_summary["by_status"],
        "recent_incidents": recent_incidents,
        "recent_audits": recent_audits
    }


# ═══════════════════════════════════════════════════════════
# 3. USER MANAGEMENT (/api/admin/users)
# ═══════════════════════════════════════════════════════════

VALID_ROLES = ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OFFICER"]

@admin_router.get("/users")
async def list_users(
    role: Optional[str] = None,
    is_active: Optional[int] = None,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """List all registered system users (passwords omitted)."""
    users = db_manager.list_admin_users(role=role, is_active=is_active)
    return users


@admin_router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Create a new user account with RBAC validation."""
    username = req.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from {VALID_ROLES}")

    # RBAC Safeguard: ADMIN cannot create SUPER_ADMIN
    if req.role == "SUPER_ADMIN" and current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only a Super Admin can create Super Admin accounts.")

    # Prevent duplicate usernames
    if db_manager.get_admin_user_by_username(username):
        raise HTTPException(status_code=409, detail=f"Username '{username}' already exists.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    pw_hash = hash_password(req.password)
    user_id = db_manager.create_admin_user(
        username=username,
        password_hash=pw_hash,
        full_name=req.full_name.strip(),
        role=req.role,
        is_active=req.is_active
    )

    if user_id <= 0:
        raise HTTPException(status_code=500, detail="Database error creating user.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="USER_CREATED",
        resource_type="USER",
        resource_id=str(user_id),
        result="SUCCESS",
        description=f"Created user '{username}' with role '{req.role}'",
        actor_user_id=current_user["id"]
    )

    created_user = db_manager.get_admin_user_by_id(user_id)
    created_user.pop("password_hash", None)
    return created_user


@admin_router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Update user attributes (role, full_name, status) with last-superadmin protection."""
    target_user = db_manager.get_admin_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User ID {user_id} not found.")

    # RBAC Safeguards
    if target_user["role"] == "SUPER_ADMIN" and current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only Super Administrators can modify Super Admin accounts.")

    if req.role and req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from {VALID_ROLES}")

    if req.role == "SUPER_ADMIN" and current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only a Super Admin can promote users to Super Admin.")

    # Protect against demoting or disabling the last active SUPER_ADMIN
    if target_user["role"] == "SUPER_ADMIN":
        if (req.is_active == 0) or (req.role and req.role != "SUPER_ADMIN"):
            if db_manager.count_active_superadmins() <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate or demote the last active Super Administrator."
                )

    success = db_manager.update_admin_user(
        user_id=user_id,
        full_name=req.full_name,
        role=req.role,
        is_active=req.is_active
    )

    if not success:
        raise HTTPException(status_code=500, detail="Database update failed.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="USER_UPDATED",
        resource_type="USER",
        resource_id=str(user_id),
        result="SUCCESS",
        description=f"Updated user '{target_user['username']}': role={req.role}, active={req.is_active}",
        actor_user_id=current_user["id"]
    )

    updated_user = db_manager.get_admin_user_by_id(user_id)
    updated_user.pop("password_hash", None)
    return updated_user


@admin_router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    req: PasswordResetRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Reset a user's password securely."""
    target_user = db_manager.get_admin_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User ID {user_id} not found.")

    if target_user["role"] == "SUPER_ADMIN" and current_user["role"] != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only Super Admins can reset Super Admin passwords.")

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    pw_hash = hash_password(req.new_password)
    db_manager.update_admin_user(user_id=user_id, password_hash=pw_hash)

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="USER_PASSWORD_RESET",
        resource_type="USER",
        resource_id=str(user_id),
        result="SUCCESS",
        description=f"Password reset for user '{target_user['username']}'",
        actor_user_id=current_user["id"]
    )

    return {"status": "success", "message": f"Password reset for user '{target_user['username']}'."}


# ═══════════════════════════════════════════════════════════
# 4. CAMERA CONFIGURATION (/api/admin/cameras)
# ═══════════════════════════════════════════════════════════

# In-memory administrative overrides for camera operational metadata
CAMERA_ADMIN_CONFIG = {
    "CAM-01": {"location_zone": "Border Restricted Zone", "ai_enabled": True, "anpr_enabled": True, "night_detection": False},
    "CAM-02": {"location_zone": "Night Checkpoint Bravo", "ai_enabled": True, "anpr_enabled": False, "night_detection": True},
    "CAM-03": {"location_zone": "Perimeter Patrol Area", "ai_enabled": True, "anpr_enabled": False, "night_detection": False},
    "CAM-04": {"location_zone": "Facility Observation Delta", "ai_enabled": True, "anpr_enabled": True, "night_detection": False},
}

@admin_router.get("/cameras")
async def get_admin_cameras(current_user: dict = Depends(get_current_user)):
    """Retrieve all cameras with real-time streaming health and admin metadata."""
    from camera_manager import camera_manager

    cams = camera_manager.get_camera_list()
    result = []
    for c in cams:
        cid = c.get("id") or c.get("camera_id")
        cfg = CAMERA_ADMIN_CONFIG.get(cid, {
            "location_zone": "Default Zone",
            "ai_enabled": True,
            "anpr_enabled": True,
            "night_detection": False
        })
        reader = camera_manager.get_reader(cid)
        fps = getattr(reader, "current_fps", 0.0) if reader else c.get("fps", 0.0)
        connected = reader.is_connected if reader else False
        last_seen = time.strftime("%Y-%m-%d %H:%M:%S") if connected else "OFFLINE"

        result.append({
            "camera_id": cid,
            "name": c.get("name", cid),
            "source": c.get("source", "video"),
            "source_type": "DEMO_FILE" if "demo_videos" in str(c.get("source", "")) else "RTSP_STREAM",
            "status": "ONLINE" if connected else "OFFLINE",
            "connected": connected,
            "active": c.get("active", False),
            "fps": round(fps, 1),
            "location_zone": cfg["location_zone"],
            "ai_enabled": cfg["ai_enabled"],
            "anpr_enabled": cfg["anpr_enabled"],
            "night_detection": cfg["night_detection"],
            "last_seen": last_seen
        })
    return result


@admin_router.patch("/cameras/{camera_id}")
async def update_admin_camera(
    camera_id: str,
    req: CameraConfigRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Safely update camera metadata and AI processing toggles."""
    from camera_manager import camera_manager
    reader = camera_manager.get_reader(camera_id)
    if not reader:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    if camera_id not in CAMERA_ADMIN_CONFIG:
        CAMERA_ADMIN_CONFIG[camera_id] = {
            "location_zone": "Default Zone",
            "ai_enabled": True,
            "anpr_enabled": True,
            "night_detection": False
        }

    cfg = CAMERA_ADMIN_CONFIG[camera_id]
    if req.name is not None:
        reader.name = req.name
    if req.location_zone is not None:
        cfg["location_zone"] = req.location_zone
    if req.ai_enabled is not None:
        cfg["ai_enabled"] = req.ai_enabled
    if req.anpr_enabled is not None:
        cfg["anpr_enabled"] = req.anpr_enabled
    if req.night_detection is not None:
        cfg["night_detection"] = req.night_detection

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="CAMERA_UPDATED",
        resource_type="CAMERA",
        resource_id=camera_id,
        result="SUCCESS",
        description=f"Updated camera {camera_id}: zone={cfg['location_zone']}, AI={cfg['ai_enabled']}",
        actor_user_id=current_user["id"]
    )

    return {
        "status": "success",
        "camera_id": camera_id,
        "name": reader.name,
        "config": cfg
    }


# ═══════════════════════════════════════════════════════════
# 5. ZONES & VIRTUAL FENCES (/api/admin/zones)
# ═══════════════════════════════════════════════════════════

@admin_router.get("/zones")
async def list_zones(
    camera_id: Optional[str] = None,
    is_enabled: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """List security zones and virtual fence configurations."""
    return db_manager.list_admin_zones(camera_id=camera_id, is_enabled=is_enabled)


@admin_router.post("/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(
    req: ZoneCreateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Create a new zone or virtual fence."""
    zone_id = db_manager.create_admin_zone(
        zone_name=req.zone_name.strip(),
        camera_id=req.camera_id.strip(),
        zone_type=req.zone_type.strip(),
        severity=req.severity,
        is_enabled=req.is_enabled,
        fence_direction=req.fence_direction,
        fence_ratio=req.fence_ratio
    )
    if zone_id <= 0:
        raise HTTPException(status_code=500, detail="Database error creating zone.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="ZONE_CREATED",
        resource_type="ZONE",
        resource_id=str(zone_id),
        result="SUCCESS",
        description=f"Created zone '{req.zone_name}' for {req.camera_id}",
        actor_user_id=current_user["id"]
    )

    return db_manager.get_admin_zone_by_id(zone_id)


@admin_router.patch("/zones/{zone_id}")
async def update_zone(
    zone_id: int,
    req: ZoneUpdateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Update an existing security zone configuration."""
    zone = db_manager.get_admin_zone_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone ID {zone_id} not found.")

    success = db_manager.update_admin_zone(
        zone_id=zone_id,
        zone_name=req.zone_name,
        zone_type=req.zone_type,
        severity=req.severity,
        is_enabled=req.is_enabled,
        fence_direction=req.fence_direction,
        fence_ratio=req.fence_ratio
    )

    if not success:
        raise HTTPException(status_code=500, detail="Database update failed.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="ZONE_UPDATED",
        resource_type="ZONE",
        resource_id=str(zone_id),
        result="SUCCESS",
        description=f"Updated zone '{zone['zone_name']}'",
        actor_user_id=current_user["id"]
    )

    return db_manager.get_admin_zone_by_id(zone_id)


@admin_router.delete("/zones/{zone_id}")
async def delete_zone(
    zone_id: int,
    current_user: dict = Depends(require_role(["SUPER_ADMIN"]))
):
    """Delete a zone (Super Admin only)."""
    zone = db_manager.get_admin_zone_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone ID {zone_id} not found.")

    db_manager.delete_admin_zone(zone_id)
    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="ZONE_DELETED",
        resource_type="ZONE",
        resource_id=str(zone_id),
        result="SUCCESS",
        description=f"Deleted zone '{zone['zone_name']}'",
        actor_user_id=current_user["id"]
    )
    return {"status": "success", "message": f"Zone {zone_id} deleted."}


# ═══════════════════════════════════════════════════════════
# 6. ALERT RULES MANAGEMENT (/api/admin/alert-rules)
# ═══════════════════════════════════════════════════════════

@admin_router.get("/alert-rules")
async def list_alert_rules(current_user: dict = Depends(get_current_user)):
    """List local event policy rules."""
    return db_manager.list_admin_alert_rules()


@admin_router.patch("/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    req: AlertRuleUpdateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Update alert severity, cooldown period, and acknowledgement settings."""
    rule = db_manager.get_admin_alert_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found.")

    success = db_manager.update_admin_alert_rule(
        rule_id=rule_id,
        severity=req.severity,
        cooldown_seconds=req.cooldown_seconds,
        requires_ack=req.requires_ack,
        is_enabled=req.is_enabled,
        description=req.description
    )

    if not success:
        raise HTTPException(status_code=500, detail="Database update failed.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="ALERT_RULE_UPDATED",
        resource_type="ALERT_RULE",
        resource_id=str(rule_id),
        result="SUCCESS",
        description=f"Updated rule '{rule['event_type']}': severity={req.severity}, cooldown={req.cooldown_seconds}s",
        actor_user_id=current_user["id"]
    )

    return db_manager.get_admin_alert_rule(rule_id)


# ═══════════════════════════════════════════════════════════
# 7. INCIDENT MANAGEMENT (/api/admin/incidents)
# ═══════════════════════════════════════════════════════════

VALID_INCIDENT_STATUSES = ["NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"]

@admin_router.get("/incidents")
async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """List operational incidents with filters and pagination."""
    return db_manager.list_admin_incidents(
        status=status,
        severity=severity,
        camera_id=camera_id,
        limit=limit,
        offset=offset
    )


@admin_router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(
    req: IncidentCreateRequest,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"]))
):
    """Create an incident linked to an operational event."""
    inc_code = f"INC-{int(time.time() * 1000) % 1000000}"
    inc_id = db_manager.create_admin_incident(
        incident_code=inc_code,
        camera_id=req.camera_id,
        event_type=req.event_type,
        severity=req.severity,
        status="NEW",
        event_id=req.event_id,
        event_table=req.event_table,
        zone_name=req.zone_name or "Restricted Sector",
        assigned_officer_id=req.assigned_officer_id,
        assigned_officer_name=req.assigned_officer_name,
        evidence_snapshot=req.evidence_snapshot,
        notes=req.notes or f"Created by {current_user['username']}"
    )

    if inc_id <= 0:
        raise HTTPException(status_code=500, detail="Database error creating incident.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action="INCIDENT_CREATED",
        resource_type="INCIDENT",
        resource_id=inc_code,
        result="SUCCESS",
        description=f"Created incident {inc_code} for {req.camera_id} ({req.event_type})",
        actor_user_id=current_user["id"]
    )

    return db_manager.get_admin_incident_by_id(inc_id)


@admin_router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve full incident details and evidence snapshot."""
    inc = db_manager.get_admin_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident ID {incident_id} not found.")
    return inc


@admin_router.patch("/incidents/{incident_id}")
async def update_incident(
    incident_id: int,
    req: IncidentUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update incident status, assign officer, or log notes."""
    inc = db_manager.get_admin_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident ID {incident_id} not found.")

    if req.status and req.status not in VALID_INCIDENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from {VALID_INCIDENT_STATUSES}")

    # Role enforcement on status transitions
    # OFFICER can only ACKNOWLEDGE or append notes; cannot resolve or dismiss
    if req.status in ["RESOLVED", "DISMISSED"] and current_user["role"] == "OFFICER":
        raise HTTPException(
            status_code=403,
            detail="Officers cannot resolve or dismiss incidents. Only Supervisors and Admins can finalize incidents."
        )

    resolved_by = current_user["username"] if req.status in ["RESOLVED", "DISMISSED"] else None

    success = db_manager.update_admin_incident(
        incident_id=incident_id,
        status=req.status,
        assigned_officer_id=req.assigned_officer_id,
        assigned_officer_name=req.assigned_officer_name,
        notes=req.notes,
        resolved_by=resolved_by
    )

    if not success:
        raise HTTPException(status_code=500, detail="Database update failed.")

    db_manager.log_audit_event(
        actor_username=current_user["username"],
        role=current_user["role"],
        action=f"INCIDENT_{req.status or 'UPDATED'}",
        resource_type="INCIDENT",
        resource_id=inc["incident_code"],
        result="SUCCESS",
        description=f"Status: {req.status or inc['status']}, Notes added by {current_user['username']}",
        actor_user_id=current_user["id"]
    )

    return db_manager.get_admin_incident_by_id(incident_id)


# ═══════════════════════════════════════════════════════════
# 8. SYSTEM HEALTH TELEMETRY (/api/admin/system-health)
# ═══════════════════════════════════════════════════════════

@admin_router.get("/system-health")
async def get_system_health(current_user: dict = Depends(get_current_user)):
    """Retrieve real live hardware, database, AI model, and camera pipeline telemetry."""
    from camera_manager import camera_manager
    from rtsp_stream import ModelRegistry

    # 1. Database Health
    db_health = db_manager.get_database_health()

    # 2. Camera Pipeline Health
    cams = camera_manager.get_camera_list()
    cam_details = {}
    for c in cams:
        cid = c.get("id") or c.get("camera_id")
        reader = camera_manager.get_reader(cid)
        connected = reader.is_connected if reader else False
        fps = round(getattr(reader, "current_fps", 0.0), 1) if reader else 0.0
        cam_details[cid] = {
            "name": c.get("name", cid),
            "status": "ONLINE" if connected else "OFFLINE",
            "fps": fps,
            "source": c.get("source", "video")
        }

    # 3. Model Registry & Hardware
    registry = ModelRegistry()
    model_loaded = registry.yolo_model is not None
    anpr_ready = registry.anpr_engine is not None

    import torch
    gpu_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if gpu_available else "CPU (Fallback)"

    # 4. Storage Checks
    static_alerts = os.path.join(os.path.dirname(__file__), "..", "static", "alerts")
    alerts_count = len(os.listdir(static_alerts)) if os.path.exists(static_alerts) else 0

    return {
        "backend": {
            "status": "ONLINE",
            "process_pid": os.getpid(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "database": db_health,
        "cameras": cam_details,
        "ai_pipeline": {
            "yolo_model": "LOADED" if model_loaded else "NOT AVAILABLE",
            "anpr_engine": "READY" if anpr_ready else "NOT AVAILABLE",
            "compute_device": device_name,
            "cuda_accelerated": gpu_available
        },
        "storage": {
            "status": "HEALTHY",
            "snapshot_count": alerts_count
        }
    }


# ═══════════════════════════════════════════════════════════
# 9. AUDIT LOGS (/api/admin/audit-logs)
# ═══════════════════════════════════════════════════════════

@admin_router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    actor: Optional[str] = None,
    current_user: dict = Depends(require_role(["SUPER_ADMIN", "ADMIN"]))
):
    """Retrieve immutable administrative audit log trail."""
    return db_manager.list_admin_audit_logs(
        limit=limit,
        offset=offset,
        action=action,
        actor=actor
    )
