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
    "Ethos", "Helios",  # authorized watch chains — approved 2026-07-21
    "Boat",  # approved 2026-08-04
    # "Boat" alone never catches this seller: Google Shopping lists boAt's
    # own store as "boat-lifestyle.com" / "boAt Lifestyle", and "lifestyle"
    # isn't a generic storefront word _brand_signature strips (rightly so —
    # "Lifestyle" is itself a real, separate retail brand) — added directly
    # after confirming in the backend logs that this exact seller was found
    # and then dropped as "untrusted" on a live search (2026-08-08).
    "boAt Lifestyle", "boat-lifestyle.com",
    # Same class of bug, found by auditing the logs for the same pattern
    # (2026-08-08): both are the parent brand's own storefront under a
    # sub-brand suffix _brand_signature doesn't recognize as generic —
    # "MNow" (Myntra's own quick-delivery arm) and "Jewellery" (Tata CLiQ's
    # jewelry vertical) — confirmed dropped as "untrusted" on live searches.
    "Myntra - MNow", "Tata CLiQ Jewellery",
    # Full-catalog audit (2026-08-08): every online-redeemable Gyftr/Maximize
    # brand's real official domain was verified via live search, then checked
    # against the existing whitelist logic. These 61 are the ones that
    # wouldn't already be recognized as trusted — same root cause as boAt:
    # the real seller domain doesn't reduce to the same signature as the
    # brand's own voucher-listing name (a sub-brand suffix, an unrelated TLD,
    # a platform name that differs from the storefront name, etc.). See
    # audits/brand_website_matching.csv for the full brand→domain mapping,
    # including the ~275 domains that were verified but already covered and
    # so needed no change here.
    "adanione.com", "adventrasports.com", "alistetechnologies.com",
    "appyhigh.com", "archiesonline.com", "assemblytravel.com", "theauric.com",
    "battlegroundsmobileindia.com", "campusshoes.com", "candere.com",
    "celloworld.com", "cinepolisindia.com", "cult.fit", "dieselindia.com",
    "duroflexworld.com", "ea.com", "euphoriajewellery.in", "fnp.com",
    "myfrido.com", "futureworldindia.in", "gasjeans.com", "giva.co",
    "goibibo.com", "gyftr.com", "hammeronline.in", "hindustantimes.com",
    "hoichoi.tv", "hunkemoller.in", "pvrcinemas.com", "kalkifashion.com",
    "ketandiamonds.com", "levi.in", "libertyshoesonline.com",
    "lifestylestores.com", "lohono.com", "malabargoldanddiamonds.com",
    "marksandspencer.in", "maxfashion.in", "microsoft.com", "xbox.com",
    "mobilelegends.com", "muscleblaze.com", "potterybarn.com",
    "ttkprestige.com", "purehomeandliving.com", "ubisoft.com", "razer.com",
    "riotgames.com", "ritukumar.com", "smilefoundationindia.org",
    "playstation.com", "store.steampowered.com", "stevemadden.in",
    "swiggy.com", "tego.fit", "playvalorant.com", "veridicushealthcares.com",
    "westelm.in", "woodlandworldwide.com", "wynk.in", "zeptonow.com",
    # Follow-up pass on the same audit (2026-08-08) — search budget ran out
    # mid-pass the first time, these are the gaps that surfaced once the
    # remaining brands got properly verified.
    "getfrenchaccent.com", "libertyshoes.com", "luzo.app",
    "matrixprofessional.in", "miraggiolife.com", "muji.in",
    "pointsforgood.org", "razorpay.com", "resonate.store",
    # Live spot-check (2026-08-08) of the domains above surfaced a deeper
    # pattern: a verified domain doesn't guarantee a match, because Google
    # Shopping often attributes a listing to the seller's legal/corporate
    # name rather than its consumer brand name — "levi.in" was already
    # whitelisted, but a real search for "Levis jeans men" returned the
    # seller as "Levi Strauss India", which reduces to a different
    # signature ("levistrauss" vs "levi") and got dropped as untrusted
    # anyway. Confirmed in this exact test run's logs. Only entries actually
    # proven this way (found in real search results, not guessed) belong
    # here — see CLAUDE.md rule #1.
    "Levi Strauss India",
    # Systematic follow-up (2026-08-08): ran a real test search for every
    # one of the 69 remaining newly-verified brands and checked the logs for
    # the same failure pattern as Levi's. 4 more real, live-confirmed gaps —
    # "TTK PrestigeLimited" alone was the seller on 31 of the Prestige
    # pressure-cooker results in one test search, i.e. the domain fix
    # (ttkprestige.com) would have missed nearly all of Prestige's own
    # listings without this.
    "TTK PrestigeLimited", "Judge by Prestige",
    "Liberty Leathers", "Pottery Barn Kids",
    # Second sweep (2026-08-10): live-tested the remaining 205 brands whose
    # own trust status had never been checked (the domain-signature match
    # said they were already fine — the same shortcut that had missed the
    # Levi's and Prestige gaps). 7 more confirmed real gaps; a handful of
    # signature-substring "hits" on "Mi.com" (Xiaomi) and "Vi" (Vodafone
    # Idea) were correctly excluded as false positives — those are real,
    # unrelated companies, not sub-brands of anything in this list.
    "Nykaa Now", "Blaupunkt Audio", "Crossword Bookstores",
    "Decathlon Sports India", "Nua", "Philips Domestic Appliances",
    "Shiv Naresh Sports",
    # Third sweep (2026-08-11): live-tested the 249 brands still marked
    # Medium/Low/Uncertain confidence in audits/brand_website_matching.csv
    # (guessed domains that were never checked against a real search). 23
    # confirmed real gaps (16 distinct fixes — a few cover multiple
    # near-duplicate SKUs of the same brand, e.g. Jos Alukkas/Joyalukkas/PC
    # Jeweller each list Diamond/Gold/etc. as separate catalog rows but sell
    # under one real storefront name). "adidas.co.in" was a bigger miss than
    # the rest — the catalog has no plain "Adidas" entry at all, only an
    # oddly-named "Adidas Kids-Luxe Gift Card" SKU, so no plain "adidas"
    # signature existed to match against. "Malabar Gold & Diamonds" replaces
    # the existing "malabargoldanddiamonds.com" fix, which doesn't actually
    # match the real seller name: the domain spells out "and", but the live
    # seller name uses "&", which the signature matcher drops entirely
    # instead of reading as "and" — so the two never reduced to the same
    # signature. Flagged separately, NOT added here: "Timezone Australia"
    # (found for the "Timezone" arcade brand, but not confirmed to be the
    # same company vs. an unrelated overseas retailer) and a handful of
    # coincidental substring hits correctly excluded as false positives
    # ("Mi.com" for "Mia", "Meena Bazaar"/"Wooden Bazar" for "Modern Bazaar",
    # "CoinGate Gift Cards" for "Coach-Luxe Gift Card" and "Luxe Gift Card").
    "adidas.co.in", "Aldo Shoes", "Bhima Jewellers",
    "Blue Tokai Coffee Roasters", "BlueStone", "Bodycraft Shop",
    "Jos Alukkas", "Joyalukkas", "Lawrence & Mayo",
    "Malabar Gold & Diamonds", "M.P.J. Jewellers", "PC Jeweller",
    "Peora India", "relaxofootwear.com", "Senco Gold and Diamonds",
    "Tira", "W For Woman",
    "culture-circle.com",
]

PRIORITY_MERCHANTS = [
    "croma", "vijay sales", "reliance digital", "tata cliq", "flipkart", "amazon",
]

# Hyperlocal/quick-commerce apps — kept last priority everywhere a route or
# candidate gets ranked (2026-07-28, flagged by the user from real usage).
# Their stock and delivery coverage is pincode-specific in a way this
# pipeline has no way to check, so a route through one of these can
# recommend something the user's location literally can't get. Never
# excluded outright — still shown if nothing else is available — just never
# allowed to outrank a normal listing on price alone.
HYPERLOCAL_MERCHANTS = ["blinkit", "zepto", "swiggy", "zomato"]

KNOWN_BRANDS = [
    "boat", "noise", "apple", "samsung", "sony", "lg", "hp", "dell", "lenovo",
    "asus", "acer", "microsoft", "google", "oneplus", "realme", "xiaomi",
    "oppo", "vivo", "motorola", "nokia", "jbl", "bose",
    "nike", "adidas", "puma", "reebok", "skechers", "fila", "asics",
    "lakme", "mamaearth", "himalaya", "nivea", "dove", "loreal", "garnier",
    "titan", "fastrack", "casio", "philips",
]

# --- WhatsApp user-facing copy ---
# Copy rules mirror design-system/dealo/MASTER.md's web copy rules: "Gift
# Voucher" (not a bare "voucher"), never say "route" or "UPI" unexplained,
# never show "Gyftr" raw (say "our voucher partner" instead).
WHATSAPP_ONBOARDING_MSG = (
    "Hi, I'm *Dealo* 👋\n\n"
    "Cheapest legit way to buy anything — Gift Vouchers, card offers, "
    "best price, all checked for you.\n\n"
    "Send a product name (or link) — like *Nike Air Force 1s*."
)
WHATSAPP_DEAD_END_MSG = (
    "Couldn't find that one. Try adding the brand or model — "
    "e.g. *Nike Air Force 1* instead of just 'shoes'."
)
WHATSAPP_SESSION_EXPIRED_MSG = (
    "That search has gone cold — send the product name again and I'll pull fresh prices."
)
WHATSAPP_NO_ALTERNATIVES_MSG = (
    "This is the only way we found to buy this — it's already your *best option*."
)
WHATSAPP_MULTI_MATCH_MSG = "Select the *exact* product you're looking for 👇"
# search_service's `approximate` / low-confidence flag (see
# _STRONG_MATCH_FRACTION) is intentionally never surfaced as its own
# message on WhatsApp — telling a user "I'm not fully sure" undermines
# trust more than it helps (user feedback 2026-08-28). A weak match just
# goes through the normal picker/result flow like any other match.
WHATSAPP_MORE_OPTIONS_MSG = "Want a different way to buy this, or a different product altogether?"
WHATSAPP_PICK_REMINDER_MSG = "*Tap* one of the options above 👆"
WHATSAPP_RATE_LIMITED_MSG = (
    "You're searching a lot in a short time — give it a few minutes and try again."
)

# Technical identifiers for the WhatsApp Flow-based photo picker — must
# exactly match the screen id / RadioButtonsGroup field name set in the
# Flow JSON published in Meta's WhatsApp Manager. Not user-visible copy.
WHATSAPP_FLOW_SCREEN_ID = "PRODUCT_PICKER"
WHATSAPP_FLOW_FIELD_NAME = "selected_product"
