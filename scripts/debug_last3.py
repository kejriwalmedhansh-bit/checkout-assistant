from playwright.sync_api import sync_playwright

SLUGS = ["spencers-retail", "giva", "domino's-pizza"]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        for slug in SLUGS:
            print(f"\n===== {slug} =====")
            try:
                resp = page.goto(f"https://www.gyftr.com/{slug}", wait_until="networkidle", timeout=20000)
                print(f"HTTP status: {resp.status if resp else 'no response'}")
                print(f"Final URL: {page.url}")
                page.wait_for_timeout(1500)
                page.screenshot(path=f"/tmp/scrape_debug/{slug}_check.png")
                title = page.title()
                print(f"Page title: {title}")
            except Exception as e:
                print(f"Error: {e}")
        print("\nClosing in 3 sec...")
        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()
