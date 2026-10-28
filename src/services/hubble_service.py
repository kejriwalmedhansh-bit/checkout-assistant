"""Buying a voucher inside Dealo through Hubble's SDK.

Hubble runs the store and takes the payment; Dealo only decides which brand
and how much, and tells Hubble who the shopper is. Three jobs live here:

- offer_for(): does Hubble sell this shop's voucher, how should the order be
  split into vouchers, and what does the shopper pay. Prices and amount
  rules are read live from Hubble (cached briefly), so the figure Dealo shows
  is the one Hubble's payment screen charges.
- store_url(): the link that opens Hubble's store straight on the payment
  step with the amounts filled in (docs.myhubble.money/sdk/features/deep-links).
- sso_token(): the 60-second signed pass that tells Hubble who is buying
  (JWT SSO, docs.myhubble.money/sdk/authentication/sso-setup).
"""
from __future__ import annotations

import json
import math
import re
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt

from ..config import get_settings
from ..repositories._brand_matching import _strip_generic_suffix_words, normalize

_DATA = Path(__file__).resolve().parents[2] / "data"
_ALIASES = _DATA / "hubble_aliases.json"
# Hubble titles ending like "Hugo Boss-Luxe Gift Card" are the shop's own
# voucher under Gyftr's "Luxe" label; the shop is "Hugo Boss".
_LUXE_SUFFIX = re.compile(r"[\s-]*luxe\s+(gift|brand)\s+card$", re.IGNORECASE)
_TLD = re.compile(r"\.(com|in|co\.in|net|org|co)(/.*)?$")

def _catalogue_path() -> Path:
    """Production and staging are different stores with different brand ids
    (scripts/build_hubble_catalogue.py writes one file per environment)."""
    env = get_settings().HUBBLE_ENV
    return _DATA / ("hubble_catalogue.json" if env == "production" else "hubble_catalogue.staging.json")


@lru_cache(maxsize=2)
def _catalogue(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Hubble vouchers by exact title key, and by the shop name hidden in a
    "-Luxe Gift Card" title (only when no plain title already has that
    key: "Nykaa LUXE" must never answer for "Nykaa")."""
    exact: dict[str, list[dict]] = {}
    luxe: dict[str, list[dict]] = {}
    brands = json.loads(path.read_text())
    for b in brands:
        exact.setdefault(normalize(b["name"]), []).append(b)
    for b in brands:
        bare = _LUXE_SUFFIX.sub("", b["name"])
        if bare != b["name"] and normalize(bare) not in exact:
            luxe.setdefault(normalize(bare), []).append(b)
    return exact, luxe


@lru_cache(maxsize=1)
def _aliases() -> dict[str, list[str]]:
    return {k: v for k, v in json.loads(_ALIASES.read_text()).items() if not k.startswith("_")}


def shop_key(merchant: str) -> str:
    """The shop behind a results-page name: "Amazon.in", "AJIO.com",
    "Hamleys India", "Westside (in-store)" all become amazon / ajio /
    hamleys / westside."""
    name = re.sub(r"\s*\(in-store\)\s*$", "", merchant or "", flags=re.IGNORECASE).strip().lower()
    name = re.sub(r"^(https?://)?(www\.)?", "", name)
    name = _TLD.sub("", name)
    return normalize(_strip_generic_suffix_words(name))


def brand_for(merchant: str, in_store: bool = False) -> dict | None:
    """The one Hubble voucher for this shop that works where the shopper
    pays: online orders get an online voucher, in-store orders an in-store
    one. A near-miss or a guess would sell a voucher for the wrong shop, so
    only three things count: the exact title, a hand-checked alias
    (data/hubble_aliases.json), or a "-Luxe Gift Card" title for the same
    shop. Two candidates with no way to tell them apart means neither."""
    want = "OFFLINE" if in_store else "ONLINE"
    key = shop_key(merchant)
    if not key:
        return None
    exact, luxe = _catalogue(_catalogue_path())
    names = _aliases().get(key)
    if names:
        pool = [b for n in names for b in exact.get(normalize(n), [])]
    else:
        pool = exact.get(key) or luxe.get(key) or []
    fits = [b for b in pool if want in b["works"]]
    return fits[0] if len(fits) == 1 else None


async def _product(brand_id: str) -> dict | None:
    hit = _products.get(brand_id)
    if hit and time.time() - hit[0] < _PRODUCT_TTL_SECONDS:
        return hit[1]
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{API_HOST[s.HUBBLE_ENV]}/v1/store/products/voucher-product/{brand_id}",
                headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[hubble] product {brand_id} unavailable: {exc}")
        return None
    product = resp.json()
    _products[brand_id] = (time.time(), product)
    return product


def _discount_pct(product: dict) -> float:
    """The shopper's discount. Cashback-style rewards don't count: Dealo only
    shows money off what is paid today."""
    for reward in product.get("rewardDetails") or []:
        if "CASHBACK" in (reward.get("rewardType") or "").upper():
            return 0.0
        return float(reward.get("discountPercentage") or 0)
    return 0.0


def _one_order(product: dict, amount: int, order_max: int) -> list[tuple[int, int]]:
    """The vouchers one Hubble order can hold towards `amount`, never more
    than it: [(value, count), ...], empty if nothing fits.

    Rules as Hubble's staging store applies them (tested 23 Oct): a brand
    with a list of card values sells only those values, several cards per
    order; any other brand sells ONE typed amount per order (AJIO ₹12,000
    shows "0% off" and a dead button). Hubble quietly swaps an amount it
    doesn't allow for its smallest card, so nothing outside these rules may
    ever reach it."""
    rules = product.get("amountConditions") or {}
    limits = product.get("restrictions") or {}
    target = min(amount, order_max)
    cards = sorted({int(d["amount"] if isinstance(d, dict) else d) for d in rules.get("denominations") or []}, reverse=True)

    if not cards:
        step = max(1, int(rules.get("stepAmount") or 1))
        one = target - target % step
        return [(one, 1)] if one >= int(rules.get("minAmount") or 1) else []

    max_cards = 1 if product.get("isOneVoucherOneDenominationOnly") else int(limits.get("maxNumberOfVouchersPerOrder") or 1)
    per_value = int(rules.get("maxNoOfVouchersPerDenomination") or max_cards)
    max_values = rules.get("maxNoOfDenominationsPerOrder")
    if (product.get("voucherProductProviderMetadata") or {}).get("onlySingleDenominationAllowed"):
        max_values = 1

    if max_values == 1:
        # Every card the same value: pick the value that covers the most.
        best = max(((c, min(target // c, max_cards, per_value)) for c in cards), key=lambda p: p[0] * p[1])
        return [best] if best[1] else []
    parts, left, count = [], target, 0
    for c in cards:
        n = min(left // c, max_cards - count, per_value)
        if n > 0:
            parts.append((c, n))
            left -= c * n
            count += n
        if max_values and len(parts) == max_values:
            break
    return parts


def _orders(product: dict, price: float, pct: float) -> list[list[tuple[int, int]]] | None:
    """Up to HUBBLE_MAX_ORDERS Hubble orders covering as much of `price` as
    the brand allows; the rest is paid at the shop as usual (Zepto ₹3,450 →
    ₹3,000 in cards + ₹450; AJIO ₹25,000 → one ₹10,000 voucher + ₹15,000).
    The results page shows Hubble only when that total beats today's best."""
    s = get_settings()
    rules = product.get("amountConditions") or {}
    limits = product.get("restrictions") or {}
    order_max = int(rules.get("maxAmount") or price)
    # Hubble refuses a payment above the cap, so cap the voucher value too.
    order_max = min(order_max, math.floor(s.HUBBLE_PAY_CAP / (1 - pct / 100)))
    # A monthly limit bounds what Dealo can ask for in one go; what the
    # shopper already bought this month isn't known here.
    month_worth = limits.get("maxWorthOfVouchersInAMonth") or math.inf
    month_cards = limits.get("maxNumberOfVouchersInAMonth") or math.inf

    orders, left = [], int(price)
    while True:
        parts = _one_order(product, left, int(min(order_max, month_worth)))
        cards = sum(n for _, n in parts)
        if not parts or len(orders) == s.HUBBLE_MAX_ORDERS or cards > month_cards:
            break
        orders.append(parts)
        worth = sum(a * n for a, n in parts)
        left -= worth
        month_worth -= worth
        month_cards -= cards
    return orders or None


async def offer_for(merchant: str, price: float, in_store: bool = False) -> dict | None:
    s = get_settings()
    if not s.HUBBLE_ENABLED or price <= 0:
        return None
    brand = brand_for(merchant, in_store)
    if not brand:
        return None
    product = await _product(brand["id"])
    if not product or product.get("status") != "ACTIVE":
        return None
    pct = _discount_pct(product)
    orders = _orders(product, price, pct) if pct > 0 else None
    if not orders:
        return None
    worths = [sum(a * c for a, c in parts) for parts in orders]
    voucher_total = sum(worths)
    you_save = round(voucher_total * pct / 100, 2)
    return {
        "brand_id": brand["id"],
        "brand_name": brand["name"],
        # The first (usually only) order; store_url() opens this one.
        "denominations": [{"amount": a, "count": c} for a, c in orders[0]],
        "orders": [
            {"denominations": [{"amount": a, "count": c} for a, c in parts], "worth": w,
             "you_pay": round(w * (1 - pct / 100), 2)}
            for parts, w in zip(orders, worths)
        ],
        "voucher_total": voucher_total,
        "discount_pct": pct,
        "you_pay": round(voucher_total - you_save, 2),
        "you_save": you_save,
        "rest_at_shop": max(0, int(price) - voucher_total),
        "in_store": in_store,
        "add_voucher_url": brand.get("add_voucher_url"),
    }


def _private_key() -> str:
    s = get_settings()
    if s.HUBBLE_PRIVATE_KEY:
        return s.HUBBLE_PRIVATE_KEY.replace("\\n", "\n")
    return Path(s.HUBBLE_PRIVATE_KEY_FILE).expanduser().read_text()


def sso_token(user_id: str, phone: str, name: str | None, email: str | None) -> str:
    """Hubble wants the phone as 10 digits, no country code, and a fresh
    token every time (never cached): it expires 60 seconds after issue."""
    s = get_settings()
    now = int(time.time())
    claims = {
        "sub": user_id,
        "iss": s.HUBBLE_CLIENT_ID,
        "iat": now,
        "exp": now + 60,
        "phoneNumber": re.sub(r"\D", "", phone)[-10:],
    }
    if name:
        claims["name"] = name
    if email:
        claims["email"] = email
    return jwt.encode(claims, _private_key(), algorithm="RS256")


def store_url(offer: dict, token: str, order: int = 0) -> str:
    """Opens Hubble on the payment step for one of the offer's orders."""
    s = get_settings()
    picked = offer["orders"][order]
    params = {
        "clientId": s.HUBBLE_CLIENT_ID,
        "appSecret": s.HUBBLE_APP_SECRET,
        "token": token,
        "wrap-plt": "web",
        "amount": picked["worth"],
        "skipToPayment": "true",
        "showBackButton": "true",
        "exitOnBack": "true",
    }
    if len(picked["denominations"]) > 1 or picked["denominations"][0]["count"] > 1:
        params["denominations"] = ",".join(
            f"{d['amount']}x{d['count']}" for d in picked["denominations"]
        )
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}/buy/{offer['brand_id']}?{urlencode(params)}"


def home_url(token: str) -> str:
    """Hubble's store home screen (staging test page only)."""
    s = get_settings()
    params = {"clientId": s.HUBBLE_CLIENT_ID, "appSecret": s.HUBBLE_APP_SECRET, "token": token, "wrap-plt": "web"}
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}/?{urlencode(params)}"
