"""Compare two extraction runs field by field.

Picking a model for this job shouldn't be a matter of taste. Run the same
brands through two models, then look at where they disagree: agreement is
cheap confidence, and every disagreement is a specific sentence a human can
settle in seconds — which is the whole point of making each answer carry its
quote.

    python3.11 scripts/compare_voucher_rules.py data/rules_a.json data/rules_b.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    a_path, b_path = sys.argv[1], sys.argv[2]
    a, b = load(a_path), load(b_path)

    shared = sorted(set(a) & set(b))
    print(f"comparing {len(shared)} listings\n")

    agree = disagree = 0
    for key in shared:
        ra, rb = a[key]["rules"], b[key]["rules"]
        diffs = []
        for field in sorted(set(ra) | set(rb)):
            va = (ra.get(field) or {}).get("value")
            vb = (rb.get(field) or {}).get("value")
            if va == vb:
                agree += 1
                continue
            disagree += 1
            diffs.append((field, va, vb,
                          (ra.get(field) or {}).get("evidence", ""),
                          (rb.get(field) or {}).get("evidence", "")))
        if diffs:
            print(f"── {a[key]['brand_name']} ({a[key]['source']})")
            for f, va, vb, ea, eb in diffs:
                print(f"   {f}")
                print(f"     A: {str(va):<12} {(ea or '(no quote)')[:78]}")
                print(f"     B: {str(vb):<12} {(eb or '(no quote)')[:78]}")
            print()

    total = agree + disagree
    if total:
        print(f"fields compared: {total}   agreed: {agree} ({agree/total:.0%})   "
              f"disagreed: {disagree}")
    print("\nEvery disagreement above is one sentence to read — the quote is next to it.")


if __name__ == "__main__":
    main()
