"""Admin panel API: dashboard, configuration, media, backups, reports."""
import json
import socket
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import backups, db, presets, queue, security, ws
from ..config import BACKUP_DIR, FRONTEND_DIST, MEDIA_DIR, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

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


# --- dashboard ------------------------------------------------------------

@router.get("/dashboard")
def dashboard(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        bdate = queue.business_date(settings)
        stats = queue.stats_today()
        counts = stats["counts"]
        avg = conn.execute(
            """SELECT AVG(strftime('%s', called_at) - strftime('%s', issued_at)) AS wait_s,
                      AVG(CASE WHEN done_at IS NOT NULL AND serving_at IS NOT NULL
                          THEN strftime('%s', done_at) - strftime('%s', serving_at) END) AS service_s
               FROM tickets WHERE business_date=? AND called_at IS NOT NULL""", (bdate,)).fetchone()
        counters = db.all_rows(conn, """
            SELECT c.id, c.name, c.status, c.is_active,
                   (SELECT group_concat(s.name, ', ') FROM staff s
                     WHERE s.counter_id=c.id AND s.is_active=1) AS staff_names,
                   (SELECT t.number FROM tickets t WHERE t.counter_id=c.id
                     AND t.status IN ('called','serving') ORDER BY t.id DESC LIMIT 1) AS ticket_number,
                   (SELECT t.status FROM tickets t WHERE t.counter_id=c.id
                     AND t.status IN ('called','serving') ORDER BY t.id DESC LIMIT 1) AS ticket_status,
                   (SELECT COUNT(*) FROM sessions se WHERE se.counter_id=c.id AND se.role='staff'
                     AND se.expires_at > strftime('%Y-%m-%dT%H:%M:%SZ','now')) AS logged_in
            FROM counters c ORDER BY c.sort_order, c.id""")
        alerts = db.all_rows(conn, """
            SELECT s.id, s.name, s.queue_alert_threshold AS threshold,
                   (SELECT COUNT(*) FROM tickets t WHERE t.service_id=s.id AND t.status='waiting') AS waiting
            FROM services s WHERE s.is_active=1 AND s.queue_alert_threshold > 0
            ORDER BY s.sort_order, s.id""")
        alerts = [a for a in alerts if a["waiting"] >= a["threshold"]]
        return {
            "business_date": bdate,
            "issued": stats["issued"],
            "waiting": counts.get("waiting", 0),
            "serving": counts.get("called", 0) + counts.get("serving", 0),
            "completed": counts.get("done", 0),
            "no_show": counts.get("no_show", 0),
            "cancelled": counts.get("cancelled", 0),
            "avg_wait_seconds": round(avg["wait_s"]) if avg["wait_s"] is not None else None,
            "avg_service_seconds": round(avg["service_s"]) if avg["service_s"] is not None else None,
            "counters": counters,
            "alerts": alerts,
            "media_files": len(queue.media_playlist()),
            "printer_status": settings.get("printer_status"),
            "printer_note": settings.get("printer_note"),
        }
    finally:
        conn.close()


# --- services -------------------------------------------------------------

def _clean_prefix(prefix: str) -> str:
    value = str(prefix or "").strip().upper()
    if not value or len(value) > 4 or not value.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid_prefix")
    return value


def _validate_clock(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        datetime.strptime(str(value), "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_time")
    return str(value)


def _service_payload(payload: dict, existing: dict | None = None) -> dict:
    base = existing or {}
    name = str(payload.get("name", base.get("name", ""))).strip()
    if not name:
        raise HTTPException(status_code=400, detail="service_name_required")
    prefix = _clean_prefix(payload.get("prefix", base.get("prefix", "")))
    threshold = int(payload.get("queue_alert_threshold", base.get("queue_alert_threshold", 0)) or 0)
    if threshold < 0:
        raise HTTPException(status_code=400, detail="invalid_threshold")
    return {
        "name": name,
        "prefix": prefix,
        "is_express": 1 if payload.get("is_express", base.get("is_express", 0)) else 0,
        "open_from": _validate_clock(payload.get("open_from", base.get("open_from"))),
        "open_to": _validate_clock(payload.get("open_to", base.get("open_to"))),
        "cut_off_time": _validate_clock(payload.get("cut_off_time", base.get("cut_off_time"))),
        "ask_account_number": 1 if payload.get("ask_account_number", base.get("ask_account_number", 0)) else 0,
        "queue_alert_threshold": threshold,
        "is_active": 1 if payload.get("is_active", base.get("is_active", 1)) else 0,
        "sort_order": int(payload.get("sort_order", base.get("sort_order", 0)) or 0),
    }


@router.get("/services")
def list_services(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        rows = db.all_rows(conn, """
            SELECT s.*, (SELECT COUNT(*) FROM tickets t WHERE t.service_id=s.id AND t.status='waiting') AS waiting
            FROM services s ORDER BY s.sort_order, s.id""")
    finally:
        conn.close()
    return {"services": rows}


@router.post("/services")
def create_service(payload: dict, request: Request):
    security.require_admin(request)
    data = _service_payload(payload)
    conn = db.connect()
    try:
        clash = conn.execute("SELECT id FROM services WHERE lower(prefix)=lower(?)", (data["prefix"],)).fetchone()
        if clash:
            raise HTTPException(status_code=409, detail="prefix_taken")
        cols = ", ".join(data.keys())
        marks = ", ".join("?" for _ in data)
        cur = conn.execute(f"INSERT INTO services({cols}) VALUES({marks})", list(data.values()))
        service_id = cur.lastrowid
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True, "id": service_id}


@router.put("/services/{service_id}")
def update_service(service_id: int, payload: dict, request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="service_not_found")
        data = _service_payload(payload, dict(row))
        clash = conn.execute(
            "SELECT id FROM services WHERE lower(prefix)=lower(?) AND id<>?", (data["prefix"], service_id)).fetchone()
        if clash:
            raise HTTPException(status_code=409, detail="prefix_taken")
        if not data["is_active"]:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM counters c JOIN counter_services cs ON cs.counter_id=c.id "
                "WHERE cs.service_id=? AND c.is_active=1", (service_id,)).fetchone()[0]
            if remaining == 0:
                waiting = conn.execute(
                    "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting'", (service_id,)).fetchone()[0]
                if waiting:
                    # Tickets stay in line; they can still be called through any open counter.
                    pass
        sets = ", ".join(f"{k}=?" for k in data)
        conn.execute(f"UPDATE services SET {sets} WHERE id=?", [*data.values(), service_id])
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True}


# --- counters -------------------------------------------------------------

def _counter_services(conn, counter_id: int) -> list[int]:
    return [r["service_id"] for r in conn.execute(
        "SELECT service_id FROM counter_services WHERE counter_id=? ORDER BY service_id", (counter_id,))]


@router.get("/counters")
def list_counters(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        rows = db.all_rows(conn, "SELECT * FROM counters ORDER BY sort_order, id")
        for row in rows:
            row["service_ids"] = _counter_services(conn, row["id"])
            row["staff"] = db.all_rows(
                conn, "SELECT id, name FROM staff WHERE counter_id=? AND is_active=1 ORDER BY name", (row["id"],))
    finally:
        conn.close()
    return {"counters": rows}


@router.post("/counters")
def create_counter(payload: dict, request: Request):
    security.require_admin(request)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="counter_name_required")
    service_ids = [int(x) for x in payload.get("service_ids") or []]
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO counters(name, is_active, status, sort_order) VALUES(?,?, 'closed', ?)",
            (name, 1 if payload.get("is_active", True) else 0, int(payload.get("sort_order") or 0)))
        counter_id = cur.lastrowid
        for sid in service_ids:
            conn.execute("INSERT OR IGNORE INTO counter_services(counter_id, service_id) VALUES(?,?)",
                         (counter_id, sid))
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True, "id": counter_id}


@router.put("/counters/{counter_id}")
def update_counter(counter_id: int, payload: dict, request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM counters WHERE id=?", (counter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="counter_not_found")
        name = str(payload.get("name", row["name"])).strip() or row["name"]
        is_active = 1 if payload.get("is_active", row["is_active"]) else 0
        sort_order = int(payload.get("sort_order", row["sort_order"]) or 0)
        status = row["status"] if is_active else "closed"
        conn.execute("UPDATE counters SET name=?, is_active=?, sort_order=?, status=? WHERE id=?",
                     (name, is_active, sort_order, status, counter_id))
        if "service_ids" in payload:
            conn.execute("DELETE FROM counter_services WHERE counter_id=?", (counter_id,))
            for sid in [int(x) for x in payload.get("service_ids") or []]:
                conn.execute("INSERT OR IGNORE INTO counter_services(counter_id, service_id) VALUES(?,?)",
                             (counter_id, sid))
        if not is_active:
            conn.execute("DELETE FROM sessions WHERE counter_id=?", (counter_id,))
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True}


# --- priority rules -------------------------------------------------------

@router.get("/priorities")
def list_priorities(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        rows = db.all_rows(conn, """
            SELECT p.*, (SELECT COUNT(*) FROM tickets t WHERE t.priority_type_id=p.id
                          AND t.business_date=(SELECT MAX(business_date) FROM tickets)) AS used_today
            FROM priority_types p ORDER BY p.sort_order, p.id""")
    finally:
        conn.close()
    return {"priorities": rows}


def _priority_payload(payload: dict, existing: dict | None = None) -> dict:
    base = existing or {}
    name_en = str(payload.get("name_en", base.get("name_en", ""))).strip()
    name_fil = str(payload.get("name_fil", base.get("name_fil", ""))).strip()
    if not name_en or not name_fil:
        raise HTTPException(status_code=400, detail="priority_names_required")
    return {
        "name_en": name_en,
        "name_fil": name_fil,
        "is_active": 1 if payload.get("is_active", base.get("is_active", 1)) else 0,
        "sort_order": int(payload.get("sort_order", base.get("sort_order", 0)) or 0),
    }


@router.post("/priorities")
def create_priority(payload: dict, request: Request):
    security.require_admin(request)
    data = _priority_payload(payload)
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO priority_types(name_en, name_fil, is_active, sort_order) VALUES(?,?,?,?)",
            tuple(data.values()))
        priority_id = cur.lastrowid
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True, "id": priority_id}


@router.put("/priorities/{priority_id}")
def update_priority(priority_id: int, payload: dict, request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM priority_types WHERE id=?", (priority_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="priority_not_found")
        data = _priority_payload(payload, dict(row))
        conn.execute("UPDATE priority_types SET name_en=?, name_fil=?, is_active=?, sort_order=? WHERE id=?",
                     (*data.values(), priority_id))
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True}


# --- settings -------------------------------------------------------------

SETTING_TYPES = {
    "institution_name": str, "institution_type": str, "institution_address": str,
    "institution_contact": str, "logo_file": str, "timezone": str,
    "language_default": str, "languages_enabled": list, "screen_language": str,
    "reset_time": str, "tracking_base_url": str, "tracking_enabled": bool,
    "ticket_show_qr": bool, "ticket_show_wait": bool, "ticket_show_logo": bool,
    "ticket_paper_size": str, "print_enabled": bool, "kiosk_enabled": bool,
    "staff_issue_enabled": bool, "qr_phone_enabled": bool, "duplicate_ticket_delay": int,
    "priority_mode": str, "priority_interleave_n": int, "recall_wait_seconds": int,
    "recall_limit": int, "default_service_seconds": int, "display_layout": int,
    "banner_text_en": str, "banner_text_fil": str, "image_duration": int,
    "voice_enabled": bool, "voice_lang": str, "media_volume": float,
    "display_show_estimate": bool, "display_show_next": bool, "media_schedule": dict,
    "printer_note": str, "backup_keep": int,
}
CHOICES = {
    "screen_language": {"en", "fil", "both"},
    "language_default": {"en", "fil"},
    "voice_lang": {"en", "fil", "both"},
    "ticket_paper_size": {"58", "80"},
    "priority_mode": {"priority_first", "interleave"},
}
RANGES = {
    "duplicate_ticket_delay": (0, 600), "priority_interleave_n": (1, 20),
    "recall_wait_seconds": (1, 600), "recall_limit": (1, 10),
    "default_service_seconds": (30, 7200), "display_layout": (45, 80),
    "image_duration": (2, 120), "media_volume": (0, 1), "backup_keep": (1, 365),
}


def _validate_setting(key: str, value):
    expected = SETTING_TYPES[key]
    if expected is bool:
        if isinstance(value, str):
            value = value.lower() in ("1", "true", "yes", "on")
        elif not isinstance(value, bool):
            value = bool(value)
    elif expected is int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail={"code": "invalid_setting", "key": key})
        low, high = RANGES.get(key, (0, 10**9))
        if not low <= value <= high:
            raise HTTPException(status_code=400, detail={"code": "out_of_range", "key": key})
    elif expected is float:
        try:
            value = round(float(value), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail={"code": "invalid_setting", "key": key})
        low, high = RANGES.get(key, (0, 1))
        if not low <= value <= high:
            raise HTTPException(status_code=400, detail={"code": "out_of_range", "key": key})
    elif expected is str:
        value = str(value or "").strip()
        if key in CHOICES and value not in CHOICES[key]:
            raise HTTPException(status_code=400, detail={"code": "invalid_choice", "key": key})
        if key == "reset_time":
            _validate_clock(value)
            if len(value) != 5:
                raise HTTPException(status_code=400, detail="invalid_time")
        if key == "timezone":
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(value)
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_timezone")
        if key == "tracking_base_url":
            value = value.rstrip("/")
        if key == "logo_file" and value:
            allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
            if Path(value).name != value or Path(value).suffix.lower() not in allowed or not (MEDIA_DIR / value).is_file():
                raise HTTPException(status_code=400, detail="logo_not_found")
    elif expected is list:
        value = [str(x) for x in value if str(x) in ("en", "fil")]
        if "en" not in value:
            value.insert(0, "en")
    elif expected is dict:
        if not isinstance(value, dict):
            raise HTTPException(status_code=400, detail={"code": "invalid_setting", "key": key})
        for field in ("from", "to"):
            if value.get(field):
                _validate_clock(value[field])
    return value


@router.get("/settings")
def get_settings(request: Request):
    security.require_admin(request)
    settings = db.get_settings()
    return {
        "settings": {k: settings.get(k) for k in SETTING_TYPES},
        "media": queue.media_playlist(),
        "media_dir": str(MEDIA_DIR),
        "timezone": settings.get("timezone"),
        "server_time": db.utcnow(),
    }


@router.put("/settings")
def update_settings(payload: dict, request: Request):
    security.require_admin(request)
    updates = {}
    unknown = [k for k in payload if k not in SETTING_TYPES]
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "unknown_settings", "keys": unknown})
    for key, value in payload.items():
        updates[key] = _validate_setting(key, value)
    settings = db.save_settings(updates)
    # Keep the legacy media row in step with the settings table.
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE media_settings SET layout=?, image_duration=?, banner_text_en=?, banner_text_fil=? WHERE id=1",
            (int(settings.get("display_layout") or 60), int(settings.get("image_duration") or 10),
             settings.get("banner_text_en", ""), settings.get("banner_text_fil", "")))
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True, "settings": {k: settings.get(k) for k in SETTING_TYPES}}


# --- media ----------------------------------------------------------------

@router.get("/media")
def media(request: Request):
    security.require_admin(request)
    files = []
    if MEDIA_DIR.exists():
        for path in sorted(MEDIA_DIR.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            kind = "image" if ext in IMAGE_EXTENSIONS else "video" if ext in VIDEO_EXTENSIONS else None
            if not kind:
                continue
            files.append({
                "name": path.name,
                "kind": kind,
                "size": path.stat().st_size,
                "url": f"/media/{path.name}",
            })
    return {"files": files, "folder": str(MEDIA_DIR), "settings": {
        "image_duration": db.get_settings().get("image_duration"),
        "media_volume": db.get_settings().get("media_volume"),
        "media_schedule": db.get_settings().get("media_schedule"),
    }}


# --- backups --------------------------------------------------------------

@router.get("/backups")
def get_backups(request: Request):
    security.require_admin(request)
    settings = db.get_settings()
    return {"backups": backups.list_backups(), "keep": settings.get("backup_keep"),
            "folder": str(BACKUP_DIR), "database": str(db.DB_PATH)}


@router.post("/backups")
def create_backup(request: Request):
    security.require_admin(request)
    return {"ok": True, "backup": backups.create_backup("manual")}


@router.post("/backups/restore")
def restore_backup(payload: dict, request: Request):
    security.require_admin(request)
    name = str(payload.get("name") or "")
    try:
        backups.restore_backup(name)
    except ValueError:
        raise HTTPException(status_code=404, detail="backup_not_found")
    ws.publish({"type": "settings_changed"})
    return {"ok": True, "restored": name}


# --- system ---------------------------------------------------------------

@router.get("/system")
def system_info(request: Request):
    security.require_admin(request)
    settings = db.get_settings()
    lan_ip = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.2)
        probe.connect(("10.255.255.255", 1))
        lan_ip = probe.getsockname()[0]
        probe.close()
    except OSError:
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            lan_ip = None
    host = request.headers.get("host", "")
    port = host.rsplit(":", 1)[1] if ":" in host else "8000"
    origin = f"http://{lan_ip}:{port}" if lan_ip else f"http://{host}"
    return {
        "lan_ip": lan_ip,
        "hostname": socket.gethostname(),
        "port": port,
        "server_origin": origin,
        "types": presets.preset_list(),
        "server_time": db.utcnow(),
        "settings": {k: settings.get(k) for k in SETTING_TYPES},
    }


@router.get("/system/check")
def system_check(request: Request):
    security.require_admin(request)
    checks = []

    def add(key, ok, detail=""):
        checks.append({"key": key, "ok": bool(ok), "detail": str(detail)})

    try:
        conn = db.connect()
        try:
            conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
            conn.execute("SELECT COUNT(*) FROM services").fetchone()
            conn.execute("SELECT COUNT(*) FROM staff").fetchone()
            add("database", True, str(db.DB_PATH))
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - surface the error in the report
        add("database", False, exc)

    settings = db.get_settings()
    add("institution", bool(settings.get("institution_name")),
        settings.get("institution_name") or "not set")
    add("timezone", bool(settings.get("timezone")), settings.get("timezone"))
    add("admin_login", True, "signed in")

    files = queue.media_playlist()
    add("media_folder", MEDIA_DIR.exists(), f"{len(files)} file(s) in {MEDIA_DIR}")
    if settings.get("logo_file"):
        add("logo", (MEDIA_DIR / settings["logo_file"]).is_file(), settings["logo_file"])
    add("frontend", (FRONTEND_DIST / "index.html").is_file(), str(FRONTEND_DIST))

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        probe = BACKUP_DIR / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        add("backups", True, f"{len(backups.list_backups())} backup(s)")
    except OSError as exc:
        add("backups", False, exc)

    conn = db.connect()
    try:
        active_services = db.all_rows(conn, "SELECT name FROM services WHERE is_active=1")
        counter_count = conn.execute("SELECT COUNT(*) FROM counters WHERE is_active=1").fetchone()[0]
        staff_count = conn.execute("SELECT COUNT(*) FROM staff WHERE is_active=1").fetchone()[0]
    finally:
        conn.close()
    add("services", bool(active_services), f"{len(active_services)} active")
    add("counters", counter_count > 0, f"{counter_count} active")
    add("staff", staff_count > 0, f"{staff_count} active")
    add("printer", settings.get("printer_status") in ("ok", "works"),
        settings.get("printer_status") or "not reported")
    add("websocket", ws.manager.loop is not None, f"{len(ws.manager.clients)} screen(s) connected")
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "server_time": db.utcnow()}


@router.post("/reset-demo")
def reset_demo(request: Request):
    security.require_admin(request)
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM ticket_events WHERE ticket_id IN (SELECT id FROM tickets WHERE is_demo=1)")
        conn.execute("DELETE FROM tickets WHERE is_demo=1")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    ws.publish({"type": "settings_changed"})
    return {"ok": True}
