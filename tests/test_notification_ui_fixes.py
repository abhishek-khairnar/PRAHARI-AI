import os
import pytest
import sqlite3
from datetime import datetime
from database import DatabaseManager
from notifications.notification_service import NotificationService

@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_prahari_notif_fix.db")
    db = DatabaseManager(db_path=db_file)
    # Ensure default admin user
    db.create_admin_user(
        username="admin_test",
        password_hash="fake_hash",
        full_name="Admin Test",
        role="SUPER_ADMIN"
    )
    yield db


def test_notification_unique_dedupe_and_idempotency(temp_db):
    """Verify that inserting duplicate dedupe keys is suppressed atomically."""
    # 1. First insertion
    notif_id_1 = temp_db.create_notification(
        incident_id=9001,
        camera_id="CAM-01",
        notification_type="INCIDENT_CREATED",
        severity="HIGH",
        title="HIGH SECURITY ALERT",
        message="Test alert",
        dedupe_key="INC_9001_INCIDENT_CREATED_HIGH"
    )
    assert notif_id_1 is not None and notif_id_1 > 0

    # 2. Second insertion with exact same dedupe_key must be suppressed (return None)
    notif_id_2 = temp_db.create_notification(
        incident_id=9001,
        camera_id="CAM-01",
        notification_type="INCIDENT_CREATED",
        severity="HIGH",
        title="HIGH SECURITY ALERT",
        message="Test alert duplicate",
        dedupe_key="INC_9001_INCIDENT_CREATED_HIGH"
    )
    assert notif_id_2 is None, "Duplicate dedupe_key must be suppressed"

    # 3. Escalation: Different severity/type produces a new dedupe_key and is allowed
    notif_id_3 = temp_db.create_notification(
        incident_id=9001,
        camera_id="CAM-01",
        notification_type="INCIDENT_ESCALATED",
        severity="CRITICAL",
        title="CRITICAL SECURITY ALERT",
        message="Escalated to critical",
        dedupe_key="INC_9001_INCIDENT_ESCALATED_CRITICAL"
    )
    assert notif_id_3 is not None and notif_id_3 > notif_id_1


def test_internal_dispatch_idempotency(temp_db):
    """Verify _create_and_dispatch_incident_notification_internal idempotency."""
    conn = temp_db._get_connection()
    cursor = conn.cursor()

    # Dispatch first time
    id_1 = temp_db._create_and_dispatch_incident_notification_internal(
        cursor=cursor,
        incident_id=9002,
        incident_code="INC-9002",
        camera_id="CAM-02",
        event_type="border_intrusion",
        severity="CRITICAL"
    )
    conn.commit()
    assert id_1 is not None

    # Dispatch second time with same incident & severity
    id_2 = temp_db._create_and_dispatch_incident_notification_internal(
        cursor=cursor,
        incident_id=9002,
        incident_code="INC-9002",
        camera_id="CAM-02",
        event_type="border_intrusion",
        severity="CRITICAL"
    )
    conn.commit()
    conn.close()
    assert id_2 is None, "Second internal dispatch must be suppressed by dedupe_key"


def test_unread_count_and_mark_all_read(temp_db):
    """Verify mark_all_notifications_read affects only unread recipient rows."""
    user = temp_db.get_admin_user_by_username("admin_test")
    uid = user["id"]

    # Create 3 notifications
    for i in range(1, 4):
        nid = temp_db.create_notification(
            incident_id=i,
            camera_id="CAM-01",
            notification_type="INCIDENT_CREATED",
            severity="HIGH",
            title=f"Alert {i}",
            message=f"Message {i}",
            dedupe_key=f"INC_{i}_HIGH"
        )
        temp_db.add_notification_recipients(nid, [uid])

    assert temp_db.get_user_unread_count(uid) == 3

    # Mark 1 as read
    temp_db.mark_notification_read(1, uid)
    assert temp_db.get_user_unread_count(uid) == 2

    # Mark all read
    affected = temp_db.mark_all_notifications_read(uid)
    assert affected == 2
    assert temp_db.get_user_unread_count(uid) == 0

    # Ensure total notifications in notifications table are NOT deleted
    notifications = temp_db.list_user_notifications(uid, limit=10)
    assert len(notifications) == 3
    assert all(n["is_read"] for n in notifications)
