"""Who is buying: checking a shopper's Firebase phone login, and keeping
Dealo's own list of buyers in Supabase (db/supabase_schema.sql).

The website logs the shopper in with Firebase (SMS code) and sends us the
ID token Firebase gave it. We check that token ourselves against Google's
published keys, so a made-up phone number can never reach Hubble.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate

from ..config import get_settings

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
        )
    except jwt.PyJWTError as exc:
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


async def save_purchase(order: dict, environment: str) -> None:
    """One row per Hubble order, from its webhook. Never stores codes or PINs."""
    s = get_settings()
    if not s.SUPABASE_URL or not s.SUPABASE_SECRET_KEY:
        return
    row = {
        "hubble_ref": order.get("transactionReferenceId"),
        "firebase_uid": order.get("userId"),
        "brand": order.get("brandName"),
        "amount": order.get("amount"),
        "discount": order.get("discountAmount"),
        "status": order.get("orderStatus"),
        "environment": environment,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{s.SUPABASE_URL}/rest/v1/purchases?on_conflict=hubble_ref",
                headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=row,
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[buyers] could not save purchase {row['hubble_ref']}: {exc}")
