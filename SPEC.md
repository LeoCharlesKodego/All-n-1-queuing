# SPEC.md — Queue System

Status: approved plan, version 1. Anything not listed here is not approved; ask first.

## 1. Overview

A configurable queuing platform for Philippine institutions. One engine, many presets. Browser-based, runs on one server PC on the local network, fully offline.

Primary use case driving the design: **payment establishments** (water districts, electric cooperatives) where customers physically pay bills and the line is long every day. The system must handle high daily volume with many cashier windows, an express lane, and clear communication of waiting time.

The system is **queue only**. It calls numbers. It does not record or process payments.

## 2. Institution presets

The wizard asks for the institution type and pre-fills configuration. A preset is only a starting point; everything stays editable.

| Preset | Starting services (examples) |
|---|---|
| Government / LGU | Per department: Treasurer, Assessor, Civil Registrar, GSO, etc. Priority lanes on |
| **Payment establishment** | Bill Payment, New Connection / Application, Reconnection, Inquiry / Complaint. Express lane, cut-off time, queue-size alert on |
| Hospital / clinic | Registration, Consultation, Laboratory, Pharmacy, Cashier |
| Bank / cooperative | Teller, New Account, Loans, Customer Service |
| Church / parish | Certificates, Baptism / Wedding Inquiry, Mass Intentions |
| School / university | Registrar, Cashier, Clinic |
| Generic / custom | Blank |

Priority types (Senior Citizen, PWD, Pregnant) are on by default in all presets.

### Payment establishment preset details
- Several cashier counters can serve the same service and pull from one shared line.
- **Express lane** is a separate service flagged `is_express` with its own prefix and its own counters.
- Per-service **cut-off time**: stop issuing tickets at a set time while already-issued tickets are still served.
- **Queue-size alert** per service: the admin dashboard flags when waiting tickets pass a threshold.
- **Optional account / reference number** per service, entered at the kiosk, shown to the cashier on call. Off by default; one-tap ticket when off.

## 3. Setup wizard (first run, re-editable later)

The fastest setup is clicking Next with defaults. Setup can be edited later in the admin panel, which uses the same settings.

1. **Institution:** name, logo, address, contact number, institution type (picks preset). **Media** (optional): confirm the media folder for display ads and videos.
2. **Services:** name, prefix (A, B, C...), optional operating hours, optional cut-off time, express lane flag, "ask for account / reference number" toggle.
3. **Counters:** how many, their names (Window 1, Cashier 2, Room 3), which services each handles. One service can have many counters.
4. **Priority rules:** Senior Citizen, PWD, Pregnant on by default; rename, disable, or add. Choose mode: `priority_first` (a waiting priority ticket is called before regular ones) or `interleave` (every Nth call goes to a waiting priority ticket; N configurable).
5. **Ticket intake:** any mix of kiosk, staff-issued at a counter, and QR on phone. Print or no-print; if print, paper size 58 mm or 80 mm. Show estimated wait on ticket. Show tracking QR on ticket.
6. **Display and language:** English, Filipino, or both for screen text; voice announcements on/off and voice language.
7. **Admin account and network:** create the single admin (password). Show the server address other devices should open, with a QR to scan.
8. **Review and finish:** one summary page. Optional **test step** that issues a demo ticket so the kiosk, counter, and display can be seen working before going live.

## 4. Ticket model and lifecycle

- **Number:** `PREFIX-NNN` per service (for example `B-024`), zero-padded to 3 digits (wider if needed). Resets daily at a configurable reset time (default start of day, local timezone).
- **Statuses:** `waiting` → `called` → `serving` → `done`. Side states: `on_hold`, `no_show`, `cancelled`, `transferred` (event, ticket continues in the new service).
- **Timestamps:** `issued_at`, `called_at`, `serving_at`, `done_at`. Waiting time = `issued_at` to first `called_at`. Service time = `serving_at` to `done_at`.
- **Events log:** every issue, call, recall, serve, done, skip, no-show, hold, resume, transfer, with time and counter/staff.
- **Public id:** random, non-sequential, used only in tracking URLs.
- **Priority:** ticket carries an optional priority type chosen at issue.

### Call-next logic (server only, atomic)
1. Counter requests next. Server considers only tickets in services assigned to that counter.
2. Apply priority mode, then oldest `issued_at` first.
3. In one transaction, mark the chosen ticket `called` for that counter. Two counters can never get the same ticket.
4. Blocked while the counter still has a ticket in `called` or `serving` (to prevent accidental skipping).
5. Broadcast the update to display, counters, and tracking pages.

### Actions
- **Call Next, Recall:** recall repeats announcement and flash.
- **Start serving:** customer arrived at the window.
- **Done:** finishes transaction, frees counter.
- **Skip / No-show:** ticket may be recalled up to **3 times** with a configurable wait between recalls; then it becomes `no_show`. A returning customer can be re-entered at the end of the line.
- **Transfer:** move to another service, optionally keeping original `issued_at` and place in line.
- **Hold / Park:** set aside temporarily and bring back later.
- **Issue ticket (staff):** button on the counter console, shown only when staff-issued intake is enabled.

### Estimated wait
`people_ahead × average service time ÷ active counters` for that service, where average service time uses the last 20 completed tickets for that service; fall back to a default setting when there is no history. Shown on ticket, display, and tracking page when enabled.

## 5. Screens

### 5.1 Kiosk (`/kiosk`, touchscreen, fullscreen)
1. Welcome: logo, name, language toggle (English / Filipino).
2. **Priority question first** (only if priority rules are on): large buttons for each priority type, plus "None".
3. Choose service: large buttons, one per open service. Closed or past cut-off services are greyed out with a short reason.
4. Optional account / reference number (only for services where enabled): large on-screen number pad and Skip.
5. Ticket issued: shows number, people ahead, estimated wait; prints; returns to welcome after a few seconds.

Behaviors: large touch targets for non-technical and older users; a short delay between tickets to stop repeated taking; clear message and admin alert if the printer is out of paper or offline; **no-print mode** shows a QR on screen so the customer gets the ticket on their phone.

### 5.2 Printed ticket
Institution name and logo; ticket number in large text; service name; priority label if any; date and time; people ahead; tracking QR (when enabled). Layout designed for 58 mm and 80 mm thermal paper.

### 5.3 Counter console (`/counter`, staff login)
- Staff log in with a short **PIN** and pick or are assigned a counter.
- Current customer panel: number, service, priority label, account number if entered, running timer.
- Waiting list for this counter's services, priority marked, wait time shown.
- Counts: waiting, served today by this counter.
- Buttons: Call Next, Recall, Start, Done, Skip / No-show, Transfer, Hold, Issue ticket (if enabled).
- **Break / Away** shows "Window closed" on the display. Close counter at end of shift.
- Keyboard shortcuts for speed (for example Space = Call Next).
- A counter only sees and calls tickets for its own services.

### 5.4 Public display (`/display`, TV, no login, no controls)
- **Split screen, adjustable:** left = queue area, right = media area.
  - Queue area: large NOW SERVING box (for example `B-024 → Window 3`); list of all windows with their current number (closed or on break shows "Closed"); short "Next in line" list.
  - Media area: playlist of videos and images from the server media folder, looping.
  - Bottom banner: scrolling announcement text (admin-editable). Header: logo, name, date and time.
- **On call:** new number flashes; chime; voice announcement using browser text-to-speech ("Number B-024, please proceed to Window 3") in English, Filipino, or both per settings; video volume ducks during the announcement. Recall repeats it. Priority tickets are clearly marked.
- **Empty queue:** media goes full-screen; returns to split layout when a ticket is issued.
- **Audio unlock:** a one-time "Start Display" button (browsers block audio until interaction) plus a sound test.
- **Resilience:** if the connection drops, show a small "Reconnecting..." marker, keep last known state, reconnect automatically, and recover after a PC restart.
- **Multiple displays supported.** All show the same queue; assignment of a display to certain services or windows can be added later.

### 5.5 Admin panel (`/admin`, single admin)
- **Dashboard (live):** tickets issued, waiting, serving, completed today; average wait and service time; counter status and who is logged in; queue-size alerts.
- **Services, Counters, Staff** (name, username, PIN, assigned counter; deactivate; reset PIN), **Priority rules.**
- **Display and media:** layout, banner text, language and voice settings, media folder status (files found, playlist order, image duration), optional play schedule.
- **Kiosk and ticket:** ticket design, paper size, printer test, intake methods on/off, duplicate-ticket delay.
- **Reports** (admin only).
- **System:** institution info and logo; backup and restore the database; daily reset time; network address and a "test everything" page. Automatic daily backup on the server.
- Changes to services and counters apply immediately without losing or renumbering tickets already in line.
- **No audit log.** (Ticket timestamps and events still exist because reports need them.)

### 5.6 Reports (inside the admin panel, admin only)
- Daily summary: issued, served, no-show, transferred; average and longest wait; average service time; peak hour.
- Volume by hour and by day/week (shows payday and due-date rushes).
- By service.
- By counter and by staff: tickets served, average service time, idle and break time.
- Priority lane report: counts per priority type and average wait compared with regular customers.
- Searchable ticket history: full timeline for any ticket.
- Filters: date range picker (covers daily, weekly, monthly), service, counter, staff. Export CSV and PDF. Print-friendly daily summary.
- Data kept indefinitely by default; admin can archive or clear old data.

### 5.7 Phone tracking (`/track/<public_id>`)
- Opened by the QR on the ticket (or the on-screen QR in no-print mode).
- Shows ticket number, status, people ahead, now-serving numbers, and estimated wait.
- **Version 1 is local-network (Wi-Fi) only.** It is configurable per setup (QR on or off, depending on how tickets are issued) and driven by `tracking_base_url`, so an online address can be used later without code changes.

## 6. Data model (main tables)

Names are indicative; keep them consistent once chosen.

- `settings` (key/value or typed config): institution info, language, timezone, reset time, tracking base URL, display options, ticket options, default service time
- `services`: name, prefix, is_express, hours, cut_off_time, ask_account_number, queue_alert_threshold, is_active, sort order
- `counters`: name, is_active, status (`open`, `away`, `closed`)
- `counter_services`: counter ↔ service assignments
- `staff`: name, username, pin_hash, assigned counter, is_active
- `admin`: single admin credentials (hashed)
- `priority_types`: name, label (per language), is_active, sort order
- `tickets`: public_id, service, number (prefix + sequence), business date, priority type, account_number, status, counter, `issued_at`, `called_at`, `serving_at`, `done_at`, recall_count
- `ticket_events`: ticket, event type, counter, staff, timestamp, details
- `daily_counters`: per service per business date, last issued sequence
- `media_settings`: layout, image duration, schedule, banner text
- Translation catalogs live in files (`en`, `fil`), not in the database.

## 7. Printing

- The kiosk PC prints to a thermal printer (58 mm or 80 mm) from the browser. Recommended: Chrome in kiosk-printing mode for silent one-click printing.
- Ticket layout uses print CSS sized for those widths.
- Printing is the riskiest integration: test it early (Phase 3) with real hardware and record the findings in `DECISIONS.md`.

## 8. Security

- Admin password and staff PINs stored hashed; login rate-limited.
- Server-side role checks on every admin and staff route.
- `/kiosk`, `/display`, `/track` are public on the local network, have no controls, and expose no personal data.
- Account / reference numbers are shown only to the counter that called the ticket.

## 9. Non-goals (version 1)

Payments or billing, multi-branch, SMS, appointments, online tracking, Windows installer, audit log, pre-recorded voice clips, browser media upload.

## 10. Later

Windows installer, online tracking, SMS notifications, appointments / pre-booking, multi-branch, display-to-service assignment, optional online media links.
