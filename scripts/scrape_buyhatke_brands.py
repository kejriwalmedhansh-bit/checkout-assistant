"""
scrape_buyhatke_brands.py — Pull the full BuyHatke gift-card brand roster.

buyhatke.com/gift-cards/brands server-renders every brand tile in one page
(no login, no JS needed for this list — only per-brand denomination/discount
detail requires scrape_buyhatke_details.py). This just enumerates slugs +
display names for that next step.

Usage:  /usr/local/bin/python3.11 scripts/scrape_buyhatke_brands.py
"""

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BRANDS_URL = "https://buyhatke.com/gift-cards/brands"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "db" / "buyhatke_brands.json"

# Non-brand nav links that share the /gift-cards/ prefix but aren't voucher pages.
_NON_BRAND_SLUGS = {"brands", "referral", "my-vouchers"}


def fetch_brands() -> list[dict]:
    resp = requests.get(BRANDS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen: dict[str, dict] = {}
    for a in soup.select('a[href^="/gift-cards/"]'):
        href = a.get("href", "")
        slug = href.removeprefix("/gift-cards/")
        if slug in _NON_BRAND_SLUGS or not slug.endswith("-gift-card"):
            continue
        # Category listing pages (e.g. /gift-cards/beauty-and-personal-care)
        # don't end in "-gift-card" so the check above already excludes them.
        name = a.find("h3")
        display_name = name.get_text(strip=True) if name else a.get_text(" ", strip=True)
        display_name = re.sub(r"\s*Gift Card$", "", display_name).strip()
        if slug not in seen:
            seen[slug] = {"slug": slug, "brand_name": display_name}

    return sorted(seen.values(), key=lambda r: r["slug"])


def main() -> None:
    print("Fetching BuyHatke brand roster...")
    brands = fetch_brands()
    print(f"Found {len(brands)} brands")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(brands, f, indent=2)
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
