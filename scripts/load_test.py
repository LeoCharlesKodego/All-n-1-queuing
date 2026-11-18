"""Simulated heavy day: 300 tickets, 5 counters, 8 concurrent callers.

Runs against a throwaway copy of the database on port 8010 so the demo data is untouched.
"""
import http.cookiejar
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SRC = "data/queue.db"
TMP = "data/loadtest.db"
BASE = "http://127.0.0.1:8010"
STAFF = [("ana", "1111", 1), ("ben", "2222", 2), ("cita", "3333", 3),
         ("dan", "4444", 4), ("eve", "5555", 5)]
TICKETS = 300


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, payload=None, method=None, timeout=30):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            BASE + path, data=data,
            headers={"Content-Type": "application/json"},
            method=method or ("POST" if data is not None else "GET"))
        started = time.perf_counter()
        with self.op.open(req, timeout=timeout) as res:
            body = json.loads(res.read())
        return body, (time.perf_counter() - started) * 1000


shutil.copy(SRC, TMP)
conn = sqlite3.connect(TMP)
conn.execute("UPDATE tickets SET status='done', done_at=COALESCE(done_at, last_event_at) WHERE status IN ('called','serving')")
conn.execute("UPDATE counters SET status='open'")
conn.execute("DELETE FROM sessions")
conn.commit()
conn.close()

env = dict(os.environ, QUEUE_DB=TMP)
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8010"],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    else:
        raise SystemExit("server did not start")

    admin = Client()
    admin.call("/api/auth/login", {"username": "admin", "password": "secret123"})
    admin.call("/api/admin/settings", {"duplicate_ticket_delay": 0}, method="PUT")

    services = [s["id"] for s in admin.call("/api/admin/services")[0]["services"] if s["is_active"]]
    print(f"issuing {TICKETS} tickets across services {services} with 10 parallel clients")
    issue_latencies = []
    lock = __import__("threading").Lock()

    def issue(i):
        client = Client()
        t0 = time.perf_counter()
        result, _ = client.call("/api/kiosk/ticket", {"service_id": services[i % len(services)]})
        with lock:
            issue_latencies.append((time.perf_counter() - t0) * 1000)
        return result["ticket"]["id"]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:
        issued_ids = list(pool.map(issue, range(TICKETS)))
    issue_seconds = time.perf_counter() - started
    print(f"issued {len(issued_ids)} unique={len(set(issued_ids))} in {issue_seconds:.1f}s "
          f"({len(issued_ids) / issue_seconds:.1f}/s, p95 {statistics.quantiles(issue_latencies, n=20)[18]:.0f} ms)")

    sessions = []
    for username, pin, counter in STAFF:
        client = Client()
        client.call("/api/staff/login", {"username": username, "pin": pin, "counter_id": counter})
        sessions.append(client)

    called = []
    call_latencies = []
    errors = []
    stop = __import__("threading").Event()
    deadline = time.time() + 90

    def worker(client):
        while not stop.is_set() and time.time() < deadline:
            try:
                ticket, ms = client.call("/api/counter/call-next", {})
                call_latencies.append(ms)
                called.append(ticket["id"])
                if len(called) >= TICKETS:
                    stop.set()
                    break
                client.call("/api/counter/done", {"ticket_id": ticket["id"]})
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    time.sleep(0.05)
                    continue
                errors.append(f"{exc.code}")
        stop.set()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(sessions)) as pool:
        list(pool.map(worker, sessions))
    call_seconds = time.perf_counter() - started
    call_latencies.sort()

    duplicates = len(called) - len(set(called))
    print(f"called {len(called)} tickets in {call_seconds:.1f}s with {len(sessions)} counters "
          f"({len(called) / call_seconds:.1f} calls/s, p95 {call_latencies[int(len(call_latencies) * 0.95)]:.0f} ms)")
    print(f"duplicate calls: {duplicates}; http errors: {len(errors)}")

    report, ms = admin.call("/api/admin/reports")
    print(f"report for {report['summary']['issued']} tickets built in {ms:.0f} ms")
    report_month, ms = admin.call("/api/admin/reports?date_from=2026-11-01&date_to=2026-11-30")
    print(f"month report in {ms:.0f} ms, history rows {len(report_month['history'])}")

    print(f"remaining waiting in test db: {TICKETS - len(called)}")
    ok = len(set(issued_ids)) == TICKETS and len(called) == TICKETS and duplicates == 0 and not errors
    print("RESULT:", "PASS" if ok else "FAIL")
    if not ok:
        raise SystemExit(1)
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    time.sleep(0.5)
    try:
        os.remove(TMP)
    except OSError:
        pass
