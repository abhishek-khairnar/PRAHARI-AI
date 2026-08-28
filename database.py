import os
import sqlite3
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger("PRAHARI-DB")

DB_PATH = os.path.join(os.path.dirname(__file__), "prahari_events.db")
SYNC_EXPORT_PATH = os.path.join(os.path.dirname(__file__), "synced_events.json")


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager for PRAHARI-AI.
    Provides persistent local storage for intrusion alerts, ANPR reads, and system events
    with an offline-first sync engine.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._last_sync_timestamp = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency without blocking
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        """Creates the required tables if they don't exist and runs safe migrations."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Intrusion Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intrusion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    camera_id TEXT DEFAULT 'CAM-01',
                    object_type TEXT NOT NULL,
                    object_id INTEGER NOT NULL,
                    direction TEXT DEFAULT 'IN',
                    plate_text TEXT DEFAULT 'PENDING',
                    plate_confidence REAL DEFAULT 0.0,
                    anpr_status TEXT DEFAULT 'PENDING',
                    validation_status TEXT DEFAULT 'DETECTED',
                    snapshot_path TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Safe migrations for intrusion_events
            for col, col_type in [
                ("camera_id", "TEXT DEFAULT 'CAM-01'"),
                ("direction", "TEXT DEFAULT 'IN'"),
                ("plate_text", "TEXT DEFAULT 'PENDING'"),
                ("plate_confidence", "REAL DEFAULT 0.0"),
                ("anpr_status", "TEXT DEFAULT 'PENDING'"),
                ("validation_status", "TEXT DEFAULT 'DETECTED'")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE intrusion_events ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # 2. ANPR Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anpr_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    camera_id TEXT DEFAULT 'CAM-01',
                    object_type TEXT NOT NULL,
                    object_id INTEGER NOT NULL,
                    plate_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    validation_status TEXT DEFAULT 'DETECTED',
                    snapshot_path TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Safe migrations for anpr_events
            for col, col_type in [
                ("camera_id", "TEXT DEFAULT 'CAM-01'"),
                ("validation_status", "TEXT DEFAULT 'DETECTED'")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE anpr_events ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # 3. System Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT
                )
            """)

            # 4. Security Events Table (Unified for suspicious_activity, night_movement, face_detection)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    camera_id TEXT DEFAULT 'CAM-01',
                    event_type TEXT NOT NULL,
                    object_type TEXT,
                    object_id INTEGER,
                    confidence REAL,
                    validation_status TEXT DEFAULT 'DETECTED',
                    snapshot_path TEXT,
                    details TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Safe migrations for security_events
            for col, col_type in [
                ("validation_status", "TEXT DEFAULT 'DETECTED'")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE security_events ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # Create indices for fast lookup & multi-camera filtering
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_intrusion_ts ON intrusion_events (timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_intrusion_cam ON intrusion_events (camera_id, timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anpr_ts ON anpr_events (timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anpr_cam ON anpr_events (camera_id, timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_intrusion_synced ON intrusion_events (synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anpr_synced ON anpr_events (synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_ts ON security_events (timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_cam ON security_events (camera_id, timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_type ON security_events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_synced ON security_events (synced)")

            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path} with WAL mode")

    def log_intrusion_event(
        self,
        timestamp: str,
        object_type: str,
        object_id: int,
        snapshot_path: str,
        camera_id: str = "CAM-01",
        direction: str = "IN",
        plate_text: str = "PENDING",
        plate_confidence: float = 0.0,
        anpr_status: str = "PENDING",
        validation_status: str = "DETECTED"
    ) -> int:
        """Asynchronously insert an intrusion event with camera_id, direction, ANPR linkage, and validation status."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO intrusion_events (
                        timestamp, camera_id, object_type, object_id, direction, plate_text, plate_confidence, anpr_status, validation_status, snapshot_path, synced
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (timestamp, camera_id, object_type, object_id, direction, plate_text, float(plate_confidence), anpr_status, validation_status, snapshot_path)
                )
                conn.commit()
                event_id = cursor.lastrowid
                conn.close()
                return event_id
            except Exception as e:
                logger.error(f"Error logging intrusion event to DB: {e}")
                return -1

    def update_intrusion_anpr(self, object_id: int, plate_text: str, plate_confidence: float, anpr_status: str, camera_id: str = None):
        """Asynchronously updates recent intrusion event with resolved ANPR license plate."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if camera_id:
                    cursor.execute(
                        """
                        UPDATE intrusion_events
                        SET plate_text = ?, plate_confidence = ?, anpr_status = ?, validation_status = ?
                        WHERE id = (
                            SELECT id FROM intrusion_events
                            WHERE object_id = ? AND camera_id = ?
                            ORDER BY id DESC LIMIT 1
                        )
                        """,
                        (plate_text, float(plate_confidence), anpr_status, "VERIFIED" if anpr_status == "VERIFIED" else "DETECTED", object_id, camera_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE intrusion_events
                        SET plate_text = ?, plate_confidence = ?, anpr_status = ?, validation_status = ?
                        WHERE id = (
                            SELECT id FROM intrusion_events
                            WHERE object_id = ?
                            ORDER BY id DESC LIMIT 1
                        )
                        """,
                        (plate_text, float(plate_confidence), anpr_status, "VERIFIED" if anpr_status == "VERIFIED" else "DETECTED", object_id)
                    )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error updating intrusion ANPR in DB: {e}")

    def log_anpr_event(
        self,
        timestamp: str,
        object_type: str,
        object_id: int,
        plate_text: str,
        confidence: float,
        snapshot_path: str,
        camera_id: str = "CAM-01",
        validation_status: str = "DETECTED"
    ) -> int:
        """Asynchronously insert an ANPR plate read event with camera_id and validation status."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO anpr_events (timestamp, camera_id, object_type, object_id, plate_text, confidence, validation_status, snapshot_path, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (timestamp, camera_id, object_type, object_id, plate_text, float(confidence), validation_status, snapshot_path)
                )
                conn.commit()
                event_id = cursor.lastrowid
                conn.close()
                return event_id
            except Exception as e:
                logger.error(f"Error logging ANPR event to DB: {e}")
                return -1

    def log_system_event(self, event_type: str, details: str = ""):
        """Logs lifecycle and stream events."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO system_events (timestamp, event_type, details) VALUES (?, ?, ?)",
                    (now_str, event_type, details)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error logging system event to DB: {e}")

    def log_security_event(
        self,
        timestamp: str,
        event_type: str,
        camera_id: str = "CAM-01",
        object_type: str = None,
        object_id: int = None,
        confidence: float = None,
        snapshot_path: str = None,
        details: str = None,
        validation_status: str = "DETECTED"
    ) -> int:
        """Insert a security event (suspicious_activity, night_movement, face_detection, etc.)."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO security_events (timestamp, camera_id, event_type, object_type, object_id, confidence, validation_status, snapshot_path, details, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (timestamp, camera_id, event_type, object_type, object_id, confidence, validation_status, snapshot_path, details)
                )
                conn.commit()
                event_id = cursor.lastrowid
                conn.close()
                return event_id
            except Exception as e:
                logger.error(f"Error logging security event to DB: {e}")
                return -1

    def get_recent_security_events(self, event_type: str = None, camera_id: str = None, limit: int = 50) -> list:
        """Retrieves recent security events, optionally filtered by event_type and camera_id."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT * FROM security_events WHERE 1=1"
                params = []
                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                result = []
                for row in rows:
                    r = dict(row)
                    if r.get("snapshot_path"):
                        filename = os.path.basename(r["snapshot_path"])
                        r["snapshot_url"] = f"/alerts/{filename}"
                    else:
                        r["snapshot_url"] = ""
                    result.append(r)
                return result
            except Exception as e:
                logger.error(f"Error fetching security events: {e}")
                return []

    def get_security_event_counts(self, camera_id: str = None) -> dict:
        """Returns counts of security events by event_type."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if camera_id:
                    cursor.execute(
                        "SELECT event_type, COUNT(*) as cnt FROM security_events WHERE camera_id = ? GROUP BY event_type",
                        (camera_id,)
                    )
                else:
                    cursor.execute(
                        "SELECT event_type, COUNT(*) as cnt FROM security_events GROUP BY event_type"
                    )
                rows = cursor.fetchall()
                conn.close()
                counts = {}
                for row in rows:
                    counts[row["event_type"]] = row["cnt"]
                return counts
            except Exception as e:
                logger.error(f"Error fetching security event counts: {e}")
                return {}

    def get_recent_intrusions(self, limit: int = 50, camera_id: str = None, validation_status: str = None) -> list:
        """Retrieves recent intrusion events for startup cache and API queries."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = """
                    SELECT id, timestamp,
                           COALESCE(camera_id, 'CAM-01') as camera_id,
                           object_type, object_id,
                           COALESCE(direction, 'IN') as direction,
                           COALESCE(plate_text, 'PENDING') as plate_text,
                           COALESCE(plate_confidence, 0.0) as plate_confidence,
                           COALESCE(anpr_status, 'PENDING') as anpr_status,
                           COALESCE(validation_status, 'DETECTED') as validation_status,
                           snapshot_path
                    FROM intrusion_events
                    WHERE 1=1
                """
                params = []
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                if validation_status:
                    query += " AND validation_status = ?"
                    params.append(validation_status)
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                result = []
                for row in rows:
                    filename = os.path.basename(row["snapshot_path"]) if row["snapshot_path"] else ""
                    result.append({
                        "id": row["id"],
                        "event_type": "intrusion",
                        "camera_id": row["camera_id"],
                        "object_type": row["object_type"],
                        "object_id": row["object_id"],
                        "direction": row["direction"],
                        "plate_text": row["plate_text"],
                        "plate_confidence": float(row["plate_confidence"]),
                        "anpr_status": row["anpr_status"],
                        "validation_status": row["validation_status"],
                        "timestamp": row["timestamp"],
                        "snapshot_url": f"/alerts/{filename}" if filename else "",
                        "snapshot_filename": filename
                    })
                return result
            except Exception as e:
                logger.error(f"Error fetching recent intrusions: {e}")
                return []

    def get_recent_anpr(self, limit: int = 50, camera_id: str = None, validation_status: str = None) -> list:
        """Retrieves recent ANPR reads for startup cache and API queries."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = """
                    SELECT id, timestamp,
                           COALESCE(camera_id, 'CAM-01') as camera_id,
                           object_type, object_id, plate_text, confidence,
                           COALESCE(validation_status, 'DETECTED') as validation_status,
                           snapshot_path
                    FROM anpr_events
                    WHERE plate_text IS NOT NULL AND plate_text != 'N/A' AND plate_text != 'PLATE NOT READ'
                """
                params = []
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                if validation_status:
                    query += " AND validation_status = ?"
                    params.append(validation_status)
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                result = []
                for row in rows:
                    filename = os.path.basename(row["snapshot_path"]) if row["snapshot_path"] else ""
                    is_verified = (row["validation_status"] == "VERIFIED") or (float(row["confidence"]) >= 0.45)
                    result.append({
                        "id": row["id"],
                        "event_type": "anpr",
                        "camera_id": row["camera_id"],
                        "vehicle_id": row["object_id"],
                        "object_id": row["object_id"],
                        "vehicle_type": row["object_type"],
                        "object_type": row["object_type"],
                        "plate_text": row["plate_text"],
                        "confidence": float(row["confidence"]),
                        "validation_status": row["validation_status"],
                        "is_verified": is_verified,
                        "timestamp": row["timestamp"],
                        "snapshot_url": f"/anpr/{filename}" if filename else "",
                        "snapshot_filename": filename
                    })
                return result
            except Exception as e:
                logger.error(f"Error fetching recent ANPR reads: {e}")
                return []

    def get_all_events(self, limit: int = 50, offset: int = 0, camera_id: str = None) -> dict:
        """Paginated endpoint for all historical events with optional camera_id filter."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Fetch intrusions
                if camera_id:
                    cursor.execute("SELECT COUNT(*) FROM intrusion_events WHERE camera_id = ?", (camera_id,))
                    total_intrusions = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM intrusion_events WHERE camera_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                        (camera_id, limit, offset)
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM intrusion_events")
                    total_intrusions = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM intrusion_events ORDER BY id DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    )
                intrusions = [dict(row) for row in cursor.fetchall()]

                # Fetch ANPR
                if camera_id:
                    cursor.execute("SELECT COUNT(*) FROM anpr_events WHERE camera_id = ?", (camera_id,))
                    total_anpr = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM anpr_events WHERE camera_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                        (camera_id, limit, offset)
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM anpr_events")
                    total_anpr = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM anpr_events ORDER BY id DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    )
                anpr = [dict(row) for row in cursor.fetchall()]

                # Fetch Security Events
                if camera_id:
                    cursor.execute("SELECT COUNT(*) FROM security_events WHERE camera_id = ?", (camera_id,))
                    total_security = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM security_events WHERE camera_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                        (camera_id, limit, offset)
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM security_events")
                    total_security = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT * FROM security_events ORDER BY id DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    )
                security = [dict(row) for row in cursor.fetchall()]

                conn.close()
                return {
                    "total_intrusions": total_intrusions,
                    "total_anpr": total_anpr,
                    "total_security": total_security,
                    "limit": limit,
                    "offset": offset,
                    "intrusions": intrusions,
                    "anpr_reads": anpr,
                    "security_events": security
                }
            except Exception as e:
                logger.error(f"Error fetching all historical events: {e}")
                return {"error": str(e)}

    def sync_pending_events(self, export_path: str = SYNC_EXPORT_PATH) -> dict:
        """
        Offline-first sync engine:
        Finds all unsynced records (synced = 0), exports to JSON archive,
        and marks synced = 1 in SQLite.
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM intrusion_events WHERE synced = 0")
                unsynced_intrusions = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM anpr_events WHERE synced = 0")
                unsynced_anpr = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM security_events WHERE synced = 0")
                unsynced_security = [dict(row) for row in cursor.fetchall()]

                count_synced = len(unsynced_intrusions) + len(unsynced_anpr) + len(unsynced_security)

                if count_synced > 0:
                    existing_data = {"intrusions": [], "anpr_reads": [], "security_events": [], "last_sync": ""}
                    if os.path.exists(export_path):
                        try:
                            with open(export_path, "r", encoding="utf-8") as f:
                                existing_data = json.load(f)
                        except Exception:
                            existing_data = {"intrusions": [], "anpr_reads": [], "security_events": [], "last_sync": ""}

                    existing_data["intrusions"].extend(unsynced_intrusions)
                    existing_data["anpr_reads"].extend(unsynced_anpr)
                    if "security_events" not in existing_data:
                        existing_data["security_events"] = []
                    existing_data["security_events"].extend(unsynced_security)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    existing_data["last_sync"] = now_str
                    self._last_sync_timestamp = now_str

                    with open(export_path, "w", encoding="utf-8") as f:
                        json.dump(existing_data, f, indent=2)

                    if unsynced_intrusions:
                        intrusion_ids = [r["id"] for r in unsynced_intrusions]
                        placeholders = ",".join("?" * len(intrusion_ids))
                        cursor.execute(f"UPDATE intrusion_events SET synced = 1 WHERE id IN ({placeholders})", intrusion_ids)

                    if unsynced_anpr:
                        anpr_ids = [r["id"] for r in unsynced_anpr]
                        placeholders = ",".join("?" * len(anpr_ids))
                        cursor.execute(f"UPDATE anpr_events SET synced = 1 WHERE id IN ({placeholders})", anpr_ids)

                    if unsynced_security:
                        sec_ids = [r["id"] for r in unsynced_security]
                        placeholders = ",".join("?" * len(sec_ids))
                        cursor.execute(f"UPDATE security_events SET synced = 1 WHERE id IN ({placeholders})", sec_ids)

                    conn.commit()
                    logger.info(f"Offline sync completed: {count_synced} new events synced to central export archive.")

                conn.close()
                return {"synced_count": count_synced, "status": "success"}
            except Exception as e:
                logger.error(f"Error during offline sync: {e}")
                return {"error": str(e), "status": "failed"}

    def get_sync_status(self) -> dict:
        """Returns statistics on total, synced, and pending events."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM intrusion_events")
                total_intrusions = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM intrusion_events WHERE synced = 1")
                synced_intrusions = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM anpr_events")
                total_anpr = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM anpr_events WHERE synced = 1")
                synced_anpr = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM security_events")
                total_security = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM security_events WHERE synced = 1")
                synced_security = cursor.fetchone()[0]

                conn.close()

                total_events = total_intrusions + total_anpr + total_security
                synced_events = synced_intrusions + synced_anpr + synced_security
                pending_sync = total_events - synced_events

                return {
                    "total_intrusion_events": total_intrusions,
                    "total_anpr_events": total_anpr,
                    "total_security_events": total_security,
                    "total_events": total_events,
                    "synced_events": synced_events,
                    "pending_sync": pending_sync,
                    "last_sync_timestamp": self._last_sync_timestamp or "Never"
                }
            except Exception as e:
                logger.error(f"Error getting sync status: {e}")
                return {
                    "total_intrusion_events": 0,
                    "total_anpr_events": 0,
                    "total_security_events": 0,
                    "total_events": 0,
                    "synced_events": 0,
                    "pending_sync": 0,
                    "last_sync_timestamp": "Error"
                }

    def get_total_counts(self, camera_id: str = None) -> dict:
        """Fast helper returning total counts for all event types, optionally per-camera."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if camera_id:
                    cursor.execute("SELECT COUNT(*) FROM intrusion_events WHERE camera_id = ?", (camera_id,))
                    total_intrusions = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM anpr_events WHERE camera_id = ?", (camera_id,))
                    total_anpr = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM security_events WHERE camera_id = ?", (camera_id,))
                    total_security = cursor.fetchone()[0]
                else:
                    cursor.execute("SELECT COUNT(*) FROM intrusion_events")
                    total_intrusions = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM anpr_events")
                    total_anpr = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM security_events")
                    total_security = cursor.fetchone()[0]
                conn.close()
                return {
                    "total_intrusions": total_intrusions,
                    "total_anpr": total_anpr,
                    "total_security": total_security
                }
            except Exception as e:
                logger.error(f"Error fetching total counts: {e}")
                return {"total_intrusions": 0, "total_anpr": 0, "total_security": 0}

    def get_analytics_summary(self) -> dict:
        """Calculates real, authentic statistical metrics derived solely from production DB events."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # 1. Total events by camera
                cursor.execute("""
                    SELECT camera_id, COUNT(*) as cnt FROM (
                        SELECT camera_id FROM intrusion_events
                        UNION ALL
                        SELECT camera_id FROM anpr_events
                        UNION ALL
                        SELECT camera_id FROM security_events
                    ) GROUP BY camera_id
                """)
                events_per_cam = {row["camera_id"]: row["cnt"] for row in cursor.fetchall()}

                # 2. Event types breakdown
                cursor.execute("SELECT COUNT(*) FROM intrusion_events")
                intrusions_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM anpr_events WHERE plate_text IS NOT NULL AND plate_text != 'N/A' AND plate_text != 'PLATE NOT READ'")
                anpr_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT event_type, COUNT(*) as cnt FROM security_events GROUP BY event_type")
                sec_types = {row["event_type"]: row["cnt"] for row in cursor.fetchall()}

                # 3. ANPR Verified vs Detected
                cursor.execute("SELECT COUNT(*) FROM anpr_events WHERE (confidence >= 0.45 OR validation_status = 'VERIFIED') AND plate_text IS NOT NULL AND plate_text != 'N/A' AND plate_text != 'PLATE NOT READ'")
                verified_plates = cursor.fetchone()[0]

                # 4. Hourly distribution for today / recent events
                cursor.execute("""
                    SELECT substr(timestamp, 12, 2) as hour, COUNT(*) as cnt
                    FROM (
                        SELECT timestamp FROM intrusion_events
                        UNION ALL
                        SELECT timestamp FROM anpr_events
                        UNION ALL
                        SELECT timestamp FROM security_events
                    )
                    WHERE timestamp IS NOT NULL AND length(timestamp) >= 13
                    GROUP BY hour ORDER BY hour ASC
                """)
                hourly = {row["hour"]: row["cnt"] for row in cursor.fetchall()}

                conn.close()
                return {
                    "events_per_camera": events_per_cam,
                    "event_breakdown": {
                        "intrusion": intrusions_cnt,
                        "anpr": anpr_cnt,
                        "suspicious_activity": sec_types.get("suspicious_activity", 0),
                        "night_movement": sec_types.get("night_movement", 0)
                    },
                    "verified_plates_count": verified_plates,
                    "total_anpr_reads": anpr_cnt,
                    "hourly_distribution": hourly
                }
            except Exception as e:
                logger.error(f"Error computing analytics summary: {e}")
                return {
                    "events_per_camera": {},
                    "event_breakdown": {},
                    "verified_plates_count": 0,
                    "total_anpr_reads": 0,
                    "hourly_distribution": {}
                }



# Global singleton database manager instance
db_manager = DatabaseManager()
