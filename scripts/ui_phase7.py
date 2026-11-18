"""Browser walkthrough of the Phase 7 tracking page and QR."""
import http.cookiejar
import json
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition)))
    print(("OK  " if condition else "FAIL"), name, detail)


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, payload=None, method=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            BASE + path, data=data,
            headers={"Content-Type": "application/json"},
            method=method or ("POST" if data is not None else "GET"))
        with self.op.open(req) as res:
            return json.loads(res.read())


admin = Client()
admin.call("/api/auth/login", {"username": "admin", "password": "secret123"})
admin.call("/api/admin/settings", {
    "tracking_base_url": "http://192.168.1.50:8000",
    "tracking_enabled": True,
    "ticket_show_qr": True,
    "print_enabled": False,
    "duplicate_ticket_delay": 0,
}, method="PUT")

issued = admin.call("/api/kiosk/ticket", {"service_id": 5})
ticket = issued["ticket"]
public_id = issued["tracking_url"].rstrip("/").split("/")[-1]
check("tracking url uses base", issued["tracking_url"].startswith("http://192.168.1.50:8000/track/"),
      issued["tracking_url"])
check("qr enabled on issue", issued["show_qr"])
with urllib.request.urlopen(f"{BASE}/api/qr?size=200&data={urllib.parse.quote(issued['tracking_url'])}") as res:
    qr_image = res.read()
check("qr endpoint image", qr_image.startswith(b"<svg") and len(qr_image) > 500, str(len(qr_image)))

staff = Client()
staff.call("/api/staff/login", {"username": "eve", "pin": "5555", "counter_id": 5})
current = staff.call("/api/counter/state").get("current")
if current:
    staff.call("/api/counter/done", {"ticket_id": current["id"]})

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 430, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(f"{BASE}/track/{public_id}")
    page.wait_for_timeout(1500)
    check("number shown", page.locator(".track-number").inner_text() == ticket["number"])
    check("service shown", ticket["service_name"] in page.locator(".track-service").inner_text())
    check("waiting status", "Waiting" in page.locator(".track-status").inner_text())
    check("people ahead numeric", page.locator(".track-figures .value").first.inner_text().isdigit())
    check("now serving list", page.locator(".track-now li").count() > 0)
    check("institution shown", page.locator(".track-head h1").inner_text().strip() != "")
    page.screenshot(path="shots/p7-track-waiting.png", full_page=True)

    # Call tickets on window 5 until this one is called.
    called = None
    for _ in range(20):
        result = staff.call("/api/counter/call-next", {})
        if result.get("id") == ticket["id"]:
            called = result
            break
        staff.call("/api/counter/done", {"ticket_id": result["id"]})
    check("ticket called via counter", called is not None, ticket["number"])
    page.wait_for_timeout(1500)
    check("live status called", "Now called" in page.locator(".track-status").inner_text(),
          page.locator(".track-status").inner_text())
    check("window shown", page.locator(".track-counter").inner_text() == "Express Window")
    page.screenshot(path="shots/p7-track-called.png", full_page=True)

    staff.call("/api/counter/start", {"ticket_id": ticket["id"]})
    page.wait_for_timeout(1200)
    check("live status serving", "Being served" in page.locator(".track-status").inner_text())
    staff.call("/api/counter/done", {"ticket_id": ticket["id"]})
    page.wait_for_timeout(1200)
    check("live status done", "Finished" in page.locator(".track-status").inner_text())
    check("finished notice", page.locator(".notice-box").count() >= 1)

    # Kiosk no-print QR.
    admin.call("/api/admin/settings", {"print_enabled": False, "duplicate_ticket_delay": 0}, method="PUT")
    page.set_viewport_size({"width": 1200, "height": 900})
    page.goto(BASE + "/kiosk")
    page.wait_for_timeout(1200)
    page.locator("button", has_text="Get a number").first.click()
    page.wait_for_timeout(600)
    no_priority = page.locator("button", has_text="No, regular queue")
    if no_priority.count():
        no_priority.first.click()
        page.wait_for_timeout(600)
    page.locator(".kiosk-grid button", has_text="Inquiry").first.click()
    page.wait_for_timeout(1500)
    qr = page.locator(".kiosk-qr img").first
    check("kiosk no-print qr visible", qr.count() == 1 and qr.is_visible())
    check("kiosk qr image loaded", page.evaluate("document.querySelector('.kiosk-qr img')?.naturalWidth > 0"))
    page.screenshot(path="shots/p7-kiosk-qr.png", full_page=True)

    # Filipino.
    page.goto(BASE + "/track/" + public_id)
    page.evaluate("localStorage.setItem('queue_lang', 'fil')")
    page.goto(f"{BASE}/track/{public_id}")
    page.wait_for_timeout(1200)
    check("filipino heading", "ANG IYONG TICKET" in page.locator(".eyebrow").first.inner_text(),
          page.locator(".eyebrow").first.inner_text())
    page.screenshot(path="shots/p7-track-filipino.png", full_page=True)
    page.evaluate("localStorage.setItem('queue_lang', 'en')")

    # Unknown id.
    page.goto(BASE + "/track/does-not-exist")
    page.wait_for_timeout(900)
    check("not found message", page.locator("h1", has_text="Ticket not found").count() == 1)

    # Server unreachable: friendly offline message instead of a blank page.
    page.route("**/api/track/**", lambda route: route.abort())
    page.goto(f"{BASE}/track/{public_id}")
    page.wait_for_timeout(1200)
    check("offline message", page.locator("h1", has_text="Cannot reach the queue server").count() == 1)
    page.screenshot(path="shots/p7-track-offline.png")
    page.unroute("**/api/track/**")
    check("no page errors", not errors, "; ".join(errors))
    browser.close()

# Restore demo settings.
admin.call("/api/admin/settings", {
    "tracking_base_url": "",
    "print_enabled": True,
    "duplicate_ticket_delay": 15,
}, method="PUT")
staff.call("/api/staff/logout", {})

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} checks OK")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
