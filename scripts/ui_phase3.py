"""Browser walkthrough of the Phase 3 kiosk."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"


def shot(page, name):
    page.screenshot(path=f"shots/{name}.png")
    print("shot", name)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE + "/kiosk")
    page.wait_for_timeout(900)
    shot(page, "p3-welcome")
    print("welcome:", page.locator(".kiosk-welcome").inner_text().replace("\n", " | ")[:120])
    page.click("button:has-text('Get a number')")
    page.wait_for_timeout(400)
    shot(page, "p3-priority")
    print("priority buttons:", page.locator(".kiosk-choice").count())
    page.click(".kiosk-choice.ghost")
    page.wait_for_timeout(400)
    shot(page, "p3-services")
    print("services:", page.locator(".kiosk-choice").count(),
          "disabled:", page.locator(".kiosk-choice.disabled").count())
    print("closed reason:", page.locator(".kiosk-choice.disabled .kiosk-choice-meta").first.inner_text())
    page.click(".kiosk-choice:has-text('Bill Payment')")
    page.wait_for_timeout(400)
    shot(page, "p3-account")
    for digit in "12345":
        page.click(f".keypad-key:has-text('{digit}')")
    print("account entry:", page.locator(".kiosk-account").inner_text())
    page.click("button:has-text('Get my number')")
    page.wait_for_timeout(1500)
    shot(page, "p3-ticket")
    print("ticket:", page.locator(".kiosk-number").inner_text(), "|", page.locator(".kiosk-service").inner_text())
    print("qr visible:", page.locator(".kiosk-qr img").count())
    page.emulate_media(media="print")
    page.screenshot(path="shots/p3-print.png")
    print("print ticket text:", page.locator(".ticket-print").inner_text().replace("\n", " | ")[:160])
    page.emulate_media(media="screen")
    # duplicate delay on a second quick ticket
    page.click("button:has-text('Done')")
    page.wait_for_timeout(400)
    page.click("button:has-text('Get a number')")
    page.wait_for_timeout(300)
    page.click(".kiosk-choice.ghost")
    page.wait_for_timeout(300)
    page.click(".kiosk-choice:has-text('Bill Payment')")
    page.wait_for_timeout(1000)
    shot(page, "p3-duplicate")
    print("duplicate msg:", page.locator(".error-box").first.inner_text() if page.locator(".error-box").count() else "none")
    # Filipino welcome
    page.goto(BASE + "/kiosk")
    page.wait_for_timeout(700)
    page.click(".lang-switch button:has-text('FIL')")
    page.wait_for_timeout(500)
    shot(page, "p3-welcome-fil")
    print("fil welcome:", page.locator(".kiosk-welcome").inner_text().replace("\n", " | ")[:120])
    print("page errors:", errors)
    b.close()
