"""Hand corrections to the scraped voucher data, applied as each platform's
master file loads, so a data refresh (which rewrites the master files) never
undoes them.

Two sources:
  * data/voucher_corrections.json — field fixes, e.g. the Amazon Pay card's
    per-bill limit, optionally only for the listings named in "listings".
  * data/voucher_choice_review.json "listings" — the exact listings behind
    each voucher name the owner reviewed. A listing a refresh files under a
    reviewed name that was not reviewed ("Amazon Prime Lite Edition" filed
    under "Amazon", 2026-09-28) is taken out of the data until reviewed, so no
    part of Dealo can offer it under the reviewed name's rules.
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR

_CORRECTIONS = DATA_DIR / "voucher_corrections.json"
_REVIEW = DATA_DIR / "voucher_choice_review.json"

# Listings taken out at load, for scripts/voucher_review_pending.py.
held_back: list[dict] = []


def _read(path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def apply(source: str, brands_by_slug: dict[str, dict]) -> None:
    """Patch `brands_by_slug` (one platform's master data) in place."""
    pinned = _read(_REVIEW).get("listings") or {}
    emptied = []
    for slug, record in brands_by_slug.items():
        allowed = pinned.get(record.get("brand_name") or "")
        if not allowed:
            continue
        kept = []
        for product in record.get("products") or []:
            if product.get("source_url") and product["source_url"] not in allowed:
                held_back.append({"platform": source, "brand_name": record.get("brand_name"),
                                  "listing": product["source_url"], "pct": product.get("best_discount_pct")})
            else:
                kept.append(product)
        record["products"] = kept
        if not kept:
            # A second record under the same name holding only held listings
            # (GIVA Silver Coin, 2026-09-28) would otherwise shadow the real one.
            emptied.append(slug)
    for slug in emptied:
        del brands_by_slug[slug]

    for key, fix in _read(_CORRECTIONS).items():
        platform, _, slug = key.partition(":")
        record = brands_by_slug.get(slug) if platform == source else None
        if not record:
            continue
        only = set(fix.get("listings") or [])
        for product in record.get("products") or []:
            if not only or product.get("source_url") in only:
                product.update(fix.get("products") or {})
