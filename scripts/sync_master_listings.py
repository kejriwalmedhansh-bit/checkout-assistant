#!/usr/bin/env python3.11
"""Bring each platform's listings into the masters: add what is new, retire
what has gone. Run before update_masters_from_scrape.py, which then prices
everything, old and new, by the same rules.

update_masters_from_scrape only ever updated listings the masters already had,
so a brand a platform added after a master was first built was collected on
every refresh and then dropped. Found 2026-09-28: BuyHatke's PVR, Amazon Pay,
PhonePe and CultFit had been collected since 2026-09-04 and never shown. The
reverse was missing too — a listing the platform stopped selling stayed active
at its last price.

A new listing is added as a bare product (identity, where it works, what it
says about itself); rates, amounts, stack limit and status are left to
update_masters_from_scrape, so a new brand cannot skip any check an old one
goes through. It starts inactive and is only switched on there if its offer is
recommendable.

A listing counts as gone only when its platform was collected in this run and
the listing was not in it. Its status goes to inactive; nothing is deleted.

  --dry-run   report, write nothing
"""
import argparse
import json
import re
from urllib.parse import unquote
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OFFERS = DATA / "voucher_offers.json"
LABEL = {"gyftr": "GyFTR", "buyhatke": "BuyHatke", "maximize": "Maximize"}


def key_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def loose_key(name: str) -> str:
    """Brand name without the platform's qualifiers: BuyHatke moved many
    listings to new addresses in September 2026 and renamed them on the way
    ("Absolute Barbecues" -> "Absolute Barbecues (In Store)")."""
    return key_of(re.sub(r"\(.*?\)", "", unquote(name or "")))


def where(offer: dict, source: str) -> str | None:
    rules = offer.get("rules") or {}
    online = (rules.get("works_online") or {}).get("value")
    store = (rules.get("works_in_store") or {}).get("value")
    on, off = online == "yes", store == "yes"
    # Each master spells this its own way; a new entry follows its neighbours.
    if source == "maximize":
        return ("Online + In-store" if on and off else "Online" if on
                else "In-store" if off else None)
    return "Both" if on and off else "Online" if on else "Offline" if off else None


def steps(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
    return [ln for ln in lines if not re.fullmatch(r"\d+|close|how to redeem.*", ln, re.I)]


def new_product(offer: dict, source: str, raw: dict) -> dict:
    return {
        "product_name": (raw.get("product_name") if source == "maximize" else None)
                        or unquote(offer["brand_name"]).strip(),
        # Gyftr's master matches on slug and carries no URL; the others match on it.
        "source_url": None if source == "gyftr" else offer["url"],
        "redemption_type": where(offer, source),
        "denominations": [],
        "is_custom_denom": False,
        "custom_min": None,
        "custom_max": None,
        "discounts": {},
        "best_payment_method": None,
        "best_discount_pct": None,
        "stack_limit": None,
        "value_cap": None,
        "purchase_cap_per_txn": None,
        "status": "inactive",
        "last_scraped": None,
        **({"reseller_qty_cap": raw.get("max_quantity_per_order")} if source == "maximize" else {}),
    }


def new_entry(offer: dict, source: str, slug: str, raw: dict) -> dict:
    rules = offer.get("rules") or {}
    club = (rules.get("combines_with_store_offers") or {}).get("value")
    once = (rules.get("one_time_use") or {}).get("value")
    return {
        "brand_name": unquote(offer["brand_name"]).strip(),
        "slug": slug,
        "source": LABEL[source],
        "products": [new_product(offer, source, raw)],
        "description": raw.get("long_description") or None,
        "important_instructions_raw": raw.get("important_instruction") or raw.get("restrictions") or None,
        "how_to_redeem_steps": steps(offer.get("instructions")),
        "full_terms_and_conditions": offer.get("terms") or None,
        "can_club_with_offers": {"yes": True, "no": False}.get(club),
        "one_time_use": {"yes": True, "no": False}.get(once),
        "redemption_restrictions": [],
        "notes": "added by sync_master_listings.py",
        "stack_limit_confidence": None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    offers = json.loads(OFFERS.read_text())
    for source in LABEL:
        path = DATA / f"{source}_master.json"
        master = json.loads(path.read_text())
        raw_all = json.loads((DATA / f"voucher_terms_raw_{source}.json").read_text())
        mine = {k: o for k, o in offers.items() if o["source"] == source}
        # Only listings collected in this run count as "on sale now".
        latest = max((r.get("scraped_at") or "")[:10] for r in raw_all.values())
        live = {k for k, r in raw_all.items() if (r.get("scraped_at") or "")[:10] == latest}

        urls = {p.get("source_url") for e in master.values() for p in e["products"]}
        stats, added, retired, moved = Counter(), [], [], []
        live_urls = {mine[k]["url"] for k in live if k in mine}
        # Products whose address is no longer on sale, by brand: a new listing
        # with the same brand name is the same card at a new address.
        orphans: dict[str, list] = {}
        if source != "gyftr":
            for e in master.values():
                for p in e["products"]:
                    if p.get("source_url") not in live_urls:
                        orphans.setdefault(loose_key(e["brand_name"]), []).append(p)

        for k, o in mine.items():
            if k not in live:
                continue
            if o["url"] in urls or (source == "gyftr" and o["slug"] in master):
                continue
            raw = (raw_all.get(k) or {}).get("raw") or {}
            same = orphans.get(loose_key(o["brand_name"])) or []
            if len(same) == 1:
                # Keep the entry — and everything keyed to it, like the owner's
                # voucher-choice answers — and follow the listing to its address.
                moved.append(f"{o['brand_name'].strip()}: {same[0]['source_url']} -> {o['url']}")
                same[0]["source_url"] = o["url"]
                orphans.pop(loose_key(o["brand_name"]))
                urls.add(o["url"])
                continue
            if source == "maximize":
                # Maximize lists several products under one brand URL name
                # (five "Amazon"s). A new one joins that brand only when it IS
                # that product; a different product filed there (Prime Lite,
                # Amazon Fresh, Air India's seats-and-baggage card, 2026-09-28)
                # took the reviewed card's name and rules, so it gets its own
                # record under its own product name and the listing's own slug,
                # which is where its read rules are filed.
                name = unquote(raw.get("product_name") or o["brand_name"]).strip()
                home = next((s for s, e in master.items()
                             if key_of(e.get("brand_name")) == key_of(name)), None)
                if home:
                    master[home]["products"].append(new_product(o, source, raw))
                    added.append(f"{name} (another listing)")
                    continue
                slug = o["slug"]
                o = {**o, "brand_name": name}
            else:
                slug = o["slug"]
            if slug in master:
                stats["skipped: slug already taken by another listing"] += 1
                continue
            master[slug] = new_entry(o, source, slug, raw)
            added.append(unquote(o["brand_name"]).strip())

        live_urls = {mine[k]["url"] for k in live if k in mine}
        live_slugs = {mine[k]["slug"] for k in live if k in mine}
        # Maximize has no live catalogue to be absent from: its list is the
        # harvested one, so a card missing from a run was missed, not delisted.
        # A card Maximize itself reports gone ("Gift Card not found") is
        # switched off by update_masters_from_scrape, like anything unsellable.
        for slug, e in (master.items() if source != "maximize" else ()):
            for p in e["products"]:
                gone = (slug not in live_slugs) if source == "gyftr" else (p.get("source_url") not in live_urls)
                if gone and p.get("status") != "inactive":
                    p["status"] = "inactive"
                    retired.append(p.get("product_name") or e["brand_name"])

        print(f"\n{source}: {len(added)} added, {len(moved)} moved to a new address, "
              f"{len(retired)} retired (no longer on sale)")
        for k, v in stats.items():
            print(f"  {v:4}  {k}")
        if added:
            print("  added  :", ", ".join(sorted(added)))
        if retired:
            print("  retired:", ", ".join(sorted(retired)))
        for m in moved:
            print("  moved  :", m)
        if not args.dry_run:
            path.write_text(json.dumps(master, indent=2, ensure_ascii=False) + "\n")

    print("\n--dry-run: nothing written" if args.dry_run else "\nmasters synced")


if __name__ == "__main__":
    main()
