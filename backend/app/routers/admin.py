"""Admin panel API: dashboard, configuration, media, backups, reports."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])
