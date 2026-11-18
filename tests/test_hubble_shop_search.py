"""A shop's plain name finds Dealo's own (Hubble) card even when the voucher
partners name the shop differently ("Hamleys" vs "Hamleys-Luxe Gift Card").
Before 2026-11-16, 111 of Hubble's 466 shops could not be found by name."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import hubble_service, search_service  # noqa: E402


def _hubble_says(monkeypatch, on_sale: bool = True):
    async def fake(merchant=None, slug=None, in_store=False):
        b = hubble_service.brand_for(merchant) or hubble_service.brand_for(merchant, True)
        if not (b and on_sale):
            return None
        return {"brand_name": b["name"], "discount_pct": 10.0, "cards": [1000, 2000]}
    monkeypatch.setattr(hubble_service, "brand_info", fake)
    monkeypatch.setattr(hubble_service, "_catalogue_path", lambda: ROOT / "data/hubble_catalogue.json")
    # The partner indexes are cached with Hubble's catalogue baked in
    # (search_service._on_sale); rebuild them here and put the old ones back
    # afterwards, so this file's catalogue never leaks into other tests.
    for cache in ("_brand_voucher_index_cache", "_maximize_brand_index_cache", "_buyhatke_brand_index_cache"):
        monkeypatch.setattr(search_service, cache, None)


def test_plain_shop_name_finds_the_hubble_card(monkeypatch):
    _hubble_says(monkeypatch)
    for q in ("Hamleys", "hamleys gift card", "Tira", "Superdry", "Titan Eye+"):
        found = search_service.search_candidates(q, exact=True, shops_only=True)
        assert found.get("mode") == "brand_voucher", q
        card = found["voucher"]
        if card.get("voucher_source") == "hubble":
            assert card["voucher_url"].startswith("http") and "/buy/" in card["voucher_url"]
            assert card["best_discount_pct"] == 10.0


def test_hamleys_is_dealos_own_card(monkeypatch):
    _hubble_says(monkeypatch)
    found = search_service.search_candidates("Hamleys", exact=True, shops_only=True)
    card = found["voucher"]
    assert card["voucher_source"] == "hubble"
    assert card["brand_name"] == "Hamleys-Luxe Gift Card"
    # The website's /search answer must accept it (it rejected a card with no slug).
    from src.schemas.search import SearchCandidatesResponse
    SearchCandidatesResponse.model_validate(found)


def test_a_shop_hubble_is_not_selling_right_now_is_not_offered(monkeypatch):
    _hubble_says(monkeypatch, on_sale=False)
    found = search_service.search_candidates("Hamleys", exact=True, shops_only=True)
    assert found.get("mode") is None


def test_a_product_search_naming_the_shop_is_not_a_shop_search(monkeypatch):
    _hubble_says(monkeypatch)
    found = search_service.search_candidates("Hamleys remote control car", exact=True, shops_only=True)
    assert found.get("mode") is None


def test_almost_every_hubble_shop_is_findable_by_name(monkeypatch):
    _hubble_says(monkeypatch)
    catalogue = json.loads((ROOT / "data/hubble_catalogue.json").read_text())
    names = {(search_service._clean_brand_name(b["name"]) or b["name"]) for b in catalogue}
    missed = [n for n in names
              if search_service.search_candidates(n, exact=True, shops_only=True).get("mode") != "brand_voucher"]
    # Known leftovers: "Giva Gold Voucher" ("Giva" finds it), "Organic India"
    # ("organic" is too common a word to alias). Anything more is a regression.
    assert len(missed) <= 3, sorted(missed)


def _a_retired_partner_card_hubble_lists():
    # A shop whose partner card the refresh retired but Hubble still lists
    # (Westside on 2026-11-16); picked from the data so a refresh can't break it.
    for name, rec in search_service._load_brand_voucher_index().items():
        products = rec.get("products") or []
        if products and not any(search_service.voucher_service._is_sellable(p) for p in products):
            return rec["brand_name"]
    return None


def test_a_retired_partner_card_is_never_shown(monkeypatch):
    _hubble_says(monkeypatch, on_sale=False)
    name = _a_retired_partner_card_hubble_lists()
    assert name, "expected at least one retired card that Hubble lists"
    found = search_service.search_candidates(name, exact=True, shops_only=True)
    for card in found.get("voucher_choices") or ([found["voucher"]] if found.get("voucher") else []):
        assert search_service._partner_sells_now(card) or card.get("voucher_source") == "hubble", (name, card.get("brand_name"))


def test_a_retired_partner_card_becomes_dealos_card_when_hubble_sells(monkeypatch):
    _hubble_says(monkeypatch)
    name = _a_retired_partner_card_hubble_lists()
    found = search_service.search_candidates(name, exact=True, shops_only=True)
    assert found.get("mode") == "brand_voucher", name
    assert found["voucher"]["voucher_source"] == "hubble" or search_service._partner_sells_now(found["voucher"])
