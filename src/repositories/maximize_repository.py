"""Maximize voucher data access — mirrors voucher_repository.py exactly.

Loads data/maximize_master.json once (built by
scripts/clean_maximize_master.py from the raw db/maximize_master.json scrape,
with the manually-verified exclusion/normalization pass already applied).
Each brand record here carries a `tiers` list (usually one, occasionally
more for a brand with several legitimate denomination sizes) rather than a
single flat voucher dict, since a brand can have more than one real price
option to compare — see src/services/voucher_service.py for how the best
tier is picked per purchase.
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR
from ._brand_matching import find_best_match

_MAXIMIZE_PATH = DATA_DIR / "maximize_master.json"

_brands_by_slug: dict[str, dict] | None = None
_brands_list: list[dict] | None = None


def _load() -> None:
    global _brands_by_slug, _brands_list
    if _brands_by_slug is not None:
        return
    with open(_MAXIMIZE_PATH) as f:
        data = json.load(f)
    _brands_by_slug = dict(data)
    _brands_list = list(data.values())


def all_brands() -> list[dict]:
    _load()
    return _brands_list  # type: ignore[return-value]


def brand_names() -> list[str]:
    """Every Maximize brand_name (used to extend the trusted-merchant whitelist)."""
    return [b.get("brand_name", "") for b in all_brands() if b.get("brand_name")]


def get_by_merchant(merchant_name: str) -> dict | None:
    """Find the Maximize brand record whose brand_name best matches merchant_name.

    Same exact -> prefix -> substring matching as voucher_repository.get_by_merchant.
    """
    return find_best_match(merchant_name, all_brands())


def get_by_slug(slug: str) -> dict | None:
    _load()
    return _brands_by_slug.get(slug)  # type: ignore[union-attr]
