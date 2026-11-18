"""Live API checks for Phase 2: staff, lifecycle, priority, and call-next concurrency."""
import http.cookiejar
import json
import sqlite3
import threading
import urllib.request
import urllib.error
from collections import Counter

BASE = "http://127.0.0.1:8000"
DB = "data/queue.db"


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(opener, path, data=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req) as res:
            text = res.read().decode()
            return res.status, json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode()
        return exc.code, json.loads(text) if text else None


def issue(service_id, priority=None):
    status, body = call(client(), "/api/kiosk/ticket",
                        {"service_id": service_id, "priority_type_id": priority})
    assert status == 200, (status, body)
    return body["ticket"]


def main():
    db = sqlite3.connect(DB)
    db.execute("UPDATE settings SET value='0' WHERE key='duplicate_ticket_delay'")
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('staff_issue_enabled','true')")
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('recall_wait_seconds','60')")
    db.execute("DELETE FROM ticket_events")
    db.execute("DELETE FROM tickets")
    db.execute("UPDATE counters SET status='closed'")
    db.commit()

    admin = client()
    print("admin login", call(admin, "/api/auth/login", {"username": "admin", "password": "secret123"})[0])
    for name, username, pin, counter in [
        ("Ana Reyes", "ana", "1111", 1), ("Ben Cruz", "ben", "2222", 2), ("Cita Lim", "cita", "3333", 3),
        ("Dan Ong", "dan", "4444", 4), ("Eve Tan", "eve", "5555", 5),
    ]:
        status, body = call(admin, "/api/admin/staff", {"name": name, "username": username, "pin": pin, "counter_id": counter})
        print("staff", username, status, body)

    bad = client()
    print("bad pin", call(bad, "/api/staff/login", {"pin": "0000"}))
    staff = {}
    for username, pin, counter in [("ana", "1111", 1), ("ben", "2222", 2), ("cita", "3333", 3), ("dan", "4444", 4), ("eve", "5555", 5)]:
        op = client()
        status, body = call(op, "/api/staff/login", {"pin": pin, "counter_id": counter})
        print("staff login", username, status, body["staff"]["name"], body["counter"]["name"])
        staff[counter] = op

    for _ in range(25):
        issue(1)
    for _ in range(5):
        issue(1, priority=1)
    for _ in range(8):
        issue(5)
    print("state keys", sorted(call(staff[1], "/api/counter/state", method="GET")[1].keys()))
    s = call(staff[1], "/api/counter/state", method="GET")[1]
    print("waiting", s["waiting_count"], "priority_mode", s["settings"].get("priority_mode"),
          "interleave", s["settings"].get("priority_interleave"))

    calls = []
    barrier = threading.Barrier(3)
    lock = threading.Lock()

    def worker(counter_id):
        op = staff[counter_id]
        for _ in range(10):
            barrier.wait()
            status, body = call(op, "/api/counter/call-next", {})
            with lock:
                calls.append((counter_id, status, body.get("number") if isinstance(body, dict) and status == 200 else body))
            if status == 200:
                call(op, "/api/counter/start", {"ticket_id": body["id"]})
                call(op, "/api/counter/done", {"ticket_id": body["id"]})

    threads = [threading.Thread(target=worker, args=(c,)) for c in (1, 2, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    numbers = [c[2] for c in calls if c[1] == 200]
    print("concurrency: attempts", len(calls), "ok", len(numbers),
          "dupes", [n for n, c in Counter(numbers).items() if c > 1],
          "failures", [c[2] for c in calls if c[1] != 200][:3])

    # Priority ordering: fresh tickets on the now-empty Bill Payment queue
    for _ in range(6):
        issue(1)
    for _ in range(2):
        issue(1, priority=1)
    order = []
    for _ in range(8):
        status, body = call(staff[2], "/api/counter/call-next", {})
        if status != 200:
            break
        order.append((body["number"], bool(body.get("priority_type_id"))))
        call(staff[2], "/api/counter/done", {"ticket_id": body["id"]})
    print("priority order", order)

    # Transfer of a current ticket to another service (new number, waiting)
    t = issue(2)
    status, body = call(staff[4], "/api/counter/call-next", {})
    print("counter4 called", status, body.get("number"), t["number"])
    tid = body["id"]
    status, newt = call(staff[4], "/api/counter/transfer", {"ticket_id": tid, "to_service_id": 1})
    print("transfer", status, newt.get("number") if isinstance(newt, dict) else newt)
    status, body = call(staff[1], "/api/counter/call-next", {})
    print("transferred called", status, body.get("number"))
    call(staff[1], "/api/counter/done", {"ticket_id": body["id"]})

    # Hold then resume immediately (recall_wait is 60s by default)
    t = issue(2)
    status, body = call(staff[4], "/api/counter/call-next", {})
    tid = body["id"]
    print("hold", call(staff[4], "/api/counter/hold", {"ticket_id": tid})[1]["status"])
    print("resume too early", call(staff[4], "/api/counter/resume", {"ticket_id": tid}))
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('recall_wait_seconds','0')")
    db.commit()
    status, body = call(staff[4], "/api/counter/resume", {"ticket_id": tid})
    print("resume", status, body)
    print("recall", call(staff[4], "/api/counter/recall", {"ticket_id": tid})[0])
    print("done", call(staff[4], "/api/counter/done", {"ticket_id": tid})[0])

    # Skip three times -> no_show -> reenter
    t = issue(2)
    status, body = call(staff[4], "/api/counter/call-next", {})
    tid = body["id"]
    for _ in range(3):
        call(staff[4], "/api/counter/recall", {"ticket_id": tid})
    print("skip at limit", call(staff[4], "/api/counter/skip", {"ticket_id": tid})[1]["status"])
    state = call(staff[4], "/api/counter/state", method="GET")[1]
    print("parked", [(p["number"], p["status"]) for p in state["parked"]])
    status, body = call(staff[4], "/api/counter/reenter", {"ticket_id": tid})
    print("reenter", status, body.get("status"), body.get("number"))
    status, body = call(staff[4], "/api/counter/call-next", {})
    print("reenter called back", status, body.get("number"))
    call(staff[4], "/api/counter/done", {"ticket_id": body["id"]})

    # Staff-issued ticket
    status, body = call(staff[1], "/api/counter/issue", {"service_id": 1})
    print("staff issue", status, body.get("number") if isinstance(body, dict) else body)
    status, body = call(staff[1], "/api/counter/call-next", {})
    print("staff ticket called", status, body.get("number"))
    call(staff[1], "/api/counter/done", {"ticket_id": body["id"]})

    # Break / away / close / open
    for st in ("away", "break", "open"):
        print("status", st, call(staff[3], "/api/counter/status", {"status": st})[0])
    print("logout", call(staff[3], "/api/staff/logout", {})[0],
          "state after logout", call(staff[3], "/api/counter/state", method="GET")[0])

    # Restore settings, then duplicate-delay still applies on kiosk
    db.execute("UPDATE settings SET value='15' WHERE key='duplicate_ticket_delay'")
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('staff_issue_enabled','false')")
    db.commit()
    status, body = call(client(), "/api/kiosk/ticket", {"service_id": 1})
    print("duplicate delay", status, body)

    print("call dupes", db.execute(
        "SELECT COUNT(*) FROM (SELECT ticket_id, COUNT(*) c FROM ticket_events WHERE event_type='call' GROUP BY ticket_id HAVING c>1)").fetchone()[0])
    print("events", dict(Counter(r[0] for r in db.execute("SELECT event_type FROM ticket_events"))))
    print("statuses", dict(Counter(r[0] for r in db.execute("SELECT status FROM tickets"))))
    db.close()


if __name__ == "__main__":
    main()
