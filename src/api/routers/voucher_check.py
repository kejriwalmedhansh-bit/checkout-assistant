"""Checkout-page voucher check for the Chrome extension.

    GET /voucher-check?domain=...&price=...
        -> is there a live Gyftr/Maximize/BuyHatke voucher deal for the
           brand at this domain? `price` is optional (see
           voucher_service.get_voucher_check for the priced vs. headline-rate
           behavior difference).

Never 404s / never raises on "no deal" — the extension's popup needs a plain
answer (has_voucher: true/false) either way, not an error to handle.
"""
from __future__ import annotations

import re
from functools import lru_cache

from fastapi import APIRouter, Query

from ...repositories import (
    buyhatke_repository,
    domain_brand_repository,
    maximize_repository,
    voucher_repository,
)
from ...schemas.voucher_check import VoucherCheckResponse
from ...services import voucher_service

router = APIRouter(tags=["voucher-check"])


@router.get("/headline")
async def headline() -> dict:
    """Live discount figures for the extension's welcome screen.

    That screen used to name a rate in its own HTML — "16% off" — which was
    true the day it was written and becomes a lie the first time the
    fortnightly refresh moves it. A number a stranger reads before they trust
    anything is the worst possible place for a stale figure.

    Deliberately NOT the maximum. The single best rate in the catalogue today
    is 85% (a Yatra listing) and the next few are tax filing and magazine
    subscriptions — figures that are either wrong or irrelevant to someone
    installing a shopping extension, and both read as a scam on a welcome
    screen. A high percentile survives one bad scrape; a maximum is defined by
    it.

    Returns the middle of the catalogue and its 95th percentile, so the page
    can say what shops usually take off and what the good ones do, both true
    on the day they are read.
    """
    from ...repositories import buyhatke_repository, maximize_repository, voucher_repository

    rates = []
    listings = (
        voucher_repository.all_vouchers()
        + maximize_repository.all_brands()
        + buyhatke_repository.all_brands()
    )
    for record in listings:
        for product in record.get("products", []):
            if product.get("status") != "active":
                continue
            rate = product.get("best_discount_pct") or 0
            if rate > 0:
                rates.append(rate)

    if not rates:
        return {"typical_pct": None, "strong_pct": None, "listings": 0}

    rates.sort()
    return {
        "typical_pct": round(rates[len(rates) // 2], 1),
        "strong_pct": round(rates[int(len(rates) * 0.95)], 1),
        "listings": len(rates),
    }


# Endings that are a country's own second level rather than anyone's name.
# India's shops live on .co.in more than on anything else, so reading the
# label before the ending — rather than the second label from the right —
# is not an edge case here, it is the common case.
_TWO_PART_ENDINGS = {
    "co", "com", "net", "org", "gov", "edu", "ac", "gen", "firm", "ind", "res",
}


def _domain_root(domain: str) -> str:
    """The registrable brand label of a host — "ajio" for ajio.com,
    "steampowered" for store.steampowered.com, "subway" for subway.co.in.

    Taking the second label from the right reads "co" out of every .co.in
    address, and "co" matches no brand, so every Indian shop on one came back
    as having no voucher unless it happened to be in the hand-written domain
    map — 10 of its 242 rows. Found 2026-09-09 when subway.co.in answered
    "no voucher" live while the same shop priced fine by name.
    """
    parts = domain.strip().lower().lstrip(".").split(".")
    if len(parts) >= 3 and parts[-2] in _TWO_PART_ENDINGS:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


# The same test scripts/build_domain_brand_map.py uses to keep store-only
# brands out of the domain map. Repeated here because the map is no longer
# the only way in: a shop whose address says its own name is answered without
# the map, so reliancedigital.in reached Reliance Digital's in-store voucher
# again the moment the two changes met (caught 2026-09-17 before merging).
# The extension only ever runs on a website, so a voucher no seller lets you
# spend online is never an answer here, whichever way the brand was found.
_OFFLINE_ONLY = {"offline", "in-store", "in store", "instore", "store locator"}
_IN_STORE_NAME = re.compile(r"in.?store|store only|offline", re.I)


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


@lru_cache(maxsize=1)
def _store_only_brands() -> frozenset[str]:
    kinds: dict[str, set[str]] = {}
    records = (
        voucher_repository.all_vouchers()
        + maximize_repository.all_brands()
        + buyhatke_repository.all_brands()
    )
    for record in records:
        seen = kinds.setdefault(_norm(record.get("brand_name")), set())
        for product in record.get("products") or []:
            kind = str(product.get("redemption_type") or "").strip().lower()
            if kind:
                seen.add(kind)
    labelled = {name for name, seen in kinds.items() if seen and seen <= _OFFLINE_ONLY}
    # A label is only the seller's summary. Where the card's own terms say it
    # works online (Gyftr labels Air India Add-ons offline; its terms say
    # airindia.com), the terms win.
    online_by_terms = {_norm(card["name"]) for card in voucher_service._online_cards()}
    return frozenset(labelled - online_by_terms)


def _usable_online(deal: dict | None) -> bool:
    if not deal:
        return False
    brand = deal.get("brand_name") or ""
    return not _IN_STORE_NAME.search(brand) and _norm(brand) not in _store_only_brands()


@router.get("/voucher-check", response_model=VoucherCheckResponse)
def voucher_check(domain: str = Query(..., min_length=1), price: float | None = None) -> dict:
    # The domain map is built from an audit CSV whose row for a domain is
    # sometimes a SUB-brand rather than the parent (ajio.com's only row is
    # "Ajio Luxe", AJIO's premium arm) — telling a shopper on ordinary AJIO
    # about an "AJIO Luxe Gift Voucher" is misleading, and was caught in live
    # testing 2026-08-31. The host's own brand label is the more truthful
    # identity, so try it first and keep it only when it resolves to a brand
    # whose name matches it exactly; otherwise fall back to the mapped name.
    #
    # Asked BEFORE the map, not after. The map used to gate this: a domain
    # missing from its 242 rows was answered "no voucher" without the host's
    # own name ever being tried, so subway.co.in drew a blank while Subway
    # priced fine by name. An exact brand-name match is its own evidence and
    # needs no listing to authorise it; the map remains the fallback for hosts
    # that don't say their brand (lifestylestores.com, tatacliq.com).
    root = _domain_root(domain)
    root_deal = voucher_service.get_voucher_check(root, price) if root else None
    if (
        root_deal
        and voucher_service.is_exact_brand_match(root, root_deal["brand_name"])
        and _usable_online(root_deal)
    ):
        return _with_product_choices(root, root_deal, price, domain)

    # No single card answers for this host: its choices still can. The Times
    # Prime map row names one membership card, which can't price every order.
    none = {"has_voucher": False}
    brand_name = domain_brand_repository.brand_for_domain(domain)
    if brand_name is None:
        return _with_product_choices(root, none, price, domain)

    deal = voucher_service.get_voucher_check(brand_name, price)
    if not _usable_online(deal):
        return _with_product_choices(root, none, price, domain)
    return _with_product_choices(root, deal, price, domain)


def _with_product_choices(root: str, deal: dict, price: float | None, domain: str = "") -> dict:
    """On a shop whose cards each pay for different products, the answer is
    the list, not whichever card pays most: a 14% hotels-only MakeMyTrip card
    was otherwise offered to someone booking a flight.

    When a choice belongs to the very website the shopper is on (luxe.ajio.com
    vs ajio.com), that choice is the answer and nothing is asked."""
    choices = [c for c in voucher_service.product_choices(root or "", price) if _usable_online(c)]
    if len(choices) < 2:
        return deal
    host = domain.strip().lower().removeprefix("www.")
    on_this_site = [
        c for c in choices
        if c.get("choice_host") and (host == c["choice_host"] or host.endswith("." + c["choice_host"]))
    ]
    if on_this_site:
        return max(on_this_site, key=lambda c: len(c["choice_host"]))
    return {**choices[0], "product_choices": choices}
