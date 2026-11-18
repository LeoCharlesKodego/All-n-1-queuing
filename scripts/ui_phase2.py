"""Browser walkthrough of the Phase 2 counter console."""
import json
import sqlite3
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
db = sqlite3.connect("data/queue.db")
db.execute("UPDATE settings SET value='0' WHERE key='duplicate_ticket_delay'")
db.commit()
for _ in range(3):
    req = urllib.request.Request(BASE + "/api/kiosk/ticket", data=json.dumps({"service_id": 1}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as res:
        print("seeded", json.loads(res.read())["ticket"]["number"])


def shot(page, name):
    page.screenshot(path=f"shots/{name}.png", full_page=False)
    print("shot", name)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE + "/counter")
    page.wait_for_timeout(800)
    shot(page, "p2-counter-login")
    print("login heading:", page.locator("h1").first.inner_text())
    page.fill("input[inputmode=numeric]", "1111")
    page.click("button:has-text('Sign in')")
    page.wait_for_timeout(1200)
    shot(page, "p2-counter-empty")
    print("topbar:", page.locator(".counter-top h1").inner_text())
    page.click(".current-panel button:has-text('Call next')")
    page.wait_for_timeout(900)
    shot(page, "p2-counter-called")
    print("called:", page.locator(".current-number").inner_text() if page.locator(".current-number").count() else page.locator(".current-panel").inner_text()[:120])
    page.click(".current-panel button:has-text('Start')")
    page.wait_for_timeout(800)
    shot(page, "p2-counter-serving")
    page.click(".current-panel button:has-text('Done')")
    page.wait_for_timeout(800)
    shot(page, "p2-counter-done")
    # Filipino
    page.click(".lang-switch button:has-text('FIL')")
    page.wait_for_timeout(500)
    shot(page, "p2-counter-fil")
    print("fil heading:", page.locator(".counter-top").inner_text().replace("\n", " | ")[:200])
    page.reload()
    page.wait_for_timeout(900)
    print("persisted fil:", "Tawagin" in page.content())
    # open waiting + parked lists presence
    print("waiting cards:", page.locator(".waiting-card").count())
    page.click(".counter-top button:has-text('Isara')")
    page.wait_for_timeout(700)
    shot(page, "p2-counter-logout")
    print("after logout h1:", page.locator("h1").first.inner_text())
    print("page errors:", errors)
    browser.close()
