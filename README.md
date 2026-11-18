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

## Daily use

1. Open `/admin` → **System** and check the server address shown there.
2. Open `/kiosk` on the touchscreen (first tap enters fullscreen), `/display` on the waiting-area TV (press F11), and `/counter` on each staff PC.
3. Staff log in with their username and PIN, pick their window, then use **Call next**, **Start**, **Done**, **Skip**, **Hold**, **Transfer**.

The daily reset runs at the time set in **System → Reset time** (default 00:00). Tickets still waiting from an earlier day are closed with an `expired` event; they are never called on the new day.

## Printer setup

- Set the paper size (58 mm or 80 mm) and print options in **Admin → Kiosk & ticket**.
- Install the printer driver on the kiosk PC and set it as the **default printer**.
- Normal mode opens the browser print dialog on each ticket. For one-touch silent printing, start Chrome with `--kiosk-printing`:
  `"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk-printing --kiosk http://127.0.0.1:8000/kiosk`
- If printing fails, the kiosk has a **Printer not working?** button; the report appears in the admin dashboard alert.
- With **Print tickets** off, the kiosk shows the tracking QR on screen instead of printing.

## Display PC

- Open `/display` and press F11. It shows the now-serving numbers, window grid, next tickets, banner, and any images/videos from the `media/` folder.
- Put image/video files in `media/` on the server PC; the admin **Display & media** tab lists what it found. No browser upload.
- Announcements use the browser's text-to-speech. Install an English and a Filipino voice in Windows for both languages to sound right (Filipino voice availability is still an open item, O-002).

## Phone tracking

- Tickets print a QR when **Tracking** and **Show QR on ticket** are on. The QR opens `/track/<public_id>` and shows only the ticket number, status, people ahead, estimated wait, and now-serving numbers.
- Phones must be on the same Wi-Fi/LAN as the server. If the QR points to `127.0.0.1`, set **System → Tracking base URL** to the server's LAN address (for example `http://192.168.1.20:8000`). Leave it blank to use whatever address the browser used.
- Windows Firewall must allow inbound TCP 8000 on the server PC, or other devices cannot connect.

## Backups and data

- **Admin → System → Create backup** writes a copy to `data/backups/`; set how many to keep there.
- Restore by stopping the server, replacing `data/queue.db` with a backup, and starting again.
- Reports live in **Admin → Reports**: daily summary, hourly volume, per service, per counter/staff (busy, idle, break), priority lane, searchable ticket history with timeline, CSV export for Excel, and a printable PDF summary.

## Troubleshooting

- **Port already in use:** stop the other process on port 8000 or run with `--port 8001` and use that address everywhere.
- **Blank page after an update:** rebuild the frontend with `cd frontend && npm run build`.
- **Wrong times or reset hour:** check the timezone in **Admin → System** (default `Asia/Manila`).
- **Duplicate ticket message at the kiosk:** wait the configured delay (default 15 s) or raise/lower **Duplicate ticket delay** in the kiosk settings.
- **Staff cannot log in:** PINs are set per staff in **Admin → Staff**; five wrong attempts lock that username for five minutes.
- **Phone cannot open the tracking page:** confirm the phone is on the office Wi-Fi, the tracking base URL is the LAN address, and the firewall allows port 8000.

## Verification scripts

Run against a live server on `127.0.0.1:8000` (admin `admin` / `secret123` in the demo database):

```bash
python scripts/queue_check.py     # queue engine and concurrency
python scripts/ui_phase5.py       # admin panel
python scripts/ui_phase6.py       # reports (20 checks)
python scripts/ui_phase7.py       # tracking and QR (20 checks)
python scripts/load_test.py       # 300 tickets, 5 counters, 8 callers on a throwaway DB
```

`load_test.py` copies the database to `data/loadtest.db`, starts its own server on port 8010, and removes the copy afterwards.

## Updating

```bash
git pull
python -m pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
# restart the server process
```

The database schema is migrated automatically at startup. Back up `data/queue.db` before updating a live site.
