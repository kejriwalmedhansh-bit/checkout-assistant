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
import re
from functools import lru_cache
from urllib.parse import unquote

from ..constants import DATA_DIR
from . import _corrections
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
    _corrections.apply("maximize", data)
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


_CARD_LINK_RE = re.compile(r"^https?://(?:www\.)?maximize\.money/gift-cards/([^/?#]+)/(\d+)/?$")


@lru_cache(maxsize=1)
def _brand_ids() -> dict[str, int]:
    """Maximize's brand number per card number; see data/maximize_brand_ids.json."""
    try:
        with open(DATA_DIR / "maximize_brand_ids.json", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    cards = data.get("cards") or {}
    return {str(k): int(v) for k, v in cards.items() if str(v).isdigit()}


def card_link(url: str | None) -> str | None:
    """The link that opens THIS card on maximize.money.

    A catalogue link (/gift-cards/<slug>/<card>) redirects to the brand page
    with the card number under a name the page ignores, so the brand's
    default card opens instead: a Tanishq Gold Jewellery link (1278) opened
    the Studded card (owner's test, 2026-11-04). Written the way Maximize's
    own listing writes it, with the brand number, the right card opens.
    Links for cards whose brand number is not on file are returned unchanged."""
    if not url:
        return url
    m = _CARD_LINK_RE.match(url.strip())
    if not m:
        return url
    slug, card = unquote(m.group(1)), m.group(2)
    brand_id = _brand_ids().get(card)
    if brand_id is None:
        return url
    path = re.sub(r"[^A-Za-z0-9]+", "", slug) or slug
    return f"https://www.maximize.money/savemax/{path}?flow=GIFTCARD&brandId={brand_id}&giftcardId={card}"
