"""Browser walkthrough of the setup wizard (Phase 1 verification)."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE}/setup")
        page.get_by_role("button", name="Payment establishment").click()
        page.get_by_label("Institution name").fill("Metro Water District")
        page.get_by_label("Address", exact=True).fill("Poblacion, Sta. Cruz")
        page.get_by_label("Contact number").fill("(049) 123-4567")
        page.screenshot(path="shots/p1_wizard_1.png", full_page=True)

        page.get_by_role("button", name="Next").click()
        page.get_by_role("button", name="Filipino").click()
        assert "Serbisyo" in page.content(), "Filipino translation missing"
        page.screenshot(path="shots/p1_wizard_2_fil.png", full_page=True)
        page.get_by_role("button", name="English").click()
        page.get_by_role("button", name="Next").click()

        # Counters
        page.get_by_role("button", name="Next").click()
        # Priority
        page.get_by_role("button", name="Next").click()
        # Intake
        page.get_by_role("button", name="Next").click()
        # Display: set banner
        page.get_by_label("Scrolling banner (English)").fill("Pay before the 20th to avoid disconnection.")
        page.get_by_label("Scrolling banner (Filipino)").fill("Magbayad bago ang ika-20 para hindi maputulan.")
        page.get_by_role("button", name="Next").click()

        # Admin
        page.get_by_label("Admin username").fill("admin")
        page.get_by_label("Admin password", exact=True).fill("secret123")
        page.get_by_label("Confirm password").fill("secret123")
        page.screenshot(path="shots/p1_wizard_admin.png", full_page=True)
        page.get_by_role("button", name="Next").click()

        page.get_by_label("Issue a demo ticket when setup finishes").check()
        page.screenshot(path="shots/p1_wizard_review.png", full_page=True)
        page.get_by_role("button", name="Finish setup").click()
        page.get_by_role("heading", name="Setup complete").wait_for(timeout=10000)
        page.screenshot(path="shots/p1_wizard_done.png", full_page=True)
        print("wizard done page:", page.inner_text("h1"))

        # Admin login
        page.goto(f"{BASE}/admin")
        page.get_by_label("Username").fill("admin")
        page.get_by_label("Password").fill("wrongpass")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(400)
        print("wrong login message:", page.inner_text(".error-box"))
        page.get_by_label("Password").fill("secret123")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(800)
        page.screenshot(path="shots/p1_admin_login.png", full_page=True)
        print("admin page:", page.inner_text("h2"))

        # Home page + kiosk placeholder
        page.goto(f"{BASE}/")
        page.screenshot(path="shots/p1_home.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
