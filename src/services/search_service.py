"""Search orchestration — the decomposed run_pipeline for the SearchApi.io engine.

Two-step flow:
  1. search_candidates(query) -> Product Picker: grouped variant rows from one
     cheap google_shopping search.
  2. build_routes_for_token(token, query, title) -> a second, focused
     google_shopping search scoped to the selected variant's own title (not
     the original broad query), filtered to trusted/sane candidates, then
     get_product() on a small capped number of the cheapest survivors —
     merging their offers rather than trusting whatever sellers Google
     associated with one representative listing.

Then apply the ported L1 guards, build Gyftr voucher deals, assemble routes, and
attach the best cashback card to every route shown (never affects ranking).

The output dict preserves the exact contract the frontend + WhatsApp depend on.
URL mode is gone, so mode is always "text".
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx

# Attach to uvicorn's configured logger so these lines show in the server
# console (the app defines no logging config of its own).
logger = logging.getLogger("uvicorn.error")

from ..config import get_settings
from ..constants import KNOWN_BRANDS, MANUAL_TRUSTED_MERCHANTS, PRIORITY_MERCHANTS
from ..repositories import searchapi_repository, voucher_repository
from . import card_service, voucher_service

# ── price parsing ──────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r"[\d][\d,]*(?:\.\d+)?")


def parse_price(value) -> float | None:
    """Parse a SearchApi price into a float. Accepts numbers or display strings
    like "₹1,299" / "$1,299.00". Returns None when no number is present."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _PRICE_RE.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


# ── L1 guards (ported from pipeline.py) ─────────────────────────────────────────

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_trusted_merchants_cache: set[str] | None = None


# Words a genuine storefront appends to its brand name ("Croma Retail",
# "JioMart Electronics", "Amazon.in", "AJIO Luxe") — ignored when comparing a
# listing's merchant name against the whitelist. Deliberately excludes any
# word a counterfeit seller uses to piggyback on a brand ("first", "copy",
# "replica"): a name is trusted only when NOTHING beyond the whitelisted
# brand itself and these words is left over. "Titan Store" passes; "Titan
# First Copy Watches" does not.
_GENERIC_MERCHANT_WORDS = frozenset({
    "store", "stores", "shop", "shopping", "official", "online", "retail",
    "outlet", "india", "in", "com", "co", "the", "electronics", "fashion",
    "luxury", "luxe", "watch", "watches", "boutique", "boutiques",
})


def _brand_signature(name: str) -> str:
    """The brand identity left after stripping generic storefront words,
    fused ("Ethos Watch Boutiques" -> "ethos", "Tata CLiQ Luxury" ->
    "tatacliq"). Falls back to the full fused name when stripping would
    leave nothing (e.g. a brand actually named "The Luxury Store")."""
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    core = [w for w in words if w not in _GENERIC_MERCHANT_WORDS]
    return "".join(core or words)


def _load_trusted_merchants() -> set[str]:
    global _trusted_merchants_cache
    if _trusted_merchants_cache is not None:
        return _trusted_merchants_cache
    whitelist: set[str] = set()
    for name in list(MANUAL_TRUSTED_MERCHANTS) + list(voucher_repository.brand_names()):
        whitelist.add(_norm(name))
        whitelist.add(_brand_signature(name))
    whitelist.discard("")
    _trusted_merchants_cache = whitelist
    return whitelist


def _is_trusted_merchant(merchant_name: str, whitelist: set[str]) -> bool:
    """Exact match on the fused name or on its brand signature — never a bare
    substring check. The old bidirectional substring match let any seller
    whose name merely *contained* a whitelisted brand through ("Titan First
    Copy Watches" matched the Gyftr brand "titan"), which is how counterfeit
    storefronts reached the picker."""
    norm = _norm(merchant_name)
    if not norm:
        return False
    return norm in whitelist or _brand_signature(merchant_name) in whitelist


def _filter_trusted_only(results: list[dict], merchant_key: str = "merchant") -> list[dict]:
    """Keep only whitelisted merchants. If nothing survives, returns an empty
    list — an untrusted-only result set is treated as no route found rather
    than shown with a warning (trust is the core product value)."""
    whitelist = _load_trusted_merchants()
    return [r for r in results if _is_trusted_merchant(r.get(merchant_key) or "", whitelist)]


# Platforms that host third-party sellers under their own storefront name —
# a price attributed to them can be a genuine sale or an unrelated reseller's
# listing (see CLAUDE.md known-bug #7), so they're fine to *show* (still
# trusted) but not reliable enough to *anchor* a price check.
_MARKETPLACE_MERCHANTS = {"flipkart", "amazon"}


def _is_marketplace_merchant(name: str) -> bool:
    """True when a merchant name belongs to a third-party marketplace platform.
    Substring match on the *name*, so "Amazon.in" and "Flipkart SmartBuy" are
    both caught."""
    lowered = (name or "").lower()
    return any(m in lowered for m in _MARKETPLACE_MERCHANTS)


def _priority_merchant_anchor(results: list[dict], merchant_key: str = "merchant") -> float | None:
    """Highest price quoted by a trusted, non-marketplace merchant among these
    results, if any. Used to anchor the outlier check on a real reference
    price instead of the survivor pool's own median — which a majority of
    clone listings can otherwise skew low enough that no clone reads as an
    outlier relative to the others. Marketplace platforms (Flipkart, Amazon)
    are excluded from anchoring since a price attributed to them isn't
    necessarily the platform's own — it can be any third-party seller's.

    Reuses `_is_trusted_merchant`'s brand-signature match (not exact-name
    comparison) — real listings say "JioMart Electronics", not bare
    "JioMart", and an exact match would silently never anchor on them.

    The marketplace exclusion is applied to the *merchant name*, not by
    subtracting entries from the whitelist — the Gyftr brand list also
    contains `amazonfresh` and `amazonprimemembership`, so removing the one
    string "amazon" wouldn't reliably keep Amazon-attributed listings from
    anchoring."""
    whitelist = _load_trusted_merchants()
    prices = [
        r.get("price") for r in results
        if r.get("price")
        and not _is_marketplace_merchant(r.get(merchant_key) or "")
        and _is_trusted_merchant(r.get(merchant_key) or "", whitelist)
    ]
    return max(prices) if prices else None


def _outlier_filter(results: list[dict]) -> tuple[list[dict], int]:
    """Remove results priced below 40% of median. Returns (filtered, removed_count)."""
    prices = [r.get("price") for r in results if r.get("price")]
    if len(prices) < 4:
        return results, 0
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    mid = n // 2
    median = sorted_prices[mid] if n % 2 else (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    threshold = 0.4 * median
    filtered = [
        r for r in results
        if (r.get("price") or 0) >= threshold or not r.get("price")
    ]
    return filtered, len(results) - len(filtered)


def _dedup_by_merchant(results: list[dict]) -> list[dict]:
    """Per merchant, keep only the lowest-priced result — except a `_pinned`
    entry (the exact listing the user selected on the Product Picker) always
    wins its merchant slot outright, regardless of price. That entry was
    already verified once at picker time; a broader downstream search
    finding a different price for the same merchant name is not grounds to
    silently swap it out from under a selection the user already made.

    Keyed on `_brand_signature`, not the raw merchant string: the picker's
    search endpoint and the route-builder's product-detail endpoint can name
    the same store differently ("Amazon" vs "Amazon.in") — an exact-string
    key would let both through as two separate "routes" for one merchant."""
    seen: dict[str, dict] = {}
    for r in results:
        key = _brand_signature(r.get("merchant") or "")
        if not key:
            continue
        if seen.get(key, {}).get("_pinned"):
            continue
        price = r.get("price") or float("inf")
        if r.get("_pinned") or key not in seen or price < (seen[key].get("price") or float("inf")):
            seen[key] = r
    return list(seen.values())


def _priority_sort(results: list[dict]) -> list[dict]:
    """Priority merchants first (in declared order), then rest sorted by price."""
    def _key(r: dict) -> tuple:
        src = (r.get("merchant") or "").lower()
        for i, m in enumerate(PRIORITY_MERCHANTS):
            if m.lower() in src:
                return (i, 0.0)
        return (len(PRIORITY_MERCHANTS), r.get("price") or float("inf"))
    return sorted(results, key=_key)


# ── offer normalization ─────────────────────────────────────────────────────────

def _merchant_name(offer: dict) -> str:
    """Extract a merchant display name defensively — the SearchApi offer shape
    exposes merchant either as {"name": ...} or as a bare string."""
    merchant = offer.get("merchant")
    if isinstance(merchant, dict):
        return merchant.get("name") or ""
    if isinstance(merchant, str):
        return merchant
    # Fallbacks seen across engines.
    return offer.get("seller") or offer.get("store_name") or offer.get("seller_name") or ""


def _offer_price(offer: dict) -> float | None:
    """Prefer a numeric extracted_price field, else parse the display price."""
    for numeric_key in ("extracted_price", "price_extracted", "extracted_total_price"):
        val = offer.get(numeric_key)
        if isinstance(val, (int, float)):
            return float(val)
    return parse_price(offer.get("price") or offer.get("total_price"))


def _build_candidates(detail: dict, source_token: str | None = None) -> list[dict]:
    """`source_token` (internal-only, not exposed to the frontend — same
    pattern as `_pinned`) records which product_token this candidate's
    get_product() call came from, so a later step can find "the real,
    already-fetched offer for exactly the listing the user picked" rather
    than matching on merchant name alone (see _find_pdp_candidate)."""
    product = detail.get("product") or {}
    title = product.get("title") or detail.get("title") or ""
    candidates = []
    for offer in detail.get("offers") or []:
        merchant = _merchant_name(offer)
        price = _offer_price(offer)
        candidates.append({
            "merchant": merchant,
            "price": price,
            "title": title,
            "sellers": [{
                "link": offer.get("link"),
                "delivery": offer.get("delivery_price") or offer.get("delivery"),
            }],
            "match_type": "Listed",
            "_source_token": source_token,
        })
    return candidates


# ── route builder (ported from pipeline._build_routes) ──────────────────────────

def _card_fomo_for_route(route: dict) -> dict | None:
    card_fomo = card_service.best_card_for_purchase(
        merchant=route["merchant"],
        purchase_amount=route["final_cost"],
        has_voucher=route.get("voucher") is not None,
    )
    if not card_fomo:
        return None
    return {
        "card_name": card_fomo["card_name"],
        "actual_saving": card_fomo["actual_saving"],
        "final_cost_with_card": round(route["final_cost"] - card_fomo["actual_saving"], 2),
        "cap_amount": card_fomo["cap_amount"],
        "cap_period": card_fomo["cap_period"],
        "apply_url": card_fomo.get("apply_url"),
    }


def _build_routes(results: list[dict], vouchers: list[dict]) -> dict:
    """Merge results + vouchers into route objects sorted by final_cost.

    final_cost = voucher UPI effective price when a voucher exists, else the
    listed price (skip if neither). Dedups on (merchant, round(final_cost, 2)).
    An offline-only voucher can't be redeemed at its merchant's online listing,
    so it's surfaced as a separate "{merchant} (in-store)" route instead of
    decorating the online one. Attaches the best cashback card to every route
    actually returned (recommended + alternatives) — never affects sort order.
    """
    voucher_map = {v["merchant"].lower(): v for v in vouchers}
    routes = []
    seen: set[tuple] = set()

    def add_route(merchant, listed_price, final_cost, sellers, match_type, title, voucher):
        key = (merchant.lower(), round(final_cost, 2))
        if key in seen:
            return
        seen.add(key)
        routes.append({
            "merchant": merchant,
            "listed_price": listed_price,
            "final_cost": final_cost,
            "sellers": sellers,
            "match_type": match_type,
            "title": title,
            "voucher": voucher,
            "card_fomo": None,
        })

    for r in results:
        merchant = r.get("merchant") or ""
        listed_price = r.get("price")
        title = r.get("title") or ""
        v = voucher_map.get(merchant.lower())

        if v and v.get("offline_only"):
            # In-store price isn't independently known — the online listing's
            # price is the best available proxy.
            add_route(
                f"{merchant} (in-store)", listed_price, v["upi"]["effective_price"],
                [], "Listed", title, v,
            )
            v = None  # don't attach an in-store-only voucher to the online listing

        if v:
            final_cost = v["upi"]["effective_price"]
        elif listed_price:
            final_cost = listed_price
        else:
            continue  # no price, no voucher — unrankable

        add_route(merchant, listed_price, final_cost, r.get("sellers") or [], r.get("match_type") or "", title, v)

    routes.sort(key=lambda x: x["final_cost"])

    if not routes:
        return {"recommended": None, "alternatives": []}

    shown = routes[:4]
    for route in shown:
        card_fomo = _card_fomo_for_route(route)
        if card_fomo:
            route["card_fomo"] = card_fomo

    return {"recommended": shown[0], "alternatives": shown[1:4]}


# ── candidate filtering + variant grouping (revives engine/matcher.py-style
#    identity signals, applied at the picker stage instead of per-result) ───────

_ACCESSORY_KEYWORDS = [
    "case", "cover", "protector", "tempered glass", "screen guard", "screenguard",
    "skin", "sticker", "charger", "charging cable", "cable", "adapter",
    "pouch", "holder", "stand", "mount", "bumper", "shell", "wallet",
]

_BULK_LISTING_KEYWORDS = [
    "pieces", "pcs", "pack of", "combo", "set of", "pair of",
]

_QUERY_STOPWORDS = {
    "buy", "price", "online", "best", "new", "latest", "india", "offer",
    "offers", "deal", "deals", "for", "the", "a", "an", "with", "and",
}

# Generic model-tier words. These identify a variant ("iPhone 17 Pro" is not
# "iPhone 17"), so they stay REQUIRED in the normal strict match — they are
# only ever softened by the zero-result fallback in `_filter_and_group_candidates`,
# where a query has already been shown to name no real product.
#
# Why this matters: shoppers routinely conflate two product lines into a name
# that doesn't exist ("AirPods Pro Max" — Apple sells AirPods *Pro* and AirPods
# *Max*, never both). Requiring every word then drops all 22 genuine AirPods Max
# listings, and counterfeit sellers who *do* use the conflated name are the only
# survivors. Worse, removing the genuine listings also removes the trusted
# merchants the price anchor needs, so the junk filter is left with nothing to
# measure against.
#
# "air" is deliberately NOT in this list. It reads like a tier but carries
# identity: AirPods, MacBook Air, Air Max, Airdopes. Softening it collapses
# "air pods pro max" down to the single word "pods", which matches every
# generic earbud clone sold ("Swiss Military Pods Pro Max" and friends).
_QUALIFIER_TOKENS = frozenset({
    "pro", "max", "plus", "ultra", "mini", "lite", "se",
})


def _token_variants(tokens: list[str]) -> list[list[str]]:
    """The query's own tokens, then each way of merging one adjacent pair.

    Shoppers space out compound product names — "air pods" for AirPods, "power
    bank" for powerbank, "smart watch" for smartwatch. Word-boundary matching
    treats those as unrelated to the listings ("\\bpods\\b" does not match
    "AirPods", and "\\bairpods\\b" does not match "Air Pods"), so *nothing*
    matches and the search falls through to its last-resort behaviour.

    Merging adjacent pairs recovers the intended product without an alias table
    for any particular brand. Bounded at n-1 extra attempts, and only ever used
    to widen a search that already found nothing.
    """
    variants = [tokens]
    for i in range(len(tokens) - 1):
        variants.append(tokens[:i] + [tokens[i] + tokens[i + 1]] + tokens[i + 2:])
    return variants

_MAX_CANDIDATES = 8  # keep the picker scannable even when grouping can't fully dedup

# Generic spec/marketing words that don't identify a distinct product/variant —
# used to find the words a title has *beyond* the query, so different sellers'
# phrasing of the exact same model (spec dumps, "for men", strap material...)
# collapses into one picker card instead of one row per seller.
_MARKETING_FILLER_WORDS = {
    "with", "for", "and", "the", "true", "truly", "wireless", "earbuds", "earbud",
    "bluetooth", "headphones", "buds", "tws", "smartwatch", "smartwatches",
    "smart", "watch", "watches", "display", "amoled", "battery", "charge",
    "charging", "fast", "playback", "mode", "tech", "quad", "mics", "mic",
    "resistance", "water", "low", "latency", "beast", "signature", "sound",
    "support", "app", "music", "ad", "free", "stream", "via", "type", "usb",
    "faces", "calling", "wellness", "ai", "coach", "premium", "design",
    "functional", "crown", "enx", "iwp", "asap", "active", "noise",
    "cancellation", "cancelling", "in", "ear", "over", "beats", "genuine",
    "original", "official", "new", "latest", "compatible", "silicone",
    "dial", "unisex", "men", "women", "girls", "boys", "bt", "dp",
    "strap", "leather", "steel", "mesh", "rubber", "metal", "band",
}

# Number+unit phrases (screen size, battery life, ANC depth, etc.) stripped as
# a whole phrase before tokenizing, so "1.93inch" doesn't leak a bare "1".
_SPEC_PHRASE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm|cm|inch|in|hz|khz|mhz|db|ms|dpi|mp|mah|hrs|hr|hours|hour|h|v|w|nits)\b"
)

_COLOR_WORDS = [
    "black", "white", "blue", "red", "green", "yellow", "purple", "pink",
    "gold", "silver", "grey", "gray", "titanium", "graphite", "midnight",
    "starlight", "rose", "orange", "beige", "brown", "teal", "navy", "coral",
]

_STORAGE_RE = re.compile(r"\b(\d+)\s?(gb|tb)\b")

# A seller listing can bundle two different SKUs behind one slash (e.g. a
# WooCommerce variant page titled "AirPods Pro 3/AirPods 3") — split on it so
# each half can be checked independently instead of letting the other half's
# words paper over a mismatch.
_SEGMENT_SPLIT_RE = re.compile(r"\s*/\s*")


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())


def _is_accessory(title: str) -> bool:
    normalized = _norm_title(title)
    return any(kw in normalized for kw in _ACCESSORY_KEYWORDS)


def _is_bulk_listing(title: str) -> bool:
    normalized = _norm_title(title)
    return any(kw in normalized for kw in _BULK_LISTING_KEYWORDS)


def _is_latin_dominant(title: str) -> bool:
    letters = [c for c in (title or "") if c.isalpha()]
    if not letters:
        return True
    latin = sum(1 for c in letters if c.isascii())
    return latin / len(letters) >= 0.5


def _required_tokens(query: str) -> list[str]:
    """Query tokens the candidate title must contain, minus brand names and
    generic stopwords — e.g. "Boat Airdopes 141" -> ["airdopes", "141"]."""
    tokens = re.findall(r"[a-z0-9]+", (query or "").lower())
    return [t for t in tokens if t not in KNOWN_BRANDS and t not in _QUERY_STOPWORDS]


def _is_bare_modifier_segment(segment: str) -> bool:
    """True if a "/"-separated title segment is just a trailing storage/color/
    bare-number continuation of the previous segment (e.g. the "512GB" in
    "256GB/512GB"), not an independent product-name claim."""
    normalized = _norm_title(segment)
    stripped = _STORAGE_RE.sub(" ", normalized)
    words = stripped.split()
    return all(w.isdigit() or w in _COLOR_WORDS for w in words)


def _token_pattern(token: str) -> str:
    """A bare generation/model number like "2" must also match its ordinal
    form in a listing title ("2nd Generation") — sellers routinely phrase the
    same product differently, and rejecting the ordinal phrasing would
    incorrectly filter out genuine listings while admitting sloppier ones
    that happen to repeat the bare digit instead.

    A fused alphanumeric model name like "pr100" must also match its spaced
    phrasing ("Tissot PR 100") — `_token_variants` merges spaced query words
    into fused ones but nothing splits a fused query word back apart, so
    without this a "PR100" search can never match the sellers who write
    "PR 100" and the whole search collapses to zero results."""
    if token.isdigit():
        return rf"\b{re.escape(token)}(?:st|nd|rd|th)?\b"
    parts = re.findall(r"[a-z]+|\d+", token)
    if len(parts) > 1:
        return r"\b" + r"\s?".join(re.escape(p) for p in parts) + r"\b"
    return rf"\b{re.escape(token)}\b"


def _matches_required_tokens(title: str, tokens: list[str]) -> bool:
    """Word-boundary match (not raw substring) — a required token like "17e"
    must not be satisfied by "17" appearing inside an unrelated word, and a
    different-but-similar product (e.g. "iPhone 16e" against a required "17e"
    token) must not slip through.

    A title with multiple "/"-separated segments (e.g. a seller listing
    bundling two SKUs as "AirPods Pro 3/AirPods 3") must have every
    non-modifier segment independently satisfy the required tokens — otherwise
    a listing that also names a different, non-matching product would still
    pass just because the *other* half happens to mention the right words.
    """
    def _segment_matches(text: str) -> bool:
        normalized = _norm_title(text)
        return all(re.search(_token_pattern(t), normalized) for t in tokens)

    segments = _SEGMENT_SPLIT_RE.split(title or "")
    if len(segments) <= 1:
        return _segment_matches(title)
    return all(_segment_matches(seg) for seg in segments if not _is_bare_modifier_segment(seg))


def _matches_relaxed_tokens(title: str, strong: list[str], qualifiers: list[str]) -> bool:
    """Looser sibling of `_matches_required_tokens`, used only by the zero-result
    fallback. Every identifying token must still be present; the model-tier
    qualifiers are satisfied by *any one* of them rather than all.

    So "airpods pro max" still requires "airpods", but accepts a title carrying
    either "pro" or "max" — surfacing both real product lines and letting the
    user pick, instead of returning nothing. A query with nothing but
    qualifiers keeps the strict all-of behaviour, since there is no identity
    left to anchor on.
    """
    if not strong:
        return False
    normalized = _norm_title(title)
    if not all(re.search(_token_pattern(t), normalized) for t in strong):
        return False
    if not qualifiers:
        return True
    return any(re.search(_token_pattern(t), normalized) for t in qualifiers)


def _distinguishing_words(title: str, exclude: set) -> frozenset:
    """Words in the title beyond the query's own tokens, known brand names,
    and generic spec/marketing filler. If nothing distinguishing survives,
    different sellers' phrasing of the same base product shares this same
    (empty) key and collapses into one picker card."""
    # Strip spec phrases (e.g. "1.93inch") from the raw text before _norm_title
    # destroys the decimal point — otherwise "1.93inch" splits into a bare "1"
    # that the regex can no longer recognize as part of a unit phrase.
    stripped_raw = _SPEC_PHRASE_RE.sub(" ", (title or "").lower())
    words = re.findall(r"[a-z0-9]+", _norm_title(stripped_raw))
    return frozenset(
        w for w in words
        # keep single-digit tokens (real model-version numbers like "Smart 4"
        # vs "Smart 3") but drop stray single-letter fragments (leftover "c"
        # from a stripped "USB C", etc.)
        if (len(w) > 1 or w.isdigit()) and w not in exclude and w not in _MARKETING_FILLER_WORDS
    )


def _extract_variant_signature(title: str, exclude: set) -> tuple:
    normalized = _norm_title(title)
    storage_m = _STORAGE_RE.search(normalized)
    storage = f"{storage_m.group(1)}{storage_m.group(2)}" if storage_m else None
    color = next((c for c in _COLOR_WORDS if re.search(rf"\b{re.escape(c)}\b", normalized)), None)
    extra_words = _distinguishing_words(title, exclude | {storage, color} - {None})
    return (extra_words, storage, color)


def _filter_and_group_candidates(candidates: list[dict], query: str) -> tuple[list[dict], bool]:
    """Drop accessories/bulk-listings/wrong-model/non-English junk, then group
    same-variant listings from different sellers into one picker card each.

    Grouping is on an exact signature match (distinguishing words beyond the
    query + storage + color) — not fuzzy similarity — so a title with a real
    extra identifier (a submodel/product-line name the query didn't mention)
    gets its own group rather than risking a false merge into the wrong
    variant. Titles with nothing extra beyond generic spec/marketing filler
    share the same signature and collapse into one card, so different
    sellers' phrasing of the exact same model doesn't read as a vendor list.
    Falls back to the unfiltered candidate list if filtering would wipe out
    everything (a degraded-but-honest result beats a false "nothing found").

    Returns ``(candidates, approximate)`` — ``approximate`` is True when the
    exact-name match found nothing and the relaxed qualifier fallback below
    supplied the results instead, so the caller can label them as a closest
    match rather than passing them off as exactly what was asked for.
    """
    tokens = _required_tokens(query)
    exclude = set(tokens) | set(KNOWN_BRANDS)
    hygienic = [
        c for c in candidates
        if c.get("title")
        and not _is_accessory(c["title"])
        and not _is_bulk_listing(c["title"])
        and _is_latin_dominant(c["title"])
    ]
    def _vet(pool: list[dict]) -> list[dict]:
        """Trust + price sanity. Runs identically on the strict pool and on the
        relaxed fallback pool, so the fallback is held to exactly the same
        standard — it widens *what counts as the product*, never what counts as
        a trustworthy seller or a believable price."""
        # Drop listings from sellers outside the trusted-merchant whitelist —
        # the same check already applied at the route-building stage, applied
        # here too so counterfeit/clone listings (e.g. generic marketplace
        # sellers undercutting a genuine product by 10x) never reach the picker
        # at all. No fallback to the unfiltered list on this stage: an
        # untrusted-only result set means no trustworthy candidate exists,
        # which is a better outcome than surfacing a counterfeit (see
        # _filter_trusted_only's docstring / CLAUDE.md rule #1 — a wrong result
        # is worse than none).
        pool = _filter_trusted_only(pool, merchant_key="source")

        # If a trusted, non-marketplace merchant quoted a price here, anchor
        # the price-sanity check on that instead of the survivor pool's own
        # median — clone listings routinely outnumber the one genuine listing
        # for a query, which otherwise drags the median low enough that no
        # clone reads as an outlier relative to the others. No anchor means no
        # such merchant showed up — falls back to the median check unchanged.
        anchor = _priority_merchant_anchor(pool, merchant_key="source")
        if anchor is not None:
            threshold = 0.4 * anchor
            pool = [c for c in pool if (c.get("price") or 0) >= threshold or not c.get("price")]

        # Defense-in-depth against price anomalies within the now-trusted set
        # (e.g. a stale/broken scrape price) — same 40%-of-median threshold
        # already used for L1 route results.
        pool, _ = _outlier_filter(pool)
        return pool

    # Widening ladder. Each rung loosens what counts as *the product*; none of
    # them ever loosens what counts as a trustworthy seller or a believable
    # price, because every rung goes through `_vet`.
    #
    #   1. every query word present, as typed
    #   2. every query word present, with one adjacent pair merged
    #      ("air pods pro max" -> "airpods pro max")
    #   3. identifying words present, model-tier qualifiers softened
    #      (for names that don't exist, like "AirPods Pro Max")
    #   4. nothing product-specific matched — vetted raw pool, then empty
    #
    # Rungs 2-4 only run when everything above them came back empty, so any
    # query that already works keeps its exact current results.
    variants = _token_variants(tokens) if tokens else [[]]
    approximate = False
    survivors: list[dict] = []
    matched_titles = False

    # Rung 1 + 2 — exact word match, then spacing variants.
    for variant in variants:
        exact = [
            c for c in hygienic
            if not variant or _matches_required_tokens(c["title"], variant)
        ]
        if not exact:
            continue
        matched_titles = True
        survivors = _vet(exact)
        if survivors:
            break

    # Rung 3 — the query probably names a product that doesn't exist: two
    # product lines conflated into one name. Requiring every word then keeps
    # only the counterfeit sellers who use the invented name, and removing the
    # genuine listings also removes the trusted merchants the price anchor
    # needs, so the junk filter has nothing to measure against.
    #
    # Deliberately gated on a wiped-out result rather than applied by default:
    # unconditionally it would inflate "puma skyrocket lite 2" from 8 results
    # to 20 by admitting non-Lite variants.
    if not survivors:
        for variant in variants:
            strong = [t for t in variant if t not in _QUALIFIER_TOKENS]
            qualifiers = [t for t in variant if t in _QUALIFIER_TOKENS]
            if not (strong and qualifiers):
                continue
            relaxed = _vet([
                c for c in hygienic
                if _matches_relaxed_tokens(c["title"], strong, qualifiers)
            ])
            if relaxed:
                survivors = relaxed
                approximate = True
                break

    # Rung 4 — nothing product-specific matched at all. Show the vetted pool
    # rather than the raw one.
    #
    # This used to `return candidates` outright: no trusted-merchant check, no
    # price anchor, no outlier filter. That is what put ₹650 "Airpods Pro Max"
    # listings in front of customers searching for a ₹60,000 product, and it
    # contradicts CLAUDE.md rule #1 — a wrong result is worse than no result.
    # Vetting it keeps the original intent (something beats a bare "nothing
    # found") without ever parading an untrusted seller at an absurd price.
    if not survivors and not matched_titles:
        vetted_raw = _vet(hygienic)
        if vetted_raw:
            survivors = vetted_raw
            approximate = True

    if not survivors:
        return [], False

    groups: dict = {}
    order: list = []
    for c in survivors:
        key = _extract_variant_signature(c["title"], exclude)
        if key not in groups:
            groups[key] = c
            order.append(key)
        else:
            existing = groups[key]
            if c.get("price") is not None and (existing.get("price") is None or c["price"] < existing["price"]):
                groups[key] = c

    # Keep Google's own relevance order — the genuine product ranks near the
    # top there. Sorting the picker by price instead floats the cheapest
    # listing up, which is usually a refurb/clone/wrong-variant, so the wrong
    # product leads the list.
    grouped = [groups[k] for k in order]
    return grouped[:_MAX_CANDIDATES], approximate


# ── source brand inference (best-effort, for the identity box) ───────────────────

def _infer_brand(name: str) -> str:
    lowered = (name or "").lower()
    for known in KNOWN_BRANDS:
        if re.search(r"\b" + re.escape(known) + r"\b", lowered):
            for word in name.split():
                if word.lower() == known:
                    return word
            return known
    return ""


# ── public orchestrator ──────────────────────────────────────────────────────────

def _product_candidate(p: dict) -> dict:
    """Shape a google_shopping result into a product the user can pick from."""
    price = None
    for numeric_key in ("extracted_price", "price_extracted"):
        val = p.get(numeric_key)
        if isinstance(val, (int, float)):
            price = float(val)
            break
    if price is None:
        price = parse_price(p.get("price"))
    return {
        "product_token": p.get("product_token"),
        "title": p.get("title") or "",
        "price": price,
        "price_raw": p.get("price"),
        "thumbnail": p.get("thumbnail") or p.get("image"),
        "source": p.get("seller") or p.get("source") or p.get("store") or "",
        "rating": p.get("rating"),
        "reviews": p.get("reviews"),
    }


_URL_QUERY_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

# Path segments that are store routing machinery, not product words.
_URL_ROUTING_SEGMENTS = frozenset({"dp", "gp", "product", "p", "d", "b", "s", "itm", "buy", "ip"})


def _query_from_url(url: str) -> str | None:
    """Human-readable product words from a store URL's slug ("…/Titan-Neo-
    Analog-Watch-Men/dp/B0ABC12345" -> "Titan Neo Analog Watch Men"), or None
    when the URL carries none (short links, bare /dp/ASIN paths).

    A pasted link used to go through token matching as-is, and its tokens
    ("https", "www", "dp", the ASIN…) appear in no listing title — so the
    identity rungs could never match and every link search fell through to
    the last-resort trust-only pool, with no check that results were even the
    linked product. Searching by the slug words instead puts link input on
    exactly the same footing as typed text."""
    segments = [unquote(s) for s in urlsplit(url).path.split("/") if s]
    best_words: list[str] = []
    best_score = 0
    for seg in segments:
        seg = seg.lower()
        if seg in _URL_ROUTING_SEGMENTS or seg.startswith("ref="):
            continue
        words = [
            w for w in re.findall(r"[a-z0-9]+", seg)
            # Opaque ids (ASINs like "b0abc12345", Flipkart "itm…" ids) carry
            # no product words — a long token mixing letters and digits is an
            # id, not a model name like "pr100".
            if not (len(w) >= 9 and any(ch.isdigit() for ch in w))
        ]
        score = sum(1 for w in words if not w.isdigit() and len(w) >= 3)
        if score > best_score:
            best_score = score
            best_words = words
    # One real word could just be a brand/category path segment ("/titan/");
    # require two before trusting the slug as a product name.
    if best_score < 2:
        return None
    return " ".join(best_words)


# Realistic browser UA — bare httpx/python UAs get bot-walled by most stores.
_TITLE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

# Product-name sources in the page head, best first. Each returns the name in
# group 1. og:title/twitter:title support both attribute orders (content before
# or after the property/name attribute).
_META_TITLE_RES = [
    re.compile(
        r"""<meta[^>]+(?:property|name)=["']og:title["'][^>]+content=["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']og:title["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+(?:property|name)=["']twitter:title["'][^>]+content=["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']twitter:title["']""",
        re.IGNORECASE,
    ),
    re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
]

# Titles that mean "we didn't get the product page" — bot walls, error pages, or
# a bare store name. Lower-cased substring match; any hit rejects the title so
# the caller falls through to slug extraction instead of searching junk.
_BAD_TITLE_MARKERS = (
    "robot check",
    "access denied",
    "attention required",
    "are you a human",
    "just a moment",
    "captcha",
    "page not found",
    "404",
    "error",
    "sign in",
    "log in",
)
_BARE_STORE_TITLES = frozenset(
    {"amazon.in", "amazon", "flipkart", "flipkart.com", "myntra", "nykaa", "ajio"}
)

# ── live Amazon price read (Amazon only — see search_service module docstring
#    for why the react-migration removed live page price extraction entirely,
#    and CLAUDE.md bug 1) ──────────────────────────────────────────────────────

_AMAZON_HOST_RE = re.compile(r"(?:^|\.)amazon\.(?:in|com)$", re.IGNORECASE)

# Amazon's buybox price block. Scoping the price regex to a window starting
# here (rather than searching the whole page) is the guard against matching
# the wrong number — the page also shows the crossed-out MRP and a "₹X off"
# badge, both of which can reuse the same "a-price-whole" CSS class elsewhere
# on the page. Ported from the deleted extractor/zyte_client.py, which had to
# solve the exact same problem.
_AMAZON_PRICE_ANCHOR = "corePriceDisplay_desktop_feature_div"
_AMAZON_PRICE_WINDOW = 3000
_AMAZON_PRICE_RE = re.compile(r'class="[^"]*a-price-whole[^"]*"[^>]*>([\d,]+)<')

# For these categories only, a matched price under ₹1000 is almost certainly a
# discount amount, not the real price — never apply this floor generally, or
# a genuinely cheap item gets its real price thrown out.
_AMAZON_DEVICE_URL_RE = re.compile(
    r"\b(macbook|iphone|ipad|laptop|macmini|imac)\b", re.IGNORECASE
)


def _is_amazon_host(host: str) -> bool:
    return bool(_AMAZON_HOST_RE.search((host or "").lower()))


def _extract_amazon_price(markup: str, *urls: str) -> float | None:
    """Amazon buybox ("pay now") price from plain page HTML, or None.

    Two-stage regex, same approach the deleted zyte_client._amazon_html_fallback
    used: scoped first to a window right after the buybox block so a "₹X off"
    badge or the struck-through MRP elsewhere on the page can't match instead,
    falling back to an unscoped search only if that block isn't present at all.
    """
    m = None
    anchor_idx = markup.find(_AMAZON_PRICE_ANCHOR)
    if anchor_idx != -1:
        m = _AMAZON_PRICE_RE.search(
            markup[anchor_idx:anchor_idx + _AMAZON_PRICE_WINDOW]
        )
    if not m:
        m = _AMAZON_PRICE_RE.search(markup)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    if not raw.isdigit():
        return None
    price = float(raw)
    if price < 1000 and any(_AMAZON_DEVICE_URL_RE.search(u or "") for u in urls):
        return None
    return price


# ── live price read for other vendors, via schema.org structured data ──────────
#
# Amazon needed hand-rolled markup regex above because it doesn't reliably
# expose a standard price field. Most other storefronts DO embed a
# schema.org "Product" block (the same JSON-LD search engines read for rich
# results) with a real, current offer price — a generic, vendor-agnostic
# read, not a per-site scraper. Each host below has been individually
# fetched and hand-verified (price checked against the page's own
# MRP/discount fields, not just "a number was found") before being added —
# see CLAUDE.md's "Live price-on-paste vendor coverage" note for the current
# status of every vendor NOT in this dict and why.
_JSONLD_MERCHANT_HOSTS = {
    # Verified 2026-07-22: myntra.com's JSON-LD offers.price matched its own
    # page's `discountedPrice` field exactly (not `mrp`) on a real product.
    "myntra.com": "Myntra",
}

_LDJSON_BLOCK_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _jsonld_host_merchant(host: str) -> str | None:
    host = (host or "").lower()
    for suffix, name in _JSONLD_MERCHANT_HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return name
    return None


def _extract_jsonld_price(markup: str) -> float | None:
    """The first schema.org Product -> Offer price in a page's own structured
    data, or None. Standard, vendor-agnostic — unlike _extract_amazon_price,
    no per-site markup knowledge needed, because the site itself is already
    labeling this number as "the offer price" for search engines to read."""
    for block in _LDJSON_BLOCK_RE.findall(markup):
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict) or node.get("@type") != "Product":
                continue
            offers = node.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict):
                price = parse_price(offers.get("price"))
                if price is not None:
                    return price
    return None


def _fetch_url_page(url: str) -> tuple[str | None, float | None, str | None]:
    """One GET for a pasted link (redirects resolved — amzn.in -> amazon.in).
    Returns (title, live_price, live_merchant).

    title: og:title -> twitter:title -> <title>, scanned over the first
    200_000 chars, rejected via _BAD_TITLE_MARKERS/_BARE_STORE_TITLES exactly
    as this function's original title-only version always did.

    live_price/live_merchant: a verified live price and its merchant name,
    read via _extract_amazon_price (Amazon's own hand-rolled markup — see
    that function) or _extract_jsonld_price (every other host currently in
    _JSONLD_MERCHANT_HOSTS, via each page's own schema.org structured data).
    Checked against the full response body (the price block can sit past the
    200_000-char title-scan cap on a large page). (None, None) for every
    host not covered and on any failure — never raises; a failure here must
    fall straight back to today's title/slug-only search, not break it.
    """
    try:
        timeout = float(get_settings().LINK_TITLE_TIMEOUT)
        with httpx.Client(
            timeout=timeout, follow_redirects=True, headers=_TITLE_FETCH_HEADERS
        ) as client:
            resp = client.get(url)
        logger.info(
            "[url-search] page-fetch %s -> final=%s status=%s",
            url, resp.url, resp.status_code,
        )
        if resp.status_code != 200:
            return None, None, None
        full_markup = resp.text
        # The title lives in <head>, early in the document; cap the text we
        # scan for it so a huge product page doesn't turn into a huge regex
        # pass. The price block can sit further down, so it's read from the
        # full body below instead.
        markup = full_markup[:200_000]
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("[url-search] page-fetch failed for %s: %s", url, exc)
        return None, None, None

    title = None
    for pattern in _META_TITLE_RES:
        m = pattern.search(markup)
        if not m:
            continue
        candidate = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        if len(candidate) < 3:
            continue
        low = candidate.lower()
        if low in _BARE_STORE_TITLES or any(b in low for b in _BAD_TITLE_MARKERS):
            logger.info("[url-search] rejected page title %r (bot-wall/bare store)", candidate)
            continue
        title = candidate
        logger.info("[url-search] using page title: %r", title)
        break
    if title is None:
        logger.info("[url-search] no usable title found in page")

    host = (resp.url.host or "").lower()
    price = None
    merchant = None
    if _is_amazon_host(host):
        price = _extract_amazon_price(full_markup, url, str(resp.url))
        merchant = "Amazon"
        logger.info("[url-search] amazon live price: %s", price)
    else:
        jsonld_merchant = _jsonld_host_merchant(host)
        if jsonld_merchant:
            price = _extract_jsonld_price(full_markup)
            merchant = jsonld_merchant
            logger.info("[url-search] %s live price: %s", jsonld_merchant, price)
    if price is None:
        merchant = None

    return title, price, merchant


# Prefix marking a candidate's product_token as synthetic (not a real
# SearchApi.io token) — used both to build the token and, in
# build_routes_for_token, to recognize and skip a get_product() lookup that
# would otherwise waste a paid SearchApi call on an ID nothing can resolve.
_LIVE_PRICE_TOKEN_PREFIX = "live-price:"


def _live_price_candidate(url: str, title: str | None, price: float, source: str) -> dict:
    """Shape a live-fetched price (Amazon's hand-rolled read or another
    vendor's structured-data read) like `_product_candidate`'s output, so it
    can sit in the same picker list as any ordinary candidate.

    `source` is deliberately the plain merchant name ("Amazon", "Myntra") —
    not decorated with "verified"/"your link" text. Once picked, this string
    becomes the merchant key for the Gyftr voucher lookup, the cashback card
    lookup, the priority-merchant sort, and the per-merchant dedup in
    build_routes_for_token — all exact/prefix matches on this string, not a
    fuzzy one. A decorated string would silently break those and could let a
    second, differently-priced row for the same merchant reappear alongside
    this one, reintroducing a version of the bug this candidate exists to
    prevent. The "this one is verified" signal is carried in `product_token`
    instead."""
    token = _LIVE_PRICE_TOKEN_PREFIX + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return {
        "product_token": token,
        "title": title or _query_from_url(url) or f"{source} product",
        "price": price,
        "price_raw": f"₹{price:,.0f}",
        "thumbnail": None,
        "source": source,
        "rating": None,
        "reviews": None,
    }


def _clean_url_for_search(url: str) -> str:
    """Strip query params and fragment from a link, leaving scheme+host+path.

    The last-resort fallback when neither the page title nor the slug yields a
    product name: searching the bare URL is weak, but at least tracking params
    (?tag=…&ref=…) shouldn't pollute the search string."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")) or url


def search_candidates(query: str) -> dict:
    """Step 1 of the two-step flow: google_shopping search only.

    Returns the list of candidate products the user picks from — does NOT run
    the (slow) google_product call. Never raises.

    ``approximate`` is True when nothing matched the query exactly and these
    are the closest trustworthy matches instead — the caller should say so
    rather than presenting them as the thing that was asked for."""
    query = (query or "").strip()
    out = {"query": query, "products": [], "error": None, "approximate": False}
    if not query:
        out["error"] = "Empty query."
        return out
    # A pasted link is turned into a search query without scraping the product:
    # its page title first, then its slug words, then the bare link. The
    # response still echoes the original input in ``query``. A link that yields
    # nothing better than the bare URL lands in the trust-only pool and gets
    # labeled approximate.
    effective_query = query
    is_url = bool(_URL_QUERY_RE.match(query))
    live_candidate = None
    if is_url:
        # Three-layer link recognition, cheapest-reliable first:
        #   1. the page's own og:title (handles short/ID-only links),
        #   2. words from the URL slug,
        #   3. the bare link with tracking params stripped.
        # The same fetch also recovers a live price when the link is a page
        # we know how to read — see _fetch_url_page / _live_price_candidate.
        logger.info("[url-search] input is a link: %s", query)
        page_title, live_price, live_merchant = _fetch_url_page(query)
        effective_query = page_title
        layer = "page-title"
        if not effective_query:
            effective_query = _query_from_url(query)
            layer = "url-slug"
        if not effective_query:
            effective_query = _clean_url_for_search(query)
            layer = "raw-link"
        logger.info(
            "[url-search] searching via %s -> query=%r", layer, effective_query
        )
        if live_price is not None and live_merchant:
            live_candidate = _live_price_candidate(query, page_title, live_price, live_merchant)
            logger.info("[url-search] live %s price captured: %s", live_merchant, live_price)
    try:
        raw = searchapi_repository.search_products(effective_query)
        if raw.get("error"):
            # A live Amazon price stands on its own even if the broader
            # Google Shopping search is down — don't lose it to an
            # unrelated API failure.
            if live_candidate:
                out["products"] = [live_candidate]
                return out
            if is_url:
                logger.info("[url-search] google api error: %s", raw["error"])
            out["error"] = raw["error"]
            return out
        shopping_results = raw.get("shopping_results", [])
        if is_url:
            logger.info(
                "[url-search] google api returned %d raw result(s):",
                len(shopping_results),
            )
            for r in shopping_results:
                logger.info(
                    "[url-search]   raw: %r | %s | %s | token=%s",
                    r.get("title"),
                    r.get("seller") or r.get("source") or r.get("store"),
                    r.get("price"),
                    "yes" if r.get("product_token") else "no",
                )
        products = [
            _product_candidate(p)
            for p in shopping_results
            if p.get("product_token")
        ]
        products, approximate = _filter_and_group_candidates(products, effective_query)
        if live_candidate:
            # Added after filtering, not before: this candidate is the exact
            # page the user pasted, already "vetted" by the fact that it's
            # what they're looking at, so it shouldn't be at risk of getting
            # dropped by the trust/anchor/outlier checks the way an
            # unverified listing would be. Supersedes rather than duplicates
            # any (possibly stale) Amazon row the broader search also
            # surfaced under a differently-formatted name ("Amazon.in" vs
            # "Amazon") — _brand_signature already exists to recognize those
            # as the same merchant, so there's never two conflicting Amazon
            # prices shown.
            live_sig = _brand_signature(live_candidate["source"])
            products = [live_candidate] + [
                p for p in products
                if _brand_signature(p.get("source") or "") != live_sig
            ]
            approximate = False
        if not products:
            if is_url:
                logger.info("[url-search] no candidates after filtering")
            out["error"] = "No products found for that search."
            return out
        out["products"] = products
        out["approximate"] = approximate
        if is_url:
            logger.info(
                "[url-search] %d candidate(s)%s:",
                len(products), " (approximate)" if approximate else "",
            )
            for p in products:
                logger.info(
                    "[url-search]   - %r | %s | %s",
                    p.get("title"), p.get("source"), p.get("price"),
                )
    except Exception as e:  # never leak a stack trace
        if is_url:
            logger.info("[url-search] search error: %s: %s", type(e).__name__, e)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# Bounded number of get_product() detail calls per selected variant — keeps
# route resolution comprehensive without letting cost scale with however many
# listings Google happens to catalog for a given product.
_ROUTE_TOKEN_CAP = 2


def _refined_variant_candidates(variant_query: str) -> list[dict]:
    """A fresh, focused google_shopping search for the exact selected variant
    (not the original broad query) — surfaces the real set of sellers for
    that specific product, not just whatever Google associated with one
    representative listing. Cheap: same call the Product Picker's first
    search already uses. Returns lightweight {product_token, title, merchant,
    price} entries for filtering — no offer/link data yet, that's the
    expensive part. `title` is required here (not just for display) so the
    caller can identity-verify each candidate before ever fetching it."""
    raw = searchapi_repository.search_products(variant_query)
    if raw.get("error"):
        return []
    out = []
    for p in raw.get("shopping_results", []):
        token = p.get("product_token")
        if not token:
            continue
        price = None
        for numeric_key in ("extracted_price", "price_extracted"):
            val = p.get(numeric_key)
            if isinstance(val, (int, float)):
                price = float(val)
                break
        if price is None:
            price = parse_price(p.get("price"))
        out.append({
            "product_token": token,
            "title": p.get("title") or "",
            "merchant": p.get("seller") or p.get("source") or p.get("store") or "",
            "price": price,
        })
    return out


def _pinned_candidate(title: str, price: float | None, source: str, sellers: list[dict] | None = None) -> dict:
    """Build a candidate dict, in the same shape `_build_candidates` produces,
    for the exact listing the user selected on the Product Picker — tagged
    `_pinned` so `_dedup_by_merchant` keeps it regardless of what a broader
    downstream search finds for the same merchant. `sellers` carries a real
    purchase link when one could be recovered (see `_find_seller_link`
    below); the Product Picker's own cheap search never has a deep link on
    its own, only a price/title/source."""
    return {
        "merchant": source,
        "price": price,
        "title": title,
        "sellers": sellers or [],
        "match_type": "Listed",
        "_pinned": True,
    }


def _find_seller_link(candidates: list[dict], source: str) -> list[dict]:
    """Best-effort recovery of a real seller link for `source` from a
    candidate pool that may include merchants the trust filter would
    otherwise strip — used only to attach a working link to an already-
    pinned, already-priced candidate, never to admit an untrusted merchant
    as a route on its own. Fallback path only — see _find_pdp_candidate,
    which is tried first and is more precise (it verifies the candidate came
    from the exact picked listing's own product-detail fetch, not just a
    matching merchant name).

    Matches on `_brand_signature`, not a plain string/`_norm` equality — the
    picker's search endpoint and this function's own candidate pool (from
    the product-detail endpoint) can name the same store differently
    ("Amazon" vs "Amazon.in"); the fallback needs to recognize those as the
    same merchant just as much as `_dedup_by_merchant`/`_find_pdp_candidate`
    already do, or it silently returns no link at all for a store it should
    have found one for."""
    sig = _brand_signature(source)
    if not sig:
        return []
    for c in candidates:
        if _brand_signature(c.get("merchant") or "") == sig and c.get("sellers"):
            return c["sellers"]
    return []


def _find_pdp_candidate(
    candidates: list[dict], source_token: str, picked_source: str,
) -> dict | None:
    """Among candidates fetched from `product_token`'s own get_product() call
    (tagged `_source_token == source_token` by _build_candidates), return the
    one whose merchant identity matches `picked_source` — i.e. the real,
    already-fetched price+link pair for the exact listing the user picked,
    when one exists. Preferred over the picker's `picked_price` + a
    name-matched link (`_find_seller_link`): both fields here come from the
    same offer object, so they're guaranteed to describe the same listing,
    which the picked_price/_find_seller_link combination never guaranteed.

    Matches on `_brand_signature`, not `_norm` — this feeds the same
    merchant-slot identity `_dedup_by_merchant` keys on (also
    `_brand_signature`, so "Amazon" and "Amazon.in" are recognized as the
    same store here too), not a raw string-equality lookup like
    `_find_seller_link`'s. Requires a parsed price; when product_token's own
    fetch legitimately returned more than one offer under this merchant
    (different sellers/conditions), the lowest-priced one wins — the same
    tie-break `_dedup_by_merchant` already applies to ordinary candidates.

    For a live-price token (Amazon/Myntra link-paste, bug 1), `source_token`
    never matches any candidate's `_source_token` by construction — those
    tokens are never passed to get_product at all — so this always returns
    None for that path and callers fall straight through to the existing
    picked_price/_find_seller_link fallback, unchanged."""
    sig = _brand_signature(picked_source)
    if not sig:
        return None
    matches = [
        c for c in candidates
        if c.get("_source_token") == source_token
        and c.get("price") is not None
        and _brand_signature(c.get("merchant") or "") == sig
    ]
    if not matches:
        return None
    return min(matches, key=lambda c: c["price"])


def build_routes_for_token(
    product_token: str, query: str = "", title: str = "",
    picked_price: float | None = None, picked_source: str = "",
    picked_thumbnail: str | None = None,
) -> dict:
    """Step 2 of the two-step flow: resolve routes for a chosen Product Picker
    selection. Never raises — errors come back in the ``error`` field.

    Comprehensive route resolution: rather than trusting whatever sellers
    Google associated with the one representative `product_token`, runs a
    fresh focused search for the exact variant (`title`, when given — falls
    back to `query`), filters to trusted/sane candidates, and fetches real
    offers from a small capped number (`_ROUTE_TOKEN_CAP`) of the cheapest
    survivors — merging their offers into one candidate pool. Falls back to
    the originally selected token alone if the refined search comes up empty.

    `picked_thumbnail` is the Product Picker candidate's own image — carried
    through as-is (not re-derived per merchant) since it identifies the
    product itself, independent of which merchant's route ends up winning.
    """
    query = (query or "").strip()
    output = {
        "input": query,
        "mode": "text",
        "source": {
            "name": query, "brand": _infer_brand(query), "price": None,
            "condition": None, "image": picked_thumbnail,
        },
        "results": [],
        "size_comparison": None,
        "vouchers": [],
        "routes": {"recommended": None, "alternatives": []},
        "error": None,
    }
    if not product_token:
        output["error"] = "No product selected."
        return output

    try:
        variant_query = (title or query).strip()
        tokens_to_fetch: list[str] = []
        if variant_query:
            refined = _refined_variant_candidates(variant_query)
            # Same protections the Product Picker already has — a refined
            # search can surface accessories, bulk listings, and different-
            # but-similar products just as easily as the original search did,
            # and none of that should ever be fetched/merged just because
            # it's from a trusted seller at a plausible price.
            refined = [
                c for c in refined
                if c.get("title") and not _is_accessory(c["title"]) and not _is_bulk_listing(c["title"])
                and _is_latin_dominant(c["title"])
            ]
            required = _required_tokens(variant_query)
            if required:
                refined = [c for c in refined if _matches_required_tokens(c["title"], required)]

            # Require the same variant identity as the item actually picked
            # (storage/color/any other distinguishing word beyond the query's
            # own tokens and known brands) — the same signature check the
            # Product Picker itself uses to keep two different variants from
            # being treated as one product (_filter_and_group_candidates),
            # applied here to keep this broader re-search from merging a
            # different variant back in once the user has already told us
            # which one they picked. _matches_required_tokens above only
            # checks that the right words are present ("right brand/model"),
            # not that nothing extra/different distinguishes this listing
            # from the one picked — this closes that gap.
            variant_exclude = set(required) | set(KNOWN_BRANDS)
            picked_signature = _extract_variant_signature(variant_query, variant_exclude)
            refined = [
                c for c in refined
                if _extract_variant_signature(c["title"], variant_exclude) == picked_signature
            ]

            refined = _filter_trusted_only(refined)

            # Same priority-merchant price anchor as the Product Picker: this
            # narrower, freshly-searched pool can just as easily be dominated
            # by clones as the picker's own pool was, so the plain median
            # filter below isn't enough on its own.
            anchor = _priority_merchant_anchor(refined)
            if anchor is not None:
                threshold = 0.4 * anchor
                refined = [c for c in refined if (c.get("price") or 0) >= threshold or not c.get("price")]

            refined, _ = _outlier_filter(refined)
            refined.sort(key=lambda c: c.get("price") if c.get("price") is not None else float("inf"))
            tokens_to_fetch = [c["product_token"] for c in refined[:_ROUTE_TOKEN_CAP]]

        # The originally-selected token was already vetted against the full
        # Product Picker candidate pool (including its own trust/price
        # checks) — a narrower refined search finding something else is not
        # grounds to drop it, only to potentially outrank it later. Placed
        # FIRST, not appended: the fetch loop below claims `display_title`
        # from whichever token's fetch succeeds first, and the user's own
        # pick must win that claim whenever its own fetch succeeds — not
        # whichever refined-search token happened to load first.
        tokens_to_fetch = [product_token] + [t for t in tokens_to_fetch if t != product_token]

        candidates: list[dict] = []
        display_title = ""
        for token in tokens_to_fetch:
            # A live-fetched candidate (e.g. an Amazon price read straight off
            # a pasted link) never came from SearchApi.io, so it has no real
            # product_token to look up — skip it here rather than spending a
            # paid SearchApi call on an ID nothing can resolve. It still
            # reaches the route via the picked_price/picked_source pin below.
            if token.startswith(_LIVE_PRICE_TOKEN_PREFIX):
                continue
            detail = searchapi_repository.get_product(token)
            if detail.get("error"):
                continue
            product = detail.get("product") or {}
            display_title = display_title or product.get("title") or detail.get("title") or ""
            candidates.extend(_build_candidates(detail, source_token=token))

        if not candidates and not product_token.startswith(_LIVE_PRICE_TOKEN_PREFIX):
            # Refined search came up empty or every fetch failed — fall back
            # to the originally selected token alone.
            detail = searchapi_repository.get_product(product_token)
            if detail.get("error"):
                output["error"] = detail["error"]
                return output
            product = detail.get("product") or {}
            display_title = product.get("title") or detail.get("title") or ""
            candidates = _build_candidates(detail, source_token=product_token)

        # A live-fetched candidate with no other real candidates found has no
        # SearchApi.io title to display — fall back to the picker's own title
        # for it (same fallback the pin block below already uses for the
        # route's own title) rather than showing the raw pasted URL.
        display_title = display_title or (title if product_token.startswith(_LIVE_PRICE_TOKEN_PREFIX) else "")

        if display_title:
            output["source"]["name"] = display_title
            output["source"]["brand"] = _infer_brand(display_title) or output["source"]["brand"]

        # Kept from before the trust filter runs, purely so the pin block
        # below can find the exact merchant the user picked even if the
        # trust whitelist would otherwise strip it — that merchant's own
        # offer (fetched above for `product_token`, which is always included
        # in tokens_to_fetch) may not be on the trust whitelist even when the
        # listing itself is genuine, and a price with no way to reach it
        # fails the "executable by anyone" requirement for a route just as
        # much as a wrong price would.
        pre_filter_candidates = candidates

        # L1 guards.
        candidates = _filter_trusted_only(candidates)

        # Anchor on priority-merchant pricing here too — this is the pool
        # final routes get built from, so it's the last and most important
        # place to keep a merged-in clone from outranking the genuine,
        # already-vetted pick on price alone.
        anchor = _priority_merchant_anchor(candidates)
        if anchor is not None:
            threshold = 0.4 * anchor
            candidates = [c for c in candidates if (c.get("price") or 0) >= threshold or not c.get("price")]

        candidates, _removed = _outlier_filter(candidates)

        # Pin the exact listing the user selected on the Product Picker —
        # added AFTER trust/anchor/outlier filtering (it was already vetted
        # once at picker time, so it shouldn't be re-subjected to the same
        # checks) but BEFORE dedup, so it wins its merchant slot instead of
        # being silently replaced by whatever this broader search found for
        # that merchant, which is a different data source with no guarantee
        # of describing the same listing.
        #
        # Prefer the real, already-fetched price+link pair for this exact
        # listing (_find_pdp_candidate) when it exists — both fields there
        # come from the same offer, so they're guaranteed to describe the
        # same thing, unlike picked_price (the picker's own, earlier number)
        # glued to a link recovered only by matching merchant NAME
        # (_find_seller_link), which can point at a different listing under
        # that same store. Only fall back to that older combination when no
        # PDP-fetched offer for this exact pick survived (e.g. product_token's
        # own get_product() call failed, or it's a live-price token from the
        # Amazon/Myntra link-paste feature, which never has one by design).
        if picked_price is not None and picked_source:
            pdp_candidate = _find_pdp_candidate(pre_filter_candidates, product_token, picked_source)
            if pdp_candidate is not None:
                candidates.append(_pinned_candidate(
                    display_title or title or query,
                    pdp_candidate["price"],
                    picked_source,
                    pdp_candidate.get("sellers") or [],
                ))
            else:
                recovered_sellers = _find_seller_link(pre_filter_candidates, picked_source)
                candidates.append(_pinned_candidate(
                    display_title or title or query, picked_price, picked_source, recovered_sellers,
                ))

        candidates = _dedup_by_merchant(candidates)
        candidates = _priority_sort(candidates)

        output["results"] = candidates
        output["vouchers"] = voucher_service.build_deals(candidates, product_name=query or display_title)
        output["routes"] = _build_routes(candidates, output["vouchers"])

    except Exception as e:  # never leak a stack trace to the router
        output["error"] = f"{type(e).__name__}: {e}"

    return output


def get_product_detail(product_token: str) -> dict:
    """Raw google_product detail for a token, with offer prices normalized.

    Returns {"error": ...} on failure (no exceptions leak)."""
    detail = searchapi_repository.get_product(product_token)
    if detail.get("error"):
        return {"error": detail["error"], "product": None, "offers": []}
    product = detail.get("product") or {}
    offers = []
    for offer in detail.get("offers") or []:
        offers.append({
            "merchant": _merchant_name(offer),
            "price": _offer_price(offer),
            "price_raw": offer.get("price"),
            "total_price": offer.get("total_price"),
            "delivery_price": offer.get("delivery_price"),
            "link": offer.get("link"),
            "tag": offer.get("tag"),
        })
    return {
        "error": None,
        "product": product,
        "title": product.get("title") or detail.get("title") or "",
        "offers": offers,
        "typical_prices": detail.get("typical_prices"),
        "specifications": detail.get("specifications", []),
    }
