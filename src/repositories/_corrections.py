"""Hand corrections to the scraped voucher data — see data/voucher_corrections.json.

Applied as each platform's master file loads, so a data refresh (which
rewrites the master files) never brings a corrected error back.
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR

_PATH = DATA_DIR / "voucher_corrections.json"


def apply(source: str, brands_by_slug: dict[str, dict]) -> None:
    """Patch `brands_by_slug` (one platform's master data) in place."""
    try:
        corrections = json.loads(_PATH.read_text())
    except (OSError, ValueError):
        return
    for key, fix in corrections.items():
        platform, _, slug = key.partition(":")
        record = brands_by_slug.get(slug) if platform == source else None
        if not record:
            continue
        for product in record.get("products") or []:
            product.update(fix.get("products") or {})
