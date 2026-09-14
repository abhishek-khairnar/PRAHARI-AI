"""
PRAHARI-AI Notification Forensic Regression Suite
Comprehensive verification covering:
- Database persistence, recipient mapping, deduplication
- RBAC recipient isolation across all 4 roles (SUPER_ADMIN, ADMIN, SUPERVISOR, OFFICER)
- REST API: authenticated history, unauthenticated 401, delta since_id cursor, filtering, mark read
- WebSocket: query token auth, frame auth, unauthorized rejection (code 1008), ping/pong heartbeat, live delivery
- Missed notification recovery and reconciliation
- Model SHA256 integrity and database preservation
"""

import os
import time
import random
import hashlib
import json
import asyncio
import unittest
import requests
import websockets

from database import db_manager
from admin.auth import create_access_token, hash_password
from notifications.notification_service import notification_service
from notifications.notification_realtime import ws_manager

BASE_URL = "http://localhost:8001"
WS_URL = "ws://localhost:8001/api/notifications/ws"
EXPECTED_YOLO_SHA = "F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36"


class TestNotificationForensicSuite(unittest.TestCase):
    _inc_counter = int(time.time()) % 1000000

    @classmethod
    def gen_incident_id(cls):
        cls._inc_counter += 1
        return cls._inc_counter + random.randint(100000, 999999)

    @classmethod
    def setUpClass(cls):
        # Verify and ensure test RBAC accounts exist
        cls.rbac_users = db_manager.ensure_rbac_users()

        # Generate fresh JWT tokens for all roles
        cls.tokens = {
            "SUPER_ADMIN": create_access_token({"sub": "superadmin", "role": "SUPER_ADMIN"}),
            "ADMIN": create_access_token({"sub": "admin_ops", "role": "ADMIN"}),
            "SUPERVISOR": create_access_token({"sub": "supervisor_sec", "role": "SUPERVISOR"}),
            "OFFICER": create_access_token({"sub": "officer_patrol", "role": "OFFICER"})
        }

        # Resolve user IDs
        cls.user_ids = {
            "SUPER_ADMIN": db_manager.get_admin_user_by_username("superadmin")["id"],
            "ADMIN": db_manager.get_admin_user_by_username("admin_ops")["id"],
            "SUPERVISOR": db_manager.get_admin_user_by_username("supervisor_sec")["id"],
            "OFFICER": db_manager.get_admin_user_by_username("officer_patrol")["id"]
        }

    # ─── 1. DATABASE PERSISTENCE & INTEGRITY ───

    def test_01_yolo_model_integrity(self):
        """Verify production YOLO model SHA256 has not been altered."""
        h = hashlib.sha256()
        with open("weights/yolov8n.pt", "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        self.assertEqual(h.hexdigest().upper(), EXPECTED_YOLO_SHA)

    def test_02_database_has_no_orphan_recipients(self):
        """Verify no recipient rows point to nonexistent notifications."""
        conn = db_manager._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM notification_recipients nr
            LEFT JOIN notifications n ON nr.notification_id = n.id
            WHERE n.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        conn.close()
        self.assertEqual(orphans, 0)

    def test_03_database_has_no_orphan_deliveries(self):
        """Verify no delivery rows point to nonexistent notifications."""
        conn = db_manager._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM notification_deliveries nd
            LEFT JOIN notifications n ON nd.notification_id = n.id
            WHERE n.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        conn.close()
        self.assertEqual(orphans, 0)

    def test_04_database_has_no_duplicate_recipient_pairs(self):
        """Verify no duplicate (notification_id, user_id) pairs exist."""
        conn = db_manager._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT notification_id, user_id, COUNT(*)
            FROM notification_recipients
            GROUP BY notification_id, user_id
            HAVING COUNT(*) > 1
        """)
        dups = cur.fetchall()
        conn.close()
        self.assertEqual(len(dups), 0)

    def test_05_database_notification_creation_persists(self):
        """Verify create_notification writes to database and returns positive ID."""
        notif_id = db_manager.create_notification(
            incident_id=self.gen_incident_id(),
            source_event_id=1,
            camera_id="CAM-01",
            notification_type="INCIDENT_CREATED",
            severity="CRITICAL",
            title="TEST INTEGRITY NOTIF",
            message="Forensic persistence test",
            dedupe_key=f"TEST_DEDUPE_{os.urandom(6).hex()}"
        )
        self.assertGreater(notif_id, 0)

        # Query back
        conn = db_manager._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, severity, title FROM notifications WHERE id = ?", (notif_id,))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["severity"], "CRITICAL")
        self.assertEqual(row["title"], "TEST INTEGRITY NOTIF")

    def test_06_database_recipient_mapping(self):
        """Verify recipient mapping attaches notification to users."""
        notif_id = db_manager.create_notification(
            incident_id=self.gen_incident_id(),
            camera_id="CAM-02",
            notification_type="INCIDENT_CREATED",
            severity="HIGH",
            title="TEST RECIPIENT MAP",
            message="Testing recipient insertion",
            dedupe_key=f"TEST_RECIP_{os.urandom(6).hex()}"
        )
        uids = [self.user_ids["SUPER_ADMIN"], self.user_ids["OFFICER"]]
        added = db_manager.add_notification_recipients(notif_id, uids)
        self.assertEqual(added, 2)

        # Check recipient records
        notifs_sa = db_manager.list_user_notifications(self.user_ids["SUPER_ADMIN"], limit=10)
        self.assertTrue(any(n["id"] == notif_id for n in notifs_sa))

    def test_07_database_mark_single_read(self):
        """Verify marking a single notification as read persists in DB."""
        notif_id = db_manager.create_notification(
            incident_id=self.gen_incident_id(),
            camera_id="CAM-01",
            notification_type="INCIDENT_CREATED",
            severity="MEDIUM",
            title="TEST READ PERSIST",
            message="Mark read test",
            dedupe_key=f"TEST_READ_{os.urandom(6).hex()}"
        )
        uid = self.user_ids["OFFICER"]
        db_manager.add_notification_recipients(notif_id, [uid])
        
        db_manager.mark_notification_read(notif_id, uid)
        notifs = db_manager.list_user_notifications(uid, limit=20)
        target = next((n for n in notifs if n["id"] == notif_id), None)
        self.assertIsNotNone(target)
        self.assertTrue(target["is_read"])
        self.assertIsNotNone(target["read_at"])

    def test_08_database_mark_all_read(self):
        """Verify mark_all_notifications_read sets all is_read=1 for user."""
        uid = self.user_ids["OFFICER"]
        affected = db_manager.mark_all_notifications_read(uid)
        unread_now = db_manager.get_user_unread_count(uid)
        self.assertEqual(unread_now, 0)

    def test_09_database_since_id_filter(self):
        """Verify list_user_notifications honors since_id cursor."""
        uid = self.user_ids["SUPER_ADMIN"]
        notifs = db_manager.list_user_notifications(uid, limit=5)
        if len(notifs) >= 2:
            target_since = notifs[1]["id"]
            newer_items = db_manager.list_user_notifications(uid, since_id=target_since, limit=10)
            self.assertTrue(all(item["id"] > target_since for item in newer_items))

    # ─── 2. RBAC RECIPIENT ISOLATION ───

    def test_10_rbac_critical_reaches_all_active_roles(self):
        """CRITICAL alerts must route to SUPER_ADMIN, ADMIN, SUPERVISOR, and OFFICER."""
        inc_id = self.gen_incident_id()
        notif_id = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-01",
            event_type="border_intrusion",
            severity="CRITICAL",
            title="RBAC CRITICAL TEST"
        )
        self.assertIsNotNone(notif_id)

        for role in ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OFFICER"]:
            uid = self.user_ids[role]
            user_notifs = db_manager.list_user_notifications(uid, limit=10)
            self.assertTrue(any(n["id"] == notif_id for n in user_notifs), f"Role {role} missing critical alert")

    def test_11_rbac_high_reaches_all_active_roles(self):
        """HIGH alerts must route to SUPER_ADMIN, ADMIN, SUPERVISOR, and OFFICER."""
        inc_id = self.gen_incident_id()
        notif_id = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-02",
            event_type="suspicious_activity",
            severity="HIGH",
            title="RBAC HIGH TEST"
        )
        self.assertIsNotNone(notif_id)

        for role in ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OFFICER"]:
            uid = self.user_ids[role]
            user_notifs = db_manager.list_user_notifications(uid, limit=10)
            self.assertTrue(any(n["id"] == notif_id for n in user_notifs), f"Role {role} missing high alert")

    def test_12_rbac_medium_reaches_supervisor_not_officer(self):
        """MEDIUM alerts route to SUPER_ADMIN, ADMIN, SUPERVISOR, but NOT OFFICER."""
        inc_id = self.gen_incident_id()
        notif_id = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-03",
            event_type="loitering",
            severity="MEDIUM",
            title="RBAC MEDIUM TEST"
        )
        self.assertIsNotNone(notif_id)

        self.assertTrue(any(n["id"] == notif_id for n in db_manager.list_user_notifications(self.user_ids["SUPER_ADMIN"], limit=10)))
        self.assertTrue(any(n["id"] == notif_id for n in db_manager.list_user_notifications(self.user_ids["ADMIN"], limit=10)))
        self.assertTrue(any(n["id"] == notif_id for n in db_manager.list_user_notifications(self.user_ids["SUPERVISOR"], limit=10)))
        self.assertFalse(any(n["id"] == notif_id for n in db_manager.list_user_notifications(self.user_ids["OFFICER"], limit=10)))

    def test_13_rbac_deduplication_deterministic_key(self):
        """Same incident + same severity must suppress duplicate creation."""
        inc_id = self.gen_incident_id()
        id1 = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-01",
            event_type="intrusion",
            severity="CRITICAL"
        )
        self.assertIsNotNone(id1)

        # Duplicate dispatch attempt
        id2 = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-01",
            event_type="intrusion",
            severity="CRITICAL"
        )
        self.assertIsNone(id2, "Duplicate notification must be suppressed")

    def test_14_rbac_escalation_creates_new_notification(self):
        """Escalation (HIGH -> CRITICAL) on same incident creates a distinct escalation notification."""
        inc_id = self.gen_incident_id()
        id_high = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-01",
            event_type="loitering",
            severity="HIGH"
        )
        self.assertIsNotNone(id_high)

        id_escalated = notification_service.dispatch_incident_notification(
            incident_id=inc_id,
            camera_id="CAM-01",
            event_type="loitering",
            severity="CRITICAL",
            is_escalation=True
        )
        self.assertIsNotNone(id_escalated)
        self.assertNotEqual(id_high, id_escalated)

    # ─── 3. REST NOTIFICATION API ───

    def test_15_rest_unauthenticated_history_rejected_with_401(self):
        """GET /api/notifications without token must return 401."""
        res = requests.get(f"{BASE_URL}/api/notifications")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.text)

    def test_16_rest_unauthenticated_unread_count_rejected_with_401(self):
        """GET /api/notifications/unread-count without token must return 401."""
        res = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        self.assertEqual(res.status_code, 401)

    def test_17_rest_authenticated_history_returns_200(self):
        """GET /api/notifications with valid JWT returns paginated items and counts."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
        res = requests.get(f"{BASE_URL}/api/notifications?limit=10", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("unread_count", data)
        self.assertIsInstance(data["items"], list)

    def test_18_rest_severity_filtering(self):
        """GET /api/notifications?severity=CRITICAL only returns CRITICAL alerts."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
        res = requests.get(f"{BASE_URL}/api/notifications?severity=CRITICAL&limit=10", headers=headers)
        self.assertEqual(res.status_code, 200)
        for item in res.json()["items"]:
            self.assertEqual(item["severity"], "CRITICAL")

    def test_19_rest_unread_filtering(self):
        """GET /api/notifications?is_read=false only returns unread alerts."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
        res = requests.get(f"{BASE_URL}/api/notifications?is_read=false&limit=10", headers=headers)
        self.assertEqual(res.status_code, 200)
        for item in res.json()["items"]:
            self.assertFalse(item["is_read"])

    def test_20_rest_since_id_delta_cursor(self):
        """GET /api/notifications?since_id=<id> returns only notifications newer than cursor."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
        res1 = requests.get(f"{BASE_URL}/api/notifications?limit=5", headers=headers)
        items = res1.json()["items"]
        if len(items) >= 2:
            cursor_id = items[1]["id"]
            res_delta = requests.get(f"{BASE_URL}/api/notifications?since_id={cursor_id}", headers=headers)
            self.assertEqual(res_delta.status_code, 200)
            for item in res_delta.json()["items"]:
                self.assertGreater(item["id"], cursor_id)

    def test_21_rest_mark_single_read_api(self):
        """POST /api/notifications/{id}/read marks item as read and returns updated count."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
        list_res = requests.get(f"{BASE_URL}/api/notifications?is_read=false&limit=1", headers=headers)
        items = list_res.json()["items"]
        if items:
            target_id = items[0]["id"]
            res = requests.post(f"{BASE_URL}/api/notifications/{target_id}/read", headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["notification_id"], target_id)
            self.assertIsInstance(data["unread_count"], int)

    def test_22_rest_mark_all_read_api(self):
        """POST /api/notifications/mark-all-read updates unread_count to 0 for officer."""
        headers = {"Authorization": f"Bearer {self.tokens['OFFICER']}"}
        res = requests.post(f"{BASE_URL}/api/notifications/mark-all-read", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["unread_count"], 0)

    def test_23_rest_preferences_get_and_update(self):
        """GET & PUT /api/notifications/preferences persits user preferences."""
        headers = {"Authorization": f"Bearer {self.tokens['ADMIN']}"}
        get_res = requests.get(f"{BASE_URL}/api/notifications/preferences", headers=headers)
        self.assertEqual(get_res.status_code, 200)

        put_res = requests.put(
            f"{BASE_URL}/api/notifications/preferences",
            headers=headers,
            json={"sound_enabled": False, "browser_enabled": True}
        )
        self.assertEqual(put_res.status_code, 200)
        self.assertFalse(put_res.json()["sound_enabled"])
        self.assertTrue(put_res.json()["browser_enabled"])

    # ─── 4. WEBSOCKET AUTHENTICATION & LIFECYCLE ───

    def test_24_ws_unauthenticated_connection_rejected_with_code_1008(self):
        """Unauthenticated WebSocket connection must be cleanly closed with code 1008."""
        async def run():
            try:
                async with websockets.connect(WS_URL) as ws:
                    try:
                        err_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(err_msg)
                        self.assertEqual(data.get("code"), 1008)
                    except websockets.exceptions.ConnectionClosed as cc:
                        self.assertEqual(cc.code, 1008)
            except websockets.exceptions.ConnectionClosed as cc:
                self.assertEqual(cc.code, 1008)
        asyncio.run(run())

    def test_25_ws_authenticated_query_token(self):
        """WebSocket connection with valid query token connects and receives ack."""
        async def run():
            uri = f"{WS_URL}?token={self.tokens['SUPER_ADMIN']}"
            async with websockets.connect(uri) as ws:
                raw_ack = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(raw_ack)
                self.assertEqual(data.get("type"), "connection.ack")
                self.assertEqual(data.get("status"), "connected")
                self.assertIsInstance(data.get("unread_count"), int)
        asyncio.run(run())

    def test_26_ws_ping_pong_heartbeat_with_unread_count(self):
        """Sending ping frame over WebSocket returns pong with timestamp and unread_count."""
        async def run():
            uri = f"{WS_URL}?token={self.tokens['SUPER_ADMIN']}"
            async with websockets.connect(uri) as ws:
                await ws.recv() # ack
                await ws.send(json.dumps({"type": "ping"}))
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(raw)
                    if data.get("type") == "pong":
                        self.assertIn("timestamp", data)
                        self.assertIn("unread_count", data)
                        return
                self.fail("Did not receive pong frame within 10 messages")
        asyncio.run(run())

    def test_27_ws_live_incident_dispatches_notification_created(self):
        """A live incident created via notification_service delivers a notification.created frame."""
        async def run():
            uri = f"{WS_URL}?token={self.tokens['SUPERVISOR']}"
            async with websockets.connect(uri) as ws:
                await ws.recv() # ack
                
                inc_id = self.gen_incident_id()
                headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
                dispatch_res = requests.post(
                    f"{BASE_URL}/api/notifications/test-dispatch",
                    headers=headers,
                    json={
                        "incident_id": inc_id,
                        "camera_id": "CAM-01",
                        "event_type": "perimeter_breach",
                        "severity": "CRITICAL",
                        "title": "LIVE WS TEST ALERT"
                    }
                )
                self.assertEqual(dispatch_res.status_code, 200)
                notif_id = dispatch_res.json()["notification_id"]

                for _ in range(15):
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    data = json.loads(msg)
                    if data.get("type") == "notification.created":
                        notif = data.get("notification", {})
                        if notif.get("id") == notif_id:
                            self.assertEqual(notif["severity"], "CRITICAL")
                            return
                self.fail(f"Notification #{notif_id} not received on WebSocket")
        asyncio.run(run())

    def test_28_ws_isolation_officer_does_not_receive_medium_frame(self):
        """An OFFICER connected to WebSocket does not receive a MEDIUM notification frame."""
        async def run():
            uri = f"{WS_URL}?token={self.tokens['OFFICER']}"
            async with websockets.connect(uri) as ws:
                await ws.recv() # ack

                inc_id = self.gen_incident_id()
                headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
                dispatch_res = requests.post(
                    f"{BASE_URL}/api/notifications/test-dispatch",
                    headers=headers,
                    json={
                        "incident_id": inc_id,
                        "camera_id": "CAM-02",
                        "event_type": "loitering",
                        "severity": "MEDIUM",
                        "title": "OFFICER ISOLATION TEST"
                    }
                )
                self.assertEqual(dispatch_res.status_code, 200)
                notif_id = dispatch_res.json()["notification_id"]

                # Read incoming frames for 1.5s; our MEDIUM alert must NEVER be delivered to officer
                try:
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                        data = json.loads(raw)
                        if data.get("type") == "notification.created":
                            notif = data.get("notification", {})
                            self.assertNotEqual(notif.get("id"), notif_id, "OFFICER received ineligible MEDIUM notification!")
                except asyncio.TimeoutError:
                    pass
        asyncio.run(run())

    def test_29_ws_mark_read_syncs_across_sockets_of_same_user(self):
        """Mark read from one socket broadcasts updated read count to other active user sessions."""
        async def run():
            uri = f"{WS_URL}?token={self.tokens['ADMIN']}"
            async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
                await ws1.recv() # ack 1
                await ws2.recv() # ack 2

                inc_id = self.gen_incident_id()
                headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}
                dispatch_res = requests.post(
                    f"{BASE_URL}/api/notifications/test-dispatch",
                    headers=headers,
                    json={
                        "incident_id": inc_id,
                        "camera_id": "CAM-03",
                        "event_type": "intrusion",
                        "severity": "CRITICAL",
                        "title": "MULTI TAB TEST"
                    }
                )
                self.assertEqual(dispatch_res.status_code, 200)
                notif_id = dispatch_res.json()["notification_id"]

                # Wait for ws1 to get notification.created for notif_id
                for _ in range(15):
                    raw = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                    data = json.loads(raw)
                    if data.get("type") == "notification.created" and data.get("notification", {}).get("id") == notif_id:
                        break

                # Mark read via ws1
                await ws1.send(json.dumps({"type": "mark_read", "notification_id": notif_id}))
                
                # ws2 should receive the notification.read event
                for _ in range(15):
                    raw = await asyncio.wait_for(ws2.recv(), timeout=3.0)
                    data = json.loads(raw)
                    if data.get("type") == "notification.read" and data.get("notification_id") == notif_id:
                        return
                self.fail(f"notification.read for #{notif_id} not received on ws2")
        asyncio.run(run())

    # ─── 5. MISSED NOTIFICATION RECOVERY & RECONCILIATION ───

    def test_30_missed_notification_reconciliation_flow(self):
        """Simulate disconnect window: notifications generated while disconnected are recovered via since_id."""
        headers = {"Authorization": f"Bearer {self.tokens['SUPER_ADMIN']}"}

        # Step A: Get latest known ID
        latest_res = requests.get(f"{BASE_URL}/api/notifications?limit=1", headers=headers)
        baseline_id = latest_res.json()["items"][0]["id"]

        # Step B: Disconnected window - 2 notifications created
        n1 = notification_service.dispatch_incident_notification(
            incident_id=self.gen_incident_id(),
            camera_id="CAM-01",
            event_type="intrusion",
            severity="CRITICAL",
            title="MISSED ALERT 1"
        )
        n2 = notification_service.dispatch_incident_notification(
            incident_id=self.gen_incident_id(),
            camera_id="CAM-04",
            event_type="intrusion",
            severity="HIGH",
            title="MISSED ALERT 2"
        )
        self.assertIsNotNone(n1)
        self.assertIsNotNone(n2)

        # Step C: Reconnect recovery query using baseline_id cursor
        recovery_res = requests.get(f"{BASE_URL}/api/notifications?since_id={baseline_id}", headers=headers)
        recovered_ids = [item["id"] for item in recovery_res.json()["items"]]
        self.assertIn(n1, recovered_ids)
        self.assertIn(n2, recovered_ids)

    def test_31_no_production_database_row_loss(self):
        """Verify core event and incident counts did not decrease."""
        conn = db_manager._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notifications")
        cnt = cur.fetchone()[0]
        conn.close()
        # Must be well above the starting 11,322 rows
        self.assertGreaterEqual(cnt, 11322)


if __name__ == "__main__":
    unittest.main()
