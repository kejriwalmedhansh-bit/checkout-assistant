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
PLATFORM_RULES = {
    "gyftr": {"checkout_model": "multi_item", "vouchers_per_order": "unlimited",
              "mixed_denominations": True, "mixed_brands": True,
              "note": "Any mix of denominations and brands in one order."},
    "maximize": {"checkout_model": "single_item", "vouchers_per_order": "multiple",
                 "mixed_denominations": False, "mixed_brands": False,
                 "note": "Several vouchers per order, all the same denomination and brand."},
    "buyhatke": {"checkout_model": "single_item", "vouchers_per_order": 1,
                 "mixed_denominations": False, "mixed_brands": False,
                 "note": "One voucher per transaction."},
}

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
        "max_spend_per_purchase", "delivery_wait_days")}
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
            ("min_order_value", "min_order_value")):
        r = get(read_name)
        if r.get("value") not in (None, "not_stated"):
            out[service_name] = rule(r["value"], r.get("evidence", ""))

    ex = get("excludes")
    if ex.get("value"):
        out["excludes"] = rule(list(ex["value"]), ex.get("evidence", ""))
        if any(SALE_WORDS.search(str(e)) for e in ex["value"]):
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
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(out) - 1} listings -> {OUT.name}")


if __name__ == "__main__":
    main()
