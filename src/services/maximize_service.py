"""Buying a voucher inside Dealo through Maximize's frame (second seller).

Maximize's own screens run inside a frame on Dealo and take the payment
(Razorpay, their account); Dealo only decides which brand and tells Maximize
who the shopper is. Same three jobs as hubble_service, same offer shape, so
the website treats both sellers alike:

- offer_for() / brand_info(): does Maximize sell this shop's voucher, at
  what rate, and how would the order be split. Rates and amount rules are
  read live from Maximize (cached briefly). The rate Dealo quotes is the UPI
  rate, the one their frame offers by default and the one every other
  voucher on Dealo is compared at (CLAUDE.md rule 6).
- store_url(): the frame address that opens straight on this brand's card.
- user_token(): Maximize's own 7-day login for the shopper, created from
  the phone number Dealo has already verified (Firebase SMS code).

Guide: Google Doc "GETDEALO_SDK_INTEGRATION_GUIDE" + Bibrata's answers,
30 Oct 2026 (~/Downloads/GetDealO - Integration Questions.pdf).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from ..config import get_settings
from ..repositories._brand_matching import normalize
from .hubble_service import shop_key

API_HOST = {"sandbox": "https://merchant-sandbox.maximize.money"}
SDK_HOST = {
    # Plain http on a bare address: fine from a local http page, blocked
    # inside https://getdealo.in. Bibrata: no https sandbox frame yet.
    "sandbox": "http://98.130.140.6:3000",
    "production": "https://merchant-sdk.maximize.money",
}
_DATA = Path(__file__).resolve().parents[2] / "data"
_ALIASES = _DATA / "maximize_aliases.json"
_MASTER = _DATA / "maximize_master.json"
# Card titles carry the product type; the shop is the part before it.
_CARD_SUFFIX = re.compile(r"\s*(e[\s-]?gift[\s-]?card|gift[\s-]?card|gift[\s-]?voucher|e[\s-]?voucher|voucher|egc|egv)\s*$", re.IGNORECASE)
_CATALOGUE_TTL = 600
_DETAILS_TTL = 600
_TOKEN_TTL = 6 * 24 * 3600          # Maximize's login lasts 7 days; renew a day early
_SESSION_TTL = 2 * 3600              # how long a webhook may follow a session

_catalogue: tuple[float, list[dict]] | None = None
_details: dict[str, tuple[float, dict]] = {}
_tokens: dict[str, tuple[float, str]] = {}
# phone digits -> (opened_at, firebase uid): who may be behind an unsigned webhook
_sessions: dict[str, tuple[float, str]] = {}


def _api_host() -> str:
    s = get_settings()
    return s.MAXIMIZE_API_HOST or API_HOST.get(s.MAXIMIZE_ENV, API_HOST["sandbox"])


def _enabled() -> bool:
    s = get_settings()
    return bool(s.MAXIMIZE_ENABLED and s.MAXIMIZE_API_KEY and s.MAXIMIZE_API_SECRET
                and (s.MAXIMIZE_ENV != "production" or s.MAXIMIZE_API_HOST))


# ── login ────────────────────────────────────────────────────────────────────

async def _auth(mobile: str, name: str | None, email: str | None) -> str:
    """POST /api/v2/auth: Maximize's 7-day login for one phone number."""
    s = get_settings()
    body = {"fullName": (name or "Dealo shopper")[:80], "email": email or f"{mobile}@shoppers.getdealo.in", "mobile": mobile}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{_api_host()}/api/v2/auth",
            headers={"apiAccessKey": s.MAXIMIZE_API_KEY, "apiSecret": s.MAXIMIZE_API_SECRET},
            json=body,
        )
        resp.raise_for_status()
    return resp.json()["data"]["token"]


async def user_token(uid: str, phone: str, name: str | None, email: str | None) -> str:
    """The shopper's Maximize login, remembered for six days. Also notes that
    this phone opened a session, so their webhook can be trusted later."""
    mobile = re.sub(r"\D", "", phone)[-10:]
    _sessions[mobile] = (time.time(), uid)
    stamped = _tokens.get(mobile)
    if stamped and time.time() - stamped[0] < _TOKEN_TTL:
        return stamped[1]
    token = await _auth(mobile, name, email)
    _tokens[mobile] = (time.time(), token)
    return token


def session_owner(phone_digits: str) -> str | None:
    """Firebase uid of the shopper who opened a Maximize session from this
    phone in the last two hours, else None."""
    stamped = _sessions.get(re.sub(r"\D", "", phone_digits or "")[-10:])
    if not stamped or time.time() - stamped[0] > _SESSION_TTL:
        return None
    return stamped[1]


async def _service_token() -> str:
    s = get_settings()
    return await user_token("dealo-catalogue", s.MAXIMIZE_SERVICE_MOBILE, "Dealo Catalogue", "catalogue@getdealo.in")


# ── catalogue ────────────────────────────────────────────────────────────────

async def _get(path: str) -> dict | list | None:
    try:
        token = await _service_token()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{_api_host()}{path}", headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 401:          # login lapsed early: once more with a fresh one
                _tokens.pop(re.sub(r"\D", "", get_settings().MAXIMIZE_SERVICE_MOBILE)[-10:], None)
                token = await _service_token()
                resp = await client.get(f"{_api_host()}{path}", headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
        return resp.json().get("data")
    except httpx.HTTPError as exc:
        print(f"[maximize] {path} unavailable: {exc}")
        return None


async def catalogue() -> list[dict]:
    """Every card Maximize sells us: id, name, UPI rate, stock. Ten-minute cache."""
    global _catalogue
    if _catalogue and time.time() - _catalogue[0] < _CATALOGUE_TTL:
        return _catalogue[1]
    data = await _get("/api/v2/gift-cards-list")
    cards = data if isinstance(data, list) else []
    if cards or not _catalogue:
        _catalogue = (time.time(), cards)
    return _catalogue[1]


async def details(card_id: str) -> dict | None:
    stamped = _details.get(card_id)
    if stamped and time.time() - stamped[0] < _DETAILS_TTL:
        return stamped[1]
    data = await _get(f"/api/v2/gift-cards-details?giftCardId={card_id}")
    if isinstance(data, dict):
        _details[card_id] = (time.time(), data)
        return data
    return stamped[1] if stamped else None


def card_key(card_name: str) -> str:
    """"Nykaa Fashion E-Gift Card" -> nykaafashion, the same key shop_key()
    makes from a results-page shop name."""
    return shop_key(_CARD_SUFFIX.sub("", card_name or ""))


def _aliases() -> dict[str, list[str]]:
    if not _ALIASES.exists():
        return {}
    return {k: v for k, v in json.loads(_ALIASES.read_text()).items() if not k.startswith("_")}


def card_for(merchant: str, cards: list[dict]) -> dict | None:
    """The one Maximize card for this shop: exact key or a hand-checked
    alias. Two candidates with no way to tell them apart means neither
    (a wrong card sells a voucher for the wrong shop)."""
    key = shop_key(merchant)
    if not key:
        return None
    names = _aliases().get(key)
    if names:
        wanted = {normalize(n) for n in names}
        pool = [c for c in cards if normalize(c.get("giftCardName", "")) in wanted]
    else:
        pool = [c for c in cards if card_key(c.get("giftCardName", "")) == key]
    pool = [c for c in pool if c.get("stock", True)]
    # the same card can be listed twice (sandbox lists Domino's twice)
    ids = {c["id"] for c in pool}
    return pool[0] if len(ids) == 1 else None


# ── rate, where it works, amounts ───────────────────────────────────────────

def upi_pct(card: dict, info: dict | None) -> float:
    """The rate their frame offers by default (UPI, no surcharge)."""
    for m in (info or {}).get("paymentMethods") or []:
        if m.get("instrument") == "default" or (m.get("name") or "").upper() == "UPI":
            if not m.get("surcharge"):
                return float(m.get("discount") or 0)
    return float(card.get("discount") or 0)


def _master_works() -> dict[str, set[str]]:
    """Where Maximize's public listing says each brand's voucher works, from
    Dealo's own scrape (data/maximize_master.json): a fallback for cards
    whose details don't say."""
    out: dict[str, set[str]] = {}
    try:
        master = json.loads(_MASTER.read_text())
    except (OSError, ValueError):
        return out
    for rec in master.values():
        key = shop_key(rec.get("brand_name") or "")
        for p in rec.get("products") or []:
            kind = (p.get("redemption_type") or "").lower()
            s = out.setdefault(key, set())
            if "online" in kind or "both" in kind:
                s.add("ONLINE")
            if "store" in kind or "offline" in kind or "both" in kind:
                s.add("OFFLINE")
    return out


def works(card: dict, info: dict | None) -> set[str]:
    """{"ONLINE"}, {"OFFLINE"} or both. The card's own "Where to Redeem?"
    line first; Dealo's scrape of Maximize's public listing second; an
    empty set when neither says (then the card is not sold: a wrong kind of
    voucher is worse than none)."""
    for item in (info or {}).get("importantInfo") or []:
        if isinstance(item, dict) and "redeem" in (item.get("title") or "").lower():
            text = (item.get("subtext") or "").lower()
            found = set()
            if re.search(r"online|website|app\b", text):
                found.add("ONLINE")
            if re.search(r"store|offline|outlet|counter", text):
                found.add("OFFLINE")
            if found:
                return found
    return _master_works().get(card_key(card.get("giftCardName", "")), set())


def _master_stack() -> dict[str, int]:
    """How many of a brand's vouchers one bill accepts, from Dealo's own scrape
    of Maximize's public listing (stack_limit), by shop key."""
    out: dict[str, int] = {}
    try:
        master = json.loads(_MASTER.read_text())
    except (OSError, ValueError):
        return out
    for rec in master.values():
        key = shop_key(rec.get("brand_name") or "")
        for p in rec.get("products") or []:
            limit = p.get("stack_limit")
            if isinstance(limit, int) and limit > 0:
                out[key] = max(out.get(key, 0), limit)
    return out


def vouchers_per_bill(card: dict, info: dict) -> int:
    """How many vouchers Dealo may put in one order. Their frame allows up to
    maxAllowedQuantity, but a shop that will not club cards ("Multiple cards
    can't be clubbed", Domino's) makes every voucher after the first
    useless, so the card's own line wins, then Dealo's scrape, then one."""
    qty = int(info.get("maxAllowedQuantity") or 1)
    for item in info.get("importantInfo") or []:
        if isinstance(item, dict) and "clubbed" in (item.get("title") or "").lower() and "card" in (item.get("title") or "").lower():
            text = (item.get("subtext") or "").lower()
            if re.search(r"can\W*t|cannot|not be|single|one card|only one", text):
                return 1
            return qty
    known = _master_stack().get(card_key(card.get("giftCardName", "")))
    return min(qty, known) if known else 1


def _amounts(info: dict, qty: int = 1) -> tuple[list[int], int | None, int | None, int]:
    """(fixed cards, min, max, vouchers per order) as their frame enforces."""
    cards = sorted({int(float(x)) for x in str(info.get("fixedDenomination") or "").split(",") if x.strip()})
    if (info.get("denominationType") or "").lower() == "range":
        lo = int(info.get("minAmount") or (cards[0] if cards else 1))
        hi = int(info.get("maxAmount") or (cards[-1] if cards else 0)) or None
        return [], lo, hi, qty
    return cards, (cards[0] if cards else None), (cards[-1] if cards else None), qty


def _split(info: dict, price: float, pct: float, qty: int = 1) -> list[tuple[int, int]] | None:
    """One order: n vouchers of one amount (Maximize sells one denomination
    per order; n is what the shop will accept on one bill), worth as much of
    the bill as possible, never more than it and never above the pay cap.
    None when nothing fits."""
    cap = get_settings().MAXIMIZE_PAY_CAP
    cards, lo, hi, qty = _amounts(info, qty)
    budget = int(price)
    best: tuple[int, int] | None = None
    if cards:
        for amount in cards:
            n = min(qty, budget // amount) if amount else 0
            while n and n * amount * (1 - pct / 100) > cap:
                n -= 1
            if n and (best is None or n * amount > best[0] * best[1]):
                best = (amount, n)
    elif lo is not None:
        top = min(budget, hi or budget)
        n = 1
        if hi and budget > hi:
            n = min(qty, budget // hi)
            top = hi
        while n and n * top * (1 - pct / 100) > cap:
            n -= 1
        if n and top >= lo:
            best = (top, n)
    return [best] if best else None


def _offer(card: dict, info: dict, parts: list[tuple[int, int]], pct: float, price: float, in_store: bool) -> dict:
    worth = sum(a * c for a, c in parts)
    save = round(worth * pct / 100, 2)
    return {
        "seller": "maximize",
        "brand_id": card["id"],
        "brand_name": _CARD_SUFFIX.sub("", card.get("giftCardName", "")).strip(),
        # the card's full title: their deep link wants it word for word
        "card_name": card.get("giftCardName", ""),
        "denominations": [{"amount": a, "count": c} for a, c in parts],
        "orders": [{"denominations": [{"amount": a, "count": c} for a, c in parts], "worth": worth, "you_pay": round(worth - save, 2)}],
        "voucher_total": worth,
        "discount_pct": pct,
        "you_pay": round(worth - save, 2),
        "you_save": save,
        "rest_at_shop": max(0, int(price) - worth),
        "in_store": in_store,
        "add_voucher_url": None,
        # Their frame shows the amount picker itself; these figures are what
        # it will charge for this split at the UPI rate.
        "amount_in_frame": True,
    }


async def offer_for(merchant: str, price: float, in_store: bool = False) -> dict | None:
    if not _enabled() or price <= 0:
        return None
    card = card_for(merchant, await catalogue())
    if not card:
        return None
    info = await details(card["id"])
    if not info or not info.get("stockAvailability", True):
        return None
    if ("OFFLINE" if in_store else "ONLINE") not in works(card, info):
        return None
    pct = upi_pct(card, info)
    parts = _split(info, price, pct, vouchers_per_bill(card, info)) if pct > 0 else None
    if not parts:
        return None
    return _offer(card, info, parts, pct, price, in_store)


async def brand_info(merchant: str) -> dict | None:
    """Shop-name search (no cart yet): rate, where it works, amounts."""
    if not _enabled():
        return None
    card = card_for(merchant, await catalogue())
    if not card:
        return None
    info = await details(card["id"])
    if not info or not info.get("stockAvailability", True):
        return None
    where = works(card, info)
    if not where:
        return None
    pct = upi_pct(card, info)
    if pct <= 0:
        return None
    cards, lo, hi, _qty = _amounts(info)
    cap = get_settings().MAXIMIZE_PAY_CAP
    max_amount = hi
    if max_amount:
        max_amount = min(max_amount, int(cap / (1 - pct / 100)))
    return {
        "seller": "maximize",
        "brand_id": card["id"],
        "brand_name": _CARD_SUFFIX.sub("", card.get("giftCardName", "")).strip(),
        "discount_pct": pct,
        "works": sorted(where),
        "in_store": "ONLINE" not in where,
        "min_amount": lo or 1,
        "max_amount": max_amount,
        "cards": [c for c in cards if not max_amount or c <= max_amount],
        "typed": not cards,
    }


def store_url(offer: dict, token: str) -> str:
    """Their frame, opened on this brand's card (Bibrata, 30 Oct 2026).

    Opened at the frame's root, not /list: on /list their page first jumps
    to the card and then, once the deep link is cleared, jumps again to the
    full catalogue (seen 30 Oct, owner's test). The root page has no second
    jump, so the shopper lands on the card and stays there."""
    s = get_settings()
    host = SDK_HOST.get(s.MAXIMIZE_ENV, SDK_HOST["sandbox"])
    params = {"accessToken": token, "productId": offer["brand_id"], "productBrand": offer.get("card_name") or offer["brand_name"]}
    return f"{host}/?{urlencode(params)}"


def frame_hosts() -> list[str]:
    """Hostnames whose postMessage events the website may trust."""
    return ["merchant-sdk.maximize.money", "98.130.140.6"]
