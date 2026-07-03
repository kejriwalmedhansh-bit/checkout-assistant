from playwright.sync_api import sync_playwright
import json, time, os

TABS = ["Terms & Conditions", "Important Instructions", "How to use"]
PROGRESS_FILE = "db/gyftr_full_scrape_progress.json"
FAILED_LOG = "db/gyftr_scrape_failures.json"
MAX_BRAND_ATTEMPTS = 3

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
            for sel in [".close", ".btn-close", "[aria-label='Close']",
                        "button:has-text('No thanks')", "button:has-text('Close')"]:
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
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
            break

def scrape_brand_attempt(page, slug):
    url = f"https://www.gyftr.com/{slug}"
    result = {"slug": slug, "url": url}

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
            close_any_open_modals(page)
            continue

    if not opened:
        raise Exception("Could not open the instructions modal")

    page.wait_for_timeout(1000)

    for tab in TABS:
        try:
            click_with_retry(page, tab, exact=False, timeout=2500, attempts=3)
            page.wait_for_timeout(700)
            text = page.locator("#detailsModal").inner_text()
            result[tab] = text if text.strip() else None
        except Exception:
            result[tab] = None

    return result

def scrape_brand(page, slug):
    last_result = None
    for attempt in range(1, MAX_BRAND_ATTEMPTS + 1):
        try:
            result = scrape_brand_attempt(page, slug)
            got_anything = any(result.get(t) for t in TABS)
            if got_anything or attempt == MAX_BRAND_ATTEMPTS:
                result["attempts"] = attempt
                return result
            last_result = result
        except Exception as e:
            last_result = {"slug": slug, "url": f"https://www.gyftr.com/{slug}",
                            "error": str(e)[:200]}
        page.wait_for_timeout(1500)
    last_result["attempts"] = MAX_BRAND_ATTEMPTS
    return last_result

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def run():
    with open("db/gyftr_vouchers.json") as f:
        brands = json.load(f)
    all_slugs = [b["slug"] for b in brands]
    total = len(all_slugs)

    progress = load_progress()
    remaining = [s for s in all_slugs if s not in progress]
    print(f"Total brands: {total}. Already done: {len(progress)}. Remaining: {len(remaining)}.")

    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=50)
        page = browser.new_page()

        for i, slug in enumerate(remaining, 1):
            done_so_far = total - len(remaining) + i
            print(f"[{done_so_far}/{total}] Scraping: {slug}")

            res = scrape_brand(page, slug)
            from datetime import date
            res["scraped_at"] = date.today().isoformat()
            progress[slug] = res
            save_progress(progress)

            got_anything = any(res.get(t) for t in TABS)
            if not got_anything:
                failed.append(slug)
                print(f"    -> FAILED after {res.get('attempts', '?')} attempts")

            time.sleep(0.5)

        browser.close()

    with open(FAILED_LOG, "w") as f:
        json.dump(failed, f, indent=2)

    print(f"\nDone. {total - len(failed)}/{total} brands captured at least one tab.")
    if failed:
        print(f"{len(failed)} brands need manual review — see {FAILED_LOG}:")
        for s in failed:
            print(f"  - {s}")
    else:
        print("No failures — every brand got at least one tab captured.")

if __name__ == "__main__":
    run()
