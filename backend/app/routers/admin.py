"""Admin panel API: dashboard, configuration, media, backups, reports."""
from fastapi import APIRouter, HTTPException, Request

from .. import db, security

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- staff ---------------------------------------------------------------

@router.get("/staff")
def list_staff(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        rows = db.all_rows(conn, """
            SELECT s.id, s.name, s.username, s.counter_id, s.is_active,
                   c.name AS counter_name
            FROM staff s LEFT JOIN counters c ON c.id=s.counter_id
            ORDER BY s.name""")
    finally:
        conn.close()
    return {"staff": rows}


def _validate_pin(pin: str) -> str:
    pin = str(pin or "").strip()
    if not (4 <= len(pin) <= 8) or not pin.isdigit():
        raise HTTPException(status_code=400, detail="invalid_pin")
    return pin


@router.post("/staff")
def create_staff(payload: dict, request: Request):
    security.require_admin(request)
    name = str(payload.get("name") or "").strip()
    username = str(payload.get("username") or "").strip()
    if not name or not username:
        raise HTTPException(status_code=400, detail="staff_fields_required")
    pin = _validate_pin(payload.get("pin"))
    conn = db.connect()
    try:
        exists = conn.execute("SELECT id FROM staff WHERE lower(username)=lower(?)", (username,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="username_taken")
        cur = conn.execute(
            "INSERT INTO staff(name, username, pin_hash, counter_id, is_active) VALUES(?,?,?,?,1)",
            (name, username, security.hash_secret(pin), payload.get("counter_id") or None))
        staff_id = cur.lastrowid
    finally:
        conn.close()
    return {"ok": True, "id": staff_id}


@router.put("/staff/{staff_id}")
def update_staff(staff_id: int, payload: dict, request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        staff = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="staff_not_found")
        name = str(payload.get("name", staff["name"])).strip() or staff["name"]
        username = str(payload.get("username", staff["username"])).strip() or staff["username"]
        taken = conn.execute(
            "SELECT id FROM staff WHERE lower(username)=lower(?) AND id<>?", (username, staff_id)).fetchone()
        if taken:
            raise HTTPException(status_code=409, detail="username_taken")
        counter_id = payload.get("counter_id", staff["counter_id"])
        is_active = payload.get("is_active", staff["is_active"])
        conn.execute(
            "UPDATE staff SET name=?, username=?, counter_id=?, is_active=? WHERE id=?",
            (name, username, counter_id or None, 1 if is_active else 0, staff_id))
        if payload.get("pin"):
            pin = _validate_pin(payload["pin"])
            conn.execute("UPDATE staff SET pin_hash=? WHERE id=?", (security.hash_secret(pin), staff_id))
            security.clear_staff_sessions(staff_id)
        if not is_active:
            security.clear_staff_sessions(staff_id)
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/staff/{staff_id}")
def deactivate_staff(staff_id: int, request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        conn.execute("UPDATE staff SET is_active=0 WHERE id=?", (staff_id,))
    finally:
        conn.close()
    security.clear_staff_sessions(staff_id)
    return {"ok": True}


@router.post("/staff/{staff_id}/pin")
def reset_pin(staff_id: int, payload: dict, request: Request):
    security.require_admin(request)
    pin = _validate_pin(payload.get("pin"))
    conn = db.connect()
    try:
        conn.execute("UPDATE staff SET pin_hash=? WHERE id=?", (security.hash_secret(pin), staff_id))
    finally:
        conn.close()
    security.clear_staff_sessions(staff_id)
    return {"ok": True}


# --- shared lookups ------------------------------------------------------

@router.get("/lookups")
def lookups(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        counters = db.all_rows(conn, "SELECT id, name, status, is_active FROM counters ORDER BY sort_order, id")
        services = db.all_rows(conn, "SELECT id, name, prefix, is_active FROM services ORDER BY sort_order, id")
    finally:
        conn.close()
    return {"counters": counters, "services": services}
