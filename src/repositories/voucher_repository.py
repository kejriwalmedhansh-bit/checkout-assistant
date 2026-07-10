"""Gyftr voucher data access.

Loads data/gyftr_master.json once. Provides brand matching (exact -> prefix ->
substring, ported from db/voucher_lookup.get_gyftr_voucher) plus listing and
slug lookup for the /vouchers endpoints.
"""
from __future__ import annotations

import json
import re

from ..constants import DATA_DIR

_VOUCHERS_PATH = DATA_DIR / "gyftr_master.json"

_vouchers_by_slug: dict[str, dict] | None = None
_vouchers_list: list[dict] | None = None


def _load() -> None:
    global _vouchers_by_slug, _vouchers_list
    if _vouchers_by_slug is not None:
        return
    with open(_VOUCHERS_PATH) as f:
        data = json.load(f)
    _vouchers_by_slug = dict(data)
    _vouchers_list = list(data.values())


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def all_vouchers() -> list[dict]:
    _load()
    return _vouchers_list  # type: ignore[return-value]


def brand_names() -> list[str]:
    """Every voucher brand_name (used to build the trusted-merchant whitelist)."""
    return [v.get("brand_name", "") for v in all_vouchers() if v.get("brand_name")]


def get_by_merchant(merchant_name: str) -> dict | None:
    """Find the Gyftr voucher whose brand_name best matches merchant_name.

    Case-insensitive; partial match OK (e.g. "amazon.in" matches "Amazon").
    Prefers the closest/shortest match over more specific sub-brand vouchers,
    and excludes reseller / authorised-store style entries.
    """
    norm_merchant = _normalize(merchant_name)
    if not norm_merchant:
        return None

    candidates = []
    for voucher in all_vouchers():
        norm_brand = _normalize(voucher.get("brand_name", ""))
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
            brand_name_lower = voucher.get("brand_name", "").lower()
            if any(w in brand_name_lower for w in (
                "reseller", "authorised", "authorized", "premium",
                "future world", "store", "electronics", "mobile",
            )):
                continue
        candidates.append((rank, len(norm_brand), voucher))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def get_by_slug(slug: str) -> dict | None:
    _load()
    return _vouchers_by_slug.get(slug)  # type: ignore[union-attr]


def list_vouchers(q: str | None = None, limit: int | None = None) -> list[dict]:
    """List vouchers, optionally filtered by a case-insensitive substring of brand_name."""
    items = all_vouchers()
    if q:
        ql = q.lower()
        items = [v for v in items if ql in (v.get("brand_name") or "").lower()]
    if limit is not None:
        items = items[:limit]
    return items
