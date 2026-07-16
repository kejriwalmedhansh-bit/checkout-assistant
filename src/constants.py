"""Application constants.

Non-secret, fixed configuration values live here (not in .env). Secrets and
per-environment credentials stay in settings / the environment.
"""
from __future__ import annotations

from pathlib import Path

# --- Filesystem ---
# data/ holds the bundled JSON knowledge bases (gyftr_master, cashback_cards).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --- CORS allowed origins ---
# The frontend is a static site; no cookies/auth are used, so "*" is safe.
CORS_ORIGINS = ["*"]

# --- SearchApi.io ---
SEARCHAPI_BASE = "https://www.searchapi.io/api/v1/search"
# Applied to every SearchApi request (India results, English).
SEARCHAPI_DEFAULTS = {"gl": "in", "hl": "en"}

# --- WhatsApp (Meta Graph API) ---
WHATSAPP_GRAPH_VERSION = "v20.0"
WHATSAPP_GRAPH_BASE = "https://graph.facebook.com"

# --- Cuelinks affiliate wrapping ---
# Merchant store links are wrapped; Gyftr voucher links are deliberately NOT.
CUELINKS_BASE = "https://linksredirect.com/?cid={cid}&source=linkkit&url={url}"

# --- L1 merchant guards (ported from pipeline.py) ---
MANUAL_TRUSTED_MERCHANTS = [
    "Amazon", "Flipkart", "Myntra", "Nykaa", "AJIO", "Croma",
    "Reliance Digital", "Vijay Sales", "Tata CLiQ", "BigBasket",
    "Apple", "Samsung", "JioMart", "Pepperfry", "Lenskart",
]

PRIORITY_MERCHANTS = [
    "croma", "vijay sales", "reliance digital", "tata cliq", "flipkart", "amazon",
]

KNOWN_BRANDS = [
    "boat", "noise", "apple", "samsung", "sony", "lg", "hp", "dell", "lenovo",
    "asus", "acer", "microsoft", "google", "oneplus", "realme", "xiaomi",
    "oppo", "vivo", "motorola", "nokia", "jbl", "bose",
    "nike", "adidas", "puma", "reebok", "skechers", "fila", "asics",
    "lakme", "mamaearth", "himalaya", "nivea", "dove", "loreal", "garnier",
    "titan", "fastrack", "casio", "philips",
]

# --- WhatsApp user-facing copy ---
WHATSAPP_ONBOARDING_MSG = (
    "Hi! I'm Dealo 👋\n\n"
    "Tell me what you want to buy.\n"
    "I'll find the smartest way to pay for it.\n\n"
    "Vouchers, card offers, best price — all in 20 seconds.\n\n"
    "Try:\n• boAt Airdopes 141\n• amazon.in/dp/B09XYZ (any product link)"
)
WHATSAPP_NUDGE_MSG = (
    "Send me a product name and I'll find the best deal — "
    "like 'boAt Airdopes 141' or 'Nike Air Force 1'."
)
WHATSAPP_DEAD_END_MSG = (
    "Couldn't find a good deal for that one. Try a more specific product name."
)
WHATSAPP_SESSION_EXPIRED_MSG = (
    "It's been a while — send the product name again and I'll look it up fresh."
)
WHATSAPP_NO_ALTERNATIVES_MSG = "This one only has one route available."
WHATSAPP_MULTI_MATCH_MSG = (
    "Got a few options. Tap the right one — product photo and details will show up right after."
)
WHATSAPP_MORE_OPTIONS_MSG = "Not what you were looking for?"
