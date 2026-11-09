"""Small SQLite data-access layer built only on Python's sqlite3 module."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accident_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
    created_at TEXT NOT NULL,
    UNIQUE(normalized_name, latitude, longitude)
);

CREATE TABLE IF NOT EXISTS accident_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    location_id INTEGER REFERENCES accident_locations(id) ON DELETE SET NULL,
    location_name TEXT NOT NULL,
    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
    occurred_at TEXT NOT NULL,
    accident_type TEXT NOT NULL,
    vehicle_types TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('Low', 'Medium', 'High')),
    casualties INTEGER NOT NULL DEFAULT 0 CHECK(casualties >= 0),
    description TEXT NOT NULL DEFAULT '',
    image_filename TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'verified', 'rejected')),
    review_notes TEXT NOT NULL DEFAULT '',
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS black_spots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_latitude REAL NOT NULL,
    center_longitude REAL NOT NULL,
    radius_meters INTEGER NOT NULL,
    accident_count INTEGER NOT NULL,
    high_count INTEGER NOT NULL,
    medium_count INTEGER NOT NULL,
    low_count INTEGER NOT NULL,
    casualties INTEGER NOT NULL,
    risk_score REAL NOT NULL,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('Low', 'Medium', 'High')),
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    black_spot_id INTEGER NOT NULL REFERENCES black_spots(id) ON DELETE CASCADE,
    accident_report_id INTEGER NOT NULL UNIQUE REFERENCES accident_reports(id) ON DELETE CASCADE,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('Low', 'Medium', 'High')),
    risk_score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON accident_reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_occurred_at ON accident_reports(occurred_at);
CREATE INDEX IF NOT EXISTS idx_reports_location ON accident_reports(location_name);
CREATE INDEX IF NOT EXISTS idx_reports_reporter ON accident_reports(reporter_id);
CREATE INDEX IF NOT EXISTS idx_blackspots_risk ON black_spots(risk_level);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql: str, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql: str, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql: str, params=()) -> int:
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor.lastrowid


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    now = utcnow()
    for key, value in (("cluster_radius_meters", "500"), ("minimum_cluster_size", "3")):
        db.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
    db.commit()


def ensure_admin() -> None:
    """Create the configured administrator once; never overwrite an existing password."""
    email = current_app.config["ADMIN_EMAIL"]
    if not query_one("SELECT id FROM users WHERE email = ?", (email,)):
        execute(
            "INSERT INTO users (full_name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
            (
                current_app.config["ADMIN_NAME"],
                email,
                generate_password_hash(current_app.config["ADMIN_PASSWORD"]),
                utcnow(),
            ),
        )


def setting(name: str, default: str | None = None) -> str | None:
    row = query_one("SELECT setting_value FROM app_settings WHERE setting_key = ?", (name,))
    return row["setting_value"] if row else default


def set_setting(name: str, value: str) -> None:
    now = utcnow()
    get_db().execute(
        """INSERT INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = excluded.updated_at""",
        (name, value, now),
    )
    get_db().commit()
