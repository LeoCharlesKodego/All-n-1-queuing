"""Public endpoints: health, bootstrap, kiosk, display, tracking, QR."""
import time

from fastapi import APIRouter, HTTPException, Request, Response

from .. import db, queue, qr
from ..queue import QueueError

router = APIRouter(prefix="/api", tags=["public"])

_last_issue: dict[str, float] = {}


def tracking_url(ticket: dict, request: Request, settings: dict) -> str:
    base = str(settings.get("tracking_base_url") or "").strip()
    if not base:
        base = str(request.base_url).rstrip("/")
    return f"{base.rstrip('/')}/track/{ticket['public_id']}"


@router.get("/health")
def health():
    return {"status": "ok", "setup_complete": db.setup_complete(), "server_time": db.utcnow()}


@router.get("/bootstrap")
def bootstrap():
    settings = db.get_settings()
    return {
        "setup_complete": bool(settings.get("setup_complete")),
        "institution_name": settings.get("institution_name"),
        "language_default": settings.get("language_default"),
        "languages_enabled": settings.get("languages_enabled"),
        "logo": f"/media/{settings['logo_file']}" if settings.get("logo_file") else None,
        "kiosk_enabled": settings.get("kiosk_enabled"),
        "staff_issue_enabled": settings.get("staff_issue_enabled"),
    }


@router.get("/kiosk")
def kiosk():
    settings = db.get_settings()
    if not settings.get("setup_complete"):
        raise HTTPException(status_code=409, detail="setup_required")
    return queue.kiosk_state()


@router.post("/kiosk/ticket")
def kiosk_ticket(payload: dict, request: Request):
    settings = db.get_settings()
    if not settings.get("setup_complete"):
        raise HTTPException(status_code=409, detail="setup_required")
    if not settings.get("kiosk_enabled"):
        raise HTTPException(status_code=409, detail="kiosk_disabled")
    delay = int(settings.get("duplicate_ticket_delay") or 0)
    key = request.client.host if request.client else "unknown"
    now = time.time()
    if delay and key in _last_issue and now - _last_issue[key] < delay:
        wait = int(delay - (now - _last_issue[key]))
        raise HTTPException(status_code=429, detail={"code": "duplicate_delay", "seconds": max(1, wait)})
    try:
        service_id = int(payload.get("service_id") or 0)
        ticket = queue.issue_ticket(
            service_id,
            priority_type_id=payload.get("priority_type_id"),
            account_number=payload.get("account_number"),
            origin="kiosk",
        )
    except QueueError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.code)
    _last_issue[key] = now
    ticket = queue.get_ticket(ticket["id"])
    conn = db.connect()
    try:
        est = queue.estimate_wait(conn, service_id, settings)
        ahead = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting' AND issued_at<?",
            (service_id, ticket["issued_at"]),
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "ticket": ticket,
        "people_ahead": ahead,
        "estimated_seconds": est["estimated_seconds"],
        "tracking_url": tracking_url(ticket, request, settings),
        "show_qr": bool(settings.get("ticket_show_qr") and settings.get("tracking_enabled")),
        "tracking_enabled": bool(settings.get("tracking_enabled")),
    }


def conn_count(service_id: int) -> int:
    conn = db.connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE service_id=? AND status='waiting'", (service_id,)
        ).fetchone()[0]
    finally:
        conn.close()


@router.get("/track/{public_id}")
def track(public_id: str):
    data = queue.track_state(public_id)
    if not data:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return data


@router.get("/display")
def display():
    return queue.display_state()


@router.get("/display/media")
def display_media():
    return {"files": queue.media_playlist()}


@router.post("/kiosk/printer")
def kiosk_printer(payload: dict):
    """Kiosk reports a printer problem (paper out / offline) for the admin alert."""
    status = str(payload.get("status") or "").strip()
    if status not in ("ok", "error"):
        raise HTTPException(status_code=400, detail="invalid_status")
    note = str(payload.get("note") or "").strip()[:200]
    db.save_settings({"printer_status": status, "printer_note": note if status == "error" else ""})
    return {"ok": True, "printer_status": status}


@router.get("/qr")
def qr_code(data: str, size: int = 160):
    try:
        svg = qr.qr_svg(data, scale=max(1, int(size) // 40))
    except ValueError:
        raise HTTPException(status_code=400, detail="qr_payload_too_long")
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})
