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
    return voucher_repository.list_vouchers(q=q, limit=limit)


@router.get("/vouchers/{slug}", response_model=VoucherDetailOut)
def get_voucher(slug: str) -> dict:
    voucher = voucher_repository.get_by_slug(slug)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    return voucher
