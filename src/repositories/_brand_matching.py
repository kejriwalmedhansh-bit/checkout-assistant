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


# A web address ending glued to the last word of a merchant's display name
# ("IGP.com", "ajio.com", "KFC.in"). The word-by-word pass below can't see
# it, because ".com" isn't a word of its own there. Found 2026-11-02: an
# igp.com product page names itself "IGP.com", and after normalising to
# "igpcom" the only partial match on offer was against "igp" — a brand name
# under 4 letters, which the matcher deliberately never partial-matches
# (too many false hits) — so IGP's vouchers on all three sources went
# unfound and the shopper was sent to pay full price.
_DOMAIN_ENDING_RE = re.compile(r"\.(?:com|in|co\.in|net|org|co)$", re.IGNORECASE)


def normalize(name: str) -> str:
    # "&" and "and" are the same word in a shop's name ("Adani Meet & Greet"
    # on its website, "Adani Meet and Greet" in the catalogue), so both read
    # as "and" before the punctuation goes (audit 2026-11-02).
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", " and "))


def _strip_generic_suffix_words(name: str) -> str:
    """Drop trailing generic words ("Hamleys India" -> "Hamleys") and a web
    address ending ("IGP.com" -> "IGP"). Stops at the first non-generic word
    from the end, so a real brand word is never removed, and never leaves
    fewer than four letters behind ("Air India" stays whole: "Air" alone is
    too short to match anything but itself). Falls back to the original
    name if stripping would empty it."""
    words = _DOMAIN_ENDING_RE.sub("", name.strip()).split()
    while (len(words) > 1 and re.sub(r"[^a-z0-9]", "", words[-1].lower()) in _GENERIC_MERCHANT_SUFFIX_WORDS
           and len(normalize(" ".join(words[:-1]))) >= 4):
        words.pop()
    return " ".join(words) if words else name


def find_best_match(merchant_name: str, records: list[dict], name_key: str = "brand_name") -> dict | None:
    """The first of find_matches, or None."""
    matches = find_matches(merchant_name, records, name_key)
    return matches[0] if matches else None


def find_matches(merchant_name: str, records: list[dict], name_key: str = "brand_name") -> list[dict]:
    """Every record whose name_key matches merchant_name, best first.

    Case-insensitive; partial match OK (e.g. "amazon.in" matches "Amazon").
    Prefers the closest/shortest match over more specific sub-brand entries,
    and excludes reseller / authorised-store style entries. Generic trailing
    words on the merchant's own display name ("Hamleys India") are stripped
    before matching so they don't break an otherwise-genuine prefix match
    against the brand record ("Hamleys-Luxe Gift Card").
    """
    norm_merchant = normalize(_strip_generic_suffix_words(merchant_name))
    if not norm_merchant:
        return []

    candidates = []
    for record in records:
        norm_brand = normalize(record.get(name_key, ""))
        if not norm_brand:
            continue
        if norm_brand == norm_merchant:
            rank = 0
        elif len(norm_brand) < 4 or len(norm_merchant) < 4:
            # Too short to partial-match either way: "igp" must not match
            # "igp-something-else", and a store called "EA" must not match
            # "EatSure" (audit 2026-11-02, once ".com" came off "EA.com").
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

    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return [c[3] for c in candidates]
