"""Focused check: admin display settings reach /display and the media schedule is enforced."""
import base64
import http.cookiejar
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path, payload=None, method=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"},
        method=method or ("POST" if data is not None else "GET"))
    with op.open(req) as res:
        return json.loads(res.read())


call("/api/auth/login", {"username": "admin", "password": "secret123"})
Path("media/schedule-check.png").write_bytes(PNG)
call("/api/admin/settings", {
    "media_schedule": {"enabled": True, "from": "00:00", "to": "00:01"},
    "banner_text_en": "ADMIN BANNER TEST",
    "screen_language": "en",
}, method="PUT")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 800})
    page.goto(BASE + "/display")
    page.wait_for_timeout(1000)
    page.click("button:has-text('Start display')")
    page.wait_for_timeout(900)
    print("banner:", page.locator(".display-banner span").inner_text())
    print("media pane outside schedule:", page.locator(".media-pane").count())
    page.screenshot(path="shots/p5-display-offhours.png")
    browser.close()

call("/api/admin/settings", {
    "media_schedule": {"enabled": True, "from": "00:00", "to": "23:59"},
}, method="PUT")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 800})
    page.goto(BASE + "/display")
    page.wait_for_timeout(1000)
    page.click("button:has-text('Start display')")
    page.wait_for_timeout(900)
    print("media pane inside schedule:", page.locator(".media-pane").count(),
          "| image:", page.locator(".media-pane img").count(),
          "| src:", page.locator(".media-pane img").get_attribute("src"))
    page.screenshot(path="shots/p5-display-hours.png")
    browser.close()

call("/api/admin/settings", {
    "media_schedule": {"enabled": False, "from": "08:00", "to": "17:00"},
    "banner_text_en": "Magbayad bago ang ika-20 para hindi maputulan.",
    "screen_language": "en",
}, method="PUT")
Path("media/schedule-check.png").unlink(missing_ok=True)
print("restored settings, media files:", len(call("/api/admin/media")["files"]))
