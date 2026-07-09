"""
v2/searchapi.py — thin SearchApi.io client for the V2 product explorer.

Two calls:
  - search_products(query)      -> google_shopping engine, returns a product list
  - get_product(product_token)  -> google_product engine, returns full details + offers

Isolated from the rest of the app (pipeline/vouchers untouched). On any HTTP or
transport error, returns {"error": "<message>"} so templates can render an error
box instead of crashing.

NOTE: the API key is hardcoded here per an explicit product decision. It is kept as
a single named constant so it can be moved to os.getenv("SEARCHAPI_KEY") later with
a one-line change.
"""

import httpx

SEARCHAPI_KEY = "Ru8vffATm8TcScJUM3vtoBjj"
BASE = "https://www.searchapi.io/api/v1/search"

# google_product is slow (~13s observed), so keep a generous timeout.
_TIMEOUT = 30.0


def _get(params: dict) -> dict:
    params = {**params, "gl": "in", "hl": "en", "api_key": SEARCHAPI_KEY}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(BASE, params=params)
        if resp.status_code != 200:
            return {"error": f"SearchApi returned HTTP {resp.status_code}"}
        return resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"Request failed: {exc}"}
    except ValueError as exc:  # JSON decode error
        return {"error": f"Bad response from SearchApi: {exc}"}


def search_products(query: str) -> dict:
    """google_shopping search. Result products live under `shopping_results`."""
    return _get({"engine": "google_shopping", "q": query})


def get_product(product_token: str) -> dict:
    """google_product lookup. Returns `product`, `offers`, `specifications`, etc."""
    return _get({"engine": "google_product", "product_token": product_token})
