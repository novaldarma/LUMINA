"""
LUMINA — SQLite Database Layer

Stores:
- CCTV and activity logs
- Patient reference photos
- GPS safe-zone configuration
- Patient location history
- SOS events
- Patient stage/emotion configuration (Stage Adaptation Agent)
"""

import os
import sqlite3
from typing import Optional


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "lumina.db",
)


def get_connection() -> sqlite3.Connection:
    """Create and return a SQLite connection."""

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")

    return connection


def init_db() -> None:
    """Create all required database tables."""

    connection = get_connection()
    cursor = connection.cursor()

    # CCTV, SOS, GPS, and activity timeline
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime')),
            alert_status TEXT NOT NULL DEFAULT 'Safe',
            activity_description TEXT,
            narrative_report TEXT,
            snapshot_image TEXT
        )
    """)

    # Patient reference photos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reference_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # One home safe-zone configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS safe_zone_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            home_latitude REAL,
            home_longitude REAL,
            radius_meters REAL NOT NULL DEFAULT 100,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO safe_zone_config (
            id,
            radius_meters,
            enabled
        )
        VALUES (1, 100, 1)
    """)

    # GPS location history from the patient's device
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime')),
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL,
            distance_from_home REAL,
            inside_safe_zone INTEGER,
            device_id TEXT DEFAULT 'patient-device'
        )
    """)

    # SOS event history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sos_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            triggered_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime')),
            latitude REAL,
            longitude REAL,
            handled INTEGER NOT NULL DEFAULT 0
        )
    """)

    # -------------------------------------------------------
    # PATIENT CONFIG — Stage Adaptation & Emotion Agent
    # Single-row table (id=1) storing patient profile
    # -------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            patient_name TEXT NOT NULL DEFAULT 'Grandma',
            patient_stage INTEGER NOT NULL DEFAULT 1
                CHECK (patient_stage BETWEEN 1 AND 3),
            emotion_state TEXT NOT NULL DEFAULT 'calm'
                CHECK (emotion_state IN ('calm', 'anxious', 'confused')),
            caregiver_notes TEXT,
            updated_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO patient_config (
            id,
            patient_name,
            patient_stage,
            emotion_state
        )
        VALUES (1, 'Grandma', 1, 'calm')
    """)

    # -------------------------------------------------------
    # MEMORIES — Family-to-Patient Photo Memories (TASK 3)
    # Separate table, NOT used by face recognition
    # -------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_path TEXT NOT NULL,
            person_name TEXT NOT NULL,
            relationship TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime'))
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# ACTIVITY LOGS
# =========================================================

def insert_log(
    alert_status: str,
    activity_description: str,
    narrative_report: str,
    snapshot_image: str = "",
) -> int:
    """Insert a new activity log."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO daily_logs (
            alert_status,
            activity_description,
            narrative_report,
            snapshot_image
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            alert_status,
            activity_description,
            narrative_report,
            snapshot_image,
        ),
    )

    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return row_id


def get_all_logs(
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return activity logs, newest first."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM daily_logs
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_today_logs() -> list[dict]:
    """Return today's activity logs, oldest first."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM daily_logs
        WHERE date(timestamp) = date('now', 'localtime')
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_log_count() -> int:
    """Return total activity log count."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM daily_logs
    """)

    row = cursor.fetchone()
    connection.close()

    return int(row["total"]) if row else 0


# =========================================================
# REFERENCE PHOTOS
# =========================================================

def insert_reference_photo(
    filename: str,
    filepath: str,
) -> int:
    """Store patient reference photo metadata."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO reference_photos (
            filename,
            filepath
        )
        VALUES (?, ?)
        """,
        (filename, filepath),
    )

    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return row_id


def get_reference_photos() -> list[dict]:
    """Return all patient reference photos."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM reference_photos
        ORDER BY uploaded_at DESC
    """)

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_reference_photo_paths() -> list[str]:
    """Return reference photo file paths."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT filepath
        FROM reference_photos
    """)

    rows = cursor.fetchall()
    connection.close()

    return [row["filepath"] for row in rows]


# =========================================================
# GPS SAFE ZONE
# =========================================================

def set_safe_zone(
    home_latitude: float,
    home_longitude: float,
    radius_meters: float,
    enabled: bool = True,
) -> dict:
    """Save the home location and safe-zone radius."""

    connection = get_connection()

    connection.execute(
        """
        UPDATE safe_zone_config
        SET
            home_latitude = ?,
            home_longitude = ?,
            radius_meters = ?,
            enabled = ?,
            updated_at = datetime('now', 'localtime')
        WHERE id = 1
        """,
        (
            home_latitude,
            home_longitude,
            radius_meters,
            1 if enabled else 0,
        ),
    )

    connection.commit()
    connection.close()

    return get_safe_zone()


def get_safe_zone() -> Optional[dict]:
    """Return the current safe-zone configuration."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM safe_zone_config
        WHERE id = 1
    """)

    row = cursor.fetchone()
    connection.close()

    if not row:
        return None

    result = dict(row)
    result["enabled"] = bool(result["enabled"])

    return result


# =========================================================
# PATIENT LOCATION
# =========================================================

def insert_patient_location(
    latitude: float,
    longitude: float,
    accuracy: Optional[float],
    distance_from_home: Optional[float],
    inside_safe_zone: Optional[bool],
    device_id: str,
) -> int:
    """Store a patient-device GPS location."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO patient_locations (
            latitude,
            longitude,
            accuracy,
            distance_from_home,
            inside_safe_zone,
            device_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            latitude,
            longitude,
            accuracy,
            distance_from_home,
            (
                None
                if inside_safe_zone is None
                else 1 if inside_safe_zone else 0
            ),
            device_id,
        ),
    )

    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return row_id


def get_last_patient_location() -> Optional[dict]:
    """Return the latest patient-device GPS location."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM patient_locations
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    connection.close()

    if not row:
        return None

    result = dict(row)

    if result["inside_safe_zone"] is not None:
        result["inside_safe_zone"] = bool(
            result["inside_safe_zone"]
        )

    return result


# =========================================================
# SOS
# =========================================================

def insert_sos(
    latitude: Optional[float],
    longitude: Optional[float],
) -> int:
    """Store an SOS emergency event."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO sos_events (
            latitude,
            longitude
        )
        VALUES (?, ?)
        """,
        (latitude, longitude),
    )

    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return row_id


# =========================================================
# PATIENT CONFIG — Stage Adaptation Agent & Emotion Agent
# =========================================================

def set_patient_config(
    patient_name: Optional[str] = None,
    patient_stage: Optional[int] = None,
    emotion_state: Optional[str] = None,
    caregiver_notes: Optional[str] = None,
) -> dict:
    """
    Update the patient profile (single-row, id=1).

    Only provided fields are updated — others remain unchanged.
    Returns the full config dict after update.
    """

    connection = get_connection()

    # Build dynamic UPDATE from non-None kwargs
    fields = []
    values = []

    if patient_name is not None:
        fields.append("patient_name = ?")
        values.append(patient_name)
    if patient_stage is not None:
        fields.append("patient_stage = ?")
        values.append(patient_stage)
    if emotion_state is not None:
        fields.append("emotion_state = ?")
        values.append(emotion_state)
    if caregiver_notes is not None:
        fields.append("caregiver_notes = ?")
        values.append(caregiver_notes)

    if fields:
        fields.append("updated_at = datetime('now', 'localtime')")
        query = f"""
            UPDATE patient_config
            SET {', '.join(fields)}
            WHERE id = 1
        """
        connection.execute(query, values)
        connection.commit()

    connection.close()

    return get_patient_config()


def get_patient_config() -> Optional[dict]:
    """Return the current patient configuration (stage, emotion, name)."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM patient_config
        WHERE id = 1
    """)

    row = cursor.fetchone()
    connection.close()

    if not row:
        return None

    return dict(row)


def detect_emotion_state() -> str:
    """
    Auto-detect the patient's emotional state based on recent activity.

    Heuristics (checked in order):
      1. SOS triggered in last 30 minutes     → 'anxious'
      2. Patient left safe zone in last 30 min → 'anxious'
      3. No activity log for > 2 hours         → 'confused'
      4. Otherwise                             → 'calm'

    Returns one of: 'calm', 'anxious', 'confused'
    """

    connection = get_connection()
    cursor = connection.cursor()

    # Check 1: Recent SOS
    cursor.execute("""
        SELECT COUNT(*) AS cnt
        FROM sos_events
        WHERE triggered_at >= datetime('now', 'localtime', '-30 minutes')
    """)
    row = cursor.fetchone()
    if row and row["cnt"] > 0:
        connection.close()
        return "anxious"

    # Check 2: Recent safe-zone breach
    cursor.execute("""
        SELECT COUNT(*) AS cnt
        FROM patient_locations
        WHERE
            timestamp >= datetime('now', 'localtime', '-30 minutes')
            AND inside_safe_zone = 0
    """)
    row = cursor.fetchone()
    if row and row["cnt"] > 0:
        connection.close()
        return "anxious"

    # Check 3: No activity for > 2 hours
    cursor.execute("""
        SELECT MAX(timestamp) AS last_activity
        FROM daily_logs
    """)
    row = cursor.fetchone()
    if row and row["last_activity"]:
        cursor.execute("""
            SELECT
                CASE
                    WHEN datetime(?, 'localtime') <
                         datetime('now', 'localtime', '-2 hours')
                    THEN 1
                    ELSE 0
                END AS is_stale
        """, (row["last_activity"],))
        stale_row = cursor.fetchone()
        if stale_row and stale_row["is_stale"]:
            connection.close()
            return "confused"
    else:
        # No logs at all → confused
        connection.close()
        return "confused"

    connection.close()
    return "calm"


# =========================================================
# MEMORIES — Family-to-Patient Photo Memories (TASK 3)
# =========================================================
# This is a SEPARATE table that does NOT interact with the
# face recognition system in cctv_engine.py. Guest photos
# stored here will NEVER be used for patient identification.

def insert_memory(
    photo_path: str,
    person_name: str,
    relationship: str,
) -> int:
    """Store a memory entry (guest/relative photo + name + relationship)."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO memories (
            photo_path,
            person_name,
            relationship
        )
        VALUES (?, ?, ?)
        """,
        (photo_path, person_name, relationship),
    )

    connection.commit()
    row_id = cursor.lastrowid
    connection.close()

    return row_id


def get_memories(limit: int = 20) -> list:
    """Return recent memory entries, newest first."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM memories
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def delete_memory(memory_id: int) -> bool:
    """Delete a memory entry by ID. Returns True if deleted."""

    connection = get_connection()
    cursor = connection.cursor()

    # Get photo path first so we can delete the file
    cursor.execute("SELECT photo_path FROM memories WHERE id = ?", (memory_id,))
    row = cursor.fetchone()

    if not row:
        connection.close()
        return False

    photo_path = row["photo_path"]

    cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    connection.commit()
    connection.close()

    # Remove the photo file from disk
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except OSError:
            pass

    return True


init_db()
