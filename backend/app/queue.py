"""All queue logic lives here. The frontend never decides who is called next."""
import math
import secrets
import sqlite3
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db
from .ws import publish


class QueueError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


ACTIVE_STATUSES = ("waiting", "called", "serving", "on_hold")
CALLABLE_STATUSES = ("waiting",)


FIXED_OFFSETS = {"Asia/Manila": 8, "Asia/Singapore": 8, "UTC": 0}


def local_tz(settings: dict):
    """ZoneInfo when the OS has tz data, otherwise a fixed offset for the offered zones.

    Asia/Manila and Asia/Singapore have no daylight saving time, so a fixed offset is exact.
    """
    name = settings.get("timezone") or "Asia/Manila"
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=FIXED_OFFSETS.get(name, 8)))


def local_now(settings: dict) -> datetime:
    return datetime.now(timezone.utc).astimezone(local_tz(settings))


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = str(value).split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def business_date(settings: dict, at: datetime | None = None) -> str:
    loc = (at or local_now(settings)).astimezone(local_tz(settings))
    reset = _parse_hhmm(settings.get("reset_time") or "00:00") or time(0, 0)
    if loc.time() < reset:
        loc = loc - timedelta(days=1)
    return loc.date().isoformat()


def service_open_state(service: dict, settings: dict) -> tuple[bool, str]:
    """Return (can_issue, reason_key)."""
    if not service.get("is_active"):
        return False, "closed_inactive"
    now = local_now(settings).time()
    start = _parse_hhmm(service.get("open_from"))
    end = _parse_hhmm(service.get("open_to"))
    if start and end and (now < start or now > end):
        return False, "closed_hours"
    cutoff = _parse_hhmm(service.get("cut_off_time"))
    if cutoff and now >= cutoff:
        return False, "closed_cutoff"
    return True, ""


def active_service_ids(conn, counter_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT cs.service_id FROM counter_services cs JOIN services s ON s.id=cs.service_id "
        "WHERE cs.counter_id=? AND s.is_active=1", (counter_id,)
    ).fetchall()
    return [r["service_id"] for r in rows]


def _service(conn, service_id: int) -> dict:
    row = conn.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
    if not row:
        raise QueueError("service_not_found", 404)
    return dict(row)


def _priority(conn, priority_id):
    if not priority_id:
        return None
    row = conn.execute("SELECT * FROM priority_types WHERE id=?", (priority_id,)).fetchone()
    return dict(row) if row else None


def estimate_wait(conn, service_id: int, settings: dict | None = None) -> dict:
    settings = settings or db.get_settings(conn)
    waiting = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting'", (service_id,)
    ).fetchone()[0]
    done = conn.execute(
        "SELECT serving_at, done_at FROM tickets WHERE service_id=? AND status='done' "
        "AND serving_at IS NOT NULL AND done_at IS NOT NULL ORDER BY done_at DESC LIMIT 20",
        (service_id,),
    ).fetchall()
    durations = []
    for row in done:
        try:
            secs = (db.parse_utc(row["done_at"]) - db.parse_utc(row["serving_at"])).total_seconds()
            if 5 <= secs <= 4 * 3600:
                durations.append(secs)
        except (ValueError, TypeError):
            continue
    avg = sum(durations) / len(durations) if durations else float(settings.get("default_service_seconds") or 300)
    counters = conn.execute(
        "SELECT COUNT(*) FROM counter_services cs JOIN counters c ON c.id=cs.counter_id "
        "WHERE cs.service_id=? AND c.is_active=1 AND c.status IN ('open','away')",
        (service_id,),
    ).fetchone()[0]
    if counters == 0:
        counters = conn.execute(
            "SELECT COUNT(*) FROM counter_services cs JOIN counters c ON c.id=cs.counter_id "
            "WHERE cs.service_id=? AND c.is_active=1", (service_id,)
        ).fetchone()[0]
    counters = max(1, counters)
    seconds = int(math.ceil(waiting * avg / counters))
    return {"people_ahead": waiting, "estimated_seconds": seconds, "average_service_seconds": int(round(avg))}


def ticket_number(conn, service: dict, bdate: str) -> tuple[int, str]:
    row = conn.execute(
        "SELECT last_seq FROM daily_counters WHERE service_id=? AND business_date=?",
        (service["id"], bdate),
    ).fetchone()
    seq = (row["last_seq"] if row else 0) + 1
    conn.execute(
        "INSERT INTO daily_counters(service_id, business_date, last_seq) VALUES(?,?,?) "
        "ON CONFLICT(service_id, business_date) DO UPDATE SET last_seq=excluded.last_seq",
        (service["id"], bdate, seq),
    )
    width = max(3, len(str(seq)))
    return seq, f"{service['prefix']}-{seq:0{width}d}"


def _event(conn, ticket_id: int, event_type: str, counter_id=None, staff_id=None, details=None) -> None:
    conn.execute(
        "INSERT INTO ticket_events(ticket_id, event_type, counter_id, staff_id, created_at, details) "
        "VALUES(?,?,?,?,?,?)",
        (ticket_id, event_type, counter_id, staff_id, db.utcnow(),
         None if details is None else __import__("json").dumps(details)),
    )


def issue_ticket(
    service_id: int,
    priority_type_id=None,
    account_number: str | None = None,
    counter_id: int | None = None,
    staff_id: int | None = None,
    origin: str = "kiosk",
    demo: bool = False,
) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        service = _service(conn, service_id)
        if not demo:
            ok, reason = service_open_state(service, settings)
            if not ok:
                raise QueueError(reason, 409)
        priority = _priority(conn, priority_type_id)
        if priority_type_id and not priority:
            raise QueueError("priority_not_found", 400)
        bdate = business_date(settings)
        seq, number = ticket_number(conn, service, bdate)
        public_id = secrets.token_urlsafe(9)
        now = db.utcnow()
        cur = conn.execute(
            """INSERT INTO tickets(public_id, service_id, number, seq, business_date, priority_type_id,
               account_number, status, counter_id, staff_id, issued_at, last_event_at, is_demo)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (public_id, service_id, number, seq, bdate,
             priority["id"] if priority else None,
             (account_number or "").strip() or None, "waiting", counter_id, staff_id, now, now,
             1 if demo else 0),
        )
        ticket_id = cur.lastrowid
        _event(conn, ticket_id, "issued", counter_id, staff_id,
               {"origin": origin, "demo": bool(demo)})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    ticket = get_ticket(ticket_id)
    publish({"type": "ticket_issued", "ticket": ticket})
    return ticket


def get_ticket(ticket_id: int) -> dict | None:
    conn = db.connect()
    try:
        row = conn.execute(
            """SELECT t.*, s.name AS service_name, s.prefix, s.is_express,
                      p.name_en AS priority_en, p.name_fil AS priority_fil,
                      c.name AS counter_name, st.name AS staff_name
               FROM tickets t
               JOIN services s ON s.id=t.service_id
               LEFT JOIN priority_types p ON p.id=t.priority_type_id
               LEFT JOIN counters c ON c.id=t.counter_id
               LEFT JOIN staff st ON st.id=t.staff_id
               WHERE t.id=?""", (ticket_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_ticket_by_public_id(public_id: str) -> dict | None:
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM tickets WHERE public_id=?", (public_id,)).fetchone()
    finally:
        conn.close()
    return get_ticket(row["id"]) if row else None


# --- counter actions ------------------------------------------------------

def _current_for_counter(conn, counter_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM tickets WHERE counter_id=? AND status IN ('called','serving') ORDER BY id DESC LIMIT 1",
        (counter_id,),
    ).fetchone()
    return dict(row) if row else None


def counter_busy(counter_id: int) -> dict | None:
    conn = db.connect()
    try:
        return _current_for_counter(conn, counter_id)
    finally:
        conn.close()


def call_next(counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        current = _current_for_counter(conn, counter_id)
        if current:
            raise QueueError("counter_busy", 409)
        service_ids = active_service_ids(conn, counter_id)
        if not service_ids:
            raise QueueError("no_services_assigned", 409)
        placeholders = ",".join("?" * len(service_ids))
        bdate = business_date(settings)
        candidates = conn.execute(
            f"""SELECT * FROM tickets WHERE status='waiting' AND service_id IN ({placeholders})
                ORDER BY issued_at ASC, id ASC""", service_ids
        ).fetchall()
        if not candidates:
            raise QueueError("no_waiting_tickets", 404)

        priorities = {r["id"] for r in conn.execute("SELECT id FROM priority_types WHERE is_active=1")}
        priority_candidates = [dict(r) for r in candidates if r["priority_type_id"] in priorities]
        regular_candidates = [dict(r) for r in candidates if r["priority_type_id"] not in priorities]

        mode = settings.get("priority_mode") or "priority_first"
        chosen = None
        if mode == "interleave":
            n = max(2, int(settings.get("priority_interleave_n") or 3))
            calls_today = conn.execute(
                """SELECT COUNT(*) FROM ticket_events e JOIN tickets t ON t.id=e.ticket_id
                   WHERE e.event_type='call' AND t.business_date=?""", (bdate,)
            ).fetchone()[0]
            use_priority = ((calls_today + 1) % n == 0)
            if use_priority and priority_candidates:
                chosen = min(priority_candidates, key=lambda t: (t["issued_at"], t["id"]))
            elif regular_candidates:
                chosen = min(regular_candidates, key=lambda t: (t["issued_at"], t["id"]))
            else:
                chosen = min(priority_candidates, key=lambda t: (t["issued_at"], t["id"]))
        else:
            ordered = sorted(candidates, key=lambda t: (
                0 if (t["priority_type_id"] in priorities) else 1, t["issued_at"], t["id"]))
            chosen = dict(ordered[0])

        now = db.utcnow()
        conn.execute(
            "UPDATE tickets SET status='called', counter_id=?, staff_id=?, called_at=?, last_event_at=? WHERE id=?",
            (counter_id, staff_id, now, now, chosen["id"]),
        )
        _event(conn, chosen["id"], "call", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    ticket = get_ticket(chosen["id"])
    publish({"type": "called", "ticket": ticket, "counter_id": counter_id})
    return ticket


def _load_active(conn, ticket_id: int) -> dict:
    row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise QueueError("ticket_not_found", 404)
    ticket = dict(row)
    return ticket


def recall(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] != "called" or ticket["counter_id"] != counter_id:
            raise QueueError("not_current_ticket", 409)
        limit = max(1, int(settings.get("recall_limit") or 3))
        count = ticket["recall_count"] + 1
        conn.execute("UPDATE tickets SET recall_count=?, last_event_at=? WHERE id=?",
                     (count, db.utcnow(), ticket_id))
        _event(conn, ticket_id, "recall", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "called", "ticket": t, "counter_id": counter_id, "recall": True,
             "limit_reached": t["recall_count"] >= max(1, int(settings.get("recall_limit") or 3))})
    return t


def start_serving(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] not in ("called", "serving") or ticket["counter_id"] != counter_id:
            raise QueueError("not_current_ticket", 409)
        if ticket["status"] == "called":
            conn.execute("UPDATE tickets SET status='serving', serving_at=?, last_event_at=? WHERE id=?",
                         (db.utcnow(), db.utcnow(), ticket_id))
            _event(conn, ticket_id, "serve", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "serving", "ticket": t})
    return t


def mark_done(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ticket = _load_active(conn, ticket_id)
        if ticket["counter_id"] != counter_id or ticket["status"] not in ("called", "serving"):
            raise QueueError("not_current_ticket", 409)
        now = db.utcnow()
        conn.execute("UPDATE tickets SET status='done', done_at=?, last_event_at=? WHERE id=?",
                     (now, now, ticket_id))
        _event(conn, ticket_id, "done", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "done", "ticket": t})
    return t


def skip(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        ticket = _load_active(conn, ticket_id)
        if ticket["counter_id"] != counter_id or ticket["status"] not in ("called", "serving"):
            raise QueueError("not_current_ticket", 409)
        limit = max(1, int(settings.get("recall_limit") or 3))
        now = db.utcnow()
        if ticket["recall_count"] >= limit:
            conn.execute("UPDATE tickets SET status='no_show', last_event_at=? WHERE id=?", (now, ticket_id))
            _event(conn, ticket_id, "no_show", counter_id, staff_id)
        else:
            conn.execute("UPDATE tickets SET status='on_hold', last_event_at=? WHERE id=?", (now, ticket_id))
            _event(conn, ticket_id, "skip", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "status_changed", "ticket": t})
    return t


def hold(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] not in ("waiting", "called", "serving"):
            raise QueueError("cannot_hold", 409)
        if ticket["status"] in ("called", "serving") and ticket["counter_id"] != counter_id:
            raise QueueError("not_current_ticket", 409)
        now = db.utcnow()
        conn.execute("UPDATE tickets SET status='on_hold', last_event_at=? WHERE id=?", (now, ticket_id))
        _event(conn, ticket_id, "hold", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "status_changed", "ticket": t})
    return t


def resume(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    """Bring a parked/skipped ticket back to the queue or recall it to this counter."""
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] != "on_hold":
            raise QueueError("not_on_hold", 409)
        raw_wait = settings.get("recall_wait_seconds")
        wait = int(60 if raw_wait is None else raw_wait)
        if ticket["last_event_at"] and wait > 0:
            elapsed = (db.parse_utc(db.utcnow()) - db.parse_utc(ticket["last_event_at"])).total_seconds()
            if elapsed < wait:
                raise QueueError("recall_wait", 409)
        limit = max(1, int(settings.get("recall_limit") or 3))
        now = db.utcnow()
        conn.execute(
            "UPDATE tickets SET status='called', counter_id=?, staff_id=?, called_at=COALESCE(called_at, ?), "
            "recall_count=recall_count+1, last_event_at=? WHERE id=?",
            (counter_id, staff_id, now, now, ticket_id),
        )
        _event(conn, ticket_id, "resume", counter_id, staff_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(ticket_id)
    publish({"type": "called", "ticket": t, "counter_id": counter_id, "recall": True,
             "limit_reached": t["recall_count"] >= max(1, int(settings.get("recall_limit") or 3))})
    return t


def transfer(ticket_id: int, to_service_id: int, counter_id: int, staff_id: int | None = None,
             keep_place: bool = False) -> dict:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] not in ("waiting", "called", "serving"):
            raise QueueError("cannot_transfer", 409)
        if ticket["status"] in ("called", "serving") and ticket["counter_id"] != counter_id:
            raise QueueError("not_current_ticket", 409)
        target = _service(conn, to_service_id)
        if not target["is_active"]:
            raise QueueError("service_not_found", 404)
        if target["id"] == ticket["service_id"]:
            raise QueueError("same_service", 409)
        bdate = business_date(settings)
        seq, number = ticket_number(conn, target, bdate)
        public_id = secrets.token_urlsafe(9)
        now = db.utcnow()
        issued_at = ticket["issued_at"] if keep_place else now
        cur = conn.execute(
            """INSERT INTO tickets(public_id, service_id, number, seq, business_date, priority_type_id,
               account_number, status, issued_at, last_event_at)
               VALUES(?,?,?,?,?,?,?,'waiting',?,?)""",
            (public_id, target["id"], number, seq, bdate, ticket["priority_type_id"],
             ticket["account_number"], issued_at, now),
        )
        new_id = cur.lastrowid
        conn.execute("UPDATE tickets SET status='transferred', last_event_at=? WHERE id=?", (now, ticket_id))
        _event(conn, ticket_id, "transfer", counter_id, staff_id,
               {"to_service_id": target["id"], "new_ticket_id": new_id, "new_number": number})
        _event(conn, new_id, "issued", counter_id, staff_id,
               {"origin": "transfer", "from_ticket_id": ticket_id, "keep_place": bool(keep_place)})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    new_ticket = get_ticket(new_id)
    publish({"type": "ticket_issued", "ticket": new_ticket})
    return new_ticket


def reenter(ticket_id: int, counter_id: int, staff_id: int | None = None) -> dict:
    """Re-enter a no-show / skipped customer at the end of the line."""
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        settings = db.get_settings(conn)
        ticket = _load_active(conn, ticket_id)
        if ticket["status"] not in ("no_show", "on_hold"):
            raise QueueError("cannot_reenter", 409)
        service = _service(conn, ticket["service_id"])
        ok, reason = service_open_state(service, settings)
        if not ok and not service["is_active"]:
            raise QueueError(reason, 409)
        bdate = business_date(settings)
        seq, number = ticket_number(conn, service, bdate)
        public_id = secrets.token_urlsafe(9)
        now = db.utcnow()
        cur = conn.execute(
            """INSERT INTO tickets(public_id, service_id, number, seq, business_date, priority_type_id,
               account_number, status, issued_at, last_event_at)
               VALUES(?,?,?,?,?,?,?,'waiting',?,?)""",
            (public_id, service["id"], number, seq, bdate, ticket["priority_type_id"],
             ticket["account_number"], now, now),
        )
        new_id = cur.lastrowid
        _event(conn, new_id, "issued", counter_id, staff_id,
               {"origin": "reentry", "from_ticket_id": ticket_id})
        _event(conn, ticket_id, "reentry", counter_id, staff_id, {"new_ticket_id": new_id})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    t = get_ticket(new_id)
    publish({"type": "ticket_issued", "ticket": t})
    return t


# --- state snapshots ------------------------------------------------------

def expire_old_tickets() -> int:
    """Cancel tickets left active from a previous business date (daily reset)."""
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        bdate = business_date(settings)
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id FROM tickets WHERE business_date < ? "
            "AND status IN ('waiting','called','serving','on_hold')", (bdate,)
        ).fetchall()
        now = db.utcnow()
        for row in rows:
            conn.execute("UPDATE tickets SET status='cancelled', last_event_at=? WHERE id=?", (now, row["id"]))
            _event(conn, row["id"], "expired")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    if rows:
        publish({"type": "reset", "expired": len(rows)})
    return len(rows)


def counter_state(counter_id: int) -> dict:
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        counter = conn.execute("SELECT * FROM counters WHERE id=?", (counter_id,)).fetchone()
        if not counter:
            raise QueueError("counter_not_found", 404)
        current_row = _current_for_counter(conn, counter_id)
        current = get_ticket(current_row["id"]) if current_row else None
        service_ids = active_service_ids(conn, counter_id)
        waiting = []
        if service_ids:
            ph = ",".join("?" * len(service_ids))
            waiting = db.all_rows(conn, f"""
                SELECT t.id, t.number, t.issued_at, t.priority_type_id, t.account_number,
                       s.name AS service_name, s.prefix,
                       p.name_en AS priority_en, p.name_fil AS priority_fil
                FROM tickets t JOIN services s ON s.id=t.service_id
                LEFT JOIN priority_types p ON p.id=t.priority_type_id
                WHERE t.status='waiting' AND t.service_id IN ({ph})
                ORDER BY t.issued_at ASC""", service_ids)
            now = db.parse_utc(db.utcnow())
            for row in waiting:
                try:
                    row["wait_seconds"] = int((now - db.parse_utc(row["issued_at"])).total_seconds())
                except (ValueError, TypeError):
                    row["wait_seconds"] = 0
        parked = []
        if service_ids:
            ph = ",".join("?" * len(service_ids))
            parked = db.all_rows(conn, f"""
                SELECT t.id, t.number, t.status, t.last_event_at, t.recall_count,
                       s.name AS service_name,
                       p.name_en AS priority_en, p.name_fil AS priority_fil
                FROM tickets t JOIN services s ON s.id=t.service_id
                LEFT JOIN priority_types p ON p.id=t.priority_type_id
                WHERE t.status IN ('on_hold','no_show') AND t.service_id IN ({ph})
                AND t.business_date = ?
                ORDER BY t.last_event_at DESC LIMIT 25""", service_ids + [business_date(settings)])
            wait = int(settings.get("recall_wait_seconds") or 0)
            now = db.parse_utc(db.utcnow())
            for row in parked:
                try:
                    elapsed = (now - db.parse_utc(row["last_event_at"])).total_seconds()
                except (ValueError, TypeError):
                    elapsed = wait
                row["can_recall"] = row["status"] == "on_hold" and elapsed >= wait
                row["recall_in"] = max(0, int(wait - elapsed))
        served_today = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE counter_id=? AND status='done' AND business_date=?",
            (counter_id, business_date(settings)),
        ).fetchone()[0]
        snapshots = []
        if service_ids:
            for sid in service_ids:
                snapshots.append({"service_id": sid, **estimate_wait(conn, sid, settings)})
        return {
            "counter": dict(counter),
            "current": current,
            "waiting": waiting,
            "parked": parked,
            "served_today": served_today,
            "waiting_count": len(waiting),
            "estimates": snapshots,
            "services": db.all_rows(
                conn, "SELECT id, name, prefix, is_active FROM services WHERE is_active=1 ORDER BY sort_order, id"),
            "priorities": db.all_rows(
                conn, "SELECT id, name_en, name_fil FROM priority_types WHERE is_active=1 ORDER BY sort_order, id"),
            "settings": _public_settings(settings),
            "server_now": db.utcnow(),
        }
    finally:
        conn.close()


def _public_settings(settings: dict) -> dict:
    keys = (
        "institution_name", "institution_type", "institution_address", "institution_contact",
        "logo_file", "language_default", "languages_enabled", "screen_language", "timezone",
        "reset_time", "ticket_show_qr", "ticket_show_wait", "ticket_show_logo", "ticket_paper_size",
        "print_enabled", "kiosk_enabled", "staff_issue_enabled", "qr_phone_enabled",
        "duplicate_ticket_delay", "priority_mode", "priority_interleave_n", "recall_wait_seconds",
        "recall_limit", "default_service_seconds", "display_layout", "banner_text_en",
        "banner_text_fil", "image_duration", "voice_enabled", "voice_lang", "media_volume",
        "display_show_estimate", "display_show_next", "media_schedule", "tracking_base_url",
        "tracking_enabled", "printer_status", "printer_note", "setup_complete",
    )
    return {k: settings.get(k) for k in keys}


def display_state() -> dict:
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        bdate = business_date(settings)
        windows = db.all_rows(conn, """
            SELECT c.id, c.name, c.status,
                   t.id AS ticket_id, t.number, t.status AS ticket_status,
                   p.name_en AS priority_en, p.name_fil AS priority_fil
            FROM counters c
            LEFT JOIN tickets t ON t.id = (
                SELECT t2.id FROM tickets t2 WHERE t2.counter_id=c.id
                AND t2.status IN ('called','serving') ORDER BY t2.id DESC LIMIT 1
            )
            LEFT JOIN priority_types p ON p.id=t.priority_type_id
            WHERE c.is_active=1 ORDER BY c.sort_order, c.id""")
        for w in windows:
            if w["ticket_status"] == "serving":
                w["state"] = "serving"
            elif w["ticket_status"] == "called":
                w["state"] = "called"
            else:
                w["state"] = "closed" if w["status"] == "closed" else (
                    "away" if w["status"] == "away" else "idle")
        next_up = db.all_rows(conn, """
            SELECT t.id, t.number, s.name AS service_name, t.priority_type_id,
                   p.name_en AS priority_en, p.name_fil AS priority_fil
            FROM tickets t JOIN services s ON s.id=t.service_id
            LEFT JOIN priority_types p ON p.id=t.priority_type_id
            WHERE t.status='waiting' ORDER BY t.issued_at ASC LIMIT 8""")
        now_serving = db.all_rows(conn, """
            SELECT t.id, t.number, t.status, t.last_event_at, c.id AS counter_id, c.name AS counter_name,
                   s.name AS service_name, t.priority_type_id,
                   p.name_en AS priority_en, p.name_fil AS priority_fil
            FROM tickets t JOIN counters c ON c.id=t.counter_id
            JOIN services s ON s.id=t.service_id
            LEFT JOIN priority_types p ON p.id=t.priority_type_id
            WHERE t.status IN ('called','serving')
            ORDER BY t.last_event_at DESC LIMIT 3""")
        waiting_total = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='waiting'").fetchone()[0]
        estimates = {}
        for sid in [r["id"] for r in conn.execute("SELECT id FROM services WHERE is_active=1")]:
            estimates[sid] = estimate_wait(conn, sid, settings)["estimated_seconds"]
        media = media_playlist()
        return {
            "windows": windows,
            "now_serving": now_serving,
            "next": next_up,
            "waiting_total": waiting_total,
            "estimates": estimates,
            "media": media,
            "business_date": bdate,
            "settings": _public_settings(settings),
            "server_now": db.utcnow(),
        }
    finally:
        conn.close()


def _media_files() -> list[dict]:
    from .config import MEDIA_DIR, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
    files = []
    if MEDIA_DIR.exists():
        for path in sorted(MEDIA_DIR.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                files.append({"name": path.name, "kind": "image", "url": f"/media/{path.name}"})
            elif ext in VIDEO_EXTENSIONS:
                files.append({"name": path.name, "kind": "video", "url": f"/media/{path.name}"})
        logo = None
        data = db.get_settings().get("logo_file")
        if data:
            logo = f"/media/{data}"
        for f in files:
            f["is_logo"] = bool(data and f["name"] == data)
    return files


def media_playlist() -> list[dict]:
    return _media_files()


def kiosk_state() -> dict:
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        services = db.all_rows(conn, "SELECT * FROM services WHERE is_active=1 ORDER BY sort_order, id")
        for svc in services:
            ok, reason = service_open_state(svc, settings)
            svc["can_issue"] = ok
            svc["reason"] = reason
            svc["people_ahead"] = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting'", (svc["id"],)
            ).fetchone()[0]
        priorities = db.all_rows(
            conn, "SELECT * FROM priority_types WHERE is_active=1 ORDER BY sort_order, id")
        return {
            "services": services,
            "priorities": priorities,
            "settings": _public_settings(settings),
            "logo": f"/media/{settings['logo_file']}" if settings.get("logo_file") else None,
        }
    finally:
        conn.close()


def track_state(public_id: str) -> dict:
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        row = conn.execute(
            """SELECT t.*, s.name AS service_name, s.prefix, p.name_en AS priority_en, p.name_fil AS priority_fil,
                      c.name AS counter_name
               FROM tickets t JOIN services s ON s.id=t.service_id
               LEFT JOIN priority_types p ON p.id=t.priority_type_id
               LEFT JOIN counters c ON c.id=t.counter_id
               WHERE t.public_id=?""", (public_id,)
        ).fetchone()
        if not row:
            return None
        t = dict(row)
        ahead = 0
        if t["status"] == "waiting":
            ahead = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting' AND issued_at<?",
                (t["service_id"], t["issued_at"]),
            ).fetchone()[0]
        now_serving = db.all_rows(conn, """
            SELECT t.number, c.name AS counter_name FROM tickets t JOIN counters c ON c.id=t.counter_id
            WHERE t.status IN ('called','serving') AND c.is_active=1 ORDER BY c.sort_order, c.id""")
        est = estimate_wait(conn, t["service_id"], settings) if t["status"] == "waiting" else None
        return {
            "ticket": {k: t[k] for k in ("number", "status", "service_name", "priority_en", "priority_fil",
                                         "counter_name", "recall_count")},
            "people_ahead": ahead,
            "now_serving": now_serving,
            "estimate": est,
            "settings": _public_settings(settings),
        }
    finally:
        conn.close()


def stats_today() -> dict:
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        bdate = business_date(settings)
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM tickets WHERE business_date=? GROUP BY status", (bdate,))}
        issued = conn.execute("SELECT COUNT(*) FROM tickets WHERE business_date=?", (bdate,)).fetchone()[0]
        return {"business_date": bdate, "issued": issued, "counts": counts}
    finally:
        conn.close()
