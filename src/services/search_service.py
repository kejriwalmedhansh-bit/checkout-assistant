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

import difflib
import hashlib
import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import httpx

# Attach to uvicorn's configured logger so these lines show in the server
# console (the app defines no logging config of its own).
logger = logging.getLogger("uvicorn.error")

from ..config import get_settings
from ..constants import HYPERLOCAL_MERCHANTS, KNOWN_BRANDS, MANUAL_TRUSTED_MERCHANTS, PRIORITY_MERCHANTS
from ..repositories import (
    apify_repository,
    buyhatke_repository,
    crawlbase_repository,
    maximize_repository,
    searchapi_repository,
    voucher_repository,
)
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


# ── budget parsing ("under 20000", "between 15000 and 20000") ──────────────────

# A number only counts as a budget figure when it's directly attached to one
# of these keywords — a bare number in the query (a model name, a spec) must
# never be mistaken for a price ceiling. Keeps "iPhone 15 under 60000" from
# treating "15" as anything but part of the product name.
_BUDGET_PHRASE_RE = re.compile(
    r"""
    (?P<kind>under|below|less\s+than|cheaper\s+than|max|maximum|up\s?to
             |over|above|more\s+than|min|minimum
             |between)
    \s+
    (?:rs\.?|inr|₹)?\s*
    (?P<num1>\d[\d,]*(?:\.\d+)?\s*k?)
    (?:
        \s*(?:-|to|and)\s*
        (?:rs\.?|inr|₹)?\s*
        (?P<num2>\d[\d,]*(?:\.\d+)?\s*k?)
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_UNDER_KINDS = {"under", "below", "less than", "cheaper than", "max", "maximum", "upto", "up to"}
_OVER_KINDS = {"over", "above", "more than", "min", "minimum"}


def _parse_budget_amount(raw: str) -> float:
    raw = raw.strip().lower()
    mult = 1.0
    if raw.endswith("k"):
        mult = 1000.0
        raw = raw[:-1].strip()
    return float(raw.replace(",", "")) * mult


def parse_budget(query: str) -> tuple[float | None, float | None, str | None]:
    """Finds a budget phrase in a free-text query ("smartphones under 20000",
    "TVs between 10000 and 15000") and returns (min_price, max_price,
    matched_phrase). matched_phrase is the exact text matched — the caller
    strips just those words from the required-token relevance check, since a
    budget number/keyword was never meant to appear verbatim in a listing's
    title the way a product word is ("Under Armour" stays untouched: "under"
    alone with no number after it never matches this pattern at all).

    Returns (None, None, None) when no budget phrase is present."""
    m = _BUDGET_PHRASE_RE.search(query or "")
    if not m:
        return None, None, None
    kind = re.sub(r"\s+", " ", m.group("kind").lower())
    num1 = _parse_budget_amount(m.group("num1"))
    num2_raw = m.group("num2")
    min_price = max_price = None
    if kind == "between":
        if num2_raw:
            num2 = _parse_budget_amount(num2_raw)
            min_price, max_price = min(num1, num2), max(num1, num2)
        else:
            max_price = num1
    elif kind in _OVER_KINDS:
        min_price = num1
    else:
        max_price = num1
    return min_price, max_price, m.group(0)


def _apply_budget_filter(products: list[dict], min_price: float | None, max_price: float | None) -> list[dict]:
    """Drops candidates priced outside the parsed budget. A candidate with no
    readable price is kept rather than dropped — there isn't enough
    information to say it's out of range, and hiding it outright risks
    losing a genuine result over a scrape gap (see CLAUDE.md rule #1: a wrong
    result is worse than no result, but that cuts the other way too — an
    unnecessarily hidden real result is its own kind of wrong)."""
    if min_price is None and max_price is None:
        return products

    def _in_budget(p: dict) -> bool:
        price = p.get("price")
        if price is None:
            return True
        if min_price is not None and price < min_price:
            return False
        if max_price is not None and price > max_price:
            return False
        return True

    return [p for p in products if _in_budget(p)]


# ── L1 guards (ported from pipeline.py) ─────────────────────────────────────────

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_trusted_merchants_cache: set[str] | None = None
_brand_voucher_index_cache: dict[str, dict] | None = None
_maximize_brand_index_cache: dict[str, dict] | None = None
_buyhatke_brand_index_cache: dict[str, dict] | None = None


def _gyftr_voucher_to_output_shape(voucher: dict) -> dict:
    # Canonical schema nests the actual rate/denomination fields inside
    # products[0] (brand-level keys like redemption_restrictions stay on
    # `voucher`) — same flattening voucher_service.get_best_voucher_deal
    # does; always exactly one product per Gyftr brand.
    products = voucher.get("products") or [{}]
    out = {**voucher, **products[0]}
    out["voucher_source"] = "gyftr"
    out["voucher_url"] = f"https://www.gyftr.com/{voucher.get('slug')}"
    return out


def _maximize_brand_to_output_shape(record: dict) -> dict:
    """Picks the brand's best-headline-rate tier and reshapes it to the same
    flat fields the Gyftr voucher dict already has, so one schema
    (VoucherDetailOut) and one frontend component serve both. There's no
    product price in this flow (it's a direct brand-name shortcut, skipping
    product search entirely), so — unlike the priced search flow, which picks
    by actual final cost — the tier is picked by headline discount rate, the
    same quick-compare number Dealo already surfaces elsewhere without a
    price in hand."""
    # Canonical schema's actual key is "products" (same as Gyftr), not
    # "tiers" — always read an empty list, so this shortcut fell through to
    # every field below defaulting empty/null. voucher_url was also reading
    # a field name ("voucher_url") that doesn't exist on a Maximize product
    # (it's "source_url") — always None, so the frontend's own fallback
    # built a gyftr.com link for what is actually a Maximize deal.
    # how_to_redeem_steps lives on the brand record, not per-product.
    products = record.get("products") or []
    best_tier = max(products, key=lambda t: t.get("best_discount_pct") or 0, default={})

    # Maximize's own master data carries no redemption-instruction fields at
    # all — "how do I use this gift card" is a brand-level fact that doesn't
    # depend on which platform sold the voucher, so borrow Gyftr's copy for
    # the same brand slug when Maximize itself has none.
    redeem_short = record.get("how_to_redeem_short")
    redeem_steps = record.get("how_to_redeem_steps") or []
    # Maximize itself never has a short summary generated (only Gyftr's data
    # does) — borrow Gyftr's for the same brand slug independently of
    # whether Maximize has its own (possibly different) long-form steps.
    if not redeem_short:
        gyftr_record = voucher_repository.get_by_slug(record.get("slug") or "")
        if gyftr_record:
            redeem_short = gyftr_record.get("how_to_redeem_short")
            if not redeem_steps:
                redeem_steps = gyftr_record.get("how_to_redeem_steps") or []

    return {
        "brand_name": record.get("brand_name"),
        "slug": record.get("slug"),
        "voucher_source": "maximize",
        "voucher_url": best_tier.get("source_url"),
        "redemption_type": best_tier.get("redemption_type", ""),
        "denominations": best_tier.get("denominations") or [],
        "is_custom_denom": best_tier.get("is_custom_denom", False),
        "custom_min": best_tier.get("custom_min"),
        "custom_max": best_tier.get("custom_max"),
        "discounts": best_tier.get("discounts") or {},
        "best_payment_method": best_tier.get("best_payment_method"),
        "best_discount_pct": best_tier.get("best_discount_pct"),
        "stack_limit": best_tier.get("stack_limit"),
        # Maximize doesn't track this separately (always None in the data) —
        # a real numeric stack_limit here is still a confirmed scraped cap,
        # just without the "unlimited_stated" language Gyftr's parser derives
        # from its own T&C text.
        "stack_limit_confidence": record.get("stack_limit_confidence"),
        "value_cap": best_tier.get("value_cap"),
        "purchase_cap_per_txn": best_tier.get("purchase_cap_per_txn"),
        "redemption_restrictions": record.get("redemption_restrictions") or [],
        "how_to_redeem_steps": redeem_steps,
        "how_to_redeem_short": redeem_short,
    }


def _buyhatke_brand_to_output_shape(record: dict) -> dict:
    """Same idea as `_maximize_brand_to_output_shape`, for BuyHatke — picks
    the best-headline-rate tier and reshapes to the same flat fields. Found
    2026-08-14: this shape function didn't exist at all, so a bare brand-name
    search (e.g. "Myntra") only ever compared Gyftr vs Maximize and could
    show a worse rate (Gyftr's 2.5%) while BuyHatke quietly had a better one
    (5%) that this flow structurally couldn't see."""
    products = record.get("products") or []
    best_tier = max(products, key=lambda t: t.get("best_discount_pct") or 0, default={})

    # BuyHatke's own data never has a short summary generated for it in the
    # same way Gyftr's does — borrow Gyftr's for the same brand name (BuyHatke
    # slugs don't match Gyftr's, so look up by normalized brand name instead
    # of by slug the way `_maximize_brand_to_output_shape` does).
    redeem_short = record.get("how_to_redeem_short")
    redeem_steps = record.get("how_to_redeem_steps") or []
    if not redeem_short:
        gyftr_voucher = _load_brand_voucher_index().get(_norm(record.get("brand_name") or ""))
        if gyftr_voucher:
            redeem_short = gyftr_voucher.get("how_to_redeem_short")
            if not redeem_steps:
                redeem_steps = gyftr_voucher.get("how_to_redeem_steps") or []

    return {
        "brand_name": record.get("brand_name"),
        "slug": record.get("slug"),
        "voucher_source": "buyhatke",
        "voucher_url": best_tier.get("source_url"),
        "redemption_type": best_tier.get("redemption_type", ""),
        "denominations": best_tier.get("denominations") or [],
        "is_custom_denom": best_tier.get("is_custom_denom", False),
        "custom_min": best_tier.get("custom_min"),
        "custom_max": best_tier.get("custom_max"),
        "discounts": best_tier.get("discounts") or {},
        "best_payment_method": best_tier.get("best_payment_method"),
        "best_discount_pct": best_tier.get("best_discount_pct"),
        "stack_limit": best_tier.get("stack_limit"),
        # BuyHatke doesn't track this separately (always None) — same as
        # Maximize, a real numeric stack_limit here is still a confirmed cap.
        "stack_limit_confidence": record.get("stack_limit_confidence"),
        "value_cap": best_tier.get("value_cap"),
        "purchase_cap_per_txn": best_tier.get("purchase_cap_per_txn"),
        "redemption_restrictions": record.get("redemption_restrictions") or [],
        "how_to_redeem_steps": redeem_steps,
        "how_to_redeem_short": redeem_short,
    }


def _load_brand_voucher_index() -> dict[str, dict]:
    """Maps a normalized, spaceless full Gyftr brand name ("Tata CLiQ" ->
    "tatacliq") to its raw voucher record, for exact whole-phrase query
    matching in `_match_brand_voucher`. Cached — 380 brands, loaded once."""
    global _brand_voucher_index_cache
    if _brand_voucher_index_cache is not None:
        return _brand_voucher_index_cache
    index: dict[str, dict] = {}
    for voucher in voucher_repository.all_vouchers():
        key = _norm(voucher.get("brand_name", ""))
        if key:
            index[key] = voucher
    _brand_voucher_index_cache = index
    return index


def _load_maximize_brand_index() -> dict[str, dict]:
    """Same idea as `_load_brand_voucher_index`, over Maximize brands."""
    global _maximize_brand_index_cache
    if _maximize_brand_index_cache is not None:
        return _maximize_brand_index_cache
    index: dict[str, dict] = {}
    for record in maximize_repository.all_brands():
        key = _norm(record.get("brand_name", ""))
        if key:
            index[key] = record
    _maximize_brand_index_cache = index
    return index


def _load_buyhatke_brand_index() -> dict[str, dict]:
    """Same idea as `_load_brand_voucher_index`, over BuyHatke brands."""
    global _buyhatke_brand_index_cache
    if _buyhatke_brand_index_cache is not None:
        return _buyhatke_brand_index_cache
    index: dict[str, dict] = {}
    for record in buyhatke_repository.all_brands():
        key = _norm(record.get("brand_name", ""))
        if key:
            index[key] = record
    _buyhatke_brand_index_cache = index
    return index


# Longest brand_name across both sources is 6 words (e.g. multi-word jewelry
# brands) — bounds the query word-window scan below.
_MAX_BRAND_WORDS = 6

# Words that can sit alongside a brand name without turning the query into a
# real product search ("Levi's gift card", "Myntra e-gift voucher"). Anything
# else left over after the brand's own words are removed means the user named
# an actual product ("Levi's denim jacket") — that must go to L1 product
# search, never the brand-only voucher shortcut.
_BRAND_VOUCHER_FILLER_WORDS = frozenset({
    "gift", "card", "cards", "voucher", "vouchers", "gc", "egift", "epay",
})

# Hand-verified pairs where Gyftr and Maximize sell the genuinely same real
# voucher under different names (2026-08 audit) — normal exact-name matching
# below would never connect these, so each side would only ever compete
# against itself. Every pair here was checked individually (redemption
# mechanism, restrictions, stack limits), not assumed from the naming
# pattern alone — a same-ish name does NOT always mean the same product (see
# Yatra and MakeMyTrip below, which is exactly why this isn't a generic
# fuzzy-match rule). Key: normalized query words (start:start+length,
# joined) that should resolve to this pair. Value: (gyftr_slug, maximize_slug)
# — either may be None if only one platform genuinely sells it.
_MANUAL_VOUCHER_MATCHES: dict[str, tuple[str | None, str | None]] = {
    # Maximize sells 6+ distinct Yatra products under near-identical names:
    # fixed-denomination single-use flight vouchers (Yatra 500/1000/1500/2000,
    # 25-85% off — a different, narrower product, deliberately NOT mapped
    # here) versus the general-purpose, stackable "Yatra Hotel" gift card
    # that's the actual Gyftr equivalent. A bare "Yatra" search must resolve
    # to the Hotel product on both sides, never the single-use family or
    # Gyftr's separate near-dead "Yatra Voucher" (0%, a different listing).
    "yatra": ("yatra-hotel-gift-card", "yatra-hotel"),
    "yatrahotel": ("yatra-hotel-gift-card", "yatra-hotel"),
    "yatrahotels": ("yatra-hotel-gift-card", "yatra-hotel"),
    # Maximize separately sells a plain "MakeMyTrip" gift card (PIN-redeemed,
    # no OTP/wallet) alongside "MakeMyTrip E-Pay" (OTP-verified wallet
    # top-up) — genuinely different redemption mechanisms, not a naming
    # variant. A bare "MakeMyTrip" search must resolve to e-Pay (what Gyftr
    # actually sells), not silently fall through to Maximize's separate,
    # cheaper plain gift card.
    "makemytrip": ("makemytrip-e-pay", "makemytrip-e-pay"),
    "makemytripepay": ("makemytrip-e-pay", "makemytrip-e-pay"),
    "superdryluxe": ("luxe-gift-card-superdry", "superdry-luxe"),
    "armaniexchangeluxe": ("luxe-gift-card-armani-exchange", "armani-exchange-luxe"),
    "hugobossluxe": ("luxe-gift-card-hugo-boss", "hugo-boss-luxe"),
    "gasluxe": ("luxe-gift-card-gas", "gas-luxe"),
    "brooksbrothersluxe": ("luxe-gift-card-brooks-brothers", "brooks-brothers-luxe"),
    "michaelkorsluxe": ("luxe-gift-card-michael-kors", "michael-kors-luxe"),
    "satyapaulluxe": ("luxe-gift-card-satya-paul", "satya-paul-luxe"),
    "tumiluxe": ("tumi", "tumi-luxe"),
    "katespadeluxe": ("kate-spade--luxe-gift-card", "kate-spade-luxe"),
    "hamleysluxe": ("luxe-gift-card-hamleys", "hamleys-luxe"),
    "braingymjr": ("braingymjr", "braingymjr-gift-voucher"),
    "unipinbgmi": ("unipin-bgmi", "unipin-bgmi-voucher"),
    "peterengland": ("peter-england-gift-voucher", "peter-england"),
    "americaneagle": ("american-eagle-gift-voucher", "american-eagle"),
    "planetfashion": ("planet-fashion-gift-voucher", "planet-fashion"),
    "allensolly": ("allen-solly-gift-voucher", "allen-solly"),
    "vanheusen": ("van-heusen-gift-voucher", "van-heusen"),
    "simoncarter": ("simon-carter-gift-voucher", "simon-carter"),
    "blinkit": ("blinkit-gift-card", "blinkit"),
    "zomato": ("zomato-gift-card", "zomato"),
    "cult": ("cult-gift-card", None),
    "louisphilippe": ("louis-philippe-gift-voucher", "louis-philippe"),
    "bpclsmartdrivefuel": ("-bpcl-", "bpcl-smartdrive-fuel"),
}


_VOUCHER_SOURCE_TIE_PRIORITY = {"gyftr": 0, "maximize": 1, "buyhatke": 2}


def _pick_better_voucher(*shaped_options: dict | None) -> dict | None:
    """Whichever has the higher headline discount wins, across however many
    sources actually have this brand (2 originally — Gyftr/Maximize — now up
    to 3 with BuyHatke). On an exact tie, whichever side's stack limit is
    clearly better wins (no stated cap beats a numeric cap; a higher numeric
    cap beats a lower one); a further tie defaults to Gyftr, then Maximize,
    then BuyHatke (simpler checkout flow first) — same priority order the
    original 2-way version used, just extended to a third source."""
    candidates = [s for s in shaped_options if s is not None]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def _pct(shaped: dict) -> float:
        return shaped.get("best_discount_pct") or 0

    best_pct = max(_pct(c) for c in candidates)
    tied = [c for c in candidates if _pct(c) == best_pct]
    if len(tied) == 1:
        return tied[0]

    def _stack_rank(shaped: dict) -> int:
        limit = shaped.get("stack_limit")
        confidence = shaped.get("stack_limit_confidence")
        if limit is None and confidence == "unlimited_stated":
            return 10**9  # explicitly no cap
        if limit is None:
            return -1  # genuinely unconfirmed — worst, not "unlimited"
        return limit

    tied.sort(key=lambda s: (-_stack_rank(s), _VOUCHER_SOURCE_TIE_PRIORITY.get(s.get("voucher_source"), 99)))
    return tied[0]


def _match_brand_voucher(query: str) -> dict | None:
    """Whole-query match only — the entire search must be just the brand name
    (optionally plus filler words like "gift card"/"voucher"), never a brand
    name appearing anywhere inside a longer, more specific search. A query
    word window (1 to `_MAX_BRAND_WORDS` consecutive words) must normalize to
    exactly equal a brand's full normalized name, checked against Gyftr,
    Maximize, and BuyHatke — and every word outside that window must be pure
    filler, or this isn't a brand-only lookup, it's a real product search
    that happens to mention the brand ("Levi's denim jacket for men" must be
    priced via L1, not short-circuited to the Levi's voucher).

    If a window matches on more than one source, whichever has the better
    headline rate wins — there's no product price in this flow to compare
    actual final cost with, so headline rate is the honest best available
    signal. (Note: the hand-verified `_MANUAL_VOUCHER_MATCHES` overrides
    below are still Gyftr/Maximize-only — extending those to BuyHatke needs
    the same brand-by-brand verification the existing pairs got, not a
    blanket rule.)"""
    words = re.findall(r"[a-z0-9]+", (query or "").lower())
    if not words:
        return None
    gyftr_index = _load_brand_voucher_index()
    maximize_index = _load_maximize_brand_index()
    buyhatke_index = _load_buyhatke_brand_index()
    for start in range(len(words)):
        for length in range(1, min(_MAX_BRAND_WORDS, len(words) - start) + 1):
            window = "".join(words[start:start + length])

            # Hand-verified cross-platform pairs take priority over each
            # platform's own name index — these exist specifically because
            # the two platforms' own brand names don't line up, so the
            # generic exact-name lookup below would never connect them.
            override = _MANUAL_VOUCHER_MATCHES.get(window)
            if override is not None:
                leftover = words[:start] + words[start + length:]
                if any(w not in _BRAND_VOUCHER_FILLER_WORDS for w in leftover):
                    continue
                g_slug, m_slug = override
                g_shaped = _gyftr_voucher_to_output_shape(voucher_repository.get_by_slug(g_slug)) if g_slug else None
                m_shaped = _maximize_brand_to_output_shape(maximize_repository.get_by_slug(m_slug)) if m_slug else None
                result = _pick_better_voucher(g_shaped, m_shaped)
                if result is not None:
                    return result
                continue

            gyftr_voucher = gyftr_index.get(window)
            maximize_record = maximize_index.get(window)
            buyhatke_record = buyhatke_index.get(window)
            if gyftr_voucher is None and maximize_record is None and buyhatke_record is None:
                continue
            leftover = words[:start] + words[start + length:]
            if any(w not in _BRAND_VOUCHER_FILLER_WORDS for w in leftover):
                continue
            g_shaped = _gyftr_voucher_to_output_shape(gyftr_voucher) if gyftr_voucher else None
            m_shaped = _maximize_brand_to_output_shape(maximize_record) if maximize_record else None
            b_shaped = _buyhatke_brand_to_output_shape(buyhatke_record) if buyhatke_record else None
            return _pick_better_voucher(g_shaped, m_shaped, b_shaped)
    return None


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
    all_names = (
        list(MANUAL_TRUSTED_MERCHANTS)
        + list(voucher_repository.brand_names())
        + list(maximize_repository.brand_names())
        + list(buyhatke_repository.brand_names())
    )
    for name in all_names:
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


def _is_hyperlocal(merchant: str) -> bool:
    """True for quick-commerce apps (Blinkit/Zepto/Swiggy/Zomato) whose stock
    and delivery coverage is pincode-specific in a way we can't verify — see
    HYPERLOCAL_MERCHANTS in constants.py for why these get ranked last."""
    src = (merchant or "").lower()
    return any(m in src for m in HYPERLOCAL_MERCHANTS)


def _priority_sort(results: list[dict]) -> list[dict]:
    """Priority merchants first (in declared order), then normal results
    sorted by price, then hyperlocal apps last (also by price among
    themselves) — never excluded, just never allowed to outrank a normal
    listing."""
    def _key(r: dict) -> tuple:
        src = (r.get("merchant") or "").lower()
        for i, m in enumerate(PRIORITY_MERCHANTS):
            if m.lower() in src:
                return (0, i, 0.0)
        if _is_hyperlocal(src):
            return (2, 0.0, r.get("price") or float("inf"))
        return (1, 0.0, r.get("price") or float("inf"))
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
    """The recommended route is always card-free — this only adds an optional
    "by the way" aside for someone who already owns a qualifying card. Never
    affects ranking, never a reason to apply for a card to get Dealo's main
    price (see CreditCardPrompt.jsx)."""
    voucher = route.get("voucher")
    if voucher is None:
        card_fomo = card_service.best_card_for_purchase(
            merchant=route["merchant"],
            purchase_amount=route["final_cost"],
        )
    else:
        # A card path means paying the voucher at THIS card's own rate (Credit
        # Card discount — already computed and sitting in voucher["card"]),
        # not the UPI rate Dealo recommends; cashback is earned on top of that
        # lower-discount price, never layered on the UPI-rate price the
        # customer wouldn't actually have paid by using a card instead.
        card_fomo = card_service.best_card_for_voucher_purchase(
            merchant=route["merchant"],
            card_rate_price=voucher["card"]["effective_price"],
            recommended_price=route["final_cost"],
            voucher_source=voucher.get("voucher_source", "gyftr"),
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

    # Hyperlocal apps (Blinkit/Zepto/Swiggy/Zomato) sort after every normal
    # route regardless of price — see HYPERLOCAL_MERCHANTS in constants.py.
    # Otherwise a route through one of these could win "Recommended" on
    # price alone despite delivery/stock we can't actually confirm for the
    # user's location.
    routes.sort(key=lambda x: (_is_hyperlocal(x["merchant"]), x["final_cost"]))

    if not routes:
        return {"recommended": None, "alternatives": [], "compared_count": 0}

    shown = routes[:4]
    for route in shown:
        card_fomo = _card_fomo_for_route(route)
        if card_fomo:
            route["card_fomo"] = card_fomo

    return {"recommended": shown[0], "alternatives": shown[1:4], "compared_count": len(routes)}


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

# A seller title can bundle two different appliances joined by a bare "&"
# without ever using the word "combo" (e.g. "...Mixer Grinder... & Prestige
# PIC 20 1600W Induction Cooktop...") — the keyword list above misses this
# entirely. Two independent wattage specs in one title is a strong, rarely-
# false-positive signal that two different appliances are being described,
# not one product's own spec repeated — a single genuine product doesn't
# carry two different wattage numbers. Deliberately requires "&" (not "+",
# which real listings also use benignly for included accessories within ONE
# product, e.g. "3 SS Jars + 1 Juicer Jar").
_WATTAGE_RE = re.compile(r"\b(\d+)\s?(?:w|watt|watts)\b")

_QUERY_STOPWORDS = {
    "buy", "price", "online", "best", "new", "latest", "india", "offer",
    "offers", "deal", "deals", "for", "the", "a", "an", "with", "and",
    # Category words a shopper adds to say *what kind* of thing they want,
    # not part of the product's own name — real listing titles routinely
    # omit them ("The Alchemist by Paulo Coelho" has no "book" in it),
    # so requiring them verbatim rejects genuine matches.
    "book", "books",
}

_MAX_CANDIDATES = 32  # picker paginates 8/page (ProductSelectPage.jsx); this is the total pool

# Below this many post-filter candidates, a brand-qualified search ("Apple
# AirPods") is treated as suspiciously thin and worth re-checking against the
# same search with the brand word removed ("AirPods") — see
# `_maybe_widen_brand_query`.
_THIN_RESULT_THRESHOLD = 3

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
    # "canvas" is Chuck Taylor's own default upper material, not an
    # alternate-material variant the way a genuine "Leather Chuck Taylor" SKU
    # would be (already covered by "leather" above) — found alongside the
    # possessive-tokenizer bug, 2026-08-26.
    "canvas",
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

# Screen size (TVs, monitors, laptops) — unlike battery life or ANC depth,
# this genuinely defines a different, differently-priced product (a 55" and
# a 65" TV are not the same item), so it's tracked as its own variant
# attribute rather than left to _SPEC_PHRASE_RE's generic "non-distinguishing
# spec filler" strip below. Matched on the already-normalized (lowercase,
# punctuation-stripped) title, so "65-inch" / "65 Inch" / "65\"" all read the
# same once _norm_title has run.
_SIZE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s?inch\b")

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
    if any(kw in normalized for kw in _BULK_LISTING_KEYWORDS):
        return True
    # Two-appliances-joined-by-"&" case — see _WATTAGE_RE comment above.
    if "&" in (title or "") and len(set(_WATTAGE_RE.findall(normalized))) >= 2:
        return True
    return False


def _is_latin_dominant(title: str) -> bool:
    """True unless a title is genuinely non-English/mixed-language junk for
    an English-speaking picker to show. The >=0.5 threshold this used to use
    only rejected a title once NON-Latin letters were the majority — so a
    title that's roughly half Hindi, half English (confirmed live,
    2026-08-27: an amazon.in Samsung Galaxy M17 listing scored exactly 0.50
    and was shown as-is, Devanagari specs and all) passed as "dominant" on a
    tie. Raised to 0.75, well above where a normal English title with the
    occasional accented character or non-Latin trademark symbol lands
    (Nescafé, L'Oreal-style apostrophes, em dashes — all still ~0.95-1.0),
    but firmly below a real half-and-half bilingual title."""
    letters = [c for c in (title or "") if c.isalpha()]
    if not letters:
        return True
    latin = sum(1 for c in letters if c.isascii())
    return latin / len(letters) >= 0.75


def _required_tokens(query: str) -> list[str]:
    """Query tokens the candidate title must contain, minus brand names,
    generic stopwords, and a budget phrase's own words ("smartphones under
    20000" -> ["smartphones"]) — a price ceiling/floor is enforced as a real
    numeric check elsewhere (see `parse_budget` / `_apply_budget_filter`),
    so the number and its keyword must not also be required to appear
    verbatim in a listing's title the way a real product word would be."""
    _, _, budget_phrase = parse_budget(query)
    budget_words = set(re.findall(r"[a-z0-9]+", budget_phrase.lower())) if budget_phrase else set()
    # A possessive ("Men's", "Women's") splits into two tokens under the
    # plain [a-z0-9]+ scan below — the real word plus a bare, meaningless
    # "s" — and that phantom "s" becomes a real required token downstream in
    # `_matches_required_tokens`'s all-tokens route-building check. Almost no
    # genuine listing's title contains a standalone "s" word, so this alone
    # was enough to drop nearly every real seller for any possessive query
    # (confirmed live: "Converse Men's Chuck Taylor..." silently excluded
    # AJIO, Amazon.in, and a cheaper Nykaa listing from route-building, all
    # for lacking a bare "s" — only listings whose own title also happened
    # to spell out an apostrophe survived by coincidence). Stripped here,
    # before tokenizing, rather than filtering a bare "s" out afterward — a
    # trailing possessive "s" is grammatical, not a product word, so it
    # shouldn't survive as a token at all, in the query or in `_norm_title`'s
    # matching title text (this only touches the query-token side; title
    # text is unaffected).
    depossessed = re.sub(r"(?<=[a-z])['’]s\b", "", (query or "").lower())
    tokens = re.findall(r"[a-z0-9]+", depossessed)
    return [t for t in tokens if t not in KNOWN_BRANDS and t not in _QUERY_STOPWORDS and t not in budget_words]


def _strip_known_brands(query: str) -> str | None:
    """Remove any `KNOWN_BRANDS` word from the query text itself (not just the
    internal token-matching step, which already ignores brand words) —
    "Apple AirPods" -> "AirPods", "Sony headphones" -> "headphones".

    Returns None when no brand word was actually present, so a caller can
    tell "nothing to strip" apart from "stripping left an empty string"."""
    words = (query or "").split()
    kept = [w for w in words if w.lower() not in KNOWN_BRANDS]
    if len(kept) == len(words):
        return None
    stripped = " ".join(kept).strip()
    return stripped or None


def _is_bare_modifier_segment(segment: str) -> bool:
    """True if a "/"-separated title segment is just a trailing storage/color/
    bare-number continuation of the previous segment (e.g. the "512GB" in
    "256GB/512GB"), not an independent product-name claim."""
    normalized = _norm_title(segment)
    stripped = _STORAGE_RE.sub(" ", normalized)
    words = stripped.split()
    return all(w.isdigit() or w in _COLOR_WORDS for w in words)


def _plural_variants(word: str) -> set[str]:
    """Both singular and plural spellings of a plain word — a category query
    ("smartphones", "TVs under 15000") must match listings that (as almost
    all of them do) title themselves in the singular ("Redmi Note 13
    Smartphone"), and vice versa. Follows the same english pluralization
    rules real listing titles do: words ending in ch/sh/x/s/z take "es"
    ("watches" <-> "watch", "boxes" <-> "box"), everything else takes a
    plain "s". Not applied to anything but plain alphabetic words — a model
    number or fused alnum token has no plural form to speak of."""
    variants = {word}
    if word.endswith(("ches", "shes", "xes", "sses", "zes")):
        variants.add(word[:-2])
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 2:
        variants.add(word[:-1])
    elif word.endswith(("ch", "sh", "x", "z", "s")):
        variants.add(word + "es")
    else:
        variants.add(word + "s")
    return variants


def _token_pattern(token: str) -> str:
    """A bare generation/model number like "2" must also match its ordinal
    form in a listing title ("2nd Generation") — sellers routinely phrase the
    same product differently, and rejecting the ordinal phrasing would
    incorrectly filter out genuine listings while admitting sloppier ones
    that happen to repeat the bare digit instead.

    A fused alphanumeric model name like "pr100" must also match its spaced
    phrasing ("Tissot PR 100") — nothing else splits a fused query word back
    apart, so without this a "PR100" search can never match the sellers who
    write "PR 100" and the whole search collapses to zero results."""
    if token.isdigit():
        return rf"\b{re.escape(token)}(?:st|nd|rd|th)?\b"
    parts = re.findall(r"[a-z]+|\d+", token)
    if len(parts) > 1:
        return r"\b" + r"\s?".join(re.escape(p) for p in parts) + r"\b"
    if token.isalpha():
        variants = sorted(_plural_variants(token), key=len, reverse=True)
        if len(variants) > 1:
            alt = "|".join(re.escape(v) for v in variants)
            return rf"\b(?:{alt})\b"
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


# A survivor matching at least this share of the query's required words
# counts as a solid match. Below it, the listing only cleared the
# permissive any-token relevance gate (one word landing anywhere), not a
# real confirmation of the product itself — e.g. "AirPods" alone matching a
# candidate titled "AirPods Max Silicone Case" (1 of 3 words). Picked to sit
# clearly above "exactly one token of several," not tuned against a labeled
# dataset — revisit if real weak-match reports turn out to disagree.
_STRONG_MATCH_FRACTION = 0.6


def _required_token_match_fraction(title: str, tokens: list[str]) -> float:
    """Share of `tokens` actually found in `title`, 0.0-1.0. 1.0 (nothing to
    fall short of) when `tokens` is empty — a query with no literal words
    left to check (pure brand/stopword) has no basis to call any result a
    weak match."""
    if not tokens:
        return 1.0
    normalized = _norm_title(title or "")
    hits = sum(1 for t in tokens if re.search(_token_pattern(t), normalized))
    return hits / len(tokens)


def _fuzzy_token_hit(token: str, normalized_title: str) -> bool:
    """Tolerate a one-letter typo/spelling slip between a query word and a
    listing's own word (e.g. query "airdryer" vs a real listing's "airfryer")
    so a single glued-together typo doesn't throw out every real result. Only
    applies to alphabetic tokens long enough that a coincidental near-match is
    implausible (>=6 letters) — below that, genuinely different short words
    read as artificially "close" too easily (e.g. "add" vs "app")."""
    if not token.isalpha() or len(token) < 6:
        return False
    for word in re.findall(r"[a-z]+", normalized_title):
        if abs(len(word) - len(token)) > 2:
            continue
        if difflib.SequenceMatcher(None, token, word).ratio() >= 0.82:
            return True
    return False


def _matches_any_required_token(title: str, tokens: list[str]) -> bool:
    """Permissive relevance gate for the picker (see bug #6 in CLAUDE.md):
    at least one required query token must appear in the title — not every
    token, the way `_matches_required_tokens` requires for route-building.
    Empty `tokens` (a query that's entirely brand words/stopwords) always
    passes, since there's nothing meaningful left to require.

    Deliberately permissive rather than reviving the old all-tokens picker
    check that was removed on 2026-08-03 for wrongly rejecting real listings
    (e.g. "Buds4 Pro" against a required "4" token, no space before the
    digit). Requiring only one token to land anywhere in the title is far
    harder to trip on a genuine listing's own phrasing, while still
    rejecting the case that actually motivated this: gibberish input
    ("asdkjhaskjdh 1234 ??!!") matching nothing at all in a real title."""
    if not tokens:
        return True
    normalized = _norm_title(title or "")
    return any(
        re.search(_token_pattern(t), normalized) or _fuzzy_token_hit(t, normalized)
        for t in tokens
    )


def _is_category_only_query(query: str, tokens: list[str]) -> bool:
    """True when a query names no specific product to verify against — just
    a category of thing to browse ("smartphones", "TVs under 15000"), with
    no known brand and no model-number-style digit anywhere in it. There's
    no single product identity here for a listing's title to confirm or
    deny (unlike "boAt Airdopes 141", where the title must actually say
    "Airdopes 141" to be trusted), and real listings phrase a category too
    inconsistently for a literal-word match to be the right tool — a phone
    listing just as often says "5G Mobile Phone" as "Smartphone". `tokens`
    is the already brand/stopword/budget-stripped required-token list, so a
    leftover digit in it is a genuine model number, never a budget figure
    (that's parsed and excluded separately by `_required_tokens`)."""
    raw_words = re.findall(r"[a-z0-9]+", (query or "").lower())
    has_known_brand = any(w in KNOWN_BRANDS for w in raw_words)
    has_model_number = any(t.isdigit() for t in tokens)
    return not has_known_brand and not has_model_number


# Only ever collapses genuinely equivalent phrasings of the *same* product
# category into one canonical search term sent to Google — never two
# different product types. A smartwatch and an analog watch are
# deliberately kept as separate groups (not merged here at all): someone
# searching "watches" wants the analog kind, not what a "smartwatch" search
# means, even though both are things you wear on your wrist. Grows only as
# new equivalences are individually confirmed — the same "targeted,
# high-confidence fix, not a broad pattern matcher" bar as everything else
# in this file (CLAUDE.md rule #1). A wrongly-merged group would silently
# swap in the wrong product category for everyone who types the "other"
# word.
_CATEGORY_SYNONYM_GROUPS: dict[str, list[str]] = {
    "smartphone": [
        "smartphones", "smartphone", "mobile phones", "mobile phone",
        "mobilephones", "mobilephone", "cell phones", "cell phone",
        "cellphones", "cellphone", "mobiles", "mobile", "phones", "phone",
    ],
    "tv": ["televisions", "television", "tvs", "tv"],
    "earbuds": ["earphones", "earphone", "earbuds", "earbud"],
    "laptop": ["notebooks", "notebook", "laptops", "laptop"],
}

_CATEGORY_SYNONYM_RE: dict[str, re.Pattern] = {
    canonical: re.compile(
        r"\b(?:" + "|".join(re.escape(s) for s in sorted(synonyms, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )
    for canonical, synonyms in _CATEGORY_SYNONYM_GROUPS.items()
}


def _canonicalize_category_words(query: str) -> str:
    """Rewrites a recognized category word/phrase to one fixed canonical
    term before the query is sent to Google — "mobilephone", "mobile
    phone", and "smartphones" all become the same search text, so they get
    back the same raw results instead of drifting apart on wording Google's
    own index happens to rank differently.

    The caller must only ever apply this to a query `_is_category_only_query`
    has already confirmed names no specific product (no brand, no model
    number) — a query that does name one has an exact product to find and
    must reach Google exactly as typed, never rewritten."""
    result = query
    for canonical, pattern in _CATEGORY_SYNONYM_RE.items():
        result = pattern.sub(canonical, result)
    return result


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
        if (len(w) > 1 or w.isdigit())
        # A plain `w not in exclude` string check missed the seller's own
        # plural of a required word ("Sneaker" required, title says
        # "Sneakers") — that alone made AJIO's own Converse listing look
        # like a different variant of the exact query it was fetched for,
        # dropping it from route-building entirely (confirmed live,
        # 2026-08-26). `_plural_variants` already exists for exactly this
        # singular/plural equivalence elsewhere in the file — reused here so
        # the two checks can't drift out of sync with each other.
        and w not in exclude and not (_plural_variants(w) & exclude)
        and w not in _MARKETING_FILLER_WORDS
    )


def _extract_variant_signature(title: str, exclude: set) -> tuple:
    normalized = _norm_title(title)
    storage_m = _STORAGE_RE.search(normalized)
    storage = f"{storage_m.group(1)}{storage_m.group(2)}" if storage_m else None
    size_m = _SIZE_RE.search(normalized)
    size = f"{size_m.group(1)}inch" if size_m else None
    color = next((c for c in _COLOR_WORDS if re.search(rf"\b{re.escape(c)}\b", normalized)), None)
    extra_words = _distinguishing_words(title, exclude | {storage, size, color} - {None})
    return (extra_words, storage, size, color)


def _filter_and_group_candidates(
    candidates: list[dict], query: str, tag: str = "[search]"
) -> tuple[list[dict], bool]:
    """Drop bulk-listings/non-English junk, then group same-variant listings
    from different sellers into one picker card each.

    Accessory filtering only applies when the query itself isn't an
    accessory search — a listing titled "iPhone 16 Pro Max Silicone Case"
    is dropped for the query "iPhone 16 Pro Max" (the shopper wants the
    phone, not a case), but kept for the query "iPhone 16 Pro Max case"
    (that IS what they're looking for). See CLAUDE.md bug #6/#7 history —
    a real-device query with no in-stock new listing from a trusted seller
    used to fall through to whatever accessory listings survived the trust
    filter instead, e.g. "iPhone 16 Pro Max" surfacing only phone cases as
    picker candidates (2026-08-31, from live client feedback). The
    relevance gate below only rejects a listing that matches NONE of the
    query's required tokens — it does not require every token to match
    (that stricter all-tokens rule was tried and reverted on 2026-08-03 for
    false negatives; see CLAUDE.md bug #6), so unrelated-but-token-
    overlapping results can still surface.

    Returns ``(candidates, approximate)``. ``approximate`` is True when even
    the best-matching survivor only weakly overlaps the query's required
    words (below _STRONG_MATCH_FRACTION) — the permissive any-token gate
    above lets a barely-scraped-by listing through on purpose (see its own
    docstring), so this is what tells that case apart from a real, solid
    match instead of showing both with the same silent confidence. Always
    False for a category-only query (`_is_category_only_query`) or a query
    with no required tokens at all — neither names a specific product for a
    title to confirm or fall short of.
    """
    tokens = _required_tokens(query)
    exclude = set(tokens) | set(KNOWN_BRANDS)
    query_is_accessory_search = _is_accessory(query)
    hygienic = [
        c for c in candidates
        if c.get("title")
        and not _is_bulk_listing(c["title"])
        and _is_latin_dominant(c["title"])
        and (query_is_accessory_search or not _is_accessory(c["title"]))
    ]
    if not query_is_accessory_search:
        for c in candidates:
            if c.get("title") and _is_accessory(c["title"]) and not _is_bulk_listing(c["title"]) and _is_latin_dominant(c["title"]):
                logger.info("%s   dropped (accessory listing for a non-accessory query): %r", tag, c["title"])
    for c in candidates:
        if not c.get("title"):
            continue
        if _is_bulk_listing(c["title"]):
            logger.info("%s   dropped (bulk listing): %r", tag, c["title"])
        elif not _is_latin_dominant(c["title"]):
            logger.info("%s   dropped (non-Latin title): %r", tag, c["title"])

    # Relevance gate (2026-08-06, re-added — see CLAUDE.md bug #6): reject a
    # listing only when it matches NONE of the query's required tokens, not
    # when it fails to match all of them. Catches gibberish/unrelated queries
    # returning a confident wrong "match" while staying far more permissive
    # than the all-tokens check removed on 2026-08-03.
    #
    # Skipped entirely for a category-only query ("smartphones", "TVs under
    # 15000") — there's no specific product name here for a title to
    # confirm, so requiring literal word overlap only ever throws away real,
    # trusted listings that phrase the category differently ("5G Mobile
    # Phone" for a "smartphones" search). Trust + price vetting below still
    # runs unchanged either way — that's what actually keeps junk out here.
    category_only = _is_category_only_query(query, tokens)
    if category_only:
        logger.info("%s category-only query %r — skipping literal-word relevance gate", tag, query)
        relevant = hygienic
    else:
        relevant = [c for c in hygienic if _matches_any_required_token(c["title"], tokens)]
        for c in hygienic:
            if c not in relevant:
                logger.info("%s   dropped (matches none of the required tokens %r): %r", tag, tokens, c["title"])
    hygienic = relevant

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
        trusted = _filter_trusted_only(pool, merchant_key="source")
        for c in pool:
            if c not in trusted:
                logger.info("%s   dropped (untrusted seller %r): %r", tag, c.get("source"), c.get("title"))
        pool = trusted

        # If a trusted, non-marketplace merchant quoted a price here, anchor
        # the price-sanity check on that instead of the survivor pool's own
        # median — clone listings routinely outnumber the one genuine listing
        # for a query, which otherwise drags the median low enough that no
        # clone reads as an outlier relative to the others. No anchor means no
        # such merchant showed up — falls back to the median check unchanged.
        #
        # Anchored and outlier-filtered *per variant group*, not across the
        # whole pool — a query like "AirPods" can match both real AirPods and
        # the much pricier AirPods Max in the same token-matched pool, and
        # they aren't clones of each other, just two different real products.
        # Grouping first (same signature the final dedup step already uses)
        # means Max's price only ever anchors other Max listings, never the
        # cheaper AirPods line's own sanity check.
        by_variant: dict[tuple, list[dict]] = {}
        for c in pool:
            by_variant.setdefault(_extract_variant_signature(c["title"], exclude), []).append(c)

        # Floor anchor computed across the *whole* matched pool — used only
        # when a variant group has no trusted price of its own to anchor on.
        # Without this, a group that's just an odd wording of a known clone
        # (a seller-name prefix, a typo) and happens to have no genuine
        # listing of its own exact wording would get zero price-sanity check
        # at all, since a lone/marketplace-only group has nothing internal to
        # compare against.
        pool_wide_anchor = _priority_merchant_anchor(pool, merchant_key="source")

        vetted: list[dict] = []
        for group in by_variant.values():
            own_anchor = _priority_merchant_anchor(group, merchant_key="source")
            anchor = own_anchor if own_anchor is not None else pool_wide_anchor
            if anchor is not None:
                threshold = 0.4 * anchor
                above = [c for c in group if (c.get("price") or 0) >= threshold or not c.get("price")]
                for c in group:
                    if c not in above:
                        logger.info(
                            "%s   dropped (price %s below %s anchor threshold %.0f): %r",
                            tag, c.get("price"),
                            "same-variant" if own_anchor is not None else "pool-wide fallback",
                            threshold, c.get("title"),
                        )
                group = above

            # Defense-in-depth against price anomalies within the now-trusted
            # set (e.g. a stale/broken scrape price) — same 40%-of-median
            # threshold already used for L1 route results, same per-variant
            # scoping as the anchor check above.
            group, removed_count = _outlier_filter(group)
            if removed_count:
                logger.info("%s   dropped %d listing(s) as same-variant price outliers", tag, removed_count)
            vetted.extend(group)
        return vetted

    # hygienic is already gated to bulk/non-Latin/no-token-overlap survivors
    # above; everything left goes straight through trust + price vetting.
    survivors = _vet(hygienic)

    if not survivors:
        logger.info("%s no survivors after trust/price vetting", tag)
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
                logger.info(
                    "%s   %r (%s) replaces cheaper duplicate %r (%s) in same group",
                    tag, c.get("title"), c.get("price"), existing.get("title"), existing.get("price"),
                )
                groups[key] = c
            else:
                logger.info(
                    "%s   %r (%s) dropped as duplicate of %r (%s)",
                    tag, c.get("title"), c.get("price"), existing.get("title"), existing.get("price"),
                )

    # Keep Google's own relevance order — the genuine product ranks near the
    # top there. Sorting the picker by price instead floats the cheapest
    # listing up, which is usually a refurb/clone/wrong-variant, so the wrong
    # product leads the list.
    grouped = [groups[k] for k in order][:_MAX_CANDIDATES]

    # Weak-match warning: only when a category-only query hasn't already
    # opted every listing out of word-matching entirely, and only when the
    # very best survivor still falls short of _STRONG_MATCH_FRACTION — one
    # strong match among several weak ones is still a real answer, not an
    # approximate one.
    if category_only or not tokens:
        approximate = False
    else:
        best_fraction = max(
            (_required_token_match_fraction(c["title"], tokens) for c in grouped),
            default=1.0,
        )
        approximate = best_fraction < _STRONG_MATCH_FRACTION
        if approximate:
            logger.info(
                "%s weak match: best survivor only overlaps %.0f%% of required tokens %r",
                tag, best_fraction * 100, tokens,
            )

    return grouped, approximate


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
    source = p.get("seller") or p.get("source") or p.get("store") or ""
    return {
        "product_token": p.get("product_token"),
        "title": p.get("title") or "",
        "price": price,
        "price_raw": p.get("price"),
        "thumbnail": p.get("thumbnail") or p.get("image"),
        "source": source,
        "rating": p.get("rating"),
        "reviews": p.get("reviews"),
        "has_voucher": bool(source) and (
            voucher_repository.get_by_merchant(source) is not None
            or maximize_repository.get_by_merchant(source) is not None
            or buyhatke_repository.get_by_merchant(source) is not None
        ),
    }


_URL_QUERY_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

# A link shared from a store app arrives with the app's own blurb attached:
# "https://dl.flipkart.com/s/!A4VgYNNNN Take a look at this … on Flipkart".
# The blurb is marketing copy, not the product name, and it makes the input
# fail _URL_QUERY_RE — so the link gets searched as text instead of being
# resolved as the specific page it points at. Pull the link out and drop
# everything else.
_EMBEDDED_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# Sentence punctuation that can end up glued to a link ("…/p/itm123."). '!'
# is deliberately absent — Flipkart's own short links contain it.
_URL_TRAILING_PUNCT = ".,;:'\"“”‘’>)]}"


def _extract_pasted_url(text: str) -> str | None:
    """The first http(s) link inside a message, or None if there isn't one.

    Position-independent: the blurb can precede the link as easily as follow
    it, depending on which app did the sharing."""
    match = _EMBEDDED_URL_RE.search(text)
    if not match:
        return None
    url = match.group(0).rstrip(_URL_TRAILING_PUNCT)
    return url or None

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

# Product-photo sources in the page head, best first — the same og:image /
# twitter:image tags every storefront already sets for link-preview cards
# (WhatsApp/iMessage/Slack use these to show a thumbnail when a link is
# shared), so no per-site scraping is needed. Same attribute-order handling
# as _META_TITLE_RES.
_META_IMAGE_RES = [
    re.compile(
        r"""<meta[^>]+(?:property|name)=["']og:image["'][^>]+content=["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']og:image["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+(?:property|name)=["']twitter:image["'][^>]+content=["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']twitter:image["']""",
        re.IGNORECASE,
    ),
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
    # Myntra serves this placeholder instead of the real page to some
    # server-side/data-center IPs (confirmed against the production
    # deployment 2026-07-22 — works fine from a normal residential
    # connection, but every Myntra link failed the same way from the
    # deployed backend). Rejecting it here means the caller falls through to
    # slug extraction, which reads the pasted URL's own words directly and
    # doesn't depend on what Myntra's server chooses to return — so a link
    # with a descriptive slug still resolves correctly even while the
    # underlying IP-block persists. See CLAUDE.md's vendor-coverage note.
    "site maintenance",
    # A smart-link/app-deeplink URL (AppsFlyer's onelink.me, and similar
    # device-redirect infra) has no real product behind it for a plain fetch
    # to read — it just serves the storefront's own generic homepage, whose
    # <title> otherwise reads as legitimate, real text and gets searched
    # literally. Live-tested 2026-08-27: an AJIO onelink.me share link
    # ("ajioapps.onelink.me/ybtf/6rf4i64g", meant to open the app to a
    # specific Air Force 1 listing) served AJIO's own homepage title
    # ("Online Shopping Site for Women, Men, Kids Fashion, Lifestyle &
    # More."), which then got searched as if it were the product name —
    # returning random unrelated kids' clothing. This exact marketing phrase
    # (or a close variant of it) is the standard homepage <title> for
    # several major Indian storefronts, not just AJIO, so it's a real,
    # generic bot-wall-equivalent signal worth catching broadly, not a
    # one-off AJIO special case.
    "online shopping site for",
)
_BARE_STORE_TITLES = frozenset(
    {"amazon.in", "amazon", "flipkart", "flipkart.com", "myntra", "nykaa", "ajio"}
)

# ── live Amazon price read (Amazon only — see search_service module docstring
#    for why the react-migration removed live page price extraction entirely,
#    and CLAUDE.md bug 1) ──────────────────────────────────────────────────────

# amazon.in only, deliberately — amazon.com prices in USD, and the buybox
# regex below reads only a bare number ("a-price-whole"), with no currency
# symbol/code to check. Live-tested 2026-08-26: an amazon.com Echo Dot's real
# $-price came back stamped "₹79" because nothing here ever looks at
# currency. Dealo doesn't price non-INR listings at all (per product rule),
# so the honest fix is to never treat amazon.com's number as rupees, not to
# label or convert it — amazon.com links still resolve by page title, just
# without a live price pinned on top of the index price.
_AMAZON_HOST_RE = re.compile(r"(?:^|\.)amazon\.in$", re.IGNORECASE)

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
    # Verified 2026-07-28 on 2 real products (PS5 Slim console ₹49,990 and a
    # Samsung microSD card ₹1,049) — offers.price matched the page's own
    # displayed selling price exactly on both.
    "reliancedigital.in": "Reliance Digital",
    # Verified 2026-07-28: a vivo T5 Lite listing's offers.price (₹19,999,
    # inside an AggregateOffer but with a real single `price` field, not just
    # a lowPrice/highPrice range) matched the page's own regularPrice/
    # finalPrice fields exactly (no discount active at verification time).
    "vijaysales.com": "Vijay Sales",
    # Verified 2026-07-28: apple.com/in only exposes a single offers.price
    # on a specific-model buy link (e.g. a configured MacBook Air SKU, ₹149,900
    # — matched the page's own displayed price exactly). Its family/range
    # pages (e.g. the general "buy Mac" page) only expose lowPrice/highPrice
    # with no `price` field, which this dict's extractor already treats as
    # "no live price" rather than guessing — confirmed safe on 2 range pages
    # (MacBook Air, iPhone 17) before adding this entry.
    "apple.com": "Apple",
    # Verified 2026-07-28: a women's hiking shorts listing's offers.price
    # (₹699) matched the page's own "selling-price" field exactly, not its
    # ₹1,199 struck-through MRP.
    "decathlon.in": "Decathlon",
    # Verified 2026-07-28: a PUMA sneaker's offers.price (₹4,949) matched the
    # page's own "item-sale-price-pdp" element exactly.
    "in.puma.com": "PUMA",
    # Verified 2026-07-28: a Chumbak mug's offers.price (₹664) matched 3
    # independent internal data points on the same page (Shopify variant
    # price, analytics payload, product JSON) — the visible DOM price wasn't
    # a reliable single check here since the page also renders a "you may
    # also like" carousel with other products' prices nearby.
    "chumbak.com": "Chumbak",
    # Verified 2026-07-28: IKEA's AggregateOffer only has lowPrice/highPrice
    # at the top level (a range across sibling color variants), but nests a
    # real single Offer for this exact page's own SKU underneath — its price
    # (₹10,990) matched the page's own displayed "pipcom-price__integer"
    # exactly. Required a small, generic addition to _extract_jsonld_price
    # to also check that nested offer (see its docstring) — not a per-site
    # scraper, still reading a field the site itself already labels.
    "ikea.com": "IKEA",
    # Verified 2026-07-28: an American Tourister backpack's offers.price
    # (₹1,925) matched the price embedded in the page's own product data
    # consistently across every occurrence on the page.
    "americantourister.in": "American Tourister",
    # Verified 2026-07-28: lifestylestores.com's JSON-LD is HTML-entity-
    # encoded in its raw markup (&quot; instead of ") — invalid JSON until
    # unescaped, which is why the generic html.unescape() step above was
    # added rather than a per-site fix. Once decoded, a Minimalist body
    # lotion's offers.price (₹269) matched the page's own displayed price
    # exactly.
    "lifestylestores.com": "Lifestyle",
    # Verified 2026-07-28: a Titan eyeglasses listing's offers.price (₹6,300)
    # matched the page's own "qa__current-price" element exactly.
    "titaneyeplus.com": "Titan Eye+",
    # Verified 2026-07-28: a GIVA pendant set's offers.price (₹5,999)
    # matched the site's own internal variant price (599900 paise) exactly.
    "giva.co": "GIVA",
    # Verified 2026-07-28: a Westside knitted top's offers.price (₹799)
    # matched the page's own displayed price exactly.
    "westside.com": "Westside",
    # Verified 2026-07-28: a Himalaya baby lotion's offers.price (₹210)
    # matched the page's own "product__price" element exactly.
    "himalayawellness.in": "Himalaya Wellness",
    # Verified 2026-07-28: a Wonderchef juicer's offers.price (₹12,099)
    # matched the site's own internal variant price (1209900 paise) exactly.
    "wonderchef.com": "Wonderchef",
    # Verified 2026-07-28: a W for Woman dupatta's offers.price (₹1,000)
    # matched the site's own internal variant price (100000 paise) exactly,
    # with no compare-at/MRP set (no discount active at verification time).
    "wforwoman.com": "W for Woman",
    # Verified 2026-07-28: a BIBA lehenga set's offers.price (₹9,995) matched
    # the page's own internal "price"/"mrp" fields exactly (equal — no
    # discount active at verification time).
    "biba.in": "BIBA",
    # Verified 2026-07-28: a Home Centre sofa cushion's offers.price (₹7,267)
    # matched the price already surfaced in the page's own title/meta tags.
    "homecentre.in": "Home Centre",
    # Verified 2026-07-28: a Titan watch's offers.price (₹14,555) matched
    # the price embedded in the page's own product data exactly.
    "titan.co.in": "Titan",
    # Verified 2026-07-28: a Fastrack watch's offers.price (₹1,650) matched
    # the price embedded in the page's own product data exactly.
    "fastrack.in": "Fastrack",
    # Verified 2026-07-28: a Tanishq necklace's offers.price (₹45,290)
    # matched the price embedded in the page's own product data exactly.
    "tanishq.co.in": "Tanishq",
    # Verified 2026-07-28: a Jockey brief's offers.price (₹449) matched the
    # site's own internal variant price (44900 paise) exactly.
    "jockey.in": "Jockey",
    # Verified 2026-07-28: a Skechers shoe's offers.price (₹8,999) matched
    # the price embedded in the page's own product data exactly.
    "skechers.in": "Skechers",
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


# Anti-bot fallback (2026-08-06): these hosts block or reject Dealo's plain
# direct fetch above outright (Myntra only from our deployed server; the
# other 3 everywhere) — see CLAUDE.md's "Live price-on-paste vendor
# coverage". Apify's official web-scraper actor (apify_repository.
# fetch_rendered_html) fetches the real page past the block; the price is
# then read via the same trusted _extract_jsonld_price used below for the
# free path, not a third-party actor's own parsing. Each host verified
# 2026-08-06 against a real pasted product link, cross-checked against an
# independent price source: Flipkart (₹1,099, matched the page's own
# schema.org offers.price), Nykaa (₹1,899, matched an independent Apify
# actor's reading of the same product), AJIO (₹2,587, matched an
# independent Apify actor's reading — also required extending
# _extract_jsonld_price to accept AJIO's "ProductGroup" schema type, not
# just "Product"), Myntra (₹759, matched an independent Apify actor's
# reading of the same product — the render+extract mechanism itself is
# confirmed working; the actual Render-server block that motivated this
# entry couldn't be reproduced from this local environment, so this is
# proven-correct-if-triggered rather than reproduced-and-fixed).
_APIFY_MERCHANT_HOSTS = {
    "flipkart.com": "Flipkart",
    "ajio.com": "AJIO",
    "nykaa.com": "Nykaa",
    "myntra.com": "Myntra",
}


def _apify_merchant_for_host(host: str) -> str | None:
    host = (host or "").lower()
    for suffix, merchant_name in _APIFY_MERCHANT_HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return merchant_name
    return None


# Hosts whose page reliably fails to finish loading on EITHER real-browser
# fetcher within a reasonable timeout budget — confirmed on titan.co.in: a
# direct fetch fails fast with a clean 403, but Apify's render twice
# exceeded its 60s budget with nothing to show for the wait (2026-08-26),
# and Crawlbase's own render was blocked outright by a Cloudflare challenge
# after 77s (2026-08-27) — live-tested both. Skipping render entirely for
# these hosts trades a slightly weaker product name (URL-slug words only —
# the same fallback already used for Myntra's server-block issue) for an
# honest, fast result instead of a minute-plus hang that fails anyway on
# every fetcher tried.
_RENDER_SKIP_HOSTS = {"titan.co.in"}


def _should_skip_render(host: str) -> bool:
    host = (host or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in _RENDER_SKIP_HOSTS)


# A stray double separator ("Nike Men Zoom Vomero 5 SP Sneakers -  - Footwear
# for Men") is the fingerprint of the MERCHANT's own page template failing to
# fill in a field — confirmed live on Myntra's /mailers/ social-share pages,
# where og:title itself already ships broken. It isn't natural language on
# any site, so it's caught generically rather than special-cased to one host.
# The text before it is still the real product name (verified against the
# Myntra case above), so the fix truncates there instead of throwing the
# whole title away and falling back to weaker URL-slug words.
_BROKEN_TEMPLATE_RE = re.compile(r"\s-\s*-\s")

# Storefronts append their own site name (and often a generic category tag)
# to the end of a product page's title — "Amazon.in: Electronics",
# "| Ajio.com" — which is never part of the product's own identity. Stripped
# as a trailing suffix, not by guessing category words, so the same rule
# works for every product category on every known storefront rather than
# needing per-category upkeep. Confirmed live 2026-08-28 against real Amazon
# and AJIO product pages — both end exactly this way.
_STOREFRONT_SUFFIX_NAMES = sorted(
    {m.lower() for m in MANUAL_TRUSTED_MERCHANTS} | {
        "amazon.in", "amazon.com", "flipkart.com", "myntra.com",
        "ajio.com", "nykaa.com", "nykaa.in", "croma.com",
        "reliancedigital.in", "vijaysales.com", "tatacliq.com",
        "jiomart.com", "bigbasket.com", "pepperfry.com", "lenskart.com",
        "apple.com", "samsung.com",
    },
    key=len, reverse=True,
)
_STOREFRONT_SUFFIX_RE = re.compile(
    r"[:|\-]\s*(?:" + "|".join(re.escape(n) for n in _STOREFRONT_SUFFIX_NAMES) + r")\b.*$",
    re.IGNORECASE,
)

# A trailing "Online" ("... Sneakers Online | Ajio.com") is call-to-action
# filler the same way a leading "Buy "/"Shop " is — stripped once the
# storefront suffix itself is already gone, so it doesn't linger as an
# orphan word.
_TRAILING_ONLINE_RE = re.compile(r"\s+online$", re.IGNORECASE)


def _extract_page_title(markup: str) -> str | None:
    """og:title -> twitter:title -> <title> from a page's markup, with the
    bot-wall/bare-store rejections applied, or None if none is usable.

    Split out of _fetch_url_page so the Apify-rendered HTML goes through the
    exact same trusted title logic as a direct fetch — a title read past a
    bot wall gets no weaker vetting than one read without it."""
    for pattern in _META_TITLE_RES:
        m = pattern.search(markup)
        if not m:
            continue
        candidate = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        if len(candidate) < 3:
            continue
        # Storefronts routinely prefix their <title>/og:title with a CTA verb
        # ("Buy Nike Air Force 1", "Shop Nike Air Force 1") that names no
        # part of the product — strip it so the resolved name reads as a
        # product name, not a call to action. Confirmed 2026-08-27: Myntra's
        # og:title for the Air Force 1 listing was exactly "Buy Nike Air
        # Force 1", surfaced verbatim to the user as the product name.
        stripped = re.sub(r"^(?:buy|shop)\s+", "", candidate, flags=re.IGNORECASE)
        if len(stripped) >= 3:
            candidate = stripped
        broken = _BROKEN_TEMPLATE_RE.search(candidate)
        if broken:
            candidate = candidate[: broken.start()].strip(" -")
            logger.info("[url-search] truncated broken-template title to %r", candidate)
            if len(candidate) < 3:
                continue
        low = candidate.lower()
        if low in _BARE_STORE_TITLES or any(b in low for b in _BAD_TITLE_MARKERS):
            logger.info("[url-search] rejected page title %r (bot-wall/bare store)", candidate)
            continue
        cleaned = _STOREFRONT_SUFFIX_RE.sub("", candidate).strip(" :|-")
        cleaned = _TRAILING_ONLINE_RE.sub("", cleaned).strip()
        # Whatever's left after the storefront's own suffix is gone, the real
        # product name is still only the first "|"-delimited segment — every
        # real title checked (Amazon, Myntra, AJIO) puts nothing but a
        # marketing spec dump after the first pipe, never a second product or
        # a variant detail that wasn't already stated before it.
        cleaned = cleaned.split("|", 1)[0].strip()
        if len(cleaned) >= 3 and cleaned != candidate:
            logger.info("[url-search] cleaned page title %r -> %r", candidate, cleaned)
            candidate = cleaned
        return candidate
    return None


def _extract_page_image(markup: str, base_url: str) -> str | None:
    """og:image -> twitter:image from a page's markup, resolved to an
    absolute URL against ``base_url`` (a handful of storefronts set a
    protocol-relative or root-relative path rather than a full URL). Same
    layering as _extract_page_title, no per-site scraping — every one of
    these hosts already publishes this tag for link-preview cards. None if
    no usable image tag is present, never raises."""
    for pattern in _META_IMAGE_RES:
        m = pattern.search(markup)
        if not m:
            continue
        candidate = html.unescape(m.group(1)).strip()
        if not candidate:
            continue
        try:
            resolved = urljoin(base_url, candidate)
        except ValueError:
            continue
        if resolved.lower().startswith(("http://", "https://")):
            return resolved
    return None


def _offer_currency_is_inr(offer: dict) -> bool:
    """True unless the offer explicitly names a non-INR currency. Dealo
    doesn't price non-INR listings at all (per product rule), and a
    multi-region storefront in _JSONLD_MERCHANT_HOSTS (ikea.com's /us/ pages,
    live-tested 2026-08-26) can otherwise hand back a real USD price with
    nothing about the number itself to say so — it then gets stamped with a
    ₹ sign as if it were rupees. Absent priceCurrency is accepted as before
    (most already-verified Indian storefronts don't always set it); this
    only rejects a currency that's positively identified as something else."""
    currency = offer.get("priceCurrency")
    return not isinstance(currency, str) or currency.strip().upper() in ("", "INR")


def _extract_jsonld_price(markup: str) -> float | None:
    """The first schema.org Product -> Offer price in a page's own structured
    data, or None. Standard, vendor-agnostic — unlike _extract_amazon_price,
    no per-site markup knowledge needed, because the site itself is already
    labeling this number as "the offer price" for search engines to read."""
    for block in _LDJSON_BLOCK_RE.findall(markup):
        try:
            # Some storefronts (found on lifestylestores.com) HTML-entity-
            # encode their own JSON-LD (&quot; instead of ") — harmless
            # no-op unescape on the (much more common) already-valid case.
            data = json.loads(html.unescape(block))
        except (json.JSONDecodeError, ValueError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            # AJIO (verified 2026-08-06) labels its top-level product block
            # "ProductGroup" rather than "Product" — schema.org's own
            # variant-group type, distinct from Product but structured the
            # same way here: a top-level offers.price sitting alongside a
            # hasVariant list of individual sized options. Confirmed real:
            # its price (₹2,587) matched an independent check on the same
            # product exactly.
            if node.get("@type") not in ("Product", "ProductGroup"):
                continue
            offers = node.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict):
                price = parse_price(offers.get("price")) if _offer_currency_is_inr(offers) else None
                if price is None:
                    # An AggregateOffer (lowPrice/highPrice spanning sibling
                    # variants, e.g. Apple's color options) can still nest a
                    # real single Offer for THIS exact page's own SKU under
                    # its own "offers" list (seen on IKEA) — only trust that,
                    # never lowPrice/highPrice itself, which is a range, not
                    # this product's actual price.
                    nested = offers.get("offers")
                    if isinstance(nested, list):
                        nested = nested[0] if nested else None
                    if isinstance(nested, dict) and _offer_currency_is_inr(nested):
                        price = parse_price(nested.get("price"))
                if price is not None:
                    return price
    return None


# Query param name(s) a mobile-app smart-link redirect (AppsFlyer's OneLink,
# the mechanism behind an app's own "Share" button — confirmed live,
# 2026-08-27, on an ajioapps.onelink.me link) carries the real product page
# in, for the app to open when installed. When the app can't open it (any
# desktop/server fetch, including ours), the redirect chain still lands on
# the storefront's bare homepage — but the real product URL was never lost,
# it's sitting unused in this param the whole time. Only "deep_link_value"
# is confirmed against a real link so far; add another name here only once
# it's actually been seen on a real redirect, not guessed from AppsFlyer's
# docs — same bar as everywhere else in this file.
_DEEPLINK_URL_PARAMS = ("deep_link_value",)


def _deeplink_redirect_target(resp: httpx.Response) -> str | None:
    """The real product URL hiding inside a smart-link's own redirect chain
    (see _DEEPLINK_URL_PARAMS), if this response followed one — None for an
    ordinary redirect (fkrt.co-style; handled separately by
    _use_resolved_host) or no redirect at all. Checked against every hop in
    `resp.history`, not just the first, since a smart-link can redirect more
    than once before the deep-link param appears."""
    for hop in resp.history:
        location = hop.headers.get("location")
        if not location:
            continue
        query = parse_qs(urlsplit(location).query)
        for param in _DEEPLINK_URL_PARAMS:
            values = query.get(param)
            if not values:
                continue
            candidate = values[0]
            if candidate.lower().startswith(("http://", "https://")):
                return candidate
    return None


def _fetch_url_page(url: str) -> tuple[str | None, float | None, str | None, str | None]:
    """One GET for a pasted link (redirects resolved — amzn.in -> amazon.in).
    Returns (title, live_price, live_merchant, image).

    title: og:title -> twitter:title -> <title>, scanned over the first
    200_000 chars, rejected via _BAD_TITLE_MARKERS/_BARE_STORE_TITLES exactly
    as this function's original title-only version always did.

    image: og:image -> twitter:image, resolved to an absolute URL, from the
    same head block as the title — every host on the merchant list already
    publishes this for link-preview cards, so it costs nothing extra to read
    alongside the title. None if absent; never blocks title/price recovery.

    live_price/live_merchant: a verified live price and its merchant name,
    read via _extract_amazon_price (Amazon's own hand-rolled markup — see
    that function) or _extract_jsonld_price (every other host currently in
    _JSONLD_MERCHANT_HOSTS, via each page's own schema.org structured data).
    Checked against the full response body (the price block can sit past the
    200_000-char title-scan cap on a large page). (None, None) for every
    host not covered and on any failure — never raises; a failure here must
    fall straight back to today's title/slug-only search, not break it.

    Apify anti-bot fallback (2026-08-06): Flipkart/AJIO/Nykaa reject this
    plain fetch outright (non-200 or a connection error), so that fallback
    is checked from *both* early-exit paths below, not just after a
    successful fetch with no readable price — the earlier version of this
    hook only checked the latter, which meant it never actually fired for
    the exact "blocked outright" case it was built for.

    Title via Apify (2026-08-10): the fallback used to read only a price out
    of the rendered page and throw the rest away, so a blocked link still
    came back nameless and fell through to slug words — which for a short
    link (dl.flipkart.com/s/<code>) are an opaque code, not a product. It now
    reads the title from that same render, for *any* host, which is what
    makes a blocked or JS-only page searchable at all. Price stays gated on
    _APIFY_MERCHANT_HOSTS; see _try_apify for why the two differ.
    """
    apify_host = (urlsplit(url).hostname or "").lower()
    apify_merchant_name = _apify_merchant_for_host(apify_host)

    def _use_resolved_host(resolved_host: str | None) -> None:
        """Re-derive which merchant's data we trust once httpx's own
        redirect-following reveals the page's real host. A shortened link
        (fkrt.co) is never in the merchant list, but the page it redirects
        to (dl.flipkart.com) may be — matching on the pre-redirect host was
        the actual reason shortened links to a known merchant fell through
        to an unrecognized-host fallback instead of the merchant's normal
        Apify/JSON-LD handling."""
        nonlocal apify_host, apify_merchant_name
        resolved_host = (resolved_host or "").lower()
        if resolved_host and resolved_host != apify_host:
            apify_host = resolved_host
            apify_merchant_name = _apify_merchant_for_host(apify_host)

    def _try_render(
        need_title: bool = True,
    ) -> tuple[str | None, float | None, str | None, str | None]:
        """Render the page through a real browser and read a title (any
        host), a photo (any host), and, where we already trust the host's
        structured data, a price. Returns (title, price, merchant, image).

        Tries Crawlbase first, Apify only if Crawlbase returns nothing —
        Crawlbase is the default fetcher as of 2026-08-27 (faster and
        live-tested correct on 11 of 13 real blocked/JS-heavy hosts: only
        AJIO and Titan resisted it), Apify stays wired in as a second
        attempt specifically for those holdouts rather than being dropped
        outright, since it does get past AJIO's block most of the time.

        One successful render serves all three: rendering is the expensive
        part, so a page fetched for its title reads its price and photo
        from the same HTML for free. Skipped entirely when there's nothing
        left to recover.
        """
        need_price = apify_merchant_name is not None
        if not need_title and not need_price:
            return None, None, None, None
        if _should_skip_render(apify_host):
            logger.info(
                "[url-search] skipping render for %s (known to exceed timeout on every fetcher)",
                apify_host,
            )
            return None, None, None, None

        markup = crawlbase_repository.fetch_rendered_html(url)
        render_source = "Crawlbase"
        if not markup:
            logger.info(
                "[url-search] Crawlbase render returned nothing for %s — trying Apify",
                apify_host,
            )
            markup = apify_repository.fetch_rendered_html(url)
            render_source = "Apify"
        if not markup:
            logger.info(
                "[url-search] render returned nothing for %s (Crawlbase + Apify both failed)",
                apify_host,
            )
            return None, None, None, None

        render_title = _extract_page_title(markup) if need_title else None
        if render_title:
            logger.info("[url-search] title via %s: %r", render_source, render_title)
        elif need_title:
            logger.info("[url-search] %s render had no usable title for %s", render_source, apify_host)

        render_image = _extract_page_image(markup, url)
        if render_image:
            logger.info("[url-search] image via %s: %s", render_source, render_image)

        # Price stays gated on the host list: _extract_jsonld_price is
        # generic, but "which hosts' structured data has been hand-checked
        # against the page's real selling price" is not — an unverified host
        # could be handing us an MRP or a range. A title is a name; a price
        # is a promise, and only the second one needs the whitelist.
        render_price = _extract_jsonld_price(markup) if need_price else None
        if render_price is not None:
            logger.info(
                "[url-search] %s live price via %s: %s", apify_merchant_name, render_source, render_price
            )
        elif need_price:
            logger.info("[url-search] %s fallback found no price for %s", render_source, apify_host)
        return (
            render_title,
            render_price,
            apify_merchant_name if render_price is not None else None,
            render_image,
        )

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
        deeplink_target = _deeplink_redirect_target(resp)
        if deeplink_target and deeplink_target != url:
            # The real product URL was riding along in the smart-link's own
            # redirect the whole time — whatever the final followed page
            # actually shows (a bare homepage, a 403, anything) is beside
            # the point once this exists. Re-run the exact same fetch logic
            # against it instead of the smart-link itself, one level deep
            # only (this target is a real storefront URL from a query
            # param, never another smart-link, so no loop risk).
            logger.info(
                "[url-search] %s is a smart-link — resolved real product URL: %s",
                url, deeplink_target,
            )
            return _fetch_url_page(deeplink_target)
        _use_resolved_host(resp.url.host)
        if resp.status_code != 200:
            return _try_render()
        full_markup = resp.text
        # The title lives in <head>, early in the document; cap the text we
        # scan for it so a huge product page doesn't turn into a huge regex
        # pass. The price block can sit further down, so it's read from the
        # full body below instead.
        markup = full_markup[:200_000]
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("[url-search] page-fetch failed for %s: %s", url, exc)
        return _try_render()

    title = _extract_page_title(markup)
    if title:
        logger.info("[url-search] using page title: %r", title)
    else:
        logger.info("[url-search] no usable title found in page")

    image = _extract_page_image(markup, str(resp.url))
    if image:
        logger.info("[url-search] using page image: %s", image)

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

    # A 200 that yielded neither a name nor a price is a soft block (a shell
    # page, or a bot wall that didn't bother with a 403) — worth one render.
    if price is None or title is None:
        render_title, render_price, render_merchant, render_image = _try_render(
            need_title=title is None
        )
        title = title or render_title
        image = image or render_image
        if render_price is not None:
            price, merchant = render_price, render_merchant

    if price is None:
        merchant = None

    return title, price, merchant, image


# Prefix marking a candidate's product_token as synthetic (not a real
# SearchApi.io token) — used both to build the token and, in
# build_routes_for_token, to recognize and skip a get_product() lookup that
# would otherwise waste a paid SearchApi call on an ID nothing can resolve.
_LIVE_PRICE_TOKEN_PREFIX = "live-price:"


def _live_price_candidate(
    url: str, title: str | None, price: float, source: str, image: str | None = None
) -> dict:
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
        "thumbnail": image,
        "source": source,
        "rating": None,
        "reviews": None,
    }


def _maybe_widen_brand_query(
    effective_query: str,
    is_url: bool,
    shopping_results: list[dict],
    products: list[dict],
    approximate: bool,
    tag: str,
) -> tuple[list[dict], bool]:
    """If a brand-qualified search (e.g. "Apple AirPods") came back thin, also
    try the same search with the brand word removed (e.g. "AirPods") and merge
    in whatever new candidates that turns up, then re-run the exact same
    filter/vet pipeline over the combined pool.

    General rule, not a per-product special case: it only fires when a
    recognized brand word is actually present in the query AND the first pass
    is thin — a healthy brand-qualified search (e.g. "Sony headphones"
    already returning plenty of real Sony listings) never triggers this, so
    it can't accidentally pull in other brands' products.

    Never applied to pasted links (`is_url`) — there, `effective_query` is a
    page title/slug already describing one specific product, not a typed
    brand+product phrase.
    """
    if is_url or len(products) >= _THIN_RESULT_THRESHOLD:
        return products, approximate
    widened_query = _strip_known_brands(effective_query)
    if not widened_query:
        return products, approximate
    logger.info(
        "%s thin result (%d) for %r — widening with brand-stripped query %r",
        tag, len(products), effective_query, widened_query,
    )
    raw2 = searchapi_repository.search_products(widened_query)
    if raw2.get("error"):
        logger.info("%s widened query failed: %s", tag, raw2["error"])
        return products, approximate
    shopping_results2 = raw2.get("shopping_results", [])
    seen_tokens = {r.get("product_token") for r in shopping_results if r.get("product_token")}
    new_raw = [
        r for r in shopping_results2
        if r.get("product_token") and r.get("product_token") not in seen_tokens
    ]
    if not new_raw:
        logger.info("%s widened query returned no new candidates", tag)
        return products, approximate
    logger.info("%s widened query returned %d new raw result(s)", tag, len(new_raw))
    combined_raw = [
        _product_candidate(p) for p in shopping_results if p.get("product_token")
    ]
    for p in new_raw:
        candidate = _product_candidate(p)
        candidate["_widened"] = True
        combined_raw.append(candidate)
    widened_products, widened_approximate = _filter_and_group_candidates(
        combined_raw, effective_query, tag=tag
    )
    if len(widened_products) > len(products):
        logger.info(
            "%s widened from %d to %d candidate(s) using brand-stripped query",
            tag, len(products), len(widened_products),
        )
        return widened_products, widened_approximate
    return products, approximate


def search_candidates(query: str) -> dict:
    """Step 1 of the two-step flow: google_shopping search only.

    Returns the list of candidate products the user picks from — does NOT run
    the (slow) google_product call. Never raises.

    ``approximate`` is True when nothing matched the query exactly and these
    are the closest trustworthy matches instead — the caller should say so
    rather than presenting them as the thing that was asked for."""
    query = (query or "").strip()
    if not _URL_QUERY_RE.match(query):
        pasted_url = _extract_pasted_url(query)
        if pasted_url:
            logger.info(
                "[url-search] stripped shared-link blurb, searching the link only: %s",
                pasted_url,
            )
            query = pasted_url
    out = {"query": query, "products": [], "error": None, "approximate": False}
    if not query:
        out["error"] = "Empty query."
        return out
    is_url = bool(_URL_QUERY_RE.match(query))
    # Shared log prefix for this call — lets a plain typed search show the
    # same step-by-step detail a pasted link already gets, instead of only
    # ever logging for links.
    tag = "[url-search]" if is_url else "[search]"
    # A brand-name query (e.g. "myntra gift card") can't be priced by L1 at
    # all — Dealo doesn't price flights/hotels/experiences, and the brand
    # match is itself the useful signal — so skip URL/SerpAPI/candidate
    # search entirely and go straight to the Gyftr voucher. Never applies to
    # a pasted link: a URL always names one specific product page, so it
    # must go through L1 price discovery, never the brand-only shortcut
    # (a brand's name showing up inside a URL's path/slug is not the same
    # signal as a user typing just that brand name).
    matched_voucher = None if is_url else _match_brand_voucher(query)
    if matched_voucher:
        out["mode"] = "brand_voucher"
        out["voucher"] = matched_voucher
        return out
    # A pasted link is turned into a search query without scraping the product:
    # its page title first, then its slug words. The response still echoes
    # the original input in ``query``.
    effective_query = query
    live_candidate = None
    if is_url:
        # Two-layer link recognition, cheapest-reliable first:
        #   1. the page's own og:title (handles short/ID-only links),
        #   2. words from the URL slug.
        # The same fetch also recovers a live price when the link is a page
        # we know how to read — see _fetch_url_page / _live_price_candidate.
        logger.info("[url-search] input is a link: %s", query)
        page_title, live_price, live_merchant, page_image = _fetch_url_page(query)
        effective_query = page_title
        layer = "page-title"
        if not effective_query:
            effective_query = _query_from_url(query)
            layer = "url-slug"
        if live_price is not None and live_merchant:
            live_candidate = _live_price_candidate(
                query, page_title, live_price, live_merchant, page_image
            )
            logger.info("[url-search] live %s price captured: %s", live_merchant, live_price)
        if not effective_query:
            # Neither the page's own title nor its URL slug named a product.
            # The old third layer searched the bare link text itself as a
            # last resort — that's nonsense as a search query and returns
            # unrelated junk instead of an honest "couldn't find this". A
            # live-fetched price still stands on its own here (possible,
            # though rare, if the title was rejected as a blocked-page
            # placeholder while the price read separately still succeeded).
            if live_candidate:
                out["products"] = [live_candidate]
                return out
            logger.info("[url-search] no product identifiable from link")
            out["error"] = (
                "Couldn't find a product on that page — try pasting the "
                "product's own page link, or search by name instead."
            )
            return out
        logger.info(
            "[url-search] searching via %s -> query=%r", layer, effective_query
        )
    elif _is_category_only_query(effective_query, _required_tokens(effective_query)):
        # Never touches a URL-derived query (that's one specific page, not a
        # category to browse) or a brand/model-qualified query (guarded by
        # `_is_category_only_query` itself) — see `_canonicalize_category_words`.
        canonical_query = _canonicalize_category_words(effective_query)
        if canonical_query != effective_query:
            logger.info(
                "%s category query canonicalized for search: %r -> %r",
                tag, effective_query, canonical_query,
            )
            effective_query = canonical_query
    # A pasted link's own page title/slug is the human-readable name of what
    # was actually searched — surface it so the picker/results screens never
    # have to fall back to showing the raw URL (`query`) to the user.
    if is_url and effective_query:
        out["resolved_query"] = effective_query
    try:
        logger.info("%s query sent to SearchApi: %r", tag, effective_query)
        raw = searchapi_repository.search_products(effective_query)
        if raw.get("error"):
            # A live Amazon price stands on its own even if the broader
            # Google Shopping search is down — don't lose it to an
            # unrelated API failure.
            if live_candidate:
                out["products"] = [live_candidate]
                return out
            logger.info("%s google api error: %s", tag, raw["error"])
            out["error"] = raw["error"]
            return out
        shopping_results = raw.get("shopping_results", [])
        logger.info(
            "%s google api returned %d raw result(s):",
            tag, len(shopping_results),
        )
        for r in shopping_results:
            logger.info(
                "%s   raw: %r | %s | %s | token=%s",
                tag,
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
        products, approximate = _filter_and_group_candidates(products, effective_query, tag=tag)
        products, approximate = _maybe_widen_brand_query(
            effective_query, is_url, shopping_results, products, approximate, tag
        )
        # A pasted link's "budget" never came from the user — it's whatever
        # promotional badge happened to be sitting in the page's own title
        # ("Upto 50% to 80% OFF"), and treating that as an intended price
        # ceiling silently zeroed out every real result on the fkrt.co
        # shortened-link test (32 genuine Flipkart candidates -> 0). Budget
        # phrases only mean something when the user typed them themselves.
        min_price, max_price, budget_phrase = (None, None, None) if is_url else parse_budget(effective_query)
        if budget_phrase:
            before_count = len(products)
            products = _apply_budget_filter(products, min_price, max_price)
            logger.info(
                "%s budget %r parsed (min=%s max=%s) -> %d of %d candidate(s) in range",
                tag, budget_phrase, min_price, max_price, len(products), before_count,
            )
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
            logger.info("%s no candidates after filtering", tag)
            out["error"] = "No products found — try adding the brand name, or search with different words."
            return out
        out["products"] = products
        out["approximate"] = approximate
        logger.info(
            "%s %d candidate(s)%s:",
            tag, len(products), " (approximate)" if approximate else "",
        )
        for p in products:
            logger.info(
                "%s   - %r | %s | %s%s",
                tag, p.get("title"), p.get("source"), p.get("price"),
                " [widened-in]" if p.get("_widened") else "",
            )
    except Exception as e:  # never leak a stack trace
        logger.info("%s search error: %s: %s", tag, type(e).__name__, e)
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


def _find_seller_link(candidates: list[dict], source: str) -> dict | None:
    """Best-effort recovery of a real seller link for `source` from a
    candidate pool that may include merchants the trust filter would
    otherwise strip — used only to attach a working link to an already-
    pinned candidate, never to admit an untrusted merchant as a route on its
    own. Fallback path only — see _find_pdp_candidate, which is tried first
    and is more precise (it verifies the candidate came from the exact
    picked listing's own product-detail fetch, not just a matching merchant
    name).

    Returns the whole matching candidate (not just its `sellers`) so the
    caller can take its price too — the price and the link this recovers
    always come from the same object, never the earlier, possibly-stale
    `picked_price` glued onto a different listing's link (the exact "price
    doesn't match the merchant page" bug this replaced).

    Matches on `_brand_signature`, not a plain string/`_norm` equality — the
    picker's search endpoint and this function's own candidate pool (from
    the product-detail endpoint) can name the same store differently
    ("Amazon" vs "Amazon.in"); the fallback needs to recognize those as the
    same merchant just as much as `_dedup_by_merchant`/`_find_pdp_candidate`
    already do, or it silently returns no link at all for a store it should
    have found one for."""
    sig = _brand_signature(source)
    if not sig:
        return None
    for c in candidates:
        if _brand_signature(c.get("merchant") or "") == sig and c.get("sellers"):
            return c
    return None


def _find_pdp_candidate(
    candidates: list[dict], source_token: str, picked_source: str,
    picked_price: float | None = None,
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
    `_find_seller_link`'s. Requires a parsed price.

    When product_token's own fetch returns more than one offer under this
    merchant, prefers whichever price is CLOSEST to `picked_price` — the
    number the user actually saw and clicked on the Product Picker — rather
    than blindly the lowest. Confirmed live (Samsung 65" QLED case): Google's
    own shopping data can attach two genuinely different real prices (almost
    certainly two different screen sizes) to what it treats as one merged
    product token/merchant pair. Picking "whichever is cheapest" there
    silently swaps the user's actual pick for a different, cheaper item they
    never chose — the opposite of what a "pin the exact listing" mechanism
    is for. Falls back to lowest-price (the old behavior) when
    `picked_price` isn't available.

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
    if picked_price is not None:
        return min(matches, key=lambda c: abs(c["price"] - picked_price))
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

        # The picked token's own detail fetch doesn't depend on the refined
        # search at all (it's already known before the refined search even
        # runs) — kicking it off in parallel here, instead of after, removes
        # one whole sequential SearchApi round trip (typically several
        # seconds) from every /routes call.
        executor = ThreadPoolExecutor(max_workers=1 + _ROUTE_TOKEN_CAP)
        primary_future = (
            executor.submit(searchapi_repository.get_product, product_token)
            if not product_token.startswith(_LIVE_PRICE_TOKEN_PREFIX)
            else None
        )

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

            # The picked candidate's own title can drop a size the user's
            # ORIGINAL query stated (e.g. the Product Picker fell back to a
            # generic "Samsung Q80A QLED 4K Smart TV" match with no size in
            # it at all) — `required`/the variant-signature check below only
            # ever look at `variant_query` (title-first), so neither would
            # catch this. Pull size from the raw `query` directly and, if the
            # user actually stated one, require every refined candidate to
            # state that same size explicitly — a cheaper, unverified-size
            # listing should never be able to win "Recommended" just because
            # neither title happens to mention its size in a comparable way.
            query_size_m = _SIZE_RE.search(_norm_title(query))
            if query_size_m:
                required_size = f"{query_size_m.group(1)}inch"
                refined = [
                    c for c in refined
                    if (m := _SIZE_RE.search(_norm_title(c["title"])))
                    and f"{m.group(1)}inch" == required_size
                ]

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
            # Hyperlocal apps sort last here too — otherwise a cheap
            # Blinkit/Zepto/etc. listing could claim one of the limited
            # fetch slots below ahead of a normal, location-independent
            # merchant, before _build_routes even gets a chance to prefer
            # the latter.
            refined.sort(
                key=lambda c: (
                    _is_hyperlocal(c.get("merchant") or ""),
                    c.get("price") if c.get("price") is not None else float("inf"),
                )
            )
            tokens_to_fetch = [c["product_token"] for c in refined[:_ROUTE_TOKEN_CAP]]

        # The originally-selected token was already vetted against the full
        # Product Picker candidate pool (including its own trust/price
        # checks) — a narrower refined search finding something else is not
        # grounds to drop it, only to potentially outrank it later. Consumed
        # FIRST below, not appended: the user's own pick must win the
        # `display_title` claim whenever its own fetch succeeds — not
        # whichever refined-search token happened to load first.
        tokens_to_fetch = [t for t in tokens_to_fetch if t != product_token]

        # A live-fetched candidate (e.g. an Amazon price read straight off a
        # pasted link) never came from SearchApi.io, so it has no real
        # product_token to look up — skip it rather than spending a paid
        # SearchApi call on an ID nothing can resolve. It still reaches the
        # route via the picked_price/picked_source pin below.
        detail_futures = {
            token: executor.submit(searchapi_repository.get_product, token)
            for token in tokens_to_fetch
            if not token.startswith(_LIVE_PRICE_TOKEN_PREFIX)
        }

        candidates: list[dict] = []
        display_title = ""

        def _consume(token: str, detail: dict) -> None:
            nonlocal display_title
            if detail.get("error"):
                return
            product = detail.get("product") or {}
            display_title = display_title or product.get("title") or detail.get("title") or ""
            candidates.extend(_build_candidates(detail, source_token=token))

        primary_detail = primary_future.result() if primary_future is not None else None
        if primary_detail is not None:
            _consume(product_token, primary_detail)
        for token, future in detail_futures.items():
            _consume(token, future.result())

        executor.shutdown(wait=False)

        if not candidates and not product_token.startswith(_LIVE_PRICE_TOKEN_PREFIX):
            # Refined search came up empty or every fetch failed — fall back
            # to the originally selected token alone. Cheap: the primary
            # fetch above already hit the cache/API for this exact token, so
            # this only does real work when that first attempt itself failed.
            detail = (
                primary_detail
                if primary_detail is not None and not primary_detail.get("error")
                else searchapi_repository.get_product(product_token)
            )
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
            pdp_candidate = _find_pdp_candidate(pre_filter_candidates, product_token, picked_source, picked_price)
            if pdp_candidate is not None:
                candidates.append(_pinned_candidate(
                    display_title or title or query,
                    pdp_candidate["price"],
                    picked_source,
                    pdp_candidate.get("sellers") or [],
                ))
            else:
                recovered = _find_seller_link(pre_filter_candidates, picked_source)
                sellers = recovered["sellers"] if recovered else []
                # A live-price token (Amazon/Myntra link-paste) has no
                # SearchApi-fetched offer to recover a link from by design
                # (see _find_pdp_candidate/_find_seller_link docstrings) — but
                # the pasted link itself IS the exact seller page, already
                # known with certainty. Without this, the route had a price
                # and a voucher but no way to actually reach the store: no
                # "Open store"/checkout link and no clickable product image
                # (reported 2026-08-27, the boAt Nike Air Force 1 Myntra link).
                if not sellers and product_token.startswith(_LIVE_PRICE_TOKEN_PREFIX) and _URL_QUERY_RE.match(query):
                    sellers = [{"link": query, "delivery": None}]
                candidates.append(_pinned_candidate(
                    display_title or title or query,
                    recovered["price"] if recovered and recovered.get("price") is not None else picked_price,
                    picked_source,
                    sellers,
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
