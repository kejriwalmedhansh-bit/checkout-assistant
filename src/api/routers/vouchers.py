"""Gyftr voucher browse endpoints.

    GET /vouchers          optional ?q= brand-name substring filter
    GET /vouchers/{slug}   full voucher detail
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...repositories import voucher_repository
from ...schemas.vouchers import VoucherDetailOut, VoucherSummaryOut

router = APIRouter(tags=["vouchers"])


@router.get("/vouchers", response_model=list[VoucherSummaryOut])
def list_vouchers(q: str | None = None, limit: int | None = None) -> list[dict]:
    # Same products[0]-nesting flattening as get_voucher below.
    return [
        {**v, **((v.get("products") or [{}])[0])}
        for v in voucher_repository.list_vouchers(q=q, limit=limit)
    ]


@router.get("/vouchers/{slug}", response_model=VoucherDetailOut)
def get_voucher(slug: str) -> dict:
    voucher = voucher_repository.get_by_slug(slug)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    # Canonical schema nests the actual rate/denomination fields inside
    # products[0] — same flattening search_service._gyftr_voucher_to_output_shape
    # and voucher_service.get_best_voucher_deal both do.
    products = voucher.get("products") or [{}]
    return {**voucher, **products[0]}
