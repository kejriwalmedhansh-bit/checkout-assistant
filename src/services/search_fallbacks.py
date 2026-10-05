"""What a search turns into when it can't be priced as a product.

Three plain-rule checks, no AI and no outside calls (owner rule):

* a shop name typed with a small spelling slip ("Sketchers") is read as the
  shop it nearly spells — only when nearly identical, since a wrong shop is
  worse than none — plus a hand list for slips the automatic check misses;
* a shop we have no gift card for ("DMart", "Agoda") gets an honest "no deal
  yet" and the gift cards of its kind of shopping instead;
* a grocery search ("Amul butter", "a kilo of atta") skips the product list
  and shows the grocery gift cards — nobody compares prices for one packet.

The word lists live in data/ so the owner can edit them without code:
data/voucher_groups.json and data/grocery_keywords.json.
"""
from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

from ..constants import KNOWN_BRANDS

_DATA = Path(__file__).resolve().parents[2] / "data"

# Same filler the shop-name match allows ("Myntra gift card").
_SHOP_FILLER = frozenset({"gift", "card", "cards", "voucher", "vouchers", "gc", "egift", "epay"})

# A guess at a shop counts only when the spelling is this close (difflib
# ratio). Tested on 14 real slips: 0.88 fixed 9 with no wrong shop; 0.80
# fixed 12 but turned "D mart" into V Mart, a different shop.
_SHOP_CUTOFF = 0.88
# Brand slips: SUS->Asus 0.86, Aple->Apple 0.89; the real word "Ample" is
# 0.80 from Apple and must stay as typed.
_BRAND_CUTOFF = 0.85
_QUANTITY_RE = re.compile(r"^\d+[a-z]{0,5}$")


@lru_cache(maxsize=1)
def _groups_data() -> dict:
    return json.loads((_DATA / "voucher_groups.json").read_text())


@lru_cache(maxsize=1)
def _grocery_data() -> tuple[set, set, set, set, int]:
    raw = json.loads((_DATA / "grocery_keywords.json").read_text())

    def phrases(key: str) -> set[tuple[str, ...]]:
        return {tuple(_words(p)) for p in raw.get(key, []) if _words(p)}

    brands, items = phrases("brands"), phrases("items")
    not_grocery, filler = phrases("not_grocery"), phrases("filler")
    longest = max(len(p) for p in brands | items | not_grocery | filler)
    return brands, items, not_grocery, filler, longest


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower().replace("'", "").replace("’", ""))


def shop_key(query: str) -> str:
    """The query as one spaceless shop key, filler like "gift card" removed."""
    return "".join(w for w in _words(query) if w not in _SHOP_FILLER)


def shop_alias(query: str) -> str | None:
    """A hand-listed spelling ("nyka", "swiggy") -> the search that finds it."""
    return _groups_data()["shop_aliases"].get(shop_key(query))


def no_deal_shop(query: str) -> dict | None:
    """{"name", "group"} when the query is just a shop we have no gift card for."""
    return _groups_data()["no_deal_shops"].get(shop_key(query))


def closest_shop_key(query: str, known_keys) -> str | None:
    """'sketchers' -> 'skechers'. Only a near-identical spelling of a name
    long enough to be distinctive counts; a domain ("booking.com") never
    does. Searches the given shop keys plus the no-deal shops."""
    key = shop_key(query)
    # Shop names are one or two words; a longer search is a product.
    if len(key) < 5 or "." in (query or "") or len(_words(query)) > 2:
        return None
    pool = set(known_keys) | set(_groups_data()["no_deal_shops"])
    hit = difflib.get_close_matches(key, pool, n=1, cutoff=_SHOP_CUTOFF)
    return hit[0] if hit and hit[0] != key else None


def group(name: str) -> dict:
    return _groups_data()["groups"][name]


def is_grocery_query(query: str) -> bool:
    """True when the search is for groceries, by plain word lists:

    * names a grocery brand ("Amul butter", "Lijjat papad"), or
    * is grocery items plus quantities and filler ("a kilo of atta"), with
      at most one unknown word and a grocery word last ("milld atta" yes,
      "rice cooker" no — in English the thing being bought comes last);
    * and in both cases no word that means something else ("cooker",
      "hair", "tv") is present.
    """
    brands, items, not_grocery, filler, longest = _grocery_data()
    words = _words(query)
    if not words or len(words) > 12:
        return False
    found_brand, unknown, last_kind = False, 0, None
    i = 0
    while i < len(words):
        for size in range(min(longest, len(words) - i), 0, -1):
            phrase = tuple(words[i:i + size])
            if phrase in brands or phrase in items:
                found_brand = found_brand or phrase in brands
                last_kind = "grocery"
                break
            if phrase in not_grocery:
                return False
            if phrase in filler or (size == 1 and _QUANTITY_RE.match(phrase[0])):
                break
        else:
            size = 1
            unknown += 1
            last_kind = "unknown"
        i += size
    if found_brand:
        return True
    return last_kind == "grocery" and unknown <= 1


def corrected_brand_query(query: str) -> str | None:
    """'SUS Vivobook 15' -> 'Asus Vivobook 15'. Only the first word — where
    people type the brand — and only against Dealo's own brand list, so a
    real word is never "fixed" into something else."""
    words = (query or "").split()
    if not words:
        return None
    first = words[0]
    low = first.lower()
    single_word_brands = [b for b in KNOWN_BRANDS if " " not in b]
    if len(low) < 3 or not low.isalpha() or low in single_word_brands:
        return None
    hit = difflib.get_close_matches(low, single_word_brands, n=1, cutoff=_BRAND_CUTOFF)
    # "Apples" is the fruit, not a slip for Apple.
    if not hit or low == hit[0] + "s":
        return None
    fixed = hit[0].upper() if len(hit[0]) <= 3 else hit[0].capitalize()
    return " ".join([fixed] + words[1:])


_CARD_SUFFIX_RE = re.compile(r"\s+(e-?gift\s+card|gift\s+card|gift\s+voucher|e-?voucher|voucher|e-?pay)$", re.I)


def shop_display_name(brand_name: str) -> str:
    """"Zomato Gift Card" -> "Zomato" (same trim the WhatsApp bot uses)."""
    return _CARD_SUFFIX_RE.sub("", (brand_name or "").strip())
