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

from fastapi import APIRouter, Query

from ...repositories import domain_brand_repository
from ...schemas.voucher_check import VoucherCheckResponse
from ...services import voucher_service

router = APIRouter(tags=["voucher-check"])


def _domain_root(domain: str) -> str:
    """The registrable brand label of a host — "ajio" for ajio.com,
    "steampowered" for store.steampowered.com."""
    parts = domain.strip().lower().lstrip(".").split(".")
    return parts[-2] if len(parts) >= 2 else parts[0]


@router.get("/voucher-check", response_model=VoucherCheckResponse)
def voucher_check(domain: str = Query(..., min_length=1), price: float | None = None) -> dict:
    brand_name = domain_brand_repository.brand_for_domain(domain)
    if brand_name is None:
        return {"has_voucher": False}

    # The domain map is built from an audit CSV whose row for a domain is
    # sometimes a SUB-brand rather than the parent (ajio.com's only row is
    # "Ajio Luxe", AJIO's premium arm) — telling a shopper on ordinary AJIO
    # about an "AJIO Luxe Gift Voucher" is misleading, and was caught in live
    # testing 2026-08-31. The host's own brand label is the more truthful
    # identity, so try it first and keep it only when it resolves to a brand
    # whose name matches it exactly; otherwise fall back to the mapped name.
    root = _domain_root(domain)
    root_deal = voucher_service.get_voucher_check(root, price) if root else None
    if root_deal and voucher_service.is_exact_brand_match(root, root_deal["brand_name"]):
        return root_deal

    deal = voucher_service.get_voucher_check(brand_name, price)
    if deal is None:
        return {"has_voucher": False}
    return deal
