"""BuyHatke's one-rate brands must price, not vanish.

BuyHatke quotes one rate per brand and sells only by UPI. From the price
refresh of 2026-09-04 that rate was stored as "any" whenever BuyHatke printed
no per-amount rates, and the pricing — which asked only for "UPI" — read 0%
and dropped 59 online brands from every priced answer. Found 2026-09-17 when
caratlane.com, chicco.in and ray-ban.com drew no voucher at checkout.

Run:  .venv/bin/python -m pytest tests/test_buyhatke_single_rate.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import voucher_service  # noqa: E402

def _chicco_tier() -> dict:
    """A real one-rate listing: Chicco's discounts read {"any": ...}."""
    deal = voucher_service.get_best_buyhatke_deal("Chicco", 5000)
    assert deal is not None, "Chicco prices to nothing"
    tier = deal[1]
    assert set(tier["discounts"]) == {"any"}, "Chicco is no longer a one-rate listing; pick another"
    return tier


def test_a_single_rate_is_the_upi_rate():
    tier = _chicco_tier()
    upi = voucher_service.calculate_effective_price(5000, tier, "upi")["voucher_discount_pct"]
    assert upi == tier["discounts"]["any"]


def test_a_single_rate_is_never_a_card_rate():
    """BuyHatke has no card purchase, so paying by card earns nothing."""
    assert voucher_service.calculate_effective_price(5000, _chicco_tier(), "card")["voucher_discount_pct"] == 0


def test_one_rate_brands_in_the_catalogue_price():
    for brand in ("Chicco", "Ray Ban", "CaratLane", "Pepperfry"):
        deal = voucher_service.get_best_buyhatke_deal(brand, 5000)
        assert deal is not None, f"{brand} has a live BuyHatke voucher but prices to nothing"
        assert deal[0]["voucher_discount_pct"] > 0, brand
