"""
Tests for Admin Panel Authentication & Session Layer
Validates bcrypt password hashing, JWT encoding/decoding, login flow,
disabled user handling, and /api/auth/me profile retrieval.
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
from admin.auth import hash_password, verify_password, create_access_token, decode_access_token


class TestAdminAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="prahari_auth_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_auth.db")
        database.db_manager.set_db_path(cls.db_path)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_bcrypt_hashing_and_verification(self):
        password = "SecurePassword2026!"
        pw_hash = hash_password(password)
        self.assertNotEqual(password, pw_hash)
        self.assertTrue(pw_hash.startswith("$2b$"))
        self.assertTrue(verify_password(password, pw_hash))
        self.assertFalse(verify_password("WrongPassword", pw_hash))

    def test_jwt_token_generation_and_decoding(self):
        data = {"sub": "testuser", "role": "ADMIN"}
        token = create_access_token(data)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("sub"), "testuser")
        self.assertEqual(payload.get("role"), "ADMIN")

    def test_login_success_with_bootstrap_superadmin(self):
        res = self.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "Admin@Prahari2026!"
        })
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("access_token", body)
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(body["user"]["username"], "superadmin")
        self.assertEqual(body["user"]["role"], "SUPER_ADMIN")

    def test_login_failure_invalid_password(self):
        res = self.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "IncorrectPassword"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid username or password", res.json()["detail"])

    def test_login_failure_nonexistent_user(self):
        res = self.client.post("/api/auth/login", json={
            "username": "ghost_user",
            "password": "AnyPassword"
        })
        self.assertEqual(res.status_code, 401)

    def test_login_disabled_user_rejected(self):
        # Create disabled user
        pw_hash = hash_password("Password123!")
        database.db_manager.create_admin_user(
            username="disabled_user",
            password_hash=pw_hash,
            full_name="Disabled Officer",
            role="OFFICER",
            is_active=0
        )
        res = self.client.post("/api/auth/login", json={
            "username": "disabled_user",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn("disabled", res.json()["detail"].lower())

    def test_auth_me_endpoint(self):
        # Login to obtain token
        login_res = self.client.post("/api/auth/login", json={
            "username": "superadmin",
            "password": "Admin@Prahari2026!"
        })
        token = login_res.json()["access_token"]

        # Call /api/auth/me with Bearer token
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        user_info = res.json()
        self.assertEqual(user_info["username"], "superadmin")
        self.assertEqual(user_info["role"], "SUPER_ADMIN")
        self.assertNotIn("password_hash", user_info)

    def test_auth_me_unauthorized_without_token(self):
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
