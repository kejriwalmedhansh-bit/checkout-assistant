"""Flatten the standardized offers into one CSV for the Google Sheet.

The Sheet reads this file from GitHub with IMPORTDATA, so committing it is the
upload — same arrangement as maximize_database.csv.

One row per listing, all three platforms together, so a brand sold in more than
one place can be compared on one screen. Every rule column carries the value;
the sentence behind it sits in the Evidence columns at the end, because a rule
that cannot be quoted should not be trusted and the reader should be able to
check.
"""
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OFFERS = REPO / "data" / "voucher_offers.json"
OUT = REPO / "voucher_offers.csv"

RULE_COLS = [
    ("works_online", "Works Online"),
    ("works_in_store", "Works In Store"),
    ("max_vouchers_per_bill", "Vouchers Per Bill"),
    ("partial_redemption", "Balance Carries Over"),
    ("one_time_use", "Single Use"),
    ("can_combine_with_store_offers", "Stacks With Store Offers"),
    ("spend_scope", "Can Only Buy"),
    ("excludes", "Will Not Buy"),
    ("validity", "Validity"),
    ("delivery_wait", "Wait Before Use"),
    ("min_order_value", "Min Order"),
    ("max_spend_per_purchase", "Max Spend"),
    ("monthly_purchase_cap", "Monthly Buying Cap"),
]
# The rules worth being able to check at a glance; quoting all thirteen would
# make the sheet unreadable.
EVIDENCE_FOR = ("max_vouchers_per_bill", "can_combine_with_store_offers", "spend_scope")


def cell(rule: dict | None) -> str:
    if not rule:
        return ""
    v = rule.get("value")
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return "" if v in (None, "not_stated") else str(v)


def main() -> None:
    offers = json.loads(OFFERS.read_text())
    rows = []
    for offer in offers.values():
        rules = offer.get("rules") or {}
        denoms = [d["value"] for d in offer.get("denominations") or [] if d.get("value")]
        methods = offer.get("methods") or {}
        row = {
            "Brand": offer["brand_name"],
            "Platform": offer["source"],
            "URL": offer["url"],
            "In Stock": "yes" if offer.get("available") else "no",
            "Recommend": "yes" if offer.get("recommendable") else "no",
            "Saving % (UPI)": offer.get("best_saving_pct"),
            "Best Saving % (any method)": offer.get("max_saving_pct"),
            "Saving By Method": " | ".join(
                f"{m}: {d['saving_pct']}%" + (" +fee" if d.get("processing_fee") else "")
                for m, d in sorted(methods.items())),
            "Denominations": " / ".join(str(int(d)) if float(d).is_integer() else str(d)
                                        for d in denoms),
            "Custom Amount": "yes" if offer.get("custom_amount") else "no",
            "Confirm With Cashier": "yes" if offer.get("confirm_with_cashier") else "",
            "Cashback Only": "yes" if offer.get("cashback_only") else "",
            "MaxCoins Instead %": offer.get("maxcoins_earn_pct") or "",
            "Order: Mixed Denominations": (
                "yes" if (offer.get("platform_buying") or {}).get(
                    "multiple_vouchers_per_order")
                and not (offer.get("platform_buying") or {}).get("must_be_same_denomination")
                else "same denomination only"),
        }
        for key, label in RULE_COLS:
            row[label] = cell(rules.get(key))
        for key in EVIDENCE_FOR:
            row[f"Evidence: {dict(RULE_COLS)[key]}"] = (rules.get(key) or {}).get("evidence", "")
        row["In Store Differs"] = " | ".join(
            f"{dict(RULE_COLS).get(k, k)}={r['in_store_value']}"
            for k, r in rules.items() if "in_store_value" in r)
        rows.append(row)

    rows.sort(key=lambda r: (r["Brand"].lower(), r["Platform"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows, {len(rows[0])} columns -> {OUT.name}")


if __name__ == "__main__":
    main()
