"""Password/PIN hashing, sessions, and login rate limiting."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from . import db

COOKIE_NAME = "queue_session"
SESSION_HOURS = 12
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_MINUTES = 5
PBKDF2_ROUNDS = 120_000


def hash_secret(secret: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), PBKDF2_ROUNDS).hex()
    return f"pbkdf2${PBKDF2_ROUNDS}${salt}${digest}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        _, rounds, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, AttributeError):
        return False


def utc_dt() -> datetime:
    return datetime.now(timezone.utc)


def create_session(role: str, staff_id: int | None = None, counter_id: int | None = None) -> str:
    token = secrets.token_urlsafe(32)
    conn = db.connect()
    now = utc_dt()
    try:
        conn.execute(
            "INSERT INTO sessions(token, role, staff_id, counter_id, created_at, expires_at) VALUES(?,?,?,?,?,?)",
            (token, role, staff_id, counter_id, now.isoformat(timespec="seconds"),
             (now + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")),
        )
    finally:
        conn.close()
    return token


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if not row:
            return None
        if db.parse_utc(row["expires_at"]) < utc_dt():
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
        return dict(row)
    finally:
        conn.close()


def delete_session(token: str | None) -> None:
    if not token:
        return
    conn = db.connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    finally:
        conn.close()


def clear_staff_sessions(staff_id: int) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM sessions WHERE role='staff' AND staff_id=?", (staff_id,))
    finally:
        conn.close()


def session_from_request(request: Request) -> dict | None:
    return get_session(request.cookies.get(COOKIE_NAME))


def require_admin(request: Request) -> dict:
    sess = session_from_request(request)
    if not sess or sess["role"] != "admin":
        raise HTTPException(status_code=401, detail="admin_required")
    return sess


def require_staff(request: Request) -> dict:
    sess = session_from_request(request)
    if not sess or sess["role"] != "staff":
        raise HTTPException(status_code=401, detail="staff_required")
    conn = db.connect()
    try:
        staff = conn.execute(
            "SELECT s.*, c.name AS counter_name, c.status AS counter_status FROM staff s "
            "LEFT JOIN counters c ON c.id = s.counter_id WHERE s.id=?", (sess["staff_id"],)
        ).fetchone()
        if not staff or not staff["is_active"]:
            raise HTTPException(status_code=401, detail="staff_required")
        out = dict(sess)
        out["staff"] = dict(staff)
        return out
    finally:
        conn.close()


def rate_limit_check(scope: str, identifier: str) -> None:
    cutoff = (utc_dt() - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)).isoformat(timespec="seconds")
    conn = db.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE scope=? AND identifier=? AND created_at>=?",
            (scope, identifier, cutoff),
        ).fetchone()[0]
        if count >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="too_many_attempts")
    finally:
        conn.close()


def rate_limit_fail(scope: str, identifier: str) -> None:
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO login_attempts(scope, identifier, created_at) VALUES(?,?,?)",
            (scope, identifier, utc_dt().isoformat(timespec="seconds")),
        )
    finally:
        conn.close()


def rate_limit_clear(scope: str, identifier: str) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM login_attempts WHERE scope=? AND identifier=?", (scope, identifier))
    finally:
        conn.close()


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"
