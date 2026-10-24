"""Search endpoints — the core Dealo route-finding surface (two-step).

    POST /search    body {query}                   -> candidate product list (step 1)
    POST /routes    body {product_token, query}     -> full routes/vouchers response (step 2)
    GET  /products/{token}                          -> raw product detail + offers
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..rate_limit import enforce_search_rate_limit
from ...schemas.search import (
    CheckedRoutesResponse,
    ProductDetailResponse,
    RoutesRequest,
    SearchCandidatesResponse,
    SearchRequest,
    SearchResultsResponse,
)
from ...services import search_service

# Every endpoint below spends money to answer — SearchApi for the lookup, then
# Crawlbase/Apify to read store pages — and none of them needs an account, so
# the cost guard goes on the whole router rather than being remembered
# endpoint by endpoint. /voucher-check and /vouchers are deliberately not
# covered: they answer from local data files and cost nothing to serve.
router = APIRouter(tags=["search"], dependencies=[Depends(enforce_search_rate_limit)])


@router.post("/search", response_model=SearchCandidatesResponse)
def search(payload: SearchRequest) -> dict:
    """Step 1: google_shopping search. Returns candidate products for the user
    to pick from (no slow product call yet).

    Errors surface in the ``error`` field of a well-formed body (never a 500).
    """
    result = search_service.search_candidates(payload.query, exact=payload.exact)
    pick = result.get("auto_pick")
    if pick:
        # The website asks for this exact comparison next: start it now, with
        # the same inputs it will send (react/src/store/searchStore.js).
        search_service.start_routes(
            pick.get("product_token"), payload.query, pick.get("title") or "",
            pick.get("price"), pick.get("source") or "",
        )
    return result


@router.post("/routes", response_model=SearchResultsResponse)
def routes(payload: RoutesRequest) -> dict:
    """Step 2: build routes/vouchers/cards for a chosen product_token."""
    return search_service.routes_without_waiting_on_check(
        payload.product_token, payload.query, payload.title,
        picked_price=payload.price, picked_source=payload.source,
    )


# Outside the cost guard: it only waits on a comparison /routes already paid
# for, and counting it would make every search cost two of the shopper's
# allowance.
checked_router = APIRouter(tags=["search"])


@checked_router.get("/routes/checked/{check_id}", response_model=CheckedRoutesResponse)
def routes_checked(check_id: str) -> dict:
    """The /routes answer after the winning store's live price re-check."""
    return {"result": search_service.checked_routes(check_id)}


@router.get("/products/{product_token}", response_model=ProductDetailResponse)
def get_product(product_token: str) -> dict:
    """Raw google_product detail for a token, with offer prices normalized."""
    return search_service.get_product_detail(product_token)
