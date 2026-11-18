# PLAN.md — Queue System build phases

**Current phase:** Phase 3 — kiosk and ticket
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

- [ ] Kiosk flow: welcome, language toggle, priority question first, service choice, optional account number pad, ticket issued
- [ ] Greyed-out closed or past-cut-off services with reason
- [ ] Duplicate-ticket delay
- [ ] Ticket print layout for 58 mm and 80 mm; test on real thermal printer
- [ ] Printer error handling (out of paper / offline) with kiosk message and admin alert
- [ ] No-print mode: on-screen QR to get the ticket on a phone
- [ ] Staff-issued tickets from the counter console, shown only when enabled in setup
- [ ] Fullscreen kiosk behavior

Exit criteria:
- Ticket printed from the kiosk with one touch (document the exact browser setup used)
- Kiosk usable on a touchscreen by a non-technical person
- Findings about printing recorded in `DECISIONS.md`

---

## Phase 4 — Public display

Goal: the waiting-area TV works reliably.

- [ ] Display layout: NOW SERVING, window list with closed/away state, next in line, header, banner
- [ ] Live updates over WebSocket; automatic reconnect and state recovery
- [ ] Chime, flash, and browser text-to-speech announcement in English and Filipino; recall repeats
- [ ] "Start Display" audio unlock and sound test
- [ ] Media area: playlist from the server media folder (videos and images), looping, image duration, volume ducking during announcements
- [ ] Empty-queue full-screen media mode
- [ ] Scrolling banner text
- [ ] Multiple displays showing the same queue

Exit criteria:
- Calling a number updates the display instantly and announces it
- Display survives a server restart and a browser refresh without manual steps beyond the audio unlock
- Media files added to the server folder appear in the playlist after a rescan

---

## Phase 5 — Admin panel completion

Goal: everything configurable and monitorable from the admin panel.

- [ ] Live dashboard (issued, waiting, serving, completed, average wait and service time, counter status, queue-size alerts)
- [ ] Services, Counters, Staff management (add, edit, disable, reset PIN)
- [ ] Priority rules management
- [ ] Display and media settings (layout, banner, voice and language, media folder status, optional schedule)
- [ ] Kiosk and ticket settings (design, paper size, printer test, intake methods, duplicate delay)
- [ ] System: institution info, backup and restore, daily reset time, network address, "test everything" page
- [ ] Automatic daily backup on the server

Exit criteria:
- Every setting made in the wizard is editable in the admin panel and takes effect immediately
- Backup file can be restored on a clean install and the data matches
- Editing services and counters while tickets are waiting loses nothing

---

## Phase 6 — Reports

Goal: managers can see and export what happened.

- [ ] Daily summary
- [ ] Volume by hour and by day / week
- [ ] By service
- [ ] By counter and by staff (served, average service time, idle and break time)
- [ ] Priority lane report
- [ ] Searchable ticket history with full timeline
- [ ] Date range picker, filters (service, counter, staff)
- [ ] CSV and PDF export; print-friendly daily summary
- [ ] Admin-only access enforced on the server

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
