"""Shared brand-name matching for voucher repositories (Gyftr, Maximize,
BuyHatke).

Same exact -> prefix -> substring algorithm all sources need to answer
"which brand record matches this merchant name" — factored out so a future
fix to the matching logic only has to happen once.
"""
from __future__ import annotations

import re

_RESELLER_WORDS = (
    "reseller", "authorised", "authorized", "premium",
    "future world", "store", "electronics", "mobile",
)

# BuyHatke bakes its own redemption-channel label straight into hundreds of
# brand names ("Titan Eye Plus In Store", "Trends Man In Store") — the bare
# "store" reseller-word above would otherwise exclude every single one of
# them as a false "reseller listing", found 2026-08-14 when "Titan" and
# "Trends" as merchant names matched nothing at all. Stripped before the
# reseller-word check runs so a real reseller name (hypothetically "XYZ
# Store") still gets caught, but this specific, extremely common legitimate
# phrase doesn't.
_IN_STORE_PHRASE_RE = re.compile(r"\bin[\s-]?store\b", re.IGNORECASE)
_DAY_WAIT_PHRASE_RE = re.compile(r"\(?\d+\s*day\s*wait\)?", re.IGNORECASE)
_ONLINE_WORD_RE = re.compile(r"\bonline\b", re.IGNORECASE)


def _is_reseller_name(brand_name_lower: str) -> bool:
    stripped = _IN_STORE_PHRASE_RE.sub("", brand_name_lower)
    return any(w in stripped for w in _RESELLER_WORDS)


def _channel_stripped_length(name: str) -> int:
    """Length of `name` with known redemption-channel qualifiers (In Store,
    Online, "N Day Wait") removed first — used only to break ties among
    same-rank candidates, never to decide which candidates qualify.

    Without this, a rank-1 tie between a brand's plain listing ("Titan In
    Store 3 Day Wait") and a genuinely different sub-brand ("Titan Eye Plus
    In Store") could resolve in the sub-brand's favour purely because its
    channel suffix ("Eye Plus") happens to be shorter than the other's ("3
    Day Wait") — found 2026-08-14: merchant "Titan" was matching "Titan Eye
    Plus In Store" over the far more generic "Titan In Store 3 Day Wait".
    Stripping the channel words first makes the comparison "Titan" (5) vs
    "Titan Eye Plus" (14) — the actually-plainer match correctly wins.
    """
    stripped = _DAY_WAIT_PHRASE_RE.sub(" ", name)
    stripped = _IN_STORE_PHRASE_RE.sub(" ", stripped)
    stripped = _ONLINE_WORD_RE.sub(" ", stripped)
    return len(normalize(stripped))

# Generic trailing words a merchant's *display* name routinely carries that
# its brand record never does (e.g. search results show "Hamleys India",
# gyftr_master.json has "Hamleys-Luxe Gift Card") — stripped from the END of
# the merchant name only, word-by-word, before matching. Never applied to
# brand_name itself, which is curated data, not a raw store listing.
_GENERIC_MERCHANT_SUFFIX_WORDS = {
    "india", "in", "com", "official", "store", "shop", "online", "in.",
}


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _strip_generic_suffix_words(name: str) -> str:
    """Drop trailing generic words ("Hamleys India" -> "Hamleys"). Stops at
    the first non-generic word from the end, so a real brand word is never
    removed. Falls back to the original name if stripping would empty it."""
    words = name.strip().split()
    while words and re.sub(r"[^a-z0-9]", "", words[-1].lower()) in _GENERIC_MERCHANT_SUFFIX_WORDS:
        words.pop()
    return " ".join(words) if words else name


def find_best_match(merchant_name: str, records: list[dict], name_key: str = "brand_name") -> dict | None:
    """Find the record whose name_key best matches merchant_name.

    Case-insensitive; partial match OK (e.g. "amazon.in" matches "Amazon").
    Prefers the closest/shortest match over more specific sub-brand entries,
    and excludes reseller / authorised-store style entries. Generic trailing
    words on the merchant's own display name ("Hamleys India") are stripped
    before matching so they don't break an otherwise-genuine prefix match
    against the brand record ("Hamleys-Luxe Gift Card").
    """
    norm_merchant = normalize(_strip_generic_suffix_words(merchant_name))
    if not norm_merchant:
        return None

    candidates = []
    for record in records:
        norm_brand = normalize(record.get(name_key, ""))
        if not norm_brand:
            continue
        if norm_brand == norm_merchant:
            rank = 0
        elif len(norm_brand) < 4:
            continue
        elif norm_merchant.startswith(norm_brand) or norm_brand.startswith(norm_merchant):
            rank = 1
        elif norm_brand in norm_merchant or norm_merchant in norm_brand:
            rank = 2
        else:
            continue

        brand_name_raw = record.get(name_key, "")
        if rank >= 1:
            if _is_reseller_name(brand_name_raw.lower()):
                continue
        candidates.append((rank, _channel_stripped_length(brand_name_raw), len(norm_brand), record))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return candidates[0][3]
