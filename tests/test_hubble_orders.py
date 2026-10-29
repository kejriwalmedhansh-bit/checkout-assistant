"""How Dealo splits a cart into Hubble orders.

Every expectation here was checked against Hubble's staging store on
23 Oct 2026 by opening its pay screen with the same amounts:
- typed-amount brands take ONE voucher per order (AJIO ₹12,000 → "0% off",
  dead button);
- card brands take only their listed values, several per order (Zepto
  ₹2,000 + ₹1,000 ok; Zepto ₹3,450 silently became one ₹1,000 card);
- a payment above ~₹10,000 is refused ("some message", dead button).

Product rules below are copied from Hubble's staging product API.

Run:  .venv/bin/python -m pytest tests/test_hubble_orders.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service as hs  # noqa: E402


def _product(min_amount, max_amount, cards=None, per_order=10, per_value=None,
             values_per_order=None, single_value=False, month_worth=None, step=1):
    return {
        "amountConditions": {
            "minAmount": min_amount, "maxAmount": max_amount, "stepAmount": step,
            "denominations": cards, "maxNoOfVouchersPerDenomination": per_value,
            "maxNoOfDenominationsPerOrder": values_per_order,
        },
        "restrictions": {"maxNumberOfVouchersPerOrder": per_order, "maxWorthOfVouchersInAMonth": month_worth},
        "voucherProductProviderMetadata": {"onlySingleDenominationAllowed": single_value},
    }


AJIO = _product(500, 10000)
FLIPKART = _product(10, 50000, month_worth=1000000)
ZOMATO = _product(250, 10000, per_order=4, month_worth=10000)
ZEPTO = _product(1000, 20000, cards=[2000, 1000])
BIGBASKET = _product(250, 10000, cards=[250, 500, 1000, 2000, 5000], per_value=10, values_per_order=1, single_value=True)
SKECHERS = _product(500, 10000, cards=[500, 1000, 2000, 5000], single_value=True, step=1000)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    s = hs.get_settings()
    monkeypatch.setattr(s, "HUBBLE_PAY_CAP", 10000)
    monkeypatch.setattr(s, "HUBBLE_MAX_ORDERS", 1)
    return s


def test_typed_amount_under_the_limit_is_one_voucher():
    assert hs._orders(AJIO, 2799, 4) == [[(2799, 1)]]


def test_typed_amount_over_the_brand_limit_stops_at_the_limit():
    # Staging: AJIO ₹12,000 and ₹25,000 (any split) both dead-end, so one
    # ₹10,000 voucher and the rest at the shop.
    assert hs._orders(AJIO, 12000, 4) == [[(10000, 1)]]
    assert hs._orders(AJIO, 25000, 4) == [[(10000, 1)]]


def test_payment_never_goes_above_the_cap():
    # Flipkart ₹11,000 at 1% = ₹10,890 to pay: refused on staging.
    assert hs._orders(FLIPKART, 11000, 1) == [[(10101, 1)]]
    assert hs._orders(FLIPKART, 10000, 1) == [[(10000, 1)]]


def test_more_orders_allowed_splits_by_the_payment_cap(_settings):
    _settings.HUBBLE_MAX_ORDERS = 3
    orders = hs._orders(FLIPKART, 25000, 1)
    assert [sum(a * n for a, n in o) for o in orders] == [10101, 10101, 4798]
    assert all(sum(a * n for a, n in o) * 0.99 <= 10000 for o in orders)


def test_card_brand_never_sends_an_amount_it_does_not_sell():
    # Zepto ₹3,450: ₹3,000 in cards, ₹450 paid at the shop.
    assert hs._orders(ZEPTO, 3450, 0.5) == [[(2000, 1), (1000, 1)]]


def test_one_value_per_order_picks_the_value_that_covers_most():
    # BigBasket ₹3,500: staging refused the mixed 2,000+1,000+500 amount.
    assert hs._orders(BIGBASKET, 3500, 3) == [[(500, 7)]]
    assert hs._orders(SKECHERS, 7500, 5) == [[(1000, 7)]]


def test_monthly_limit_caps_the_order():
    assert hs._orders(ZOMATO, 8000, 4) == [[(8000, 1)]]
    assert hs._orders(ZOMATO, 12000, 4) == [[(10000, 1)]]


def test_below_the_smallest_voucher_is_not_offered():
    assert hs._orders(ZEPTO, 900, 1) is None
    assert hs._orders(AJIO, 400, 4) is None


# --- Showing Hubble when it is a little behind today's best (owner, 28 Oct 2026) ---

def test_hubble_shown_within_two_points_of_best(monkeypatch):
    s = hs.get_settings()
    monkeypatch.setattr(s, "HUBBLE_RATE_TOLERANCE", 2.0)
    assert hs.worth_showing(7.0, 7.75)      # Pantaloons: Hubble 7 vs Maximize 7.75
    assert hs.worth_showing(11.0, 11.0)     # tie
    assert hs.worth_showing(8.0, 10.0)      # exactly 2 points behind still shows
    assert not hs.worth_showing(7.5, 10.0)  # 2.5 behind: today's route stays
    assert hs.worth_showing(4.0, None)      # nothing to compare against
    assert not hs.worth_showing(0.0, None)  # 0% is never an offer
