"""Replay saved Google Shopping searches through the picker, offline.

tests/fixtures/benchmark/*.json (tests/capture_benchmark.py) are raw
google_shopping results. This runs each through the same steps the website
does before showing the picker - candidate shaping, the trust/price filter,
the ID-card tiering - and checks that listings a human confirmed are the
product are still there to be picked. The matcher's answer key is scored in
test_match_checklist.py; this test covers the filtering around it.

Run:  .venv/bin/python -m pytest tests/test_picker_replay.py -q
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services import product_identity, search_service  # noqa: E402

BENCH = ROOT / "tests" / "fixtures" / "benchmark"

# Listings that must come out of the picker for the search named by the
# fixture: (seller, price). Each was a real shop selling the exact product.
MUST_SURVIVE = {
    "adidas_originals_women_handball_spezial_sneakers": [],   # no trusted exact seller in this capture
    "nike_downshifter_14": [("AJIO.com", 3916.0), ("Nykaa Man", 3916.0), ("Tata CLiQ Fashion", 4895.0)],
    # one card per version: the cheapest of same-looking listings is kept, so
    # Amazon's 512 at 999 folds into Myntra's at 811
    "levis_512_slim_taper_jeans_men": [("AJIO.com", 1440.0), ("Myntra", 811.0)],
    "boat_rockerz_550_headphones": [("Tata Neu", 1499.0)],
    "realme_buds_t310_earbuds": [("Flipkart", 2399.0), ("AJIO.com", 1899.0), ("Myntra", 1899.0)],
    "philips_hl7756_mixer_grinder_750w": [("Amazon.in", 3299.0)],
    "samsung_galaxy_m35_5g_8gb_128gb": [("JioMart", 15998.0)],
    "jbl_flip_6_bluetooth_speaker": [],
}


def picker_rows(slug: str) -> tuple[list[dict], dict]:
    raw = json.loads((BENCH / f"{slug}.json").read_text())
    query = raw["query"]
    candidates = [search_service._product_candidate(p) for p in raw["shopping_results"] if p.get("product_token")]
    if raw.get("url"):
        ident = product_identity.build_identity(raw.get("page_title") or query, raw["url"])
    else:
        ident = search_service._typed_identity(query)
    if ident is not None:
        ident = product_identity.weigh_identity(
            ident, [p.get("title") or "" for p in raw["shopping_results"]], search_service._load_trusted_merchants())
    products, _ = search_service._filter_and_group_candidates(candidates, query, tag="[replay]", identity=ident)
    if ident is None:
        return products, {"products": products}
    exact, similar, unconfirmed = search_service._tier_by_identity(products, ident, "[replay]")
    return exact, {"exact": exact, "similar": similar, "unconfirmed": unconfirmed}


@pytest.mark.parametrize("slug", sorted(MUST_SURVIVE), ids=sorted(MUST_SURVIVE))
def test_confirmed_listings_reach_the_picker(slug: str):
    exact, tiers = picker_rows(slug)
    shown = {(p.get("source"), p.get("price")) for p in exact}
    missing = [w for w in MUST_SURVIVE[slug] if w not in shown]
    assert not missing, f"{slug}: {missing} not offered. Picker: {sorted(shown)}"


if __name__ == "__main__":
    for slug in sorted(MUST_SURVIVE):
        exact, tiers = picker_rows(slug)
        print(f"{slug}: {len(exact)} exact, {len(tiers.get('similar', []))} similar, {len(tiers.get('unconfirmed', []))} unconfirmed")
        for p in exact[:8]:
            print(f"   {p.get('source')!s:22} {p.get('price')!s:9} {p.get('was_price')!s:8} {p.get('title')[:70]}")
