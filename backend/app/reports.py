"""Report queries and exports (CSV, PDF). Admin-only callers live in routers/admin.py."""
import csv
import io
from collections import Counter
from datetime import datetime, time, timezone as dt_timezone

from . import db, queue


def _dt(value):
    return db.parse_utc(value) if value else None


def _seconds(later, earlier):
    if not later or not earlier:
        return None
    return max(0, int((later - earlier).total_seconds()))


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values)) if values else None


def local_range(date_from: str, date_to: str, timezone: str):
    """UTC bounds for a business-date range, used only for event tables."""
    tz = queue.local_tz({"timezone": timezone})
    start = datetime.combine(datetime.fromisoformat(date_from).date(), time(0, 0), tzinfo=tz)
    end = datetime.combine(datetime.fromisoformat(date_to).date(), time(23, 59, 59), tzinfo=tz)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


def ticket_rows(conn, date_from, date_to, service_id=None, counter_id=None, staff_id=None):
    where = ["t.business_date BETWEEN ? AND ?"]
    params = [date_from, date_to]
    if service_id:
        where.append("t.service_id = ?")
        params.append(int(service_id))
    if staff_id:
        where.append("t.staff_id = ?")
        params.append(int(staff_id))
    if counter_id:
        where.append("t.counter_id = ?")
        params.append(int(counter_id))
    sql = f"""
        SELECT t.*, s.name AS service_name, c.name AS counter_name,
               st.name AS staff_name, p.name_en AS priority_en, p.name_fil AS priority_fil,
               (SELECT COUNT(*) FROM ticket_events e
                 WHERE e.ticket_id = t.id AND e.event_type = 'transfer') AS transfers
        FROM tickets t
        LEFT JOIN services s ON s.id = t.service_id
        LEFT JOIN counters c ON c.id = t.counter_id
        LEFT JOIN staff st ON st.id = t.staff_id
        LEFT JOIN priority_types p ON p.id = t.priority_type_id
        WHERE {' AND '.join(where)}
        ORDER BY t.business_date DESC, t.id DESC
    """
    return db.all_rows(conn, sql, tuple(params))


def _hour_local(iso, tz):
    value = _dt(iso)
    return value.astimezone(tz).hour if value else None


def _status_times(rows):
    waits, services = [], []
    for r in rows:
        issued, called = _dt(r["issued_at"]), _dt(r["called_at"])
        serving, done = _dt(r["serving_at"]), _dt(r["done_at"])
        if called:
            waits.append(_seconds(called, issued))
        if done:
            services.append(_seconds(done, serving or called))
    return waits, services


def _event_seconds(conn, date_from, date_to, timezone, counter_id=None, staff_id=None):
    """Open/away/closed seconds per counter (or staff) inside the local range."""
    start, end = local_range(date_from, date_to, timezone)
    where = ["created_at BETWEEN ? AND ?"]
    params = [start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")]
    if counter_id:
        where.append("counter_id = ?")
        params.append(int(counter_id))
    if staff_id:
        where.append("staff_id = ?")
        params.append(int(staff_id))
    rows = db.all_rows(
        conn,
        f"SELECT counter_id, staff_id, event_type, created_at FROM counter_events "
        f"WHERE {' AND '.join(where)} ORDER BY counter_id, created_at",
        tuple(params),
    )
    groups = {}
    for row in rows:
        key = row["counter_id"] if not staff_id else row["staff_id"]
        groups.setdefault(key, []).append(row)
    totals = {}
    for key, events in groups.items():
        open_s = break_s = 0
        previous = None
        previous_type = None
        for event in events:
            at = _dt(event["created_at"])
            if previous and previous_type in ("open", "away", "login"):
                span = int((at - previous).total_seconds())
                if previous_type == "away":
                    break_s += span
                else:
                    open_s += span
            previous, previous_type = at, event["event_type"]
        totals[key] = {"open": open_s, "break": break_s}
    return totals


def build(conn, date_from, date_to, timezone="Asia/Manila", service_id=None,
          counter_id=None, staff_id=None, search=None):
    tz = queue.local_tz({"timezone": timezone})
    rows = ticket_rows(conn, date_from, date_to, service_id, counter_id, staff_id)
    done = [r for r in rows if r["status"] == "done"]
    no_show = [r for r in rows if r["status"] == "no_show"]
    waits, services = _status_times(rows)
    hours = Counter()
    served_hours = Counter()
    for r in rows:
        hour = _hour_local(r["issued_at"], tz)
        if hour is not None:
            hours[hour] += 1
        if r["done_at"]:
            h = _hour_local(r["done_at"], tz)
            if h is not None:
                served_hours[h] += 1
    peak = max(hours, key=hours.get) if hours else None
    summary = {
        "issued": len(rows),
        "served": len(done),
        "waiting": len([r for r in rows if r["status"] == "waiting"]),
        "serving": len([r for r in rows if r["status"] == "serving"]),
        "no_show": len(no_show),
        "transferred": len([r for r in rows if r["transfers"]]),
        "avg_wait_seconds": _avg(waits),
        "longest_wait_seconds": max(waits) if waits else None,
        "avg_service_seconds": _avg(services),
        "peak_hour": peak,
        "peak_count": hours.get(peak, 0) if peak is not None else 0,
    }

    by_service = {}
    for r in rows:
        item = by_service.setdefault(r["service_id"], {
            "id": r["service_id"], "name": r["service_name"], "issued": 0, "served": 0,
            "no_show": 0, "waits": [], "services": []})
        item["issued"] += 1
        if r["status"] == "done":
            item["served"] += 1
        if r["status"] == "no_show":
            item["no_show"] += 1
        if r["called_at"]:
            item["waits"].append(_seconds(_dt(r["called_at"]), _dt(r["issued_at"])))
        if r["done_at"]:
            item["services"].append(_seconds(_dt(r["done_at"]), _dt(r["serving_at"] or r["called_at"])))
    services_out = []
    for item in by_service.values():
        services_out.append({
            "id": item["id"], "name": item["name"] or "—",
            "issued": item["issued"], "served": item["served"], "no_show": item["no_show"],
            "avg_wait_seconds": _avg(item["waits"]), "avg_service_seconds": _avg(item["services"]),
        })
    services_out.sort(key=lambda x: -x["issued"])

    counter_events = _event_seconds(conn, date_from, date_to, timezone, counter_id=counter_id, staff_id=staff_id)
    by_counter = {}
    for r in rows:
        if not r["counter_id"]:
            continue
        item = by_counter.setdefault(r["counter_id"], {
            "id": r["counter_id"], "name": r["counter_name"] or "—",
            "served": 0, "services": []})
        if r["status"] == "done":
            item["served"] += 1
        if r["done_at"]:
            item["services"].append(_seconds(_dt(r["done_at"]), _dt(r["serving_at"] or r["called_at"])))
    counters_out = []
    for item in by_counter.values():
        times = counter_events.get(item["id"], {"open": 0, "break": 0})
        busy = sum(item["services"])
        counters_out.append({
            "id": item["id"], "name": item["name"], "served": item["served"],
            "avg_service_seconds": _avg(item["services"]), "busy_seconds": busy,
            "break_seconds": times["break"], "idle_seconds": max(0, times["open"] - busy - times["break"]),
        })
    counters_out.sort(key=lambda x: -x["served"])

    by_staff = {}
    for r in rows:
        if not r["staff_id"]:
            continue
        item = by_staff.setdefault(r["staff_id"], {
            "id": r["staff_id"], "name": r["staff_name"] or "—", "served": 0, "services": []})
        if r["status"] == "done":
            item["served"] += 1
        if r["done_at"]:
            item["services"].append(_seconds(_dt(r["done_at"]), _dt(r["serving_at"] or r["called_at"])))
    staff_out = []
    for item in by_staff.values():
        times = counter_events.get(item["id"], {"open": 0, "break": 0})
        busy = sum(item["services"])
        staff_out.append({
            "id": item["id"], "name": item["name"], "served": item["served"],
            "avg_service_seconds": _avg(item["services"]), "busy_seconds": busy,
            "break_seconds": times["break"], "idle_seconds": max(0, times["open"] - busy - times["break"]),
        })
    staff_out.sort(key=lambda x: -x["served"])

    regular_waits, priority_rows = [], {}
    for r in rows:
        wait = _seconds(_dt(r["called_at"]), _dt(r["issued_at"])) if r["called_at"] else None
        if not r["priority_type_id"]:
            if wait is not None:
                regular_waits.append(wait)
            continue
        label = r["priority_en"] or "Priority"
        item = priority_rows.setdefault(r["priority_type_id"], {
            "id": r["priority_type_id"], "name": label, "count": 0, "waits": []})
        item["count"] += 1
        if wait is not None:
            item["waits"].append(wait)
    priority_out = [{
        "id": p["id"], "name": p["name"], "count": p["count"],
        "avg_wait_seconds": _avg(p["waits"]),
    } for p in priority_rows.values()]
    priority_out.sort(key=lambda x: -x["count"])
    priority_out.append({"id": None, "name": None, "count": len(rows) - sum(p["count"] for p in priority_out),
                         "avg_wait_seconds": _avg(regular_waits), "regular": True})

    daily = {}
    for r in rows:
        item = daily.setdefault(r["business_date"], {"date": r["business_date"], "issued": 0, "served": 0, "no_show": 0})
        item["issued"] += 1
        if r["status"] == "done":
            item["served"] += 1
        if r["status"] == "no_show":
            item["no_show"] += 1

    history_sql = """
        SELECT t.id, t.number, t.public_id, t.status, t.business_date, t.issued_at,
               t.called_at, t.serving_at, t.done_at, s.name AS service_name,
               c.name AS counter_name, st.name AS staff_name
        FROM tickets t
        LEFT JOIN services s ON s.id=t.service_id
        LEFT JOIN counters c ON c.id=t.counter_id
        LEFT JOIN staff st ON st.id=t.staff_id
        WHERE t.business_date BETWEEN ? AND ?
    """
    history_params = [date_from, date_to]
    if service_id:
        history_sql += " AND t.service_id=?"
        history_params.append(int(service_id))
    if counter_id:
        history_sql += " AND t.counter_id=?"
        history_params.append(int(counter_id))
    if staff_id:
        history_sql += " AND t.staff_id=?"
        history_params.append(int(staff_id))
    if search:
        history_sql += " AND (t.number LIKE ? OR t.account_number LIKE ? OR t.public_id LIKE ?)"
        like = f"%{search.strip()}%"
        history_params.extend([like, like, like])
    history_sql += " ORDER BY t.id DESC LIMIT 300"
    history = db.all_rows(conn, history_sql, tuple(history_params))

    return {
        "from": date_from,
        "to": date_to,
        "summary": summary,
        "hourly": [{"hour": h, "issued": hours.get(h, 0), "served": served_hours.get(h, 0)} for h in range(24)],
        "daily": sorted(daily.values(), key=lambda x: x["date"]),
        "services": services_out,
        "counters": counters_out,
        "staff": staff_out,
        "priority": priority_out,
        "history": history,
    }


def timeline(conn, ticket_id):
    ticket = db.one_row(conn, """
        SELECT t.*, s.name AS service_name, c.name AS counter_name, st.name AS staff_name,
               p.name_en AS priority_en, p.name_fil AS priority_fil
        FROM tickets t
        LEFT JOIN services s ON s.id=t.service_id
        LEFT JOIN counters c ON c.id=t.counter_id
        LEFT JOIN staff st ON st.id=t.staff_id
        LEFT JOIN priority_types p ON p.id=t.priority_type_id
        WHERE t.id=?""", (ticket_id,))
    if not ticket:
        return None
    events = db.all_rows(conn, """
        SELECT e.id, e.event_type, e.created_at, e.details, c.name AS counter_name,
               st.name AS staff_name
        FROM ticket_events e
        LEFT JOIN counters c ON c.id=e.counter_id
        LEFT JOIN staff st ON st.id=e.staff_id
        WHERE e.ticket_id=? ORDER BY e.id""", (ticket_id,))
    return {"ticket": ticket, "events": events}


# --- exports ---------------------------------------------------------------

def tickets_csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["number", "service", "counter", "staff", "status", "priority",
                     "business_date", "issued_at", "called_at", "serving_at", "done_at",
                     "wait_seconds", "service_seconds", "account_number"])
    for r in rows:
        wait = _seconds(_dt(r["called_at"]), _dt(r["issued_at"])) if r["called_at"] else ""
        service = _seconds(_dt(r["done_at"]), _dt(r["serving_at"] or r["called_at"])) if r["done_at"] else ""
        writer.writerow([r["number"], r["service_name"], r["counter_name"] or "", r["staff_name"] or "",
                         r["status"], r["priority_en"] or "", r["business_date"], r["issued_at"],
                         r["called_at"] or "", r["serving_at"] or "", r["done_at"] or "",
                         wait, service, r["account_number"] or ""])
    return "\ufeff" + buffer.getvalue()


def _pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(value):
    return str(value).encode("latin-1", "replace").decode("latin-1")


def summary_pdf(report, institution="Queue reports"):
    """Small hand-rolled PDF (Courier) so the app stays offline and dependency-free."""
    lines = []
    s = report["summary"]
    lines.append(f"Institution: {institution}")
    lines.append(f"Date range: {report['from']} to {report['to']}")
    lines.append("")
    lines.append("DAILY SUMMARY")
    lines.append(f"Issued {s['issued']}   Served {s['served']}   No-show {s['no_show']}   "
                 f"Transferred {s['transferred']}   Waiting {s['waiting']}")
    lines.append(f"Average wait {fmt_seconds(s['avg_wait_seconds'])}   "
                 f"Longest wait {fmt_seconds(s['longest_wait_seconds'])}   "
                 f"Average service {fmt_seconds(s['avg_service_seconds'])}")
    lines.append(f"Peak hour {s['peak_hour'] if s['peak_hour'] is not None else '-'}:00 "
                 f"({s['peak_count']} issued)")
    lines.append("")
    lines.append("VOLUME BY HOUR")
    for item in report["hourly"]:
        if item["issued"] or item["served"]:
            lines.append(f"  {item['hour']:02d}:00  issued {item['issued']:>4}   served {item['served']:>4}")
    lines.append("")
    lines.append("BY SERVICE")
    lines.append("  Service                         Issued  Served  No-show  Avg wait")
    for row in report["services"]:
        lines.append(f"  {_pdf_text(row['name'])[:30]:30} {row['issued']:>6} {row['served']:>7} "
                     f"{row['no_show']:>8}  {fmt_seconds(row['avg_wait_seconds']):>8}")
    lines.append("")
    lines.append("BY COUNTER")
    lines.append("  Counter                         Served  Avg service    Idle    Break")
    for row in report["counters"]:
        lines.append(f"  {_pdf_text(row['name'])[:30]:30} {row['served']:>6} "
                     f"{fmt_seconds(row['avg_service_seconds']):>11} {fmt_seconds(row['idle_seconds']):>7} "
                     f"{fmt_seconds(row['break_seconds']):>7}")
    lines.append("")
    lines.append("BY STAFF")
    for row in report["staff"]:
        lines.append(f"  {_pdf_text(row['name'])[:30]:30} {row['served']:>6} "
                     f"{fmt_seconds(row['avg_service_seconds']):>11} {fmt_seconds(row['idle_seconds']):>7} "
                     f"{fmt_seconds(row['break_seconds']):>7}")
    lines.append("")
    lines.append("PRIORITY")
    for row in report["priority"]:
        label = "Regular" if row.get("regular") else _pdf_text(row["name"])
        lines.append(f"  {label[:24]:24} {row['count']:>5} tickets   avg wait {fmt_seconds(row['avg_wait_seconds'])}")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[]]
    objects = []

    def add(obj):
        objects.append(obj)
        return len(objects)

    catalog_id = add(None)
    pages_id = add(None)
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []
    for page_lines in pages:
        content = "BT\n/F1 9 Tf\n40 790 Td\n12 TL\n"
        for line in page_lines:
            content += f"({_pdf_escape(line)}) Tj\nT*\n"
        content += "ET"
        stream_id = add(f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream".encode("latin-1"))
        page_ids.append(add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R >>".encode("latin-1")))
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1")
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>"
    ).encode("latin-1")

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode("latin-1"))
        output.write(obj if isinstance(obj, bytes) else obj.encode("latin-1"))
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.write(f"trailer << /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode("latin-1"))
    return output.getvalue()


def fmt_seconds(value):
    if value is None:
        return "-"
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"
