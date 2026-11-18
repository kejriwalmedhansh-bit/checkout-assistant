"""Buying a voucher inside Dealo through Hubble's SDK.

Hubble runs the store and takes the payment; Dealo only decides which brand
and how much, and tells Hubble who the shopper is. Three jobs live here:

- offer_for(): does Hubble sell this shop's voucher, how should the order be
  split into vouchers, and what does the shopper pay. Prices and amount
  rules are read live from Hubble (cached briefly), so the figure Dealo shows
  is the one Hubble's payment screen charges.
- store_url(): the link that opens Hubble's store straight on the payment
  step with the amounts filled in (docs.myhubble.money/sdk/features/deep-links).
- sso_token(): the 60-second signed pass that tells Hubble who is buying
  (JWT SSO, docs.myhubble.money/sdk/authentication/sso-setup).
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt

from ..config import get_settings
from ..repositories._brand_matching import _strip_generic_suffix_words
from ..repositories import domain_brand_repository
from ..repositories.domain_brand_repository import brand_for_domain


def normalize(name: str) -> str:
    """Hubble's own catalogue key: letters and digits only. Kept apart from
    the voucher matcher's normalize (which reads "&" as "and") because the
    /buy/<slug> links already shared ("bath-body-works") must keep
    resolving to the same brand."""
    return re.sub(r"[^a-z0-9]", "", name.lower())

SDK_HOST = {
    "staging": "https://sdk.dev.myhubble.money",
    "production": "https://sdk.myhubble.money",
}
API_HOST = {
    "staging": "https://api.dev.myhubble.money",
    "production": "https://api.myhubble.money",
}
_DATA = Path(__file__).resolve().parents[2] / "data"
_ALIASES = _DATA / "hubble_aliases.json"
# Hubble titles ending like "Hugo Boss-Luxe Gift Card" are the shop's own
# voucher under Gyftr's "Luxe" label; the shop is "Hugo Boss".
_LUXE_SUFFIX = re.compile(r"[\s-]*luxe\s+(gift|brand)\s+card$", re.IGNORECASE)
_TLD = re.compile(r"\.(com|in|co\.in|net|org|co)(/.*)?$")
# Words a partner's listing hangs on the shop's name that say nothing about
# which shop it is: "PVR Cinemas - GYFTR", "Zomato Gift Card", "Swiggy Money
# Voucher", "Bigbasket (Custom)", "Pantaloons (In Store, 4 Hr Wait)",
# "MakeMyTrip Hotel e-Pay" (Gyftr) / "MakeMyTrip Hotel E Pay" (Maximize). Peeled
# off the end, one layer at a time, before the shop key is built. Hubble's
# own titles are never touched, so "Dominos Fixed" and "Zomato Fixed" stay
# the distinct vouchers they are.
_LISTING_DECOR = re.compile(
    r"\s*(?:\((?:in[\s-]?store|offline|custom|fixed)[^)]*\)"
    r"|-\s*(?:gyftr|fixed)"
    r"|e[\s-]?pay|e-?gift\s*(?:card|voucher)|gift\s*(?:card|voucher)|voucher|money)\s*$",
    re.IGNORECASE,
)
# Hubble asks partners not to hold store data for long; ten minutes keeps a
# busy results page from calling them on every view.
_PRODUCT_TTL_SECONDS = 600
_products: dict[str, tuple[float, dict]] = {}
# When each voucher was last asked for by a shopper: those are kept fresh in
# the background (refresh_popular) so a search never waits on Hubble for them.
_looked_up: dict[str, float] = {}

def _catalogue_path() -> Path:
    """Production and staging are different stores with different brand ids
    (scripts/build_hubble_catalogue.py writes one file per environment)."""
    env = get_settings().HUBBLE_ENV
    return _DATA / ("hubble_catalogue.json" if env == "production" else "hubble_catalogue.staging.json")


@lru_cache(maxsize=2)
def _catalogue(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    return _build_index(json.loads(path.read_text()))


# Hubble's list as the server last read it (refresh_catalogue, daily), used
# in place of the file once read, so a voucher Hubble adds is sold the same
# day without anyone updating the file or deploying (audit 18 Nov 2026: the
# file was three weeks old). The file stays the start-up copy.
_live: dict = {"brands": None, "index": None, "at": 0.0}


def catalogue_brands() -> list[dict]:
    if _live["brands"] is not None:
        return _live["brands"]
    return json.loads(_catalogue_path().read_text())


def _index() -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    if _live["index"] is not None:
        return _live["index"]
    return _catalogue(_catalogue_path())


def _build_index(brands: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Hubble vouchers by exact title key, and by the shop name hidden in a
    "-Luxe Gift Card" title (only when no plain title already has that
    key: "Nykaa LUXE" must never answer for "Nykaa")."""
    exact: dict[str, list[dict]] = {}
    luxe: dict[str, list[dict]] = {}
    for b in brands:
        exact.setdefault(normalize(b["name"]), []).append(b)
    for b in brands:
        bare = _LUXE_SUFFIX.sub("", b["name"])
        if bare != b["name"] and normalize(bare) not in exact:
            luxe.setdefault(normalize(bare), []).append(b)
    return exact, luxe


@lru_cache(maxsize=1)
def _aliases() -> dict[str, list[str]]:
    return {k: v for k, v in json.loads(_ALIASES.read_text()).items() if not k.startswith("_")}


def shop_key(merchant: str, strip_decor: bool = True) -> str:
    """The shop behind a results-page name: "Amazon.in", "AJIO.com",
    "Hamleys India", "Westside (in-store)" all become amazon / ajio /
    hamleys / westside. With strip_decor, a partner listing's decoration
    goes too: "PVR Cinemas - GYFTR" -> pvrcinemas, "Zomato Gift Card" ->
    zomato."""
    name = (merchant or "").strip().lower()
    while strip_decor:
        bare = _LISTING_DECOR.sub("", name).strip()
        if bare == name or not bare:
            break
        name = bare
    name = re.sub(r"^(https?://)?(www\.)?", "", name)
    name = _TLD.sub("", name)
    return normalize(_strip_generic_suffix_words(name))


def _brand_by_name(merchant: str, in_store: bool) -> dict | None:
    """The exact-name half of brand_for()."""
    want = "OFFLINE" if in_store else "ONLINE"
    exact, luxe = _index()
    aliases = _aliases()
    # The name as given first ("Hugo Boss-Luxe Gift Card" is a Hubble title
    # of its own); the listing's decoration comes off only when that finds
    # nothing ("Zomato Gift Card" -> Zomato).
    # The whole name first: "Shop", "India" and "Online" come off a results
    # page's name ("Hamleys India" -> hamleys), but in "The Body Shop", "The
    # Raymond Shop" and "Organic India" they are the shop's own name.
    whole = normalize(_TLD.sub("", re.sub(r"^(https?://)?(www\.)?", "", (merchant or "").strip().lower())))
    tried: set[str] = set()
    for key in (whole, shop_key(merchant, strip_decor=False), shop_key(merchant)):
        if not key or key in tried:
            continue
        tried.add(key)
        names = aliases.get(key)
        if names:
            pool = [b for n in names for b in exact.get(normalize(n), [])]
        else:
            pool = exact.get(key) or luxe.get(key) or []
        fits = [b for b in pool if want in b["works"]]
        if len(fits) == 1:
            return fits[0]
    return None


def _hosts(merchant: str, link: str | None) -> list[str]:
    """The websites a result points at: the shop name itself when it is a web
    address ("decathlon.in"), then the buy link's host
    ("https://www.decathlon.in/p/..." -> "decathlon.in"). Only "www." comes
    off: "luxe.ajio.com" must never be read as "ajio.com"."""
    found: list[str] = []
    for raw in (merchant, link):
        host = re.sub(r"^[a-z]+://", "", (raw or "").strip().lower())
        host = re.split(r"[/?#:]", host)[0]
        host = host[4:] if host.startswith("www.") else host
        if "." in host and " " not in host and host not in found:
            found.append(host)
    return found


def brand_for(merchant: str, in_store: bool = False, link: str | None = None) -> dict | None:
    """The one Hubble voucher for this shop that works where the shopper
    pays: online orders get an online voucher, in-store orders an in-store
    one. A near-miss or a guess would sell a voucher for the wrong shop, so
    only four things count: the exact title, a hand-checked alias
    (data/hubble_aliases.json), a "-Luxe Gift Card" title for the same
    shop, or the shop's website in the hand-checked website list
    (data/domain_brand_map.json). Two candidates with no way to tell them
    apart means neither."""
    found = _brand_by_name(merchant, in_store)
    if found:
        return found
    # The shop's own name didn't match: Google Shopping calls decathlon.in
    # "Decathlon Sports India" (fishing rod, 17 Nov 2026). Its website does,
    # through the hand-checked website list (data/domain_brand_map.json),
    # so a long or odd display name never hides Dealo's card.
    for host in _hosts(merchant, link):
        name = brand_for_domain(host)
        found = _brand_by_name(name, in_store) if name else None
        if found and not _has_siblings(found, in_store):
            return found
    return None


def _has_siblings(brand: dict, in_store: bool) -> bool:
    """Does Hubble sell this shop's voucher in more than one kind? The
    website list names one partner card per site, and for some shops that is
    one kind of several (candere.com -> "Candere Gold Coin", though Hubble
    also sells Candere Gold and Diamond Jewellery; timesprime.com -> "Times
    Prime Lite" of Lite/Power/Prive). A website can't say which kind the
    cart needs, so such a shop gets no card from its website, as a shop name
    with two candidates gets none."""
    want = "OFFLINE" if in_store else "ONLINE"
    words = [normalize(w) for w in brand["name"].split() if normalize(w)]
    stem = words[0] if words and len(words[0]) >= 4 else "".join(words[:2])
    exact, _ = _index()
    kinds = {key for key, items in exact.items()
             if key.startswith(stem) and any(want in b["works"] for b in items)}
    return len(kinds) > 1


def buy_slug(brand_name: str) -> str:
    """The address part of a Dealo buy link: "AJIO Luxe" -> "ajio-luxe",
    "DOMINO'S" -> "domino-s". Only letters and digits survive, so any slug
    normalises back to the same catalogue key the title does."""
    return re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-")


def buy_link(brand_name: str, amount: int | None = None, src: str | None = None, in_store: bool = False) -> str:
    """The web page where this voucher is bought inside Dealo. Every other
    surface (WhatsApp, extension, chat apps) hands the shopper here, because
    the login and Hubble's payment window only run on the website."""
    s = get_settings()
    params = {}
    if amount:
        params["amount"] = int(amount)
    if src:
        params["src"] = src
    if in_store:
        # Lifestyle, Max, Home Centre... sell an online and an in-store card
        # under one name: the link must say which (audit 18 Nov 2026).
        params["store"] = 1
    query = f"?{urlencode(params)}" if params else ""
    return f"{s.WEBSITE_URL.rstrip('/')}/buy/{buy_slug(brand_name)}{query}"


def brand_by_slug(slug: str, in_store: bool = False) -> dict | None:
    """The catalogue entry a buy link names. Online first, unless the link
    says in store (?store=1); a shop Hubble sells only one way still
    answers, the page says so."""
    exact, _ = _index()
    pool = exact.get(normalize(slug)) or []
    if not pool:
        return None
    if in_store:
        store = [b for b in pool if "OFFLINE" in b["works"]]
        if len(store) == 1:
            return store[0]
    online = [b for b in pool if "ONLINE" in b["works"]]
    if len(online) == 1:
        return online[0]
    return pool[0] if len(pool) == 1 and not online else None


# A brief Hubble hiccup uses the last good copy (up to 30 minutes old) instead
# of turning a buy into "Something went wrong" (audit 18 Nov 2026). Rates
# rarely move within the hour, and Hubble's own pay screen charges today's.
_STALE_OK_SECONDS = 30 * 60


async def _product(brand_id: str, background: bool = False) -> dict | None:
    """Hubble's page for one voucher (rate, amounts, terms), kept ten
    minutes. `background`: the keep-fresh job re-reading it early, which
    neither counts as a shopper's interest nor waits for the copy to expire."""
    if not background:
        _looked_up[brand_id] = time.time()
    hit = _products.get(brand_id)
    if hit and not background and time.time() - hit[0] < _PRODUCT_TTL_SECONDS:
        return hit[1]
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(
                f"{API_HOST[s.HUBBLE_ENV]}/v1/store/products/voucher-product/{brand_id}",
                headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID},
            )
            resp.raise_for_status()
            product = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"[hubble] product {brand_id} unavailable: {exc}")
        if hit and time.time() - hit[0] < _STALE_OK_SECONDS:
            return hit[1]
        return None
    _products[brand_id] = (time.time(), product)
    return product


def _discount_pct(product: dict) -> float:
    """The shopper's discount. Cashback-style rewards don't count: Dealo only
    shows money off what is paid today."""
    for reward in product.get("rewardDetails") or []:
        if "CASHBACK" in (reward.get("rewardType") or "").upper():
            return 0.0
        return float(reward.get("discountPercentage") or 0)
    return 0.0


_NOTES = _DATA / "hubble_card_notes.json"

# What the icon row says, read from Hubble's own terms. Each fact is shown
# only when one sentence says it plainly; a voucher whose terms say both
# ("once offline; multiple times online") gets no fact for that question.
_ONE_USE = re.compile(r"one[- ]time|only (?:be )?used once|can only be used once|redeemed only once|"
                      r"cannot be redeemed in part|partial redemption is not allowed|use all value in one", re.I)
_REUSE = re.compile(r"multiple times|multi-use|partially redeemed|multiple transactions|multiple purchases", re.I)
_NO_OFFERS = re.compile(r"cannot be clubbed with|no other offers|cannot be combined with|"
                        r"cannot be redeemed on existing discount|not be clubbed", re.I)
_OFFERS = re.compile(r"offers can be clubbed|can be clubbed with (?:the )?(?:existing|selected) offer|"
                     r"clubbed with existing offers|can be used during sale", re.I)
_NO_REFUND = re.compile(r"cannot be cancelled or refunded|no refunds|non-refundable", re.I)
_VALIDITY = re.compile(r"(\d+)\s*-?\s*(year|month)s?", re.I)


def _first(terms: list[str], pattern: re.Pattern) -> str | None:
    return next((t for t in terms if pattern.search(t)), None)


def _yes_no(terms: list[str], yes: re.Pattern, no: re.Pattern, no_wins: bool = False) -> tuple[bool | None, str | None]:
    """With no_wins, a sentence that says no is a no even when it also reads
    like a yes ("No other offers can be clubbed" holds "offers can be
    clubbed"). Without it, such a sentence is mixed ("once offline; multiple
    times online") and nothing is said."""
    both = [t for t in terms if yes.search(t) and no.search(t)]
    if both and not no_wins:
        return None, None
    said_no = _first(terms, no)
    said_yes = next((t for t in terms if yes.search(t) and not no.search(t)), None)
    if said_yes and said_no:
        return None, None
    return (True, said_yes) if said_yes else (False, said_no) if said_no else (None, None)


def _facts(terms: list[str], modes: set[str], in_store: bool, per_bill: dict | None = None) -> list[dict]:
    facts = []
    if in_store:
        facts.append({"icon": "store", "title": "In store", "sub": "show the code", "tone": "info"})
    elif "OFFLINE" in modes:
        facts.append({"icon": "globe", "title": "Online", "sub": "& in store", "tone": "info"})
    else:
        facts.append({"icon": "globe", "title": "Online", "sub": "shopping", "tone": "info"})
    if per_bill:
        facts.append(per_bill)
    reuse, quote = _yes_no(terms, _REUSE, _ONE_USE)
    if reuse is not None:
        facts.append({"icon": "repeat", "title": "Reuse" if reuse else "One use",
                      "sub": "till \u20b90" if reuse else "spend it all", "tone": "yes" if reuse else "no", "quote": quote})
    offers, quote = _yes_no(terms, _OFFERS, _NO_OFFERS, no_wins=True)
    if offers is not None:
        facts.append({"icon": "tag", "title": "Offers" if offers else "No offers",
                      "sub": "still apply" if offers else "on top", "tone": "yes" if offers else "no", "quote": quote})
    valid = next(((t, m) for t in terms if "valid" in t.lower() or "within a period" in t.lower()
                  for m in [_VALIDITY.search(t)] if m), None)
    if valid:
        n, unit = int(valid[1].group(1)), valid[1].group(2).lower()
        facts.append({"icon": "cal", "title": f"{n} {unit}{'s' if n != 1 else ''}", "sub": "validity",
                      "tone": "info", "quote": valid[0]})
    refund = _first(terms, _NO_REFUND)
    if refund and len(facts) < 5:
        facts.append({"icon": "undo", "title": "No refund", "sub": "once bought", "tone": "no", "quote": refund})
    return facts[:5]

# How many of this shop's cards one bill takes. Read from Hubble's own terms
# first, then from what Gyftr, Maximize and BuyHatke say about the same
# shop's card (data/voucher_rules.json); when they disagree the stricter
# answer wins (owner's rule). A sentence that splits online and in-store
# ("Online: one per bill; Offline: multiple") says nothing.
_CARD = r"(?:(?:e[\s-]*)?gift\s+|virtual\s+|e[\s-]*)?(?:cards?|vouchers?|gvs?|gcs?|gv\s*/\s*gcs?|egvs?|codes?)"
_PER = r"(?:bill|order|transaction|invoice|purchase|booking)"
_MAX_N = re.compile(rf"(?:up\s*to|upto|maximum(?:\s+of)?|max\.?|only)\s+(\d+)\s+{_CARD}\b.*?\b(?:single|one|per|each|same)\s+{_PER}", re.I)
_N_IN_ONE = re.compile(rf"\b(\d+)\s+{_CARD}\s+(?:can|may)\s+be\s+(?:used|redeemed|clubbed|combined)\b.*?\b(?:single|one|per)\s+{_PER}", re.I)
_ONLY_ONE = re.compile(
    rf"(?:only\s+(?:one|1|a\s+single)|maximum\s+(?:one|1)|\bsingle|\bone)\s+{_CARD}\s+(?:can|may|shall)\s+be\s+(?:used|redeemed|applied)"
    rf"\b.*?\b(?:per|in\s+one|against\s+one|in\s+a\s+single|single|one)\s+{_PER}"
    rf"|(?:multiple|more\s+than\s+one)\s+{_CARD}\s+(?:can['’]?t|cannot|can\s+not|shall\s+not|will\s+not|may\s+not)\s+be\s+(?:used|clubbed|combined|redeemed)"
    rf"|{_CARD}\s+can['’]?t\s+be\s+clubbed", re.I)
_MANY = re.compile(
    rf"(?:multiple|more\s+than\s+one|several)\s+{_CARD}\s+(?:can|may|could)\s+be\s+(?:used|clubbed|combined|redeemed|added)"
    rf"|{_CARD}\s+can\s+be\s+clubbed\s+(?:together|in\s+a\s+single)", re.I)
_MIXED = re.compile(r"\bonline\b.*\boff-?line\b|\boff-?line\b.*\bonline\b|in[\s-]?store.*\bonline\b|\bonline\b.*in[\s-]?store", re.I)
_ONLINE_WORDS = re.compile(r"\bonline\b|\.com\b|\bwebsite\b|\bapp\b", re.I)
_STORE_WORDS = re.compile(r"off-?line|in[\s-]?store|\bstores?\b|\boutlets?\b|showrooms?|\bat the counter", re.I)
_MANY_N = 99
_VOUCHER_RULES = _DATA / "voucher_rules.json"
_SELLER = {"gyftr": "Gyftr", "maximize": "Maximize", "buyhatke": "BuyHatke"}


def _cards_per_bill(sentence: str) -> int | None:
    """1, a number, _MANY_N for "several", or None when the sentence doesn't say."""
    if _MIXED.search(sentence):
        return None
    m = _MAX_N.search(sentence) or _N_IN_ONE.search(sentence)
    if m:
        return max(1, int(m.group(1)))
    if _ONLY_ONE.search(sentence):
        return 1
    if _MANY.search(sentence):
        return _MANY_N
    return None


@lru_cache(maxsize=1)
def _partner_rules() -> dict[str, list[dict]]:
    by_shop: dict[str, list[dict]] = {}
    for key, entry in json.loads(_VOUCHER_RULES.read_text()).items():
        if key.startswith("_"):
            continue
        by_shop.setdefault(shop_key(entry.get("brand_name") or ""), []).append(entry)
    return by_shop


def _per_bill_fact(terms: list[str], brand_name: str, in_store: bool) -> dict | None:
    found: list[tuple[int, str, str]] = []  # (cards, quote, seller)
    for t in terms:
        n = _cards_per_bill(t)
        if n:
            found.append((n, t, "Hubble"))
    where = "works_in_store" if in_store else "works_online"
    other_mode = _ONLINE_WORDS if in_store else _STORE_WORDS
    keys = {shop_key(brand_name)} | {k for k, titles in _aliases().items() if brand_name in titles}
    entries = [e for k in sorted(keys) for e in _partner_rules().get(k, [])]
    for entry in entries:
        rules = entry.get("rules") or {}
        if (rules.get(where) or {}).get("value") == "no":
            continue
        combine = rules.get("can_combine") or {}
        quote = (combine.get("evidence") or "").strip()
        if not quote or _MIXED.search(quote) or other_mode.search(quote):
            continue  # says nothing, or speaks only of the other way of paying
        most = (rules.get("max_cards_per_order") or {}).get("value")
        if combine.get("value") == "no":
            n = 1
        elif combine.get("value") == "yes":
            n = int(most) if isinstance(most, (int, float)) and most >= 1 else _MANY_N
        else:
            continue
        found.append((n, quote, _SELLER.get(entry.get("source"), entry.get("source") or "")))
    if not found:
        return None
    n, quote, seller = min(found, key=lambda f: f[0])
    sub = "per bill" if in_store else "per order"
    if n == 1:
        return {"icon": "one", "title": "1 card", "sub": sub, "tone": "no", "quote": quote, "source": seller}
    title = "Many" if n >= _MANY_N else f"Up to {n}"
    return {"icon": "stack", "title": title, "sub": sub, "tone": "yes", "quote": quote, "source": seller}


@lru_cache(maxsize=1)
def _notes() -> dict[str, list[dict]]:
    return {k: v for k, v in json.loads(_NOTES.read_text()).items() if not k.startswith("_")}


def card_details(product: dict, brand_name: str, in_store: bool) -> dict:
    """What the Dealo voucher card shows besides the price, all from Hubble's
    own terms: an icon row of plain facts, the hand-picked things it can't
    pay for (data/hubble_card_notes.json; an item whose sentence Hubble no
    longer has is dropped), the full terms, and the how-to steps for where
    the shopper will use it (shown after buying when there is no direct
    add-voucher link)."""
    meta = product.get("voucherProductMetadata") or {}
    terms = [t.strip(" -") for t in meta.get("conditions") or [] if t and t.strip(" -")]
    ways = meta.get("howToUseSteps") or []
    modes = {(w.get("retailMode") or "").upper() for w in ways}
    want = ("OFFLINE",) if in_store else ("ONLINE", "APP")
    def hints(modes_wanted: tuple[str, ...]) -> list[str]:
        way = next((w for w in ways if (w.get("retailMode") or "").upper() in modes_wanted), None)
        return [h for h in ((way or {}).get("howToUseHints") or {}).get("hints") or [] if h]

    steps = hints(want)
    # Both ways of using the card, for the In store / Online switch.
    usage = {k: v for k, v in (("store", hints(("OFFLINE",))), ("online", hints(("ONLINE", "APP")))) if v}
    cant = [{k: i[k] for k in ("icon", "label")} for i in _notes().get(normalize(brand_name), [])
            if any(i["quote"] in t for t in terms)]
    per_bill = _per_bill_fact(terms, brand_name, in_store)
    return {"facts": _facts(terms, modes, in_store, per_bill), "cant": cant[:3], "terms": terms,
            "steps": steps, "ways": usage}


def _one_order(product: dict, amount: int, order_max: int) -> list[tuple[int, int]]:
    """The vouchers one Hubble order can hold towards `amount`, never more
    than it: [(value, count), ...], empty if nothing fits.

    Rules as Hubble's staging store applies them (tested 23 Oct): a brand
    with a list of card values sells only those values, several cards per
    order; any other brand sells ONE typed amount per order (AJIO ₹12,000
    shows "0% off" and a dead button). Hubble quietly swaps an amount it
    doesn't allow for its smallest card, so nothing outside these rules may
    ever reach it."""
    rules = product.get("amountConditions") or {}
    limits = product.get("restrictions") or {}
    target = min(amount, order_max)
    cards = sorted({int(d["amount"] if isinstance(d, dict) else d) for d in rules.get("denominations") or []}, reverse=True)

    if not cards:
        step = max(1, int(rules.get("stepAmount") or 1))
        one = target - target % step
        return [(one, 1)] if one >= int(rules.get("minAmount") or 1) else []

    max_cards = 1 if product.get("isOneVoucherOneDenominationOnly") else int(limits.get("maxNumberOfVouchersPerOrder") or 1)
    per_value = int(rules.get("maxNoOfVouchersPerDenomination") or max_cards)
    max_values = rules.get("maxNoOfDenominationsPerOrder")
    if (product.get("voucherProductProviderMetadata") or {}).get("onlySingleDenominationAllowed"):
        max_values = 1

    if max_values == 1:
        # Every card the same value: pick the value that covers the most.
        best = max(((c, min(target // c, max_cards, per_value)) for c in cards), key=lambda p: p[0] * p[1])
        return [best] if best[1] else []
    parts, left, count = [], target, 0
    for c in cards:
        n = min(left // c, max_cards - count, per_value)
        if n > 0:
            parts.append((c, n))
            left -= c * n
            count += n
        if max_values and len(parts) == max_values:
            break
    return parts


def _orders(product: dict, price: float, pct: float) -> list[list[tuple[int, int]]] | None:
    """Up to HUBBLE_MAX_ORDERS Hubble orders covering as much of `price` as
    the brand allows; the rest is paid at the shop as usual (Zepto ₹3,450 →
    ₹3,000 in cards + ₹450; AJIO ₹25,000 → one ₹10,000 voucher + ₹15,000).
    The results page shows Hubble only when that total beats today's best."""
    s = get_settings()
    rules = product.get("amountConditions") or {}
    limits = product.get("restrictions") or {}
    order_max = int(rules.get("maxAmount") or price)
    # Hubble refuses a payment above the cap, so cap the voucher value too.
    order_max = min(order_max, math.floor(s.HUBBLE_PAY_CAP / (1 - pct / 100)))
    # A monthly limit bounds what Dealo can ask for in one go; what the
    # shopper already bought this month isn't known here.
    month_worth = limits.get("maxWorthOfVouchersInAMonth") or math.inf
    month_cards = limits.get("maxNumberOfVouchersInAMonth") or math.inf

    orders, left = [], int(price)
    while True:
        parts = _one_order(product, left, int(min(order_max, month_worth)))
        cards = sum(n for _, n in parts)
        if not parts or len(orders) == s.HUBBLE_MAX_ORDERS or cards > month_cards:
            break
        orders.append(parts)
        worth = sum(a * n for a, n in parts)
        left -= worth
        month_worth -= worth
        month_cards -= cards
    return orders or None


async def offer_for(merchant: str, price: float, in_store: bool = False, link: str | None = None) -> dict | None:
    s = get_settings()
    if not s.HUBBLE_ENABLED or price <= 0:
        return None
    brand = brand_for(merchant, in_store, link)
    if not brand:
        return None
    product = await _product(brand["id"])
    if not product or product.get("status") != "ACTIVE":
        return None
    pct = _discount_pct(product)
    orders = _orders(product, price, pct) if pct > 0 else None
    if not orders:
        return None
    worths = [sum(a * c for a, c in parts) for parts in orders]
    voucher_total = sum(worths)
    you_save = round(voucher_total * pct / 100, 2)
    return {
        "brand_id": brand["id"],
        "brand_name": brand["name"],
        # The first (usually only) order; store_url() opens this one.
        "denominations": [{"amount": a, "count": c} for a, c in orders[0]],
        "orders": [
            {"denominations": [{"amount": a, "count": c} for a, c in parts], "worth": w,
             "you_pay": round(w * (1 - pct / 100), 2)}
            for parts, w in zip(orders, worths)
        ],
        "voucher_total": voucher_total,
        "discount_pct": pct,
        "you_pay": round(voucher_total - you_save, 2),
        "you_save": you_save,
        "rest_at_shop": max(0, int(price) - voucher_total),
        "in_store": in_store,
        "add_voucher_url": brand.get("add_voucher_url"),
        "shop_url": shop_url(brand["id"]),
        "card": card_details(product, brand["name"], in_store),
    }


async def _offers(items: list[tuple[str, float, bool, str | None]], timeout: float) -> list[tuple[bool, dict | None]]:
    async def one(item):
        merchant, price, in_store, link = item
        if not price or price <= 0 or not brand_for(merchant, in_store, link):
            return True, None  # Hubble doesn't sell this shop: a sure "no"
        try:
            offer = await asyncio.wait_for(offer_for(merchant, price, in_store, link), timeout)
        except Exception:  # noqa: BLE001 — slow or failing Hubble: "don't know"
            return False, None
        if offer is None and brand_for(merchant, in_store, link)["id"] not in _products:
            return False, None  # the product page didn't load: "don't know", not "no"
        return True, offer
    return list(await asyncio.gather(*(one(i) for i in items)))


def offers_for_shops(items: list[tuple[str, float, bool, str | None]], timeout: float = 5.0) -> list[tuple[bool, dict | None]]:
    """Dealo's own voucher for each (shop, price, in_store, buy link), asked
    once on the server so every screen (website, WhatsApp, price lists) shows
    the same answer (18 Nov 2026: the website used to ask only when a partner
    also sold the shop, so Hubble-only shops showed no voucher at all).

    Each answer is (checked, offer): checked is False when Hubble didn't
    answer in time, so a caller can ask again later instead of reading that
    as "Hubble doesn't sell it". Called from worker threads (search runs off
    the event loop); inside a running loop it answers "don't know" for all."""
    if not get_settings().HUBBLE_ENABLED:
        return [(True, None) for _ in items]
    if not items:
        return []
    try:
        asyncio.get_running_loop()
        return [(False, None) for _ in items]
    except RuntimeError:
        pass
    try:
        return asyncio.run(_offers(items, timeout))
    except Exception:  # noqa: BLE001
        return [(False, None) for _ in items]


@lru_cache(maxsize=1)
def _shop_sites() -> dict[str, str]:
    """Hubble card id -> the shop's own website, from the hand-checked website
    list, so the "voucher ready" screen's "Open <shop>" button always has
    somewhere to go (it was empty for most shop-card buys; audit 18 Nov 2026)."""
    domain_brand_repository._load()
    sites: dict[str, str] = {}
    for domain in sorted(domain_brand_repository._domain_to_brand or {}, key=len):
        for in_store in (False, True):
            brand = brand_for(domain, in_store)
            if brand and brand["id"] not in sites:
                sites[brand["id"]] = f"https://{domain}"
    return sites


def shop_url(brand_id: str) -> str | None:
    try:
        return _shop_sites().get(brand_id)
    except Exception:  # noqa: BLE001 — a missing list must never break a buy
        return None


# ── Keeping Hubble current (audit 18 Nov 2026) ─────────────────────────────

_POPULAR_SECONDS = 24 * 60 * 60   # a voucher asked for in the last day stays fresh
_REFRESH_BEFORE = 3 * 60          # re-read it this long before its copy runs out


async def fetch_catalogue(previous: list[dict] | None = None) -> list[dict]:
    """Every voucher Hubble sells us right now, with where each works
    (online / in store) and its add-to-wallet link. A voucher that left
    Hubble's listing but whose page still says it's on sale is kept (Zepto
    and Zomato Fixed, 18 Nov 2026). Raises on a Hubble error, so a bad read
    never replaces a good list."""
    s = get_settings()
    base = API_HOST[s.HUBBLE_ENV]
    async with httpx.AsyncClient(headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID}, timeout=60) as client:
        resp = await client.get(f"{base}/v3/store/products/search", params={"pageNo": 0, "limit": 2000})
        resp.raise_for_status()
        listed: dict[str, dict] = {}
        for section in resp.json().get("data", []):
            for p in section.get("products", []):
                vp = p.get("voucherProduct") or {}
                if p.get("type") == "VOUCHER" and vp.get("status") == "ACTIVE":
                    listed[p["id"]] = {"id": p["id"], "name": vp.get("title", "").strip(),
                                       "brand_key": (p.get("brandKey") or "").lower()}
        known = {b["id"]: b for b in previous or []}
        gate = asyncio.Semaphore(8)

        async def details(brand: dict) -> dict | None:
            # One voucher's page failing must not sink the whole read: a new
            # one is skipped until it answers, a known one is kept until a
            # clear answer says it's gone (Zepto's page gave 500s, 18 Nov).
            try:
                async with gate:
                    r = await client.get(f"{base}/v1/store/products/voucher-product/{brand['id']}")
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                product = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                print(f"[hubble] list read: {brand['name']} didn't answer ({exc})")
                return known.get(brand["id"])
            if product.get("status") not in (None, "ACTIVE"):
                return None
            meta = product.get("voucherProductMetadata") or {}
            modes = sorted({(st.get("retailMode") or "").upper() for st in meta.get("howToUseSteps") or []} - {""})
            if not modes:
                modes = ["OFFLINE"] if "offline" in brand["brand_key"] else ["ONLINE"]
            return {**brand, "works": modes, "add_voucher_url": meta.get("addVoucherBrandPageUrl")}

        # Known vouchers keep their details; only new ones (and ones that
        # left the listing, to see whether they still sell) are read.
        to_read = [b for i, b in listed.items() if i not in known]
        gone = [b for i, b in known.items() if i not in listed]
        fresh = await asyncio.gather(*(details(b) for b in to_read + gone))
    out = [known[i] if i in known else None for i in listed]
    out = [b for b in out if b] + [b for b in fresh if b]
    return sorted({b["id"]: b for b in out}.values(), key=lambda b: (b["name"].lower(), b["brand_key"]))


async def refresh_catalogue() -> dict:
    """Read Hubble's list and use it from now on. A read that comes back much
    smaller than the list in use is not trusted (a Hubble glitch must never
    take Dealo's cards away). Returns what changed, for the logs."""
    old = catalogue_brands()
    new = await fetch_catalogue(old)
    if len(new) < 0.8 * len(old):
        print(f"[hubble] list read gave {len(new)} vouchers against {len(old)}; keeping the old list")
        return {"kept_old": True, "read": len(new), "in_use": len(old)}
    old_ids, new_ids = {b["id"] for b in old}, {b["id"] for b in new}
    _live.update(brands=new, index=_build_index(new), at=time.time())
    _shop_sites.cache_clear()
    added = sorted(b["name"] for b in new if b["id"] not in old_ids)
    removed = sorted(b["name"] for b in old if b["id"] not in new_ids)
    print(f"[hubble] list refreshed: {len(new)} vouchers, added {added}, removed {removed}")
    return {"kept_old": False, "count": len(new), "added": added, "removed": removed}


async def refresh_popular() -> int:
    """Re-read, just before its copy expires, every voucher a shopper asked
    for in the last day, so a search for a popular shop never waits on
    Hubble. Copies still never outlive the ten minutes Hubble allows."""
    now = time.time()
    for stale in [i for i, t in _looked_up.items() if now - t > _POPULAR_SECONDS]:
        _looked_up.pop(stale, None)
    due = [i for i in _looked_up
           if not _products.get(i) or now - _products[i][0] > _PRODUCT_TTL_SECONDS - _REFRESH_BEFORE]
    gate = asyncio.Semaphore(4)

    async def one(brand_id: str) -> None:
        async with gate:
            await _product(brand_id, background=True)
    await asyncio.gather(*(one(i) for i in due))
    return len(due)


async def keep_current(stop: asyncio.Event) -> None:
    """Runs beside the server: Hubble's list once a day (first a minute after
    start), popular vouchers every two minutes. Errors are logged, never
    raised: a Hubble outage must not take the server down."""
    if not get_settings().HUBBLE_ENABLED:
        return
    next_list = time.time() + 60
    while not stop.is_set():
        try:
            if time.time() >= next_list:
                await refresh_catalogue()
                next_list = time.time() + 24 * 60 * 60
            await refresh_popular()
        except Exception as exc:  # noqa: BLE001
            print(f"[hubble] keeping current failed: {exc}")
            next_list = min(next_list, time.time() + 30 * 60)
        try:
            # Wake for the next popular refresh, or the first list read.
            await asyncio.wait_for(stop.wait(), timeout=max(1.0, min(120.0, next_list - time.time())))
        except asyncio.TimeoutError:
            pass


def worth_showing(hubble_pct: float, best_pct: float | None = None) -> bool:  # noqa: ARG001 — best_pct kept for callers
    """Dealo sells the voucher itself wherever Hubble has it at a real rate
    (owner's call, 3 Nov 2026, replacing the earlier within-2-points rule).
    Partner sellers are offered only for shops Hubble does not sell. The
    public best rate is no longer compared; the parameter stays so every
    caller reads the same."""
    return hubble_pct > 0


async def brand_info(merchant: str | None = None, slug: str | None = None, in_store: bool = False) -> dict | None:
    """What Hubble sells for this shop when there is no cart yet (a shop-name
    search, or a buy link naming the voucher by slug): rate, where it works,
    and the amounts the shopper may pick. Online first; a shop Hubble only
    sells in-store still gets its card."""
    s = get_settings()
    if not s.HUBBLE_ENABLED:
        return None
    # A buy link or search for paying in a shop gets the in-store card when
    # Hubble sells one (?store=1); otherwise online first, as before.
    want_store = in_store
    if slug:
        brand = brand_by_slug(slug, want_store)
        online = brand if brand and "ONLINE" in brand["works"] and not want_store else None
        in_store = None if online else brand
    else:
        store_card = brand_for(merchant or "", True)
        online = None if (want_store and store_card) else brand_for(merchant or "", False)
        in_store = store_card
        brand = online or in_store
    if not brand:
        return None
    product = await _product(brand["id"])
    if not product or product.get("status") != "ACTIVE":
        return None
    pct = _discount_pct(product)
    if pct <= 0:
        return None
    rules = product.get("amountConditions") or {}
    cards = sorted({int(d["amount"] if isinstance(d, dict) else d) for d in rules.get("denominations") or []})
    max_amount = int(rules.get("maxAmount") or 0) or None
    if max_amount:
        max_amount = min(max_amount, math.floor(s.HUBBLE_PAY_CAP / (1 - pct / 100)))
    return {
        "brand_id": brand["id"],
        "brand_name": brand["name"],
        "discount_pct": pct,
        "works": brand["works"],
        "in_store": brand is in_store and not online,
        "min_amount": int(rules.get("minAmount") or (cards[0] if cards else 1)),
        "max_amount": max_amount,
        "cards": [c for c in cards if not max_amount or c <= max_amount],
        "typed": not cards,
        "card": card_details(product, brand["name"], brand is in_store and not online),
    }


def _private_key() -> str:
    s = get_settings()
    if s.HUBBLE_PRIVATE_KEY:
        return s.HUBBLE_PRIVATE_KEY.replace("\\n", "\n")
    return Path(s.HUBBLE_PRIVATE_KEY_FILE).expanduser().read_text()


def sso_token(user_id: str, phone: str, name: str | None, email: str | None) -> str:
    """Hubble wants the phone as 10 digits, no country code, and a fresh
    token every time (never cached): it expires 60 seconds after issue."""
    s = get_settings()
    now = int(time.time())
    claims = {
        "sub": user_id,
        "iss": s.HUBBLE_CLIENT_ID,
        "iat": now,
        "exp": now + 60,
        "phoneNumber": re.sub(r"\D", "", phone)[-10:],
    }
    if name:
        claims["name"] = name
    if email:
        claims["email"] = email
    return jwt.encode(claims, _private_key(), algorithm="RS256")


def store_url(offer: dict, token: str, order: int = 0) -> str:
    """Opens Hubble on the payment step for one of the offer's orders."""
    s = get_settings()
    picked = offer["orders"][order]
    params = {
        "clientId": s.HUBBLE_CLIENT_ID,
        "appSecret": s.HUBBLE_APP_SECRET,
        "token": token,
        "wrap-plt": "web",
        "amount": picked["worth"],
        "skipToPayment": "true",
        "showBackButton": "true",
        "exitOnBack": "true",
    }
    if len(picked["denominations"]) > 1 or picked["denominations"][0]["count"] > 1:
        params["denominations"] = ",".join(
            f"{d['amount']}x{d['count']}" for d in picked["denominations"]
        )
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}/buy/{offer['brand_id']}?{urlencode(params)}"


def home_url(token: str) -> str:
    """Hubble's store home screen (staging test page only)."""
    s = get_settings()
    params = {"clientId": s.HUBBLE_CLIENT_ID, "appSecret": s.HUBBLE_APP_SECRET, "token": token, "wrap-plt": "web"}
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}/?{urlencode(params)}"


_REF = re.compile(r"^[0-9A-Z]{26}$")


def card_url(token: str, ref: str | None = None) -> str:
    """Hubble's own page for one gift card the shopper bought (card number,
    PIN, redeem button), or their whole "My gift cards" list. Whose cards
    is set by the login token, so a shopper only ever sees their own; Dealo
    never stores a code. `ref` is the order's transactionReferenceId."""
    s = get_settings()
    params = {
        "clientId": s.HUBBLE_CLIENT_ID,
        "appSecret": s.HUBBLE_APP_SECRET,
        "token": token,
        "wrap-plt": "web",
        "showBackButton": "true",
        "exitOnBack": "true",
    }
    path = f"/transaction/{ref}" if ref and _REF.match(ref) else "/transactions"
    host = SDK_HOST.get(s.HUBBLE_ENV, SDK_HOST["staging"])
    return f"{host}{path}?{urlencode(params)}"
