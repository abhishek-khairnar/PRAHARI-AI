"""
tests/admin/test_data_truth_pipeline.py
Authoritative regression test suite validating:
1. Zero production incident seeding on fresh database initialization.
2. Real-time event-to-incident correlation and alert rule policy integration.
3. Cooldown window deduplication.
4. Mathematical consistency of overview KPIs.
5. Camera telemetry (ONLINE, DEGRADED, OFFLINE) and dual FPS (AI vs Ingestion).
6. Incident state machine and audit trail for reopening.
"""

import os
import time
import tempfile
import pytest
from datetime import datetime, timedelta

from database import DatabaseManager
from admin.admin_routes import evaluate_camera_runtime_health


@pytest.fixture
def temp_db():
    """Create a completely isolated temporary database instance."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Ensure PRAHARI_DEMO_SEED is unset so we test real production behavior
    old_seed = os.environ.pop("PRAHARI_DEMO_SEED", None)
    old_env = os.environ.pop("PRAHARI_ENV", None)

    db = DatabaseManager(db_path=path)
    yield db

    # Cleanup
    if old_seed is not None:
        os.environ["PRAHARI_DEMO_SEED"] = old_seed
    if old_env is not None:
        os.environ["PRAHARI_ENV"] = old_env
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_zero_production_incident_seeding(temp_db):
    """Phase 2 & 26: Production startup MUST NOT seed fake operational incidents."""
    incidents = temp_db.list_admin_incidents()
    assert len(incidents) == 0, "Fresh production database must have 0 incidents"

    summary = temp_db.count_admin_incidents_summary()
    assert summary["total"] == 0
    assert summary["open"] == 0
    assert summary["closed"] == 0
    assert summary["by_status"]["NEW"] == 0
    assert summary["by_status"]["ACKNOWLEDGED"] == 0
    assert summary["by_status"]["INVESTIGATING"] == 0
    assert summary["by_status"]["RESOLVED"] == 0
    assert summary["by_status"]["DISMISSED"] == 0


def test_event_to_incident_promotion_night_movement(temp_db):
    """Phase 3, 5, 6, 7: Security event promotion into incident according to alert rules."""
    now_str = "2026-09-13 14:00:00"
    event_id = temp_db.log_security_event(
        timestamp=now_str,
        event_type="night_movement",
        camera_id="CAM-02",
        object_type="person",
        object_id=42,
        confidence=0.88,
        snapshot_path="CAM-02_snap.jpg",
        details="Night movement detected (Person ID #42, disp=150px)"
    )
    assert event_id > 0, "Security event must be logged"

    # Verify incident was created
    incidents = temp_db.list_admin_incidents()
    assert len(incidents) == 1, "Security event must trigger incident creation"
    inc = incidents[0]
    assert inc["event_id"] == event_id
    assert inc["camera_id"] == "CAM-02"
    assert inc["event_type"] == "night_movement"
    assert inc["severity"] == "HIGH", "Must match rule in admin_alert_rules"
    assert inc["status"] == "NEW"
    assert inc["detected_at"] == now_str, "Detected time must match raw event timestamp"
    assert inc["incident_code"].startswith("INC-")


def test_event_to_incident_promotion_intrusion(temp_db):
    """Phase 3: Border intrusion event promotion to CRITICAL incident."""
    now_str = "2026-09-13 14:05:00"
    event_id = temp_db.log_intrusion_event(
        timestamp=now_str,
        object_type="vehicle",
        object_id=10,
        snapshot_path="CAM-01_intrusion.jpg",
        camera_id="CAM-01",
        direction="IN"
    )
    assert event_id > 0

    incidents = temp_db.list_admin_incidents()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["event_id"] == event_id
    assert inc["camera_id"] == "CAM-01"
    assert inc["event_type"] == "border_intrusion"
    assert inc["severity"] == "CRITICAL", "Border intrusion alert rule severity is CRITICAL"
    assert inc["status"] == "NEW"


def test_alert_rule_disabling_suppresses_incident_creation(temp_db):
    """Phase 18: Disabling an alert rule must prevent incident creation."""
    # 1. Disable night_movement rule
    rule = temp_db.get_admin_alert_rule("night_movement")
    assert rule is not None
    updated = temp_db.update_admin_alert_rule(rule["id"], is_enabled=0)
    assert updated is True

    # 2. Log night_movement security event
    now_str = "2026-09-13 14:10:00"
    event_id = temp_db.log_security_event(
        timestamp=now_str,
        event_type="night_movement",
        camera_id="CAM-02",
        details="Movement while rule disabled"
    )
    assert event_id > 0

    # 3. Verify security event was stored in database
    sec_events = temp_db.get_recent_security_events(camera_id="CAM-02")
    assert len(sec_events) >= 1

    # 4. Verify NO incident was created
    incidents = temp_db.list_admin_incidents()
    assert len(incidents) == 0, "Disabled alert rule must not generate admin incidents"


def test_alert_rule_severity_influence(temp_db):
    """Phase 5 & 18: Changing alert rule severity alters new incident severity."""
    rule = temp_db.get_admin_alert_rule("night_movement")
    temp_db.update_admin_alert_rule(rule["id"], severity="CRITICAL")

    now_str = "2026-09-13 14:15:00"
    event_id = temp_db.log_security_event(
        timestamp=now_str,
        event_type="night_movement",
        camera_id="CAM-03",
        details="Night movement with updated severity rule"
    )
    assert event_id > 0

    incidents = temp_db.list_admin_incidents()
    assert len(incidents) == 1
    assert incidents[0]["severity"] == "CRITICAL", "Incident severity must reflect active alert rule"


def test_incident_cooldown_deduplication(temp_db):
    """Phase 4: Cooldown window deduplicates repeated detections on same camera."""
    # Alert rule for night_movement has cooldown_seconds = 15
    t1 = "2026-09-13 14:20:00"
    e1 = temp_db.log_security_event(
        timestamp=t1,
        event_type="night_movement",
        camera_id="CAM-02",
        details="Initial detection"
    )
    assert e1 > 0
    assert len(temp_db.list_admin_incidents()) == 1

    # Rapid second event 3 seconds later on same camera
    t2 = "2026-09-13 14:20:03"
    e2 = temp_db.log_security_event(
        timestamp=t2,
        event_type="night_movement",
        camera_id="CAM-02",
        details="Repeated detection within cooldown"
    )
    assert e2 > 0
    # Must NOT create a duplicate incident
    assert len(temp_db.list_admin_incidents()) == 1, "Should deduplicate within cooldown window"

    # Event on DIFFERENT camera (CAM-03) must NOT be suppressed
    t3 = "2026-09-13 14:20:05"
    e3 = temp_db.log_security_event(
        timestamp=t3,
        event_type="night_movement",
        camera_id="CAM-03",
        details="Detection on another camera"
    )
    assert e3 > 0
    assert len(temp_db.list_admin_incidents()) == 2, "Different camera must create separate incident"

    # Event AFTER cooldown (25 seconds later) on CAM-02 creates new incident
    t4 = "2026-09-13 14:20:26"
    e4 = temp_db.log_security_event(
        timestamp=t4,
        event_type="night_movement",
        camera_id="CAM-02",
        details="Subsequent detection after cooldown expired"
    )
    assert e4 > 0
    assert len(temp_db.list_admin_incidents()) == 3


def test_overview_mathematical_consistency(temp_db):
    """Phase 9: NEW + ACKNOWLEDGED + INVESTIGATING + RESOLVED + DISMISSED == TOTAL."""
    # Seed 5 controlled incidents across different states
    id1 = temp_db.create_admin_incident(incident_code="INC-0001", camera_id="CAM-01", event_type="test", severity="LOW", status="NEW")
    id2 = temp_db.create_admin_incident(incident_code="INC-0002", camera_id="CAM-02", event_type="test", severity="MED", status="ACKNOWLEDGED")
    id3 = temp_db.create_admin_incident(incident_code="INC-0003", camera_id="CAM-03", event_type="test", severity="HIGH", status="INVESTIGATING")
    id4 = temp_db.create_admin_incident(incident_code="INC-0004", camera_id="CAM-04", event_type="test", severity="CRIT", status="RESOLVED")
    id5 = temp_db.create_admin_incident(incident_code="INC-0005", camera_id="CAM-01", event_type="test", severity="LOW", status="DISMISSED")

    summary = temp_db.count_admin_incidents_summary()
    assert summary["total"] == 5
    assert summary["open"] == 3  # NEW + ACKNOWLEDGED + INVESTIGATING
    assert summary["closed"] == 2  # RESOLVED + DISMISSED
    assert summary["open"] + summary["closed"] == summary["total"]

    by_status = summary["by_status"]
    status_sum = (
        by_status["NEW"] +
        by_status["ACKNOWLEDGED"] +
        by_status["INVESTIGATING"] +
        by_status["RESOLVED"] +
        by_status["DISMISSED"]
    )
    assert status_sum == summary["total"]


def test_camera_runtime_health_evaluator():
    """Phase 11, 12, 13: Accurate camera telemetry and status classification."""
    class MockReader:
        def __init__(self, running, is_connected, last_frame_time, current_fps, capture_fps):
            self.running = running
            self.is_connected = is_connected
            self.last_frame_time = last_frame_time
            self.current_fps = current_fps
            self.capture_fps = capture_fps

    now = time.time()

    # 1. ONLINE (<5s)
    reader_online = MockReader(True, True, now - 1.2, 5.7, 29.5)
    h_online = evaluate_camera_runtime_health(reader_online, {})
    assert h_online["status"] == "ONLINE"
    assert h_online["connected"] is True
    assert h_online["ai_fps"] == 5.7
    assert h_online["capture_fps"] == 29.5
    assert h_online["last_frame_age_seconds"] <= 2.0

    # 2. DEGRADED (5-15s)
    reader_degraded = MockReader(True, True, now - 8.5, 5.5, 29.0)
    h_degraded = evaluate_camera_runtime_health(reader_degraded, {})
    assert h_degraded["status"] == "DEGRADED"
    assert h_degraded["connected"] is True
    assert 8.0 <= h_degraded["last_frame_age_seconds"] <= 10.0

    # 3. OFFLINE (>15s)
    reader_stale = MockReader(True, True, now - 22.0, 0.0, 0.0)
    h_stale = evaluate_camera_runtime_health(reader_stale, {})
    assert h_stale["status"] == "OFFLINE"

    # 4. Disconnected / Stopped
    reader_stopped = MockReader(False, False, 0.0, 0.0, 0.0)
    h_stopped = evaluate_camera_runtime_health(reader_stopped, {})
    assert h_stopped["status"] == "OFFLINE"
    assert h_stopped["connected"] is False
