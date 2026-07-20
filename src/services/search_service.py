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

import re

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


def _load_trusted_merchants() -> set[str]:
    global _trusted_merchants_cache
    if _trusted_merchants_cache is not None:
        return _trusted_merchants_cache
    whitelist = {_norm(n) for n in MANUAL_TRUSTED_MERCHANTS}
    for brand in voucher_repository.brand_names():
        whitelist.add(_norm(brand))
    _trusted_merchants_cache = whitelist
    return whitelist


def _is_trusted_merchant(merchant_name: str, whitelist: set[str]) -> bool:
    norm = _norm(merchant_name)
    if not norm:
        return False
    if norm in whitelist:
        return True
    for entry in whitelist:
        if len(entry) < 4:
            continue
        if norm.startswith(entry) or entry.startswith(norm) or entry in norm or norm in entry:
            return True
    return False


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

    Reuses `_is_trusted_merchant`'s fuzzy substring match (not exact-name
    comparison) — real listings say "JioMart Electronics", not bare
    "JioMart", and an exact match would silently never anchor on them.

    The marketplace exclusion is applied to the *merchant name*, not by
    subtracting entries from the whitelist. Subtracting only removes the exact
    strings "amazon"/"flipkart", but the Gyftr brand list also contains
    `amazonfresh`, `amazonprimemembership` and `amazonshoppingvoucher` — and
    against a fuzzy substring match a listing from "Amazon" matches those and
    anchors anyway, defeating the exclusion entirely."""
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
    silently swap it out from under a selection the user already made."""
    seen: dict[str, dict] = {}
    for r in results:
        key = (r.get("merchant") or "").lower()
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


def _build_candidates(detail: dict) -> list[dict]:
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
_QUALIFIER_TOKENS = frozenset({
    "pro", "max", "plus", "ultra", "mini", "air", "lite", "se",
})

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
    that happen to repeat the bare digit instead."""
    if token.isdigit():
        return rf"\b{re.escape(token)}(?:st|nd|rd|th)?\b"
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

    strict = [
        c for c in hygienic
        if not tokens or _matches_required_tokens(c["title"], tokens)
    ]
    survivors = _vet(strict) if strict else []

    # Nothing survived. Usually this means the query names a product that does
    # not exist — two product lines conflated into one name ("AirPods Pro Max").
    # Requiring every word then keeps only the counterfeit sellers who use that
    # invented name, and removing the genuine listings also removes the trusted
    # merchants the price anchor needs, so the junk filter has nothing to
    # measure against and the whole result is either junk or empty.
    #
    # Retry once with the model-tier qualifiers softened. Deliberately gated on
    # a wiped-out result rather than applied by default: unconditionally, it
    # would inflate "puma skyrocket lite 2" from 8 results to 20 by admitting
    # non-Lite variants. Gated, every query that currently works is untouched.
    approximate = False
    if not survivors and tokens:
        strong = [t for t in tokens if t not in _QUALIFIER_TOKENS]
        qualifiers = [t for t in tokens if t in _QUALIFIER_TOKENS]
        if strong and qualifiers:
            relaxed = _vet([
                c for c in hygienic
                if _matches_relaxed_tokens(c["title"], strong, qualifiers)
            ])
            if relaxed:
                survivors = relaxed
                approximate = True

    if not survivors:
        # Only hand back the unfiltered pool when the *title* match found
        # nothing at all. If titles matched but trust/price vetting rejected
        # every one of them, that rejection is the answer — surfacing them
        # anyway would parade untrusted listings as results.
        return (candidates, False) if not strict else ([], False)

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

    grouped = [groups[k] for k in order]
    grouped.sort(key=lambda c: c.get("price") if c.get("price") is not None else float("inf"))
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
    try:
        raw = searchapi_repository.search_products(query)
        if raw.get("error"):
            out["error"] = raw["error"]
            return out
        products = [
            _product_candidate(p)
            for p in raw.get("shopping_results", [])
            if p.get("product_token")
        ]
        products, approximate = _filter_and_group_candidates(products, query)
        if not products:
            out["error"] = "No products found for that search."
            return out
        out["products"] = products
        out["approximate"] = approximate
    except Exception as e:  # never leak a stack trace
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
    as a route on its own."""
    norm_source = _norm(source)
    if not norm_source:
        return []
    for c in candidates:
        if _norm(c.get("merchant") or "") == norm_source and c.get("sellers"):
            return c["sellers"]
    return []


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
        # grounds to drop it, only to potentially outrank it later.
        if product_token not in tokens_to_fetch:
            tokens_to_fetch.append(product_token)

        candidates: list[dict] = []
        display_title = ""
        for token in tokens_to_fetch:
            detail = searchapi_repository.get_product(token)
            if detail.get("error"):
                continue
            product = detail.get("product") or {}
            display_title = display_title or product.get("title") or detail.get("title") or ""
            candidates.extend(_build_candidates(detail))

        if not candidates:
            # Refined search came up empty or every fetch failed — fall back
            # to the originally selected token alone.
            detail = searchapi_repository.get_product(product_token)
            if detail.get("error"):
                output["error"] = detail["error"]
                return output
            product = detail.get("product") or {}
            display_title = product.get("title") or detail.get("title") or ""
            candidates = _build_candidates(detail)

        if display_title:
            output["source"]["name"] = display_title
            output["source"]["brand"] = _infer_brand(display_title) or output["source"]["brand"]

        # Kept from before the trust filter runs, purely so the pinned
        # candidate below can recover a real seller link for the exact
        # merchant the user picked — that merchant's own offer (fetched
        # above for `product_token`, which is always included in
        # tokens_to_fetch) may not be on the trust whitelist even when the
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
        if picked_price is not None and picked_source:
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
