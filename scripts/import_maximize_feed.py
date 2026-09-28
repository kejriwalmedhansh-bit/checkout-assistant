#!/usr/bin/env python3.11
"""Turn Maximize's own gift-card feed into the raw records the rest of the
refresh already reads — the same fields scrape_maximize() used to produce by
clicking through every page.

Why: clicking each payment method on each of ~410 pages took about three hours.
The page itself gets every one of those numbers from one call,
savemax.maximize.money/api/savemax/giftcard/details-max-coins, which answers
only a logged-in browser. So the collection is done in the user's logged-in
Chrome (the page's own answers are recorded as each card opens) and saved as
one JSON file of {giftCardId: {"status": ..., "text": <the feed's answer>}}.
This script reads that file.

Verified 2026-09-28 against the 2026-09-04 click-through, card by card: see
--compare.

  python3.11 scripts/import_maximize_feed.py FEED.json --compare   report only
  python3.11 scripts/import_maximize_feed.py FEED.json             write
"""
import argparse
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_voucher_terms import maximize_targets, save_out, untag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "voucher_terms_raw_maximize.json"

# The feed lists a method once per payment gateway ("Credit Card (Ccavenue)",
# "Credit Card (Razorpay)"); the page, and the app, show one "Credit Card", and
# that one is the first the feed lists: taking the first reproduced every
# 2026-09-04 click-through figure, taking the best overstated "CC on UPI".
METHOD_NAMES = {
    "upi": "UPI", "debit card": "Debit Card", "credit card": "Credit Card",
    "amazon pay": "Amazon pay", "cc on upi": "CC on UPI",
    "pay with rewards": "Pay With Rewards", "diners": "Diners Club",
    "diners club": "Diners Club", "wallets": "Wallets", "amex": "Amex",
}


def method_name(name: str) -> str:
    base = re.sub(r"\s*\(.*?\)\s*$", "", name or "").strip().lower()
    return METHOD_NAMES.get(base, (name or "").strip())


def saving_pct(m: dict) -> float:
    """What the shopper actually saves on this method: the instant discount less
    any surcharge the method adds, never below zero (a surcharge with no
    discount is a method nobody should be sent to, not a negative deal)."""
    return round(max((m.get("discount") or 0) - (m.get("surcharge") or 0), 0), 2)


def lines(value) -> str:
    """The feed gives terms and how-to steps as a list of sentences — the same
    sentences the page's pop-ups print one per line."""
    if isinstance(value, list):
        return "\n".join(t for t in (untag(v if isinstance(v, str) else json.dumps(v)) for v in value) if t)
    return untag(value)


def to_raw(d: dict) -> dict:
    denoms = [float(v) for v in re.findall(r"[\d.]+", str(d.get("denomination") or ""))]
    rates: dict[str, dict] = {}
    for m in d.get("paymentMethods") or []:
        name = method_name(m.get("name"))
        pct = saving_pct(m)
        if name not in rates:
            rates[name] = {"discount_pct": pct, "instant_offered": pct > 0,
                           "surcharge_pct": m.get("surcharge") or 0}
    terms, steps = lines(d.get("terms")), lines(d.get("howToRedeem"))
    ranged = d.get("type") == "range"
    return {
        "info_boxes": {b.get("title"): b.get("subtext") for b in d.get("shortInfo") or []
                       if b.get("title")},
        "full_terms": f"Terms & Conditions\n{terms}" if terms else "",
        "how_to_redeem": f"How To Redeem\n{steps}" if steps else "",
        "product_name": html.unescape(d.get("giftCardName") or "") or None,
        "denominations": [{"value": v} for v in denoms],
        "max_quantity_per_order": d.get("maxAllowedQuantity"),
        "instant_discount": rates.get("UPI") or {"discount_pct": 0.0, "instant_offered": False},
        "maxcoins_earn": ([{"pct": float(d["earnPercent"])}] if d.get("earnPercent") else []),
        "payment_methods_offered": list(rates),
        "payment_method_rates": rates,
        "custom_amount_min": d.get("minAmount") if ranged else None,
        "custom_amount_max": d.get("maxAmount") if ranged else None,
        "channel": d.get("channel"),
        "active": d.get("active"),
        "collected_via": "details-max-coins feed",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("feed")
    ap.add_argument("--compare", action="store_true", help="report against the current raw file, write nothing")
    args = ap.parse_args()

    feed = json.loads(Path(args.feed).read_text())
    old = json.loads(RAW.read_text())
    # Keep each listing under the key it already has: the terms manifest and the
    # read rules are keyed that way, and a new key would read as a new brand.
    key_by_url = {rec.get("url"): k for k, rec in old.items()}
    targets = {t["url"].rsplit("/", 1)[-1]: t for t in maximize_targets()}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out, stats, dead = {}, Counter(), []
    for gid, resp in feed.items():
        t = targets.get(str(gid))
        if not t:
            stats["id not in catalogue"] += 1
            continue
        key = key_by_url.get(t["url"]) or f"maximize:{t['slug']}"
        body = json.loads(resp["text"]) if resp.get("text") else {}
        if resp.get("status") != 200 or not body.get("data"):
            # 404 "Gift Card not found": listed in search, gone from sale.
            dead.append(t["brand_name"])
            out[key] = {**t, "scraped_at": now, "raw": {"load_incomplete": True,
                                                        "feed_status": resp.get("status")}}
            continue
        out[key] = {**t, "scraped_at": now, "raw": to_raw(body["data"])}
        stats["collected"] += 1

    print(dict(stats), f"| gone from sale: {len(dead)}")
    if args.compare:
        same = diff = 0
        examples = []
        for k, rec in out.items():
            o = (old.get(k) or {}).get("raw") or {}
            a = {m: v["discount_pct"] for m, v in (rec["raw"].get("payment_method_rates") or {}).items()}
            b = {m: v.get("discount_pct") for m, v in (o.get("payment_method_rates") or {}).items()
                 if isinstance(v, dict) and "discount_pct" in v}
            if not a or not b:
                continue
            if a == b:
                same += 1
            else:
                diff += 1
                if len(examples) < 12:
                    examples.append((rec["brand_name"], b, a))
        print(f"per-method rates identical to 2026-09-04: {same}, different: {diff}")
        for name, b, a in examples:
            print(f"  {name[:28]:30} then {b}\n  {'':30} now  {a}")
        return

    old.update(out)
    save_out(old, RAW)
    print(f"wrote {len(out)} listings -> {RAW.name}")


if __name__ == "__main__":
    main()
