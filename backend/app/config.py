"""Paths and shared configuration for the queue server."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("QUEUE_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("QUEUE_DB", DATA_DIR / "queue.db"))
MEDIA_DIR = Path(os.environ.get("QUEUE_MEDIA_DIR", BASE_DIR / "media"))
BACKUP_DIR = Path(os.environ.get("QUEUE_BACKUP_DIR", DATA_DIR / "backups"))
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogv", ".m4v"}

DEFAULT_SETTINGS = {
    "setup_complete": False,
    "institution_name": "",
    "institution_type": "generic",
    "institution_address": "",
    "institution_contact": "",
    "logo_file": "",
    "timezone": "Asia/Manila",
    "language_default": "en",
    "languages_enabled": ["en", "fil"],
    "screen_language": "both",
    "reset_time": "00:00",
    "tracking_base_url": "",
    "tracking_enabled": True,
    "ticket_show_qr": True,
    "ticket_show_wait": True,
    "ticket_show_logo": True,
    "ticket_paper_size": "58",
    "print_enabled": True,
    "kiosk_enabled": True,
    "staff_issue_enabled": False,
    "qr_phone_enabled": False,
    "duplicate_ticket_delay": 15,
    "priority_mode": "priority_first",
    "priority_interleave_n": 3,
    "recall_wait_seconds": 60,
    "recall_limit": 3,
    "default_service_seconds": 300,
    "display_layout": 60,
    "banner_text_en": "",
    "banner_text_fil": "",
    "image_duration": 10,
    "voice_enabled": True,
    "voice_lang": "both",
    "media_volume": 0.4,
    "display_show_estimate": True,
    "display_show_next": True,
    "media_schedule": {"enabled": False, "from": "08:00", "to": "17:00"},
    "printer_status": "unknown",
    "printer_note": "",
    "backup_keep": 30,
}
