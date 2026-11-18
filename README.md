# Queue System

Configurable, offline queuing platform for institutions in the Philippines.
FastAPI + SQLite backend, React frontend served by the same process.

## Requirements

- Python 3.11+
- Node.js 18+ (only needed to rebuild the frontend; a built copy is served by the server)

## First run (Windows or Linux/macOS)

```bash
python -m pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/setup` on the server PC and complete the wizard.
Other devices on the same Wi-Fi/LAN open the address shown in the wizard
(for example `http://192.168.1.20:8000/kiosk`).

## Screens

- `/setup` — first-run setup wizard
- `/kiosk` — touchscreen ticket kiosk
- `/counter` — staff console (PIN login)
- `/display` — waiting-area TV (no login)
- `/admin` — admin panel
- `/track/<public_id>` — phone tracking page

## Data and folders

- `data/queue.db` — SQLite database (created on first start)
- `data/backups/` — automatic and manual backups
- `media/` — logo, display images and videos (files are read from this folder; no upload)

Set `QUEUE_DATA_DIR`, `QUEUE_DB`, `QUEUE_MEDIA_DIR` or `QUEUE_BACKUP_DIR` to move them.

The server works fully offline. Do not add internet dependencies.
