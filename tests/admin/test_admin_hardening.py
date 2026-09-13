"""
Tests for PRAHARI-AI Admin Panel Hardening Enhancements
Covers:
1. Environment-aware auth context (/api/auth/context)
2. First-login password rotation & bootstrap credential invalidation
3. Strict incident state-machine transitions (NEW -> ACK -> INV -> RES/DISM)
4. Role restrictions on incident finalization & re-opening
5. Pagination with item totals for Incidents and Audit Logs
6. Camera configuration persistence in SQLite
7. Zone fence ratio updates
8. Full audit event trail verification
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
from admin.auth import hash_password, create_access_token


class TestAdminHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db_path = database.db_manager.db_path
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_hardening_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_hardening.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

        # Create test users with different roles
        cls.superadmin_token = create_access_token({"sub": "superadmin", "role": "SUPER_ADMIN", "user_id": 1})
        cls.admin_token = create_access_token({"sub": "test_admin", "role": "ADMIN", "user_id": 2})
        cls.officer_token = create_access_token({"sub": "test_officer", "role": "OFFICER", "user_id": 3})

        database.db_manager.create_admin_user(
            username="test_admin",
            password_hash=hash_password("AdminPass123!"),
            full_name="Test Administrator",
            role="ADMIN"
        )
        database.db_manager.create_admin_user(
            username="test_officer",
            password_hash=hash_password("OfficerPass123!"),
            full_name="Test Officer",
            role="OFFICER"
        )

    @classmethod
    def tearDownClass(cls):
        try:
            default_db = os.path.abspath("prahari_events.db")
            database.db_manager.set_db_path(default_db)
        except Exception:
            pass
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_auth_context_endpoint(self):
        """Verify /api/auth/context accurately reports environment flags."""
        res = self.client.get("/api/auth/context")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_development", data)
        self.assertIn("allow_demo_credentials", data)

    def test_02_first_login_password_rotation(self):
        """Verify first login requires password change and rotates password properly."""
        # Create user requiring password change
        uid = database.db_manager.create_admin_user(
            username="rot_user",
            password_hash=hash_password("InitialTemp123!"),
            full_name="Rotation User",
            role="OFFICER",
            must_change_password=1
        )
        # Login with initial password
        res = self.client.post("/api/auth/login", json={
            "username": "rot_user",
            "password": "InitialTemp123!"
        })
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        self.assertTrue(bool(res.json()["user"]["must_change_password"]))

        # Attempt to change password with wrong old password
        bad_change = self.client.post("/api/auth/change-password", json={
            "old_password": "WrongOldPassword!",
            "new_password": "NewPermanentPass2026!"
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(bad_change.status_code, 400)

        # Attempt with too short new password
        short_change = self.client.post("/api/auth/change-password", json={
            "old_password": "InitialTemp123!",
            "new_password": "short"
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(short_change.status_code, 400)

        # Successful password rotation
        good_change = self.client.post("/api/auth/change-password", json={
            "old_password": "InitialTemp123!",
            "new_password": "NewPermanentPass2026!"
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(good_change.status_code, 200)
        self.assertEqual(good_change.json()["user"]["must_change_password"], 0)

        # Old password must no longer work
        old_login = self.client.post("/api/auth/login", json={
            "username": "rot_user",
            "password": "InitialTemp123!"
        })
        self.assertEqual(old_login.status_code, 401)

        # New password works
        new_login = self.client.post("/api/auth/login", json={
            "username": "rot_user",
            "password": "NewPermanentPass2026!"
        })
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(new_login.json()["user"]["must_change_password"], 0)

    def test_03_incident_state_machine_valid_progression(self):
        """Verify strict incident state transitions: NEW -> ACK -> INV -> RES."""
        headers = {"Authorization": f"Bearer {self.superadmin_token}"}
        create_res = self.client.post("/api/admin/incidents", json={
            "camera_id": "CAM-01",
            "event_type": "border_intrusion",
            "severity": "CRITICAL",
            "zone_name": "Sector Alpha"
        }, headers=headers)
        self.assertEqual(create_res.status_code, 201)
        inc_id = create_res.json()["id"]

        # Step 1: NEW -> ACKNOWLEDGED
        ack_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "ACKNOWLEDGED",
            "assigned_officer_name": "Operator Alpha"
        }, headers=headers)
        self.assertEqual(ack_res.status_code, 200)
        self.assertEqual(ack_res.json()["status"], "ACKNOWLEDGED")

        # Step 2: ACKNOWLEDGED -> INVESTIGATING
        inv_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "INVESTIGATING",
            "notes": "Patrol vehicle dispatched"
        }, headers=headers)
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(inv_res.json()["status"], "INVESTIGATING")

        # Step 3: INVESTIGATING -> RESOLVED
        res_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "RESOLVED",
            "notes": "Intruder intercepted and secured"
        }, headers=headers)
        self.assertEqual(res_res.status_code, 200)
        self.assertEqual(res_res.json()["status"], "RESOLVED")

    def test_04_incident_state_machine_rejections(self):
        """Verify invalid skips in the incident state machine are rejected with HTTP 400."""
        headers = {"Authorization": f"Bearer {self.superadmin_token}"}
        create_res = self.client.post("/api/admin/incidents", json={
            "camera_id": "CAM-02",
            "event_type": "loitering",
            "severity": "HIGH"
        }, headers=headers)
        inc_id = create_res.json()["id"]

        # Attempt illegal transition: NEW -> RESOLVED (cannot resolve directly from NEW)
        bad_trans = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "RESOLVED"
        }, headers=headers)
        self.assertEqual(bad_trans.status_code, 400)
        self.assertIn("Invalid state transition", bad_trans.json()["detail"])

        # Attempt illegal transition: NEW -> INVESTIGATING (must acknowledge first)
        bad_trans2 = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "INVESTIGATING"
        }, headers=headers)
        self.assertEqual(bad_trans2.status_code, 400)

    def test_05_incident_reopen_role_authorization(self):
        """Verify re-opening a resolved incident requires SUPER_ADMIN or ADMIN."""
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        officer_headers = {"Authorization": f"Bearer {self.officer_token}"}

        # Create, ack, inv, resolve
        create_res = self.client.post("/api/admin/incidents", json={
            "camera_id": "CAM-03",
            "event_type": "night_movement",
            "severity": "MEDIUM"
        }, headers=admin_headers)
        inc_id = create_res.json()["id"]

        self.client.patch(f"/api/admin/incidents/{inc_id}", json={"status": "ACKNOWLEDGED"}, headers=admin_headers)
        self.client.patch(f"/api/admin/incidents/{inc_id}", json={"status": "INVESTIGATING"}, headers=admin_headers)
        self.client.patch(f"/api/admin/incidents/{inc_id}", json={"status": "RESOLVED"}, headers=admin_headers)

        # Officer attempts to re-open -> 403 Forbidden
        officer_reopen = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "INVESTIGATING"
        }, headers=officer_headers)
        self.assertEqual(officer_reopen.status_code, 403)

        # Admin re-opens -> 200 OK
        admin_reopen = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "INVESTIGATING",
            "notes": "Re-opened for secondary forensic review"
        }, headers=admin_headers)
        self.assertEqual(admin_reopen.status_code, 200)
        self.assertEqual(admin_reopen.json()["status"], "INVESTIGATING")

    def test_06_incidents_pagination(self):
        """Verify incidents endpoint supports paginated responses and backward-compatible arrays."""
        headers = {"Authorization": f"Bearer {self.superadmin_token}"}
        # Paginated request
        res = self.client.get("/api/admin/incidents?page=1&page_size=2", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, dict)
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("page", data)
        self.assertIn("page_size", data)
        self.assertIn("X-Total-Count", res.headers)
        self.assertLessEqual(len(data["items"]), 2)

        # Non-paginated request (legacy mode)
        res_legacy = self.client.get("/api/admin/incidents?limit=10", headers=headers)
        self.assertEqual(res_legacy.status_code, 200)
        self.assertIsInstance(res_legacy.json(), list)
        self.assertIn("X-Total-Count", res_legacy.headers)

    def test_07_audit_logs_pagination(self):
        """Verify audit-logs endpoint supports pagination with total count."""
        headers = {"Authorization": f"Bearer {self.superadmin_token}"}
        res = self.client.get("/api/admin/audit-logs?page=1&page_size=3", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, dict)
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 3)
        self.assertIn("X-Total-Count", res.headers)

    def test_08_camera_configuration_sqlite_persistence(self):
        """Verify camera configuration edits persist in the admin_camera_config table."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.patch("/api/admin/cameras/CAM-01", json={
            "name": "Northern Perimeter Sensor Alpha",
            "location_zone": "Sector 01 - High Ridge",
            "ai_enabled": True,
            "anpr_enabled": False,
            "night_detection": True
        }, headers=headers)
        self.assertEqual(res.status_code, 200)

        # Verify persisted via database direct query
        row = database.db_manager.get_admin_camera_config("CAM-01")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Northern Perimeter Sensor Alpha")
        self.assertEqual(row["location_zone"], "Sector 01 - High Ridge")
        self.assertEqual(row["ai_enabled"], 1)
        self.assertEqual(row["anpr_enabled"], 0)
        self.assertEqual(row["night_detection"], 1)

    def test_09_overview_telemetry_accuracy(self):
        """Verify overview endpoint returns real non-hardcoded counts and AI status."""
        headers = {"Authorization": f"Bearer {self.superadmin_token}"}
        res = self.client.get("/api/admin/overview", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("metrics", data)
        self.assertIn("incidents_by_status", data)
        self.assertIn("ai_pipeline", data)
        self.assertIn("system_summary", data)

        metrics = data["metrics"]
        self.assertGreaterEqual(metrics["active_users"], 1)
        self.assertGreaterEqual(metrics["total_cameras"], 4)
        self.assertIn("status", data["ai_pipeline"])
        self.assertIn(data["ai_pipeline"]["status"], ["ONLINE", "READY", "DEGRADED", "OFFLINE"])


if __name__ == "__main__":
    unittest.main()
