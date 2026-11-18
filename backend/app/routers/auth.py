"""Admin login/logout and session info."""
from fastapi import APIRouter, HTTPException, Request, Response

from .. import db, security

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def admin_login(payload: dict, request: Request, response: Response):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    ip = security.client_key(request)
    security.rate_limit_check("admin", f"{username}|{ip}")
    conn = db.connect()
    try:
        admin = conn.execute("SELECT * FROM admin WHERE username=?", (username,)).fetchone()
    finally:
        conn.close()
    if not admin or not security.verify_secret(password, admin["password_hash"]):
        security.rate_limit_fail("admin", f"{username}|{ip}")
        raise HTTPException(status_code=401, detail="invalid_credentials")
    security.rate_limit_clear("admin", f"{username}|{ip}")
    token = security.create_session("admin")
    response.set_cookie(
        security.COOKIE_NAME, token, httponly=True, samesite="lax", max_age=security.SESSION_HOURS * 3600)
    return {"ok": True, "role": "admin", "username": admin["username"]}


@router.post("/logout")
def admin_logout(request: Request, response: Response):
    security.delete_session(request.cookies.get(security.COOKIE_NAME))
    response.delete_cookie(security.COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def admin_me(request: Request):
    sess = security.session_from_request(request)
    if not sess or sess["role"] != "admin":
        raise HTTPException(status_code=401, detail="admin_required")
    conn = db.connect()
    try:
        admin = conn.execute("SELECT username FROM admin WHERE id=1").fetchone()
        settings = db.get_settings(conn)
    finally:
        conn.close()
    return {
        "role": "admin",
        "username": admin["username"] if admin else "",
        "setup_complete": bool(settings.get("setup_complete")),
        "institution_name": settings.get("institution_name"),
        "language_default": settings.get("language_default"),
        "languages_enabled": settings.get("languages_enabled"),
    }
