"""Browser walkthrough of the Phase 4 public display."""
import http.cookiejar
import json
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"


def staff_client(pin):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(BASE + "/api/staff/login", data=json.dumps({"pin": pin}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req) as res:
        return op, json.loads(res.read())


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE + "/display")
    page.wait_for_timeout(1200)
    page.screenshot(path="shots/p4-start-overlay.png")
    print("overlay visible:", page.locator(".start-overlay").count())
    page.click("button:has-text('Start display')")
    page.wait_for_timeout(900)
    page.screenshot(path="shots/p4-display.png")
    print("now serving:", page.locator(".now-serving .number").inner_text(),
          "| window:", page.locator(".now-serving .window").inner_text())
    print("windows:", page.locator(".window-cell").count(),
          "next chips:", page.locator(".next-chip").count(),
          "media img:", page.locator(".media-pane img").count(),
          "banner:", page.locator(".display-banner span").inner_text()[:50])

    op, _ = staff_client("1111")
    req = urllib.request.Request(BASE + "/api/counter/call-next", data=b"{}",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req) as res:
        ticket = json.loads(res.read())
    print("called via API:", ticket["number"])
    page.wait_for_timeout(1200)
    print("display updated:", page.locator(".now-serving .number").inner_text(),
          "| flash:", page.locator(".now-serving.flash").count(),
          "| window:", page.locator(".now-serving .window").inner_text())
    page.screenshot(path="shots/p4-called.png")
    page.click("button:has-text('Test sound')")
    page.wait_for_timeout(1200)
    print("speech supported:", page.evaluate("'speechSynthesis' in window"))
    print("page errors:", errors)
    b.close()
