"""Brand-name -> best affiliate network lookup, used by /go (redirect.py) to
decide whether a merchant link should wrap through Cuelinks or INRDeals.

Loads data/affiliate_coverage.json once (built by
scripts/refresh_affiliate_coverage.py — re-run that script to refresh; this
module doesn't call either network's API directly). Same loader shape as
domain_brand_repository.py.
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR

_MAP_PATH = DATA_DIR / "affiliate_coverage.json"

_coverage: dict[str, dict] | None = None


def _load() -> None:
    global _coverage
    if _coverage is not None:
        return
    with open(_MAP_PATH) as f:
        _coverage = json.load(f)


def network_for_brand(brand: str) -> dict | None:
    """Returns the coverage entry for `brand` (e.g. {"network": "inrdeals",
    "inrdeals_campaign_type": "cps"}), or None if the brand isn't in the
    file at all (script hasn't been re-run since a new brand was added to
    domain_brand_map.json) — treat None the same as {"network": "none"}."""
    _load()
    return _coverage.get(brand)  # type: ignore[union-attr]
