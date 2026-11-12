"""Shopify product reader — a shop's own clean product data instead of its page.

Every Shopify shop publishes each product as plain data at
`/products/<handle>.json`: the exact name, the brand ("vendor"), every
size/colour with its own price and stock, and the photos. Reading that is
faster and more exact than reading the rendered page and guessing.

87 of the 350 shop websites Dealo knows run on Shopify
(data/shopify_shops.json, checked 2026-11-12: each one's /products.json read
back through Context.dev). Shopify answers a server's plain request with 429
for most of them (boAt, Snitch: bot protection, not a rate limit), so we try
one quick plain request and then Context.dev, which gets through.

Never raises: any failure returns None and the caller falls back to today's
page read.
"""
from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import parse_qs, quote_plus, urlsplit

import httpx

from ..constants import DATA_DIR
from . import context_dev_repository

logger = logging.getLogger(__name__)

_SHOPS_PATH = DATA_DIR / "shopify_shops.json"
_shops: dict[str, str] | None = None

# /products/<handle>, also when nested under a collection
# (/collections/sale/products/<handle>). Handles are lowercase words and dashes.
_HANDLE_RE = re.compile(r"/products/([a-z0-9][a-z0-9\-_.%]*?)(?:\.json|\.js)?/?$", re.IGNORECASE)

_PLAIN_TIMEOUT = 5.0
_PLAIN_HEADERS = {"User-Agent": "DealoShopReader/1.0 (+https://getdealo.in)", "Accept": "application/json"}


def _load() -> dict[str, str]:
    global _shops
    if _shops is None:
        try:
            with open(_SHOPS_PATH) as f:
                _shops = json.load(f)
        except (OSError, ValueError):
            logger.warning("[shopify] could not load %s", _SHOPS_PATH)
            _shops = {}
    return _shops


def _bare(host: str) -> str:
    host = (host or "").strip().lower()
    return host[4:] if host.startswith("www.") else host


def is_shopify_host(host: str) -> bool:
    return _bare(host) in _load()


def product_handle(url: str) -> str | None:
    """The product's handle when `url` is a Shopify product page, else None."""
    m = _HANDLE_RE.search(urlsplit(url).path or "")
    return m.group(1) if m else None


def _parse_product(text: str) -> dict | None:
    """The `product` object out of a .json body, or out of Context.dev's HTML
    wrapping of it (the JSON shows as page text, HTML-escaped)."""
    text = (text or "").strip()
    if not text.startswith("{"):
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    start = text.find('{"product"')
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    product = data.get("product") if isinstance(data, dict) else None
    return product if isinstance(product, dict) and product.get("title") else None


def _pick_variant(product: dict, variant_id: str | None) -> dict | None:
    variants = [v for v in product.get("variants") or [] if isinstance(v, dict)]
    if not variants:
        return None
    if variant_id:
        for v in variants:
            if str(v.get("id")) == variant_id:
                return v
    # Shopify's product JSON has no stock flag, so the pasted (or first)
    # variant stands in for the product, as the product page itself does.
    return variants[0]


def _price(variant: dict | None) -> float | None:
    try:
        value = float((variant or {}).get("price"))
    except (TypeError, ValueError):
        return None
    # Below ₹10 is a placeholder (a free gift bag priced ₹0.01), not a price.
    return value if value >= 10 else None


def _image(product: dict, variant: dict | None) -> str | None:
    images = [i for i in product.get("images") or [] if isinstance(i, dict)]
    image_id = (variant or {}).get("image_id")
    if image_id:
        for i in images:
            if i.get("id") == image_id and i.get("src"):
                return i["src"]
    src = (product.get("image") or {}).get("src") if isinstance(product.get("image"), dict) else None
    return src or (images[0].get("src") if images else None)


def read_product(url: str) -> dict | None:
    """{"title", "vendor", "price", "image", "variant"} for a product link on a
    known Shopify shop, else None. `price` is the pasted variant's (from
    ?variant=), or the first variant's; None if it reads as zero."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not is_shopify_host(host):
        return None
    handle = product_handle(url)
    if not handle:
        return None
    json_url = f"https://{host}/products/{handle}.json"
    variant_id = (parse_qs(parts.query).get("variant") or [None])[0]

    product = None
    try:
        with httpx.Client(timeout=_PLAIN_TIMEOUT, follow_redirects=True, headers=_PLAIN_HEADERS) as client:
            resp = client.get(json_url)
        if resp.status_code == 200:
            product = _parse_product(resp.text)
            if product:
                logger.info("[shopify] plain read ok: %s", json_url)
        elif resp.status_code == 404:
            # The shop itself says there is no such product (a mistyped or
            # removed link): a paid read would only confirm it.
            logger.info("[shopify] %s is not a product on this shop", json_url)
            return None
        else:
            logger.info("[shopify] plain read %s for %s, trying Context.dev", resp.status_code, json_url)
    except httpx.HTTPError as exc:
        logger.info("[shopify] plain read failed for %s: %s", json_url, exc)

    if product is None:
        product = _parse_product(context_dev_repository.fetch_rendered_html(json_url) or "")
        if product:
            logger.info("[shopify] Context.dev read ok: %s", json_url)
    if product is None:
        logger.info("[shopify] no product data for %s, falling back to the page", url)
        return None

    variant = _pick_variant(product, variant_id)
    variant_title = (variant or {}).get("title")
    return {
        "title": re.sub(r"\s+", " ", str(product["title"])).strip(),
        "vendor": (product.get("vendor") or "").strip() or None,
        "price": _price(variant),
        "image": _image(product, variant),
        "variant": variant_title if variant_title and variant_title != "Default Title" else None,
    }


def shops() -> dict[str, str]:
    """{bare domain: host that answers} for every known Shopify shop."""
    return dict(_load())


def search(host: str, query: str, merchant: str, limit: int = 5) -> list[dict]:
    """The shop's own top results for `query` (Shopify's search box data) as
    store rows, the same shape as flipkart_repository.search, or [] on any
    failure. Rows still go through the caller's exact-product check, so a
    near miss ("Airdopes 141 Gen 2", a silicon cover) is dropped there."""
    url = (f"https://{host}/search/suggest.json?q={quote_plus(query)}"
           f"&resources%5Btype%5D=product&resources%5Blimit%5D={limit}")
    text = None
    try:
        with httpx.Client(timeout=_PLAIN_TIMEOUT, follow_redirects=True, headers=_PLAIN_HEADERS) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            text = resp.text
        else:
            logger.info("[shopify] plain search %s for %s, trying Context.dev", resp.status_code, host)
    except httpx.HTTPError as exc:
        logger.info("[shopify] plain search failed for %s: %s", host, exc)
    if text is None:
        text = context_dev_repository.fetch_rendered_html(url) or ""
    if not text.lstrip().startswith("{"):
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    start = text.find('{"resources"')
    try:
        products = json.JSONDecoder().raw_decode(text[start:])[0]["resources"]["results"]["products"] if start >= 0 else []
    except (ValueError, KeyError, TypeError):
        products = []
    rows = []
    for p in products:
        if not isinstance(p, dict) or not p.get("title") or not p.get("url"):
            continue
        price = _price({"price": p.get("price_min") or p.get("price")})
        if price is None:
            continue
        was = _price({"price": p.get("compare_at_price_max")})
        rows.append({
            "merchant": merchant,
            "title": re.sub(r"\s+", " ", str(p["title"])).strip(),
            "price": price,
            "was_price": was if was and was > price else None,
            "link": f"https://{host}" + str(p["url"]).split("?", 1)[0],
            "details": [] if p.get("available", True) else ["Out of stock"],
            "_source_token": "shopify-search",
        })
    logger.info("[shopify] %d result(s) on %s for %r", len(rows), host, query)
    return rows
