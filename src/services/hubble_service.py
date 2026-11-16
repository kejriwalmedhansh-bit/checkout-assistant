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

def _catalogue_path() -> Path:
    """Production and staging are different stores with different brand ids
    (scripts/build_hubble_catalogue.py writes one file per environment)."""
    env = get_settings().HUBBLE_ENV
    return _DATA / ("hubble_catalogue.json" if env == "production" else "hubble_catalogue.staging.json")


@lru_cache(maxsize=2)
def _catalogue(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Hubble vouchers by exact title key, and by the shop name hidden in a
    "-Luxe Gift Card" title (only when no plain title already has that
    key: "Nykaa LUXE" must never answer for "Nykaa")."""
    exact: dict[str, list[dict]] = {}
    luxe: dict[str, list[dict]] = {}
    brands = json.loads(path.read_text())
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


def brand_for(merchant: str, in_store: bool = False) -> dict | None:
    """The one Hubble voucher for this shop that works where the shopper
    pays: online orders get an online voucher, in-store orders an in-store
    one. A near-miss or a guess would sell a voucher for the wrong shop, so
    only three things count: the exact title, a hand-checked alias
    (data/hubble_aliases.json), or a "-Luxe Gift Card" title for the same
    shop. Two candidates with no way to tell them apart means neither."""
    want = "OFFLINE" if in_store else "ONLINE"
    exact, luxe = _catalogue(_catalogue_path())
    aliases = _aliases()
    # The name as given first ("Hugo Boss-Luxe Gift Card" is a Hubble title
    # of its own); the listing's decoration comes off only when that finds
    # nothing ("Zomato Gift Card" -> Zomato).
    tried: set[str] = set()
    for key in (shop_key(merchant, strip_decor=False), shop_key(merchant)):
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


def buy_slug(brand_name: str) -> str:
    """The address part of a Dealo buy link: "AJIO Luxe" -> "ajio-luxe",
    "DOMINO'S" -> "domino-s". Only letters and digits survive, so any slug
    normalises back to the same catalogue key the title does."""
    return re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-")


def buy_link(brand_name: str, amount: int | None = None, src: str | None = None) -> str:
    """The web page where this voucher is bought inside Dealo. Every other
    surface (WhatsApp, extension, chat apps) hands the shopper here, because
    the login and Hubble's payment window only run on the website."""
    s = get_settings()
    params = {}
    if amount:
        params["amount"] = int(amount)
    if src:
        params["src"] = src
    query = f"?{urlencode(params)}" if params else ""
    return f"{s.WEBSITE_URL.rstrip('/')}/buy/{buy_slug(brand_name)}{query}"


def brand_by_slug(slug: str) -> dict | None:
    """The catalogue entry a buy link names. Online first; a shop Hubble
    only sells in-store still answers, the page says so."""
    exact, _ = _catalogue(_catalogue_path())
    pool = exact.get(normalize(slug)) or []
    if not pool:
        return None
    online = [b for b in pool if "ONLINE" in b["works"]]
    if len(online) == 1:
        return online[0]
    return pool[0] if len(pool) == 1 and not online else None


async def _product(brand_id: str) -> dict | None:
    hit = _products.get(brand_id)
    if hit and time.time() - hit[0] < _PRODUCT_TTL_SECONDS:
        return hit[1]
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{API_HOST[s.HUBBLE_ENV]}/v1/store/products/voucher-product/{brand_id}",
                headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[hubble] product {brand_id} unavailable: {exc}")
        return None
    product = resp.json()
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


async def offer_for(merchant: str, price: float, in_store: bool = False) -> dict | None:
    s = get_settings()
    if not s.HUBBLE_ENABLED or price <= 0:
        return None
    brand = brand_for(merchant, in_store)
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
        "card": card_details(product, brand["name"], in_store),
    }


def worth_showing(hubble_pct: float, best_pct: float | None = None) -> bool:  # noqa: ARG001 — best_pct kept for callers
    """Dealo sells the voucher itself wherever Hubble has it at a real rate
    (owner's call, 3 Nov 2026, replacing the earlier within-2-points rule).
    Partner sellers are offered only for shops Hubble does not sell. The
    public best rate is no longer compared; the parameter stays so every
    caller reads the same."""
    return hubble_pct > 0


async def brand_info(merchant: str | None = None, slug: str | None = None) -> dict | None:
    """What Hubble sells for this shop when there is no cart yet (a shop-name
    search, or a buy link naming the voucher by slug): rate, where it works,
    and the amounts the shopper may pick. Online first; a shop Hubble only
    sells in-store still gets its card."""
    s = get_settings()
    if not s.HUBBLE_ENABLED:
        return None
    if slug:
        brand = brand_by_slug(slug)
        online = brand if brand and "ONLINE" in brand["works"] else None
        in_store = None if online else brand
    else:
        online = brand_for(merchant or "", False)
        in_store = brand_for(merchant or "", True)
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
