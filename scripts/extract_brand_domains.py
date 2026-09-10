"""Find each voucher brand's own shopping website, from terms we already have.

The extension has to recognise a shop's checkout page, and it can only do that
for shops it can name. Only 242 of ~1,500 brands had a confirmed domain, which
capped how often Dealo could appear at all.

The product owner's observation, which turned out to be right: the sellers
already publish the answer. A brand's redemption terms say where to spend the
voucher — Pizza Hut's Gyftr page names pizzahut.co.in — so the domains can be
read out of `data/voucher_terms_raw_*.json` rather than hunted for.

Writes two review files, because a machine guessing at brand identity should
be checked by a person:

  audits/brand_domains_found.csv    — every brand with a candidate, its
                                      confidence, and the evidence
  audits/brand_domains_missing.csv  — every brand with nothing, to be
                                      chased by hand

Run: .venv/bin/python scripts/extract_brand_domains.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AUDITS = REPO / "audits"

# Domains that appear in the terms but are never the shop: the sellers
# themselves, their support desks, app stores and social links.
NOT_A_SHOP = {
    "gyftr.com", "gvhelpdesk.com", "maximize.money", "buyhatke.com", "woohoo.in",
    "inr.deals", "linksredirect.com", "vouchagram.com", "vouchagram.net",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
    "linkedin.com", "whatsapp.com", "pinterest.com", "threads.net",
    "google.com", "play.google.com", "apps.apple.com", "itunes.apple.com",
    "bit.ly", "goo.gl", "tinyurl.com", "gmail.com", "example.com",
    "w3.org", "schema.org", "jquery.com", "cloudflare.com", "googleapis.com",
    "gstatic.com", "fontawesome.com", "bootstrapcdn.com", "jsdelivr.net",
}

URL = re.compile(r"(?:https?://|www\.)([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)
BARE = re.compile(r"\b([a-z0-9][a-z0-9-]{2,}\.(?:com|in|co\.in|net|org|shop|store|io|app))\b", re.I)

# Redemption types that never involve a website. A voucher you hand to a
# cashier has no checkout page for the extension to recognise, so chasing a
# domain for it is wasted effort — and leaving them in the review files buries
# the ones that matter under hundreds that never will. Excluded entirely, per
# the product owner 2026-09-09.
OFFLINE_ONLY = {"offline", "in-store", "in store", "instore", "store locator"}
IN_STORE_NAME = re.compile(r"in.?store|store only|offline", re.I)


def offline_only_listings() -> set[tuple[str, str]]:
    """(source, slug) pairs the masters say cannot be redeemed online."""
    out: set[tuple[str, str]] = set()
    for source in ("gyftr", "maximize", "buyhatke"):
        path = REPO / "data" / f"{source}_master.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for record in (data if isinstance(data, list) else list(data.values())):
            slug = record.get("slug") or ""
            kinds = {str(p.get("redemption_type") or "").strip().lower() for p in record.get("products", [])}
            kinds.discard("")
            # Only exclude when NOTHING about the listing is online.
            if kinds and kinds <= OFFLINE_ONLY:
                out.add((source, slug))
    return out


def norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def label_of(host: str) -> str:
    """The distinctive part of a host — "pizzahut" for pizzahut.co.in."""
    parts = host.split(".")
    return parts[-3] if len(parts) >= 3 and parts[-2] in {"co", "com", "net", "org"} else parts[0]


def confidence(brand: str, host: str) -> str:
    """How sure are we that this host belongs to this brand?

    Deliberately crude, and deliberately honest about it: the whole point of
    the review file is that a person checks the middling ones. Only an actual
    name match counts as high.
    """
    b, label = norm(brand), norm(label_of(host))
    if not b or not label:
        return "low"
    if b == label:
        return "high"
    if b.startswith(label) or label.startswith(b) or b in label or label in b:
        return "medium"
    return "low"


def harvest() -> tuple[list[dict], list[dict], int]:
    offline = offline_only_listings()
    skipped = 0
    by_brand: dict[tuple[str, str], dict] = {}
    for source in ("gyftr", "maximize", "buyhatke"):
        path = REPO / "data" / f"voucher_terms_raw_{source}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for record in (data if isinstance(data, list) else list(data.values())):
            brand = record.get("brand_name") or ""
            slug = record.get("slug") or ""
            if (source, slug) in offline or IN_STORE_NAME.search(brand):
                skipped += 1
                continue
            blob = json.dumps(record.get("raw"))
            hosts: dict[str, int] = defaultdict(int)
            for m in list(URL.finditer(blob)) + list(BARE.finditer(blob)):
                host = m.group(1).lower().removeprefix("www.").rstrip(".")
                if host in NOT_A_SHOP or any(host.endswith("." + d) for d in NOT_A_SHOP):
                    continue
                hosts[host] += 1
            key = (norm(brand), source)
            ranked = sorted(hosts, key=lambda h: ({"high": 0, "medium": 1, "low": 2}[confidence(brand, h)], -hosts[h]))
            by_brand[key] = {
                "brand": brand,
                "source": source,
                "slug": slug,
                "domain": ranked[0] if ranked else "",
                "confidence": confidence(brand, ranked[0]) if ranked else "",
                "other_candidates": " | ".join(ranked[1:4]),
                "seller_page": record.get("url") or "",
            }

    found = [r for r in by_brand.values() if r["domain"]]
    missing = [r for r in by_brand.values() if not r["domain"]]
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda r: (order.get(r["confidence"], 3), r["brand"].lower()))
    missing.sort(key=lambda r: r["brand"].lower())
    return found, missing, skipped


def main() -> None:
    AUDITS.mkdir(exist_ok=True)
    found, missing, skipped = harvest()

    with (AUDITS / "brand_domains_found.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["confidence", "brand", "domain", "source", "other_candidates", "slug", "seller_page"], extrasaction="ignore")
        w.writeheader()
        w.writerows(found)

    with (AUDITS / "brand_domains_missing.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["brand", "source", "slug", "seller_page"], extrasaction="ignore")
        w.writeheader()
        w.writerows(missing)

    counts = defaultdict(int)
    for r in found:
        counts[r["confidence"]] += 1
    total = len(found) + len(missing)
    print(f"{total} online brand listings read  ({skipped} in-store/offline listings excluded — no website to find)")
    print(f"  domain found : {len(found):>5}   ({len(found) * 100 // max(total, 1)}%)")
    for level in ("high", "medium", "low"):
        print(f"      {level:<7} {counts[level]:>5}")
    print(f"  nothing found: {len(missing):>5}   ({len(missing) * 100 // max(total, 1)}%)")
    print(f"\nwritten: audits/brand_domains_found.csv, audits/brand_domains_missing.csv")


if __name__ == "__main__":
    main()
