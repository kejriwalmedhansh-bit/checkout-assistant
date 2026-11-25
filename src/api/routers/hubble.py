"""Buy a voucher inside Dealo (Hubble SDK).

    GET  /hubble/offer?merchant=AJIO&price=2799[&in_store=true]
        -> can Hubble sell this shop's voucher, and for how much
    POST /hubble/session {id_token, name, email, marketing_optin, merchant, price}
        -> checks the shopper's phone login, saves them as a buyer, and
           returns the link that opens Hubble on the payment step
    POST /hubble/webhook
        -> Hubble tells us an order finished (signed with X-Verify)
    GET  /hubble/orders/latest?session=&brand=   (Authorization: Bearer <id_token>)
        -> the voucher this purchase made (the payment screen /session
           opened, for this brand), for the "voucher ready" screen
    POST /hubble/login {id_token}
        -> after the SMS code: saves the number, returns the name we know (if any)
    POST /hubble/account {id_token, name, email}
        -> a new number's name and email (asked once, after the code)
    GET  /hubble/card[?ref=]     (Authorization: Bearer <id_token>)
        -> link to the shopper's gift card (code + PIN) on Hubble's own page
    GET  /hubble/me              (Authorization: Bearer <id_token>)
        -> everything the shopper bought and saved, for "Your account"
           (no codes: those stay on the shopper's phone)

Voucher codes from the webhook are held in memory for 30 minutes so the
website can show them once, then forgotten. They never reach Supabase.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ...config import get_settings
from ...services import buyer_service, hubble_service

router = APIRouter(prefix="/hubble", tags=["hubble"])

_RECENT_SECONDS = 30 * 60
# Every order a shopper finished in the last 30 minutes, newest last. A list,
# not one slot: a second voucher bought soon after the first used to show the
# first one's code (audit 18 Nov 2026).
_recent_orders: dict[str, list[tuple[float, dict]]] = {}
# Each payment screen /session opens: who, which voucher, and when (server
# clock), so the "voucher ready" screen gets this purchase's code only.
_sessions: dict[str, tuple[float, str, str]] = {}


def _remember_order(uid: str, order: dict) -> None:
    now = time.time()
    kept = [(t, o) for t, o in _recent_orders.get(uid, []) if now - t <= _RECENT_SECONDS]
    ref = order.get("transactionReferenceId")
    kept = [(t, o) for t, o in kept if not ref or o.get("transactionReferenceId") != ref]
    _recent_orders[uid] = (kept + [(now, order)])[-10:]


def _open_session(uid: str, brand_name: str) -> str:
    now = time.time()
    for stale in [k for k, (t, _, _) in _sessions.items() if now - t > _RECENT_SECONDS]:
        _sessions.pop(stale, None)
    sid = secrets.token_urlsafe(12)
    _sessions[sid] = (now, uid, brand_name)
    return sid


def _this_purchase(uid: str, session: str | None, brand: str | None) -> dict | None:
    """The order this purchase made. With the session /session handed out:
    the shopper's first order for that voucher after its payment screen
    opened. Without one (older page, or a restart forgot it): their newest
    order for `brand`. With neither: their newest order, as before."""
    now = time.time()
    orders = [(t, o) for t, o in _recent_orders.get(uid, []) if now - t <= _RECENT_SECONDS]
    started = _sessions.get(session or "")
    if started and started[1] == uid:
        after, want = started[0], started[2]
        fits = [o for t, o in orders if t >= after and _same_brand(o, want)]
        return fits[0] if fits else None
    if brand:
        fits = [o for _, o in orders if _same_brand(o, brand)]
        return fits[-1] if fits else None
    return orders[-1][1] if orders else None


def _same_brand(order: dict, brand: str) -> bool:
    return hubble_service.normalize(order.get("brandName") or "") == hubble_service.normalize(brand)

# Which visit and which link a shopper's purchase belongs to, noted when the
# payment screen opens and read back when Hubble's webhook reports the order
# (usually within minutes). Lets the 'Voucher Sold' event join the shopper's
# funnel in Mixpanel. Memory only: a restart in between loses the join, never
# the sale.
_ATTRIBUTION_SECONDS = 6 * 60 * 60
_attribution: dict[str, tuple[float, dict]] = {}


def _remember_attribution(uid: str, body: "SessionRequest") -> None:
    now = time.time()
    for stale in [k for k, (t, _) in _attribution.items() if now - t > _ATTRIBUTION_SECONDS]:
        _attribution.pop(stale, None)
    _attribution[uid] = (now, {
        "dealo_id": body.dealo_id,
        "visit_id": body.visit_id,
        "src": body.src,
        "placement": body.placement,
        "merchant": body.merchant,
        "referrer_domain": body.referrer_domain,
        "landing_page": body.landing_page,
        "utm_source": body.utm_source,
        "utm_medium": body.utm_medium,
        "utm_campaign": body.utm_campaign,
    })


def _attribution_for(uid: str | None) -> dict:
    stamped = _attribution.get(uid or "")
    if not stamped or time.time() - stamped[0] > _ATTRIBUTION_SECONDS:
        return {}
    return stamped[1]


@router.get("/offer")
async def offer(
    merchant: str = Query(...),
    price: float = Query(..., gt=0),
    in_store: bool = False,
    best_pct: float | None = Query(default=None, description="today's best voucher rate for this shop, if any"),
    link: str | None = Query(default=None, description="the result's buy link; its website finds the shop when the name doesn't"),
) -> dict:
    found = await hubble_service.offer_for(merchant, price, in_store, link)
    if found and not hubble_service.worth_showing(found["discount_pct"], best_pct):
        found = None
    return {"available": bool(found), "offer": found}


@router.get("/brand")
async def brand(
    merchant: str | None = Query(default=None),
    slug: str | None = Query(default=None, description="the voucher a /buy/<slug> link names"),
    best_pct: float | None = Query(default=None),
    in_store: bool = Query(default=False, description="the shopper pays in a shop (a buy link's ?store=1)"),
) -> dict:
    """Shop-name search (no cart price yet), or a buy link: can Dealo sell
    this shop's voucher, at what rate, and which amounts may the shopper pick."""
    if not merchant and not slug:
        raise HTTPException(status_code=422, detail="merchant or slug is required")
    found = await hubble_service.brand_info(merchant, slug=slug, in_store=in_store)
    if found and not hubble_service.worth_showing(found["discount_pct"], best_pct):
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
    # The result's buy link, so the shop is found the same way /offer found it.
    link: str | None = None
    # Analytics only (see _attribution): the visitor's anonymous Mixpanel id
    # when they agreed to cookies, and the buy link's src / page placement.
    dealo_id: str | None = None
    # Without consent: the visit's in-memory tag (visit:<random>), the id its
    # website events are counted under. Lets the sale join that one visit.
    visit_id: str | None = None
    src: str | None = None
    placement: str | None = None
    # Where the visit came from: the site that sent the shopper, the first
    # page they landed on and any campaign tag. Facts about the visit, not
    # the person, so they are sent with or without cookie consent.
    referrer_domain: str | None = None
    landing_page: str | None = None
    utm_source: str | None = None
    # utm_campaign names the post, reel or creator (getdealo.in/ig/<name>).
    utm_medium: str | None = None
    utm_campaign: str | None = None


def _visit_source(body) -> dict:
    """The visit's source as sent by the website, for the buyer's record."""
    return {k: getattr(body, k, None) for k in ("referrer_domain", "landing_page", "utm_source", "utm_medium", "utm_campaign")}


@router.post("/session")
async def session(body: SessionRequest) -> dict:
    found = await hubble_service.offer_for(body.merchant, body.price, body.in_store, body.link)
    if not found:
        raise HTTPException(404, "Hubble doesn't sell this voucher")
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    name = body.name.strip()[:80] or None
    email = (body.email or "").strip()[:120] or None
    await buyer_service.save_buyer(login["uid"], login["phone"], name, email, body.marketing_optin)
    await buyer_service.note_first_source(login["uid"], _visit_source(body))
    _remember_attribution(login["uid"], body)
    buyer_service.report_buyer_seen(login["uid"], "payment_screen", get_settings().HUBBLE_ENV, _visit_source(body),
                                    dealo_id=body.dealo_id, visit_id=body.visit_id)
    token = hubble_service.sso_token(login["uid"], login["phone"], name, email)
    return {"url": hubble_service.store_url(found, token), "offer": found,
            "session": _open_session(login["uid"], found["brand_name"]),
            # True until the buyer has answered "How did you hear about Dealo?"
            "ask_heard_from": await buyer_service.should_ask_heard_from(login["uid"])}


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
        # The code first, so the "voucher ready" screen shows it even if the
        # record below fails to save.
        if order["orderStatus"] == "COMPLETED" and order.get("userId"):
            _remember_order(order["userId"], order)
        saved = await buyer_service.save_purchase(order, get_settings().HUBBLE_ENV, attribution=_attribution_for(order.get("userId")))
        if not saved:
            # Not "ok": Hubble can send it again, instead of the purchase
            # silently missing from "Your account" (audit 18 Nov 2026).
            raise HTTPException(503, "could not save the purchase")
    return {"ok": True}


@router.get("/orders/latest")
async def latest_order(
    authorization: str = Header(default=""),
    session: str | None = Query(default=None, description="the session /hubble/session returned"),
    brand: str | None = Query(default=None, description="the voucher bought, as Hubble names it"),
) -> dict:
    try:
        login = await buyer_service.verify_login(authorization.removeprefix("Bearer ").strip())
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    order = _this_purchase(login["uid"], session, brand)
    if not order:
        return {"found": False}
    return {
        "found": True,
        "brand": order.get("brandName"),
        "vouchers": [
            {"code": v.get("cardNumber"), "pin": v.get("cardPin"), "amount": v.get("amount"), "valid_till": v.get("validTill")}
            for v in order.get("vouchers") or []
        ],
    }


class LoginRequest(BaseModel):
    id_token: str
    # Where this visit came from (see SessionRequest), kept on the buyer's
    # record the first time we see them.
    referrer_domain: str | None = None
    landing_page: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    # The visit's own tag (see SessionRequest), so the login joins the visit.
    dealo_id: str | None = None
    visit_id: str | None = None


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    """Right after the SMS code, from either login (Your account or the buy
    flow): notes the number as a buyer and says whether we already know
    their name. Phone first, like the big apps: only new numbers are asked
    for a name (then POST /hubble/account)."""
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    known = await buyer_service.buyer_profile(login["uid"])
    await buyer_service.save_buyer(login["uid"], login["phone"], None, None, False)
    await buyer_service.note_first_source(login["uid"], _visit_source(body))
    buyer_service.report_buyer_seen(login["uid"], "login", get_settings().HUBBLE_ENV, _visit_source(body),
                                    dealo_id=body.dealo_id, visit_id=body.visit_id)
    name = (known.get("name") or "").strip()
    return {"name": name or None, "email": known.get("email") or None, "new": not name}


class AccountRequest(BaseModel):
    id_token: str
    name: str
    email: str | None = None


@router.post("/account")
async def account(body: AccountRequest) -> dict:
    """Logging in from "Your account" without buying anything: keeps the
    shopper's name (and email, if given) against their number, the same row
    a purchase would create. Firebase gives a number the same login on every
    browser, so /me then shows purchases made anywhere."""
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    name = body.name.strip()[:80] or None
    email = (body.email or "").strip()[:120] or None
    await buyer_service.save_buyer(login["uid"], login["phone"], name, email, False)
    return {"ok": True}


class HeardFromRequest(BaseModel):
    id_token: str
    choice: str


@router.post("/heard-from")
async def heard_from(body: HeardFromRequest) -> dict:
    """The buyer's one-tap answer to "How did you hear about Dealo?" on the
    voucher-ready screen. The only way word of mouth ever gets recorded."""
    if body.choice not in buyer_service.HEARD_FROM_CHOICES:
        raise HTTPException(422, "unknown choice")
    try:
        login = await buyer_service.verify_login(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"ok": await buyer_service.save_heard_from(login["uid"], body.choice)}


@router.get("/me")
async def me(authorization: str = Header(default="")) -> dict:
    try:
        login = await buyer_service.verify_login(authorization.removeprefix("Bearer ").strip())
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    try:
        rows = await buyer_service.purchases_for(login["uid"], get_settings().HUBBLE_ENV)
    except Exception as exc:  # noqa: BLE001 — say "couldn't load", never "you bought nothing"
        raise HTTPException(503, "Couldn't load your purchases") from exc
    purchases = [
        {
            "brand": r.get("brand"),
            "amount": float(r["amount"]) if r.get("amount") is not None else None,
            "saved": float(r["discount"]) if r.get("discount") is not None else 0.0,
            "at": r.get("created_at"),
            # Opens this card's code on Hubble (GET /hubble/card).
            "ref": r.get("hubble_ref"),
        }
        for r in rows
    ]
    return {
        "phone": login["phone"],
        "total_saved": round(sum(p["saved"] for p in purchases), 2),
        "total_bought": round(sum(p["amount"] or 0 for p in purchases), 2),
        "purchases": purchases,
    }


@router.get("/card")
async def card(ref: str | None = Query(default=None), authorization: str = Header(default="")) -> dict:
    """The link to one of the shopper's gift cards on Hubble (code + PIN),
    or to all of them without `ref`: how codes reach every phone and laptop
    without Dealo keeping them. The login token makes Hubble show only this
    shopper's own cards."""
    try:
        login = await buyer_service.verify_login(authorization.removeprefix("Bearer ").strip())
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    token = hubble_service.sso_token(login["uid"], login["phone"], None, None)
    return {"url": hubble_service.card_url(token, ref)}
