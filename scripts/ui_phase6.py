"""Browser walkthrough of the Phase 6 reports tab."""
import http.cookiejar
import json
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


admin = Client()
admin.call("/api/auth/login", {"username": "admin", "password": "secret123"})
report = admin.call("/api/admin/reports")
checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition)))
    print(("OK  " if condition else "FAIL"), name, detail)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(BASE + "/admin")
    page.wait_for_timeout(800)
    page.fill("input[autocomplete=username]", "admin")
    page.fill("input[type=password]", "secret123")
    page.click("button.btn.primary")
    page.wait_for_timeout(1200)
    check("reports tab present", page.locator(".tab", has_text="Reports").count() == 1)
    page.click(".tab:has-text('Reports')")
    page.wait_for_timeout(1200)
    page.screenshot(path="shots/p6-reports.png", full_page=True)

    cards = page.locator(".stat-card .value").all_inner_texts()
    check("issued matches API", cards[0] == str(report["summary"]["issued"]), cards[0])
    check("served matches API", cards[1] == str(report["summary"]["served"]), cards[1])
    check("hourly has 24 bars", page.locator(".hour-col").count() == 24)
    check("history rows match", page.locator(".report-history tbody tr").count() == len(report["history"]),
          str(page.locator(".report-history tbody tr").count()))
    check("service table rows", page.locator(".card:has(h2:text('By service')) tbody tr").count() == len(report["services"]))
    check("counter table rows", page.locator(".card:has(h2:text('By counter')) tbody tr").count() == len(report["counters"]))

    # Timeline modal from a history row.
    page.locator(".report-history tbody tr").first.click()
    page.wait_for_timeout(700)
    check("timeline modal open", page.locator(".modal").count() == 1)
    check("timeline has events", page.locator(".modal tbody tr").count() >= 1,
          str(page.locator(".modal tbody tr").count()))
    page.screenshot(path="shots/p6-timeline.png")
    page.locator(".modal button").first.click()
    page.wait_for_timeout(300)

    # Service filter: pick service 2 and confirm the API agrees.
    page.locator("label.field", has_text="Service").locator("select").select_option("2")
    page.click("button:has-text('Show report')")
    page.wait_for_timeout(900)
    filtered = admin.call("/api/admin/reports?service_id=2")
    filtered_cards = page.locator(".stat-card .value").all_inner_texts()
    check("service filter issued", filtered_cards[0] == str(filtered["summary"]["issued"]),
          f"{filtered_cards[0]} vs {filtered['summary']['issued']}")
    check("service filter history", page.locator(".report-history tbody tr").count() == len(filtered["history"]))
    page.screenshot(path="shots/p6-filtered.png", full_page=True)

    # Search narrows the history.
    first_number = filtered["history"][0]["number"]
    page.fill("input[placeholder='Search number or account']", first_number)
    page.click(".report-history button:has-text('Search')")
    page.wait_for_timeout(900)
    rows = page.locator(".report-history tbody tr").all_inner_texts()
    check("search narrows rows", len(rows) == 1 and first_number in rows[0], str(len(rows)))
    page.fill("input[placeholder='Search number or account']", "")
    page.click("button:has-text('Show report')")
    page.wait_for_timeout(900)

    # Yesterday should have no tickets.
    page.fill("input[type=date] >> nth=0", "2026-11-17")
    page.fill("input[type=date] >> nth=1", "2026-11-17")
    page.click("button:has-text('Show report')")
    page.wait_for_timeout(900)
    check("empty day shows zero", page.locator(".stat-card .value").first.inner_text() == "0")
    page.click("button:has-text('Today')")
    page.click("button:has-text('Show report')")
    page.wait_for_timeout(900)

    # Downloads.
    with page.expect_download() as dl:
        page.click("a:has-text('Export CSV')")
    path = dl.value.path()
    raw = open(path, "rb").read()
    check("csv download", raw.startswith(b"\xef\xbb\xbfnumber,") and len(raw) > 200, str(len(raw)))
    with page.expect_download() as dl:
        page.click("a:has-text('Export PDF')")
    raw = open(dl.value.path(), "rb").read()
    check("pdf download", raw.startswith(b"%PDF") and len(raw) > 1000, str(len(raw)))
    check("no page errors", not errors, "; ".join(errors))

    # Print layout: header visible, controls hidden.
    page.emulate_media(media="print")
    page.wait_for_timeout(300)
    check("print header visible", page.locator(".report-print-head").is_visible())
    check("print filters hidden", not page.locator(".report-filters").is_visible())
    check("print tables visible", page.locator(".card:has(h2:text('By service'))").is_visible())
    page.pdf(path="shots/p6-report.pdf", format="A4", print_background=True)
    page.screenshot(path="shots/p6-print.png", full_page=True)
    page.emulate_media(media="screen")

    # Filipino.
    page.click(".lang-switch button:has-text('FIL')")
    page.wait_for_timeout(600)
    check("filipino reports heading", page.locator("h2", has_text="Mga ulat").count() >= 1)
    page.screenshot(path="shots/p6-filipino.png", full_page=True)
    page.click(".lang-switch button:has-text('EN')")

    browser.close()

failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} checks OK")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
