"""Pydantic schemas for the /vouchers endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class VoucherSummaryOut(BaseModel):
    brand_name: str
    slug: str
    redemption_type: str = ""
    best_payment_method: str | None = None
    best_discount_pct: float | None = None


class VoucherDetailOut(BaseModel):
    brand_name: str
    slug: str
    redemption_type: str = ""
    denominations: list[int] = []
    discounts: dict[str, Any] = {}
    best_payment_method: str | None = None
    best_discount_pct: float | None = None
    stack_limit: int | None = None
    value_cap: float | None = None
    purchase_cap_per_txn: int | None = None
    redemption_restrictions: list[str] = []
    how_to_redeem_steps: list[str] = []
