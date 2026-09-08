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
# 0. The terms and important instructions come first. A platform's rules are
#    the structure; what the terms say will be accepted on one bill is what the
#    plan is built to. Product owner, 2026-09-07. And they are read PER SELLER
#    (2026-09-08): the same brand can genuinely carry different rules on each
#    platform, because each issues its own voucher under its own agreement.
#    Where one seller lists a brand twice, the stricter of the two wins.
# 5. Gyftr's cart takes ten of any one brand-and-denomination and no more
#    ("Same voucher more than 10 quantity is not allowed!"). Ten ₹10,000 plus
#    ten ₹2,000 plus ten ₹500 is one legal order; another brand gets its own
#    ten. Every brand's own rule still applies on top, and the stricter wins.

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


def test_the_selling_platforms_own_terms_cap_the_plan():
    """Rule 0. A plan is held to the terms of the exact listing it sends the
    shopper to — not another seller's terms for the same brand, and not the
    strictest of everything that seller lists under the name. Both distinctions
    are real: Westside reads differently on Gyftr and Maximize because each
    issues its own voucher (product owner, 2026-09-08), and Maximize's two
    Hidesign listings are different products at 7.75% and 13%.

    Checked through the deal's own `voucher_url`, which is the listing the
    shopper is actually sent to buy."""
    import json
    from pathlib import Path as _P

    raw = json.loads((_P(__file__).resolve().parents[1] / "data" / "voucher_rules.json").read_text())
    limits = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue
        rules = entry.get("rules") or {}
        named = (rules.get("max_cards_per_order") or {}).get("value")
        limit = 1 if (rules.get("can_combine") or {}).get("value") == "no" else (
            int(named) if isinstance(named, (int, float)) and named >= 1 else None
        )
        if limit is not None:
            limits[key] = limit

    by_url = vs._slug_by_listing_url()
    getters = (vs.get_best_voucher_deal, vs.get_best_maximize_deal, vs.get_best_buyhatke_deal)
    brands = {entry.get("brand_name") for entry in raw.values() if isinstance(entry, dict)}
    failures = []
    checked = 0
    for brand in sorted(b for b in brands if b):
        for price in (12000, 54999):
            for getter in getters:
                result = getter(brand, price)
                deal = result[0] if isinstance(result, tuple) else result
                if not deal:
                    continue
                source = deal["voucher_platform"].lower()
                slug = by_url.get((source, deal.get("voucher_url") or ""))
                limit = limits.get(f"{source}:{slug}") if slug else None
                if limit is None:
                    continue
                checked += 1
                bought = sum(b["count"] for b in deal["denomination_breakdown"])
                if bought > limit:
                    failures.append(
                        f"{brand} at ₹{price:,} -> {source}:{slug}: "
                        f"{deal['purchase_breakdown']} against its own stated limit of {limit}"
                    )
    assert checked > 100, f"only {checked} priced listings carried a stated limit"
    assert not failures, "plans exceeding what the listing's terms allow:\n" + "\n".join(failures[:10])


def test_gyftr_takes_ten_of_one_denomination_and_no_more():
    """Rule 5, stated by the product owner 2026-09-07 with the cart's own error
    message. A ₹54,999 Subway order used to come out as 55x₹1,000, which that
    cart would have refused."""
    import json
    from pathlib import Path as _P

    assert platform_rules.rules_for("gyftr")["vouchers_per_order"] == 10

    raw = json.loads((_P(__file__).resolve().parents[1] / "data" / "gyftr_master.json").read_text())
    failures = []
    for record in raw.values():
        brand = record.get("brand_name")
        if not brand:
            continue
        for price in (12000, 54999):
            deal = vs.get_best_voucher_deal(brand, price)
            if not deal:
                continue
            over = [b for b in deal["denomination_breakdown"] if b["count"] > 10]
            if over:
                failures.append(f"{brand} at ₹{price:,}: {deal['purchase_breakdown']}")
    assert not failures, "more than ten of one denomination:\n" + "\n".join(failures[:10])


def test_maximize_sells_one_custom_amount_voucher_per_order():
    """Rule 4, for typed-in amounts. Stated by the product owner 2026-09-07:
    "No matter the custom amount, on Maximize you can only purchase one custom
    amount voucher at a time" — one ₹1,400 voucher, never two or three. The
    quantity cap of four is about repeats of a listed denomination, and does
    not carry over to amounts you type in."""
    import json
    from pathlib import Path as _P

    raw = json.loads((_P(__file__).resolve().parents[1] / "data" / "maximize_master.json").read_text())
    failures = []
    checked = 0
    for record in raw.values():
        for product in record.get("products", []):
            if not product.get("is_custom_denom") or product.get("status") == "inactive":
                continue
            custom_max = product.get("custom_max")
            if not custom_max:
                continue
            checked += 1
            # Priced well past one voucher, which is where a second would appear.
            deal = vs.calculate_effective_price(
                custom_max * 3,
                {**record, **product, "voucher_platform": "Maximize", "reseller_stack_limit": 4},
            )
            vouchers = sum(b["count"] for b in deal["denomination_breakdown"]) or 1
            if vouchers > 1 or deal["voucher_amount"] > custom_max:
                failures.append(
                    f"{record.get('brand_name')}: {deal['purchase_breakdown']} "
                    f"(₹{deal['voucher_amount']:,.0f} against a ₹{custom_max:,.0f} maximum)"
                )
    assert checked > 100, f"only {checked} custom-amount Maximize brands checked"
    assert not failures, "more than one typed-in amount per order:\n" + "\n".join(failures[:10])


def test_gyftrs_invented_transaction_cap_decides_nothing():
    """Gyftr's `purchase_cap_per_txn` is not a Gyftr fact: build_master.py fills
    it with `10 x sum(unique denominations)` for any brand whose terms mention
    e-Pay stacking. Subway's "₹26,000" is 10 x (100+250+500+750+1000). Asked
    where the number came from by the product owner 2026-09-07, so it now
    caps no basket and creates no checkout — a ₹54,999 Subway order is one
    Gyftr basket, not three."""
    import json
    from pathlib import Path as _P

    raw = json.loads((_P(__file__).resolve().parents[1] / "data" / "gyftr_master.json").read_text())
    subway = next(r for r in raw.values() if (r.get("brand_name") or "").lower() == "subway")
    product = subway["products"][0]
    assert product["purchase_cap_per_txn"] == 10 * sum(sorted(set(product["denominations"]))), (
        "Subway's cap is no longer the 10x formula — check whether Gyftr now publishes a real one"
    )
    # Whatever the number, it is not allowed to decide anything for Gyftr.
    assert vs._per_txn_rupee_cap({**subway, **product, "voucher_platform": "Gyftr"}) is None

    for domain, price in (("subway.co.in", 54999), ("baskinrobbinsindia.com", 28999)):  # noqa: E501
        r = vs.get_voucher_check(domain, price)
        if not r or not r.get("has_voucher"):
            continue
        assert r.get("txns_needed", 1) == 1, (
            f"{domain} at ₹{price:,} wants {r['txns_needed']} checkouts off an invented cap"
        )


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
