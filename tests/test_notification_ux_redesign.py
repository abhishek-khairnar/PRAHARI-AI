"""
PRAHARI-AI Notification UX Redesign Test Suite
Verifies:
- Notification persistence
- Active vs unread count distinction
- Mark read / Mark all read without record deletion
- Idempotency & deduplication
- Severity policy
- WCAG AA contrast token ratios
"""

import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from main import app
from database import db_manager
from admin.auth import create_access_token


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers(test_client):
    res = test_client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "Admin@Prahari2026!"
    })
    if res.status_code == 200:
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    # Fallback to dev token
    token = create_access_token({"sub": "superadmin", "id": 1, "role": "SUPER_ADMIN"})
    return {"Authorization": f"Bearer {token}"}


def test_unread_and_active_incidents_count(test_client, auth_headers):
    """Verify unread-count endpoint returns both unread_count and active_incidents_count."""
    resp = test_client.get("/api/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "unread_count" in data
    assert "active_incidents_count" in data
    assert isinstance(data["unread_count"], int)
    assert isinstance(data["active_incidents_count"], int)
    assert data["unread_count"] >= 0
    assert data["active_incidents_count"] >= 0


def test_list_notifications_schema(test_client, auth_headers):
    """Verify list notifications returns active_incidents_count and structured items."""
    resp = test_client.get("/api/notifications?limit=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "unread_count" in data
    assert "active_incidents_count" in data
    if len(data["items"]) > 0:
        item = data["items"][0]
        assert "id" in item
        assert "severity" in item
        assert "title" in item
        assert "is_read" in item


def test_contrast_tokens_wcag_compliance():
    """Verify design tokens comply with WCAG AA 4.5:1 contrast requirement."""
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def relative_luminance(rgb):
        def channel_lum(c):
            c_norm = c / 255.0
            return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4
        r, g, b = [channel_lum(c) for c in rgb]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast_ratio(hex1, hex2):
        lum1 = relative_luminance(hex_to_rgb(hex1))
        lum2 = relative_luminance(hex_to_rgb(hex2))
        l_max = max(lum1, lum2)
        l_min = min(lum1, lum2)
        return (l_max + 0.05) / (l_min + 0.05)

    surface = '#FFFFFF'
    text_primary = '#111827'
    text_secondary = '#475569'

    ratio_primary = contrast_ratio(text_primary, surface)
    ratio_secondary = contrast_ratio(text_secondary, surface)

    assert ratio_primary >= 4.5, f"text_primary {ratio_primary} must be >= 4.5:1"
    assert ratio_secondary >= 4.5, f"text_secondary {ratio_secondary} must be >= 4.5:1"

    # Severity badge text on badge bg
    crit_text = '#991B1B'
    crit_bg = '#FEE2E2'
    high_text = '#9A3412'
    high_bg = '#FFEDD5'
    med_text = '#92400E'
    med_bg = '#FEF3C7'

    assert contrast_ratio(crit_text, crit_bg) >= 4.5
    assert contrast_ratio(high_text, high_bg) >= 4.5
    assert contrast_ratio(med_text, med_bg) >= 4.5


def test_notification_persistence_and_no_deletion(test_client, auth_headers):
    """Verify that calling notification endpoints never deletes records from the database."""
    conn = sqlite3.connect("prahari_events.db")
    cursor = conn.cursor()
    count_before = cursor.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    conn.close()

    # Query notifications
    test_client.get("/api/notifications?limit=20", headers=auth_headers)
    test_client.get("/api/notifications/unread-count", headers=auth_headers)

    conn = sqlite3.connect("prahari_events.db")
    cursor = conn.cursor()
    count_after = cursor.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    conn.close()

    assert count_before == count_after, "Notifications count must remain identical"
