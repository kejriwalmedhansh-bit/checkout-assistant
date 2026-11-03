#!/usr/bin/env python3
"""Builds react/src/data/shopPages.json: one entry per shop page at
/brands/<slug>/ — the pages Google sends people to when they search
"<shop> gift card discount".

Each entry carries today's rate from every seller side by side (Dealo's own
voucher through Hubble, then Gyftr, Maximize and BuyHatke), the cheapest
marked, plus the fine print the voucher data knows (online or in store,
UPI vs card rate, single- or multi-use, what the voucher cannot buy, how to
redeem). The live page and scripts/prerender.mjs both read this file, so
the static HTML a crawler sees and the page a visitor sees say the same
thing.

Partner rates come from the three master files the voucher refresh keeps.
Dealo's own rate comes from the live backend (Hubble's catalogue has no
rates in the repo; the production keys live only on the server), so run
this with the network on. A shop whose Hubble lookup fails keeps its last
known Hubble rate from the previous shopPages.json.

Which shops: SHOPS below — the ones people search most on Dealo
(Mixpanel, 90 days to 3 Nov 2026) plus the big names deal hunters search
Google for. A shop makes it onto a page only when some seller gives at
least MIN_PCT, or it already had a hand-written page in brandDeals.js.

Run after every voucher refresh (see VOUCHER_REFRESH.md):
    python3 scripts/build_shop_pages.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "react" / "src" / "data" / "shopPages.json"
API = "https://dealo-backend.onrender.com"
MIN_PCT = 3.0
CURATED = {"amazon", "flipkart", "myntra", "croma", "reliance-digital", "ajio"}

# (slug, display name, extra names the sellers list it under). Exact
# normalized-name matching only, same rule as build_all_brand_deals.py:
# a sibling like "Myntra LUXE" or "Zomato (1 Day Wait)" never merges in.
SHOPS: list[tuple[str, str, list[str]]] = [
    ("myntra", "Myntra", []),
    ("ajio", "AJIO", []),
    ("nykaa", "Nykaa", []),
    ("nykaa-fashion", "Nykaa Fashion", []),
    ("zomato", "Zomato", []),
    ("swiggy", "Swiggy", []),
    ("amazon", "Amazon", ["Amazon Pay", "Amazon Shopping"]),
    ("flipkart", "Flipkart", []),
    ("croma", "Croma", []),
    ("reliance-digital", "Reliance Digital", []),
    ("makemytrip", "MakeMyTrip", ["MakeMyTrip Flights", "MakeMyTrip Hotels"]),
    ("yatra", "Yatra", ["Yatra Flights", "Yatra Hotels"]),
    ("cleartrip", "Cleartrip", []),
    ("pvr", "PVR", ["PVR Cinemas", "PVR INOX"]),
    ("bookmyshow", "BookMyShow", []),
    ("uber", "Uber", []),
    ("bigbasket", "BigBasket", []),
    ("blinkit", "Blinkit", []),
    ("zepto", "Zepto", []),
    ("tata-cliq", "Tata CLiQ", ["Tata CLiQ Fashion"]),
    ("pepperfry", "Pepperfry", []),
    ("ikea", "IKEA", []),
    ("urban-ladder", "Urban Ladder", []),
    ("dominos", "Domino's", ["Dominos", "Domino's Pizza"]),
    ("pizza-hut", "Pizza Hut", []),
    ("kfc", "KFC", []),
    ("subway", "Subway", []),
    ("starbucks", "Starbucks", []),
    ("lifestyle", "Lifestyle", []),
    ("westside", "Westside", []),
    ("shoppers-stop", "Shoppers Stop", []),
    ("decathlon", "Decathlon", []),
    ("puma", "PUMA", []),
    ("skechers", "Skechers", []),
    ("bata", "Bata", []),
    ("lenskart", "Lenskart", []),
    ("boat", "boAt", []),
    ("titan", "Titan", []),
    ("firstcry", "FirstCry", []),
    ("netmeds", "Netmeds", []),
    ("jockey", "Jockey", []),
    ("airbnb", "Airbnb", []),
]

SOURCES = [("gyftr", "Gyftr"), ("maximize", "Maximize"), ("buyhatke", "BuyHatke")]
_SUFFIX = re.compile(r"(egiftcard|giftcard|egiftvoucher|giftvoucher|evoucher|voucher|ecard|online)$")


def norm(name: str | None) -> str:
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return _SUFFIX.sub("", n)


def load(source: str) -> dict:
    with open(DATA / f"{source}_master.json") as f:
        return json.load(f)


def partner_row(source: str, label: str, brand: dict, slug: str) -> dict | None:
    products = [p for p in brand.get("products") or [] if (p.get("status") or "active") == "active"]
    if not products:
        return None
    best = max(products, key=lambda p: p.get("best_discount_pct") or 0)
    pct = best.get("best_discount_pct")
    if not pct:
        return None
    url = best.get("source_url")
    if url:
        url = quote(url, safe="/:")
    elif source == "gyftr":
        url = f"https://www.gyftr.com/{slug}"
    if not url:
        return None
    discounts = best.get("discounts") or {}
    rtype = (best.get("redemption_type") or "").lower()
    denoms = best.get("denominations") or []
    return {
        "source": source,
        "label": label,
        "pct": float(pct),
        "upi_pct": discounts.get("UPI"),
        "card_pct": discounts.get("Credit Card"),
        "url": url,
        "online": "online" in rtype or "both" in rtype or rtype == "",
        "offline": "offline" in rtype or "store" in rtype or "both" in rtype,
        "denominations": sorted({int(d) for d in denoms if isinstance(d, (int, float))})[:8],
        "typed": bool(best.get("is_custom_denom")),
        "typed_min": best.get("custom_min") or best.get("typed_min"),
        "typed_max": best.get("custom_max") or best.get("typed_max"),
        "stack_limit": best.get("stack_limit"),
        "value_cap": best.get("value_cap"),
    }


def hubble_rate(name: str) -> dict | None:
    """Dealo's own rate from the live backend; None when Hubble doesn't sell it
    or the server can't be reached."""
    try:
        url = f"{API}/hubble/brand?" + urllib.parse.urlencode({"merchant": name})
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except Exception as exc:  # noqa: BLE001 — a missing rate must not stop the build
        print(f"  hubble {name}: {exc}", file=sys.stderr)
        return {"error": True}
    b = data.get("brand") if data.get("available") else None
    if not b or not b.get("discount_pct"):
        return None
    return {
        "pct": float(b["discount_pct"]),
        "brand_name": b.get("brand_name") or name,
        "in_store": bool(b.get("in_store")),
        "cards": b.get("cards") or [],
        "min_amount": b.get("min_amount"),
        "max_amount": b.get("max_amount"),
        "typed": bool(b.get("typed")),
    }


def pick_terms(brands: list[dict]) -> dict:
    """Fine print from whichever seller states it; sellers agree far more
    often than they differ, and a stated value beats a blank."""
    steps: list[str] = []
    restrictions: list[str] = []
    one_time = None
    can_club = None
    for b in brands:
        if not steps and b.get("how_to_redeem_steps"):
            steps = [s for s in b["how_to_redeem_steps"] if isinstance(s, str)][:4]
        for r in b.get("redemption_restrictions") or []:
            # Short, named exclusions only ("Gold & Silver coins"), never a
            # numbered clause copied out of the terms.
            if isinstance(r, str) and r not in restrictions and 3 < len(r) < 70 and not re.match(r"^\s*\d", r) and "valid" not in r.lower():
                restrictions.append(r.strip().rstrip("."))
        if one_time is None and b.get("one_time_use") is not None:
            one_time = bool(b["one_time_use"])
        if can_club is None and b.get("can_club_with_offers") is not None:
            can_club = bool(b["can_club_with_offers"])
    return {"steps": steps, "restrictions": restrictions[:3], "multiUse": None if one_time is None else not one_time, "canClub": can_club}


def main() -> None:
    masters = {src: load(src) for src, _ in SOURCES}
    previous = {}
    if OUT.exists():
        previous = {s["slug"]: s for s in json.load(open(OUT))}

    with ThreadPoolExecutor(6) as ex:
        hubble = dict(zip([s[0] for s in SHOPS], ex.map(lambda s: hubble_rate(s[1]), SHOPS)))

    pages = []
    for slug, name, aliases in SHOPS:
        wanted = {norm(name)} | {norm(a) for a in aliases}
        sellers = []
        matched_brands = []
        for src, label in SOURCES:
            candidates = [(s, b) for s, b in masters[src].items() if norm(b.get("brand_name")) in wanted]
            rows = [r for s, b in candidates if (r := partner_row(src, label, b, s))]
            matched_brands += [b for _, b in candidates]
            if rows:
                sellers.append(max(rows, key=lambda r: r["pct"]))
        h = hubble.get(slug)
        if h and h.get("error"):
            h = previous.get(slug, {}).get("hubble")
            print(f"  {name}: kept last Hubble rate")
        best_partner = max(sellers, key=lambda r: r["pct"]) if sellers else None
        top = max([r["pct"] for r in sellers] + ([h["pct"]] if h else []), default=0)
        if top < MIN_PCT and slug not in CURATED:
            print(f"  skip {name}: best {top}%")
            continue
        if not sellers and not h:
            print(f"  skip {name}: no seller")
            continue
        terms = pick_terms(matched_brands)
        best = {"source": "dealo", "pct": h["pct"]} if h and (not best_partner or h["pct"] >= best_partner["pct"]) else (
            {"source": best_partner["source"], "pct": best_partner["pct"]} if best_partner else None)
        pages.append({
            "slug": slug,
            "name": name,
            "checked": date.today().isoformat(),
            "hubble": h,
            "sellers": sorted(sellers, key=lambda r: -r["pct"]),
            "best": best,
            "online": any(r["online"] for r in sellers) or bool(h and not h["in_store"]),
            "offline": any(r["offline"] for r in sellers) or bool(h and h["in_store"]),
            **terms,
        })
        print(f"  {name}: dealo {h['pct'] if h else '-'}%  " + "  ".join(f"{r['label']} {r['pct']}%" for r in sellers))

    OUT.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(pages)} shop pages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
