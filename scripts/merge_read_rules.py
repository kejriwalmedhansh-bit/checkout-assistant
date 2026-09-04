"""Fold the read rules into the standardized offer records.

The reading was done in 30 parallel passes, which is fast but drifts: the same
judgement was made differently in different chunks — a monthly wallet-loading
cap filed as a purchase limit in one and a spend limit in another, location
restrictions kept in one chunk's exclusions and dropped from another's. Those
are reconciled here rather than left as an inconsistency in the data.

Every value keeps the sentence it came from. A rule with no quote is dropped:
across the whole set the reading produced none, and it should stay that way.

  data/rules_chunks/out_*.json + data/voucher_offers.json
      -> data/voucher_offers.json (rules replaced)
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHUNKS = REPO / "data" / "rules_chunks"
OFFERS = REPO / "data" / "voucher_offers.json"

# A cap sentence that talks about using, spending or redeeming is not a limit on
# buying, whatever field the reader put it in.
SPEND_WORDS = re.compile(r"redeem|spend|utilis|utiliz|purchase (?:of|from) |transaction value"
                         r"|per day|per bill|order", re.I)
BUY_WORDS = re.compile(r"can be (?:purchas|bought|generat|add)|worth of gift cards?"
                       r"|cumulative gv value|added to the e-?pay", re.I)
LOCATION = re.compile(r"airport|factory outlet|outlet|store|mall|city|cities|lounge"
                      r"|terminal|kiosk", re.I)


def load_read() -> dict:
    """Prefer the merged two-pass readings when they exist.

    One pass misses a stated rule on about a third of listings, so a single
    reading is a fallback, not the intended input.
    """
    source = CHUNKS / "merged"
    if not any(source.glob("out_*.json")):
        source = CHUNKS
        print("no merged readings found — using the first pass alone")
    out = {}
    for p in sorted(source.glob("out_*.json")):
        out.update(json.loads(p.read_text()))
    return out


def norm_rules(rec: dict) -> dict:
    """One convention for all 30 passes."""
    quotes = rec.get("quotes") or {}
    r = dict(rec)

    # A monthly cap whose own sentence is about spending belongs on the spend
    # side, and vice versa. The quote decides, not the field it arrived in.
    cap = r.get("monthly_purchase_cap")
    cap_q = quotes.get("monthly_purchase_cap", "")
    if cap not in (None, "not_stated") and cap_q:
        if SPEND_WORDS.search(cap_q) and not BUY_WORDS.search(cap_q):
            if r.get("max_spend_per_purchase") in (None, "not_stated"):
                r["max_spend_per_purchase"] = cap
                quotes["max_spend_per_purchase"] = cap_q
            r["monthly_purchase_cap"] = "not_stated"
            quotes.pop("monthly_purchase_cap", None)

    # Location restrictions are as binding as product ones — a shopper turned
    # away at an airport store does not care which list it was on. Some passes
    # kept them, some dropped them; keep them, marked.
    fixed = []
    for item in r.get("excludes") or []:
        if not isinstance(item, str):
            continue
        if LOCATION.search(item) and not item.lower().startswith(("location:", "date:")):
            item = f"location: {item}"
        fixed.append(item)
    r["excludes"] = fixed
    r["quotes"] = quotes
    return r


def main() -> None:
    read = load_read()
    offers = json.loads(OFFERS.read_text())

    applied = dropped = 0
    fields = Counter()
    for key, rec in read.items():
        if key not in offers or "error" in rec:
            continue
        rec = norm_rules(rec)
        quotes = rec.get("quotes") or {}
        rules = {}
        for field, value in rec.items():
            if field in ("quotes", "_usage") or value in (None, "not_stated", [], ""):
                continue
            quote = quotes.get(field, "")
            if not quote:
                # Channel and redemption flags are read off a structured line
                # that the reader does not always quote; everything else must
                # carry its sentence or it does not go in.
                if field not in ("works_online", "works_in_store"):
                    dropped += 1
                    continue
            rules[field] = {"value": value, "evidence": quote}
            fields[field] += 1
        offers[key]["rules"] = rules
        offers[key]["rules_source"] = "read"
        applied += 1

    OFFERS.write_text(json.dumps(offers, indent=2, ensure_ascii=False) + "\n")
    print(f"offers updated : {applied} of {len(offers)}")
    print(f"claims dropped for having no quote : {dropped}")
    print("\nstated, by field:")
    for f, n in fields.most_common():
        print(f"  {f:32} {n:5}  ({round(100*n/applied)}%)")


if __name__ == "__main__":
    main()
