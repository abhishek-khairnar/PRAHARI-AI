"""
PRAHARI-AI Notification Models & Schemas
Pydantic data schemas for REST API endpoints and real-time WebSocket payloads.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    id: int
    incident_id: Optional[int] = None
    source_event_id: Optional[int] = None
    source_event_table: Optional[str] = None
    camera_id: Optional[str] = None
    notification_type: str = "INCIDENT_CREATED"
    severity: str = "HIGH"
    title: str
    message: str
    metadata: Optional[str] = None
    dedupe_key: Optional[str] = None
    created_at: str
    is_read: bool = False
    read_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    total: int
    unread_count: int
    active_incidents_count: Optional[int] = 0
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    unread_count: int
    active_incidents_count: Optional[int] = 0


class PreferencesUpdateRequest(BaseModel):
    critical_enabled: Optional[bool] = None
    high_enabled: Optional[bool] = None
    medium_enabled: Optional[bool] = None
    low_enabled: Optional[bool] = None
    sound_enabled: Optional[bool] = None
    browser_enabled: Optional[bool] = None
    web_push_enabled: Optional[bool] = None


class PreferencesResponse(BaseModel):
    user_id: int
    critical_enabled: bool = True
    high_enabled: bool = True
    medium_enabled: bool = True
    low_enabled: bool = False
    sound_enabled: bool = True
    browser_enabled: bool = False
    web_push_enabled: bool = False
    updated_at: str


class MarkReadResponse(BaseModel):
    success: bool
    notification_id: Optional[int] = None
    unread_count: int


class MarkAllReadResponse(BaseModel):
    success: bool
    affected_count: int
    unread_count: int


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: Dict[str, str]
