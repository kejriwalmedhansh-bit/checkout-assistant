"""A pasted link on a Shopify shop is read from the shop's own product data.

87 of Dealo's 350 shop websites run on Shopify (data/shopify_shops.json,
2026-11-12). Their /products/<handle>.json states the exact name, brand and
each variant's price, so Dealo reads that instead of guessing from the page.
These tests use saved data and never touch the network.

Run:  .venv/bin/python -m pytest tests/test_shopify_reader.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repositories import shopify_repository  # noqa: E402
from src.services import search_service  # noqa: E402

# Trimmed from boat-lifestyle.com/products/airdopes-141.json (2026-11-12).
# "vendor" is the shop's account name, not the brand: the case that broke the
# first version (title read "boAtlifestylein boAt Airdopes 141", no price).
BOAT = {"product": {
    "title": "boAt Airdopes 141 | Wireless Earbuds with 42 Hours Playback",
    "vendor": "boAtlifestylein",
    "variants": [
        {"id": 111, "title": "Black", "price": "999.00", "image_id": 1},
        {"id": 222, "title": "Bold Blue", "price": "1099.00", "image_id": 2},
    ],
    "images": [{"id": 1, "src": "https://cdn.shopify.com/black.jpg"},
               {"id": 2, "src": "https://cdn.shopify.com/blue.jpg"}],
    "image": {"id": 1, "src": "https://cdn.shopify.com/black.jpg"},
}}


def test_known_shops_load():
    assert shopify_repository.is_shopify_host("www.boat-lifestyle.com")
    assert shopify_repository.is_shopify_host("mokobara.com")
    assert not shopify_repository.is_shopify_host("www.myntra.com")


def test_product_handle():
    h = shopify_repository.product_handle
    assert h("https://www.boat-lifestyle.com/products/airdopes-141?variant=1") == "airdopes-141"
    assert h("https://www.giva.co/collections/sale/products/silver-zircon-ferns-bracelet") == "silver-zircon-ferns-bracelet"
    assert h("https://www.boat-lifestyle.com/collections/earbuds") is None


def test_parse_plain_and_context_dev_wrapped():
    plain = json.dumps(BOAT)
    wrapped = "<html><body><pre>" + plain.replace('"', "&quot;") + "</pre></body></html>"
    for text in (plain, wrapped):
        assert shopify_repository._parse_product(text)["title"].startswith("boAt Airdopes 141")
    assert shopify_repository._parse_product("<html>Page not found</html>") is None


def test_pasted_variant_sets_price_and_photo(monkeypatch):
    class Resp:
        status_code = 200
        text = json.dumps(BOAT)

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return Resp()

    monkeypatch.setattr(shopify_repository.httpx, "Client", Client)
    p = shopify_repository.read_product("https://www.boat-lifestyle.com/products/airdopes-141?variant=222")
    assert p["price"] == 1099.0 and p["variant"] == "Bold Blue"
    assert p["image"].endswith("blue.jpg")


def test_link_reader_uses_shop_name_not_vendor(monkeypatch):
    monkeypatch.setattr(shopify_repository, "read_product", lambda url: {
        "title": BOAT["product"]["title"], "vendor": "boAtlifestylein",
        "price": 999.0, "image": "https://cdn.shopify.com/black.jpg", "variant": "Black"})
    title, price, merchant, image = search_service._read_shopify_link(
        "https://www.boat-lifestyle.com/products/airdopes-141")
    assert title.startswith("boAt Airdopes 141") and "boAtlifestylein" not in title
    assert price == 999.0 and merchant == "Boat"


def test_other_shops_untouched():
    assert search_service._read_shopify_link("https://www.myntra.com/shoes/nike/123/buy") is None


def test_unlisted_shopify_shop(monkeypatch):
    """A shop not in the list: trusted as the brand's own only when the brand
    names the web address; otherwise the page read decides."""
    product = {"title": "Oversized Linen Shirt", "vendor": "Snitch", "price": 1299.0, "image": None, "variant": None}
    monkeypatch.setattr(shopify_repository, "read_product", lambda url: product)
    title, price, merchant, _ = search_service._read_shopify_link("https://www.snitch.com/products/oversized-linen-shirt")
    assert merchant == "Snitch" and price == 1299.0 and title.startswith("Snitch")
    product = {**product, "vendor": "Some Other Label"}
    assert search_service._read_shopify_link("https://www.randomshop.in/products/oversized-linen-shirt") is None


def test_listed_single_card_name_falls_back(monkeypatch):
    """giva.co is listed as "GIVA Silver Coin"; a bracelet must not be priced
    against the coin card, so the shortcut steps aside for the page read."""
    monkeypatch.setattr(shopify_repository, "read_product", lambda url: {
        "title": "Silver Zircon Ferns Bracelet", "vendor": "GIVA Jewellery",
        "price": 1999.0, "image": None, "variant": None})
    assert search_service._read_shopify_link("https://www.giva.co/products/silver-zircon-ferns-bracelet") is None


def test_placeholder_price_ignored():
    assert shopify_repository._price({"price": "0.01"}) is None
    assert shopify_repository._price({"price": "599.00"}) == 599.0
