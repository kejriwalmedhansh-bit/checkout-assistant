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


_TWO_PART_ENDINGS = {"co", "com", "net", "org", "gov", "edu", "ac", "gen", "firm", "ind", "res"}


def _site_of(host: str) -> str:
    parts = host.strip().lower().removeprefix("www.").split(".")
    if len(parts) >= 3 and parts[-2] in _TWO_PART_ENDINGS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def shop_sites() -> list[str]:
    """Every website Dealo recognises as a shop, as the website itself
    ("ajio.com" for luxe.ajio.com). The extension loads on every page of
    these, so it can see a cart that opens as a panel or a pop-up checkout
    over any page, not only on cart-looking addresses."""
    _load()
    return sorted({_site_of(d) for d in _domain_to_brand})  # type: ignore[union-attr]
