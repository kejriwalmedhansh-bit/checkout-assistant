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
    "gyftr": {"multiple_vouchers_per_order": True, "must_be_same_denomination": False,
              "multiple_brands_per_order": True,
              "note": "Any mix of denominations, and different brands, in one order."},
    "maximize": {"multiple_vouchers_per_order": True, "must_be_same_denomination": True,
                 "multiple_brands_per_order": False,
                 "note": "Several vouchers per order, but all the same denomination."},
    "buyhatke": {"multiple_vouchers_per_order": True, "must_be_same_denomination": True,
                 "multiple_brands_per_order": False,
                 "note": "Several vouchers per order, but all the same denomination."},
}

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

    filled = flagged = 0
    for key, offer in offers.items():
        offer["platform_buying"] = PLATFORM_BUYING.get(offer["source"], {})

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
    print(f"per-bill answers filled from the combine sentence : {filled}")
    print(f"vouchers flagged 'confirm with cashier'           : {flagged}")
    stated = sum(1 for v in offers.values()
                 if v.get("rules", {}).get("max_vouchers_per_bill"))
    print(f"listings now stating a per-bill limit             : {stated}")


if __name__ == "__main__":
    main()
