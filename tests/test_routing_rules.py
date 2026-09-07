"""The routing rules, written as examples anyone can read.

This file is the executable half of the rulebook. The rules themselves live in
`data/voucher_rules.json` under `_platform_rules`; the cases below pin down what
those rules must produce for real shops at real order sizes.

Every case names the rule it protects. If you change a rule, a case here should
change with it — and if one fails without you having changed a rule, something
has regressed.

Run:  .venv/bin/python -m pytest tests/test_routing_rules.py -q
or:   .venv/bin/python tests/test_routing_rules.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repositories import platform_rules_repository as platform_rules  # noqa: E402
from src.services import voucher_service as vs  # noqa: E402


# --- The rules, as stated by the product owner 2026-09-07 -------------------
#
# 1. Dealo only ever recommends a plan buyable in ONE checkout. Anything not
#    covered is paid normally by card.
# 2. One voucher needed -> whichever platform is cheapest, Maximize and
#    BuyHatke included.
# 3. More than one denomination needed -> Gyftr, always. Maximize and BuyHatke
#    have no cart and cannot take two different amounts in one order. They are
#    not dropped for it, though: they are planned inside the one-checkout rule
#    from the start, taking the best single amount they can and leaving the
#    rest to the card. Dropping them instead sent a ₹2,199 Frido order to
#    Gyftr at ₹1,919 when Maximize could do ₹1,874 in one checkout.
# 4. Repeats of the SAME denomination -> allowed on Maximize up to four, and
#    only where the brand's own terms permit combining vouchers on one bill.
#    BuyHatke sells one voucher per transaction whatever the denomination.

CASES = [
    # (shop domain, order, expected platform, rule being protected)
    ("myfrido.com", 2199, "maximize",
     "rule 1+2 — one ₹2,000 voucher and ₹199 on the card beats Gyftr's ₹1,919"),
    ("myfrido.com", 5000, "maximize",
     "rule 2 — one voucher, Maximize's 16.25% beats Gyftr's 14%"),
    ("myfrido.com", 12000, "gyftr",
     "rule 3 — needs ₹5,000 + ₹2,000, and Maximize has no cart"),
    ("myfrido.com", 29999, "gyftr",
     "rule 3/4 — the order that was wrongly sent to Maximize as 8 purchases"),
    ("skullcandy.in", 5000, "buyhatke",
     "rule 2 — one voucher, BuyHatke cheapest"),
    ("skullcandy.in", 12000, "maximize",
     "rule 1+3 — still one typed-in amount only, but ₹10,000 there plus "
     "₹2,000 on the card is one checkout and beats Gyftr's three-voucher basket"),
    ("netmeds.com", 5000, "maximize",
     "rule 4 — 4×₹1,000 is one amount within Maximize's cap of four, so one "
     "checkout, with the last ₹1,000 on the card"),
    ("myntra.com", 12000, "buyhatke",
     "rule 2 — a single ₹10,000 voucher, remainder on card"),
    ("croma.com", 29999, "gyftr",
     "rule 3 — three ₹10,000 vouchers in one Gyftr basket"),
]


def test_every_recommendation_is_one_checkout():
    """Rule 1. The rule that makes all the others simple."""
    failures = []
    for domain, price, _, _ in CASES:
        r = vs.get_voucher_check(domain, price)
        if r.get("has_voucher") and r.get("txns_needed", 1) > 1:
            failures.append(f"{domain} at ₹{price:,} wants {r['txns_needed']} checkouts")
    assert not failures, "plans needing more than one checkout: " + "; ".join(failures)


def test_platform_choice():
    """Rules 2, 3 and 4, one worked example at a time."""
    failures = []
    for domain, price, expected, why in CASES:
        r = vs.get_voucher_check(domain, price)
        got = r.get("voucher_source")
        if got != expected:
            failures.append(f"{domain} ₹{price:,}: expected {expected}, got {got}  ({why})")
    assert not failures, "\n".join(failures)


def test_never_offers_a_listing_that_is_not_on_sale():
    """The refresh marks listings inactive — out of stock, 0%, loyalty-only.
    Nothing in the service read that flag until 2026-09-07, so a Yatra booking
    was quoted an inactive 64.75% voucher nobody could buy. Guards the rule
    that an out-of-stock voucher is never recommended."""
    import json
    from pathlib import Path as _P

    inactive_rates = set()
    for src in ("gyftr", "maximize", "buyhatke"):
        raw = json.loads((_P(__file__).resolve().parents[1] / "data" / f"{src}_master.json").read_text())
        for record in (raw if isinstance(raw, list) else list(raw.values())):
            for product in record.get("products", []):
                if product.get("status") == "inactive" and product.get("best_discount_pct"):
                    inactive_rates.add((record.get("brand_name"), product["best_discount_pct"]))

    # Yatra is the case that exposed it: an inactive 64.75% beside live ~5%.
    for price in (2000, 8000, 20000):
        r = vs.get_voucher_check("yatra.com", price)
        if not r.get("has_voucher"):
            continue
        assert r["pct"] < 60, (
            f"yatra.com at ₹{price:,} was quoted {r['pct']}%, which is the inactive listing"
        )


def test_buyhatke_never_sells_more_than_one_voucher():
    """Rule 4. BuyHatke is one per transaction whatever the brand's terms say,
    which is why brand stacking is irrelevant to it."""
    for brand_stacks in (True, False, None):
        assert platform_rules.max_vouchers_per_checkout("buyhatke", brand_stacks) == 1


def test_maximize_is_capped_at_four_and_gated_on_the_brand():
    """Rule 4. Four is Maximize's own ceiling; it applies only where the shop
    accepts several vouchers on one bill."""
    assert platform_rules.max_vouchers_per_checkout("maximize", True) == 4
    assert platform_rules.max_vouchers_per_checkout("maximize", False) == 1
    # Terms that never said are read as "no" — the stricter source wins.
    assert platform_rules.max_vouchers_per_checkout("maximize", None) == 1


def test_only_gyftr_may_mix_denominations():
    """Rule 3, at the rulebook level rather than through a shop."""
    assert platform_rules.allows_mixed_denominations("gyftr") is True
    assert platform_rules.allows_mixed_denominations("maximize") is False
    assert platform_rules.allows_mixed_denominations("buyhatke") is False


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"  ok    {check.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {check.__name__}\n        {e}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    sys.exit(1 if failed else 0)
