"""Cuelinks publisher API — live campaign status and payout rates.

Added 2026-08-31 so the affiliate-network coverage list (which merchant
should route through Cuelinks vs. INRDeals) can be refreshed by calling
Cuelinks directly, instead of relying on a one-off manual check. This module
only reads campaign data; it never touches click/link generation, which
stays exactly as-is in constants.CUELINKS_BASE / redirect.py.

Same never-raises contract as the other repositories (crawlbase_repository,
searchapi_repository): any failure returns an empty list/None so a refresh
run can log a clear error and keep whatever coverage data it already has,
rather than crash or silently wipe it.

Note: developers.cuelinks.com is behind Cloudflare and returns HTTP 403
("error code: 1010") to requests without a browser-like User-Agent — the
default httpx/urllib UA gets blocked even with a valid API key. Always send
_HEADERS below, not just the Authorization header.
"""
from __future__ import annotations

import logging

import httpx

from ..config import get_settings

logger = logging.getLogger("uvicorn.error")

CUELINKS_API_BASE = "https://developers.cuelinks.com/pub_api/v3"
INDIA_COUNTRY_ID = 252

_HEADERS_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Token {settings.CUELINKS_API_KEY}",
        "User-Agent": _HEADERS_UA,
        "Accept": "application/json",
    }


def fetch_all_india_campaigns(timeout: float = 30.0) -> list[dict]:
    """Returns every India campaign Cuelinks has (open, pending, not_applied,
    restricted, rejected — all access statuses), each as the raw dict the API
    returns (id, name, access_status, payout, payout_currency, epc_7d,
    epc_90d, ...). Empty list on any failure or if CUELINKS_API_KEY isn't set.

    Paginates internally (the API caps at 500/page) — callers get the full
    catalog in one call.
    """
    settings = get_settings()
    if not settings.CUELINKS_API_KEY:
        logger.info("[cuelinks] no CUELINKS_API_KEY configured — not run")
        return []

    campaigns: list[dict] = []
    page = 1
    try:
        with httpx.Client(timeout=timeout, headers=_headers()) as client:
            while True:
                resp = client.get(
                    f"{CUELINKS_API_BASE}/campaigns",
                    params={"country_id": INDIA_COUNTRY_ID, "per_page": 500, "page": page},
                )
                resp.raise_for_status()
                body = resp.json()
                batch = body.get("data") or body.get("campaigns") or []
                campaigns.extend(batch)
                meta = body.get("meta") or {}
                if not meta.get("next_page") or not batch:
                    break
                page = meta["next_page"]
    except httpx.HTTPError as exc:
        logger.info("[cuelinks] campaign fetch failed on page %d: %s: %s", page, type(exc).__name__, exc)
        return []

    logger.info("[cuelinks] fetched %d India campaigns across %d page(s)", len(campaigns), page)
    return campaigns
