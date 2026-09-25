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
    # 118 ml is Cetaphil's repackaged 125 ml (user, 2026-09-25): same product.
    assert tier(cleanser, "Cetaphil Gentle Skin Cleanser For Normal, Dry Skin (118ml)") == "exact"
    assert tier(cleanser, "Cetaphil Gentle Skin Cleanser (Dry to Normal, Sensitive Skin), 250 ml") == "similar"
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


def test_strength_packs_bundles_and_editions():
    serum = "Minimalist 10% Niacinamide Face Serum With Matmarine + Zinc"
    assert tier(serum, "Minimalist 5% Niacinamide Serum For Glowing") == "wrong"
    assert tier(serum, "Minimalist Niacinamide 10% Face Serum for Blemishes - 30 ml") == "exact"
    assert tier(serum, "Minimalist Set of Vitamin C 10% & Niacinamide 10% Face Serum - 10 ml each (Pack)") == "similar"
    wash = "Himalaya Purifying Neem Face Wash, 150 ml"
    assert tier(wash, "Himalaya Purifying Neem Face Wash 150ml( Pack Of 3)") == "similar"
    briefs = "Jockey 8008 Men's Super Combed Cotton Rib Solid Boxer Brief (Pack of 4),Assorted"
    assert tier(briefs, "Jockey 8008 Men Cotton Solid Boxer Brief - Black") == "similar"
    mouse = "Logitech MX Master 3S - Wireless Performance Mouse with Ultra-Fast Scrolling (Black)"
    assert tier(mouse, "Logitech MX Master 3S for Mac Wireless Bluetooth Mouse") == "wrong"


def test_noise_cancelling_is_its_own_edition():
    airpods = "Apple AirPods 4 Wireless Earbuds, Bluetooth Headphones, Personalised Spatial Audio"
    assert tier(airpods, "Apple AirPods 4 with Active Noise Cancellation, Adaptive Audio") == "wrong"
    sony = "Sony WH-1000XM5 Best Active Noise Cancelling Wireless Bluetooth Over Ear Headphones"
    assert tier(sony, "SONY WH-1000XM5 ANC Headphones") == "exact"
    anc = "boAt Airdopes 141 ANC, Active Noise Cancellation(~32dB), 50ms Low Latency"
    assert tier(anc, "boAt Airdopes 141 Wireless Earbuds") == "wrong"


def test_storage_missing_from_the_pick_comes_from_the_link():
    url = "https://www.flipkart.com/samsung-galaxy-s25-5g-mint-128-gb/p/itmcc2f488d41676"
    assert tier("Samsung Galaxy S25 5G", "SAMSUNG MOBILE GALAXY S25 12GB 256GB NAVY BLUE", url) == "similar"


def test_brand_websites_are_trusted_by_address_not_name():
    from src.services.search_service import _is_brand_store
    assert _is_brand_store("Sony Center", "https://www.sony.co.in/electronics/headband-headphones/wh-1000xm5", "sony")
    assert _is_brand_store("Bajaj", "https://shop.bajajelectricals.com/fans/frore", "bajaj")
    assert not _is_brand_store("Sony Store", "https://www.sonydealsindia.in/wh-1000xm5", "sony")
    assert not _is_brand_store("Minimalist", "https://www.cheapskincare.in/minimalist-serum", "minimalist")


def test_spare_parts_combos_and_bluetooth_edition():
    url = "https://www.flipkart.com/philips-phlips-hl7756-00-daily-collection-750-mixer-grinder-3-jars-black/p/itm60d841bdca6dc"
    page = "PHILIPS by Phlips Daily Collection 750 W Mixer Grinder"
    assert tier(page, "Philips HL7756/00 Mixer Grinder, 750W, 3 Jars (Black) & Classic GC097/50 750-Watt Dry Iron (Peach)", url) == "similar"
    assert tier(page, "Philips HL7756/00 Daily Collection Mixer Grinder 750W 3 Jars", url) == "exact"
    mouse = "Logitech MX Master 3S - Wireless Performance Mouse with Ultra-Fast Scrolling (Black)"
    assert tier(mouse, "Logitech MX Master 3S Bluetooth Edition Wireless Mouse, No USB Receiver") == "wrong"
    from src.services.search_service import _SPARE_PART_RE
    assert _SPARE_PART_RE.search("Buy SS JAR ASSLY 1.0LTR-HL7756-Dry jar")
