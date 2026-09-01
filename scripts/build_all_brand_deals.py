#!/usr/bin/env python3.11
"""Builds react/src/data/allBrandDeals.json — the full cross-source brand
directory behind the "Store deals" search/browse page (as opposed to
react/src/data/brandDeals.js, the small hand-written set of flagship pages
with full copy).

Merges data/gyftr_master.json, data/maximize_master.json, and
data/buyhatke_master.json into one row per brand: whichever source has the
higher `best_discount_pct` wins that brand's row. Brand identity is decided
by an EXACT normalized-name match only (lowercase, punctuation/whitespace
stripped) — the same rule voucher_service._norm_brand / is_exact_brand_match
uses for the live per-merchant lookup. This deliberately does NOT do fuzzy
matching: that's exactly how a same-family sibling like "Ajio" vs "Ajio
Luxe", or "Amazon" vs "Amazon Fresh", could get silently merged into the
wrong brand's rate — a live-confirmed bug class this codebase has already
hit once (see voucher_service.py's _prefer_exact_name_matches). An exact
match staying unmerged just means both show up as separate, correctly
labeled rows, which is the safe failure mode.

Run whenever the three source master files are refreshed:
    python3.11 scripts/build_all_brand_deals.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = REPO_ROOT / "react" / "src" / "data" / "allBrandDeals.json"

SOURCES = [
    ("gyftr", DATA_DIR / "gyftr_master.json"),
    ("maximize", DATA_DIR / "maximize_master.json"),
    ("buyhatke", DATA_DIR / "buyhatke_master.json"),
]


def norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def voucher_url(source: str, slug: str, best_product: dict) -> str | None:
    url = best_product.get("source_url")
    if url:
        # Maximize's own source_url has the raw, unencoded brand name in the
        # path ("/gift-cards/Absolute Barbecues/791") — a literal space in a
        # URL is invalid and some browsers/crawlers mishandle it. quote()
        # with safe="/:" only escapes the space, leaving the rest of the URL
        # (scheme, slashes) untouched.
        return quote(url, safe="/:")
    if source == "gyftr":
        # Gyftr's own master file never carries a source_url (verified
        # 2026-09-01: 421/421 null) — same fallback search_service.py and
        # voucher_service.get_voucher_check already use for this source.
        return f"https://www.gyftr.com/{slug}"
    return None


def best_row_per_source(source: str, path: Path) -> dict[str, dict]:
    with open(path) as f:
        data = json.load(f)

    rows: dict[str, dict] = {}
    for slug, brand in data.items():
        name = (brand.get("brand_name") or "").strip()
        products = brand.get("products") or []
        if not name or not products:
            continue

        best_product = max(products, key=lambda p: p.get("best_discount_pct") or 0)
        pct = best_product.get("best_discount_pct")
        if not pct:
            continue

        url = voucher_url(source, slug, best_product)
        if not url:
            continue

        key = norm(name)
        row = {
            "name": name,
            "pct": round(float(pct), 2),
            "source": source,
            "url": url,
            "redemptionType": best_product.get("redemption_type"),
        }
        existing = rows.get(key)
        if existing is None or row["pct"] > existing["pct"]:
            rows[key] = row
    return rows


def main() -> None:
    merged: dict[str, dict] = {}
    for source, path in SOURCES:
        for key, row in best_row_per_source(source, path).items():
            existing = merged.get(key)
            if existing is None or row["pct"] > existing["pct"]:
                merged[key] = row

    out = sorted(merged.values(), key=lambda r: r["name"].lower())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {len(out)} brands to {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
