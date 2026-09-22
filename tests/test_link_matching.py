"""A pasted brand-website link should find that exact product, at that shop.

Found 2026-09-22 checking bestseller links for marketing: Bath & Body Works
"Paris Cafe" searched without its brand and matched coffee makers; a new
Wonderchef OTG matched its renewed twin; a Skechers sandal link opened on a
different shoe; and wonderchef.com got no voucher because an in-store-only card
had the higher rate.

Run:  .venv/bin/python -m pytest tests/test_link_matching.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import search_service as ss  # noqa: E402
from src.services import voucher_service as vs  # noqa: E402

# Trimmed from bathandbodyworks.in's real product page, 2026-09-22.
_BBW_PAGE = """
<meta property="og:site_name" content="Bath and Body Works" />
<meta property="og:title" content="Paris Cafe" />
<script type="application/ld+json">{"@type": "Product", "name": "Paris Cafe",
 "brand": {"@type": "Thing", "name": "Bath amp; Body Works"},
 "image": ["https://www.bathandbodyworks.in/paris-cafe.jpg"],
 "offers": {"@type": "Offer", "price": "2599.00", "priceCurrency": "INR"}}</script>
"""


def test_brand_names_read_the_way_people_write_them():
    assert ss._clean_brand_name("Bath amp; Body Works") == "Bath & Body Works"
    assert ss._clean_brand_name("Bath and Body Works") == "Bath & Body Works"
    assert ss._clean_brand_name("Superdry-Luxe Gift Card") == "Superdry"
    assert ss._clean_brand_name("FRIDO") == "Frido"
    assert ss._clean_brand_name("Wonderchef India") == "Wonderchef"
    assert ss._clean_brand_name("ALDO") == "ALDO"


def test_a_title_without_its_brand_gets_one():
    assert ss._title_with_brand("Paris Cafe", "Bath & Body Works") == "Bath & Body Works Paris Cafe"
    assert ss._title_with_brand("Skechers BOBS SKILLZ", "Skechers") == "Skechers BOBS SKILLZ"
    assert ss._title_with_brand("Wonder Chef Nutri-Blend", "Wonderchef") == "Wonder Chef Nutri-Blend"


def test_a_shop_selling_only_itself_is_a_brand_website():
    name, brand, image = ss._extract_jsonld_product(_BBW_PAGE)
    assert name == "Paris Cafe"
    assert image == "https://www.bathandbodyworks.in/paris-cafe.jpg"
    assert ss._brand_website_name(_BBW_PAGE, "www.bathandbodyworks.in", brand) == "Bath & Body Works"


def test_a_marketplace_is_not_the_brands_website():
    page = """<meta property="og:site_name" content="Myntra" />
    <script type="application/ld+json">{"@type": "Product", "name": "Air Max",
     "brand": {"name": "Nike"}}</script>"""
    assert ss._brand_website_name(page, "www.myntra.com", "Nike") is None
    assert not ss._is_brand_site_merchant("Myntra")
    assert ss._is_brand_site_merchant("Skechers")
    assert ss._is_brand_site_merchant("Bath & Body Works")


def test_renewed_listings_answer_only_a_renewed_search():
    new = {"title": "Wonderchef OTG Oven Toaster Griller 60L", "price": 13999.0, "source": "Wonderchef", "product_token": "a"}
    renewed = {"title": "Wonderchef Renewed OTG Oven Toaster Griller 60L", "price": 9999.0, "source": "Wonderchef", "product_token": "b"}
    kept, _ = ss._filter_and_group_candidates([renewed, new], "Wonderchef OTG Oven Toaster Griller 60L")
    assert [c["title"] for c in kept] == [new["title"]]
    kept, _ = ss._filter_and_group_candidates([renewed, new], "Wonderchef Renewed OTG 60L")
    assert renewed["title"] in [c["title"] for c in kept]


def test_an_in_store_voucher_never_takes_the_websites_slot():
    online = {"redemption_type": "Online"}
    in_store = {"redemption_type": "Offline"}
    assert vs._deal_is_offline_only(in_store, {})
    assert not vs._deal_is_offline_only(online, {})
    # The shop's own "cannot be used online" outranks the platform's flag.
    assert vs._deal_is_offline_only(online, {"works_online": {"value": "no"}})


def test_a_site_wide_preview_title_does_not_hide_the_product_name():
    page = """<meta property="og:title" content="Skullcandy | Headphones, Earbuds, and Gaming Headphones" />
    <title>Skullcandy Method 360 ANC - Sound by Bose</title>"""
    assert ss._extract_page_title(page).startswith("Skullcandy Method 360 ANC")
    # A one-word name still comes back when it is all the page offers.
    assert ss._extract_page_title("<title>Skullcandy</title>") == "Skullcandy"
