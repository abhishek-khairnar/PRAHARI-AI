"""
PRAHARI-AI Automated Notification Subsystem Tests
Validates persistent notifications, recipient routing, deduplication,
read status tracking, user preferences, delivery auditing, and WebSocket auth.
"""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import database
from fastapi.testclient import TestClient
from main import app
from admin.auth import hash_password


class TestNotificationSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_notif_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_notif.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

        # Login as superadmin
        res = cls.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "Admin@Prahari2026!"
        })
        assert res.status_code == 200, f"Superadmin login failed: {res.text}"
        cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

        # Create test users for role-routing tests
        # 1. Supervisor
        pw_hash = hash_password("Supervisor@2026!")
        database.db_manager.create_admin_user("supervisor_test", pw_hash, "Test Supervisor", "SUPERVISOR", 1, 0)
        # 2. Officer
        pw_hash_off = hash_password("Officer@2026!")
        database.db_manager.create_admin_user("officer_test", pw_hash_off, "Test Officer", "OFFICER", 1, 0)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.close()
        except Exception:
            pass
        try:
            from camera_manager import camera_manager
            camera_manager.stop_all()
        except Exception:
            pass
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        database.db_manager.set_db_path(self.db_path)

    def test_01_incident_creation_creates_persistent_notification(self):
        """Creating an authentic incident must automatically insert persistent notification."""
        superadmin_user = database.db_manager.get_admin_user_by_username("superadmin")
        initial_unread = database.db_manager.get_user_unread_count(superadmin_user["id"])

        # Create an incident via evaluate_and_create_incident_from_event
        inc_id = database.db_manager.evaluate_and_create_incident_from_event(
            event_table="security_events",
            event_id=9001,
            event_type="border_intrusion",
            camera_id="CAM-01",
            timestamp="2026-09-13 14:00:00",
            details="Perimeter fence crossing detected"
        )
        self.assertIsNotNone(inc_id)
        self.assertGreater(inc_id, 0)

        # Verify notification exists
        notifs = database.db_manager.list_user_notifications(superadmin_user["id"])
        self.assertGreaterEqual(len(notifs), 1)

        latest = notifs[0]
        self.assertEqual(latest["incident_id"], inc_id)
        self.assertEqual(latest["camera_id"], "CAM-01")
        self.assertEqual(latest["severity"], "CRITICAL")
        self.assertFalse(latest["is_read"])

        # Verify unread count incremented
        new_unread = database.db_manager.get_user_unread_count(superadmin_user["id"])
        self.assertEqual(new_unread, initial_unread + 1)

    def test_02_role_based_routing(self):
        """Notifications must route only to authorized roles according to RBAC."""
        superadmin = database.db_manager.get_admin_user_by_username("superadmin")
        supervisor = database.db_manager.get_admin_user_by_username("supervisor_test")
        officer = database.db_manager.get_admin_user_by_username("officer_test")

        # Create a HIGH severity incident
        inc_high = database.db_manager.create_admin_incident(
            camera_id="CAM-02",
            event_type="night_movement",
            severity="HIGH",
            event_id=9002,
            notes="Night movement detected"
        )
        self.assertGreater(inc_high, 0)

        # Superadmin, Supervisor, Officer all receive HIGH
        self.assertTrue(any(n["incident_id"] == inc_high for n in database.db_manager.list_user_notifications(superadmin["id"])))
        self.assertTrue(any(n["incident_id"] == inc_high for n in database.db_manager.list_user_notifications(supervisor["id"])))
        self.assertTrue(any(n["incident_id"] == inc_high for n in database.db_manager.list_user_notifications(officer["id"])))

        # Create a MEDIUM alert (e.g. ANPR detection)
        inc_med = database.db_manager.create_admin_incident(
            camera_id="CAM-04",
            event_type="anpr_detection",
            severity="MEDIUM",
            event_id=9003,
            notes="Plate recognized"
        )
        self.assertGreater(inc_med, 0)

        # Superadmin & Supervisor receive MEDIUM; Officer does NOT (Officer only CRITICAL/HIGH by policy)
        self.assertTrue(any(n["incident_id"] == inc_med for n in database.db_manager.list_user_notifications(superadmin["id"])))
        self.assertTrue(any(n["incident_id"] == inc_med for n in database.db_manager.list_user_notifications(supervisor["id"])))
        self.assertFalse(any(n["incident_id"] == inc_med for n in database.db_manager.list_user_notifications(officer["id"])))

    def test_03_notification_deduplication(self):
        """Repeated events within cooldown window must not create duplicate notifications."""
        superadmin = database.db_manager.get_admin_user_by_username("superadmin")
        count_before = len(database.db_manager.list_user_notifications(superadmin["id"]))

        # Trigger event on CAM-01 (border_intrusion has 10s cooldown)
        inc_1 = database.db_manager.evaluate_and_create_incident_from_event(
            event_table="security_events",
            event_id=9100,
            event_type="border_intrusion",
            camera_id="CAM-01",
            timestamp="2026-09-13 14:10:00"
        )
        count_after_first = len(database.db_manager.list_user_notifications(superadmin["id"]))
        self.assertEqual(count_after_first, count_before + 1)

        # Trigger duplicate event 2 seconds later on same camera and event_type
        inc_dup = database.db_manager.evaluate_and_create_incident_from_event(
            event_table="security_events",
            event_id=9101,
            event_type="border_intrusion",
            camera_id="CAM-01",
            timestamp="2026-09-13 14:10:02"
        )
        # Incident policy correlates to existing incident
        self.assertEqual(inc_dup, inc_1)

        # Notification count MUST NOT increment
        count_after_dup = len(database.db_manager.list_user_notifications(superadmin["id"]))
        self.assertEqual(count_after_dup, count_after_first, "Duplicate event within cooldown must not generate duplicate notification")

    def test_04_mark_single_and_all_as_read(self):
        """Mark as read must update database read_at and decrement unread count."""
        superadmin = database.db_manager.get_admin_user_by_username("superadmin")
        unread_before = database.db_manager.get_user_unread_count(superadmin["id"])
        self.assertGreater(unread_before, 0)

        notifs = database.db_manager.list_user_notifications(superadmin["id"], is_read=False)
        target_id = notifs[0]["id"]

        # Mark single as read via REST API
        res = self.client.post(f"/api/notifications/{target_id}/read", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["unread_count"], unread_before - 1)

        # Mark all as read via REST API
        res_all = self.client.post("/api/notifications/mark-all-read", headers=self.headers)
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.json()["unread_count"], 0)

        # Confirm DB agreement
        self.assertEqual(database.db_manager.get_user_unread_count(superadmin["id"]), 0)

    def test_05_user_notification_preferences(self):
        """User preferences must control severity delivery and persist correctly."""
        superadmin = database.db_manager.get_admin_user_by_username("superadmin")

        # Update preferences: disable HIGH notifications
        put_res = self.client.put("/api/notifications/preferences", json={
            "critical_enabled": True,
            "high_enabled": False,
            "sound_enabled": True,
            "browser_enabled": False
        }, headers=self.headers)
        self.assertEqual(put_res.status_code, 200)
        self.assertFalse(put_res.json()["high_enabled"])

        # Create a HIGH severity incident
        inc_high = database.db_manager.create_admin_incident(
            camera_id="CAM-03",
            event_type="suspicious_activity",
            severity="HIGH",
            event_id=9200
        )
        self.assertGreater(inc_high, 0)

        # Superadmin has high_enabled = False, so superadmin should NOT receive this notification
        superadmin_notifs = database.db_manager.list_user_notifications(superadmin["id"])
        self.assertFalse(any(n["incident_id"] == inc_high for n in superadmin_notifs))

        # Restore preferences
        self.client.put("/api/notifications/preferences", json={
            "high_enabled": True
        }, headers=self.headers)

    def test_06_notification_delivery_logging(self):
        """Delivery attempts must be logged in notification_deliveries table."""
        conn = database.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notification_deliveries WHERE channel = 'IN_APP'")
        count = cursor.fetchone()[0]
        if count == 0:
            database.db_manager.create_admin_incident(
                camera_id="CAM-01",
                event_type="border_intrusion",
                severity="HIGH",
                event_id=9900
            )
            cursor.execute("SELECT COUNT(*) FROM notification_deliveries WHERE channel = 'IN_APP'")
            count = cursor.fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "IN_APP delivery attempts must be logged in database")

    def test_07_websocket_authentication_guard(self):
        """WebSocket must reject unauthenticated connections and accept valid JWT."""
        # Unauthenticated connection with invalid token should receive unauthorized error
        with self.client.websocket_connect("/api/notifications/ws?token=invalid_jwt") as ws:
            err = ws.receive_json()
            self.assertEqual(err.get("error"), "unauthorized")

        # Authenticated connection via query param ?token=
        with self.client.websocket_connect(f"/api/notifications/ws?token={self.token}") as ws:
            data = ws.receive_json()
            self.assertEqual(data["type"], "connection.ack")
            self.assertEqual(data["status"], "connected")
            self.assertIn("unread_count", data)

            # Test ping/pong
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            self.assertEqual(pong["type"], "pong")


if __name__ == "__main__":
    unittest.main()
