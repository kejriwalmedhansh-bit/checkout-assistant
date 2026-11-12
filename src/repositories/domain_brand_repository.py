"""Domain -> brand-name lookup for the Chrome extension's checkout check.

Loads data/domain_brand_map.json once (built by
scripts/build_domain_brand_map.py from audits/brand_website_matching.csv —
re-run that script after the CSV changes; this module doesn't read the CSV
directly).
"""
from __future__ import annotations

import json

from ..constants import DATA_DIR

_MAP_PATH = DATA_DIR / "domain_brand_map.json"

_domain_to_brand: dict[str, str] | None = None


def _load() -> None:
    global _domain_to_brand
    if _domain_to_brand is not None:
        return
    with open(_MAP_PATH) as f:
        _domain_to_brand = json.load(f)


def brand_for_domain(domain: str) -> str | None:
    """`domain` should already be a bare host (no scheme/path), e.g.
    "myntra.com" — matches exactly, plus a "www." strip, since that's the
    only normalization the map's own build script applies."""
    _load()
    domain = domain.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return _domain_to_brand.get(domain)  # type: ignore[union-attr]


def domain_for_shop(shop_key: str) -> str | None:
    """The website of a shop named by its letters-only key ("makemytrip" ->
    "makemytrip.com"), for showing its logo. A domain whose own name is the
    shop wins ("ajio.com" for "ajio"); else one whose mapped brand starts with
    the shop's name ("giva.co" -> "GIVA Silver Coin" for "giva")."""
    _load()
    key = "".join(ch for ch in (shop_key or "").lower() if ch.isalnum())
    if len(key) < 3:
        return None
    by_brand = None
    for domain, brand in sorted(_domain_to_brand.items()):  # type: ignore[union-attr]
        if domain.split(".")[0].replace("-", "") == key:
            return domain
        if by_brand is None and "".join(ch for ch in brand.lower() if ch.isalnum()).startswith(key):
            by_brand = domain
    return by_brand
