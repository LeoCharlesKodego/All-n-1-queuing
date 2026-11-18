"""Staff PIN login and counter console actions."""
from fastapi import APIRouter, HTTPException, Request, Response

from .. import db, queue, security
from ..queue import QueueError

router = APIRouter(prefix="/api", tags=["counter"])


def handle(exc: QueueError):
    raise HTTPException(status_code=exc.status, detail=exc.code)


def _counter_status(counter_id: int, status: str, staff_id: int | None, event: str) -> None:
    conn = db.connect()
    try:
        conn.execute("UPDATE counters SET status=? WHERE id=?", (status, counter_id))
        conn.execute(
            "INSERT INTO counter_events(counter_id, staff_id, event_type, created_at) VALUES(?,?,?,?)",
            (counter_id, staff_id, event, db.utcnow()),
        )
    finally:
        conn.close()
    queue.publish({"type": "counter_status", "counter_id": counter_id, "status": status})


@router.get("/staff/options")
def staff_options():
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        counters = db.all_rows(
            conn, "SELECT id, name, status FROM counters WHERE is_active=1 ORDER BY sort_order, id")
    finally:
        conn.close()
    return {
        "counters": counters,
        "institution_name": settings.get("institution_name"),
        "logo": f"/media/{settings['logo_file']}" if settings.get("logo_file") else None,
        "language_default": settings.get("language_default"),
    }


@router.post("/staff/login")
def staff_login(payload: dict, request: Request, response: Response):
    pin = str(payload.get("pin", "")).strip()
    username = str(payload.get("username", "")).strip()
    counter_id = payload.get("counter_id")
    ip = security.client_key(request)
    security.rate_limit_check("staff", ip)
    if not pin:
        raise HTTPException(status_code=400, detail="pin_required")
    conn = db.connect()
    try:
        rows = db.all_rows(conn, "SELECT * FROM staff WHERE is_active=1")
        if username:
            rows = [r for r in rows if r["username"].lower() == username.lower()]
        matches = [r for r in rows if security.verify_secret(pin, r["pin_hash"])]
        if not matches:
            security.rate_limit_fail("staff", ip)
            raise HTTPException(status_code=401, detail="invalid_credentials")
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail="pin_ambiguous")
        staff = matches[0]
        assigned = staff["counter_id"] or counter_id
        if not assigned:
            raise HTTPException(status_code=400, detail="counter_required")
        counter = conn.execute(
            "SELECT * FROM counters WHERE id=? AND is_active=1", (int(assigned),)
        ).fetchone()
        if not counter:
            raise HTTPException(status_code=400, detail="counter_not_found")
    finally:
        conn.close()
    security.rate_limit_clear("staff", ip)
    token = security.create_session("staff", staff_id=staff["id"], counter_id=counter["id"])
    response.set_cookie(
        security.COOKIE_NAME, token, httponly=True, samesite="lax",
        max_age=security.SESSION_HOURS * 3600)
    _counter_status(counter["id"], "open", staff["id"], "login")
    return {
        "ok": True,
        "role": "staff",
        "staff": {"id": staff["id"], "name": staff["name"]},
        "counter": {"id": counter["id"], "name": counter["name"]},
    }


@router.post("/staff/logout")
def staff_logout(request: Request, response: Response):
    sess = security.session_from_request(request)
    if sess and sess["role"] == "staff":
        _counter_status(sess["counter_id"], "closed", sess["staff_id"], "logout")
    security.delete_session(request.cookies.get(security.COOKIE_NAME))
    response.delete_cookie(security.COOKIE_NAME)
    return {"ok": True}


@router.get("/counter/me")
def counter_me(request: Request):
    sess = security.require_staff(request)
    return {
        "staff": sess["staff"],
        "counter_id": sess["counter_id"],
    }


@router.get("/counter/state")
def counter_state(request: Request):
    sess = security.require_staff(request)
    try:
        state = queue.counter_state(sess["counter_id"])
    except QueueError as exc:
        handle(exc)
    state["staff"] = sess["staff"]
    return state


@router.post("/counter/call-next")
def counter_call_next(request: Request):
    sess = security.require_staff(request)
    conn = db.connect()
    try:
        counter = conn.execute("SELECT status FROM counters WHERE id=?", (sess["counter_id"],)).fetchone()
    finally:
        conn.close()
    if counter and counter["status"] == "closed":
        _counter_status(sess["counter_id"], "open", sess["staff_id"], "open")
    try:
        return queue.call_next(sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/recall")
def counter_recall(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0) or _current_id(sess["counter_id"])
    try:
        return queue.recall(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/start")
def counter_start(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0) or _current_id(sess["counter_id"])
    try:
        return queue.start_serving(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/done")
def counter_done(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0) or _current_id(sess["counter_id"])
    try:
        return queue.mark_done(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/skip")
def counter_skip(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0) or _current_id(sess["counter_id"])
    try:
        return queue.skip(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/hold")
def counter_hold(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0) or _current_id(sess["counter_id"])
    try:
        return queue.hold(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/resume")
def counter_resume(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0)
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_required")
    try:
        return queue.resume(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/transfer")
def counter_transfer(payload: dict, request: Request):
    sess = security.require_staff(request)
    try:
        return queue.transfer(
            int(payload.get("ticket_id") or 0),
            int(payload.get("to_service_id") or 0),
            sess["counter_id"],
            sess["staff_id"],
            keep_place=bool(payload.get("keep_place")),
        )
    except QueueError as exc:
        handle(exc)


@router.post("/counter/reenter")
def counter_reenter(payload: dict, request: Request):
    sess = security.require_staff(request)
    ticket_id = int(payload.get("ticket_id") or 0)
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_required")
    try:
        return queue.reenter(ticket_id, sess["counter_id"], sess["staff_id"])
    except QueueError as exc:
        handle(exc)


@router.post("/counter/issue")
def counter_issue(payload: dict, request: Request):
    sess = security.require_staff(request)
    conn = db.connect()
    try:
        settings = db.get_settings(conn)
        if not settings.get("staff_issue_enabled"):
            raise HTTPException(status_code=409, detail="staff_issue_disabled")
        service_id = int(payload.get("service_id") or 0)
        allowed = queue.active_service_ids(conn, sess["counter_id"])
        if service_id not in allowed:
            raise HTTPException(status_code=409, detail="service_not_assigned")
    finally:
        conn.close()
    try:
        return queue.issue_ticket(
            service_id,
            priority_type_id=payload.get("priority_type_id"),
            account_number=payload.get("account_number"),
            counter_id=sess["counter_id"],
            staff_id=sess["staff_id"],
            origin="counter",
        )
    except QueueError as exc:
        handle(exc)


@router.post("/counter/status")
def counter_status(payload: dict, request: Request):
    sess = security.require_staff(request)
    status = str(payload.get("status") or "")
    if status not in ("open", "away", "closed"):
        raise HTTPException(status_code=400, detail="invalid_status")
    _counter_status(sess["counter_id"], status, sess["staff_id"], status)
    return {"ok": True, "status": status}


def _current_id(counter_id: int) -> int:
    current = queue.counter_busy(counter_id)
    if not current:
        raise HTTPException(status_code=409, detail="no_current_ticket")
    return current["id"]
