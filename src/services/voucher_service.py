"""Gyftr voucher business logic (ported from db/voucher_lookup.py).

Computes the effective price after applying a voucher's payment-method discount
and builds per-merchant voucher deals for a set of route candidates, honouring
category redemption restrictions.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from ..category_classifier import classify_product, restriction_mentions_category
from ..repositories import buyhatke_repository, maximize_repository, voucher_repository

# Maps the caller-facing payment_method argument to the keys used in the
# discounts dict of gyftr_master.json / maximize_master.json. "card" means
# Credit Card specifically, not "whichever of Credit/Debit is higher" — every
# cashback card this app knows about is a credit card, and Maximize's Debit
# Card rate is sometimes higher than its Credit Card rate (the opposite of
# Gyftr), so mixing them in would misrepresent what that specific card path
# actually pays.
PAYMENT_METHOD_TO_DISCOUNT_KEYS = {
    "card": ["Credit Card"],
    "netbanking": ["Net Banking"],
    "upi": ["UPI"],
    "paytm_upi": ["UPI"],
    "amazon_pay": ["UPI"],
}

# Gyftr is the only platform confirmed (live-tested 2026-09-03) to let a
# shopper put several different voucher amounts in one cart and pay once.
# Maximize and BuyHatke only ever let you pick ONE amount per checkout —
# buying a second, different denomination means a second separate purchase,
# regardless of how many the *store* is willing to combine at redemption
# (that's `_store_allows_stacking`, a different fact — see its docstring).
_SINGLE_ITEM_CHECKOUT_PLATFORMS = {"maximize", "buyhatke"}

# Recommended Route tie-break: a cheaper multi-transaction deal only beats a
# single-transaction deal when it saves more than this fraction extra on top
# of the single-transaction price. Below that, the one-click option wins even
# though it costs a little more — closing purchase friction is a stated
# product USP, not just a nice-to-have. Set 2026-09-03 per product decision:
# up to ~5% more is worth paying to avoid extra transactions.
MULTI_TXN_SAVINGS_THRESHOLD = 0.05

# Load standardized voucher rules from T&C extraction
def _load_voucher_rules() -> dict:
    """Load standardized voucher rules extracted from T&Cs. Returns {source:slug: {rules}}.
    If file doesn't exist or is empty, returns empty dict (rules optional for now)."""
    rules_path = Path(__file__).resolve().parent.parent.parent / "data" / "voucher_rules.json"
    if not rules_path.exists():
        return {}
    try:
        return json.loads(rules_path.read_text()) or {}
    except (json.JSONDecodeError, IOError):
        return {}

VOUCHER_RULES = _load_voucher_rules()

def _get_voucher_rules(source: str, slug: str) -> dict | None:
    """Get standardized T&C rules for a voucher (source:slug format).
    Returns rules dict or None if not found."""
    return VOUCHER_RULES.get(f"{source}:{slug}")

def validate_voucher_against_rules(source: str, slug: str, use_case: dict) -> tuple[bool, str | None]:
    """Validate whether a voucher can be used based on standardized T&C rules.

    Args:
        source: 'gyftr', 'maximize', or 'buyhatke'
        slug: brand slug
        use_case: dict with optional keys:
            - combine_with_other: bool (using multiple vouchers together)
            - on_sale_item: bool
            - with_store_offers: bool

    Returns: (is_valid, reason_if_invalid) where reason is a human-readable string
    explaining why voucher cannot be used (or None if valid/not stated).
    """
    rules = _get_voucher_rules(source, slug)
    if not rules or "rules" not in rules:
        return True, None  # No rules = assume valid

    rules = rules["rules"]

    # Check: can_combine
    if use_case.get("combine_with_other") and rules.get("can_combine", {}).get("value") == "no":
        return False, "This voucher cannot be combined with other gift cards."

    # Check: works_on_sale_items
    if use_case.get("on_sale_item") and rules.get("works_on_sale_items", {}).get("value") == "no":
        return False, "This voucher is not applicable on sale or discounted items."

    # Check: combines_with_store_offers
    if use_case.get("with_store_offers") and rules.get("combines_with_store_offers", {}).get("value") == "no":
        return False, "This voucher cannot be combined with other store offers."

    # Check: max_cards_per_order
    num_cards = use_case.get("num_cards", 1)
    max_cards = rules.get("max_cards_per_order", {}).get("value")
    if max_cards is not None and num_cards > max_cards:
        return False, f"This voucher allows a maximum of {max_cards} cards per order, but you're trying to use {num_cards}."

    return True, None


def _parse_denominations(voucher: dict) -> tuple[bool, list[int]]:
    """Returns (is_custom, sorted_fixed_denoms). is_custom=True when empty."""
    denoms = sorted(set(int(d) for d in (voucher.get("denominations") or []) if d is not None))
    if denoms:
        return False, denoms
    return True, []


def _greedy_voucher_amount(
    price: float,
    fixed_denoms: list[int],
    stack_limit: int | None = None,
    value_cap: float | None = None,
) -> tuple[int, list[dict]]:
    """Largest sum of denominations (with repetition) within price, stack_limit,
    and value_cap. Returns (total, breakdown) — breakdown is the actual list of
    {denom, count} purchases that sum to `total`, since Gyftr only sells fixed
    denominations and a customer can't literally buy one voucher for the total
    amount; they need to know exactly which/how-many denominations to buy."""
    remaining = int(price)
    total = 0
    count_used = 0
    breakdown: list[dict] = []
    for d in sorted(fixed_denoms, reverse=True):
        if stack_limit is not None:
            room_by_count = stack_limit - count_used
            if room_by_count <= 0:
                break
        else:
            room_by_count = float("inf")
        if value_cap is not None:
            room_by_value = value_cap - total
            if room_by_value <= 0:
                break
            room_by_value_count = room_by_value // d
        else:
            room_by_value_count = float("inf")
        count = min(remaining // d, room_by_count, room_by_value_count)
        if count > 0:
            breakdown.append({"denom": d, "count": int(count)})
        total += count * d
        remaining -= count * d
        count_used += count
    return total, breakdown


def _format_breakdown(breakdown: list[dict]) -> str:
    """'8x Rs 5,000 + 1x Rs 2,000' style summary for how-to-buy copy — or just
    'Rs 2,000' for the common single-voucher case, not '1x Rs 2,000'."""
    if len(breakdown) == 1 and breakdown[0]["count"] == 1:
        return f"₹{breakdown[0]['denom']:,}"
    return " + ".join(f"{b['count']}×₹{b['denom']:,}" for b in breakdown)


def _denominations_str(voucher: dict) -> str:
    if voucher.get("is_custom_denom"):
        lo, hi = voucher.get("custom_min"), voucher.get("custom_max")
        if lo and hi:
            return f"Custom (₹{lo}–₹{hi})"
    denoms = sorted(set(int(d) for d in (voucher.get("denominations") or []) if d is not None))
    return " / ".join(str(d) for d in denoms)


def _discount_pct(voucher: dict, payment_method: str) -> float:
    keys = PAYMENT_METHOD_TO_DISCOUNT_KEYS.get(payment_method.lower(), [])
    discounts = voucher.get("discounts") or {}
    found = [discounts[k] for k in keys if discounts.get(k) is not None]
    if found:
        return max(found)
    return 0


_INSTRUCTION_EXCLUDE = [
    "also works at",
    "also be used on",
    "also accepted at",
    "can also be used online on",
    "can also be used at",
]


_ALL_CAPS_HEADER_RE = re.compile(r"^[A-Z][A-Z\s&/-]+$")
_TRAILING_IMPORTANT_INSTRUCTIONS_RE = re.compile(r"important instructions\s*$", re.IGNORECASE)


def _clean_instructions(html: str) -> list[str]:
    """Strip HTML tags, cross-redemption mentions, and Gyftr page-navigation
    noise (all-caps tab labels like "TERMS & CONDITIONS" / "HOW TO USE", and
    "{Brand} Important Instructions" section headers) — the single source of
    truth for both web and WhatsApp, which both display this list as-is."""
    text = re.sub(r"<[^>]+>", "", html)
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _TRAILING_IMPORTANT_INSTRUCTIONS_RE.search(line) or _ALL_CAPS_HEADER_RE.match(line):
            continue
        lower = line.lower()
        if any(phrase in lower for phrase in _INSTRUCTION_EXCLUDE):
            continue
        result.append(line)
    return result


def calculate_effective_price(price: float, voucher: dict, payment_method: str = "upi") -> dict:
    discount_pct = _discount_pct(voucher, payment_method)
    custom_txns_needed = None
    denomination_breakdown: list[dict] = []

    if voucher.get("is_custom_denom"):
        # Real custom-amount range (e.g. Titan: any exact amount ₹100-10,000).
        # Always preferred over any fixed denominations the brand also lists —
        # it covers the purchase price more precisely. max_value is a per-voucher
        # cap; up to stack_limit vouchers can be combined in one bill.
        custom_max = voucher.get("custom_max") or 0
        stack_limit = voucher.get("stack_limit")
        if stack_limit is not None:
            total_cap = custom_max * stack_limit
        elif voucher.get("stack_limit_confidence") == "unlimited_stated":
            # No stated per-bill count cap — bounded by the purchase price
            # itself (or a real value_cap, if the brand's terms separately
            # state one), not an arbitrary vouchers-per-bill number.
            value_cap = voucher.get("value_cap")
            total_cap = min(price, value_cap) if value_cap else price
        else:
            # Unknown — conservative default of a single voucher.
            total_cap = custom_max
        voucher_amount = min(price, total_cap) if custom_max else 0.0
        remainder = round(price - voucher_amount, 2)
        is_custom = True
        custom_txns_needed = math.ceil(voucher_amount / custom_max) if custom_max and voucher_amount else 0
    else:
        is_custom, fixed_denoms = _parse_denominations(voucher)
        if is_custom or not fixed_denoms:
            voucher_amount = price
            remainder = 0.0
            is_custom = True
        else:
            # A missing stack_limit means "no stacking data found," not
            # "unlimited" — only a confirmed unlimited_stated confidence
            # (e.g. a wallet/e-Pay brand like Bata) should be passed through
            # as truly uncapped. Same conservative-default-of-1 rule the
            # is_custom_denom branch above already applies; without this,
            # brands we simply never found stacking text for (Swiggy
            # Instamart, Lenskart, Max Fashion Online, ...) were silently
            # treated the same as a confirmed-unlimited wallet brand.
            stack_limit = voucher.get("stack_limit")
            if stack_limit is None and voucher.get("stack_limit_confidence") != "unlimited_stated":
                stack_limit = 1
            amount, denomination_breakdown = _greedy_voucher_amount(
                price, fixed_denoms,
                stack_limit=stack_limit,
                value_cap=voucher.get("value_cap"),
            )
            voucher_amount = float(amount)
            remainder = round(price - voucher_amount, 2)

    # Two unrelated caps can both apply to a custom-amount voucher (e.g.
    # Archies Gallery): `custom_max` limits how big a SINGLE voucher can be
    # (₹10,000), `purchase_cap_per_txn` limits total rupees per checkout
    # (₹88,500) — a big purchase can need multiple *vouchers* without ever
    # needing multiple *checkouts*. The old code let whichever cap happened
    # to be set win outright, so a custom-denom brand that also had a
    # purchase_cap_per_txn silently ignored its own custom_max — telling the
    # customer to buy one voucher bigger than Gyftr actually allows.
    # Bug found via live testing, 2026-08-28.
    cap_txns = math.ceil(voucher_amount / voucher["purchase_cap_per_txn"]) if voucher.get("purchase_cap_per_txn") and voucher_amount else 1

    # Real number of separate checkouts needed to buy this denomination mix
    # on a single-item-checkout platform: each *distinct* denomination in the
    # breakdown is its own purchase (you can't select two different amounts
    # in one Maximize/BuyHatke order), and repeats of the *same* denomination
    # beyond that reseller's own per-order quantity cap need another purchase
    # too. Deliberately uses `reseller_stack_limit` — the reseller's real,
    # un-overridden order-quantity cap — never the `stack_limit` that
    # `_store_allows_stacking` may have lifted to "unlimited" for value-cap
    # purposes; that override describes what the STORE will redeem, not how
    # many the RESELLER lets you buy in one sitting. Missing data defaults to
    # 1 per order, the same conservative-default rule used elsewhere here.
    reseller_denom_txns = 1
    if denomination_breakdown and voucher.get("voucher_platform", "Gyftr").lower() in _SINGLE_ITEM_CHECKOUT_PLATFORMS:
        reseller_limit = voucher.get("reseller_stack_limit") or 1
        reseller_denom_txns = sum(math.ceil(b["count"] / reseller_limit) for b in denomination_breakdown)

    txns_needed = max(cap_txns, custom_txns_needed or 1, reseller_denom_txns)
    if custom_txns_needed is not None and custom_txns_needed >= cap_txns:
        per_txn_cap: float | None = voucher.get("custom_max")
        per_txn_cap_kind: str | None = "voucher"
    elif voucher.get("purchase_cap_per_txn"):
        per_txn_cap = voucher["purchase_cap_per_txn"]
        per_txn_cap_kind = "transaction"
    else:
        per_txn_cap = None
        per_txn_cap_kind = None

    discount_amount = round(voucher_amount * discount_pct / 100, 2)
    effective_price = round(price - discount_amount, 2)

    # What the customer actually needs to buy — Gyftr only sells fixed
    # denominations (or, for custom-amount/wallet brands, up to `custom_max`
    # per voucher), so "buy a voucher worth the full total" is never
    # literally purchasable when more than one voucher is needed. Surfacing
    # the real breakdown here (rather than just the total) is what makes the
    # how-to-buy copy actually executable instead of misleading. Gated on
    # `custom_txns_needed` specifically (how many voucher *units* are
    # needed), not the combined `txns_needed` above — a custom voucher still
    # needs its per-unit breakdown even when it all fits in one checkout.
    if denomination_breakdown:
        purchase_breakdown = _format_breakdown(denomination_breakdown)
    elif is_custom and voucher.get("is_custom_denom") and custom_txns_needed and voucher.get("custom_max"):
        custom_max = voucher["custom_max"]
        if custom_txns_needed > 1:
            # A custom-amount voucher is bought by typing in an exact rupee
            # figure, not by choosing "up to X" — so the buy step must hand
            # the customer the exact amount for each of the N vouchers
            # (custom_max for every voucher but the last, the true remainder
            # for the last one), the same way the fixed-denomination branch
            # above always gives an exact, purchasable breakdown. Also
            # populated as a real denomination_breakdown (not just a string)
            # so callers can render an itemized list/box instead of an
            # ambiguous inline "2×₹10,000" fragment.
            full_count = int(voucher_amount // custom_max)
            last_amount = round(voucher_amount - full_count * custom_max, 2)
            if full_count:
                denomination_breakdown.append({"denom": int(custom_max), "count": full_count})
            if last_amount:
                denomination_breakdown.append({"denom": int(last_amount), "count": 1})
            purchase_breakdown = _format_breakdown(denomination_breakdown)
        else:
            purchase_breakdown = f"₹{voucher_amount:,.0f}"
    else:
        purchase_breakdown = f"₹{voucher_amount:,.0f}" if voucher_amount else ""

    return {
        "original_price": price,
        "voucher_amount": voucher_amount,
        "remainder_at_checkout": remainder,
        "is_custom": is_custom,
        "voucher_discount_pct": discount_pct,
        "voucher_discount_amount": discount_amount,
        "effective_price": effective_price,
        "payment_method": payment_method,
        "txns_needed": txns_needed,
        "per_txn_cap": per_txn_cap,
        "per_txn_cap_kind": per_txn_cap_kind,
        "voucher_platform": voucher.get("voucher_platform", "Gyftr"),
        "voucher_url": voucher.get("voucher_url") or f"https://www.gyftr.com/{voucher['slug']}",
        "redemption_type": voucher.get("redemption_type", ""),
        "denominations": _denominations_str(voucher),
        "denomination_breakdown": denomination_breakdown,
        "purchase_breakdown": purchase_breakdown,
        "redemption_instructions": voucher.get("redemption_instructions")
        if voucher.get("redemption_instructions") is not None
        else _clean_instructions(voucher.get("important_instructions_raw") or ""),
    }


def get_best_voucher_deal(merchant_name: str, price: float) -> dict | None:
    """UPI-rate voucher deal for merchant_name, or None if no voucher, 0% UPI
    discount, or price below the minimum denomination."""
    record = voucher_repository.get_by_merchant(merchant_name)
    if record is None:
        return None
    products = record.get("products") or []
    if not products:
        return None
    # Gyftr's canonical schema nests the actual rate/denomination/stack_limit
    # fields calculate_effective_price needs inside products[0] (brand-level
    # keys like important_instructions_raw/stack_limit_confidence stay on
    # `record`) — always exactly one product per Gyftr brand, unlike
    # Maximize's multi-tier records. Flatten before calculating.
    voucher = {**record, **products[0]}
    deal = calculate_effective_price(price, voucher, payment_method="upi")
    if not deal["voucher_discount_pct"]:
        return None
    if deal["voucher_amount"] == 0:
        return None
    return deal


def _best_tier_deal(price: float, tiers: list[dict], payment_method: str = "upi") -> tuple[dict, dict] | None:
    """Runs calculate_effective_price per tier (unchanged) and keeps whichever
    tier yields the lowest effective_price among tiers with a real discount
    and a non-zero voucher_amount — same guard get_best_voucher_deal uses,
    just tried once per tier since a Maximize brand can have more than one
    genuine denomination size (e.g. BigBasket's custom-up-to-10k vs its
    fixed-up-to-2k listing)."""
    best_deal = None
    best_tier = None
    for tier in tiers:
        deal = calculate_effective_price(price, tier, payment_method)
        if not deal["voucher_discount_pct"] or deal["voucher_amount"] == 0:
            continue
        if best_deal is None or deal["effective_price"] < best_deal["effective_price"]:
            best_deal = deal
            best_tier = tier
    if best_deal is None:
        return None
    return best_deal, best_tier


def get_best_maximize_deal(merchant_name: str, price: float) -> tuple[dict, dict, str | None] | None:
    """Maximize equivalent of get_best_voucher_deal — returns (deal, tier,
    brand_name). brand_name is the catalog's own clean display name (e.g.
    "AJIO Luxe") — the tier dict itself doesn't carry it, and callers need
    it for display instead of the raw seller string a search result reports
    for this merchant (sometimes a bare domain like "luxe.ajio.com")."""
    record = maximize_repository.get_by_merchant(merchant_name)
    if record is None:
        return None
    # Canonical schema's actual key is "products" (same as Gyftr), not
    # "tiers" — this was reading an empty list for every single Maximize
    # brand, so Maximize deals never once won the price comparison against
    # Gyftr, regardless of actual rate. Each product also needs its own
    # source_url/platform label flattened in (Maximize's field is
    # source_url, not voucher_url — calculate_effective_price's generic
    # "gyftr.com/{slug}" fallback is only correct for actual Gyftr vouchers).
    stacks = _store_allows_stacking(merchant_name)
    store_cap = _store_value_cap(merchant_name)
    tiers = [
        {
            **record, **p,
            "voucher_platform": "Maximize",
            "voucher_url": p.get("source_url"),
            # Maximize's own real per-order quantity cap, kept under a
            # separate key so it survives the "stacks" override just below —
            # that override answers "how much will the store redeem in
            # total," this answers "how many can I actually buy in one
            # Maximize checkout," and they can legitimately differ (live-
            # confirmed 2026-09-03: Frido's store terms allow combining
            # vouchers, but Maximize itself still caps the order at 4).
            "reseller_stack_limit": p.get("stack_limit"),
            # Same correction as BuyHatke: a reseller's per-order voucher
            # count describes its own checkout, not what the store accepts.
            # 58 Maximize brands carry "1 voucher" against stores whose own
            # terms say vouchers combine.
            **({"stack_limit": None, "stack_limit_confidence": "unlimited_stated"} if stacks else {}),
            # The store's own redemption ceiling still applies, whoever sold it.
            **({"value_cap": store_cap} if store_cap else {}),
        }
        for p in (record.get("products") or [])
    ]
    result = _best_tier_deal(price, tiers, payment_method="upi")
    if result is None:
        return None
    deal, tier = result
    return deal, tier, record.get("brand_name")


def _store_allows_stacking(merchant_name: str) -> bool:
    """Does the STORE let a shopper combine several vouchers in one order?

    That is a fact about the store, stated in its own terms, and Gyftr's
    scrape is the only source that parses it (`stack_limit_confidence ==
    "unlimited_stated"`, e.g. Myntra's "Multiple Gift Vouchers CAN be
    combined & added to Myntra Wallet").

    It matters because Maximize and BuyHatke report limits about *buying on
    their own site* — BuyHatke's `maxVoucherPerOrder: 1` means one voucher
    per BuyHatke order, nothing about what Myntra accepts — and those were
    being applied as redemption limits. On a ₹4,049 Myntra bag that quoted
    ₹132 of savings instead of ₹212, because it bought one ₹2,500 voucher
    instead of ₹2,500 + ₹1,500. Found 2026-09-02 when the shopper pointed
    out that BuyHatke visibly sells Myntra vouchers far larger than the
    "cap" we were enforcing.
    """
    gyftr = voucher_repository.get_by_merchant(merchant_name)
    return bool(gyftr) and gyftr.get("stack_limit_confidence") == "unlimited_stated"


def _store_value_cap(merchant_name: str) -> float | None:
    """A ceiling the STORE puts on redemption, e.g. Amazon's "Gift Vouchers
    over INR 50,000 CANNOT be added to wallet per calendar month".

    Like stacking, this is a fact about the store, so it holds no matter who
    sold the voucher — but it is only parsed out of Gyftr's terms scrape.
    Without this, lifting the stacking limit let a Maximize-sourced Amazon
    deal recommend ₹60,403 of credit, ₹10,403 of which could not have been
    loaded that month (caught 2026-09-02, immediately after the fix that
    lifted stacking).
    """
    gyftr = voucher_repository.get_by_merchant(merchant_name)
    if not gyftr:
        return None
    caps = [p.get("value_cap") for p in (gyftr.get("products") or []) if p.get("value_cap")]
    return min(caps) if caps else None


def get_best_buyhatke_deal(merchant_name: str, price: float) -> tuple[dict, dict, str | None] | None:
    """BuyHatke equivalent of get_best_maximize_deal — same multi-tier shape
    (different denomination bands can carry different discount %, e.g.
    Myntra's ₹250 tier vs its ₹200/₹500/etc tier), same tier-picking logic.

    BuyHatke has no card-purchase option at all (confirmed via live testing,
    2026-08-13) — its discounts dict only ever carries a "UPI" key, never
    "Credit Card", so calculate_effective_price's card path naturally yields
    a 0% card discount here instead of a fabricated one.
    """
    record = buyhatke_repository.get_by_merchant(merchant_name)
    if record is None:
        return None
    stacks = _store_allows_stacking(merchant_name)
    store_cap = _store_value_cap(merchant_name)
    tiers = [
        {
            **record, **p,
            "voucher_platform": "BuyHatke",
            "voucher_url": p.get("source_url"),
            # BuyHatke's real per-order quantity cap is always 1 voucher —
            # confirmed by the user's own live testing 2026-09-03: unlike
            # Maximize (which can vary, e.g. Frido allows 4 of the same
            # denomination in one order), BuyHatke never lets you buy more
            # than a single voucher per checkout, even of the same
            # denomination. Hardcoded rather than read from `stack_limit`,
            # since that field carries a different, store-side meaning (see
            # _store_allows_stacking's docstring) — reading it here for
            # per-order quantity purposes is exactly the same category of
            # mistake already fixed for Maximize.
            "reseller_stack_limit": 1,
            # BuyHatke reports a per-order voucher COUNT for its own checkout.
            # It says nothing about how many the store will accept, and when
            # the store's own terms say vouchers can be combined, that is the
            # rule that governs redemption. No value or transaction limit is
            # inferred here — inventing one is what produced a wrong ₹2,500
            # ceiling on a brand that visibly sells ₹10,000 vouchers.
            **({
                "stack_limit": None,
                "stack_limit_confidence": "unlimited_stated",
            } if stacks else {}),
            # The store's own redemption ceiling still applies, whoever sold it.
            **({"value_cap": store_cap} if store_cap else {}),
        }
        for p in (record.get("products") or [])
    ]
    result = _best_tier_deal(price, tiers, payment_method="upi")
    if result is None:
        return None
    deal, tier = result
    return deal, tier, record.get("brand_name")


def _pick_best_candidate(candidates: list[tuple]) -> tuple:
    """Chooses which source's deal to recommend for one merchant.

    Cheapest wins by default (Dealo's "always show the cheaper source"
    rule) — UNLESS a single-transaction option exists and the cheapest
    option needs more than one transaction. In that case the single-
    transaction option wins unless the multi-transaction one is cheaper by
    more than MULTI_TXN_SAVINGS_THRESHOLD: closing purchase friction is a
    stated product USP, so a couple of percent extra saving isn't worth
    sending the user through a second or third checkout. Product decision
    made 2026-09-03 after a real case (Frido) where Maximize's 16.25% needed
    2 transactions and Gyftr's 14% needed 1, for only ~2.6% more.
    """
    cheapest = min(candidates, key=lambda c: c[0]["effective_price"])
    if cheapest[0].get("txns_needed", 1) <= 1:
        return cheapest

    single_txn = [c for c in candidates if c[0].get("txns_needed", 1) <= 1]
    if not single_txn:
        return cheapest

    best_single = min(single_txn, key=lambda c: c[0]["effective_price"])
    single_price = best_single[0]["effective_price"]
    cheapest_price = cheapest[0]["effective_price"]
    if cheapest_price <= single_price * (1 - MULTI_TXN_SAVINGS_THRESHOLD):
        return cheapest
    return best_single


def build_deals(results: list[dict], product_name: str = "") -> list[dict]:
    """Build per-merchant voucher deals for the given route candidates,
    checking Gyftr, Maximize, and BuyHatke and keeping whichever gives the
    lower final price — this is Dealo's "always show the cheaper source"
    rule.

    Ported from pipeline.step5_vouchers. Skips a *source* whose redemption
    restrictions exclude the product's category (not the whole merchant —
    a Gyftr category restriction must not hide a valid Maximize/BuyHatke
    deal for the same merchant, and vice versa). UPI is the recommendation
    rate.
    """
    deals: list[dict] = []
    seen_merchants: set[str] = set()

    try:
        category = classify_product(product_name)
    except Exception:
        category = None

    def _category_blocked(restrictions: list[str]) -> bool:
        try:
            return category is not None and restriction_mentions_category(restrictions, category)
        except Exception:
            return False

    for r in results:
        if r.get("match_type") not in ("Exact Match", "Listed"):
            continue
        merchant = r.get("merchant") or r.get("source") or ""
        price = r.get("price") or r.get("extracted_price") or 0
        merchant_key = merchant.lower()
        if not merchant or not price or merchant_key in seen_merchants:
            continue
        seen_merchants.add(merchant_key)

        gyftr_voucher = voucher_repository.get_by_merchant(merchant)
        gyftr_deal = None
        if gyftr_voucher is not None and not _category_blocked(gyftr_voucher.get("redemption_restrictions", [])):
            gyftr_deal = get_best_voucher_deal(merchant, price)

        # Maximize/BuyHatke tiers carry no redemption_restrictions field yet
        # (Gyftr's scrape captured category rules from free-text T&Cs;
        # neither source's structured fields expose an equivalent) —
        # category filtering simply doesn't apply to these deals until that
        # data exists.
        maximize_result = get_best_maximize_deal(merchant, price)
        maximize_deal, maximize_tier, maximize_brand_name = maximize_result if maximize_result else (None, None, None)

        buyhatke_result = get_best_buyhatke_deal(merchant, price)
        buyhatke_deal, buyhatke_tier, buyhatke_brand_name = buyhatke_result if buyhatke_result else (None, None, None)

        candidates = [
            c for c in (
                (gyftr_deal, gyftr_voucher, "gyftr", gyftr_voucher.get("brand_name") if gyftr_voucher else None),
                (maximize_deal, maximize_tier, "maximize", maximize_brand_name),
                (buyhatke_deal, buyhatke_tier, "buyhatke", buyhatke_brand_name),
            )
            if c[0] is not None
        ]
        if not candidates:
            continue

        # Dealo's "always show the cheaper source" rule, now friction-aware:
        # see _pick_best_candidate for the single-vs-multi-transaction
        # tie-break.
        deal, voucher, voucher_source, brand_name = _pick_best_candidate(candidates)

        # `deal["redemption_type"]`, not `voucher.get(...)`: for a Gyftr deal,
        # `voucher` here is the raw brand-level record, and redemption_type
        # actually lives one level deeper, inside its `products[0]` — reading
        # it off `voucher` directly always silently returned "" (never
        # "Offline"), which meant offline-only vouchers (e.g. Puma) never
        # tripped the in-store split below and got baked straight into the
        # online route's price instead. `deal` was already correctly built
        # from the flattened product data, so its own field is what's right.
        offline_only = deal.get("redemption_type") == "Offline"

        card_deal = calculate_effective_price(price, voucher, "card")

        # "How do I use this gift card" is a brand-level fact, the same
        # regardless of which platform actually sold the voucher — so prefer
        # Gyftr's copy whenever this merchant has a Gyftr listing at all,
        # even when the winning route is Maximize/BuyHatke. Gyftr's field
        # has had real manual QA (20+ brands hand-corrected after specific
        # wrong-instruction bugs); Maximize/BuyHatke's is a fresh, far less
        # reviewed auto-extraction over messier source text (BuyHatke's is
        # raw HTML) that's already been caught producing a *worse* line for
        # the same brand than Gyftr has (TATA CLiQ: Gyftr's correctly names
        # the CLiQ Cash/KYC step; Maximize's own extraction doesn't). Only
        # fall through to the winning source's own field when Gyftr doesn't
        # cover this merchant at all — `gyftr_voucher` is already looked up
        # above for every merchant regardless of which source wins.
        how_to_redeem_short = None
        if gyftr_voucher is not None:
            how_to_redeem_short = gyftr_voucher.get("how_to_redeem_short")
        if not how_to_redeem_short:
            how_to_redeem_short = voucher.get("how_to_redeem_short")

        deals.append({
            "merchant": merchant,
            "brand_name": brand_name or merchant,
            "product_price": price,
            "voucher_url": deal["voucher_url"],
            "voucher_source": voucher_source,
            "offline_only": offline_only,
            "upi": {
                "pct": deal["voucher_discount_pct"],
                "voucher_amount": deal["voucher_amount"],
                "remainder": deal.get("remainder_at_checkout") or 0,
                "saving": deal["voucher_discount_amount"],
                "effective_price": deal["effective_price"],
                "txns_needed": deal.get("txns_needed", 1),
                # Whichever cap actually forced multiple purchases — not
                # always `purchase_cap_per_txn`; for a custom-amount voucher
                # it's `custom_max` (see calculate_effective_price). Reading
                # the raw voucher record's purchase_cap_per_txn here directly
                # used to show an unrelated, much larger number next to a
                # multi-buy instruction actually driven by custom_max.
                "purchase_cap_per_txn": deal.get("per_txn_cap"),
                "per_txn_cap_kind": deal.get("per_txn_cap_kind"),
                "denomination_breakdown": deal.get("denomination_breakdown") or [],
                "purchase_breakdown": deal.get("purchase_breakdown") or "",
            },
            "card": {
                "pct": card_deal["voucher_discount_pct"],
                "saving": card_deal["voucher_discount_amount"],
                "effective_price": card_deal["effective_price"],
            },
            "redemption_type": deal["redemption_type"],
            "denominations": deal["denominations"],
            "redemption_instructions": deal.get("redemption_instructions", []),
            "how_to_redeem_short": how_to_redeem_short,
        })

    return deals


def _headline_rate(record: dict | None, source: str) -> tuple[float, dict, str | None] | None:
    """Best UPI headline discount % for a brand record, with no price in
    hand to compute a real ₹ saving against (the Chrome extension's
    checkout-price read failed or wasn't attempted). Gyftr always has
    exactly one product; Maximize/BuyHatke can have several tiers — picks
    whichever has the higher UPI rate, same "honest best available signal"
    approach `search_service._match_brand_voucher` already uses for its own
    no-price brand-voucher shortcut."""
    if record is None:
        return None
    products = record.get("products") or []
    if not products:
        return None
    if source == "gyftr":
        product = products[0]
        pct = (product.get("discounts") or {}).get("UPI") or 0
        return (pct, product, record.get("brand_name")) if pct else None
    best = max(products, key=lambda p: p.get("best_discount_pct") or 0, default=None)
    if not best or not best.get("best_discount_pct"):
        return None
    return best["best_discount_pct"], best, record.get("brand_name")


def _norm_brand(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


_SOURCE_REPOS = {
    "gyftr": voucher_repository,
    "maximize": maximize_repository,
    "buyhatke": buyhatke_repository,
}


def _redemption_help(merchant_name: str, voucher_source: str) -> tuple[str | None, list, list]:
    """How to use THIS voucher, and what this voucher specifically excludes —
    both taken from the source actually selling it. Returns
    (short, steps, restrictions).

    Deliberately does NOT borrow another seller's copy. The three sources sell
    genuinely different products under the same brand name, confirmed in the
    data (2026-09-02): Maximize's Myntra card is one-time-use where Gyftr's
    isn't; Gyftr's Nykaa card works in store while BuyHatke's is online only;
    and BuyHatke's AJIO card is not valid on H&M products, a restriction that
    appears on no other source. Showing Gyftr's instructions beside a BuyHatke
    voucher therefore states rules that may not hold for the thing the shopper
    just bought.

    266 BuyHatke listings publish no steps of their own (Myntra among them —
    its usageInstructions is literally empty). Those return nothing here, and
    the caller sends the shopper to the voucher page instead of showing
    someone else's steps.
    """
    repo = _SOURCE_REPOS.get(voucher_source)
    record = repo.get_by_merchant(merchant_name) if repo else None
    if not record:
        return None, [], []
    return (
        record.get("how_to_redeem_short"),
        record.get("how_to_redeem_steps") or [],
        record.get("redemption_restrictions") or [],
    )


def is_exact_brand_match(queried: str, resolved_brand_name: str | None) -> bool:
    """True when a lookup resolved to the brand actually asked for, rather
    than fuzzy-matching onto a same-family sibling ("Ajio" -> "Ajio Luxe")."""
    return _norm_brand(queried) == _norm_brand(resolved_brand_name)


def _prefer_exact_name_matches(candidates: list[tuple], merchant_name: str, brand_index: int) -> list[tuple]:
    """When at least one source's matched brand_name is an exact (normalized)
    match for the merchant we actually asked about, restrict to only those —
    a source that could only fuzzy-match to a same-family sibling (e.g.
    BuyHatke has no plain "Amazon" listing, only "Amazon Fresh"/"Amazon
    Shopping", and would otherwise win the % comparison on a technicality)
    must not outrank a source with the real, exact brand. Live-confirmed
    2026-08-31: querying "Amazon" returned BuyHatke's unrelated "Amazon
    Fresh" (1.68%) over Gyftr's/Maximize's correct plain "Amazon" listings,
    purely because BuyHatke doesn't carry a plain "Amazon" entry at all —
    same family-brand ambiguity class as the Titan/Trends case, but this one
    has a real, exact match available on other sources to prefer instead of
    leaving it unresolved."""
    target = _norm_brand(merchant_name)
    exact = [c for c in candidates if _norm_brand(c[brand_index]) == target]
    return exact or candidates


def get_voucher_check(merchant_name: str, price: float | None = None) -> dict | None:
    """Single merchant-name lookup across all 3 voucher sources, for the
    Chrome extension's checkout-page popup (`GET /voucher-check`). Returns
    None if no source has a voucher for this merchant at all.

    With a real `price`, reuses the same priced per-source lookups
    (`get_best_voucher_deal` / `get_best_maximize_deal` /
    `get_best_buyhatke_deal`) `build_deals` already uses for routes, keeping
    whichever source gives the lowest effective price — real ₹ savings, not
    a guess. Without a price (the extension couldn't read one confidently
    off the page), falls back to each source's own headline UPI rate and
    keeps the highest one — a % is still honest without a price; a ₹ figure
    would not be.
    """
    if price:
        gyftr_record = voucher_repository.get_by_merchant(merchant_name)
        gyftr_voucher = (
            {**gyftr_record, **((gyftr_record.get("products") or [{}])[0])} if gyftr_record else None
        )
        gyftr_deal = get_best_voucher_deal(merchant_name, price) if gyftr_record else None

        maximize_result = get_best_maximize_deal(merchant_name, price)
        maximize_deal, maximize_tier, maximize_brand_name = (
            maximize_result if maximize_result else (None, None, None)
        )

        buyhatke_result = get_best_buyhatke_deal(merchant_name, price)
        buyhatke_deal, buyhatke_tier, buyhatke_brand_name = (
            buyhatke_result if buyhatke_result else (None, None, None)
        )

        candidates = [
            c for c in (
                (gyftr_deal, "gyftr", gyftr_voucher.get("brand_name") if gyftr_voucher else None, gyftr_voucher),
                (maximize_deal, "maximize", maximize_brand_name, maximize_tier),
                (buyhatke_deal, "buyhatke", buyhatke_brand_name, buyhatke_tier),
            )
            if c[0] is not None
        ]
        if not candidates:
            return None
        candidates = _prefer_exact_name_matches(candidates, merchant_name, brand_index=2)
        deal, voucher_source, brand_name, voucher = min(
            candidates, key=lambda c: c[0]["effective_price"]
        )

        # What the same purchase would earn paid by card instead. The rate we
        # promise on the store's checkout page is the UPI rate, so if the
        # shopper pays for the voucher by card the promised saving silently
        # shrinks (Nykaa: 5% by UPI, 3% by card). The extension needs this to
        # warn them at the moment they're choosing how to pay.
        card_pct = 0.0
        try:
            card_pct = calculate_effective_price(price, voucher, "card")["voucher_discount_pct"]
        except Exception:
            pass

        redeem_short, redeem_steps, redeem_limits = _redemption_help(merchant_name, voucher_source)
        return {
            "has_voucher": True,
            "brand_name": brand_name or merchant_name,
            "voucher_source": voucher_source,
            "pct": deal["voucher_discount_pct"],
            "saving": deal["voucher_discount_amount"],
            "effective_price": deal["effective_price"],
            "voucher_url": deal["voucher_url"],
            "priced": True,
            # --- everything below powers the guided journey ---
            "voucher_amount": deal.get("voucher_amount"),
            "remainder": deal.get("remainder_at_checkout") or 0,
            "purchase_breakdown": deal.get("purchase_breakdown") or "",
            "denomination_breakdown": deal.get("denomination_breakdown") or [],
            "txns_needed": deal.get("txns_needed", 1),
            "card_pct": card_pct,
            "how_to_redeem_short": redeem_short,
            "how_to_redeem_steps": redeem_steps,
            "restrictions": redeem_limits,
        }

    raw_hits = (
        ("gyftr", _headline_rate(voucher_repository.get_by_merchant(merchant_name), "gyftr")),
        ("maximize", _headline_rate(maximize_repository.get_by_merchant(merchant_name), "maximize")),
        ("buyhatke", _headline_rate(buyhatke_repository.get_by_merchant(merchant_name), "buyhatke")),
    )
    hits = [(pct, product, brand_name, source) for source, hit in raw_hits if hit for pct, product, brand_name in [hit]]
    if not hits:
        return None
    hits = _prefer_exact_name_matches(hits, merchant_name, brand_index=2)
    pct, product, brand_name, voucher_source = max(hits, key=lambda h: h[0])
    voucher_url = product.get("voucher_url") or product.get("source_url")
    if voucher_source == "gyftr" and not voucher_url:
        voucher_url = f"https://www.gyftr.com/{product.get('slug') or ''}"

    # "Where do I enter this code" doesn't depend on knowing the order total —
    # but it used to be returned only on the priced path, so a shopper whose
    # cart total couldn't be read lost the redemption coaching entirely, which
    # is the most valuable part of the last step (found in live testing).
    redeem_short, redeem_steps, redeem_limits = _redemption_help(merchant_name, voucher_source)
    return {
        "has_voucher": True,
        "brand_name": brand_name or merchant_name,
        "voucher_source": voucher_source,
        "pct": pct,
        "saving": None,
        "effective_price": None,
        "voucher_url": voucher_url,
        "priced": False,
        "how_to_redeem_short": redeem_short,
        "how_to_redeem_steps": redeem_steps,
        "restrictions": redeem_limits,
    }
