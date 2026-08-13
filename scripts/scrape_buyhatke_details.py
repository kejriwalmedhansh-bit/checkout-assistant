"""
scrape_buyhatke_details.py — Per-brand denomination/discount/T&C detail for
every BuyHatke gift-card brand in db/buyhatke_brands.json.

Each /gift-cards/{slug} page fetches its own data client-side from
ext1.buyhatke.com/giftVoucher/vouchers/voucherChoices as part of loading
normally for a visitor — no separate API integration, just a real (headless)
browser visiting the public page and reading what it loads, same as
scrape_all_gyftr.py does for Gyftr's T&C modals. No Cloudflare/login blocker
was found for this site (unlike Maximize), so plain headless Chromium works.

Usage:  /usr/local/bin/python3.11 scripts/scrape_buyhatke_details.py
"""

import json
import os
import time
from datetime import date

from playwright.sync_api import sync_playwright

BRANDS_FILE = "db/buyhatke_brands.json"
PROGRESS_FILE = "db/buyhatke_scrape_progress.json"
FAILED_LOG = "db/buyhatke_scrape_failures.json"
MAX_BRAND_ATTEMPTS = 3
VOUCHER_CHOICES_MARKER = "/giftVoucher/vouchers/voucherChoices"


def scrape_brand_attempt(page, slug: str) -> dict:
    url = f"https://buyhatke.com/gift-cards/{slug}"
    captured = {}

    def on_response(response):
        if VOUCHER_CHOICES_MARKER in response.url:
            try:
                captured["body"] = response.json()
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(1500)
    finally:
        page.remove_listener("response", on_response)

    body = captured.get("body")
    choices = (body or {}).get("data", {}).get("voucherChoices") if body else None
    if not choices:
        raise Exception("No voucherChoices response captured")
    return {"slug": slug, "url": url, "voucherChoices": choices}


def scrape_brand(page, slug: str) -> dict:
    last_result = None
    for attempt in range(1, MAX_BRAND_ATTEMPTS + 1):
        try:
            result = scrape_brand_attempt(page, slug)
            result["attempts"] = attempt
            return result
        except Exception as e:
            last_result = {"slug": slug, "url": f"https://buyhatke.com/gift-cards/{slug}",
                            "error": str(e)[:200], "attempts": attempt}
        page.wait_for_timeout(1000)
    return last_result


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress: dict) -> None:
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def run() -> None:
    with open(BRANDS_FILE) as f:
        brands = json.load(f)
    all_slugs = [b["slug"] for b in brands]
    total = len(all_slugs)

    progress = load_progress()
    remaining = [s for s in all_slugs if s not in progress]
    print(f"Total brands: {total}. Already done: {len(progress)}. Remaining: {len(remaining)}.")

    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, slug in enumerate(remaining, 1):
            done_so_far = total - len(remaining) + i
            print(f"[{done_so_far}/{total}] Scraping: {slug}")

            res = scrape_brand(page, slug)
            res["scraped_at"] = date.today().isoformat()
            progress[slug] = res
            save_progress(progress)

            if "error" in res:
                failed.append(slug)
                print(f"    -> FAILED after {res.get('attempts', '?')} attempts: {res['error']}")

            time.sleep(0.3)

        browser.close()

    with open(FAILED_LOG, "w") as f:
        json.dump(failed, f, indent=2)

    print(f"\nDone. {total - len(failed)}/{total} brands captured.")
    if failed:
        shown = failed[:20]
        more = f" (+{len(failed) - 20} more)" if len(failed) > 20 else ""
        print(f"{len(failed)} brands need manual review — see {FAILED_LOG}: {shown}{more}")
    else:
        print("No failures.")


if __name__ == "__main__":
    run()
