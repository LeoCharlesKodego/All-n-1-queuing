"""Setup wizard API."""
from fastapi import APIRouter, HTTPException

from .. import db, presets, queue
from ..queue import QueueError

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/media")
def setup_media():
    from ..config import IMAGE_EXTENSIONS, MEDIA_DIR
    files = []
    if MEDIA_DIR.exists():
        files = sorted(
            p.name for p in MEDIA_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
    return {"images": files, "folder": str(MEDIA_DIR)}


@router.get("/state")
def setup_state():
    settings = db.get_settings()
    return {
        "setup_complete": bool(settings.get("setup_complete")),
        "presets": presets.preset_list(),
        "defaults": {
            "timezone": settings.get("timezone"),
            "reset_time": settings.get("reset_time"),
            "priority_types": presets.PRIORITY_DEFAULT,
        },
    }


@router.post("/complete")
def complete_setup(payload: dict):
    if db.setup_complete():
        raise HTTPException(status_code=409, detail="setup_already_complete")
    try:
        presets.apply_setup(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = {"ok": True, "demo_ticket": None}
    if payload.get("demo_ticket"):
        conn = db.connect()
        try:
            svc = conn.execute("SELECT id FROM services WHERE is_active=1 ORDER BY sort_order LIMIT 1").fetchone()
        finally:
            conn.close()
        if svc:
            try:
                ticket = queue.issue_ticket(svc["id"], origin="demo", demo=True)
                result["demo_ticket"] = {"number": ticket["number"], "public_id": ticket["public_id"]}
            except QueueError as exc:
                result["demo_ticket"] = None
    return result
