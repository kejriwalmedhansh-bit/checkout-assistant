"""Who is buying: checking a shopper's Firebase phone login, and keeping
Dealo's own list of buyers in Supabase (db/supabase_schema.sql).

The website logs the shopper in with Firebase (SMS code) and sends us the
ID token Firebase gave it. We check that token ourselves against Google's
published keys, so a made-up phone number can never reach Hubble.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone

import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate

from ..config import get_settings
from . import analytics_service

_GOOGLE_CERTS = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_certs: dict[str, str] = {}
_certs_expire_at = 0.0


async def _google_certs() -> dict[str, str]:
    global _certs, _certs_expire_at
    if _certs and time.time() < _certs_expire_at:
        return _certs
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_GOOGLE_CERTS)
        resp.raise_for_status()
    max_age = 3600
    for part in resp.headers.get("cache-control", "").split(","):
        if part.strip().startswith("max-age="):
            max_age = int(part.strip()[8:])
    _certs, _certs_expire_at = resp.json(), time.time() + max_age
    return _certs


async def verify_login(id_token: str) -> dict:
    """The checked login: {"uid", "phone"}. Raises ValueError if the token
    is fake, expired, from another Firebase project, or has no phone."""
    project = get_settings().FIREBASE_PROJECT_ID
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
        cert = (await _google_certs()).get(kid)
        if not cert:
            raise ValueError("unknown signing key")
        public_key = load_pem_x509_certificate(cert.encode()).public_key()
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=project,
            issuer=f"https://securetoken.google.com/{project}",
            # A minute of slack for clock differences between machines.
            leeway=60,
        )
    except jwt.PyJWTError as exc:
        print(f"[buyers] login rejected: {exc}")
        raise ValueError(f"login not valid: {exc}") from exc
    phone = claims.get("phone_number")
    if not claims.get("sub") or not phone:
        raise ValueError("login has no phone number")
    return {"uid": claims["sub"], "phone": phone}


def _headers() -> dict[str, str]:
    key = get_settings().SUPABASE_SECRET_KEY
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def save_buyer(uid: str, phone: str, name: str | None, email: str | None, marketing_optin: bool) -> None:
    """Add or update the buyer. Never fails the purchase: if Supabase is
    down, the shopper still gets their voucher and we lose one row."""
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return
    now = datetime.now(timezone.utc).isoformat()
    row = {"firebase_uid": uid, "phone": phone, "last_login_at": now}
    if name:
        row["name"] = name
    if email:
        row["email"] = email
    if marketing_optin:
        # Only ever switched on here, with the time they ticked the box.
        # Switching it off is its own request, so an untouched box on a later
        # purchase can't quietly withdraw consent given earlier.
        row["marketing_optin"] = True
        row["marketing_optin_at"] = now
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{s.SUPABASE_URL}/rest/v1/buyers?on_conflict=firebase_uid",
                headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=row,
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not save buyer {uid}: {exc}")


_SOURCE_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "referrer_domain", "landing_page")

# The one-tap answers to "How did you hear about Dealo?" (BuyFlow.jsx).
HEARD_FROM_CHOICES = ("google", "chatgpt", "instagram", "friend", "other")


def _source_columns(source: dict | None, prefix: str = "") -> dict:
    """The visit's source as database columns, blanks left out."""
    return {f"{prefix}{k}": v for k in _SOURCE_FIELDS if (v := _short((source or {}).get(k)))}


async def note_first_source(uid: str, source: dict | None) -> None:
    """Where the buyer came from the first time we saw them: written once,
    never overwritten, so a buyer who first arrived from Instagram stays
    "Instagram" however they come back. Never fails the login or purchase."""
    s = get_settings()
    columns = _source_columns(source, "first_")
    if not columns or not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return
    columns["first_source_at"] = datetime.now(timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{s.SUPABASE_URL}/rest/v1/buyers",
                headers={**_headers(), "Prefer": "return=minimal"},
                # Only a row with no source yet.
                params={"firebase_uid": f"eq.{uid}", "first_source_at": "is.null"},
                json=columns,
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not note source for {uid}: {exc}")


async def should_ask_heard_from(uid: str) -> bool:
    """True when the buyer has not yet said how they heard about Dealo.
    False when we can't tell (Supabase off or down): never ask twice."""
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return False
    params = {"select": "heard_from", "firebase_uid": f"eq.{uid}", "limit": "1"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{s.SUPABASE_URL}/rest/v1/buyers", headers=_headers(), params=params)
            resp.raise_for_status()
            rows = resp.json()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not read heard_from for {uid}: {exc}")
        return False
    return bool(rows) and not rows[0].get("heard_from")


async def save_heard_from(uid: str, choice: str) -> bool:
    s = get_settings()
    if choice not in HEARD_FROM_CHOICES or not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{s.SUPABASE_URL}/rest/v1/buyers",
                headers={**_headers(), "Prefer": "return=minimal"},
                params={"firebase_uid": f"eq.{uid}"},
                json={"heard_from": choice, "heard_from_at": datetime.now(timezone.utc).isoformat()},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not save heard_from for {uid}: {exc}")
        return False
    return True


async def buyer_profile(uid: str) -> dict:
    """The name and email we already have for this login, so a returning
    shopper is never asked again. Empty when Supabase is off or down: the
    worst case is asking for a name we had."""
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return {}
    params = {"select": "name,email", "firebase_uid": f"eq.{uid}", "limit": "1"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{s.SUPABASE_URL}/rest/v1/buyers", headers=_headers(), params=params)
            resp.raise_for_status()
            rows = resp.json()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not read buyer {uid}: {exc}")
        return {}
    return rows[0] if rows else {}


_DEALO_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


async def purchases_for(uid: str, environment: str) -> list[dict]:
    """The shopper's own finished Hubble orders, newest first, for their
    "Your account" screen. Never includes codes (they are never stored);
    hubble_ref opens the code on Hubble's own page."""
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return []
    params = {
        "select": "brand,amount,discount,created_at,hubble_ref",
        "firebase_uid": f"eq.{uid}",
        "environment": f"eq.{environment}",
        "status": "eq.COMPLETED",
        "order": "created_at.desc",
        "limit": "200",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{s.SUPABASE_URL}/rest/v1/purchases", headers=_headers(), params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not read purchases: {exc}")
        raise


def _short(value: object) -> str | None:
    """A visit-source value from the browser, cut to a sane length: it is
    typed by nobody but still arrives from outside, so it is never trusted
    to be short."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:120]


def voucher_sold_event(order: dict, environment: str, attribution: dict | None = None) -> dict | None:
    """The Mixpanel event for one completed Hubble order, built from its
    webhook. This is the number the business runs on: vouchers actually
    bought through Dealo. Carries no codes, PINs or phone numbers; the buyer
    is a one-way hash of their login id, enough to count distinct buyers and
    nothing more. The insert id is fixed per order, so a webhook Hubble
    retries does not count the sale twice. `attribution` (noted when the
    payment screen opened) joins the sale to the visit and to the link that
    brought the shopper, when known."""
    ref = order.get("transactionReferenceId")
    if not ref or order.get("orderStatus") != "COMPLETED":
        return None
    try:
        amount = float(order["amount"]) if order.get("amount") is not None else None
        discount = float(order["discountAmount"]) if order.get("discountAmount") is not None else None
    except (TypeError, ValueError):
        amount, discount = None, None
    pct = round(discount / amount * 100, 2) if amount and discount is not None else None
    uid = order.get("userId")
    attribution = attribution or {}
    dealo_id = attribution.get("dealo_id")
    if dealo_id and not _DEALO_ID.match(str(dealo_id)):
        dealo_id = None
    return analytics_service.build_event(
        "Voucher Sold",
        surface="web",
        device_id=dealo_id,
        insert_id=hashlib.sha256(f"hubble:{ref}".encode()).hexdigest()[:32],
        properties={
            "seller": "hubble",
            "brand": order.get("brandName"),
            "merchant": attribution.get("merchant") or order.get("brandName"),
            "amount": amount,
            "discount": discount,
            "discount_pct": pct,
            "src": attribution.get("src"),
            "placement": attribution.get("placement"),
            "referrer_domain": _short(attribution.get("referrer_domain")),
            "landing_page": _short(attribution.get("landing_page")),
            "utm_source": _short(attribution.get("utm_source")),
            "utm_medium": _short(attribution.get("utm_medium")),
            "utm_campaign": _short(attribution.get("utm_campaign")),
            "seller_environment": environment,
            "buyer_key": hashlib.sha256(str(uid).encode()).hexdigest()[:16] if uid else None,
        },
    )


async def save_purchase(order: dict, environment: str, attribution: dict | None = None) -> bool:
    """One row per Hubble order, from its webhook. Never stores codes or PINs.
    A completed order also goes to Mixpanel as 'Voucher Sold' (a resent order
    carries the same $insert_id, so Mixpanel keeps one). False when the row
    didn't save, so the webhook can ask Hubble to send it again."""
    try:
        event = voucher_sold_event(order, environment, attribution)
        if event:
            analytics_service.fire(event)
    except Exception as exc:  # noqa: BLE001 — analytics must never fail the purchase
        print(f"[buyers] could not report sale {order.get('transactionReferenceId')}: {exc}")
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return True
    row = {
        "hubble_ref": order.get("transactionReferenceId"),
        "firebase_uid": order.get("userId"),
        "brand": order.get("brandName"),
        "amount": order.get("amount"),
        "discount": order.get("discountAmount"),
        "status": order.get("orderStatus"),
        "environment": environment,
    }
    # Where the visit that made this purchase came from, beside the sale
    # itself. Left off when unknown (a resent webhook after a restart), so a
    # resend never blanks a source saved the first time.
    source = _source_columns(attribution)
    url = f"{s.SUPABASE_URL}/rest/v1/purchases?on_conflict=hubble_ref"
    headers = {**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json={**row, **source})
            if resp.status_code == 400 and source:
                # The source columns are not in the database yet: the sale
                # itself must still save.
                print(f"[buyers] purchase {row['hubble_ref']} saved without its source: {resp.text[:200]}")
                resp = await client.post(url, headers=headers, json=row)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not save purchase {row['hubble_ref']}: {exc}")
        return False
    return True
