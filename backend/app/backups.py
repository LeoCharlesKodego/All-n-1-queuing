"""Automatic and manual SQLite backups."""
import asyncio
import shutil
import sqlite3
from datetime import datetime

from .config import BACKUP_DIR, DB_PATH, DATA_DIR
from . import db


def ensure_dirs() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def list_backups() -> list[dict]:
    ensure_dirs()
    out = []
    for path in sorted(BACKUP_DIR.glob("queue-*.db"), reverse=True):
        stat = path.stat()
        out.append({
            "name": path.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        })
    return out


def create_backup(reason: str = "manual") -> dict:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"queue-{stamp}-{reason}.db"
    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    keep = int(db.get_settings().get("backup_keep") or 30)
    backups = sorted(BACKUP_DIR.glob("queue-*.db"))
    for old in backups[:-keep] if keep > 0 else []:
        try:
            old.unlink()
        except OSError:
            pass
    return {"name": target.name, "size": target.stat().st_size}


def restore_backup(filename: str) -> None:
    safe = (BACKUP_DIR / filename).resolve()
    if BACKUP_DIR.resolve() not in safe.parents or not safe.is_file():
        raise ValueError("backup_not_found")
    tmp = DATA_DIR / "restore.tmp"
    shutil.copyfile(safe, tmp)
    check = sqlite3.connect(str(tmp))
    try:
        check.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    finally:
        check.close()
    for suffix in ("-wal", "-shm"):
        p = DB_PATH.with_name(DB_PATH.name + suffix)
        if p.exists():
            p.unlink()
    shutil.move(str(tmp), str(DB_PATH))


async def backup_loop() -> None:
    while True:
        try:
            settings = db.get_settings()
            stamp = datetime.now().strftime("%Y%m%d")
            existing = list(BACKUP_DIR.glob(f"queue-{stamp}-daily*.db"))
            if not existing:
                create_backup("daily")
        except Exception:
            pass
        await asyncio.sleep(3600)
