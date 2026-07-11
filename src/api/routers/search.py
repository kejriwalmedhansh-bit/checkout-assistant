"""Search endpoints — the core Dealo route-finding surface (two-step).

    POST /search    body {query}                   -> candidate product list (step 1)
    POST /routes    body {product_token, query}     -> full routes/vouchers response (step 2)
    GET  /products/{token}                          -> raw product detail + offers
"""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.search import (
    ProductDetailResponse,
    RoutesRequest,
    SearchCandidatesResponse,
    SearchRequest,
    SearchResultsResponse,
)
from ...services import search_service

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchCandidatesResponse)
def search(payload: SearchRequest) -> dict:
    """Step 1: google_shopping search. Returns candidate products for the user
    to pick from (no slow product call yet).

    Errors surface in the ``error`` field of a well-formed body (never a 500).
    """
    return search_service.search_candidates(payload.query)


@router.post("/routes", response_model=SearchResultsResponse)
def routes(payload: RoutesRequest) -> dict:
    """Step 2: build routes/vouchers/cards for a chosen product_token."""
    return search_service.build_routes_for_token(payload.product_token, payload.query, payload.title)


@router.get("/products/{product_token}", response_model=ProductDetailResponse)
def get_product(product_token: str) -> dict:
    """Raw google_product detail for a token, with offer prices normalized."""
    return search_service.get_product_detail(product_token)
