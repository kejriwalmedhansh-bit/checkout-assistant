"""
normalize_buyhatke_master.py — Build data/buyhatke_master.json from the raw
db/buyhatke_scrape_progress.json scrape, in the same canonical
{brand_name, slug, source, products[...]} shape voucher_repository.py and
maximize_repository.py already read (see normalize_existing_masters.py for
the Gyftr/Maximize equivalents).

Field mapping decisions (BuyHatke's voucherChoices API — see
scrape_buyhatke_details.py):

- redemption_type: "Online" if availableOnline else "Offline" — a real
  structured flag, not a Gyftr-style free-text guess.
- Per-denomination discount variance (e.g. Myntra's ₹250 tier at a different
  rate than its other denominations, reported directly by the user from live
  testing): denominationDisMap gives an exact rate per denomination, so
  denominations are grouped into one `products[]` tier per distinct rate —
  the same multi-tier shape Maximize already uses, reusing
  voucher_service._best_tier_deal as-is.
- stack_limit = min(maxVoucherPerOrder, maxVouchersPerUserTransaction) where
  present — the tighter of the two count caps BuyHatke reports; conservative
  by the same "don't overstate the benefit" logic Gyftr's own defaults use.
- value_cap = maxOrderAmount. Deliberately NOT purchase_cap_per_txn: real
  scraped data shows maxOrderAmount is often *below* the largest single
  denomination (e.g. Absolute Barbecues: denoms up to ₹5,000 but
  maxOrderAmount ₹5,000 while maxVoucherAmount reads ₹10,000) — i.e. a real
  per-order total-value ceiling, not a payment-processor transaction cap.
  purchase_cap_per_txn is instead mapped from maxAmountPerUserTransaction,
  a separate field that was None in every brand sampled so far but exists
  for exactly this distinct concept.
- Custom-amount brands (denominations: null) use minVoucherAmount/
  maxVoucherAmount for the real per-voucher range — minAmount/maxAmount are
  sometimes null even when a real range exists (e.g. "109F").
- isCashback brands (e.g. Amazon Pay) are EXCLUDED, not just discounted: a
  cashback voucher means paying full price and getting money back later, not
  an instant discount at purchase time the way every other source here
  works — folding it into the same discounts{} field as a real discount
  would overstate certainty at the moment of purchase (CLAUDE.md rule #1:
  a wrong result is worse than no result). Flagged for a product decision
  later rather than silently included or silently dropped without a trace —
  see EXCLUDED_CASHBACK_LOG below.
- discounts only ever has a "UPI" key, never "Credit Card": BuyHatke doesn't
  accept card payment for buying a voucher at all (confirmed via live
  testing, 2026-08-13) — leaving "Credit Card" unset makes
  voucher_service.calculate_effective_price's card path naturally report 0%
  instead of a fabricated rate (see get_best_buyhatke_deal's docstring).

Usage:  /usr/local/bin/python3.11 scripts/normalize_buyhatke_master.py
"""

import json
import re
from pathlib import Path

PROGRESS_FILE = Path(__file__).resolve().parent.parent / "db" / "buyhatke_scrape_progress.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "buyhatke_master.json"
EXCLUDED_CASHBACK_LOG = Path(__file__).resolve().parent.parent / "db" / "buyhatke_excluded_cashback.json"
EXCLUDED_INACTIVE_LOG = Path(__file__).resolve().parent.parent / "db" / "buyhatke_excluded_inactive.json"
EXCLUDED_SUBSCRIPTION_LOG = Path(__file__).resolve().parent.parent / "db" / "buyhatke_excluded_subscription.json"

_RESTRICTION_MARKERS = (
    "not applicable on",
    "not applicable for",
    "restricted categor",
    "cannot be used to purchase",
    "cannot be used on",
)

# BuyHatke's own `title` field sometimes duplicates its wait-time suffix
# verbatim in parentheses, e.g. "Titan In Store 3 Day Wait (3 Day Wait)" —
# found 2026-08-14 across 14 brands (Titan/Fastrack/Lenskart/etc families).
# Cosmetic only (doesn't affect matching or pricing), but confusing to read
# in the sheet, so collapse the redundant "(X)" back down to "X".
_DUPLICATE_PAREN_SUFFIX_RE = re.compile(r"^(.*?)\s*\(\1\)\s*$")


def _clean_title(title: str) -> str:
    # Only the exact trailing phrase repeated in parens should collapse —
    # try progressively shorter trailing word-groups against the
    # parenthesized text rather than the whole title (the duplicate is
    # always just the last few words, e.g. "3 Day Wait", not the full name).
    m = re.search(r"\(([^()]+)\)\s*$", title)
    if not m:
        return title
    paren = m.group(1).strip()
    before = title[: m.start()].rstrip()
    if before.lower().endswith(paren.lower()):
        return before
    return title


# BuyHatke brands whose product is a subscription/membership activation
# code, not a spend-anywhere voucher — same real-world category Gyftr's and
# Maximize's own vendor audits already exclude for the literal same reason
# (see "All GV Details" sheet: Amazon product IDs 547-549, "Excluded ...
# (subscription)"). Only Amazon's variants make this list: "Amazon" is also
# a genuine general-marketplace merchant name in Dealo's own matching, so an
# "Amazon Prime" voucher can collide with and get recommended for an
# ordinary physical-product Amazon purchase it can't actually discount — a
# real correctness risk (CLAUDE.md rule #1), not merely a is-it-a-subscription
# label. Other subscription-only BuyHatke brands (Discovery Plus, Zee5,
# FITPASS, AppyHigh Prime) have no such name collision — Gyftr's and
# Maximize's own audits keep those, so this does too.
_EXCLUDED_SUBSCRIPTION_SLUGS = {
    "amazon-prime-gift-card",
    "amazon-prime-12-months-gift-card",
    "amazon-prime-3-months-gift-card",
    "amazon-prime-lite-edition-gift-card",
    "amazon-prime-shopping-edition-gift-card",
}


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val) -> int | None:
    f = _to_float(val)
    return int(f) if f is not None else None


def _stack_limit(ar: dict, choice: dict) -> int | None:
    candidates = [
        _to_int(ar.get("maxVoucherPerOrder")),
        _to_int(choice.get("maxVouchersPerUserTransaction")),
    ]
    candidates = [c for c in candidates if c is not None]
    return min(candidates) if candidates else None


def _redemption_restrictions(terms: list[str]) -> list[str]:
    return [t for t in terms if any(m in t.lower() for m in _RESTRICTION_MARKERS)]


def _build_products(slug: str, choice: dict, scraped_at: str | None) -> list[dict]:
    ar = choice.get("amountRestrictions") or {}
    redemption_type = "Online" if choice.get("availableOnline") else "Offline"
    stack_limit = _stack_limit(ar, choice)
    value_cap = _to_float(ar.get("maxOrderAmount"))
    purchase_cap_per_txn = _to_float(choice.get("maxAmountPerUserTransaction"))
    status = "active" if choice.get("status") == "ACTIVE" else "inactive"
    source_url = f"https://buyhatke.com/gift-cards/{slug}"
    title = _clean_title(choice.get("title") or slug)

    common = {
        "source_url": source_url,
        "redemption_type": redemption_type,
        "stack_limit": stack_limit,
        "value_cap": value_cap,
        "purchase_cap_per_txn": purchase_cap_per_txn,
        "status": status,
        "last_scraped": scraped_at,
    }

    denoms_raw = ar.get("denominations")
    if not denoms_raw:
        # Custom-amount voucher — minAmount/maxAmount are sometimes null even
        # when a real range exists; minVoucherAmount/maxVoucherAmount are the
        # reliable fields.
        custom_min = _to_float(ar.get("minVoucherAmount")) or _to_float(ar.get("minAmount"))
        custom_max = _to_float(ar.get("maxVoucherAmount")) or _to_float(ar.get("maxAmount"))
        rate = _to_float(choice.get("brandDiscount")) or 0.0
        return [{
            "product_name": title,
            "denominations": [],
            "is_custom_denom": True,
            "custom_min": custom_min,
            "custom_max": custom_max,
            "discounts": {"UPI": rate},
            "best_payment_method": "UPI",
            "best_discount_pct": rate,
            **common,
        }]

    denoms = sorted({_to_int(d) for d in denoms_raw if _to_int(d) is not None})
    dis_map = choice.get("denominationDisMap") or {}
    flat_rate = _to_float(choice.get("brandDiscount")) or 0.0

    # Group denominations by their real rate (denominationDisMap), falling
    # back to the flat brandDiscount for any denomination the map doesn't
    # cover — this is exactly the Myntra ₹200-vs-₹250 case the user found.
    rate_groups: dict[float, list[int]] = {}
    for d in denoms:
        rate = _to_float(dis_map.get(str(d))) if dis_map else None
        if rate is None:
            rate = flat_rate
        rate_groups.setdefault(rate, []).append(d)

    products = []
    for rate, group_denoms in sorted(rate_groups.items(), key=lambda kv: kv[1][0]):
        products.append({
            "product_name": title,
            "denominations": sorted(group_denoms),
            "is_custom_denom": False,
            "custom_min": None,
            "custom_max": None,
            "discounts": {"UPI": rate},
            "best_payment_method": "UPI",
            "best_discount_pct": rate,
            **common,
        })
    return products


def normalize_brand(slug: str, rec: dict) -> dict | None:
    choices = rec.get("voucherChoices")
    if not choices:
        return None
    choice = choices[0]
    if choice.get("isCashback"):
        return None

    terms = choice.get("termsAndConditions") or []
    usage = choice.get("usageInstructions") or {}
    how_to_redeem_steps = list(usage.get("ONLINE") or []) + list(usage.get("OFFLINE") or [])

    products = _build_products(slug, choice, rec.get("scraped_at"))
    if not products:
        return None

    is_one_time_use = choice.get("isOneTimeUse")

    return {
        "brand_name": _clean_title(choice.get("title") or slug),
        "slug": slug,
        "source": "BuyHatke",
        "products": products,
        "description": None,
        "important_instructions_raw": "\n".join(terms) if terms else None,
        "how_to_redeem_steps": how_to_redeem_steps,
        "full_terms_and_conditions": "\n".join(terms) if terms else None,
        "redemption_restrictions": _redemption_restrictions(terms),
        "notes": None,
        "stack_limit_confidence": None,
        "can_club_with_offers": None,
        "one_time_use": bool(is_one_time_use) if is_one_time_use is not None else None,
    }


def main() -> None:
    with open(PROGRESS_FILE) as f:
        progress = json.load(f)

    master: dict[str, dict] = {}
    excluded_cashback: list[str] = []
    excluded_inactive: list[str] = []
    excluded_subscription: list[str] = []
    skipped_errors: list[str] = []

    for slug, rec in progress.items():
        if "error" in rec:
            skipped_errors.append(slug)
            continue
        choices = rec.get("voucherChoices")
        if not choices:
            skipped_errors.append(slug)
            continue
        choice = choices[0]
        if choice.get("isCashback"):
            excluded_cashback.append(slug)
            continue
        if slug in _EXCLUDED_SUBSCRIPTION_SLUGS:
            excluded_subscription.append(slug)
            continue
        # Not just a data-quality filter: about 1 in 5 brands sampled came
        # back "INACTIVE" (temporarily unavailable on BuyHatke, e.g. out of
        # stock with the underlying brand) rather than "ACTIVE" — recommending
        # one would send someone to buy a voucher they can't actually get.
        # Neither Gyftr's nor Maximize's build scripts filter on their own
        # status field at all (pre-existing gap, out of scope here), but
        # BuyHatke's status is a live, high-confidence signal worth acting on.
        if choice.get("status") != "ACTIVE":
            excluded_inactive.append(slug)
            continue
        normalized = normalize_brand(slug, rec)
        if normalized is not None:
            master[slug] = normalized

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(master, f, indent=2)

    with open(EXCLUDED_CASHBACK_LOG, "w") as f:
        json.dump(excluded_cashback, f, indent=2)
    with open(EXCLUDED_INACTIVE_LOG, "w") as f:
        json.dump(excluded_inactive, f, indent=2)
    with open(EXCLUDED_SUBSCRIPTION_LOG, "w") as f:
        json.dump(excluded_subscription, f, indent=2)

    print(f"Normalized {len(master)} brands -> {OUTPUT_PATH}")
    print(f"Excluded {len(excluded_cashback)} cashback-type brands -> {EXCLUDED_CASHBACK_LOG}: {excluded_cashback}")
    print(f"Excluded {len(excluded_inactive)} inactive brands -> {EXCLUDED_INACTIVE_LOG}")
    print(f"Excluded {len(excluded_subscription)} subscription-type brands -> {EXCLUDED_SUBSCRIPTION_LOG}: {excluded_subscription}")
    if skipped_errors:
        print(f"Skipped {len(skipped_errors)} brands with scrape errors: {skipped_errors}")


if __name__ == "__main__":
    main()
