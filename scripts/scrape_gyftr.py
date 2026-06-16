"""
scrape_gyftr.py — Pull discount/redemption data for every Gyftr brand voucher.

Usage:  .venv/bin/python scripts/scrape_gyftr.py
"""

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://api.gyftr.com/gyftrapi/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.gyftr.com",
    "Referer": "https://www.gyftr.com/",
    "Accept": "application/json",
}
REQUEST_DELAY_SECONDS = 0.3
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "db" / "gyftr_vouchers.json"


def fetch_brand_list() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/v1/home/brand/list", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["brands"]


def fetch_brand_detail(slug: str) -> dict | None:
    try:
        resp = requests.get(f"{BASE_URL}/v1/brand/detail/{slug}", headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [{slug}] request failed: {e}")
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


def extract_fields(slug: str, detail: dict) -> dict:
    data = detail.get("data", {})
    brand = data.get("brand", {})

    # API has no explicit min_value field — mrp doubles as the minimum for
    # custom-amount vouchers (max_value > 0) and as the fixed amount otherwise.
    products = [
        {
            "mrp": p.get("mrp"),
            "min_value": p.get("mrp"),
            "max_value": p.get("max_value"),
        }
        for p in data.get("products", [])
    ]

    # pgdis[] carries PAYTM UPI/Paytm Wallet but never Amazon Pay/MobiKwik;
    # pgmodes[] carries Amazon Pay/MobiKwik but never PAYTM UPI/Paytm Wallet.
    # Merge both so no payment method's discount is silently dropped.
    pg_discounts: dict[str, float] = {}
    for pg in data.get("pgdis", []):
        pg_discounts[pg.get("pg_name")] = pg.get("brand_pg_discount")
    for pg in data.get("pgmodes", []):
        pg_discounts.setdefault(pg.get("pg_name"), pg.get("pg_discount"))

    pgdis = [{"pg_name": name, "brand_pg_discount": disc} for name, disc in pg_discounts.items()]

    return {
        "brand_name": brand.get("brand_name", ""),
        "slug": slug,
        "redemption_type": brand.get("redemption_type", ""),
        "defaut_pg_dis": brand.get("defaut_pg_dis"),
        "pgdis": pgdis,
        "products": products,
        "important_instruction": brand.get("important_instruction", ""),
        "checkout_instruction": brand.get("checkout_instruction", ""),
    }


def main() -> None:
    print("Fetching brand list...")
    brands = fetch_brand_list()
    total = len(brands)
    print(f"Found {total} brands\n")

    results = []
    failures = []

    for i, b in enumerate(brands, 1):
        slug = b.get("slug", "")
        if slug:
            detail = fetch_brand_detail(slug)
            if detail is None or detail.get("code") != 200:
                failures.append(slug)
            else:
                results.append(extract_fields(slug, detail))
            time.sleep(REQUEST_DELAY_SECONDS)

        if i % 50 == 0 or i == total:
            print(f"  Progress: {i}/{total} brands processed ({len(failures)} failed so far)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} brand records to {OUTPUT_PATH}")
    if failures:
        shown = failures[:20]
        more = f" (+{len(failures) - 20} more)" if len(failures) > 20 else ""
        print(f"Failed to fetch {len(failures)} brands: {shown}{more}")


if __name__ == "__main__":
    main()
