from playwright.sync_api import sync_playwright
import json

BRAND_URL = "https://www.gyftr.com/bigbasket"
TABS = ["Terms & Conditions", "Important Instructions", "How to use"]

def run():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        page.goto(BRAND_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        try:
            page.get_by_text("No thanks", exact=False).first.click(timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass
        try:
            page.locator("#loginMod").click(position={"x": 5, "y": 5}, force=True, timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

        page.get_by_text("INSTRUCTIONS", exact=True).first.click(timeout=5000)
        page.wait_for_timeout(1000)

        for tab in TABS:
            try:
                page.get_by_text(tab, exact=False).first.click(timeout=3000)
                page.wait_for_timeout(800)
                modal_text = page.locator("#detailsModal").inner_text()
                results[tab] = modal_text
                print(f"Captured tab: {tab}")
            except Exception as e:
                print(f"Could not click tab '{tab}': {e}")
                results[tab] = None

        # Grab video link without clicking, if one exists
        try:
            video_el = page.locator("iframe, video").first
            results["Watch Video"] = video_el.get_attribute("src", timeout=2000)
            print("Captured video link.")
        except Exception:
            results["Watch Video"] = None
            print("No video link found.")

        with open("/tmp/all_tabs_raw.json", "w") as f:
            json.dump(results, f, indent=2)

        print("DONE. Closing in 2 seconds...")
        page.wait_for_timeout(2000)
        browser.close()

if __name__ == "__main__":
    run()
