"""Combine the two independent readings of every listing.

A measured sample put two readings at 88% agreement over 650 field comparisons —
and, importantly, they never stated *different* values for the same field. The
disagreement is entirely about whether a reading notices a rule at all: a third
of listings had a rule stated plainly that one pass walked past. So the two
passes are combined rather than one being chosen:

  one silent, one states it   ->  take the stated rule; this is the coverage the
                                  second pass was run for
  both state the same thing   ->  keep it
  both state different things ->  the more restrictive wins, per the user's rule.
                                  Being told "no" and finding it works costs the
                                  shopper nothing; the reverse strands them at
                                  the till.

Writes data/rules_chunks/merged/ for merge_read_rules.py to consume.
"""
import json
import re
from collections import Counter
from pathlib import Path

CHUNKS = Path(__file__).resolve().parent.parent / "data" / "rules_chunks"
OUT = CHUNKS / "merged"

# Which way each field gets stricter. A shopper refused at the counter is the
# expensive failure, so "stricter" always means the answer that promises less.
STRICTER = {
    "works_online": ["no", "yes"],
    "works_in_store": ["no", "yes"],
    "one_time_use": ["yes", "no"],          # single use is the tighter rule
    "partial_redemption": ["no", "yes"],    # losing the balance is the tighter rule
    "can_combine_with_store_offers": ["no", "yes"],
}
NUMERIC_LOWER_IS_STRICTER = ("max_vouchers_per_bill", "max_spend_per_purchase",
                             "monthly_purchase_cap")
NUMERIC_HIGHER_IS_STRICTER = ("min_order_value",)
BLANK = (None, "not_stated", "", [], {})


def blank(v):
    return v in BLANK or (isinstance(v, str) and v.strip().lower() == "not_stated")


def as_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        if v.strip().lower() == "unlimited":
            return float("inf")
        # "unlimited in physical stores; 1 on the website" — the online figure is
        # the one Dealo needs, and it is the one after the channel word.
        m = re.search(r"(\d[\d,]*)\s*(?:on|via)?\s*(?:the\s*)?(?:website|app|online)", v, re.I)
        if m:
            return float(m.group(1).replace(",", ""))
        m = re.search(r"\d[\d,]*", v)
        if m:
            return float(m.group(0).replace(",", ""))
    return None


def pick(field, a, b, stats):
    """a is the first reading, b the second. Either may be blank."""
    av, bv = a.get(field), b.get(field)
    aq = (a.get("quotes") or {}).get(field, "")
    bq = (b.get("quotes") or {}).get(field, "")

    if blank(av) and blank(bv):
        return None, ""
    if blank(av):
        stats["gained from second reading"] += 1
        return bv, bq
    if blank(bv):
        stats["kept from first reading"] += 1
        return av, aq

    if field == "excludes":
        # More exclusions is the stricter answer, and the two readings phrase
        # them differently, so keep both sets rather than choosing.
        seen, merged = set(), []
        for item in list(av) + list(bv):
            k = re.sub(r"[^a-z0-9]", "", str(item).lower())
            if k and k not in seen:
                seen.add(k)
                merged.append(item)
        stats["exclusions pooled"] += 1
        return merged, aq or bq

    if str(av).strip().lower() == str(bv).strip().lower():
        stats["both readings agree"] += 1
        return av, aq or bq

    if field in STRICTER:
        order = STRICTER[field]
        ai = order.index(str(av).lower()) if str(av).lower() in order else 99
        bi = order.index(str(bv).lower()) if str(bv).lower() in order else 99
        stats["conflict — stricter wins"] += 1
        return (av, aq) if ai <= bi else (bv, bq)

    if field in NUMERIC_LOWER_IS_STRICTER or field in NUMERIC_HIGHER_IS_STRICTER:
        an, bn = as_number(av), as_number(bv)
        if an is not None and bn is not None:
            stats["conflict — stricter wins"] += 1
            lower_wins = field in NUMERIC_LOWER_IS_STRICTER
            if (an <= bn) == lower_wins:
                return av, aq
            return bv, bq

    # Wording differences on descriptive fields (validity, spend_scope, waits):
    # neither is stricter, so keep the fuller statement.
    stats["wording differs — fuller kept"] += 1
    return (av, aq) if len(str(av)) >= len(str(bv)) else (bv, bq)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    stats, listings = Counter(), 0
    for first_path in sorted(CHUNKS.glob("out_0*.json")):
        n = first_path.stem.split("_")[1]
        second_path = CHUNKS / f"out2_{n}.json"
        first = json.loads(first_path.read_text())
        second = json.loads(second_path.read_text()) if second_path.exists() else {}
        if not second:
            print(f"  chunk {n}: no second reading — first reading used as is")

        merged = {}
        for key, a in first.items():
            b = second.get(key, {})
            fields = set(a) | set(b)
            fields.discard("quotes")
            rec, quotes = {}, {}
            for f in sorted(fields):
                v, q = pick(f, a, b, stats)
                if v is not None:
                    rec[f] = v
                    if q:
                        quotes[f] = q
            rec["quotes"] = quotes
            merged[key] = rec
            listings += 1
        (OUT / f"out_{n}.json").write_text(
            json.dumps(merged, indent=1, ensure_ascii=False))

    print(f"\n{listings} listings merged -> {OUT}")
    for k, v in stats.most_common():
        print(f"  {v:6}  {k}")


if __name__ == "__main__":
    main()
