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
    "Send me a product name or paste a link and I'll find the cheapest way to buy it.\n\n"
    "Examples:\n• boAt Airdopes 141\n• https://www.amazon.in/dp/B0ABC123"
)
WHATSAPP_NUDGE_MSG = (
    "Send a product name (e.g. 'Samsung Galaxy S24') or paste a product link."
)
WHATSAPP_DEAD_END_MSG = (
    "Couldn't find a reliable route for that one yet. "
    "Try a different product or paste the link directly."
)
WHATSAPP_SESSION_EXPIRED_MSG = (
    "Session expired — send the product again and I'll re-check."
)
WHATSAPP_NO_ALTERNATIVES_MSG = "No alternative routes found for this one."
WHATSAPP_MULTI_MATCH_MSG = "I found multiple matches. Pick the exact product."
WHATSAPP_MORE_OPTIONS_MSG = "Not the right fit?"
