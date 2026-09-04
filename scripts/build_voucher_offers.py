"""One standardized record per brand, per platform.

The three sites describe the same things in different words and different
places, so every downstream caller has been re-deriving them. This produces a
single shape for all three, and — where a platform simply does not state a
thing — says "not_stated" rather than leaving a blank that reads as "no".

Every rule keeps the wording it came from. A claim Dealo makes to a shopper
should be traceable to a sentence on the seller's own page, not to a guess made
here.

Rule names match scripts/extract_all_voucher_rules.py so the two agree.

  data/voucher_terms_raw_*.json  ->  data/voucher_offers.json
                                     data/voucher_offers_coverage.json
"""
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data"
OUT = RAW / "voucher_offers.json"
COVERAGE = RAW / "voucher_offers_coverage.json"

# The thirteen from extract_all_voucher_rules.py, so the two agree, plus
# validity, which the platforms state plainly and shoppers ask about.
RULES = ("works_online", "works_in_store", "one_time_use", "can_combine",
         "combines_with_store_offers", "max_cards_per_order", "ceiling_amount",
         "ceiling_period", "min_order_value", "max_spend_per_purchase",
         "works_on_sale_items", "excludes", "delivery_wait_days", "validity")

_spec = importlib.util.spec_from_file_location(
    "extract_all_voucher_rules", REPO / "scripts" / "extract_all_voucher_rules.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
extract_from_terms = _mod.extract_rules


# "Valid for partial redemption" is not a validity period, so match only a
# stated length of time.
VALIDITY_RE = re.compile(
    r"valid\s+(?:for|upto|up to|till|until)\s+[^.\n]{0,40}?"
    r"(?:day|days|week|weeks|month|months|year|years)[^.\n]{0,20}", re.I)
# Named exclusions — the brand or product a voucher will not buy. The generic
# "not on discounted items" case is works_on_sale_items and is handled already.
EXCLUDE_RE = re.compile(
    r"(?:cannot be redeemed (?:for|against)|not valid (?:for|on)|not applicable (?:for|on)|"
    r"excluding|except (?:for|on)?)\s+([^.\n;]{3,90})", re.I)
GENERIC_EXCLUSION = re.compile(
    r"discount|sale item|sale price|offer|promotion|cash|other voucher|gift card", re.I)


def fill_extras(rules: dict, terms: str, instructions: str) -> None:
    """Validity period and named exclusions: both stated plainly and both worth
    surfacing, neither covered by the shared extractor."""
    text = f"{terms}\n{instructions}"
    if rules["validity"]["value"] == "not_stated" and (m := VALIDITY_RE.search(text)):
        set_rule(rules, "validity", m.group(0).strip(), m.group(0))
    if rules["excludes"]["value"] in ([], None, "not_stated"):
        found, evidence = [], ""
        for m in EXCLUDE_RE.finditer(text):
            phrase = m.group(1).strip()
            if GENERIC_EXCLUSION.search(phrase) or len(phrase.split()) > 12:
                continue
            if phrase.lower() not in {f.lower() for f in found}:
                found.append(phrase)
            evidence = evidence or m.group(0)
        if found:
            set_rule(rules, "excludes", found[:8], evidence)


def fill_from_terms(rules: dict, terms: str, instructions: str) -> None:
    """The structured boxes are the better source and win where they exist; the
    terms fill the rest. Gyftr publishes no boxes at all, so without this it
    would report "not stated" for rules its own terms spell out."""
    if not (terms or instructions):
        return
    found = extract_from_terms(terms, instructions)
    for name, got in found.items():
        if name not in rules:
            continue
        empty = got["value"] in (None, "not_stated", [])
        # A rule with no quote behind it is a guess, and a guess about what a
        # shop will accept is worse than saying nothing. "up to 45% off on
        # vouchers" was being stored as a 45-voucher limit on 380 brands, with
        # no evidence recorded, because nothing required one.
        if not (got.get("evidence") or "").strip():
            continue
        if not empty and rules[name]["value"] in (None, "not_stated", []):
            rules[name] = {"value": got["value"],
                           "evidence": re.sub(r"\s+", " ", got.get("evidence") or "").strip()[:300]}


def blank_rules() -> dict:
    return {r: {"value": "not_stated", "evidence": ""} for r in RULES}


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def set_rule(rules: dict, name: str, value, evidence: str) -> None:
    rules[name] = {"value": value, "evidence": re.sub(r"\s+", " ", evidence).strip()[:300]}


def redeem_rules(rules: dict, phrase: str) -> None:
    """"used only online" / "only in-store" / "both online and in-store"."""
    low = phrase.lower()
    if "both" in low:
        set_rule(rules, "works_online", "yes", phrase)
        set_rule(rules, "works_in_store", "yes", phrase)
    elif "in-store" in low or "in store" in low:
        set_rule(rules, "works_online", "no", phrase)
        set_rule(rules, "works_in_store", "yes", phrase)
    elif "online" in low or "website" in low or "app" in low:
        set_rule(rules, "works_online", "yes", phrase)
        set_rule(rules, "works_in_store", "no", phrase)


# --------------------------------------------------------------------------

def from_gyftr(rec: dict) -> dict:
    raw = rec["raw"]
    page = raw.get("page_text") or ""
    denoms = raw.get("denominations") or []
    rules = blank_rules()

    # The platform's own flag, which beats reading it out of prose.
    flag = {"ON": ("yes", "no"), "OFF": ("no", "yes"), "B": ("yes", "yes")}.get(
        raw.get("redemption_type") or "")
    if flag:
        ev = f"redemption_type = {raw['redemption_type']}"
        set_rule(rules, "works_online", flag[0], ev)
        set_rule(rules, "works_in_store", flag[1], ev)

    # processing_charge_apply says the method is *subject* to the brand's
    # processing charge, not that a charge exists: it reads "Y" on 422 brands
    # while only six carry a non-zero charge. Taking the flag alone marked
    # nearly every card payment as fee-bearing when it costs nothing extra.
    charge = num(raw.get("processing_charge")) or 0.0
    methods = {}
    for name, m in (raw.get("payment_methods") or {}).items():
        pct = num(m.get("discount_pct"))
        if pct is None:
            continue
        applies = m.get("processing_charge_apply") == "Y" and charge > 0
        methods[name] = {"saving_pct": pct,
                         # A real fee eats the headline rate, so the best rate
                         # is not always the cheapest route.
                         "processing_fee": applies,
                         "processing_fee_pct": charge if applies else 0.0}

    return {
        # stock_left reads 0 on listings plainly on sale, so it says nothing.
        "available": bool(denoms) and "sold out" not in page.lower(),
        "methods": methods,
        "denominations": [{"value": d["value"]} for d in denoms if d.get("value")],
        "custom_amount": any((d.get("max_value") or 0) > 0 for d in denoms),
        "rules": rules,
        "terms": raw.get("full_terms") or "",
        "instructions": raw.get("important_instruction") or "",
        "cashback_only": False, "cashback_pct": None, "maxcoins_earn_pct": None,
    }


def from_buyhatke(rec: dict) -> dict:
    raw = rec["raw"]
    page = raw.get("page_text") or ""
    restrictions = raw.get("restrictions") or ""
    headline = raw.get("headline_discount") or ""
    # Cashback pays out in BuyHatke points, so it is never counted as a saving.
    is_cashback = "cashback" in headline.lower()
    pct = num(m.group(1)) if (m := re.search(r"([\d.]+)%", headline)) else None

    rules = blank_rules()
    if (m := re.search(r"Where to Redeem\?\s*\n\s*([^\n]+)", restrictions, re.I)):
        redeem_rules(rules, m.group(1))
    if (m := re.search(r"Multi-Use or Single Use\?\s*\n\s*([^\n]+)", restrictions, re.I)):
        line = m.group(1)
        set_rule(rules, "one_time_use", "yes" if re.search(r"only 1 time|single", line, re.I)
                 else "no", line)
    if (m := re.search(r"LIMIT:\s*(\d+)\s*PER TRANSACTION", page, re.I)):
        set_rule(rules, "max_cards_per_order", int(m.group(1)), m.group(0))
    if (m := re.search(r"Maximum purchase limit:\s*₹\s*([\d,]+)\s*per\s*(\w+)",
                       restrictions, re.I)):
        set_rule(rules, "ceiling_amount", num(m.group(1)), m.group(0))
        set_rule(rules, "ceiling_period", m.group(2).lower(), m.group(0))
    if (m := re.search(r"ACTIVE AFTER:\s*([^\n]+)", page, re.I)):
        set_rule(rules, "delivery_wait_days", m.group(1).strip(), m.group(0))

    denoms = []
    for d in raw.get("denominations") or []:
        e = {"value": d.get("value")}
        # A per-amount rate labelled CASHBACK is not a saving either.
        if d.get("discount_pct") is not None and d.get("label") != "CASHBACK":
            e["saving_pct"] = d["discount_pct"]
        denoms.append(e)

    return {
        "available": bool(raw.get("available")),
        # BuyHatke quotes one rate for the brand, not per payment method.
        "methods": ({} if is_cashback or pct is None else
                    {"any": {"saving_pct": pct, "processing_fee": None}}),
        "denominations": denoms,
        "custom_amount": bool(raw.get("custom_amount")),
        "rules": rules,
        "terms": raw.get("full_terms") or "",
        "instructions": raw.get("how_to_redeem") or "",
        "cashback_only": is_cashback,
        "cashback_pct": pct if is_cashback else None,
        "maxcoins_earn_pct": None,
    }


def from_maximize(rec: dict) -> dict:
    raw = rec["raw"]
    boxes = raw.get("info_boxes") or {}
    rules = blank_rules()

    if (v := boxes.get("Where to Redeem?")):
        redeem_rules(rules, v)
    if (v := boxes.get("Multi-Use or Single Use?")):
        set_rule(rules, "one_time_use",
                 "yes" if re.search(r"full balance in one go|single", v, re.I) else "no", v)
    if (v := boxes.get("Can the cards be clubbed?")):
        set_rule(rules, "can_combine", "no" if re.search(r"can'?t|cannot", v, re.I) else "yes", v)
    if (v := boxes.get("Can be clubbed with other offers?")):
        set_rule(rules, "combines_with_store_offers",
                 "no" if re.search(r"can'?t|cannot|no,", v, re.I) else "yes", v)
    if (v := boxes.get("Validity")):
        set_rule(rules, "validity", v, v)

    methods = {}
    for name, m in (raw.get("payment_method_rates") or {}).items():
        pct = num(m.get("discount_pct"))
        if pct is not None:
            methods[name] = {"saving_pct": pct, "processing_fee": None}

    denoms, seen = [], set()
    for d in raw.get("denominations") or []:
        v = d.get("value")
        if v and v not in seen:
            seen.add(v)
            denoms.append({"value": v})

    coins = raw.get("maxcoins_earn") or []
    return {
        # Maximize never prints an out-of-stock notice, so the amount picker is
        # the only signal, and a page that failed to load looks the same.
        "available": bool(denoms) and not raw.get("load_incomplete"),
        "methods": methods,
        "denominations": denoms,
        "custom_amount": "Custom" in (raw.get("page_text") or ""),
        "rules": rules,
        "terms": raw.get("full_terms") or "",
        "instructions": raw.get("how_to_redeem") or "",
        "cashback_only": False, "cashback_pct": None,
        # Paying full price to earn coins is not a saving; kept, never ranked on.
        "maxcoins_earn_pct": num(coins[0]["pct"]) if coins else None,
    }


READERS = {"gyftr": from_gyftr, "buyhatke": from_buyhatke, "maximize": from_maximize}


def main() -> None:
    out, coverage = {}, {}
    for source, reader in READERS.items():
        path = RAW / f"voucher_terms_raw_{source}.json"
        if not path.exists():
            print(f"{source:9} no raw file yet — skipped")
            continue

        rows = []
        for key, rec in json.loads(path.read_text()).items():
            if "error" in rec:
                continue
            offer = reader(rec)
            fill_from_terms(offer["rules"], offer["terms"], offer["instructions"])
            fill_extras(offer["rules"], offer["terms"], offer["instructions"])
            # Rank on the UPI rate, per the user's call. It is the rate most
            # shoppers get, and ranking on each platform's best method barely
            # moves the answer anyway — of 252 brands sold on more than one
            # platform, the two rules disagree on exactly one. Every method is
            # still stored: a card payer would be better served elsewhere on
            # 110 of those 252, which is a question for when Dealo knows how
            # the shopper pays.
            methods = offer["methods"]
            upi_key = next((k for k in ("UPI", "any") if k in methods), None)
            best = ((upi_key, methods[upi_key]) if upi_key else (None, None))
            offer.update({
                "source": source, "slug": rec["slug"], "brand_name": rec["brand_name"],
                "url": rec["url"], "collected_at": rec.get("scraped_at"),
                "best_saving_pct": best[1]["saving_pct"] if best[1] else None,
                "best_saving_method": best[0],
                "has_terms": bool(offer["terms"]),
            })
            # Best rate across every method, for the day Dealo asks how the
            # shopper pays. Never used for ranking today.
            offer["max_saving_pct"] = max(
                (m["saving_pct"] for m in methods.values()), default=None)
            # The one field a caller should gate on: in stock, and saving real
            # money today rather than points. A voucher at 0% is not shown at
            # all — the user's call, and right: it is a listing, not an offer.
            offer["recommendable"] = bool(
                offer["available"] and (offer["best_saving_pct"] or 0) > 0)
            out[key] = offer
            rows.append(offer)

        stated = Counter()
        for o in rows:
            for r in RULES:
                if o["rules"][r]["value"] != "not_stated":
                    stated[r] += 1
        coverage[source] = {
            "offers": len(rows),
            "available": sum(o["available"] for o in rows),
            "recommendable": sum(o["recommendable"] for o in rows),
            "with_terms": sum(o["has_terms"] for o in rows),
            "per_method_rates": sum(len(o["methods"]) > 1 for o in rows),
            "rules_stated": {r: stated[r] for r in RULES},
        }
        c = coverage[source]
        print(f"{source:9} {c['offers']:4} offers | {c['available']:4} in stock | "
              f"{c['recommendable']:4} recommendable | {c['with_terms']:4} with terms")

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    COVERAGE.write_text(json.dumps(coverage, indent=2) + "\n")
    print(f"\n-> {OUT.name} and {COVERAGE.name}")


if __name__ == "__main__":
    main()
