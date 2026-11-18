# AGENTS.md — Queue System (All-in-One Queuing Platform)

You are the implementation agent for this project. Read this file fully before every session.

## 1. What this project is

A configurable, browser-based queuing platform for institutions in the Philippines (city halls, water districts, electric cooperatives, clinics, banks, parishes, schools, and generic offices). On first install a setup wizard asks what kind of institution it is and shapes the system around the answer. The core queue engine is the same for everyone; only configuration changes.

It runs on **one server PC on the local network, with no internet required**. Kiosk, counter PCs, display TVs, and the admin all open it in a web browser.

## 2. Read order (every session)

1. `AGENTS.md` (this file): rules
2. `SPEC.md`: what to build
3. `PLAN.md`: phases, tasks, and current status
4. `DECISIONS.md`: approved decisions (D-xxx) and open items (O-xxx)

Read each of these files **once per session**, in full. Do not re-read a file unless it changed or you need one specific section.

If anything in these files conflicts, `DECISIONS.md` wins, then `SPEC.md`, then `PLAN.md`. If something is missing or unclear, **stop and ask**; do not invent a decision.

## 3. Working rules (non-negotiable)

1. **Analyze before editing.** Read the relevant existing code and the relevant SPEC section first. State briefly what you will change and why.
2. **Minimal-change scope.** Change only what the current task requires. No drive-by refactors, renames, or reformatting of untouched code.
3. **No silent deletions.** Never delete or overwrite files, tables, columns, or features without saying so explicitly and getting approval.
4. **Mandatory live verification.** Do not claim something works because the code looks right. Run it: start the server, call the endpoint, open the page, exercise the flow, and report what you actually observed. If you could not run something, say so plainly.
5. **Phases in order, continuously.** Work through `PLAN.md` from the current phase to Phase 7 in order, without waiting for approval between phases. Finish, verify, and commit one phase before starting the next. Stop only for the conditions in section 8.
6. **Conventional commits.** Use `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`. Small, focused commits.
7. **No cloud services without approval.** No external APIs, CDNs, analytics, fonts from the internet, or hosted databases. The system must run fully offline.
8. **No new dependencies without approval.** Prefer the standard library and the stack in section 4. If you need a new package, name it, say why, and wait.
9. **Log decisions.** Any choice not already in `DECISIONS.md` gets a proposed entry (status: Proposed) and is raised with the user.
10. **Keep the plan current.** Tick tasks in `PLAN.md` only after live verification. Update the status line at the top.

## 4. Fixed technical direction (see DECISIONS.md)

- **Backend:** Python, FastAPI.
- **Database:** SQLite (single file). Keep data access in one layer so PostgreSQL could be added later.
- **Frontend:** React, built once and served by the same backend. One process to run.
- **Live updates:** WebSockets (display, counters, kiosk, and phone tracking update instantly).
- **Routes:** `/setup`, `/kiosk`, `/counter`, `/display`, `/admin`, `/track/<public_id>`.
- **Languages:** English and Filipino from the start.
- **Timezone:** store timestamps in UTC; the daily reset and all displayed times use the configured local timezone (default `Asia/Manila`).
- **Install (v1):** plain "run the server" setup. A Windows installer comes later.

## 5. Architecture rules

- **All queue logic lives on the server, in one module.** The frontend never decides who is called next.
- **Call-next must be atomic.** Use a database transaction so two counters can never receive the same ticket, even on simultaneous clicks.
- **Everything configurable lives in the database**, not in code or constants. The setup wizard and the admin panel edit the same settings.
- **Never lose or renumber existing tickets** when services or counters are edited or disabled. Waiting tickets are always still served.
- **Every ticket keeps its own timestamps:** issued, called, serving started, done, plus a ticket events log. Reports depend on them.
- **Internationalization from day one.** No hardcoded user-facing text. All strings go through translation catalogs (`en`, `fil`). Adding a language must not require touching components.
- **Offline-first.** Bundle all assets locally. No internet calls at runtime.
- **Security basics.** Hash admin password and staff PINs. Rate-limit login attempts. Role checks on the server for every protected route (admin vs. staff). `/kiosk`, `/display`, and `/track` have no controls and expose no personal data.
- **Tracking page** shows only ticket number, status, position in line, and the now-serving numbers. Use a random public id in the URL, never a sequential number.
- **Tracking address is a setting** (`tracking_base_url`), so the QR can point to a local address now and an online address later without code changes.
- **Media** for the display comes from a folder on the server PC (no browser upload). The server serves those files; the admin panel shows what it found.

## 6. Out of scope for version 1

Do not build these unless the user explicitly asks:

- Recording payments, billing, or any POS function (this is a queue system only)
- Multi-branch / multi-site management
- SMS notifications, appointments / pre-booking
- Online (internet) phone tracking
- Windows installer
- Audit log of admin changes (explicitly declined)
- Pre-recorded voice clips (browser text-to-speech only)
- Uploading media through the browser

## 7. Verification checklist (before ending any phase)

- [ ] Server starts from a clean checkout following the README steps
- [ ] Every feature in the phase was exercised live, not just read
- [ ] Two simultaneous actions tested where relevant (for example, two counters calling next)
- [ ] Both languages checked on every new screen
- [ ] No hardcoded text, no internet dependency introduced
- [ ] `PLAN.md` ticked, status line updated, new decisions logged in `DECISIONS.md`
- [ ] Changes committed with conventional commit messages

## 8. Running phases without prompts

After the first start prompt, continue through all phases on your own.

**After each phase:**
1. Run the verification checklist (section 7).
2. Tick `PLAN.md` and add a **Progress log** entry (max 8 lines: done, how verified, deferred, new proposals, how to run it).
3. Commit with a conventional commit message.
4. Start the next phase immediately.

**Stop and ask the user only when:**
- A decision is needed that is not in `DECISIONS.md` (log it as Proposed first).
- A new dependency or any cloud service would be required.
- An open item (O-xxx) needs real hardware or user input (for example the thermal printer, Filipino voice). Build everything around it, mark the task `[pending user]` in `PLAN.md`, and continue with the other tasks.
- An exit criterion still fails after two fix attempts.
- A destructive action is needed (deleting or overwriting existing work).

Do not stop for routine confirmation. Do not ask permission to start the next phase.

**Final report** (after Phase 7, max 25 lines): what was built, what is `[pending user]`, open items still needed, exact commands to run it, and known risks.

## 9. Token economy (important)

- Work from `PLAN.md`; do not re-derive the plan or restate the spec in chat.
- Read only what a task needs: search first (grep / file search), then read the relevant line range, not whole files.
- Never print or paste whole files, long logs, or full command output. Quote only the lines that matter.
- Keep chat replies short. No summaries of what you are about to do or just did, beyond the Progress log entry.
- Batch related edits into one pass per file; avoid rewriting a whole file for a small change.
- Reuse existing components, helpers, and translation keys instead of duplicating them.
- Do not re-run the full test suite or reinstall dependencies when nothing relevant changed; run the smallest check that proves the change.
- Keep the Progress log in `PLAN.md` accurate so a resumed session can continue from it without re-reading the codebase.
- Quality comes first: saving tokens never means skipping live verification.
