"""Searches Dealo can't price as a product: shop-name spelling slips, shops
with no gift card, grocery searches, brand typos and WhatsApp questions.
The examples are real searches from Mixpanel (Sep-Oct 2026). No network:
every path here answers from the local gift-card files."""
import pytest

from src.services import search_fallbacks, search_service
from src.services.whatsapp_service import classify_input

GROCERY = [
    "Amul butter", "Need to buy a kilo of Milld atta", "Lijjat papad", "Pampers xxl",
    "Pampers xxl flipkart", "Akshayakalpa Organic Handcrafted Malai Paneer, 200 gm",
    "basmati rice 5kg", "toor dal", "aashirvaad atta 10 kg", "maggi", "surf excel 2kg",
    "eggs", "tata salt", "peanut butter", "cooking oil 1 litre", "apples 1kg",
]
NOT_GROCERY = [
    "rice cooker", "Samsung 65 inch tv", "Shoes", "Nike t-shirt", "iphone 18 pro",
    "Front loaded washing machine", "coffee maker", "hair oil", "body butter", "engine oil",
    "Apple", "mango dress", "Booking.com", "Realme buds air 8", "milk frother", "tea set",
    "water bottle", "5 star hotel", "galaxy s25", "boAt Airdopes 141", "Noise Master Buds",
    "chocolate box", "D mart", "Blinkit", "Ledis Shows", "coconut oil for hair", "egg boiler",
]


@pytest.mark.parametrize("query", GROCERY)
def test_grocery_searches_are_recognised(query):
    assert search_fallbacks.is_grocery_query(query)


@pytest.mark.parametrize("query", NOT_GROCERY)
def test_other_searches_are_not_grocery(query):
    assert not search_fallbacks.is_grocery_query(query)


@pytest.mark.parametrize("typed, fixed", [
    ("SUS Vivobook 15", "Asus Vivobook 15"),
    ("Samsng galaxy s24", "Samsung galaxy s24"),
    ("Aple iphone", "Apple iphone"),
    ("Addidas shoes", "Adidas shoes"),
])
def test_brand_slip_is_fixed(typed, fixed):
    assert search_fallbacks.corrected_brand_query(typed) == fixed


@pytest.mark.parametrize("typed", ["Ample storage box", "Apples", "Shoes", "Dell laptop", "Jeans"])
def test_real_words_are_left_alone(typed):
    assert search_fallbacks.corrected_brand_query(typed) is None


@pytest.mark.parametrize("typed, shop", [
    ("Sketchers", "Skechers"), ("Nyka", "Nykaa"), ("Blinkt", "Blinkit"),
    ("Mintra", "Myntra"), ("Makemytrp", "MakeMyTrip"), ("Decatlon", "Decathlon"),
])
def test_shop_slip_finds_the_shop(typed, shop):
    found = search_service._search_miss_fallback(typed)
    assert found["mode"] == "brand_voucher"
    assert found["corrected_query"] == shop


def test_a_near_miss_never_becomes_a_different_shop():
    # At a looser setting "D mart" read as V Mart, a different shop.
    found = search_service._search_miss_fallback("D mart")
    assert found["mode"] == "voucher_group"
    assert found["group_headline"] == "No DMart deal yet"


@pytest.mark.parametrize("query, group", [
    ("DMart", "grocery"), ("Agoda", "hotels"), ("Booking.com", "hotels"), ("IndiGo", "travel"),
    ("Amul butter", "grocery"),
])
def test_group_cards_best_rate_first(query, group):
    found = search_service._search_miss_fallback(query)
    assert found["mode"] == "voucher_group" and found["group"] == group
    rates = [c["best_discount_pct"] for c in found["voucher_choices"]]
    assert rates and rates == sorted(rates, reverse=True) and all(r > 0 for r in rates)
    assert all(c["voucher_url"] and c["choice_label"] for c in found["voucher_choices"])


def test_shops_we_sell_are_untouched():
    assert search_service.search_candidates("Myntra", shops_only=True)["mode"] == "brand_voucher"
    assert search_service._search_miss_fallback("iphone 18 pro") is None


@pytest.mark.parametrize("text, kind", [
    ("Do you just help track the portal with the best voucher price or also sell vouchers?", "about"),
    ("Is this free?", "about"),
    ("H r u", "unparseable"),
    ("I want to buy iPhone 18 pro max", "product_name"),
    ("Can I buy iphone 18 cheaper?", "product_name"),
])
def test_whatsapp_questions(text, kind):
    assert classify_input(text)["type"] == kind
