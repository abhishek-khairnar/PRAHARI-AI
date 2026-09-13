import os
import sqlite3
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger("PRAHARI-DB")

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "prahari_events.db")
DB_PATH = os.getenv("PRAHARI_DB_PATH", DEFAULT_DB_PATH)
SYNC_EXPORT_PATH = os.getenv("PRAHARI_SYNC_PATH", os.path.join(os.path.dirname(__file__), "synced_events.json"))


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager for PRAHARI-AI.
    Provides persistent local storage for intrusion alerts, ANPR reads, and system events
    with an offline-first sync engine.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("PRAHARI_DB_PATH", DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        self._last_sync_timestamp = None
        self._init_db()

    def set_db_path(self, db_path: str):
        """Allows dynamically redirecting the database path (e.g. for isolated test suites)."""
        with self._lock:
            self.db_path = db_path
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

            # 5. Admin Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('SUPER_ADMIN', 'ADMIN', 'SUPERVISOR', 'OFFICER')),
                    is_active INTEGER DEFAULT 1,
                    must_change_password INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )
            """)

            # Safe migration for must_change_password
            try:
                cursor.execute("ALTER TABLE admin_users ADD COLUMN must_change_password INTEGER DEFAULT 0")
            except Exception:
                pass

            # 6. Admin Camera Configuration Table (Persistent storage for AI toggles and zone assignment)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_camera_config (
                    camera_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    location_zone TEXT NOT NULL,
                    ai_enabled INTEGER DEFAULT 1,
                    anpr_enabled INTEGER DEFAULT 1,
                    night_detection INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)

            # 7. Admin Zones Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_name TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    zone_type TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'INFO')),
                    is_enabled INTEGER DEFAULT 1,
                    fence_direction TEXT DEFAULT 'BOTH',
                    fence_ratio REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 8. Admin Alert Rules Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT UNIQUE NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'INFO')),
                    cooldown_seconds INTEGER DEFAULT 10,
                    requires_ack INTEGER DEFAULT 1,
                    is_enabled INTEGER DEFAULT 1,
                    description TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # 9. Admin Incidents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_code TEXT UNIQUE NOT NULL,
                    event_id INTEGER,
                    event_table TEXT DEFAULT 'security_events',
                    camera_id TEXT NOT NULL,
                    zone_name TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'DISMISSED')),
                    assigned_officer_id INTEGER,
                    assigned_officer_name TEXT,
                    evidence_snapshot TEXT,
                    notes TEXT,
                    detected_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_by TEXT,
                    resolved_at TEXT
                )
            """)

            # Safe migration for detected_at in admin_incidents
            try:
                cursor.execute("ALTER TABLE admin_incidents ADD COLUMN detected_at TEXT")
            except Exception:
                pass

            # 10. Admin Audit Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor_user_id INTEGER,
                    actor_username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    result TEXT NOT NULL CHECK(result IN ('SUCCESS', 'FAILURE', 'DENIED')),
                    description TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_users_user ON admin_users (username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_incidents_status ON admin_incidents (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_incidents_cam ON admin_incidents (camera_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_ts ON admin_audit_logs (timestamp DESC)")

            # Seed default Camera Config if empty
            cursor.execute("SELECT COUNT(*) FROM admin_camera_config")
            if cursor.fetchone()[0] == 0:
                now_seed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                default_cam_configs = [
                    ("CAM-01", "Border Post Alpha", "Border Restricted Zone", 1, 1, 0, now_seed),
                    ("CAM-02", "Night Surveillance Bravo", "Night Checkpoint Bravo", 1, 0, 1, now_seed),
                    ("CAM-03", "Perimeter Activity Charlie", "Perimeter Patrol Area", 1, 0, 0, now_seed),
                    ("CAM-04", "Urban Facility Delta", "Facility Observation Delta", 1, 1, 0, now_seed)
                ]
                cursor.executemany("""
                    INSERT INTO admin_camera_config (camera_id, name, location_zone, ai_enabled, anpr_enabled, night_detection, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, default_cam_configs)

            # Seed default Alert Rules if empty
            cursor.execute("SELECT COUNT(*) FROM admin_alert_rules")
            if cursor.fetchone()[0] == 0:
                now_seed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                default_rules = [
                    ("border_intrusion", "CRITICAL", 10, 1, 1, "Perimeter virtual fence intrusion detected", now_seed),
                    ("repeated_intrusion", "CRITICAL", 5, 1, 1, "Multiple consecutive boundary violations", now_seed),
                    ("suspicious_activity", "HIGH", 15, 1, 1, "Irregular dwell or suspicious movement detected", now_seed),
                    ("loitering", "HIGH", 20, 1, 1, "Extended stationary dwell in protected zone", now_seed),
                    ("night_movement", "HIGH", 15, 1, 1, "Unauthorized night luminance movement alert", now_seed),
                    ("anpr_detection", "MEDIUM", 5, 0, 1, "License plate recognized by ANPR pipeline", now_seed),
                    ("face_detected", "INFO", 5, 0, 1, "Facial entity isolated by YuNet detector", now_seed)
                ]
                cursor.executemany("""
                    INSERT INTO admin_alert_rules (event_type, severity, cooldown_seconds, requires_ack, is_enabled, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, default_rules)

            # Seed default Zones if empty
            cursor.execute("SELECT COUNT(*) FROM admin_zones")
            if cursor.fetchone()[0] == 0:
                now_seed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                default_zones = [
                    ("Border Restricted Zone", "CAM-01", "RESTRICTED", "CRITICAL", 1, "IN", 0.70, now_seed, now_seed),
                    ("Night Checkpoint Bravo", "CAM-02", "CHECKPOINT", "HIGH", 1, "BOTH", 0.65, now_seed, now_seed),
                    ("Perimeter Patrol Area", "CAM-03", "PATROL", "HIGH", 1, "BOTH", 0.60, now_seed, now_seed),
                    ("Facility Observation Delta", "CAM-04", "OBSERVATION", "MEDIUM", 1, "BOTH", 0.70, now_seed, now_seed)
                ]
                cursor.executemany("""
                    INSERT INTO admin_zones (zone_name, camera_id, zone_type, severity, is_enabled, fence_direction, fence_ratio, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, default_zones)

            # Seed bootstrap superadmin user if empty
            cursor.execute("SELECT COUNT(*) FROM admin_users")
            if cursor.fetchone()[0] == 0:
                try:
                    import bcrypt
                    admin_user = os.getenv("PRAHARI_ADMIN_USERNAME", "superadmin")
                    admin_pass = os.getenv("PRAHARI_ADMIN_PASSWORD", "Admin@Prahari2026!")
                    pw_hash = bcrypt.hashpw(admin_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    now_seed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("""
                        INSERT INTO admin_users (username, password_hash, full_name, role, is_active, must_change_password, created_at)
                        VALUES (?, ?, ?, 'SUPER_ADMIN', 1, 1, ?)
                    """, (admin_user, pw_hash, "System Super Administrator", now_seed))
                    logger.info(f"[AdminAuth] Bootstrapped initial SUPER_ADMIN account: '{admin_user}' (First-login rotation required)")
                except Exception as ex:
                    logger.warning(f"[AdminAuth] Failed to bootstrap superadmin user: {ex}")

            # Seed initial demo incidents ONLY when explicitly enabled by environment configuration
            # In standard production deployments, operational incidents MUST originate from live surveillance events
            demo_seed_enabled = os.getenv("PRAHARI_DEMO_SEED", "").lower() in ("true", "1", "yes") or os.getenv("PRAHARI_ENV", "").lower() == "development_demo"
            cursor.execute("SELECT COUNT(*) FROM admin_incidents")
            if cursor.fetchone()[0] == 0 and demo_seed_enabled:
                now_seed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    SELECT id, timestamp, camera_id, event_type, validation_status, snapshot_path, details
                    FROM security_events
                    ORDER BY id DESC LIMIT 4
                """)
                sec_rows = cursor.fetchall()
                code_idx = 101
                for s_row in sec_rows:
                    inc_code = f"INC-{code_idx}"
                    status = "NEW" if code_idx % 2 == 1 else "ACKNOWLEDGED"
                    severity = "CRITICAL" if "intrusion" in s_row["event_type"].lower() else "HIGH"
                    cursor.execute("""
                        INSERT INTO admin_incidents (
                            incident_code, event_id, event_table, camera_id, zone_name, event_type, severity, status, evidence_snapshot, notes, detected_at, created_at, updated_at
                        ) VALUES (?, ?, 'security_events', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (inc_code, s_row["id"], s_row["camera_id"], "Restricted Perimeter", s_row["event_type"], severity, status, s_row["snapshot_path"], "Auto-linked from security event pipeline", s_row["timestamp"], s_row["timestamp"], now_seed))
                    code_idx += 1

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
                event_id = cursor.lastrowid
                if event_id > 0:
                    self._evaluate_incident_policy(
                        conn,
                        event_table="intrusion_events",
                        event_id=event_id,
                        event_type="border_intrusion",
                        camera_id=camera_id,
                        timestamp=timestamp,
                        snapshot_path=snapshot_path,
                        details=f"{object_type} #{object_id} crossed virtual fence [{direction}]",
                        object_type=object_type,
                        object_id=object_id
                    )
                conn.commit()
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
                event_id = cursor.lastrowid
                if event_id > 0:
                    self._evaluate_incident_policy(
                        conn,
                        event_table="security_events",
                        event_id=event_id,
                        event_type=event_type,
                        camera_id=camera_id,
                        timestamp=timestamp,
                        snapshot_path=snapshot_path,
                        details=details or f"{event_type} detected on {camera_id}",
                        object_type=object_type,
                        object_id=object_id
                    )
                conn.commit()
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

    # ─── Admin Users API ───

    def get_admin_user_by_username(self, username: str):
        """Fetch user by unique username."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching admin user '{username}': {e}")
                return None

    def get_admin_user_by_id(self, user_id: int):
        """Fetch user by id."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching admin user by ID {user_id}: {e}")
                return None

    def list_admin_users(self, role=None, is_active=None):
        """List all admin users, optionally filtered by role and active status (passwords omitted)."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT id, username, full_name, role, is_active, must_change_password, created_at, last_login FROM admin_users WHERE 1=1"
                params = []
                if role:
                    query += " AND role = ?"
                    params.append(role)
                if is_active is not None:
                    query += " AND is_active = ?"
                    params.append(int(is_active))
                query += " ORDER BY id ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing admin users: {e}")
                return []

    def create_admin_user(self, username: str, password_hash: str, full_name: str, role: str = "OFFICER", is_active: int = 1, must_change_password: int = 0) -> int:
        """Insert a new user account."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO admin_users (username, password_hash, full_name, role, is_active, must_change_password, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (username, password_hash, full_name, role, is_active, must_change_password, now_str))
                conn.commit()
                new_id = cursor.lastrowid
                conn.close()
                return new_id
            except Exception as e:
                logger.error(f"Error creating admin user '{username}': {e}")
                return -1

    def update_admin_user(self, user_id: int, full_name=None, role=None, is_active=None, password_hash=None, must_change_password=None) -> bool:
        """Update existing user properties."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                updates = []
                params = []
                if full_name is not None:
                    updates.append("full_name = ?")
                    params.append(full_name)
                if role is not None:
                    updates.append("role = ?")
                    params.append(role)
                if is_active is not None:
                    updates.append("is_active = ?")
                    params.append(int(is_active))
                if password_hash is not None:
                    updates.append("password_hash = ?")
                    params.append(password_hash)
                if must_change_password is not None:
                    updates.append("must_change_password = ?")
                    params.append(int(must_change_password))
                if not updates:
                    conn.close()
                    return True
                params.append(user_id)
                query = f"UPDATE admin_users SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error updating admin user {user_id}: {e}")
                return False

    def change_admin_user_password(self, user_id: int, new_password_hash: str) -> bool:
        """Rotate user password and clear must_change_password flag."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE admin_users
                    SET password_hash = ?, must_change_password = 0
                    WHERE id = ?
                """, (new_password_hash, user_id))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error changing password for user {user_id}: {e}")
                return False

    def update_admin_user_last_login(self, user_id: int):
        """Record login timestamp for user."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE admin_users SET last_login = ? WHERE id = ?", (now_str, user_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error updating last login for user {user_id}: {e}")

    def count_active_superadmins(self) -> int:
        """Count active users with SUPER_ADMIN role (used to protect against lockout)."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM admin_users WHERE role = 'SUPER_ADMIN' AND is_active = 1")
                cnt = cursor.fetchone()[0]
                conn.close()
                return cnt
            except Exception as e:
                logger.error(f"Error counting superadmins: {e}")
                return 0

    # ─── Admin Camera Configuration API ───

    def get_admin_cameras_config(self) -> list:
        """Fetch all camera configurations from SQLite."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_camera_config ORDER BY camera_id ASC")
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing camera configs: {e}")
                return []

    def get_admin_camera_config(self, camera_id: str):
        """Fetch single camera config by camera_id."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_camera_config WHERE camera_id = ?", (camera_id,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching camera config for {camera_id}: {e}")
                return None

    def update_admin_camera_config(self, camera_id: str, name=None, location_zone=None, ai_enabled=None, anpr_enabled=None, night_detection=None) -> bool:
        """Update or insert camera configuration in SQLite."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("SELECT * FROM admin_camera_config WHERE camera_id = ?", (camera_id,))
                existing = cursor.fetchone()
                if existing:
                    updates = ["updated_at = ?"]
                    params = [now_str]
                    if name is not None:
                        updates.append("name = ?")
                        params.append(name)
                    if location_zone is not None:
                        updates.append("location_zone = ?")
                        params.append(location_zone)
                    if ai_enabled is not None:
                        updates.append("ai_enabled = ?")
                        params.append(1 if ai_enabled else 0)
                    if anpr_enabled is not None:
                        updates.append("anpr_enabled = ?")
                        params.append(1 if anpr_enabled else 0)
                    if night_detection is not None:
                        updates.append("night_detection = ?")
                        params.append(1 if night_detection else 0)
                    params.append(camera_id)
                    query = f"UPDATE admin_camera_config SET {', '.join(updates)} WHERE camera_id = ?"
                    cursor.execute(query, params)
                else:
                    cursor.execute("""
                        INSERT INTO admin_camera_config (camera_id, name, location_zone, ai_enabled, anpr_enabled, night_detection, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        camera_id,
                        name or camera_id,
                        location_zone or "Default Zone",
                        1 if ai_enabled is None or ai_enabled else 0,
                        1 if anpr_enabled is None or anpr_enabled else 0,
                        1 if night_detection else 0,
                        now_str
                    ))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error updating camera config for {camera_id}: {e}")
                return False

    # ─── Admin Zones & Virtual Fences API ───

    def list_admin_zones(self, camera_id=None, is_enabled=None):
        """List configured zones and virtual fences."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT * FROM admin_zones WHERE 1=1"
                params = []
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                if is_enabled is not None:
                    query += " AND is_enabled = ?"
                    params.append(int(is_enabled))
                query += " ORDER BY camera_id ASC, id ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing zones: {e}")
                return []

    def get_admin_zone_by_id(self, zone_id: int):
        """Retrieve zone by id."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_zones WHERE id = ?", (zone_id,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching zone {zone_id}: {e}")
                return None

    def create_admin_zone(self, zone_name: str, camera_id: str, zone_type: str, severity: str = "MEDIUM", is_enabled: int = 1, fence_direction: str = "BOTH", fence_ratio: float = 0.5) -> int:
        """Create a new zone or virtual fence configuration."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO admin_zones (zone_name, camera_id, zone_type, severity, is_enabled, fence_direction, fence_ratio, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (zone_name, camera_id, zone_type, severity, is_enabled, fence_direction, fence_ratio, now_str, now_str))
                conn.commit()
                new_id = cursor.lastrowid
                conn.close()
                return new_id
            except Exception as e:
                logger.error(f"Error creating zone: {e}")
                return -1

    def update_admin_zone(self, zone_id: int, zone_name=None, zone_type=None, severity=None, is_enabled=None, fence_direction=None, fence_ratio=None) -> bool:
        """Update zone properties."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                updates = ["updated_at = ?"]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                params = [now_str]
                if zone_name is not None:
                    updates.append("zone_name = ?")
                    params.append(zone_name)
                if zone_type is not None:
                    updates.append("zone_type = ?")
                    params.append(zone_type)
                if severity is not None:
                    updates.append("severity = ?")
                    params.append(severity)
                if is_enabled is not None:
                    updates.append("is_enabled = ?")
                    params.append(int(is_enabled))
                if fence_direction is not None:
                    updates.append("fence_direction = ?")
                    params.append(fence_direction)
                if fence_ratio is not None:
                    updates.append("fence_ratio = ?")
                    params.append(float(fence_ratio))
                params.append(zone_id)
                query = f"UPDATE admin_zones SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error updating zone {zone_id}: {e}")
                return False

    def delete_admin_zone(self, zone_id: int) -> bool:
        """Delete a zone."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM admin_zones WHERE id = ?", (zone_id,))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error deleting zone {zone_id}: {e}")
                return False

    # ─── Admin Alert Rules API ───

    def list_admin_alert_rules(self):
        """List all configured alert rules."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_alert_rules ORDER BY id ASC")
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing alert rules: {e}")
                return []

    def get_admin_alert_rule(self, rule_id_or_type):
        """Retrieve alert rule by id or event_type."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if isinstance(rule_id_or_type, int) or (isinstance(rule_id_or_type, str) and rule_id_or_type.isdigit()):
                    cursor.execute("SELECT * FROM admin_alert_rules WHERE id = ?", (int(rule_id_or_type),))
                else:
                    cursor.execute("SELECT * FROM admin_alert_rules WHERE event_type = ?", (str(rule_id_or_type),))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching alert rule {rule_id_or_type}: {e}")
                return None

    def update_admin_alert_rule(self, rule_id: int, severity=None, cooldown_seconds=None, requires_ack=None, is_enabled=None, description=None) -> bool:
        """Update an alert rule's policy attributes."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                updates = ["updated_at = ?"]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                params = [now_str]
                if severity is not None:
                    updates.append("severity = ?")
                    params.append(severity)
                if cooldown_seconds is not None:
                    updates.append("cooldown_seconds = ?")
                    params.append(int(cooldown_seconds))
                if requires_ack is not None:
                    updates.append("requires_ack = ?")
                    params.append(int(requires_ack))
                if is_enabled is not None:
                    updates.append("is_enabled = ?")
                    params.append(int(is_enabled))
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                params.append(rule_id)
                query = f"UPDATE admin_alert_rules SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error updating alert rule {rule_id}: {e}")
                return False

    # ─── Admin Incident Management API ───

    def list_admin_incidents(self, status=None, severity=None, camera_id=None, limit: int = 50, offset: int = 0):
        """List incidents with filtering and pagination."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT * FROM admin_incidents WHERE 1=1"
                params = []
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if severity:
                    query += " AND severity = ?"
                    params.append(severity)
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                query += " ORDER BY id DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing incidents: {e}")
                return []

    def get_admin_incident_by_id(self, incident_id: int):
        """Retrieve single incident details."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM admin_incidents WHERE id = ?", (incident_id,))
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error fetching incident {incident_id}: {e}")
                return None

    def _evaluate_incident_policy(
        self,
        conn,
        event_table: str,
        event_id: int,
        event_type: str,
        camera_id: str,
        timestamp: str,
        snapshot_path: str = None,
        details: str = None,
        object_type: str = None,
        object_id: int = None
    ):
        """
        Authoritative event-to-incident correlation and alert policy engine.
        Evaluates active admin_alert_rules for event_type, checks deduplication / cooldown,
        and creates an admin_incidents record if authorized by security policy.
        """
        try:
            cursor = conn.cursor()
            # 1. Look up alert rule for event_type (or fallback to related category)
            cursor.execute("SELECT * FROM admin_alert_rules WHERE event_type = ?", (event_type,))
            rule = cursor.fetchone()
            if not rule:
                if "intrusion" in event_type.lower():
                    cursor.execute("SELECT * FROM admin_alert_rules WHERE event_type = 'border_intrusion'")
                    rule = cursor.fetchone()
                elif "loiter" in event_type.lower():
                    cursor.execute("SELECT * FROM admin_alert_rules WHERE event_type = 'loitering'")
                    rule = cursor.fetchone()
                elif "suspicious" in event_type.lower():
                    cursor.execute("SELECT * FROM admin_alert_rules WHERE event_type = 'suspicious_activity'")
                    rule = cursor.fetchone()

            if not rule:
                return None

            # 2. Check if rule is enabled
            if not rule["is_enabled"]:
                logger.info(f"[IncidentPolicy] Rule for '{event_type}' is disabled. Suppressed incident creation.")
                return None

            severity = rule["severity"]
            cooldown_seconds = rule["cooldown_seconds"] or 10

            # 3. Deduplication Check 1: Has an incident already been created for this exact event?
            cursor.execute("SELECT id FROM admin_incidents WHERE event_table = ? AND event_id = ?", (event_table, event_id))
            existing_event_inc = cursor.fetchone()
            if existing_event_inc:
                return existing_event_inc[0]

            # 4. Deduplication Check 2: Cooldown window on (camera_id, event_type)
            cursor.execute("""
                SELECT id, detected_at, created_at FROM admin_incidents
                WHERE camera_id = ? AND event_type = ? AND status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')
                ORDER BY id DESC LIMIT 1
            """, (camera_id, event_type))
            recent_inc = cursor.fetchone()
            if recent_inc:
                inc_time_str = recent_inc["detected_at"] or recent_inc["created_at"]
                try:
                    inc_dt = datetime.strptime(inc_time_str, "%Y-%m-%d %H:%M:%S")
                    evt_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    delta = abs((evt_dt - inc_dt).total_seconds())
                    if delta < cooldown_seconds:
                        logger.info(f"[IncidentPolicy] Cooldown active for {camera_id}:{event_type} ({delta:.1f}s < {cooldown_seconds}s). Correlating into incident #{recent_inc['id']}.")
                        return recent_inc[0]
                except Exception:
                    pass

            # 5. Determine zone name
            cursor.execute("SELECT zone_name FROM admin_zones WHERE camera_id = ? AND is_enabled = 1 LIMIT 1", (camera_id,))
            z_row = cursor.fetchone()
            if z_row and z_row["zone_name"]:
                zone_name = z_row["zone_name"]
            else:
                cursor.execute("SELECT location_zone FROM admin_camera_config WHERE camera_id = ?", (camera_id,))
                c_row = cursor.fetchone()
                zone_name = c_row["location_zone"] if c_row and c_row["location_zone"] else f"{camera_id} Monitored Zone"

            # 6. Generate sequential incident code
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM admin_incidents")
            next_id = cursor.fetchone()[0]
            inc_code = f"INC-{next_id:04d}"

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            detected_time = timestamp if timestamp else now_str

            cursor.execute("""
                INSERT INTO admin_incidents (
                    incident_code, event_id, event_table, camera_id, zone_name, event_type,
                    severity, status, evidence_snapshot, notes, detected_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?, ?, ?, ?)
            """, (
                inc_code, event_id, event_table, camera_id, zone_name, event_type,
                severity, snapshot_path, details, detected_time, now_str, now_str
            ))
            new_inc_id = cursor.lastrowid
            logger.warning(f"🚨 [NEW INCIDENT {inc_code}] Created from {event_table}:{event_id} ({event_type} on {camera_id}, Severity={severity})")
            return new_inc_id
        except Exception as ex:
            logger.error(f"[IncidentPolicy] Failed to evaluate event {event_table}:{event_id} - {ex}")
            return None

    def evaluate_and_create_incident_from_event(
        self,
        event_table: str,
        event_id: int,
        event_type: str,
        camera_id: str,
        timestamp: str,
        snapshot_path: str = None,
        details: str = None,
        object_type: str = None,
        object_id: int = None
    ):
        """External thread-safe method to evaluate policy and create incident for an existing event."""
        with self._lock:
            try:
                conn = self._get_connection()
                inc_id = self._evaluate_incident_policy(
                    conn, event_table, event_id, event_type, camera_id, timestamp, snapshot_path, details, object_type, object_id
                )
                conn.commit()
                conn.close()
                return inc_id
            except Exception as e:
                logger.error(f"Error in evaluate_and_create_incident_from_event: {e}")
                return None

    def create_admin_incident(self, incident_code: str = None, camera_id: str = "CAM-01", event_type: str = "security_alert", severity: str = "HIGH", status: str = "NEW", event_id=None, event_table: str = "security_events", zone_name=None, assigned_officer_id=None, assigned_officer_name=None, evidence_snapshot=None, notes=None, detected_at: str = None) -> int:
        """Create a new operational incident from an event or manual entry with persistent monotonic ID."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if not incident_code:
                    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM admin_incidents")
                    next_id = cursor.fetchone()[0]
                    incident_code = f"INC-{next_id:04d}"
                det_time = detected_at if detected_at else now_str
                cursor.execute("""
                    INSERT INTO admin_incidents (
                        incident_code, event_id, event_table, camera_id, zone_name, event_type, severity, status, assigned_officer_id, assigned_officer_name, evidence_snapshot, notes, detected_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (incident_code, event_id, event_table, camera_id, zone_name, event_type, severity, status, assigned_officer_id, assigned_officer_name, evidence_snapshot, notes, det_time, now_str, now_str))
                conn.commit()
                new_id = cursor.lastrowid
                conn.close()
                return new_id
            except Exception as e:
                logger.error(f"Error creating incident: {e}")
                return -1

    def update_admin_incident(self, incident_id: int, status=None, assigned_officer_id=None, assigned_officer_name=None, notes=None, resolved_by=None) -> bool:
        """Update incident lifecycle state, officer assignment, or append investigator notes."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updates = ["updated_at = ?"]
                params = [now_str]
                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                    if status == "RESOLVED":
                        updates.append("resolved_at = ?")
                        params.append(now_str)
                        if resolved_by:
                            updates.append("resolved_by = ?")
                            params.append(resolved_by)
                if assigned_officer_id is not None:
                    updates.append("assigned_officer_id = ?")
                    params.append(assigned_officer_id)
                if assigned_officer_name is not None:
                    updates.append("assigned_officer_name = ?")
                    params.append(assigned_officer_name)
                if notes is not None:
                    # Append timestamped notes
                    cursor.execute("SELECT notes FROM admin_incidents WHERE id = ?", (incident_id,))
                    existing_row = cursor.fetchone()
                    prev = existing_row["notes"] if existing_row and existing_row["notes"] else ""
                    appended_note = f"[{now_str}] {notes}" if not prev else f"{prev}\n[{now_str}] {notes}"
                    updates.append("notes = ?")
                    params.append(appended_note)
                params.append(incident_id)
                query = f"UPDATE admin_incidents SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Error updating incident {incident_id}: {e}")
                return False

    def count_admin_incidents_summary(self) -> dict:
        """Retrieve authoritative count of incidents grouped by status and severity, guaranteed consistent."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status, COUNT(*) as cnt FROM admin_incidents GROUP BY status")
                status_counts = {r["status"]: r["cnt"] for r in cursor.fetchall()}
                for st in ["NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"]:
                    status_counts.setdefault(st, 0)
                cursor.execute("SELECT COUNT(*) FROM admin_incidents WHERE status IN ('NEW', 'ACKNOWLEDGED', 'INVESTIGATING')")
                open_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM admin_incidents")
                total_count = cursor.fetchone()[0]
                conn.close()
                return {
                    "total": total_count,
                    "open": open_count,
                    "closed": status_counts["RESOLVED"] + status_counts["DISMISSED"],
                    "by_status": status_counts
                }
            except Exception as e:
                logger.error(f"Error summarizing incidents: {e}")
                empty_counts = {s: 0 for s in ["NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"]}
                return {"total": 0, "open": 0, "closed": 0, "by_status": empty_counts}

    def count_admin_incidents_by_query(self, status=None, severity=None, camera_id=None) -> int:
        """Count total incidents matching filter query (for pagination)."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM admin_incidents WHERE 1=1"
                params = []
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if severity:
                    query += " AND severity = ?"
                    params.append(severity)
                if camera_id:
                    query += " AND camera_id = ?"
                    params.append(camera_id)
                cursor.execute(query, params)
                cnt = cursor.fetchone()[0]
                conn.close()
                return cnt
            except Exception as e:
                logger.error(f"Error counting incidents: {e}")
                return 0

    # ─── Admin Audit Logs API ───

    def log_audit_event(self, actor_username: str, role: str, action: str, resource_type: str, resource_id=None, result: str = "SUCCESS", description=None, actor_user_id=None) -> int:
        """Append an immutable audit entry to admin_audit_logs."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO admin_audit_logs (timestamp, actor_user_id, actor_username, role, action, resource_type, resource_id, result, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (now_str, actor_user_id, actor_username, role, action, resource_type, str(resource_id) if resource_id is not None else None, result, description))
                conn.commit()
                log_id = cursor.lastrowid
                conn.close()
                return log_id
            except Exception as e:
                logger.error(f"Error logging audit event: {e}")
                return -1

    def list_admin_audit_logs(self, limit: int = 100, offset: int = 0, action=None, actor=None):
        """Fetch audit log records with filtering and pagination."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT * FROM admin_audit_logs WHERE 1=1"
                params = []
                if action:
                    query += " AND action LIKE ?"
                    params.append(f"%{action}%")
                if actor:
                    query += " AND actor_username LIKE ?"
                    params.append(f"%{actor}%")
                query += " ORDER BY id DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing audit logs: {e}")
                return []

    def count_admin_audit_logs_by_query(self, action=None, actor=None) -> int:
        """Count total audit logs matching filter query (for pagination)."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM admin_audit_logs WHERE 1=1"
                params = []
                if action:
                    query += " AND action LIKE ?"
                    params.append(f"%{action}%")
                if actor:
                    query += " AND actor_username LIKE ?"
                    params.append(f"%{actor}%")
                cursor.execute(query, params)
                cnt = cursor.fetchone()[0]
                conn.close()
                return cnt
            except Exception as e:
                logger.error(f"Error counting audit logs: {e}")
                return 0

    # ─── System & Database Health Telemetry ───

    def get_database_health(self) -> dict:
        """Fetch real-time SQLite database health telemetry."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode;")
                journal = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM intrusion_events")
                intrusions = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM anpr_events")
                anprs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM security_events")
                secs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM admin_users")
                users = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM admin_incidents")
                incidents = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM admin_audit_logs")
                audits = cursor.fetchone()[0]
                conn.close()

                db_size_mb = 0.0
                if os.path.exists(self.db_path):
                    db_size_mb = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)

                return {
                    "status": "ONLINE",
                    "mode": journal.upper(),
                    "path": self.db_path,
                    "size_mb": db_size_mb,
                    "table_counts": {
                        "intrusion_events": intrusions,
                        "anpr_events": anprs,
                        "security_events": secs,
                        "admin_users": users,
                        "admin_incidents": incidents,
                        "admin_audit_logs": audits
                    }
                }
            except Exception as e:
                logger.error(f"Database health check error: {e}")
                return {
                    "status": "ERROR",
                    "error": str(e),
                    "path": self.db_path
                }



# Global singleton database manager instance
db_manager = DatabaseManager()

