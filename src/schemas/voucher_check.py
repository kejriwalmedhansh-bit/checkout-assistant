"""Pydantic schema for GET /voucher-check (the Chrome extension's checkout
popup)."""
from __future__ import annotations

from pydantic import BaseModel


class VoucherCheckResponse(BaseModel):
    has_voucher: bool
    brand_name: str | None = None
    voucher_source: str | None = None
    pct: float | None = None
    # None when no price was passed in (headline-rate-only lookup) rather
    # than a real computed 0 — the extension distinguishes "don't know" from
    # "definitely nothing" when deciding whether to show a ₹ figure.
    saving: float | None = None
    effective_price: float | None = None
    voucher_url: str | None = None
    priced: bool = False

    # --- the guided journey needs all of this, and only exists when priced ---
    # How much voucher to actually buy, and the real executable breakdown
    # ("2×₹2,000") — a shopper can't buy one ₹4,000 voucher when the brand
    # only sells ₹2,000 denominations.
    voucher_amount: float | None = None
    purchase_breakdown: str = ""
    denomination_breakdown: list[dict] = []
    txns_needed: int = 1
    # What's still payable at the store after the voucher covers what it can.
    remainder: float = 0
    # The discount if they pay for the voucher BY CARD instead of UPI. The
    # promised rate is the UPI one, so the extension warns when these differ.
    card_pct: float | None = None
    # The brand's own redemption instructions, for the "where do I enter it"
    # step once they're back at the store.
    how_to_redeem_short: str | None = None
    how_to_redeem_steps: list[str] = []
