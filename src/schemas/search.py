"""Pydantic schemas for the /search and /products endpoints.

These mirror the exact output contract the frontend (templates/index.html) and
the WhatsApp formatter depend on. Fields are permissive (Optional / defaults) so
a partial or error response still validates.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str


class ProductCandidate(BaseModel):
    product_token: str
    title: str = ""
    price: float | None = None
    price_raw: str | None = None
    thumbnail: str | None = None
    source: str = ""
    rating: float | None = None
    reviews: int | None = None


class SearchCandidatesResponse(BaseModel):
    query: str
    products: list[ProductCandidate] = []
    error: str | None = None


class RoutesRequest(BaseModel):
    product_token: str
    query: str = ""
    title: str = ""
    # The exact price/seller the Product Picker displayed for this token, so
    # the route builder can pin it as a verified candidate instead of
    # silently trusting whatever a broader downstream lookup returns for the
    # same merchant (which is a different data source and isn't guaranteed
    # to describe the same listing). Optional so older frontend builds still
    # validate — falling back to prior (unpinned) behavior, not breaking.
    price: float | None = None
    source: str = ""


class DenominationPurchase(BaseModel):
    denom: int
    count: int


class VoucherUpi(BaseModel):
    pct: float = 0
    voucher_amount: float = 0
    remainder: float = 0
    saving: float = 0
    effective_price: float = 0
    txns_needed: int = 1
    purchase_cap_per_txn: int | None = None
    # What to actually buy on Gyftr — a customer can't purchase one voucher
    # for `voucher_amount` directly when it's the sum of several fixed
    # denominations; this is the real, executable breakdown.
    denomination_breakdown: list[DenominationPurchase] = []
    purchase_breakdown: str = ""


class VoucherCard(BaseModel):
    pct: float = 0
    saving: float = 0
    effective_price: float = 0


class VoucherDeal(BaseModel):
    merchant: str
    product_price: float
    voucher_url: str
    offline_only: bool = False
    upi: VoucherUpi
    card: VoucherCard
    redemption_type: str = ""
    denominations: str = ""
    redemption_instructions: list[str] = []


class CardFomo(BaseModel):
    card_name: str
    actual_saving: float
    final_cost_with_card: float
    cap_amount: float | None = None
    cap_period: str | None = None
    apply_url: str | None = None


class Seller(BaseModel):
    link: str | None = None
    delivery: str | None = None


class RouteModel(BaseModel):
    merchant: str
    listed_price: float | None = None
    final_cost: float
    sellers: list[Seller] = []
    match_type: str = ""
    title: str = ""
    voucher: VoucherDeal | None = None
    card_fomo: CardFomo | None = None


class RoutesModel(BaseModel):
    recommended: RouteModel | None = None
    alternatives: list[RouteModel] = []


class SourceModel(BaseModel):
    name: str
    brand: str = ""
    price: float | None = None
    condition: str | None = None


class SearchResultsResponse(BaseModel):
    input: str
    mode: str = "text"
    source: SourceModel | None = None
    results: list[dict[str, Any]] = []
    size_comparison: dict[str, Any] | None = None
    vouchers: list[VoucherDeal] = []
    routes: RoutesModel = RoutesModel()
    error: str | None = None


class ProductDetailResponse(BaseModel):
    error: str | None = None
    product: dict[str, Any] | None = None
    title: str = ""
    offers: list[dict[str, Any]] = []
    typical_prices: dict[str, Any] | None = None
    specifications: list[Any] = []
