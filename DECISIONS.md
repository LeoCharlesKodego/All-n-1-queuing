# DECISIONS.md — Queue System decision register

Status values: **Approved** (user decided), **Proposed** (agent suggestion, waiting for the user), **Superseded**.
The agent never marks its own proposals as Approved. New entries continue the numbering.

## Approved decisions

| ID | Decision | Date |
|---|---|---|
| D-001 | The product is a configurable, all-in-one queuing platform for any institution in the Philippines. A setup wizard asks what the system is for, and it is up to the user how it is configured. One generic engine with presets. | 2026-11-18 |
| D-002 | Presets: Government/LGU, Payment establishment, Hospital/clinic, Bank/cooperative, Church/parish, School/university, Generic/custom. A preset is only a starting point; everything stays editable. | 2026-11-18 |
| D-003 | "Payment establishment" means physical bill-payment places such as water districts and electric cooperatives, which have long queues every day. The preset is built for high volume: many cashier counters per service, express lane, cut-off time, queue-size alert, estimated wait. | 2026-11-18 |
| D-004 | The system is queue only. It does not record or process payments, billing, or POS. | 2026-11-18 |
| D-005 | Each service can optionally ask for an account / reference number at the kiosk. Off by default; shown to the cashier on call. | 2026-11-18 |
| D-006 | Delivery is web-browser based. One server PC on the local network; all other devices use browsers. Must work fully offline. | 2026-11-18 |
| D-007 | Setup wizard has 8 steps (institution, services, counters, priority rules, ticket intake, display and language, admin and network, review and finish). Wizard and admin panel edit the same settings. | 2026-11-18 |
| D-008 | Priority types Senior Citizen, PWD, Pregnant are on by default; they can be renamed, disabled, or extended. | 2026-11-18 |
| D-009 | Ticket intake is configurable as any mix of kiosk, staff-issued, and QR on phone. The "Issue ticket" button on the counter console appears only when staff-issued intake is enabled. | 2026-11-18 |
| D-010 | Kiosk asks the priority question first, then the service, then the optional account number. Print is the default; a no-print mode shows a QR on screen so the customer gets the ticket on their phone. | 2026-11-18 |
| D-011 | Counter console actions: call next, recall, start serving, done, skip / no-show, transfer, hold, break / away, close counter. | 2026-11-18 |
| D-012 | Staff are created by the admin in the admin panel and log in with a short PIN; each staff member has an assigned counter. | 2026-11-18 |
| D-013 | A skipped customer is recalled up to 3 times (configurable wait between recalls), then marked no-show. A returning customer can be re-entered at the end of the line. | 2026-11-18 |
| D-014 | Public display is a split screen: queue area plus media area, scrolling banner, and full-screen media when the queue is empty. | 2026-11-18 |
| D-015 | Display announcements use browser text-to-speech (English, Filipino, or both). No pre-recorded voice clips in version 1. | 2026-11-18 |
| D-016 | Multiple displays are supported, all showing the same queue. Assigning a display to certain services or windows is a later feature. | 2026-11-18 |
| D-017 | Display media (videos and images) comes from a folder on the server PC. No browser upload. No online links in version 1. | 2026-11-18 |
| D-018 | One office only (single site) and a single admin account at setup. Multi-branch is later. | 2026-11-18 |
| D-019 | No audit log of admin changes. Ticket timestamps and ticket events are still stored because reports need them. | 2026-11-18 |
| D-020 | Reports (daily summary, volume by hour / day, by service, by counter and staff, priority lane, searchable ticket history) live inside the admin panel only, admin only. Date range picker; CSV and PDF export. | 2026-11-18 |
| D-021 | Stack: Python (FastAPI), SQLite, React served by the same backend, WebSockets for live updates. Routes: /kiosk, /counter, /display, /admin, /track. | 2026-11-18 |
| D-022 | Phone tracking is local-network (Wi-Fi) only in version 1, but configurable per setup depending on how tickets are issued, and built so online tracking can be added later (address comes from the `tracking_base_url` setting). | 2026-11-18 |
| D-023 | Version 1 install is a plain "run the server" setup. A Windows installer comes later. | 2026-11-18 |
| D-024 | Screens and announcements support English and Filipino from the start, through translation catalogs. No hardcoded user-facing text. | 2026-11-18 |
| D-025 | Build in 7 phases (foundation and wizard; core queue and counter console; kiosk and printing; public display; admin completion; reports; phone tracking and polish). One phase at a time. | 2026-11-18 |

## Proposed (agent suggestions awaiting the user)

| ID | Decision | Date |
|---|---|---|
| D-026 | Frontend is built with React 18 + Vite (`npm install && npm run build`); the built bundle is served locally by FastAPI. These are build-time only; runtime stays offline. | 2026-11-18 |
| D-027 | Timezone handling uses `zoneinfo` when the OS has tz data, otherwise a fixed UTC offset for the three zones offered in setup (Asia/Manila +8, Asia/Singapore +8, UTC +0). Both PH zones have no DST, so the offset is exact. This avoids the `tzdata` package dependency on Windows. | 2026-11-18 |
| D-028 | Defaults for open items: `interleave` prioritises every 3rd call (N=3); daily reset at 00:00 local time; recall wait 60 s; recall limit 3; default service time 300 s; queue alert thresholds come from the preset (Bill Payment 40, Express 15); image duration 10 s. All editable in admin/setup. Proposed answers to O-003, O-005, O-006. | 2026-11-18 |
| D-029 | At the daily reset, tickets still active from an earlier business date are set to `cancelled` with an `expired` event (they are never called on the new day); numbering for the new day starts at 001. The sweep runs at startup and every 30 s. | 2026-11-18 |
| D-030 | Tickets print with the browser print dialog from a print-only 58/80 mm CSS layout; for silent one-touch printing run Chrome with `--kiosk-printing`. A browser cannot see paper-out/offline state, so the kiosk offers a "Printer not working?" report that stores `printer_status` + `printer_note` for the admin alert; automatic detection waits for the real printer (O-001). | 2026-11-18 |

## Open items

| ID | Item | Needed by |
|---|---|---|
| O-001 | Real thermal printer model(s) and paper size(s) for the first site; confirm the exact browser setup that prints silently with one touch (58/80 mm layout is ready; hardware test pending). | Phase 3 |
| O-002 | Confirm Filipino text-to-speech voice availability on the display PC (voice quality depends on what is installed). If unavailable, decide on a fallback (for example, announce in English or use a chime). | Phase 4 |
| O-003 | Confirm the exact behavior of `interleave` priority mode (every Nth call goes to a waiting priority ticket) and its default N. | Phase 2 |
| O-004 | Confirm with each institution the legal or policy basis for the default priority lanes. | Before go-live |
| O-005 | Default daily reset time (start of day vs. opening time). | Phase 2 |
| O-006 | Default values: recall wait between attempts, queue-size alert threshold, default service time when there is no history, image display duration. | Phases 2 to 5 |
