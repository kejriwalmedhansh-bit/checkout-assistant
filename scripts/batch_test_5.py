from playwright.sync_api import sync_playwright
import json, time

TABS = ["Terms & Conditions", "Important Instructions", "How to use"]

def click_with_retry(page, text, exact, timeout=3000, attempts=4):
    last_err = None
    for _ in range(attempts):
        try:
            page.get_by_text(text, exact=exact).first.click(timeout=timeout)
            return True
        except Exception as e:
            last_err = e
            page.wait_for_timeout(600)
    raise last_err

def close_any_open_modals(page, max_rounds=5):
    """Generic: find any visible modal/dialog on the page and close it, whatever it is."""
    for _ in range(max_rounds):
        closed_something = False

        # Any element that looks like an open modal (Bootstrap-style 'show' class, or role=dialog)
        modal = page.locator(".modal.show, [role='dialog']")
        count = modal.count()
        if count == 0:
            break  # nothing open, we're done

        for i in range(count):
            m = modal.nth(i)
            if not m.is_visible():
                continue
            # Try common close buttons/icons inside this modal first
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
                # No close button found — click just outside the modal's content box (top-left corner)
                try:
                    m.click(position={"x": 5, "y": 5}, force=True, timeout=1000)
                    closed_something = True
                    page.wait_for_timeout(400)
                except Exception:
                    pass

        if not closed_something:
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
            break

def scrape_brand(page, slug):
    url = f"https://www.gyftr.com/{slug}"
    result = {"slug": slug, "url": url, "errors": []}
    try:
        page.goto(url, wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2000)

        close_any_open_modals(page)

        opened = False
        for label in ["INSTRUCTIONS", "Instructions"]:
            try:
                click_with_retry(page, label, exact=True, timeout=3000, attempts=4)
                opened = True
                break
            except Exception:
                close_any_open_modals(page)  # something new may have popped up — clear and retry
                continue

        if not opened:
            result["errors"].append("Could not open the instructions modal at all")
            page.screenshot(path=f"/tmp/scrape_debug/{slug}_FAILED.png")
            return result

        page.wait_for_timeout(1000)

        for tab in TABS:
            try:
                click_with_retry(page, tab, exact=False, timeout=2500, attempts=3)
                page.wait_for_timeout(700)
                result[tab] = page.locator("#detailsModal").inner_text()
            except Exception:
                result[tab] = None

    except Exception as e:
        result["errors"].append(f"page load: {str(e)[:200]}")
        page.screenshot(path=f"/tmp/scrape_debug/{slug}_FAILED.png")

    return result

def run():
    with open("db/gyftr_vouchers.json") as f:
        brands = json.load(f)

    picks = [b for b in brands if b["slug"] in
             ["archies-gallery", "zee5", "wynk-music", "adidas-kids-luxe-gift-card", "french-accent"]]
    slugs = [b["slug"] for b in picks]
    print(f"Testing: {slugs}")

    all_results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page = browser.new_page()
        for slug in slugs:
            print(f"\nScraping: {slug}")
            res = scrape_brand(page, slug)
            all_results.append(res)
            for tab in TABS:
                status = "OK" if res.get(tab) else "missing/none"
                length = len(res.get(tab) or "")
                print(f"  {tab}: {status} ({length} chars)")
            if res["errors"]:
                print(f"  ERRORS: {res['errors']}")
            time.sleep(1)
        browser.close()

    with open("/tmp/batch_test_5.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\nSaved to /tmp/batch_test_5.json")
    print("Any brand that fully failed has a debug screenshot in /tmp/scrape_debug/")

if __name__ == "__main__":
    run()
