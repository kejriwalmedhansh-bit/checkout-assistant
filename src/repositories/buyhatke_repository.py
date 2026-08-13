"""BuyHatke voucher data access — mirrors maximize_repository.py exactly.

Loads data/buyhatke_master.json once (built by
scripts/normalize_buyhatke_master.py from the raw
db/buyhatke_scrape_progress.json scrape). Each brand record carries a
`products` list, one entry per denomination band that shares a discount rate
(BuyHatke's own per-denomination rates, e.g. Myntra's ₹250 tier at a
different % than its ₹200/₹500/etc tier) — same multi-tier shape Maximize
already uses, so voucher_service's existing tier-picking logic applies as-is.
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR
from ._brand_matching import find_best_match

_BUYHATKE_PATH = DATA_DIR / "buyhatke_master.json"

_brands_by_slug: dict[str, dict] | None = None
_brands_list: list[dict] | None = None


def _load() -> None:
    global _brands_by_slug, _brands_list
    if _brands_by_slug is not None:
        return
    with open(_BUYHATKE_PATH) as f:
        data = json.load(f)
    _brands_by_slug = dict(data)
    _brands_list = list(data.values())


def all_brands() -> list[dict]:
    _load()
    return _brands_list  # type: ignore[return-value]


def brand_names() -> list[str]:
    """Every BuyHatke brand_name (used to extend the trusted-merchant whitelist)."""
    return [b.get("brand_name", "") for b in all_brands() if b.get("brand_name")]


def get_by_merchant(merchant_name: str) -> dict | None:
    """Find the BuyHatke brand record whose brand_name best matches merchant_name.

    Same exact -> prefix -> substring matching as voucher_repository.get_by_merchant.
    """
    return find_best_match(merchant_name, all_brands())


def get_by_slug(slug: str) -> dict | None:
    _load()
    return _brands_by_slug.get(slug)  # type: ignore[union-attr]
