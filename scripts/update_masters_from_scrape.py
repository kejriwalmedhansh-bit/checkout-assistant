"""Refresh the price side of the master files from the latest scrape.

The rules already flow through build_service_rules.py. The money does not: the
pipeline reads discounts, denominations and stock from db/*_master.json, which
were last built before this scrape. So Dealo was quoting September 2nd's rates
alongside September 4th's rules.

Only the fields the scrape actually re-measures are touched — discounts,
denominations, custom-amount range, stack limit, status. Everything else the
masters carry (value caps, purchase caps, redemption restrictions, descriptions)
is left exactly as it was, because this scrape does not measure it and a blank
would be read as "no restriction".

Matching is by source_url, which both sides carry and which survives a brand
being renamed.

  --dry-run   report what would change, write nothing
"""
import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OFFERS = DATA / "voucher_offers.json"
SOURCES = ("gyftr", "buyhatke", "maximize")


def as_int(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def stack_limit_from(offer: dict):
    """max_vouchers_per_bill, as a number the pipeline can use. "unlimited" is
    left as None — the pipeline reads None as no limit, which is what it means."""
    rule = (offer.get("rules") or {}).get("max_vouchers_per_bill") or {}
    v = rule.get("value")
    if v in (None, "not_stated"):
        return "keep"          # say nothing rather than clear a known limit
    if isinstance(v, str) and v.strip().lower() == "unlimited":
        return None
    n = as_int(v)
    return n if n is not None else "keep"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    offers = json.loads(OFFERS.read_text())
    by_url = {o["url"]: o for o in offers.values()}
    # Gyftr's master carries no source_url at all, so it is matched on the slug
    # that keys both sides. The other two match on URL, which survives a brand
    # being renamed.
    by_slug = {(o["source"], o["slug"]): o for o in offers.values()}
    scraped_at = max((o.get("collected_at") or "")[:10] for o in offers.values())

    for source in SOURCES:
        path = DATA / f"{source}_master.json"
        master = json.loads(path.read_text())
        stats = Counter()
        rate_moves = []

        for slug, entry in master.items():
            for product in entry.get("products") or []:
                offer = (by_url.get(product.get("source_url"))
                         or by_slug.get((source, slug)))
                if not offer:
                    stats["no match in the new scrape"] += 1
                    continue
                stats["matched"] += 1

                # A BuyHatke brand whose rate varies by amount is modelled in
                # the master as several products, one per denomination band —
                # VROTT carries 32.89% and 46.73% under one brand. Stamping the
                # brand's best rate on every product would overstate the cheaper
                # band, so each product takes the rate for the amounts it holds.
                priced = {d["value"]: d["saving_pct"]
                          for d in (offer.get("denominations") or [])
                          if d.get("saving_pct") is not None}
                own = [priced[v] for v in (product.get("denominations") or [])
                       if v in priced]
                if own and len(offer.get("methods") or {}) == 1 and "any" in offer["methods"]:
                    new_rates = {"UPI": max(own)}
                else:
                    new_rates = {m: d["saving_pct"]
                                 for m, d in (offer.get("methods") or {}).items()}
                if new_rates and new_rates != product.get("discounts"):
                    old_best = product.get("best_discount_pct")
                    product["discounts"] = new_rates
                    best = max(new_rates.items(), key=lambda kv: kv[1])
                    product["best_payment_method"], product["best_discount_pct"] = best
                    stats["rates updated"] += 1
                    if old_best is not None and abs((best[1] or 0) - old_best) >= 1:
                        rate_moves.append((offer["brand_name"], old_best, best[1]))

                denoms = [as_int(d["value"]) for d in offer.get("denominations") or []
                          if d.get("value")]
                denoms = sorted({d for d in denoms if d})
                if denoms and denoms != product.get("denominations"):
                    product["denominations"] = denoms
                    stats["denominations updated"] += 1

                if offer.get("custom_amount") is not None:
                    product["is_custom_denom"] = bool(offer["custom_amount"])

                limit = stack_limit_from(offer)
                if limit != "keep" and limit != product.get("stack_limit"):
                    product["stack_limit"] = limit
                    stats["stack limit updated"] += 1

                # A listing hidden for carrying another brand's terms, or gated
                # behind a loyalty membership, must not be sold.
                want = "active" if offer.get("recommendable") else "inactive"
                if product.get("status") != want:
                    product["status"] = want
                    stats[f"marked {want}"] += 1

                product["last_scraped"] = scraped_at

        print(f"\n{source}")
        for k, v in stats.most_common():
            print(f"  {v:5}  {k}")
        if rate_moves:
            rate_moves.sort(key=lambda r: -abs(r[2] - r[1]))
            print("  biggest rate moves:")
            for b, o, n in rate_moves[:5]:
                print(f"     {b[:32]:34} {o}% -> {n}%")
        if not args.dry_run:
            path.write_text(json.dumps(master, indent=2, ensure_ascii=False) + "\n")

    print("\n--dry-run: nothing written" if args.dry_run else "\nmasters updated")


if __name__ == "__main__":
    main()
