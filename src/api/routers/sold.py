"""Which seller stands behind Dealo's own Buy button for a shop.

    GET /sold/offer?merchant=AJIO&price=2799[&in_store=true][&best_pct=7]
    GET /sold/brand?merchant=AJIO[&best_pct=7]

Asks every seller Dealo can sell through (Hubble, Maximize) and answers with
one: the higher rate to the shopper wins, never the one that pays Dealo
more (owner's call, 30 Oct 2026). The 2-point rule still applies to the
winner: shown only when it is within HUBBLE_RATE_TOLERANCE points of
today's best voucher rate, so a redirect that saves clearly more still wins.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from ...services import hubble_service, maximize_service
from ...services.hubble_service import worth_showing

router = APIRouter(prefix="/sold", tags=["sold"])


def _pick(found: list[dict | None], best_pct: float | None) -> dict | None:
    offers = [o for o in found if o]
    if not offers:
        return None
    best = max(offers, key=lambda o: (o["discount_pct"], -o.get("rest_at_shop", 0)))
    return best if worth_showing(best["discount_pct"], best_pct) else None


@router.get("/offer")
async def offer(
    merchant: str = Query(...),
    price: float = Query(..., gt=0),
    in_store: bool = False,
    best_pct: float | None = Query(default=None),
) -> dict:
    hub, mx = await asyncio.gather(
        hubble_service.offer_for(merchant, price, in_store),
        maximize_service.offer_for(merchant, price, in_store),
        return_exceptions=True,
    )
    hub = None if isinstance(hub, BaseException) else (hub and {**hub, "seller": "hubble"})
    mx = None if isinstance(mx, BaseException) else mx
    picked = _pick([hub, mx], best_pct)
    return {"available": bool(picked), "offer": picked}


@router.get("/brand")
async def brand(merchant: str = Query(...), best_pct: float | None = Query(default=None)) -> dict:
    hub, mx = await asyncio.gather(
        hubble_service.brand_info(merchant),
        maximize_service.brand_info(merchant),
        return_exceptions=True,
    )
    hub = None if isinstance(hub, BaseException) else (hub and {**hub, "seller": "hubble"})
    mx = None if isinstance(mx, BaseException) else mx
    picked = _pick([hub, mx], best_pct)
    return {"available": bool(picked), "brand": picked}
