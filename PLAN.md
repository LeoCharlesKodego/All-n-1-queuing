# PLAN.md — Queue System build phases

**Current phase:** Phase 7 — phone tracking and polish
**Last updated:** 2026-11-18

Rules for this file:
- Work through the phases in order, continuously, without waiting for approval between phases (see AGENTS.md section 8 for the only reasons to stop).
- Tick a task only after it was verified live (see AGENTS.md section 3, rule 4).
- Mark tasks that need real hardware or user input as `[pending user]` and continue.
- After each phase, add a short entry to the Progress log below (max 8 lines) and commit.
- Each phase must leave the project in a working, runnable state.

---

## Phase 1 — Foundation

Goal: a running server, database, settings, setup wizard, and admin login.

- [x] Project structure (backend, frontend, media folder, translations, README with run steps)
- [x] FastAPI server serving the built React app; health check endpoint
- [x] SQLite database layer and migrations; all core tables from SPEC section 6
- [x] Settings storage (typed, editable, read by wizard and admin)
- [x] Translation layer with `en` and `fil` catalogs; language switch works; no hardcoded user-facing text
- [x] Setup wizard, all 8 steps, with presets (including Payment establishment) and sensible defaults
- [x] Wizard "test" step that creates a demo ticket
- [x] Single admin account creation; hashed password; login with rate limiting
- [x] First-run detection: wizard shows until setup is complete, then routes go to the system

Exit criteria:
- Fresh checkout starts with the documented commands and opens the wizard
- Completing the wizard with the Payment establishment preset produces the expected services, counters, and priority types in the database
- Admin can log out and log back in; wrong password is rejected and rate limited
- Switching language changes every wizard screen

---

## Phase 2 — Core queue

Goal: the queue works end to end, even if screens are plain.

- [x] Ticket issuing: per-service numbering with prefix, daily reset at the configured time
- [x] Priority types on tickets; `priority_first` and `interleave` modes
- [x] Per-service cut-off time enforced at issue time
- [x] Atomic call-next (single transaction); counter only sees its own services
- [x] Ticket lifecycle and events log (issue, call, recall, serve, done, skip, no-show, hold, resume, transfer)
- [x] Recall limit (3) with configurable wait, then no-show; re-entry at end of line
- [x] Transfer between services (optionally keeping original place)
- [x] Staff accounts (admin-created) with PIN login and assigned counter
- [x] Counter console: all actions, running timer, waiting list, counts, break / away / close, keyboard shortcuts
- [x] WebSocket updates for counter changes
- [x] Estimated wait calculation

Exit criteria:
- Two counters pressing Call Next at the same moment never receive the same ticket (tested live, repeated many times)
- Priority modes behave as specified
- Closing a service or disabling a counter does not lose or renumber waiting tickets
- Timestamps and events are correct for a full ticket lifecycle

---

## Phase 3 — Kiosk and ticket

Goal: customers can take a ticket, and tickets print.

- [x] Kiosk flow: welcome, language toggle, priority question first, service choice, optional account number pad, ticket issued
- [x] Greyed-out closed or past-cut-off services with reason
- [x] Duplicate-ticket delay
- [x] Ticket print layout for 58 mm and 80 mm
- [pending user] Test printing on a real thermal printer (O-001)
- [pending user] Printer error handling: kiosk reports a printer problem and shows a message; automatic paper-out detection needs hardware testing
- [x] No-print mode: on-screen QR to get the ticket on a phone
- [x] Staff-issued tickets from the counter console, shown only when enabled in setup
- [x] Fullscreen kiosk behavior

Exit criteria:
- Ticket printed from the kiosk with one touch (document the exact browser setup used)
- Kiosk usable on a touchscreen by a non-technical person
- Findings about printing recorded in `DECISIONS.md`

---

## Phase 4 — Public display

Goal: the waiting-area TV works reliably.

- [x] Display layout: NOW SERVING, window list with closed/away state, next in line, header, banner
- [x] Live updates over WebSocket; automatic reconnect and state recovery
- [x] Chime, flash, and browser text-to-speech announcement in English and Filipino; recall repeats
- [x] "Start Display" audio unlock and sound test
- [x] Media area: playlist from the server media folder (videos and images), looping, image duration, volume ducking during announcements
- [x] Empty-queue full-screen media mode
- [x] Scrolling banner text
- [x] Multiple displays showing the same queue

Exit criteria:
- Calling a number updates the display instantly and announces it
- Display survives a server restart and a browser refresh without manual steps beyond the audio unlock
- Media files added to the server folder appear in the playlist after a rescan

---

## Phase 5 — Admin panel completion

Goal: everything configurable and monitorable from the admin panel.

- [x] Live dashboard (issued, waiting, serving, completed, average wait and service time, counter status, queue-size alerts)
- [x] Services, Counters, Staff management (add, edit, disable, reset PIN)
- [x] Priority rules management
- [x] Display and media settings (layout, banner, voice and language, media folder status, optional schedule)
- [x] Kiosk and ticket settings (design, paper size, printer test, intake methods, duplicate delay)
- [x] System: institution info, backup and restore, daily reset time, network address, "test everything" page
- [x] Automatic daily backup on the server

Exit criteria:
- Every setting made in the wizard is editable in the admin panel and takes effect immediately
- Backup file can be restored on a clean install and the data matches
- Editing services and counters while tickets are waiting loses nothing

---

## Phase 6 — Reports

Goal: managers can see and export what happened.

- [x] Daily summary
- [x] Volume by hour and by day / week
- [x] By service
- [x] By counter and by staff (served, average service time, idle and break time)
- [x] Priority lane report
- [x] Searchable ticket history with full timeline
- [x] Date range picker, filters (service, counter, staff)
- [x] CSV and PDF export; print-friendly daily summary
- [x] Admin-only access enforced on the server

Exit criteria:
- Report numbers match the underlying tickets and events (spot-checked by hand)
- Exports open correctly

---

## Phase 7 — Phone tracking and polish

Goal: finish version 1 and prove it under load.

- [ ] `/track/<public_id>` page (ticket, status, people ahead, now serving, estimated wait)
- [ ] Tracking QR on tickets and on the no-print kiosk screen; driven by `tracking_base_url` and the per-setup toggle
- [ ] Reconnection handling and clear error messages across all screens
- [ ] Complete Filipino translation review for every screen and announcement
- [ ] Load test with simulated heavy day (hundreds of tickets, many counters, simultaneous calls)
- [ ] Final README: install, run, printer setup, backup, troubleshooting

Exit criteria:
- Simulated high-volume day completes with correct numbering and no duplicate calls
- Phone on the office Wi-Fi can track a ticket live
- A person who did not build the system can set it up from the README

---

## Later (not in version 1)

Windows installer, online tracking, SMS notifications, appointments / pre-booking, multi-branch, display-to-service assignment, optional online media links.

---

## Progress log

(The agent adds one short entry per finished phase: date, phase, what was done and how it was verified, what is deferred or `[pending user]`, how to run it.)

### 2026-11-18 — Phase 6 — Reports ✅
- Backend: `reports.py` aggregation (summary, hourly, daily, service, counter/staff busy-idle-break, priority, history, per-ticket timeline), CSV with BOM for Excel, hand-rolled text PDF; admin-only endpoints `/api/admin/reports`, `/reports/tickets/{id}`, `/reports/export.csv`, `/reports/export.pdf`.
- Frontend: Reports tab with range shortcuts, service/counter/staff filters, summary cards, 24-hour bars, daily/service/counter/staff/priority tables, searchable history with timeline modal, CSV/PDF links, print-only header.
- Verified live via `scripts/ui_phase6.py` (20/20 checks): UI numbers equal API and hand-run SQL (76 issued, 45 done, 1 no-show, 1 transferred, avg 2m 22s, peak 11:00/66); service filter 11; yesterday 0; CSV/PDF downloads open (PDF rendered in Chrome); print media hides controls; Filipino tab renders; no page errors.
- Proposed: none. Run: same server; open `/admin` → Reports (admin `admin`/`secret123`).

### 2026-11-18 — Phase 5 — Admin panel ✅
- Tabbed admin panel: dashboard (stats, queue alerts, counters, printer), Services, Counters, Staff, Priority rules, Display & media, Kiosk & ticket, System; all text in EN/FIL.
- Feature prefixes/names/hours/express, counter-service assignment, staff PIN reset/disable, priority mode, banner/voice/layout/media schedule, ticket paper/printer test, institution/logo/timezone/tracking, LAN QR, 12 system checks, backup list/create/restore.
- Verified live in Chrome via Playwright: renamed a service and disabled a counter while tickets waited (numbers and waiting status unchanged), staff created and signed in at its counter, banner + `screen_language=both` reached the display, media pane hidden outside `media_schedule` and shown inside with a test image, all 12 checks OK, backup created then restored (post-backup marker ticket gone, counts back).
- `[pending user]`: real thermal printer output (O-001); print test uses the browser dialog.
- Run: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`, open `/admin` (demo admin `admin` / `secret123`).

### 2026-11-18 — Phase 4 — Public display ✅
- Display: header with logo/name/clock, NOW SERVING box with flash, window grid (called/serving/open/break/closed), next-in-line chips, scrolling banner, split media pane, empty-queue full-screen media.
- Live: WebSocket call events update all open displays instantly, chime + EN/FIL speech (voice_lang), "Start display" audio unlock, sound test, reconnect badge; polls every 30 s as a safety net.
- Media: image/video playlist from `media/`, image duration, video looping, volume ducked to 0.08 during announcements.
- Verified live in Chrome via Playwright: call from a counter changed two displays at once and set the flash class; speech text queued (EN + FIL) with audio context chime; media rotation and video playback worked; empty queue showed full-screen media and split layout returned when a ticket was issued; killing the server showed "Reconnecting…" and restarting cleared it while keeping the last state; bilingual screen labels (`screen_language=both`).
- Limitation: speech audibility/voice quality cannot be judged headlessly (O-002 pending); test media files were removed after verification.

### 2026-11-18 — Phase 3 — Kiosk and ticket ✅
- Kiosk: welcome + language toggle, priority question, service grid with closed/cut-off reasons and waiting counts, account-number keypad, ticket screen with number/people ahead/estimate/QR, 12 s auto-return, automatic fullscreen on first tap.
- Ticket: print-only layout for 58 mm and 80 mm (Chrome kiosk-printing recommended), no-print mode shows the QR, printer-problem button reports `printer_status`/`printer_note` for the admin alert.
- Verified live in Chrome via Playwright: full EN flow incl. account number, FIL welcome, duplicate-delay message (57 s), disabled service reason, print-media screenshots for both paper sizes, no-print QR notice, printer report endpoint, fullscreen true after first tap.
- `[pending user]`: real thermal printer test and automatic paper-out/offline detection (O-001).
- Proposed: D-030 (browser print strategy and manual printer-problem report).

### 2026-11-18 — Phase 2 — Core queue ✅
- Backend: staff PIN auth (PBKDF2, rate limit, session cookie), call-next/start/done/recall/skip/hold/resume/transfer/reenter/status/issue endpoints, admin staff CRUD, daily-reset sweep that cancels previous business dates, ticket events log.
- Frontend: `/counter` console (login, current ticket + timer, waiting and parked lists, action grid, transfer/issue modals, keyboard shortcuts, EN/FIL switch).
- Verified live via Playwright + API scripts: 30 simultaneous call-next requests on 3 counters produced 0 duplicates; interleave and priority_first ordering; transfer (new number called by target counter), hold/resume with recall wait, skip×3 → no-show → reentry, staff-issued ticket, break/away, logout; WebSocket pushed a new ticket to an open console without reload; cutoff returned 409; previous-day waiting ticket auto-cancelled with `expired` event.
- Deferred: counter/service editing UI in admin (Phase 5).
- Run: same as Phase 1; `/counter` PINs from `POST /api/admin/staff` (demo staff ana/1111 … eve/5555 created by `scripts/queue_check.py`).

### 2026-11-18 — Phase 1 — Foundation ✅
- Backend: FastAPI app, SQLite schema/migrations, typed settings, PBKDF2 admin auth + session cookies, login rate limit (5 fails / 5 min), backup module.
- Frontend: React shell with hand-rolled routes, EN/FIL catalogs, Home, full 8-step setup wizard (all presets incl. Payment establishment), admin login.
- Verified live in Chrome via Playwright: completed the whole wizard in EN and switched steps to FIL, Payment preset wrote 5 services / 5 counters / 3 priority types; demo ticket B-001 created; wrong password rejected; 6th attempt returned 429; logout invalidated session.
- Deferred: full admin panel (Phase 5), kiosk/counter/display/track screens are placeholders until their phases.
- Proposed: D-026 (Vite build), D-027 (tz fallback), D-028 (defaults for O-003/O-005/O-006).
- Run: `pip install -r requirements.txt`, `cd frontend && npm install && npm run build`, `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`, open `/setup`.
