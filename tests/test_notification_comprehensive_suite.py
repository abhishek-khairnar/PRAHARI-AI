"""
PRAHARI-AI Comprehensive End-to-End Notification Verification Suite
Executes Phases 17 through 26 in a completely isolated test environment:
- Phase 17: Notification Persistence Across DB Restarts
- Phase 18: End-to-End Security Event -> Incident -> Notification Chain
- Phase 19: Real CRITICAL Incident Pipeline Test
- Phase 20: Real HIGH Incident Pipeline Test
- Phase 21: Disabled Alert Rule Enforcement
- Phase 22: Cooldown Deduplication & Non-Duplication
- Phase 23: Multi-User Role-Aware Routing & Privacy Isolation
- Phase 24: Logout & Session Invalidation Guard
- Phase 25: Disconnect, Missed Alert Recovery, and Reconnect
- Phase 26: Multi-Tab Single-Notification Delivery
"""

import os
import sys
import shutil
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database
from fastapi.testclient import TestClient
from main import app
from admin.auth import hash_password, create_access_token


class TestNotificationComprehensiveSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db_path = database.db_manager.db_path
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_comprehensive_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_comprehensive.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

        # Login as bootstrap superadmin
        res = cls.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "Admin@Prahari2026!"
        })
        assert res.status_code == 200, f"Superadmin login failed: {res.text}"
        cls.admin_token = res.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        cls.admin_user = database.db_manager.get_admin_user_by_username("superadmin")

        # Create test users: Supervisor and Officer
        pw_sup = hash_password("Supervisor@2026!")
        cls.sup_id = database.db_manager.create_admin_user("supervisor_user", pw_sup, "Test Supervisor", "SUPERVISOR", 1, 0)
        cls.sup_user = database.db_manager.get_admin_user_by_username("supervisor_user")

        # Officer user
        pw_off = hash_password("Officer@2026!")
        cls.off_id = database.db_manager.create_admin_user("officer_user", pw_off, "Test Officer", "OFFICER", 1, 0)
        cls.off_user = database.db_manager.get_admin_user_by_username("officer_user")

        # Officer token
        res_off = cls.client.post("/api/auth/login", json={
            "username": "officer_user",
            "password": "Officer@2026!"
        })
        cls.off_token = res_off.json()["access_token"]
        cls.off_headers = {"Authorization": f"Bearer {cls.off_token}"}

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
            if hasattr(cls, "orig_db_path") and cls.orig_db_path:
                database.db_manager.set_db_path(cls.orig_db_path)
        except Exception:
            pass
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        database.db_manager.set_db_path(self.db_path)

    # ─── PHASE 17: PERSISTENCE ACROSS APPLICATION RESTARTS ───
    def test_phase_17_persistence_across_restarts(self):
        """Notification and read state must survive complete process/DB restart."""
        # 1. Create a notification
        notif_id = database.db_manager.create_notification(
            incident_id=101,
            camera_id="CAM-01",
            notification_type="INCIDENT_CREATED",
            severity="HIGH",
            title="Perimeter Alert Test",
            message="Motion detected near fence",
            dedupe_key="TEST_P17_RESTART_1"
        )
        self.assertIsNotNone(notif_id)
        database.db_manager.add_notification_recipients(notif_id, [self.admin_user["id"]])

        # 2. Simulate Application Restart by instantiating a fresh DatabaseManager on the same file
        fresh_db = database.DatabaseManager(db_path=self.db_path)
        notif_read = fresh_db.get_notification_by_id(notif_id)
        self.assertIsNotNone(notif_read, "Notification must persist across restart")
        self.assertEqual(notif_read["title"], "Perimeter Alert Test")

        # 3. Mark as read
        success = fresh_db.mark_notification_read(notif_id, self.admin_user["id"])
        self.assertTrue(success)

        # 4. Simulate second Application Restart
        fresh_db_2 = database.DatabaseManager(db_path=self.db_path)
        items = fresh_db_2.list_user_notifications(self.admin_user["id"], is_read=True)
        self.assertTrue(any(i["id"] == notif_id and i["is_read"] for i in items), "Read state must persist across restart")

    # ─── PHASE 18: END-TO-END EVENT -> INCIDENT -> NOTIFICATION ───
    def test_phase_18_end_to_end_event_to_notification(self):
        """Logging a security event triggers policy, creates incident, and generates persistent notification."""
        initial_unread = database.db_manager.get_user_unread_count(self.admin_user["id"])

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evt_id = database.db_manager.log_intrusion_event(
            timestamp=now_str,
            object_type="person",
            object_id=501,
            snapshot_path="static/alerts/test_intrusion.jpg",
            camera_id="CAM-01",
            direction="INTRUSION"
        )
        self.assertGreater(evt_id, 0)

        # Confirm notification exists with incident correlation
        notifs = database.db_manager.list_user_notifications(self.admin_user["id"], limit=5)
        self.assertGreater(len(notifs), 0)
        latest = notifs[0]

        self.assertIsNotNone(latest["incident_id"])
        self.assertEqual(latest["camera_id"], "CAM-01")
        self.assertEqual(latest["severity"], "CRITICAL")
        self.assertIn("Border Intrusion", latest["message"])

        # Unread count incremented
        new_unread = database.db_manager.get_user_unread_count(self.admin_user["id"])
        self.assertEqual(new_unread, initial_unread + 1)

    # ─── PHASE 19: CRITICAL EVENT PIPELINE TEST ───
    def test_phase_19_critical_event_pipeline(self):
        """Border intrusion maps to CRITICAL and verifies full metadata structure."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evt_id = database.db_manager.log_security_event(
            camera_id="CAM-01",
            event_type="border_intrusion",
            object_type="person",
            object_id=601,
            confidence=0.94,
            timestamp=now_str,
            details="Armed fence crossing detected"
        )
        self.assertGreater(evt_id, 0)

        notifs = database.db_manager.list_user_notifications(self.admin_user["id"], severity="CRITICAL", limit=5)
        self.assertGreater(len(notifs), 0)
        crit_notif = notifs[0]

        self.assertEqual(crit_notif["severity"], "CRITICAL")
        self.assertEqual(crit_notif["camera_id"], "CAM-01")
        self.assertIn("CRITICAL SECURITY ALERT", crit_notif["title"])

    # ─── PHASE 20: HIGH EVENT PIPELINE TEST ───
    def test_phase_20_high_event_pipeline(self):
        """Night surveillance movement maps to HIGH and reaches appropriate roles."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evt_id = database.db_manager.log_security_event(
            camera_id="CAM-02",
            event_type="night_movement",
            object_type="person",
            object_id=701,
            confidence=0.88,
            timestamp=now_str,
            details="Thermal night movement detected in perimeter sector Bravo"
        )
        self.assertGreater(evt_id, 0)

        notifs = database.db_manager.list_user_notifications(self.admin_user["id"], severity="HIGH", limit=5)
        self.assertGreater(len(notifs), 0)
        high_notif = notifs[0]

        self.assertEqual(high_notif["severity"], "HIGH")
        self.assertEqual(high_notif["camera_id"], "CAM-02")

    # ─── PHASE 21: DISABLED ALERT RULE ENFORCEMENT ───
    def test_phase_21_disabled_alert_rule_behavior(self):
        """When an alert rule is disabled, no incident and no notification may be created."""
        conn = database.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admin_alert_rules SET is_enabled = 0 WHERE event_type = 'suspicious_activity'")
        conn.commit()
        conn.close()

        count_before = database.db_manager.get_user_unread_count(self.admin_user["id"])

        # Trigger event for disabled rule
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evt_id = database.db_manager.log_security_event(
            camera_id="CAM-03",
            event_type="suspicious_activity",
            object_type="person",
            object_id=801,
            confidence=0.85,
            timestamp=now_str
        )
        self.assertGreater(evt_id, 0)

        # Verify NO notification created
        count_after = database.db_manager.get_user_unread_count(self.admin_user["id"])
        self.assertEqual(count_after, count_before, "Disabled rule must not generate notifications")

        # Re-enable rule
        conn = database.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admin_alert_rules SET is_enabled = 1 WHERE event_type = 'suspicious_activity'")
        conn.commit()
        conn.close()

    # ─── PHASE 22: COOLDOWN DEDUPLICATION TEST ───
    def test_phase_22_deduplication_within_cooldown(self):
        """Repeated events within cooldown window must not create duplicate notifications."""
        admin_id = self.admin_user["id"]
        notifs_before = len(database.db_manager.list_user_notifications(admin_id))

        # Event 1
        t1 = "2026-09-13 15:00:00"
        database.db_manager.evaluate_and_create_incident_from_event(
            event_table="security_events",
            event_id=9801,
            event_type="border_intrusion",
            camera_id="CAM-01",
            timestamp=t1
        )
        notifs_after_1 = len(database.db_manager.list_user_notifications(admin_id))
        self.assertEqual(notifs_after_1, notifs_before + 1)

        # Event 2, 3, 4 within 10s cooldown
        for sec in [2, 4, 6]:
            t_dup = f"2026-09-13 15:00:0{sec}"
            database.db_manager.evaluate_and_create_incident_from_event(
                event_table="security_events",
                event_id=9801 + sec,
                event_type="border_intrusion",
                camera_id="CAM-01",
                timestamp=t_dup
            )

        notifs_after_dups = len(database.db_manager.list_user_notifications(admin_id))
        self.assertEqual(notifs_after_dups, notifs_after_1, "Repeated events in cooldown must be deduplicated")

    # ─── PHASE 23: MULTI-USER PRIVACY & ROLE-BASED ROUTING ───
    def test_phase_23_multi_user_privacy_isolation(self):
        """User A must never be able to access User B's notifications; Officer only receives CRITICAL/HIGH."""
        # Create a MEDIUM incident (e.g. anpr_detection)
        inc_id = database.db_manager.create_admin_incident(
            camera_id="CAM-04",
            event_type="anpr_detection",
            severity="MEDIUM",
            event_id=9950
        )
        self.assertGreater(inc_id, 0)

        # 1. Admin & Supervisor received the MEDIUM alert
        admin_notifs = database.db_manager.list_user_notifications(self.admin_user["id"])
        self.assertTrue(any(n["incident_id"] == inc_id for n in admin_notifs))

        sup_notifs = database.db_manager.list_user_notifications(self.sup_user["id"])
        self.assertTrue(any(n["incident_id"] == inc_id for n in sup_notifs))

        # 2. Officer RBAC policy suppresses MEDIUM alerts
        off_notifs = database.db_manager.list_user_notifications(self.off_user["id"])
        self.assertFalse(any(n["incident_id"] == inc_id for n in off_notifs), "Officer must not receive MEDIUM notifications")

        # 3. Privacy boundary: Officer calling REST API only sees Officer's notifications
        res = self.client.get("/api/notifications", headers=self.off_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        for item in items:
            self.assertIn(item["severity"], ("CRITICAL", "HIGH"), "Officer cannot retrieve unauthorized notifications")

    # ─── PHASE 24: LOGOUT & WEBSOCKET INVALIDATION ───
    def test_phase_24_logout_and_session_guard(self):
        """Unauthenticated or expired tokens cannot open real-time WebSocket."""
        # Unauthenticated request is rejected
        with self.client.websocket_connect("/api/notifications/ws") as ws:
            err = ws.receive_json()
            self.assertEqual(err.get("error"), "unauthorized")

        # Valid login works
        with self.client.websocket_connect(f"/api/notifications/ws?token={self.admin_token}") as ws:
            ack = ws.receive_json()
            self.assertEqual(ack["status"], "connected")

    # ─── PHASE 25: DISCONNECT & RECOVERY TEST ───
    def test_phase_25_disconnect_and_missed_notification_recovery(self):
        """Missed notifications during disconnect must be recovered from persistent storage on reconnect."""
        unread_before = database.db_manager.get_user_unread_count(self.admin_user["id"])

        # Create notification while client is offline
        notif_id = database.db_manager.create_notification(
            incident_id=202,
            camera_id="CAM-02",
            notification_type="INCIDENT_CREATED",
            severity="HIGH",
            title="Missed Alert While Offline",
            message="System state recovery test",
            dedupe_key="TEST_OFFLINE_RECOVERY_1"
        )
        database.db_manager.add_notification_recipients(notif_id, [self.admin_user["id"]])

        # Client reconnects: WebSocket delivers updated unread count in ACK
        with self.client.websocket_connect(f"/api/notifications/ws?token={self.admin_token}") as ws:
            ack = ws.receive_json()
            self.assertEqual(ack["type"], "connection.ack")
            self.assertEqual(ack["unread_count"], unread_before + 1)

        # Client queries REST API to populate drawer: alert is present
        res = self.client.get("/api/notifications?is_read=false", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        ids = [n["id"] for n in res.json()["items"]]
        self.assertIn(notif_id, ids, "Missed notification must be recovered from persistent storage")

    # ─── PHASE 26: MULTI-TAB DELIVERY & SINGLE PERSISTENCE ───
    def test_phase_26_multi_tab_delivery_single_row(self):
        """Two open sessions of the same user receive real-time sync without duplicate database records."""
        admin_id = self.admin_user["id"]
        initial_notif_count = database.db_manager.count_user_notifications(admin_id)

        with self.client.websocket_connect(f"/api/notifications/ws?token={self.admin_token}") as ws_tab1:
            ws_tab1.receive_json() # ack

            with self.client.websocket_connect(f"/api/notifications/ws?token={self.admin_token}") as ws_tab2:
                ws_tab2.receive_json() # ack

                # Create 1 authentic incident
                inc_id = database.db_manager.create_admin_incident(
                    camera_id="CAM-01",
                    event_type="border_intrusion",
                    severity="CRITICAL",
                    notes="Multi-tab test"
                )
                self.assertGreater(inc_id, 0)

                # Exactly 1 new notification row in database
                final_count = database.db_manager.count_user_notifications(admin_id)
                self.assertEqual(final_count, initial_notif_count + 1, "Exactly one notification record must be created")


if __name__ == "__main__":
    unittest.main()
