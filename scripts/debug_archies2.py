from playwright.sync_api import sync_playwright

def close_any_open_modals(page, max_rounds=5):
    for _ in range(max_rounds):
        closed_something = False
        modal = page.locator(".modal.show, [role='dialog']")
        count = modal.count()
        if count == 0:
            break
        for i in range(count):
            m = modal.nth(i)
            if not m.is_visible():
                continue
            for sel in [".close", ".btn-close", "[aria-label='Close']", "button:has-text('No thanks')", "button:has-text('Close')"]:
                try:
                    btn = m.locator(sel).first
                    if btn.is_visible(timeout=500):
                        btn.click(force=True, timeout=1000)
                        closed_something = True
                        page.wait_for_timeout(400)
                        break
                except Exception:
                    continue
            else:
                try:
                    m.click(position={"x": 5, "y": 5}, force=True, timeout=1000)
                    closed_something = True
                    page.wait_for_timeout(400)
                except Exception:
                    pass
        if not closed_something:
            break

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        page.goto("https://www.gyftr.com/archies-gallery", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2000)
        close_any_open_modals(page)

        page.get_by_text("INSTRUCTIONS", exact=True).first.click(timeout=5000)
        page.wait_for_timeout(1000)
        page.screenshot(path="/tmp/archies_step1_modal_open.png")

        page.get_by_text("Terms & Conditions", exact=False).first.click(timeout=3000)
        page.wait_for_timeout(700)
        page.screenshot(path="/tmp/archies_step2_after_tc.png")

        try:
            page.get_by_text("Important Instructions", exact=False).first.click(timeout=3000)
            page.wait_for_timeout(700)
            page.screenshot(path="/tmp/archies_step3_after_ii.png")
            print("Important Instructions click SUCCEEDED")
        except Exception as e:
            page.screenshot(path="/tmp/archies_step3_FAILED.png")
            print(f"Important Instructions click FAILED: {e}")

        print("Closing in 3 seconds...")
        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()
