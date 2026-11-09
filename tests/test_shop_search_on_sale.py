"""A shop-name search never offers a card the refresh retired or marked
out of stock (Ikea left Gyftr on 2026-11-09 and the search still showed it)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import hubble_service, search_service  # noqa: E402


def test_no_retired_gyftr_card_is_offered_by_shop_search():
    master = json.loads((ROOT / "data/gyftr_master.json").read_text())
    retired = [e["brand_name"] for e in master.values()
               if e.get("products") and all(p.get("status") == "inactive" for p in e["products"])]
    assert retired
    for name in retired:
        if hubble_service.brand_for(name) or hubble_service.brand_for(name, in_store=True):
            continue  # Hubble still sells it: the website shows Dealo's card instead
        found = search_service.search_candidates(name, exact=True, shops_only=True)
        for card in found.get("voucher_choices") or [found.get("voucher") or {}]:
            same = (card.get("brand_name") or "").lower() == name.lower()
            assert not (same and card.get("voucher_source") == "gyftr"), name


def test_a_shop_only_hubble_still_sells_stays_findable():
    # Every partner listing gone, Hubble still sells it: the shop must still
    # come back, so the website can show Dealo's own card.
    record = {"brand_name": "PVR Cinemas", "products": [{"status": "inactive"}]}
    if hubble_service.brand_for("PVR Cinemas"):
        assert search_service._on_sale(record) is record
    assert search_service._on_sale({"brand_name": "Nowhere Shop", "products": [{"status": "inactive"}]}) is None
