"""Shared brand-name matching for voucher repositories (Gyftr, Maximize).

Same exact -> prefix -> substring algorithm both sources need to answer
"which brand record matches this merchant name" — factored out so a future
fix to the matching logic only has to happen once.
"""
from __future__ import annotations

import re

_RESELLER_WORDS = (
    "reseller", "authorised", "authorized", "premium",
    "future world", "store", "electronics", "mobile",
)


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_best_match(merchant_name: str, records: list[dict], name_key: str = "brand_name") -> dict | None:
    """Find the record whose name_key best matches merchant_name.

    Case-insensitive; partial match OK (e.g. "amazon.in" matches "Amazon").
    Prefers the closest/shortest match over more specific sub-brand entries,
    and excludes reseller / authorised-store style entries.
    """
    norm_merchant = normalize(merchant_name)
    if not norm_merchant:
        return None

    candidates = []
    for record in records:
        norm_brand = normalize(record.get(name_key, ""))
        if not norm_brand:
            continue
        if norm_brand == norm_merchant:
            rank = 0
        elif len(norm_brand) < 4:
            continue
        elif norm_merchant.startswith(norm_brand) or norm_brand.startswith(norm_merchant):
            rank = 1
        elif norm_brand in norm_merchant or norm_merchant in norm_brand:
            rank = 2
        else:
            continue

        if rank >= 1:
            brand_name_lower = record.get(name_key, "").lower()
            if any(w in brand_name_lower for w in _RESELLER_WORDS):
                continue
        candidates.append((rank, len(norm_brand), record))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]
