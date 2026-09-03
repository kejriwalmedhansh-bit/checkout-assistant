"""Turn the three raw term dumps into one comparable offer per brand.

The raw files keep whatever each platform prints. This step applies the rules
that decide what Dealo may actually recommend, in one place, so no downstream
caller has to remember them:

  1. Cashback is not a saving. BuyHatke's "0.88% CASHBACK" pays out in BuyHatke
     points and Maximize's MaxCoins route earns coins for paying full price.
     Neither lowers what the shopper hands over today, so neither counts toward
     saving_pct — both are still recorded, under a separate field, because the
     shopper may still want to know.
  2. Nothing out of stock is recommendable, however good its headline rate.
  3. The saving is per payment method, never one number per brand, and the
     method with the best rate is not always the cheapest once Gyftr's
     processing charge on cards is counted.

Written by scrape_voucher_terms.py -> data/voucher_offers.json
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data"
OUT = RAW / "voucher_offers.json"


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def from_gyftr(rec: dict) -> dict:
    raw = rec["raw"]
    page = raw.get("page_text") or ""
    denoms = raw.get("denominations") or []
    # stock_left reads 0 on nearly every listing including ones plainly on sale,
    # so it says nothing; the sold-out banner is the honest signal.
    available = bool(denoms) and "sold out" not in page.lower()

    methods = {}
    for name, m in (raw.get("payment_methods") or {}).items():
        pct = num(m.get("discount_pct"))
        if pct is None:
            continue
        methods[name] = {"saving_pct": pct,
                         # A fee on this method eats into the headline rate, so
                         # the best-looking rate is not always the cheapest.
                         "processing_fee": m.get("processing_charge_apply") == "Y"}
    return {"available": available, "methods": methods,
            "denominations": [{"value": d.get("value")} for d in denoms if d.get("value")],
            "cashback_only": False}


def from_buyhatke(rec: dict) -> dict:
    raw = rec["raw"]
    headline = raw.get("headline_discount") or ""
    is_cashback = "cashback" in headline.lower()
    pct = num(m.group(1)) if (m := re.search(r"([\d.]+)%", headline)) else None
    denoms = []
    for d in raw.get("denominations") or []:
        e = {"value": d.get("value")}
        if d.get("discount_pct") is not None and d.get("label") != "CASHBACK":
            e["saving_pct"] = d["discount_pct"]
        denoms.append(e)
    return {"available": bool(raw.get("available")),
            # BuyHatke quotes one rate for the whole brand, not per method.
            "methods": ({} if is_cashback or pct is None else {"any": {"saving_pct": pct}}),
            "denominations": denoms,
            "cashback_only": is_cashback,
            "cashback_pct": pct if is_cashback else None}


def from_maximize(rec: dict) -> dict:
    raw = rec["raw"]
    methods = {}
    for name, m in (raw.get("payment_method_rates") or {}).items():
        pct = num(m.get("discount_pct"))
        if pct is not None:
            methods[name] = {"saving_pct": pct}
    coins = raw.get("maxcoins_earn") or []
    denoms = []
    seen = set()
    for d in raw.get("denominations") or []:
        v = d.get("value")
        if v and v not in seen:
            seen.add(v)
            denoms.append({"value": v})
    # Maximize never prints an out-of-stock notice, so the amount picker is the
    # only signal: no amounts means either nothing on sale or a page that did
    # not finish loading, and neither is safe to recommend.
    return {"available": bool(denoms),
            "methods": methods,
            "denominations": denoms,
            "cashback_only": False,
            # Paying full price to earn coins is not a saving; kept separately.
            "maxcoins_earn_pct": num(coins[0]["pct"]) if coins else None}


READERS = {"gyftr": from_gyftr, "buyhatke": from_buyhatke, "maximize": from_maximize}


def main() -> None:
    out = {}
    for source, reader in READERS.items():
        path = RAW / f"voucher_terms_raw_{source}.json"
        if not path.exists():
            print(f"{source}: no raw file yet, skipped")
            continue
        data = json.loads(path.read_text())
        for key, rec in data.items():
            if "error" in rec:
                continue
            offer = reader(rec)
            best = max((m["saving_pct"] for m in offer["methods"].values()), default=None)
            offer.update({
                "source": source, "slug": rec["slug"], "brand_name": rec["brand_name"],
                "url": rec["url"],
                "best_saving_pct": best,
                # The single field a caller should gate on.
                "recommendable": bool(offer["available"] and best),
            })
            out[key] = offer

        live = [o for o in out.values() if o["source"] == source]
        print(f"{source:9} {len(live):4} offers | {sum(o['recommendable'] for o in live):4} recommendable"
              f" | {sum(o['cashback_only'] for o in live):3} cashback-only (excluded)")

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
