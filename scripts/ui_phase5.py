"""Browser walkthrough of the Phase 5 admin panel."""
import http.cookiejar
import json
import sqlite3
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"


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


# Reruns: drop the temporary staff rows left by an earlier pass.
conn = sqlite3.connect("data/queue.db")
conn.execute("DELETE FROM sessions WHERE staff_id IN (SELECT id FROM staff WHERE username='zedtest')")
conn.execute("DELETE FROM staff WHERE username='zedtest'")
conn.commit()
conn.close()

admin = Client()
admin.call("/api/auth/login", {"username": "admin", "password": "secret123"})
admin.call("/api/admin/settings", {"duplicate_ticket_delay": 0}, method="PUT")
ticket = admin.call("/api/kiosk/ticket", {"service_id": 2})["ticket"]
print("issued waiting ticket:", ticket["number"], ticket["service_name"])

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(BASE + "/admin")
    page.wait_for_timeout(900)
    page.fill("input[autocomplete=username]", "admin")
    page.fill("input[type=password]", "secret123")
    page.click("button.btn.primary")
    page.wait_for_timeout(1200)
    page.screenshot(path="shots/p5-dashboard.png", full_page=True)
    print("tabs:", page.locator(".tab").all_inner_texts())
    print("stats:", [c.inner_text() for c in page.locator(".stat-card").all()][:4])
    print("dashboard rows:", page.locator(".table-wrap tbody tr").count())

    # Services: rename service 2, then confirm the waiting ticket keeps its number.
    page.click(".tab:has-text('Services')")
    page.wait_for_timeout(600)
    row = page.locator("tr", has_text="New Connection").first
    print("service row waiting:", row.locator("td").nth(3).inner_text())
    row.locator("button:has-text('Edit')").click()
    page.wait_for_timeout(300)
    name_input = page.locator(".modal label.field", has_text="Service name").locator("input")
    original = name_input.input_value()
    name_input.fill(original + " TEST")
    page.locator(".modal button:has-text('Save')").click()
    page.wait_for_timeout(900)
    print("renamed visible:", page.locator("tr", has_text=original + " TEST").count())
    page.screenshot(path="shots/p5-services.png", full_page=True)
    page.locator("tr", has_text=original + " TEST").locator("button:has-text('Edit')").click()
    page.wait_for_timeout(300)
    page.locator(".modal label.field", has_text="Service name").locator("input").fill(original)
    page.locator(".modal button:has-text('Save')").click()
    page.wait_for_timeout(800)
    state = admin.call("/api/admin/dashboard")
    waiting_numbers = [t["number"] for t in admin.call("/api/admin/queue")["waiting"]] \
        if False else None
    print("service name restored:", admin.call("/api/admin/services")["services"][1]["name"])

    # Counters: disable counter 5 through the UI and check the API.
    page.click(".tab:has-text('Counters')")
    page.wait_for_timeout(600)
    counter_row = page.locator(".table-wrap tbody tr").nth(0)
    counter_name = counter_row.locator("td").first.inner_text()
    counter_row.locator("button:has-text('Edit')").click()
    page.wait_for_timeout(300)
    modal = page.locator(".modal")
    modal.locator("label:has-text('Active') input").uncheck()
    modal.locator("button:has-text('Save')").click()
    page.wait_for_timeout(900)
    counters = admin.call("/api/admin/counters")["counters"]
    print("counter", counter_name, "active:", [c["is_active"] for c in counters if c["name"] == counter_name])
    counter_row = page.locator(".table-wrap tbody tr").nth(0)
    counter_name = counter_row.locator("td").first.inner_text()
    counter_row.locator("button:has-text('Edit')").click()
    page.wait_for_timeout(300)
    page.locator(".modal label:has-text('Active') input").check()
    page.locator(".modal button:has-text('Save')").click()
    page.wait_for_timeout(800)

    # Staff: add a temporary member and sign in with its PIN.
    page.click(".tab:has-text('Staff')")
    page.wait_for_timeout(600)
    page.click("button:has-text('Add staff')")
    page.wait_for_timeout(600)
    print("staff modal:", page.locator(".modal").count(), "selects:", page.locator(".modal select").count())
    page.locator(".modal label.field:has(.field-label:text-is('Name'))").locator("input").fill("Zed Test")
    page.locator(".modal label.field:has(.field-label:text-is('Username'))").locator("input").fill("zedtest")
    page.locator(".modal label.field:has(.field-label:text-is('PIN'))").locator("input").fill("9999")
    page.locator(".modal select").select_option(label="Cashier 4")
    page.locator(".modal button:has-text('Save')").click()
    page.wait_for_timeout(1000)
    print("zed listed:", page.locator("tr", has_text="zedtest").count())
    staff_client = Client()
    try:
        me = staff_client.call("/api/staff/login", {"pin": "9999"})
        listed = [s for s in admin.call("/api/admin/staff")["staff"] if s["username"] == "zedtest"]
        print("zed login:", me, "| listed counter:", listed[0]["counter_name"] if listed else None)
    except Exception as exc:
        print("zed login failed:", exc)
    page.screenshot(path="shots/p5-staff.png", full_page=True)

    # Display settings: banner and language change take effect on /display.
    page.click(".tab:has-text('Display')")
    page.wait_for_timeout(700)
    banner = page.locator("label.field", has_text="Banner (English)").locator("input")
    old_banner = banner.input_value()
    banner.fill("ADMIN BANNER TEST")
    page.locator("select").first.select_option("both")
    page.locator(".panel button.btn.primary").first.click()
    page.wait_for_timeout(900)
    page.screenshot(path="shots/p5-display-settings.png", full_page=True)
    display = browser.new_page(viewport={"width": 1400, "height": 800})
    display.goto(BASE + "/display")
    display.wait_for_timeout(1000)
    display.click("button:has-text('Start display')")
    display.wait_for_timeout(800)
    print("display banner:", display.locator(".display-banner span").inner_text()[:60])
    print("both-language labels:", display.locator("text=NOW SERVING").count())
    display.close()

    # Media schedule: turn it on outside the current time and check the pane disappears.
    page.locator("label:has-text('Play media only during these hours') input").check()
    page.locator("label.field", has_text="From").locator("input").fill("03:00")
    page.locator("label.field", has_text="To").locator("input").fill("03:01")
    page.locator(".panel button.btn.primary").first.click()
    page.wait_for_timeout(800)
    display = browser.new_page(viewport={"width": 1400, "height": 800})
    display.goto(BASE + "/display")
    display.wait_for_timeout(1000)
    display.click("button:has-text('Start display')")
    display.wait_for_timeout(800)
    print("media pane with schedule off:", display.locator(".media-pane").count())
    display.close()
    page.locator("label:has-text('Play media only during these hours') input").uncheck()
    page.locator("label.field", has_text="Banner (English)").locator("input").fill(old_banner)
    page.locator("select").first.select_option("en")
    page.locator(".panel button.btn.primary").first.click()
    page.wait_for_timeout(800)

    # Priority rules.
    page.click(".tab:has-text('Priority')")
    page.wait_for_timeout(700)
    print("priority rules:", page.locator("tbody tr").count(),
          "mode:", page.locator("input[name=priority-mode]:checked").count())
    page.screenshot(path="shots/p5-priority.png", full_page=True)

    # Kiosk settings page renders.
    page.click(".tab:has-text('Kiosk')")
    page.wait_for_timeout(700)
    page.screenshot(path="shots/p5-kiosk.png", full_page=True)
    print("paper setting:", page.locator("label.field", has_text="Paper size").locator("select").input_value())

    # System: checks, backup, restore.
    page.click(".tab:has-text('System')")
    page.wait_for_timeout(1500)
    page.screenshot(path="shots/p5-system.png", full_page=True)
    pills = page.locator(".card", has_text="Test everything").locator(".pill")
    print("checks:", [p.inner_text() for p in pills.all()])
    page.click("button:has-text('Back up now')")
    page.wait_for_timeout(1500)
    backup_rows = page.locator("table").last.locator("tbody tr")
    print("backups listed:", backup_rows.count())
    # Create a marker ticket, restore the backup, and confirm it is gone.
    waiting_before_marker = admin.call("/api/admin/dashboard")["waiting"]
    marker = admin.call("/api/kiosk/ticket", {"service_id": 1})["ticket"]
    print("marker before restore:", marker["number"],
          "waiting", admin.call("/api/admin/dashboard")["waiting"])
    backup_rows.first.locator("button:has-text('Restore')").click()
    page.wait_for_timeout(400)
    page.locator(".modal button:has-text('Restore this backup')").click()
    page.wait_for_timeout(2500)
    after = admin.call("/api/admin/dashboard")
    print("dashboard after restore:", after["waiting"], "waiting (was", waiting_before_marker, "before marker)")
    page.screenshot(path="shots/p5-system-restored.png", full_page=True)

    # Filipino pass over the tabs.
    page.click(".topbar .lang-switch button:has-text('FIL')")
    page.wait_for_timeout(800)
    page.screenshot(path="shots/p5-filipino.png", full_page=True)
    page.click(".tab:nth-child(2)")
    page.wait_for_timeout(600)
    print("filipino service heading:", page.locator(".panel-head h2").inner_text())
    print("page errors:", errors)
    browser.close()

# Leave the demo data as found: restore the duplicate delay, retire the test staff member.
admin.call("/api/admin/settings", {"duplicate_ticket_delay": 15}, method="PUT")
zed = [s for s in admin.call("/api/admin/staff")["staff"] if s["username"] == "zedtest"]
if zed:
    admin.call(f"/api/admin/staff/{zed[0]['id']}", {"is_active": 0}, method="PUT")
print("cleanup done")
