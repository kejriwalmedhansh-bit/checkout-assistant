"""SearchApi.io data access (ported from v2/searchapi.py).

Two calls:
  - search_products(query)      -> google_shopping engine, returns a product list
  - get_product(product_token)  -> google_product engine, full details + offers

The API key now comes from settings (was hardcoded). Results are wrapped in the
in-memory 24h search cache to protect the SearchApi budget. On any HTTP or
transport error, returns {"error": "<message>"} so callers can surface an error
object instead of crashing.
"""
from __future__ import annotations

import httpx

from ..cache import search_cache
from ..config import get_settings
from ..constants import SEARCHAPI_BASE, SEARCHAPI_DEFAULTS


def _get(params: dict) -> dict:
    settings = get_settings()
    if not settings.SEARCHAPI_KEY:
        return {"error": "SEARCHAPI_KEY is not configured."}

    call_params = {**SEARCHAPI_DEFAULTS, **params, "api_key": settings.SEARCHAPI_KEY}

    # Cache key excludes the api_key (it's constant per-deploy anyway).
    cache_key = tuple(sorted((k, v) for k, v in params.items()))
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=float(settings.SEARCHAPI_TIMEOUT)) as client:
            resp = client.get(SEARCHAPI_BASE, params=call_params)
        if resp.status_code != 200:
            return {"error": f"SearchApi returned HTTP {resp.status_code}"}
        data = resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"Request failed: {exc}"}
    except ValueError as exc:  # JSON decode error
        return {"error": f"Bad response from SearchApi: {exc}"}

    # Only cache successful responses.
    if not data.get("error"):
        search_cache.set(cache_key, data)
    return data


def search_products(query: str) -> dict:
    """google_shopping search. Result products live under `shopping_results`."""
    return _get({"engine": "google_shopping", "q": query})


def get_product(product_token: str) -> dict:
    """google_product lookup. Returns `product`, `offers`, `specifications`, etc."""
    return _get({"engine": "google_product", "product_token": product_token})
