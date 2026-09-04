"""Apply the product decisions to the read rules.

These are the user's calls, applied once across the whole catalogue rather than
voucher by voucher:

1. Combining vouchers into the platform's balance IS the answer to "how many
   per bill". 148 listings were already read that way and 47 identical ones were
   left blank, because a sentence about a wallet does not look like a sentence
   about a bill. It is the same fact either way.
2. Where the platform's summary and the brand's terms disagree, the more
   restrictive of the two stands.
3. A voucher redeemed in a shop carries a warning to confirm with the cashier
   before buying. Terms describe what should happen; the person at the counter
   decides what does.

Platform buying rules are recorded here too — they are properties of the seller,
not of any voucher, and they decide whether a large purchase can be assembled at
all.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OFFERS = REPO / "data" / "voucher_offers.json"
RAW = REPO / "data"

# What each platform lets you buy in a single transaction. Gyftr takes any mix;
# the other two take several vouchers only at one denomination, so a large
# purchase has to be assembled from equal-sized cards or split across orders.
PLATFORM_BUYING = {
    # Gyftr: a real cart. Any mix of denominations, and different brands, in one
    # order — so a large purchase can be assembled exactly (20,000 + 10,000 +
    # 5,000) and paid for once.
    "gyftr": {
        "vouchers_per_order": "unlimited",
        "mixed_denominations": True,
        "mixed_brands": True,
        "note": "Any mix of denominations and brands in a single order.",
    },
    # Maximize: several vouchers per order, but all the same denomination and
    # the same brand — so a large purchase has to be built from equal-sized
    # cards (4 x 10,000), never an exact combination.
    "maximize": {
        "vouchers_per_order": "multiple",
        "mixed_denominations": False,
        "mixed_brands": False,
        "note": "Several vouchers per order, but all the same denomination and brand.",
    },
    # BuyHatke: one voucher per transaction, confirmed by the user's own live
    # testing. Whatever the merchant would accept at the till is therefore moot
    # here — Dealo can only ever send someone to BuyHatke for a purchase a
    # single voucher covers.
    "buyhatke": {
        "vouchers_per_order": 1,
        "mixed_denominations": False,
        "mixed_brands": False,
        "note": "One voucher per transaction. Use only when one voucher covers the bill.",
    },
}


# A page that publishes another merchant's terms cannot be trusted for any of
# its rules, and repeating them makes Dealo look like it does not know the
# product: a bookshop voucher does not have a BigBasket wallet or a BBdaily
# exclusion. The user's call is to hide these outright.
#
# Detected by the terms document, not by keyword. Plenty of legitimate pages
# name BigBasket in a list of brands — keying off the word hid 395 listings
# including TGIF and Pizza Hut. A listing is only foreign when it shares its
# ENTIRE terms text with other unrelated brands and that text is unmistakably
# one specific merchant's.
FOREIGN_MARKERS = re.compile(r"bbdaily|big\s?basket wallet|tata\s?neu coins", re.I)


def foreign_terms_keys(raw: dict) -> set:
    """Listings whose whole terms document belongs to a merchant they are not."""
    groups: dict[str, list] = {}
    for key, rec in raw.items():
        terms = re.sub(r"\s+", " ", (rec.get("raw", {}).get("full_terms") or "")).strip()
        if len(terms) < 200 or not FOREIGN_MARKERS.search(terms):
            continue
        groups.setdefault(terms, []).append((key, rec.get("brand_name", "")))
    out = set()
    for terms, members in groups.items():
        # If one of the brands sharing this document IS the merchant it
        # describes, the document is theirs and everyone else borrowed it —
        # but if none of them is, it is nobody's and all of them are wrong.
        if any("bigbasket" in re.sub(r"[^a-z]", "", b.lower()) for _, b in members):
            continue
        out.update(k for k, _ in members)
    return out


# "Valid for redemption only on products on discount up to 30%" is a ceiling on
# how deeply discounted an item may be, not a requirement that it be discounted
# at all. Read as the latter it inverts the rule: the voucher was recorded as
# working ONLY on sale stock, when in fact it works on ordinary stock and stops
# at steeply discounted items. The user caught this on the Samsonite page.
DISCOUNT_CEILING = re.compile(
    r"valid for redemption only on products on discount\s*up\s?to\s*(\d+)\s*%"
    r"[^.]{0,40}?(\d+)\s*%", re.I)


def fix_discount_ceiling(offer: dict) -> bool:
    rules = offer.get("rules") or {}
    scope = rules.get("spend_scope") or {}
    m = DISCOUNT_CEILING.search(scope.get("evidence") or "")
    if not m:
        return False
    brand = offer["brand_name"].lower()
    # The sentence names two brands and two ceilings, in order.
    limit = m.group(2) if "tourister" in brand else m.group(1)
    ev = scope["evidence"]
    del rules["spend_scope"]
    existing = (rules.get("excludes") or {}).get("value") or []
    rules["excludes"] = {"value": existing + [f"products discounted more than {limit}%"],
                         "evidence": ev}
    return True


COMBINE = re.compile(
    r"multiple\s+(?:gift\s+vouchers?|gvs?|gv/gc|e-?gvs?)[^.\n]{0,60}"
    r"(?:combin|club|add)[^.\n]{0,60}(?:e-?pay|balance|wallet)[^.\n]{0,40}", re.I)


def raw_text(rec: dict) -> str:
    r = rec.get("raw", {})
    return " ".join(str(r.get(f) or "") for f in (
        "important_instruction", "full_terms", "faqs", "checkout_instruction",
        "restrictions", "how_to_redeem"))


def main() -> None:
    offers = json.loads(OFFERS.read_text())
    raw = {}
    for src in ("gyftr", "buyhatke", "maximize"):
        raw.update(json.loads((RAW / f"voucher_terms_raw_{src}.json").read_text()))

    foreign = foreign_terms_keys(raw)
    filled = flagged = hidden = ceilings = 0
    for key, offer in offers.items():
        offer["platform_buying"] = PLATFORM_BUYING.get(offer["source"], {})

        if key in foreign:
            offer["available"] = False
            offer["recommendable"] = False
            offer["hidden_reason"] = "page publishes another merchant's terms"
            hidden += 1

        if fix_discount_ceiling(offer):
            ceilings += 1

        rules = offer.get("rules") or {}
        if offer.get("rules_source") == "read" and "max_vouchers_per_bill" not in rules:
            m = COMBINE.search(raw_text(raw.get(key, {})))
            if m:
                # Only fills a blank. A listing that states its own number keeps
                # it — Domino's says multiple GVs cannot be used in one bill and
                # also mentions the balance, and the specific number wins.
                rules["max_vouchers_per_bill"] = {
                    "value": "unlimited", "evidence": m.group(0).strip()}
                filled += 1

        # Terms say what should happen; the cashier decides what does. Anything
        # redeemed in a shop gets the warning, including cards that work both
        # ways, because that is where the shopper is exposed.
        in_store = rules.get("works_in_store", {}).get("value") == "yes"
        if in_store:
            offer["confirm_with_cashier"] = True
            flagged += 1
        offer["rules"] = rules

    OFFERS.write_text(json.dumps(offers, indent=2, ensure_ascii=False) + "\n")
    print(f"hidden for carrying another merchant's terms      : {hidden}")
    print(f"discount-ceiling rules corrected                  : {ceilings}")
    print(f"per-bill answers filled from the combine sentence : {filled}")
    print(f"vouchers flagged 'confirm with cashier'           : {flagged}")
    stated = sum(1 for v in offers.values()
                 if v.get("rules", {}).get("max_vouchers_per_bill"))
    print(f"listings now stating a per-bill limit             : {stated}")


if __name__ == "__main__":
    main()
