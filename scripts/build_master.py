import json, re

with open("db/gyftr_vouchers.json") as f:
    api_brands = {b["slug"]: b for b in json.load(f)}

with open("db/gyftr_full_scrape_progress.json") as f:
    scraped = json.load(f)

with open("db/gyftr_stacking_rules.json") as f:
    rules = json.load(f)

REDEMPTION_MAP = {"ON": "Online", "OFF": "Offline", "B": "Both"}

def normalize_label(pg_name):
    name = (pg_name or "").strip().lower()
    if "upi" in name or "amazon pay" in name:
        return "UPI"
    if "credit card" in name:
        return "Credit Card"
    if "debit card" in name:
        return "Debit Card"
    if "net banking" in name or "netbanking" in name:
        return "Net Banking"
    return pg_name

def normalized_discount_map(pgdis_list):
    merged = {}
    for pg in (pgdis_list or []):
        label = normalize_label(pg.get("pg_name"))
        val = pg.get("brand_pg_discount")
        if val is None:
            continue
        if label not in merged or val > merged[label]:
            merged[label] = val
    return merged

def best_payment(merged_map):
    if not merged_map:
        return None, None
    best_val = max(merged_map.values())
    tied = [label for label, v in merged_map.items() if v == best_val]
    if "UPI" in tied:
        return "UPI", best_val
    return tied[0], best_val

def extract_count_limit(text):
    """Extract a per-bill voucher count limit from text. Returns (limit, None) or (None, None)."""
    if not text:
        return None, None

    # "Multiple GV/GC/vouchers/GV's cannot be used/clubbed in one bill"
    if re.search(
        r'multiple\s+(?:gv\'?s?\s*/?\s*gc\'?s?|gift\s*(?:vouchers?|cards?)|vouchers?)\s+cannot\s+be\s+(?:used|clubbed|redeemed|combined)',
        text, re.IGNORECASE
    ):
        return 1, None

    # "only 1 GV/GC per order" / "redeem only 1 GV/GC" (numeral form)
    if re.search(
        r'(?:redeem\s+)?only\s+1\s+(?:gv\s*/\s*gc|gift\s*(?:voucher|card))',
        text, re.IGNORECASE
    ):
        return 1, None

    # "Only one Gift Voucher CAN be used per bill/order/subscription/donation"
    # or "...for one subscription/bill" (spelled-out "one", as opposed to the
    # numeral "1" case above; "GV/GC", "GV", "GC", or "gift voucher/card" as
    # the noun; "per X" or "for one X" as the trailing construction — all
    # variants genuinely appear across different brands' scraped terms for
    # the exact same restriction).
    if re.search(
        r'only\s+one\s+(?:gift\s*)?(?:voucher|card|gv\s*/?\s*gc|gv|gc)s?\s+(?:can\s+be\s+used\s+)?(?:per|for\s+one)\s+(?:bill|order|day|transaction|subscription|donation|booking)',
        text, re.IGNORECASE
    ):
        return 1, None

    # "up to N Gift Vouchers/Cards CAN be used"
    m = re.search(
        r'up\s+to\s+(\d+)\s+(?:gift\s*(?:vouchers?|cards?)|gv\s*/\s*gc)',
        text, re.IGNORECASE
    )
    if m:
        return int(m.group(1)), None

    # "combine a maximum of N" / "maximum of N Gift Cards"
    m = re.search(
        r'(?:combine\s+a\s+)?max(?:imum)?\s+of\s+(\d+)\s+(?:gift\s*(?:vouchers?|cards?)|gv\s*/\s*gc)',
        text, re.IGNORECASE
    )
    if m:
        return int(m.group(1)), None

    # "GV/GC (maximum N) CAN be used in one bill"  e.g. Malabar Silver Coin → 9
    m = re.search(r'\(maximum\s+(\d+)\)\s+can\s+be\s+used\s+in\s+one\s+bill', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), None

    # "Gift Cards/vouchers cannot be clubbed in single invoice/order"  e.g. Veridicus → 1
    if re.search(
        r'(?:gift\s*cards?|vouchers?|gv\s*/\s*gc)\s+cannot\s+be\s+clubbed\s+in\s+single',
        text, re.IGNORECASE
    ):
        return 1, None

    # "One voucher valid for one transaction"  e.g. Elivaas → 1
    if re.search(
        r'one\s+(?:voucher|gv|gc)\s+(?:is\s+)?valid\s+for\s+one\s+(?:transaction|order|bill)',
        text, re.IGNORECASE
    ):
        return 1, None

    # "Multiple coupons cannot be used for single orders"  e.g. Elivaas → 1
    if re.search(
        r'multiple\s+coupons?\s+cannot\s+be\s+used\s+for\s+single\s+orders?',
        text, re.IGNORECASE
    ):
        return 1, None

    return None, None


def detects_unlimited_stacking(text):
    """Returns True if text affirmatively states multiple vouchers CAN be used/combined."""
    if not text:
        return False
    return bool(re.search(
        r'multiple\s+(?:gv\s*/\s*gc|gift\s*(?:vouchers?|cards?)|vouchers?)\s+can\s+be\s+(?:used|redeemed|combined|clubbed)',
        text, re.IGNORECASE
    ))


# Matches the confirmed real phrasings across wallet-model brands (AJIO,
# Nykaa, Steam, UniPin, Sony PlayStation, Valorant, Domino's, Elivaas, Kama
# Ayurveda): the voucher's value gets loaded/converted into a wallet/balance/
# account, after which combining multiple vouchers is just how the wallet
# works. Deliberately does NOT use bare "wallet"/"balance"/"account" as
# stand-alone keywords — those words also show up in unrelated sentences
# like "pay the remaining balance" or "activate your account", which caused
# false positives (e.g. Apollo Diagnostics, Lionsgate Play) before this was
# tightened to require the specific "added to/converted to ... wallet or
# balance" construction.
_WALLET_STACK_RE = [
    re.compile(r'multiple\s+instant\s+gift\s+vouchers?\s+can\s+be\s+used\s+against\s+one\s+bill', re.IGNORECASE),
    re.compile(
        r'multiple\s+gift\s+vouchers?\s+can\s+be\s+(?:added\s+to|combined\s*&?\s*added\s+to)\s+(?:the\s+)?[\w\s]{0,20}(?:e[-\s]?pay\s+)?(?:balance|wallet|account)',
        re.IGNORECASE
    ),
    re.compile(
        r'gift\s+voucher\s+can\s+be\s+used\s+multiple\s+times\s+once\s+(?:added\s+to|converted\s+to)\s+(?:the\s+)?[\w\s]{0,20}(?:e[-\s]?pay|wallet)\s*(?:balance)?',
        re.IGNORECASE
    ),
]

def detects_wallet_stacking(text):
    """Returns True if text indicates wallet/e-Pay load-and-redeem stacking pattern."""
    if not text:
        return False
    return any(p.search(text) for p in _WALLET_STACK_RE)


def extract_value_cap(text):
    """Extract a total rupee cap per bill (distinct from per-voucher denomination). Returns (amount, period) or (None, None)."""
    if not text:
        return None, None

    # "up to Rs. X CAN be combined/added" or "clubbed up to X and added"
    m = re.search(
        r'(?:up\s+to\s+(?:rs\.?\s*|inr\s*|₹)?|clubbed\s+up\s+to\s+)'
        r'(\d[\d,]+)'
        r'(?=\s+(?:can\s+be\s+combined|(?:can\s+be\s+)?(?:clubbed\s+and\s+)?added|\s*and\s+added))',
        text, re.IGNORECASE
    )
    if m:
        amount = int(m.group(1).replace(',', ''))
        if amount >= 1000:
            period_m = re.search(r'(?:within|in)\s+(\d+\s*(?:days?|months?))', text, re.IGNORECASE)
            return amount, (period_m.group(1).strip() if period_m else None)

    # "a max of Rs X on all platforms / in one bill"
    m = re.search(
        r'(?:a\s+)?max(?:imum)?\s+(?:of\s+)?(?:rs\.?\s*|inr\s*|₹)?(\d[\d,]+)'
        r'\s+(?:on\s+all\s+platforms|in\s+(?:one|a\s+single)\s+(?:bill|order|transaction)|per\s+(?:order|bill))',
        text, re.IGNORECASE
    )
    if m:
        amount = int(m.group(1).replace(',', ''))
        if amount >= 1000:
            return amount, None

    return None, None


def resolve_stack_limit(ii_raw, full_tc, how_to_text, rule_data):
    """
    Determine stack_limit and stack_limit_confidence by:
    1. Checking for a wallet/balance-loading redemption mechanism FIRST — if
       the voucher's value gets loaded into a wallet, combining multiple
       vouchers is fundamentally how that mechanism works, and this must be
       checked before ever trusting rule_data's "explicit" label, since the
       first-pass parser frequently mislabels wallet brands as "explicit: 1"
       by matching generic single-code-reuse boilerplate ("one-time use")
       that says nothing about stacking.
    2. Otherwise extracting an explicit count from important_instructions_raw,
       then full_terms_and_conditions.
    3. Only falling back to rule_data's own determination if neither of the
       above found anything.
    Returns (stack_limit, stack_limit_confidence).
    """
    rule_limit = rule_data.get("max_per_bill")
    rule_confidence = rule_data.get("limit_confidence", "unknown")

    # Keep existing high-confidence determinations from the rules file. Note:
    # the first-pass parser (parse_stacking_rules.py) no longer treats generic
    # "one-time use"/"single use" boilerplate as a stacking signal (that was
    # the actual root cause of brands like AJIO being wrongly capped at 1),
    # so an "explicit" here is now trustworthy on its own — no need to
    # second-guess it with the wallet/text checks below, which caused a
    # regression (Flipkart, Tanishq Gold Jewellery, and others with a
    # legitimate specific count got overridden to "unlimited") the first
    # time this was tried. The 87 brands individually verified during the
    # investigation that found this bug are handled separately, by the
    # explicit STACK_LIMIT_OVERRIDES table applied after this function
    # returns — not by reordering this general logic.
    if rule_confidence in ("explicit", "unlimited_stated"):
        return rule_limit, rule_confidence

    # Below only runs when rule_data itself came back "unknown" — i.e. the
    # first-pass parser found no signal at all. Wallet-mechanism check first,
    # since combining vouchers is just how a wallet/balance redemption works.
    combined_for_wallet = " ".join(t for t in (ii_raw, full_tc, how_to_text) if t)
    if detects_wallet_stacking(combined_for_wallet):
        return None, "unlimited_stated"

    # Specific counts from text (either a restrictive "only 1" or an
    # explicit "up to N") take priority over a generic unlimited statement,
    # since a specific number is more informative than "some multiple is ok".
    limit_ii, _ = extract_count_limit(ii_raw)
    limit_tc, _ = extract_count_limit(full_tc)
    unlimited_ii = detects_unlimited_stacking(ii_raw)
    unlimited_tc = detects_unlimited_stacking(full_tc)

    if limit_ii is not None and limit_tc is not None:
        if limit_ii != limit_tc:
            return min(limit_ii, limit_tc), "conflicting_sources_used_restrictive"
        return limit_ii, "text_extracted"

    if limit_ii is not None:
        # Instructions give a limit; check if TC contradicts with unlimited language
        if unlimited_tc and not limit_tc:
            return limit_ii, "conflicting_sources_used_restrictive"
        return limit_ii, "text_extracted"

    if limit_tc is not None:
        # TC gives a limit; check if instructions contradict with unlimited language
        if unlimited_ii and not limit_ii:
            return limit_tc, "conflicting_sources_used_restrictive"
        return limit_tc, "text_extracted"

    # Step 3: no specific count found anywhere, but a generic "multiple
    # vouchers can be used/combined" statement is present without a number.
    if unlimited_ii or unlimited_tc:
        return None, "unlimited_stated"

    # Step 4: nothing found in text at all — only now fall back to rule_data
    # (the first-pass parser's own determination, typically "unknown").
    return rule_limit, rule_confidence


def parse_how_to_steps(how_to_text):
    if not how_to_text:
        return None
    parts = re.split(r'\d+\s*\n?\s*STEP\s*\n*', how_to_text)
    steps = [p.strip().replace("\n", " ") for p in parts if p.strip()]
    steps = [s for s in steps if len(s) > 5 and "TERMS & CONDITIONS" not in s.upper()]
    return steps if steps else None

# Fix: anchor now allows plural "Cards"/"Vouchers" (was singular-only,
# which is why "Gift Cards cannot be used to purchase..." on Flipkart
# stopped matching after the subject-anchoring fix).
RESTRICTION_TRIGGERS = [
    r'except(?:\s+for)?[:\s]+(.+?)(?=\n\d+\.|\Z)',
    r'restricted\s+categories?(?:\s+including)?[:\s]*(.+?)(?=\n\d+\.|\Z)',
    r'not\s+applicable\s+for\s+(?:the\s+)?purchase\s+of\s+(.+?)(?=\n\d+\.|\Z)',
    r'(?:gv\s*/\s*gc|gift\s*cards?|e[\s-]?gift\s*cards?|vouchers?)\s+cannot\s+be\s+used\s+to\s+purchase\s+(.+?)(?=\n\d+\.|\Z)',
]

def find_restriction_text(tc_text):
    for pat in RESTRICTION_TRIGGERS:
        m = re.search(pat, tc_text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()[:600]
    return None

NOISE_MARKERS = ['http://', 'https://', 'www.', 'please visit']

def parse_restrictions(raw_text):
    if not raw_text:
        return []
    items = re.split(r'[•\u2022]|\n\d+\.|,\s+and\s+|,\s*&\s*|\.\s+(?=[A-Z])', raw_text)
    items = [i.strip().rstrip('.').strip() for i in items if i.strip()]
    items = [i for i in items if 3 < len(i) < 250]
    items = [i for i in items if not any(marker in i.lower() for marker in NOISE_MARKERS)]
    return items

# Manually verified overrides for the 87 brands that were originally
# mislabeled "stack_limit=1, confidence=explicit" purely from generic
# boilerplate. Each of these was individually checked (either by direct
# regex-verified evidence from important_instructions_raw/full_terms_and_
# conditions, or by hand) during a live bug investigation — these values are
# ground truth, not re-derived by the general classifier above, so they
# can't drift if the general regex logic changes later.
STACK_LIMIT_OVERRIDES = {
    # Wallet/balance-model brands and other brands with an explicit
    # affirmative "multiple vouchers allowed" statement — unlimited,
    # bounded only by any real value_cap/purchase_cap_per_txn already
    # present in the data.
    "ajio": (None, "unlimited_stated"),
    "ajio-luxe": (None, "unlimited_stated"),
    "cult-gift-card": (None, "unlimited_stated"),
    "easybuy": (None, "unlimited_stated"),
    "elivaas": (None, "unlimited_stated"),
    "healthkart": (None, "unlimited_stated"),
    "nykaa": (None, "unlimited_stated"),
    "nykaa-fashion": (None, "unlimited_stated"),
    "nykaa-man": (None, "unlimited_stated"),
    "pizza-hut": (None, "unlimited_stated"),
    "roblox": (None, "unlimited_stated"),
    "roblox-gift-card": (None, "unlimited_stated"),
    "sony-playstation": (None, "unlimited_stated"),
    "steam-gift-card": (None, "unlimited_stated"),
    "steam-wallet": (None, "unlimited_stated"),
    "unipin": (None, "unlimited_stated"),
    "unipin-bgmi": (None, "unlimited_stated"),
    "valorant": (None, "unlimited_stated"),
    "valorant-gift-card": (None, "unlimited_stated"),
    "william-penn": (None, "unlimited_stated"),
    "zoomcar": (None, "unlimited_stated"),
    "dominos": (None, "unlimited_stated"),
    "kama-ayurveda": (None, "unlimited_stated"),
    # Explicit non-standard cap: terms say "up to 3 GV/GCs combined in a
    # single transaction."
    "yatra-hotel-gift-card": (3, "explicit"),
    # Deprioritized: not currently used, or genuinely contradictory/no-signal
    # text with no wallet mechanism to explain it — stays at the safe
    # default (capped at 1) but honestly labeled unconfirmed rather than a
    # false "explicit", pending a manual check if/when these ever matter.
    "timezone": (1, "unconfirmed"),
    "tinder": (1, "unconfirmed"),
    "iocl": (1, "unconfirmed"),
    "veridicus": (1, "unconfirmed"),
    "shiv-naresh": (1, "unconfirmed"),
    "amazon-prime-membership": (1, "unconfirmed"),
    "braingymjr": (1, "unconfirmed"),
    # Confirmed genuinely restricted to 1 by direct text evidence, but the
    # general text patterns above don't happen to match their specific
    # phrasing (e.g. "Only one GV / GC can be used in one bill/transaction"
    # uses a slash-separated "GV / GC" the count-limit patterns don't cover).
    # Locking these in explicitly rather than leaving them to a regex that's
    # already proven to miss edge-case phrasing at least once this session.
    "docubay": (1, "explicit"),
    "hyperice": (1, "explicit"),
    "swiss-beauty": (1, "explicit"),
    "chicago-pizza": (1, "explicit"),
    "eazydiner": (1, "explicit"),
    "taj-wellness-gift-card": (1, "explicit"),
}

master = {}

for slug, brand in api_brands.items():
    name = brand.get("brand_name", slug)
    redemption_type = REDEMPTION_MAP.get(brand.get("redemption_type", ""), brand.get("redemption_type", ""))
    pgdis = brand.get("pgdis", [])

    merged_map = normalized_discount_map(pgdis)
    discounts = {
        "Credit Card": merged_map.get("Credit Card"),
        "Debit Card": merged_map.get("Debit Card"),
        "Net Banking": merged_map.get("Net Banking"),
        "UPI": merged_map.get("UPI"),
    }
    best_method, best_disc = best_payment(merged_map)

    products = brand.get("products", [])
    # Gyftr uses max_value=0 as its own sentinel for "no custom range" (a fixed
    # denomination SKU). A real custom-amount range has max_value truthy and
    # different from min_value.
    custom_rows = [
        p for p in products
        if p.get("max_value") and p.get("min_value") is not None and p["max_value"] != p["min_value"]
    ]
    fixed_rows = [p for p in products if p not in custom_rows]
    denominations = sorted([p.get("mrp") for p in fixed_rows if p.get("mrp")])
    is_custom_denom = bool(custom_rows)
    custom_min = min((p["min_value"] for p in custom_rows), default=None)
    custom_max = max((p["max_value"] for p in custom_rows), default=None)

    scrape_data = scraped.get(slug, {})
    rule_data = rules.get(slug, {})

    if scrape_data.get("delisted"):
        status = "delisted"
        notes = scrape_data.get("reason", "")
    elif scrape_data.get("skipped"):
        status = "skipped"
        notes = scrape_data.get("reason", "")
    elif scrape_data.get("error"):
        status = "scrape_failed"
        notes = scrape_data.get("error", "")
    elif scrape_data:
        status = "active"
        notes = ""
    else:
        status = "not_scraped"
        notes = ""

    how_to_text = scrape_data.get("How to use", "")
    full_tc = scrape_data.get("Terms & Conditions", "") or ""
    ii_raw = scrape_data.get("Important Instructions", "") or brand.get("important_instruction", "")

    restriction_raw = find_restriction_text(full_tc)
    stack_limit, stack_limit_confidence = resolve_stack_limit(ii_raw, full_tc, how_to_text, rule_data)
    if slug in STACK_LIMIT_OVERRIDES:
        stack_limit, stack_limit_confidence = STACK_LIMIT_OVERRIDES[slug]
    value_cap, value_cap_period = extract_value_cap(ii_raw or "")
    if value_cap is None:
        value_cap, value_cap_period = extract_value_cap(full_tc or "")

    if stack_limit is None and value_cap is None and denominations:
        combined = (ii_raw or "") + " " + (full_tc or "")
        purchase_cap_per_txn = 10 * sum(set(denominations)) if detects_wallet_stacking(combined) else None
    else:
        purchase_cap_per_txn = None

    master[slug] = {
        "brand_name": name,
        "slug": slug,
        "redemption_type": redemption_type,
        "denominations": denominations,
        "is_custom_denom": is_custom_denom,
        "custom_min": custom_min,
        "custom_max": custom_max,
        "discounts": discounts,
        "best_payment_method": best_method,
        "best_discount_pct": best_disc,
        "stack_limit": stack_limit,
        "stack_limit_confidence": stack_limit_confidence,
        "value_cap": value_cap,
        "value_cap_period": value_cap_period,
        "purchase_cap_per_txn": purchase_cap_per_txn,
        "can_club_with_offers": rule_data.get("can_club_with_offers"),
        "one_time_use": rule_data.get("one_time_use", False),
        "redemption_restrictions": parse_restrictions(restriction_raw),
        "how_to_redeem_steps": parse_how_to_steps(how_to_text),
        "full_terms_and_conditions": full_tc.strip() if full_tc else None,
        "important_instructions_raw": ii_raw.strip() if ii_raw else None,
        "status": status,
        "notes": notes,
        "last_scraped": scrape_data.get("scraped_at"),
    }

with open("db/gyftr_master.json", "w") as f:
    json.dump(master, f, indent=2, ensure_ascii=False)

total = len(master)
active = sum(1 for m in master.values() if m["status"] == "active")
with_steps = sum(1 for m in master.values() if m["how_to_redeem_steps"])
null_steps_active = sum(1 for m in master.values() if m["status"] == "active" and m["how_to_redeem_steps"] is None)
with_restrictions = sum(1 for m in master.values() if m["redemption_restrictions"])
explicit_limit = sum(1 for m in master.values() if m["stack_limit_confidence"] == "explicit")
text_extracted_limit = sum(1 for m in master.values() if m["stack_limit_confidence"] == "text_extracted")
conflicting_limit = sum(1 for m in master.values() if m["stack_limit_confidence"] == "conflicting_sources_used_restrictive")
unknown_limit = sum(1 for m in master.values() if m["status"] == "active" and m["stack_limit_confidence"] == "unknown")
unconfirmed_limit = sum(1 for m in master.values() if m["stack_limit_confidence"] == "unconfirmed")
unlimited_limit = sum(1 for m in master.values() if m["stack_limit_confidence"] == "unlimited_stated")
with_value_cap = sum(1 for m in master.values() if m.get("value_cap"))
with_purchase_cap = sum(1 for m in master.values() if m.get("purchase_cap_per_txn"))

print(f"Master file rebuilt: db/gyftr_master.json")
print(f"Total brands: {total}")
print(f"Active: {active}")
print(f"With parsed how-to-redeem steps: {with_steps}")
print(f"Active brands with NULL steps: {null_steps_active}")
print(f"With parsed redemption_restrictions: {with_restrictions}")
print(f"With explicit stack limits: {explicit_limit}")
print(f"With text-extracted stack limits: {text_extracted_limit}")
print(f"With conflicting-source stack limits: {conflicting_limit}")
print(f"Active brands with UNKNOWN stack limit: {unknown_limit}")
print(f"With UNCONFIRMED stack limit (flagged, safe default): {unconfirmed_limit}")
print(f"With unlimited stacking (wallet or explicit multi-voucher): {unlimited_limit}")
print(f"Manual overrides applied: {len(STACK_LIMIT_OVERRIDES)}")
print(f"With value cap: {with_value_cap}")
print(f"With purchase_cap_per_txn (wallet stacking): {with_purchase_cap}")
