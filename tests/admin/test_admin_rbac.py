"""
Tests for Admin Panel Role-Based Access Control (RBAC)
Tests authorization matrix across:
- SUPER_ADMIN: Full access
- ADMIN: User management (except creating SUPER_ADMIN), configuration
- SUPERVISOR: Incident management and monitoring
- OFFICER: Limited operational incident updates
- Anonymous: Denied by default (401)
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


class TestAdminRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_rbac_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_rbac.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

        pw_hash = hash_password("TestPass2026!")

        # Create one user for each test role
        database.db_manager.create_admin_user("admin_user", pw_hash, "Admin User", role="ADMIN")
        database.db_manager.create_admin_user("supervisor_user", pw_hash, "Supervisor User", role="SUPERVISOR")
        database.db_manager.create_admin_user("officer_user", pw_hash, "Officer User", role="OFFICER")

        # Obtain JWT tokens for each role
        cls.tokens = {}
        for username, password in [
            ("superadmin", "Admin@Prahari2026!"),
            ("admin_user", "TestPass2026!"),
            ("supervisor_user", "TestPass2026!"),
            ("officer_user", "TestPass2026!")
        ]:
            res = cls.client.post("/api/auth/login", json={"username": username, "password": password})
            cls.tokens[username] = res.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        # Re-assert DB path in case another test touched it
        database.db_manager.set_db_path(self.db_path)

    def _headers(self, username: str):
        return {"Authorization": f"Bearer {self.tokens[username]}"}

    def test_anonymous_access_denied(self):
        """All admin routes must deny unauthenticated access with 401."""
        endpoints = [
            ("GET", "/api/admin/overview"),
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/cameras"),
            ("GET", "/api/admin/zones"),
            ("GET", "/api/admin/alert-rules"),
            ("GET", "/api/admin/incidents"),
            ("GET", "/api/admin/system-health"),
            ("GET", "/api/admin/audit-logs"),
        ]
        for method, ep in endpoints:
            if method == "GET":
                res = self.client.get(ep)
            self.assertEqual(res.status_code, 401, f"Failed for {method} {ep}")

    def test_superadmin_has_full_access(self):
        """SUPER_ADMIN can access all admin endpoints."""
        headers = self._headers("superadmin")
        self.assertEqual(self.client.get("/api/admin/overview", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/users", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/cameras", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/zones", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/alert-rules", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/incidents", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/system-health", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/audit-logs", headers=headers).status_code, 200)

    def test_admin_cannot_create_superadmin(self):
        """ADMIN cannot create another SUPER_ADMIN account."""
        headers = self._headers("admin_user")
        res = self.client.post("/api/admin/users", json={
            "username": "escalated_admin",
            "password": "Password123!",
            "full_name": "Privilege Escalation Test",
            "role": "SUPER_ADMIN"
        }, headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Super Admin", res.json()["detail"])

    def test_admin_can_create_operational_user(self):
        """ADMIN can create an OFFICER or SUPERVISOR user."""
        headers = self._headers("admin_user")
        res = self.client.post("/api/admin/users", json={
            "username": "new_officer_by_admin",
            "password": "Password123!",
            "full_name": "New Officer",
            "role": "OFFICER"
        }, headers=headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["username"], "new_officer_by_admin")

    def test_supervisor_cannot_manage_users(self):
        """SUPERVISOR is forbidden from accessing /api/admin/users."""
        headers = self._headers("supervisor_user")
        res = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(res.status_code, 403)

    def test_supervisor_cannot_view_audit_logs(self):
        """SUPERVISOR is forbidden from viewing audit logs."""
        headers = self._headers("supervisor_user")
        res = self.client.get("/api/admin/audit-logs", headers=headers)
        self.assertEqual(res.status_code, 403)

    def test_supervisor_can_view_cameras_and_incidents(self):
        """SUPERVISOR can view cameras, zones, and incidents."""
        headers = self._headers("supervisor_user")
        self.assertEqual(self.client.get("/api/admin/cameras", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/zones", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/incidents", headers=headers).status_code, 200)

    def test_officer_cannot_manage_users_or_zones(self):
        """OFFICER cannot access user or zone mutation APIs."""
        headers = self._headers("officer_user")
        self.assertEqual(self.client.get("/api/admin/users", headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/api/admin/zones", json={
            "zone_name": "Illegal Zone",
            "camera_id": "CAM-01",
            "zone_type": "RESTRICTED"
        }, headers=headers).status_code, 403)

    def test_officer_cannot_resolve_incidents(self):
        """OFFICER cannot resolve or dismiss incidents (Supervisor/Admin only)."""
        # Create test incident
        inc_id = database.db_manager.create_admin_incident(
            incident_code="INC-TEST-RBAC",
            camera_id="CAM-01",
            event_type="border_intrusion",
            severity="CRITICAL"
        )
        headers = self._headers("officer_user")
        res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "RESOLVED"
        }, headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Officers cannot resolve", res.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
