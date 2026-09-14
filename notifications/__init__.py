"""
PRAHARI-AI Security Notification Subsystem
Handles persistence, recipient routing, deduplication, and real-time delivery
of operational security alerts across WebSocket and UI channels.
"""

from .notification_service import notification_service
from .notification_realtime import ws_manager
from .notification_routes import notification_router

__all__ = ["notification_service", "ws_manager", "notification_router"]
