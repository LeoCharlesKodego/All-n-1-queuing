"""SQLite access layer. All database access in the app goes through this module."""
import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH, DATA_DIR, MEDIA_DIR, BACKUP_DIR, DEFAULT_SETTINGS

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    is_express INTEGER NOT NULL DEFAULT 0,
    open_from TEXT,
    open_to TEXT,
    cut_off_time TEXT,
    ask_account_number INTEGER NOT NULL DEFAULT 0,
    queue_alert_threshold INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'closed',
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS counter_services (
    counter_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    PRIMARY KEY (counter_id, service_id)
);
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL,
    counter_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS priority_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_fil TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    service_id INTEGER NOT NULL,
    number TEXT NOT NULL,
    seq INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    priority_type_id INTEGER,
    account_number TEXT,
    status TEXT NOT NULL DEFAULT 'waiting',
    counter_id INTEGER,
    staff_id INTEGER,
    issued_at TEXT NOT NULL,
    called_at TEXT,
    serving_at TEXT,
    done_at TEXT,
    recall_count INTEGER NOT NULL DEFAULT 0,
    last_event_at TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_business_date ON tickets(business_date);
CREATE TABLE IF NOT EXISTS ticket_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    counter_id INTEGER,
    staff_id INTEGER,
    created_at TEXT NOT NULL,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON ticket_events(ticket_id);
CREATE TABLE IF NOT EXISTS daily_counters (
    service_id INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    last_seq INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service_id, business_date)
);
CREATE TABLE IF NOT EXISTS media_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    layout INTEGER NOT NULL DEFAULT 60,
    image_duration INTEGER NOT NULL DEFAULT 10,
    banner_text_en TEXT NOT NULL DEFAULT '',
    banner_text_fil TEXT NOT NULL DEFAULT '',
    schedule TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    staff_id INTEGER,
    counter_id INTEGER,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    identifier TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS counter_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    counter_id INTEGER,
    staff_id INTEGER,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

MEDIA_ROW = """INSERT OR IGNORE INTO media_settings (id, layout, image_duration) VALUES (1, 60, 10)"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_dirs()
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            conn.executescript(SCHEMA_V1)
            conn.execute(MEDIA_ROW)
            conn.execute("PRAGMA user_version=1")
        else:
            conn.execute(MEDIA_ROW)
    finally:
        conn.close()


# --- settings -------------------------------------------------------------

def get_settings(conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        data = dict(DEFAULT_SETTINGS)
        for row in rows:
            try:
                data[row["key"]] = json.loads(row["value"])
            except (ValueError, TypeError):
                data[row["key"]] = row["value"]
        return data
    finally:
        if own:
            conn.close()


def save_settings(updates: dict) -> dict:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for key, value in updates.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
        conn.execute("COMMIT")
        return get_settings(conn)
    finally:
        conn.close()


def setup_complete() -> bool:
    conn = connect()
    try:
        return bool(get_settings(conn).get("setup_complete"))
    finally:
        conn.close()


# --- serialization helpers ------------------------------------------------

def rowdict(row) -> dict | None:
    return dict(row) if row is not None else None


def all_rows(conn, sql, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one_row(conn, sql, params=()) -> dict | None:
    return rowdict(conn.execute(sql, params).fetchone())
