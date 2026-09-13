import os
import sys
import sqlite3
import json
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, base_dir)

from database import DatabaseManager, DEFAULT_DB_PATH

def audit_database():
    db_path = os.path.abspath(DEFAULT_DB_PATH)
    
    report = {
        "db_path": db_path,
        "exists": os.path.exists(db_path),
        "file_size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "connection_test": "FAIL",
        "journal_mode": None,
        "tables_found": [],
        "expected_tables": ["intrusion_events", "anpr_events", "system_events", "security_events"],
        "tables_verified": False,
        "schema_details": {},
        "production_record_counts": {},
        "insert_test": "FAIL",
        "read_test": "FAIL",
        "integrity_test": "FAIL",
        "cleanup_test": "FAIL",
        "overall_status": "PASS"
    }

    if not report["exists"]:
        report["overall_status"] = "FAIL"
        return save_and_return(report)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        report["connection_test"] = "PASS"

        # Check PRAGMA journal_mode
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        report["journal_mode"] = mode.upper()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        report["tables_found"] = tables
        report["tables_verified"] = all(t in tables for t in report["expected_tables"])

        # Table schema details and current production counts
        for tbl in report["expected_tables"]:
            if tbl in tables:
                cursor.execute(f"PRAGMA table_info({tbl});")
                cols = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "dflt_value": c[4], "pk": c[5]} for c in cursor.fetchall()]
                cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
                cnt = cursor.fetchone()[0]
                report["schema_details"][tbl] = cols
                report["production_record_counts"][tbl] = cnt

        conn.close()
    except Exception as e:
        report["connection_error"] = str(e)
        report["overall_status"] = "FAIL"
        return save_and_return(report)

    # Test safe Insert, Read, and immediate Cleanup
    db_mgr = DatabaseManager(db_path=db_path)
    test_obj_id = 999999
    test_ts = "2026-09-13 09:30:00"
    test_cam = "CAM-AUDIT-TEST"

    try:
        # Safe insert using DatabaseManager
        db_mgr.log_intrusion_event(
            timestamp=test_ts,
            object_type="Person",
            object_id=test_obj_id,
            snapshot_path="audit_test.jpg",
            camera_id=test_cam,
            direction="IN",
            plate_text="AUDIT99",
            plate_confidence=0.99,
            anpr_status="VERIFIED",
            validation_status="DETECTED"
        )
        report["insert_test"] = "PASS"

        # Read back test record
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM intrusion_events WHERE object_id = ? AND camera_id = ?;", (test_obj_id, test_cam))
        row = cur.fetchone()
        if row is not None:
            report["read_test"] = "PASS"
            # Verify event integrity
            if (row["object_id"] == test_obj_id and
                row["camera_id"] == test_cam and
                row["direction"] == "IN" and
                row["plate_text"] == "AUDIT99" and
                round(row["plate_confidence"], 2) == 0.99 and
                row["timestamp"] == test_ts):
                report["integrity_test"] = "PASS"

            # Immediate cleanup of ONLY the test record
            cur.execute("DELETE FROM intrusion_events WHERE object_id = ? AND camera_id = ?;", (test_obj_id, test_cam))
            conn.commit()

            # Verify deletion
            cur.execute("SELECT COUNT(*) FROM intrusion_events WHERE object_id = ? AND camera_id = ?;", (test_obj_id, test_cam))
            after_count = cur.fetchone()[0]
            if after_count == 0:
                report["cleanup_test"] = "PASS"
        conn.close()
    except Exception as e:
        report["insert_read_error"] = str(e)
        report["overall_status"] = "FAIL"

    if (report["connection_test"] == "PASS" and
        report["tables_verified"] and
        report["insert_test"] == "PASS" and
        report["read_test"] == "PASS" and
        report["integrity_test"] == "PASS" and
        report["cleanup_test"] == "PASS"):
        report["overall_status"] = "PASS"
    else:
        report["overall_status"] = "PARTIAL"

    return save_and_return(report)

def save_and_return(report):
    out_path = os.path.join(os.path.dirname(__file__), "database_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Database audit report written to {out_path}")
    return report

if __name__ == "__main__":
    audit_database()
