"""Buy a voucher inside Dealo through Maximize's frame (second seller).

    GET  /maximize/offer?merchant=AJIO&price=2799[&in_store=true]
    GET  /maximize/brand?merchant=AJIO
    POST /maximize/session {id_token, name, email, marketing_optin, merchant, price}
        -> checks the shopper's phone login, saves them as a buyer, logs them
           in with Maximize and returns the frame address for this brand
    POST /maximize/webhook      <- Maximize: a voucher was issued
    GET  /maximize/orders/latest (Authorization: Bearer <id_token>)

Voucher codes from the webhook are held in memory for 30 minutes so the
website can show them once, then forgotten. They never reach Supabase.
The webhook carries no signature yet (30 Oct 2026): a notice is accepted
only for a phone that opened a Maximize session here in the last two hours,
or when the shared secret matches once Maximize provides one.
"""
from __future__ import annotations

import hmac
import json
import re
import time

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from ...config import get_settings
from ...services import buyer_service, maximize_service
from ...services.hubble_service import worth_showing

router = APIRouter(prefix="/maximize", tags=["maximize"])

_RECENT_SECONDS = 30 * 60
_recent_orders: dict[str, tuple[float, dict]] = {}


@router.get("/offer")
async def offer(
    merchant: str = Query(...),
    price: float = Query(..., gt=0),
    in_store: bool = False,
    best_pct: float | None = Query(default=None),
) -> dict:
    found = await maximize_service.offer_for(merchant, price, in_store)
    if found and not worth_showing(found["discount_pct"], best_pct):
        found = None
    return {"available": bool(found), "offer": found}


@router.get("/brand")
async def brand(merchant: str = Query(...), best_pct: float | None = Query(default=None)) -> dict:
    found = await maximize_service.brand_info(merchant)
    if found and not worth_showing(found["discount_pct"], best_pct):
        found = None
    return {"available": bool(found), "brand": found}


class SessionRequest(BaseModel):
    id_token: str
    name: str
    email: str | None = None
    marketing_optin: bool = False
    merchant: str
    price: float
    in_store: bool = False


@router.post("/session")
async def session(body: SessionRequest) -> dict:
    found = await maximize_service.offer_for(body.merchant, body.price, body.in_store)
    if not found:
        raise HTTPException(404, "Maximize doesn't sell this voucher")
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    name = body.name.strip()[:80] or None
    email = (body.email or "").strip()[:120] or None
    await buyer_service.save_buyer(login["uid"], login["phone"], name, email, body.marketing_optin)
    try:
        token = await maximize_service.user_token(login["uid"], login["phone"], name, email)
    except Exception as exc:  # their login API down: the shopper keeps the redirect
        print(f"[maximize] login failed: {exc}")
        raise HTTPException(502, "Maximize login failed") from exc
    return {"url": maximize_service.store_url(found, token), "offer": found}


@router.post("/webhook")
async def webhook(request: Request, x_maximize_secret: str = Header(default="")) -> dict:
    s = get_settings()
    if not s.MAXIMIZE_ENABLED:
        raise HTTPException(404)
    raw = await request.body()
    try:
        notice = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(400, "not json") from exc
    phone = re.sub(r"\D", "", str(notice.get("customerPhone") or ""))[-10:]
    uid = maximize_service.session_owner(phone)
    signed = bool(s.MAXIMIZE_WEBHOOK_SECRET) and hmac.compare_digest(s.MAXIMIZE_WEBHOOK_SECRET, x_maximize_secret or "")
    if not uid and not signed:
        raise HTTPException(401, "no session for this shopper")
    if notice.get("event") == "gift_card.issued":
        vouchers = notice.get("vouchers") or []
        await buyer_service.save_sale(
            seller="maximize",
            ref=str(notice.get("transactionId") or notice.get("requestId") or ""),
            uid=uid,
            brand=notice.get("giftCardName"),
            amount=notice.get("totalGiftCardValue"),
            discount=(float(notice.get("totalGiftCardValue") or 0) - float(notice.get("orderValue") or 0)) or None,
            status="COMPLETED",
            environment=s.MAXIMIZE_ENV,
        )
        if uid:
            _recent_orders[uid] = (time.time(), {
                "brand": notice.get("giftCardName"),
                "vouchers": [
                    {"code": v.get("giftCardCode"), "pin": v.get("giftCardPin"), "amount": v.get("denomination"), "valid_till": v.get("expiryDate")}
                    for v in vouchers
                ],
            })
    return {"ok": True}


@router.get("/orders/latest")
async def latest_order(authorization: str = Header(default="")) -> dict:
    try:
        login = await buyer_service.verify_login(authorization.removeprefix("Bearer ").strip())
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    stamped = _recent_orders.get(login["uid"])
    if not stamped or time.time() - stamped[0] > _RECENT_SECONDS:
        return {"found": False}
    return {"found": True, **stamped[1]}
