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

_CATALOGUE = Path(__file__).resolve().parents[2] / "data" / "hubble_catalogue.json"
SDK_HOST = {
    "staging": "https://sdk.dev.myhubble.money",
    "production": "https://sdk.myhubble.money",
}
API_HOST = {
    "staging": "https://api.dev.myhubble.money",
    "production": "https://api.myhubble.money",
}
# Hubble asks partners not to hold store data for long; ten minutes keeps a
# busy results page from calling them on every view.
_PRODUCT_TTL_SECONDS = 600
_products: dict[str, tuple[float, dict]] = {}


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


@lru_cache(maxsize=1)
def _brands_by_key() -> dict[str, list[dict]]:
    by_key: dict[str, list[dict]] = {}
    for b in json.loads(_CATALOGUE.read_text()):
        by_key.setdefault(_key(b["name"]), []).append(b)
    return by_key


def brand_for(merchant: str, in_store: bool = False) -> dict | None:
    """The one Hubble voucher for this shop that works where the shopper
    pays: online orders get an online voucher, in-store orders an in-store
    one. Exact name match only, and two candidates with no way to tell them
    apart means neither is used: a near-miss or a guess sends the shopper a
    voucher for the wrong shop or at a price Dealo didn't show."""
    want = "OFFLINE" if in_store else "ONLINE"
    fits = [b for b in _brands_by_key().get(_key(merchant), []) if want in b["works"]]
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


def _split(product: dict, price: float) -> list[tuple[int, int]] | None:
    """Vouchers covering as much of `price` as the brand allows, never more
    than the price. Returns [(amount, count), ...] or None if nothing fits."""
    rules = product.get("amountConditions") or {}
    limits = product.get("restrictions") or {}
    lo = int(rules.get("minAmount") or 1)
    hi = int(rules.get("maxAmount") or price)
    max_count = int(limits.get("maxNumberOfVouchersPerOrder") or 1)
    if product.get("isOneVoucherOneDenominationOnly"):
        max_count = 1
    per_denom = rules.get("maxNoOfVouchersPerDenomination")
    one_amount_only = rules.get("maxNoOfDenominationsPerOrder") == 1
    total = int(price)

    fixed = [int(d["amount"] if isinstance(d, dict) else d) for d in rules.get("denominations") or []]
    if fixed:
        remaining, count, parts = total, 0, []
        for denom in sorted(set(fixed), reverse=True):
            room = max_count - count
            if per_denom:
                room = min(room, int(per_denom))
            n = min(remaining // denom, room)
            if n > 0:
                parts.append((denom, n))
                remaining -= denom * n
                count += n
            if one_amount_only and parts:
                break
        return parts or None

    # Some brands only sell set steps (Domino's: multiples of ₹500).
    step = max(1, int(rules.get("stepAmount") or 1))

    def fit(amount: int) -> int:
        return amount - amount % step

    if total < lo:
        return None
    if total <= hi:
        one = fit(total)
        return [(one, 1)] if one >= lo else None
    cap = min(max_count, int(per_denom)) if per_denom else max_count
    hi = fit(hi)
    if one_amount_only:
        # Same amount every time: n equal vouchers just under the price.
        n = min(math.ceil(total / hi), cap)
        each = fit(min(hi, total // n))
        return [(each, n)] if each >= lo else None
    full, rest = divmod(total, hi)
    full = min(full, cap)
    parts = [(hi, full)]
    rest = fit(rest)
    if rest >= lo and full < cap:
        parts.append((rest, 1))
    return parts


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
    parts = _split(product, price)
    if pct <= 0 or not parts:
        return None
    voucher_total = sum(a * c for a, c in parts)
    you_save = round(voucher_total * pct / 100, 2)
    return {
        "brand_id": brand["id"],
        "brand_name": brand["name"],
        "denominations": [{"amount": a, "count": c} for a, c in parts],
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


def store_url(offer: dict, token: str) -> str:
    s = get_settings()
    params = {
        "clientId": s.HUBBLE_CLIENT_ID,
        "appSecret": s.HUBBLE_APP_SECRET,
        "token": token,
        "wrap-plt": "web",
        "amount": offer["voucher_total"],
        "skipToPayment": "true",
        "showBackButton": "true",
        "exitOnBack": "true",
    }
    if len(offer["denominations"]) > 1 or offer["denominations"][0]["count"] > 1:
        params["denominations"] = ",".join(
            f"{d['amount']}x{d['count']}" for d in offer["denominations"]
        )
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}/buy/{offer['brand_id']}?{urlencode(params)}"
