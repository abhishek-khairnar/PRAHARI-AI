"""
Tests for Admin Panel Modules
Validates Users, Cameras, Zones/Fences, Alert Rules, Incidents, System Health, and Audit Logs.
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


class TestAdminModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_modules_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_modules.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

        res = cls.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "Admin@Prahari2026!"
        })
        cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        # Re-assert DB path in case another test touched it
        database.db_manager.set_db_path(self.db_path)

    # 1. User Management Tests
    def test_user_crud_and_last_superadmin_guard(self):
        # Create user
        res = self.client.post("/api/admin/users", json={
            "username": "test_cadet",
            "password": "CadetPassword2026!",
            "full_name": "Cadet Smith",
            "role": "OFFICER"
        }, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        cadet_id = res.json()["id"]

        # Duplicate username rejection
        dup_res = self.client.post("/api/admin/users", json={
            "username": "test_cadet",
            "password": "OtherPassword!",
            "full_name": "Duplicate Cadet",
            "role": "OFFICER"
        }, headers=self.headers)
        self.assertEqual(dup_res.status_code, 409)

        # Update user
        up_res = self.client.patch(f"/api/admin/users/{cadet_id}", json={
            "full_name": "Senior Cadet Smith",
            "role": "SUPERVISOR"
        }, headers=self.headers)
        self.assertEqual(up_res.status_code, 200)
        self.assertEqual(up_res.json()["role"], "SUPERVISOR")

        # Disable user
        dis_res = self.client.patch(f"/api/admin/users/{cadet_id}", json={
            "is_active": 0
        }, headers=self.headers)
        self.assertEqual(dis_res.status_code, 200)
        self.assertEqual(dis_res.json()["is_active"], 0)

        # Attempt to deactivate the only active SUPER_ADMIN (must fail with 400)
        super_res = self.client.patch("/api/admin/users/1", json={
            "is_active": 0
        }, headers=self.headers)
        self.assertEqual(super_res.status_code, 400)
        self.assertIn("last active Super Administrator", super_res.json()["detail"])

    # 2. Camera Management Tests
    def test_camera_list_and_safe_update(self):
        res = self.client.get("/api/admin/cameras", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        cams = res.json()
        self.assertGreaterEqual(len(cams), 4)

        # Update CAM-01 metadata
        up_cam = self.client.patch("/api/admin/cameras/CAM-01", json={
            "name": "Northern Border Gate Alpha",
            "location_zone": "Sector 7 North"
        }, headers=self.headers)
        self.assertEqual(up_cam.status_code, 200)
        self.assertEqual(up_cam.json()["name"], "Northern Border Gate Alpha")

    # 3. Zones & Virtual Fences Tests
    def test_zones_crud(self):
        # List default zones
        list_res = self.client.get("/api/admin/zones", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(len(list_res.json()), 4)

        # Create new zone
        create_res = self.client.post("/api/admin/zones", json={
            "zone_name": "High Security Depot",
            "camera_id": "CAM-04",
            "zone_type": "RESTRICTED",
            "severity": "CRITICAL",
            "is_enabled": 1,
            "fence_direction": "IN",
            "fence_ratio": 0.45
        }, headers=self.headers)
        self.assertEqual(create_res.status_code, 201)
        zone_id = create_res.json()["id"]

        # Update zone
        patch_res = self.client.patch(f"/api/admin/zones/{zone_id}", json={
            "severity": "HIGH",
            "fence_ratio": 0.50
        }, headers=self.headers)
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["severity"], "HIGH")

        # Delete zone
        del_res = self.client.delete(f"/api/admin/zones/{zone_id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 200)

    # 4. Alert Rules Management Tests
    def test_alert_rules(self):
        res = self.client.get("/api/admin/alert-rules", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        rules = res.json()
        self.assertGreaterEqual(len(rules), 7)

        # Update a rule
        rule_id = rules[0]["id"]
        up_res = self.client.patch(f"/api/admin/alert-rules/{rule_id}", json={
            "severity": "CRITICAL",
            "cooldown_seconds": 25,
            "is_enabled": 1
        }, headers=self.headers)
        self.assertEqual(up_res.status_code, 200)
        self.assertEqual(up_res.json()["cooldown_seconds"], 25)

    # 5. Incident Management Tests
    def test_incident_lifecycle_workflow(self):
        # Create incident
        create_res = self.client.post("/api/admin/incidents", json={
            "camera_id": "CAM-01",
            "event_type": "border_intrusion",
            "severity": "CRITICAL",
            "zone_name": "Border Restricted Zone",
            "notes": "Intrusion detected near fence boundary"
        }, headers=self.headers)
        self.assertEqual(create_res.status_code, 201)
        inc = create_res.json()
        inc_id = inc["id"]
        self.assertEqual(inc["status"], "NEW")

        # Acknowledge incident
        ack_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "ACKNOWLEDGED",
            "assigned_officer_name": "Officer Sharma",
            "notes": "Incident acknowledged by dispatcher"
        }, headers=self.headers)
        self.assertEqual(ack_res.status_code, 200)
        self.assertEqual(ack_res.json()["status"], "ACKNOWLEDGED")

        # Move to Investigating
        inv_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "INVESTIGATING",
            "notes": "Patrol dispatched to location"
        }, headers=self.headers)
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(inv_res.json()["status"], "INVESTIGATING")

        # Resolve Incident
        res_res = self.client.patch(f"/api/admin/incidents/{inc_id}", json={
            "status": "RESOLVED",
            "notes": "Perimeter verified clear. Resolved."
        }, headers=self.headers)
        self.assertEqual(res_res.status_code, 200)
        resolved_inc = res_res.json()
        self.assertEqual(resolved_inc["status"], "RESOLVED")
        self.assertEqual(resolved_inc["resolved_by"], "superadmin")
        self.assertIsNotNone(resolved_inc["resolved_at"])

    # 6. System Health Tests
    def test_system_health_endpoint(self):
        res = self.client.get("/api/admin/system-health", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        health = res.json()
        self.assertIn("backend", health)
        self.assertEqual(health["backend"]["status"], "ONLINE")
        self.assertIn("database", health)
        self.assertEqual(health["database"]["status"], "ONLINE")
        self.assertIn("cameras", health)
        self.assertIn("ai_pipeline", health)
        self.assertEqual(health["ai_pipeline"]["yolo_model"], "LOADED")

    # 7. Audit Log Tests
    def test_audit_logs_recorded(self):
        res = self.client.get("/api/admin/audit-logs", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        audits = res.json()
        self.assertGreater(len(audits), 0)
        actions = [a["action"] for a in audits]
        # Previous actions should be present in audit trail
        self.assertTrue(any("USER" in a or "ZONE" in a or "INCIDENT" in a or "LOGIN" in a for a in actions))


if __name__ == "__main__":
    unittest.main(verbosity=2)
