"""A pasted link must only show listings of that exact product.

Titles are real ones from the 2026-09-25 link test (30 new links + the 19
earlier ones): before this, 9 in 10 picker rows were a different model.

Run:  .venv/bin/python -m pytest tests/test_exact_product_match.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.product_identity import build_identity, identity_query, match_tier  # noqa: E402


def tier(page_title, listing, url=None, source=""):
    return match_tier(build_identity(page_title, url), listing, source)[0]


def test_other_models_of_the_same_line_are_wrong():
    page = "boAt Rockerz 450/450R, 15 HRS Battery, 40mm Drivers, Wireless Headphone with Mic (Luscious Black)"
    assert tier(page, "boAt Rockerz 450R") == "exact"
    assert tier(page, "boAt Rockerz 430 Headphones") == "wrong"
    assert tier(page, "boAt Rockerz Plus 450 ANC 80h Playback and 40dB ANC") == "wrong"
    sony = "Sony WH-1000XM5 Best Active Noise Cancelling Wireless Bluetooth Over Ear Headphones with Mic -Black"
    assert tier(sony, "Sony Unisex Best Active Wireless Bluetooth Headphones with Mic-WH-1000XM5 (Purple)") == "exact"
    assert tier(sony, "Sony WH-1000XM6 Noise-Cancelling Over-Ear Wireless Headphones") == "wrong"


def test_model_codes_tolerate_separators_and_region_suffixes():
    casio = "Casio Vintage A-158WA-1Q Digital Watch"
    assert tier(casio, "Casio A158WA-1DF Black Digital Dial Silver Stainless Steel Band") == "exact"
    assert tier(casio, "Casio A168WA-1WDF Vintage Digital Unisex Watch") == "wrong"
    trimmer = "Philips BT3221/15 Smart Beard Trimmer - Power adapt technology"
    assert tier(trimmer, "Philips BT3201/15 Cordless Beard Trimmer") == "wrong"


def test_sibling_sub_models_are_wrong():
    fan = "BAJAJ Frore with 1 Year Warranty 1200 mm Ceiling Fan"
    assert tier(fan, "Bajaj Frore Ceiling Fan") == "exact"
    assert tier(fan, "Bajaj Frore Turbo 1200 mm BLDC Ceiling Fan") == "wrong"
    shoes = "skechers men go walk flex lace up shoes"
    assert tier(shoes, "Skechers Men GO WALK FLEX Navy Blue Walking Shoes") == "exact"
    assert tier(shoes, "Skechers Men's Go Walk Flex Remark Walking Shoe") == "wrong"
    wash = "Himalaya Purifying Neem Face Wash, 150 ml"
    assert tier(wash, "Himalaya Purifying Neem Foaming Face Wash") == "wrong"


def test_air_in_a_product_name_is_not_the_air_sub_model():
    fryer = "PHILIPS NA231/00 with touch panel & Cooking window, 1700W, with Rapid Air Technology Air Fryer"
    assert tier(fryer, "Philips Air Fryer NA231/00 with touch panel") == "exact"


def test_other_sizes_packs_and_storage_are_similar_not_exact():
    cleanser = "Cetaphil Gentle Skin Cleanser, 125ml"
    assert tier(cleanser, "Cetaphil Gentle Skin Cleanser For Normal, Dry Skin (118ml)") == "similar"
    phone = "Samsung Galaxy A56 5G 256 GB, 8 GB RAM, Awesome Graphite, Mobile Phone at Reliance Digital"
    assert tier(phone, "Galaxy A56 5G Samsung") == "exact"
    assert tier(phone, "Samsung Galaxy A56 5G (Awesome Olive, 12GB, 256GB)") == "similar"


def test_model_number_from_the_link_when_the_title_drops_it():
    url = "https://www.flipkart.com/prestige-pic-20-0-1600-w-induction-cooktop/p/itm5607e11031cc9"
    page = "Prestige 1600 W Induction Cooktop Push Button - Buy Prestige 1600 W Induction Cooktop Push Button Online at best"
    assert tier(page, "Prestige PIC 20.0 Induction Cooktop", url) == "exact"
    assert tier(page, "Prestige PIC 20 NEO 1600W Induction Cooktop", url) == "wrong"
    assert tier(page, "Prestige PIC 16.0 1600 W Induction Cooktop", url) == "wrong"


def test_a_store_homepage_title_falls_back_to_the_link_words():
    url = "https://www.vijaysales.com/p/P241181/241184/oneplus-nord-ce5-5g-8gb-ram-128gb-storage-black-infinity"
    ident = build_identity("Oneplus Smartphones Online at Best Price", url)
    assert "ce5" in ident["codes"] and ident["variants"]["storage"] == 128


def test_a_real_title_is_kept_over_a_keyword_stuffed_link():
    url = "https://www.amazon.in/Samsung-Snapdragon-Processor-6-2-inch-Smartphone/dp/B0H3FLD9NM"
    ident = build_identity("Samsung Galaxy S25 5G (Navy, 12GB RAM, 128GB Storage)", url)
    assert ident["codes"] == ["s25"]
    assert identity_query(ident) == "samsung galaxy s25 128GB"
