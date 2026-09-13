import os
import sys
import json
import tempfile
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, base_dir)

from centroid_tracker import CentroidTracker
from camera_manager import DEFAULT_CAMERAS
from database import DatabaseManager

def audit_intrusion():
    # 1. Verify Fence configuration across all cameras
    fence_configs = {}
    valid_configs = True
    for cam in DEFAULT_CAMERAS:
        cid = cam["id"]
        ratio = cam.get("line_y_ratio")
        is_valid = ratio is not None and 0.0 < ratio < 1.0
        fence_configs[cid] = {
            "name": cam.get("name"),
            "line_y_ratio": ratio,
            "valid_ratio": is_valid
        }
        if not is_valid:
            valid_configs = False

    # 2. Test IN and OUT crossing logic with CentroidTracker
    tracker = CentroidTracker(max_disappeared=25, max_distance=220.0)
    line_y = 500

    # Test IN Crossing (moving from y=400 to y=550 -> confirmed on second frame y=560)
    # Frame 1: y=400 (confirmed side: -1 / ABOVE)
    t1 = tracker.update([(100, 380, 140, 420, "Person", 0.90)])
    obj_id = next(iter(t1.keys()))
    cross1, dir1 = tracker.check_intrusion_crossing(obj_id, line_y)

    # Frame 2: y=550 (candidate side: 1 / BELOW)
    t2 = tracker.update([(100, 530, 140, 570, "Person", 0.90)])
    cross2, dir2 = tracker.check_intrusion_crossing(obj_id, line_y)

    # Frame 3: y=560 (confirmed crossing side: 1 / BELOW -> IN event!)
    t3 = tracker.update([(100, 540, 140, 580, "Person", 0.90)])
    cross3, dir3 = tracker.check_intrusion_crossing(obj_id, line_y)

    in_crossing_success = (not cross1) and (not cross2) and (cross3 is True and dir3 == "IN")

    # Test OUT Crossing (moving back from y=560 to y=420 -> confirmed at y=410)
    # Frame 4: y=420 (candidate side: -1 / ABOVE)
    t4 = tracker.update([(100, 400, 140, 440, "Person", 0.90)])
    cross4, dir4 = tracker.check_intrusion_crossing(obj_id, line_y)

    # Frame 5: y=410 (confirmed crossing side: -1 / ABOVE -> OUT event!)
    t5 = tracker.update([(100, 390, 140, 430, "Person", 0.90)])
    cross5, dir5 = tracker.check_intrusion_crossing(obj_id, line_y)

    out_crossing_success = (not cross4) and (cross5 is True and dir5 == "OUT")

    # Test Duplicate Prevention (staying at y=410)
    # Frame 6: y=410
    t6 = tracker.update([(100, 390, 140, 430, "Person", 0.90)])
    cross6, dir6 = tracker.check_intrusion_crossing(obj_id, line_y)
    no_duplicate = (cross6 is False)

    # 3. Test Event creation with metadata and database storage in temporary isolated DB
    tmp_dir = tempfile.mkdtemp(prefix="audit_db_")
    tmp_db_path = os.path.join(tmp_dir, "test_audit.db")
    test_db = DatabaseManager(db_path=tmp_db_path)

    test_db.log_intrusion_event(
        timestamp="2026-09-13 10:00:00",
        object_type="Person",
        object_id=obj_id,
        snapshot_path="test_snapshot.jpg",
        camera_id="CAM-01",
        direction="IN",
        plate_text="N/A",
        plate_confidence=0.0,
        anpr_status="NOT_APPLICABLE",
        validation_status="DETECTED"
    )

    logged = test_db.get_recent_intrusions(limit=10, camera_id="CAM-01")
    event_verified = False
    if logged and len(logged) == 1:
        rec = logged[0]
        event_verified = (
            rec["camera_id"] == "CAM-01" and
            rec["object_id"] == obj_id and
            rec["object_type"] == "Person" and
            rec["direction"] == "IN" and
            rec["timestamp"] == "2026-09-13 10:00:00"
        )

    result = {
        "fence_configuration": {
            "status": "PASS" if valid_configs else "FAIL",
            "cameras": fence_configs
        },
        "crossing_logic": {
            "in_crossing": {
                "status": "PASS" if in_crossing_success else "FAIL",
                "direction": dir3
            },
            "out_crossing": {
                "status": "PASS" if out_crossing_success else "FAIL",
                "direction": dir5
            },
            "duplicate_suppression": {
                "status": "PASS" if no_duplicate else "FAIL"
            }
        },
        "event_integrity": {
            "status": "PASS" if event_verified else "FAIL",
            "sample_event": logged[0] if logged else None
        },
        "overall_status": "PASS" if (valid_configs and in_crossing_success and out_crossing_success and event_verified) else "FAIL"
    }

    out_path = os.path.join(os.path.dirname(__file__), "intrusion_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Intrusion audit report written to {out_path}")

if __name__ == "__main__":
    audit_intrusion()
