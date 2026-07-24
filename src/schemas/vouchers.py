"""Pydantic schemas for the /vouchers endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


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

    @field_validator("how_to_redeem_steps", mode="before")
    @classmethod
    def _null_steps_to_empty(cls, v: Any) -> Any:
        # 17 of 380 gyftr_master.json brands (e.g. Pizza Hut) store this as
        # null rather than [] — coerce rather than crash serialization.
        return v if v is not None else []
