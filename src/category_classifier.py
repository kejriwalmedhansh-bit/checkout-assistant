"""Product category classification + voucher restriction matching.

Moved verbatim from engine/category_classifier.py. Used to skip Gyftr vouchers
whose redemption restrictions exclude the product's category.
"""
import re

CATEGORY_KEYWORDS = {
    "electronics": [
        "iphone", "samsung", "galaxy", "oneplus", "xiaomi", "redmi", "realme",
        "laptop", "macbook", "earbuds", "airdopes", "airpods", "headphone",
        "smartphone", "tablet", "ipad", "television", "tv", "smartwatch",
        "watch", "camera", "speaker", "charger", "power bank", "monitor",
        "keyboard", "mouse", "router", "processor", "graphics card",
    ],
    "groceries": [
        "milk", "vegetables", "fruits", "rice", "atta", "flour", "oil",
        "grocery", "groceries", "dal", "pulses", "spices", "snacks",
        "biscuit", "bread", "eggs", "meat", "chicken", "fish",
    ],
    "fashion": [
        "shirt", "tshirt", "t-shirt", "jeans", "dress", "kurta", "saree",
        "shoes", "sneakers", "sandals", "footwear", "jacket", "trousers",
        "clothing", "apparel",
    ],
    "beauty": [
        "lipstick", "makeup", "skincare", "cream", "lotion", "shampoo",
        "conditioner", "perfume", "cosmetics", "moisturizer", "serum",
    ],
    "jewelry": [
        "gold", "silver", "diamond", "jewelry", "jewellery", "necklace",
        "ring", "earrings", "bangles", "coin",
    ],
}

CATEGORY_SYNONYMS = {
    "electronics": ["electronics", "electronic"],
    "groceries": ["grocery", "groceries"],
    "jewelry": ["gold", "silver", "jewelry", "jewellery", "coin"],
    "fashion": ["fashion", "apparel", "clothing"],
    "beauty": ["beauty", "cosmetics"],
}


def classify_product(product_name: str) -> str | None:
    name_lower = product_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', name_lower):
                return category
    return None


def restriction_mentions_category(restrictions: list[str], category: str | None) -> bool:
    if not category:
        return False
    synonyms = CATEGORY_SYNONYMS.get(category, [category])
    combined_text = " ".join(restrictions).lower()
    return any(re.search(r'\b' + re.escape(syn) + r'\b', combined_text) for syn in synonyms)
