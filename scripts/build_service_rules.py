"""Write data/voucher_rules.json — what voucher_service.py actually reads.

The service already has the right shape and the right distinctions; what it had
was worse data, extracted by pattern matching. This regenerates that same file
from the read terms, so the logic is untouched and only the facts underneath
improve. Nothing in src/ changes.

Field names differ between the two, and the mapping is where the care is needed:

  service field            <- read field
  can_combine              <- max_vouchers_per_bill  (1 means no)
  max_cards_per_order      <- max_vouchers_per_bill  (a number, or absent if unlimited)
  combines_with_store_offers <- can_combine_with_store_offers
  works_on_sale_items      <- excludes, when it names discounted or sale items
  ceiling_amount / period  <- monthly_purchase_cap
  max_spend_per_purchase   <- max_spend_per_purchase, numbers only

A rule the terms do not state stays "not_stated", which the service already
treats as "no restriction known" rather than as permission.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OFFERS = REPO / "data" / "voucher_offers.json"
OUT = REPO / "data" / "voucher_rules.json"

# What each platform lets a shopper buy in one checkout. The service keys off
# checkout_model; the extra fields carry the detail behind it.
# What each platform's own checkout permits. This is the single source of truth
# for platform behaviour: the pricing code reads it from the generated
# voucher_rules.json rather than carrying its own copy, because two copies of
# one fact is how the wrong platform got recommended for a ₹29,999 Frido order.
#
# `vouchers_per_order` is now always a number or "unlimited" — never a word
# like "multiple", which cannot be reasoned about and which the code silently
# read as "no limit at all".
#
# `requires_brand_stacking` says whether buying several vouchers here is only
# useful when the BRAND itself permits combining them on one bill — the
# `can_combine` rule extracted from the seller's own terms. Buying four
# vouchers the shop will not accept together is not a saving.
PLATFORM_RULES = {
    # Ten of any ONE brand+denomination per cart — Gyftr's cart says "Same
    # voucher more than 10 quantity is not allowed!" and the product owner
    # confirmed it 2026-09-07. It is a per-line limit, not a cart limit: ten
    # ₹10,000 plus ten ₹2,000 plus ten ₹500 is a legal single order, and other
    # brands get their own ten each. The brand's own combining rule still
    # applies on top, and the stricter of the two wins.
    "gyftr": {"checkout_model": "multi_item", "vouchers_per_order": 10,
              "mixed_denominations": True, "mixed_brands": True,
              "requires_brand_stacking": True,
              "note": "Any mix of denominations and brands in one order, "
                      "up to ten of each brand-and-denomination."},
    # Four is the platform's own ceiling, confirmed by the product owner
    # 2026-09-07 and visible as "Max: 4" on every Maximize product page. It
    # applies only where the brand permits combining vouchers at all.
    "maximize": {"checkout_model": "single_item", "vouchers_per_order": 4,
                 "mixed_denominations": False, "mixed_brands": False,
                 "requires_brand_stacking": True,
                 "note": "Up to four vouchers per order, all the same denomination and brand, "
                         "and only where the brand allows vouchers to be combined."},
    # One per transaction whatever the denomination, so brand stacking never
    # comes into it: a single voucher needs nobody's permission to combine.
    "buyhatke": {"checkout_model": "single_item", "vouchers_per_order": 1,
                 "mixed_denominations": False, "mixed_brands": False,
                 "requires_brand_stacking": False,
                 "note": "One voucher per transaction, whatever the denomination."},
}

# Rules whose extracted answer is not supported by the sentence quoted beside
# it. Found by reading all 330 listings that answer "no" to can_combine
# (2026-09-08, at the product owner's request) — every rule Dealo states has to
# carry the seller's own words, and these six state something the words do not
# say. Corrected to "not_stated" rather than to "yes": the terms are silent on
# combining, which is a different thing from permitting it, and silence leaves
# the service on its existing fallback.
#
# Deliberately NOT corrected, because the sentence does support the answer for
# the purchase Dealo actually plans — an online one:
#   * "Up to 5 GV/GCs ... at the listed Pizza Hut stores. Only 1 ... on the
#     mobile app and website" and four others like it. Several in store, one
#     online. The online half is the half that applies.
#   * "For Flight Booking, Only One Gift Cards can be used ... Upto 3 ... for
#     Holiday Packages." One per flight booking, which is the common case.
# And left for a product decision rather than a data fix: the several listings
# whose terms say vouchers cannot be combined ON the bill but CAN be merged
# into one e-Pay balance or wallet first (Domino's, EatSure and its kitchens,
# Nykaa). Those are buyable in quantity; whether Dealo should send a shopper
# through a merge step is not a question the terms answer.
UNSUPPORTED_CAN_COMBINE = {
    "gyftr:beyoung":
        "Quotes \u201cCash on delivery cannot be clubbed with GV\u201d \u2014 about paying cash on delivery.",
    "gyftr:swiggy-food-discount-voucher":
        "Quotes \u201cOffer valid once per user per transaction\u201d \u2014 an offer's usage limit.",
    "buyhatke:devagabond-gift-card":
        "Quotes \u201cTwo coupon codes cannot be clubbed together\u201d \u2014 about coupon codes.",
    "buyhatke:marriott-dining-1-(in-store)-gift-card":
        "Quotes a single-use clause \u2014 says a card is spent in one go, not that two cannot be used.",
    "buyhatke:marriott-dining-2-(in-store)-gift-card":
        "Quotes a single-use clause \u2014 says a card is spent in one go, not that two cannot be used.",
    "maximize:amazon-prime-voucher---3-months-membership-550":
        "Quotes \u201cVoucher cannot be reused and only one can be applied per customer\u201d \u2014 per customer, and about reuse.",
}


def drop_unsupported(rules_by_listing):
    """Blank out an answer wherever its evidence does not support it.

    Both fields are mapped from the same extracted answer and so carry the same
    mistake: leaving max_cards_per_order's "1" behind would keep capping the
    plan at one voucher after the sentence behind it had gone. Written to be
    safe to run twice — each field is corrected on its own state, not on
    whether the other one has already been fixed.
    """
    for key, why in UNSUPPORTED_CAN_COMBINE.items():
        rules = (rules_by_listing.get(key) or {}).get("rules") or {}
        combines = rules.get("can_combine")
        if combines and combines.get("value") == "no":
            combines.update({"value": "not_stated", "evidence": "", "corrected": why})
        named = rules.get("max_cards_per_order")
        if named and named.get("value") == 1:
            named.update({"value": None, "evidence": "", "corrected": why})
    return rules_by_listing


SALE_WORDS = re.compile(r"discount|sale item|sale price|slashed|EOSS|full[- ]price", re.I)
NOT_STATED = {"value": "not_stated", "evidence": ""}


def num(x):
    if isinstance(x, (int, float)):
        return float(x)
    # A value like "Rs. 5,000 per day" carries its number; one like
    # "no value limit at retail stores" carries none, and a bare comma must not
    # be mistaken for one.
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(x or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def rule(value, evidence):
    return {"value": value, "evidence": evidence or ""}


# The user's rule: where a page states both a permission and a restriction for
# the same thing, the restriction stands. Discovery Plus says "There are no
# restrictions related to deals and discounts" in one place and "Gift Vouchers
# CANNOT be clubbed with existing offers" in another; reading picked the first
# and would have told a shopper to stack when the page says they cannot.
NO_CLUB_OFFERS = re.compile(
    r"[^.\n]{0,120}(?:cannot|can not|can't|not)\s+be\s+(?:clubbed|combined|used)"
    r"[^.\n]{0,60}(?:offer|promotion|discount|deal)[^.\n]{0,60}", re.I)
NO_CLUB_CARDS = re.compile(
    r"[^.\n]{0,120}(?:cannot|can not|can't|not)\s+be\s+(?:clubbed|combined)"
    r"[^.\n]{0,60}(?:voucher|gift card|gv|another card)[^.\n]{0,60}", re.I)


def tighten(out: dict, terms: str) -> None:
    """Downgrade a permission the same page contradicts."""
    if out["combines_with_store_offers"]["value"] == "yes":
        if m := NO_CLUB_OFFERS.search(terms):
            out["combines_with_store_offers"] = rule("no", m.group(0).strip())
    if out["can_combine"]["value"] == "yes":
        if m := NO_CLUB_CARDS.search(terms):
            out["can_combine"] = rule("no", m.group(0).strip())
            out["max_cards_per_order"] = rule(1, m.group(0).strip())


def convert(offer: dict) -> dict:
    src = offer.get("rules") or {}

    def get(name):
        return src.get(name) or {}

    out = {k: dict(NOT_STATED) for k in (
        "can_combine", "max_cards_per_order", "ceiling_amount", "ceiling_period",
        "one_time_use", "works_online", "works_in_store", "works_on_sale_items",
        "combines_with_store_offers", "min_order_value", "excludes",
        "max_spend_per_purchase", "delivery_wait_days", "spend_scope")}
    out["max_cards_per_order"] = {"value": None, "evidence": ""}
    out["excludes"] = {"value": [], "evidence": ""}

    per_bill = get("max_vouchers_per_bill")
    if per_bill.get("value") is not None:
        v, ev = per_bill["value"], per_bill.get("evidence", "")
        if v == "unlimited":
            out["can_combine"] = rule("yes", ev)
        elif isinstance(v, int):
            out["can_combine"] = rule("yes" if v > 1 else "no", ev)
            out["max_cards_per_order"] = rule(v, ev)
        else:
            # A limit that differs by product ("1 for flights, 3 for packages")
            # cannot be a number. Say nothing rather than pick one.
            out["can_combine"] = rule("not_stated", ev)

    for service_name, read_name in (
            ("one_time_use", "one_time_use"), ("works_online", "works_online"),
            ("works_in_store", "works_in_store"),
            ("combines_with_store_offers", "can_combine_with_store_offers"),
            ("min_order_value", "min_order_value"),
            # What the voucher may actually be spent on. Air India Ancillary
            # pays 18% and buys only seat selection and extra baggage; without
            # this the service cannot warn anyone buying a ticket.
            ("spend_scope", "spend_scope")):
        r = get(read_name)
        if r.get("value") not in (None, "not_stated"):
            out[service_name] = rule(r["value"], r.get("evidence", ""))

    ex = get("excludes")
    if ex.get("value"):
        out["excludes"] = rule(list(ex["value"]), ex.get("evidence", ""))
        # "discounted more than 30%" is a ceiling, not a ban on sale items:
        # the voucher works on ordinary and lightly discounted stock.
        if any(SALE_WORDS.search(str(e)) and "more than" not in str(e).lower()
               for e in ex["value"]):
            out["works_on_sale_items"] = rule("no", ex.get("evidence", ""))

    # The same fact lives under whichever heading the page happened to state it:
    # Scotch & Soda's "redeemed only against full priced merchandise" arrives as
    # a store-offers rule, not an exclusion, and mapping the fields one-to-one
    # dropped it. Any rule whose own sentence rules out discounted goods answers
    # this one.
    if out["works_on_sale_items"]["value"] == "not_stated":
        for name in ("can_combine_with_store_offers", "spend_scope"):
            r = get(name)
            ev = r.get("evidence") or ""
            if r.get("value") in ("no", None) or name == "spend_scope":
                if SALE_WORDS.search(ev) and r.get("value") not in (None, "not_stated"):
                    out["works_on_sale_items"] = rule("no", ev)
                    break

    cap = get("monthly_purchase_cap")
    if num(cap.get("value")) is not None:
        out["ceiling_amount"] = rule(num(cap["value"]), cap.get("evidence", ""))
        out["ceiling_period"] = rule("month", cap.get("evidence", ""))

    spend = get("max_spend_per_purchase")
    if num(spend.get("value")) is not None:
        out["max_spend_per_purchase"] = rule(num(spend["value"]), spend.get("evidence", ""))

    wait = get("delivery_wait")
    if wait.get("value") not in (None, "not_stated"):
        text = str(wait["value"])
        hours = re.search(r"(\d+)\s*h(?:ou)?rs?", text, re.I)
        days = re.search(r"(\d+)\s*days?", text, re.I)
        val = (int(days.group(1)) if days else
               round(int(hours.group(1)) / 24, 2) if hours else text)
        out["delivery_wait_days"] = rule(val, wait.get("evidence", ""))

    return out


def main() -> None:
    offers = json.loads(OFFERS.read_text())
    raw = {}
    for src in ("gyftr", "buyhatke", "maximize"):
        raw.update(json.loads((REPO / "data" / f"voucher_terms_raw_{src}.json").read_text()))
    out = {"_platform_rules": PLATFORM_RULES}
    for key, offer in offers.items():
        if offer.get("hidden_reason"):
            # A page carrying another merchant's terms states no rule we can
            # attribute to this brand.
            continue
        rules = convert(offer)
        r = raw.get(key, {}).get("raw", {})
        tighten(rules, " ".join(str(r.get(f) or "") for f in (
            "important_instruction", "full_terms", "faqs", "restrictions")))
        out[key] = {"brand_name": offer["brand_name"], "source": offer["source"],
                    "slug": offer["slug"], "rules": rules}
    drop_unsupported(out)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(out) - 1} listings -> {OUT.name}")


if __name__ == "__main__":
    main()
