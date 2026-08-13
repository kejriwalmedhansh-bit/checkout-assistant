"""Card options for the "Have a credit card?" flow.

    POST /card-options    body: the route the shopper is looking at
                           -> every card that earns something on it, with its
                              real voucher-discount + cashback numbers.

The frontend already has the full route object from /routes, so it's sent
back as-is rather than re-fetched by a token — Dealo keeps no route state
server-side between requests.
"""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.search import CardOptionsResponse, RouteModel
from ...services import card_service

router = APIRouter(tags=["cards"])


@router.post("/card-options", response_model=CardOptionsResponse)
def card_options(route: RouteModel) -> dict:
    """Every card eligible on this route, each with its own real numbers —
    no auto-picked "best" card, no comparison against UPI."""
    options = [
        quote
        for card_name in card_service.eligible_cards_for_route(route)
        if (quote := card_service.get_card_quote(route, card_name)) is not None
    ]
    return {"options": options}
