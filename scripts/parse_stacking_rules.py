import json, re

with open("db/gyftr_full_scrape_progress.json") as f:
    scraped = json.load(f)

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

LIMIT_PATTERNS = [
    r'only\s+(\d+)\s+gift\s+vouchers?\s+can\s+be\s+clubbed',
    r'only\s+(\d+)\s+(?:gift\s+)?vouchers?\s+(?:can\s+be\s+used|per\s+(?:bill|day|transaction))',
    r'(?:maximum|max)\s+(?:of\s+)?(\d+)\s+(?:gift\s+)?vouchers?',
    r'(\d+)\s+(?:gift\s+)?vouchers?\s+per\s+(?:bill|day|transaction)',
    r'limit\s+of\s+(\d+)\s+gv',
    r'only\s+(one|two|three|four|five)\s+(?:gift\s+)?vouchers?\s+can',
]

NO_STACK_PATTERNS = [
    r'cannot\s+be\s+used\s+multiple\s+times',
    r'one[\s-]time\s+use',
    r'single\s+use',
    r'only\s+one\s+(?:gift\s+)?voucher\s+can\s+be\s+used',
]

# "Cannot be used multiple times" / "single use" describe an individual voucher
# being non-reusable, NOT a per-bill stacking cap — brands routinely say both
# "up to N vouchers can be used in one bill" AND "[each] voucher cannot be used
# multiple times" in the same T&C. Check for an explicit multi-voucher count
# first so NO_STACK_PATTERNS doesn't wrongly collapse a real N-voucher stacking
# allowance down to 1.
UP_TO_N_PATTERNS = [
    r'up\s*to\s+(\d+)\s*(?:gift\s+)?vouchers?\s+can\s+be\s+used',
    r'\(?up\s*to\s+(\d+)\)?\s+can\s+be\s+used',
]

MULTI_OK_PATTERNS = [
    r'multiple\s+gift\s+vouchers?\s+can\s+be\s+used',
    r'multiple\s+gvs?\s+can\s+be\s+used',
]

CANNOT_CLUB_OFFERS_PATTERNS = [
    r'cannot\s+be\s+clubbed\s+with\s+(?:existing\s+)?offers?',
    r'cannot\s+be\s+clubbed\s+with\s+any\s+(?:existing\s+)?offers?',
]

CAN_CLUB_OFFERS_PATTERNS = [
    r'can\s+be\s+clubbed\s+with\s+(?:existing\s+)?offers?',
    r'can\s+be\s+clubbed\s+with\s+discounts?',
]

def find_limit(text_lower):
    for pat in LIMIT_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            val = m.group(1)
            if val in NUMBER_WORDS:
                return NUMBER_WORDS[val]
            return int(val)
    return None

def any_match(patterns, text_lower):
    return any(re.search(p, text_lower) for p in patterns)

def find_up_to_n(text_lower):
    for pat in UP_TO_N_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            n = int(m.group(1))
            if n <= 20:  # sanity bound — real per-bill voucher counts are small
                return n
    return None

def parse_brand(slug, data):
    ii = (data.get("Important Instructions") or "").lower()
    tc = (data.get("Terms & Conditions") or "").lower()
    how_to = (data.get("How to use") or "").lower()
    combined = ii + " " + tc + " " + how_to

    result = {"slug": slug}

    limit = find_limit(combined)
    up_to_n = find_up_to_n(combined)
    if limit is not None:
        result["max_per_bill"] = limit
        result["limit_confidence"] = "explicit"
    elif up_to_n is not None:
        result["max_per_bill"] = up_to_n
        result["limit_confidence"] = "explicit"
    elif any_match(MULTI_OK_PATTERNS, combined):
        # Checked before NO_STACK_PATTERNS: "multiple vouchers can be used" is
        # an affirmative stacking statement and must win over a same-brand
        # "voucher cannot be used multiple times" disclaimer, which describes
        # single-voucher reuse (a different question), not a per-bill cap.
        result["max_per_bill"] = None
        result["limit_confidence"] = "unlimited_stated"
    elif any_match(NO_STACK_PATTERNS, combined):
        result["max_per_bill"] = 1
        result["limit_confidence"] = "explicit"
    else:
        result["max_per_bill"] = None
        result["limit_confidence"] = "unknown"

    if any_match(CANNOT_CLUB_OFFERS_PATTERNS, combined):
        result["can_club_with_offers"] = False
    elif any_match(CAN_CLUB_OFFERS_PATTERNS, combined):
        result["can_club_with_offers"] = True
    else:
        result["can_club_with_offers"] = None

    result["one_time_use"] = bool(re.search(r'one[\s-]time\s+use', combined))

    excl_match = re.search(r'except(?:\s+for)?[:\s]+(.{0,600})', tc)
    if excl_match:
        result["exclusions_raw"] = excl_match.group(1).strip()[:600]
    else:
        result["exclusions_raw"] = None

    result["has_source_text"] = bool(ii or tc or how_to)
    return result

rules = {}
needs_review = []

for slug, data in scraped.items():
    if data.get("delisted") or data.get("skipped") or data.get("error"):
        continue
    parsed = parse_brand(slug, data)
    rules[slug] = parsed
    if parsed["limit_confidence"] == "unknown" and parsed["has_source_text"]:
        needs_review.append(slug)

with open("db/gyftr_stacking_rules.json", "w") as f:
    json.dump(rules, f, indent=2)

explicit = sum(1 for r in rules.values() if r["limit_confidence"] == "explicit")
unlimited_stated = sum(1 for r in rules.values() if r["limit_confidence"] == "unlimited_stated")
unknown = sum(1 for r in rules.values() if r["limit_confidence"] == "unknown")

print(f"Parsed {len(rules)} brands (now scanning Important Instructions + T&C + How to Use).")
print(f"  Explicit numeric/1x limit found: {explicit}")
print(f"  Stated as multi-voucher OK (no cap given): {unlimited_stated}")
print(f"  Unknown/unclear (treated as cautious by default): {unknown}")
print(f"\nSaved to db/gyftr_stacking_rules.json")
