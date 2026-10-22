"""Buy a voucher inside Dealo (Hubble SDK).

    GET  /hubble/offer?merchant=AJIO&price=2799[&in_store=true]
        -> can Hubble sell this shop's voucher, and for how much
    POST /hubble/session {id_token, name, email, marketing_optin, merchant, price}
        -> checks the shopper's phone login, saves them as a buyer, and
           returns the link that opens Hubble on the payment step
    POST /hubble/webhook
        -> Hubble tells us an order finished (signed with X-Verify)
    GET  /hubble/orders/latest   (Authorization: Bearer <id_token>)
        -> the shopper's voucher from the last 30 minutes, for the
           "voucher ready" screen

Voucher codes from the webhook are held in memory for 30 minutes so the
website can show them once, then forgotten. They never reach Supabase.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import time

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ...config import get_settings
from ...services import buyer_service, hubble_service

router = APIRouter(prefix="/hubble", tags=["hubble"])

_RECENT_SECONDS = 30 * 60
_recent_orders: dict[str, tuple[float, dict]] = {}


@router.get("/offer")
async def offer(merchant: str = Query(...), price: float = Query(..., gt=0), in_store: bool = False) -> dict:
    found = await hubble_service.offer_for(merchant, price, in_store)
    return {"available": bool(found), "offer": found}


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
    found = await hubble_service.offer_for(body.merchant, body.price, body.in_store)
    if not found:
        raise HTTPException(404, "Hubble doesn't sell this voucher")
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    name = body.name.strip()[:80] or None
    email = (body.email or "").strip()[:120] or None
    await buyer_service.save_buyer(login["uid"], login["phone"], name, email, body.marketing_optin)
    token = hubble_service.sso_token(login["uid"], login["phone"], name, email)
    return {"url": hubble_service.store_url(found, token), "offer": found}


@router.get("/test-home", response_class=HTMLResponse)
async def test_home() -> str:
    """Staging only: Hubble's store home screen framed the way the buy flow
    frames it, so a phone can reach Hubble's ⋮ → Deeplink test for the
    go-live recording (the buy flow jumps past the home screen)."""
    if get_settings().HUBBLE_ENV != "staging":
        raise HTTPException(404)
    token = hubble_service.sso_token("deeplink-test", "9999999999", "Test Buyer", None)
    url = hubble_service.home_url(token)
    return (
        '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>html,body{margin:0;height:100%}iframe{border:0;width:100%;height:100%}</style>'
        f'<iframe title="Hubble" src="{html.escape(url)}" allow="payment; clipboard-write"></iframe>'
        # Same app/link opening as BuyFlow.jsx's openHubbleLink.
        "<script>addEventListener('message',e=>{"
        "if(!/myhubble\\.money$/.test(new URL(e.origin).hostname))return;"
        "let m=e.data;if(typeof m==='string'){try{m=JSON.parse(m)}catch{return}}"
        "const l=m&&m.action==='launch_link'&&m.properties&&m.properties.link;"
        "if(typeof l!=='string'||!l||/^(javascript|data):/i.test(l))return;"
        "if(/^https?:/i.test(l))open(l,'_blank','noopener');else location.href=l})</script>"
    )


@router.post("/webhook")
async def webhook(request: Request, x_verify: str = Header(default="")) -> dict:
    secret = get_settings().HUBBLE_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(404)
    raw = await request.body()
    expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected, x_verify):
        raise HTTPException(401, "bad signature")
    order = json.loads(raw)
    if "orderStatus" in order:
        await buyer_service.save_purchase(order, get_settings().HUBBLE_ENV)
        if order["orderStatus"] == "COMPLETED" and order.get("userId"):
            _recent_orders[order["userId"]] = (time.time(), order)
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
    order = stamped[1]
    return {
        "found": True,
        "brand": order.get("brandName"),
        "vouchers": [
            {"code": v.get("cardNumber"), "pin": v.get("cardPin"), "amount": v.get("amount"), "valid_till": v.get("validTill")}
            for v in order.get("vouchers") or []
        ],
    }
