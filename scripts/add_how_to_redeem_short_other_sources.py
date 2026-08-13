"""
Generate `how_to_redeem_short` directly from Maximize's and BuyHatke's own
`how_to_redeem_steps` data, in data/maximize_master.json and
data/buyhatke_master.json.

Same extraction rules as scripts/add_how_to_redeem_short_rulebased.py
(reused from there, not duplicated) -- this script only adapts the two
things that differ about these sources' schema:

1. Both files are read/written in place (unlike Gyftr, there's no separate
   flat db/ source of truth for these two -- data/*.json already is the
   canonical, cleaned schema; db/maximize_master.json is pre-normalization
   raw scrape data with an unrelated shape and has no equivalent for
   BuyHatke at all).
2. redemption_type lives one level down, on each brand's first product
   entry, not at brand-record top level (Gyftr's db/ schema is flat).

Before this, every Maximize/BuyHatke deal that won Dealo's price race fell
back to generic "add to cart, apply the code" copy regardless of the real
redemption mechanics, even though the real steps were already sitting in
this same data unused -- voucher_service.py's Gyftr-borrow fallback only
covers merchants that also happen to have a Gyftr listing.

Usage:
    python3.11 scripts/add_how_to_redeem_short_other_sources.py --preview
    python3.11 scripts/add_how_to_redeem_short_other_sources.py
"""

import argparse
import html
import json
import re
from pathlib import Path

from add_how_to_redeem_short_rulebased import OFFLINE_FIXED, find_candidate, has_needs_review

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "Maximize": REPO_ROOT / "data" / "maximize_master.json",
    "BuyHatke": REPO_ROOT / "data" / "buyhatke_master.json",
}

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(steps: list[str]) -> list[str]:
    """Gyftr's how_to_redeem_steps (what the imported extractor was written
    against) is plain text; BuyHatke's is raw HTML (<p>, <li>, entities like
    &lt; and &rdquo;) -- unstripped, that HTML leaks straight into the
    generated short text ("<p><strong>How -> enter voucher code + PIN")."""
    cleaned = []
    for s in steps:
        s = _TAG_RE.sub(" ", s or "")
        s = html.unescape(s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            cleaned.append(s)
    return cleaned


_DANGLING_QUOTE_RE = re.compile(r"[\"'‘’“”]\s*$")
_STOP_WORDS_RE = re.compile(r"^(how|use|steps?|redeem)$", re.I)
# Clauses that read as a sentence fragment rather than naming a place/action
# ("You can also", "IOS users can", "Registered UniPin users can also",
# "Click here", "Step 5") — grammatically valid sentences the extractor
# picked up, but not the kind of concrete "[Where]" this template needs.
_FRAGMENT_START_RE = re.compile(
    r"^(you|ios|android|registered|app\s+users|click\s+here|step\s*\d)", re.I
)


def is_trustworthy_where(where: str) -> bool:
    """The regex extractor sometimes produces a "where" that reads like
    real text but isn't -- a phrase truncated mid-quote ("Go to the '"), an
    HTML heading word left over after tag-stripping ("How"), or otherwise
    too thin to mean anything to someone actually reading it. Reject those
    rather than ship a confident-sounding sentence with no real content
    behind it -- the whole point of this pass is trustworthy instructions,
    not just non-empty ones."""
    if _DANGLING_QUOTE_RE.search(where):
        return False
    if "→" in where or _FRAGMENT_START_RE.match(where):
        return False
    words = where.split()
    if len(words) < 2 or len(words) > 8:
        # A real "[Where]" is a short location phrase ("On the payment
        # page") -- something this long is the extractor grabbing an
        # unrelated run-on clause, not a place name (e.g. PhonePe's
        # "Gift Card balance is selected as a default mode for making the
        # payment, you may").
        return False
    if all(_STOP_WORDS_RE.match(w) for w in words):
        return False
    return True


def brand_redemption_type(brand: dict) -> str | None:
    """Unlike Gyftr's flat db/ schema, redemption_type isn't a brand-level
    field here -- it lives on each product/tier. A brand's tiers are always
    the same real-world merchant, so the first product's value stands in
    for the whole brand (matches how offline_only is derived elsewhere in
    this codebase, e.g. voucher_service.build_deals)."""
    products = brand.get("products") or []
    return products[0].get("redemption_type") if products else None


def rule_based_short(brand: dict) -> tuple[str | None, str]:
    raw_steps = brand.get("how_to_redeem_steps")
    rtype = brand_redemption_type(brand)

    if not raw_steps or has_needs_review(raw_steps):
        return None, "null_missing_or_needs_review"

    steps = strip_html(raw_steps)
    if not steps:
        return None, "null_missing_or_needs_review"

    if rtype == "Offline":
        return OFFLINE_FIXED, "offline_fixed"

    if rtype in ("Online", "Both"):
        candidate = find_candidate(steps)
        if candidate is None:
            # No sentence in the real steps names a *specific* place/action
            # for the code — the same failure mode that produced the wrong
            # "At checkout" line for TATA CLiQ before (see voucher_service.py
            # commit history). Rather than guess, leave this null: the
            # frontend's existing generic fallback is honest about not
            # knowing, instead of stating something that might be wrong.
            return None, "online_no_specific_candidate_skipped"

        from add_how_to_redeem_short_rulebased import extract_where

        where = extract_where(candidate)
        if where == "At checkout":
            # extract_where itself fell back to the same generic phrase —
            # same reasoning as above, skip rather than assert a specific-
            # sounding claim with nothing concrete behind it.
            return None, "online_generic_where_skipped"
        if not is_trustworthy_where(where):
            return None, "online_low_quality_where_skipped"
        return f"{where} → enter voucher code + PIN", "online_extracted"

    return None, "null_missing_or_needs_review"


def process_file(path: Path, label: str, preview: bool) -> None:
    with open(path) as f:
        data = json.load(f)

    results = {}
    counts: dict[str, int] = {}
    for slug, brand in data.items():
        if brand.get("how_to_redeem_short"):
            continue  # don't overwrite anything already set (e.g. by hand)
        value, category = rule_based_short(brand)
        results[slug] = value
        counts[category] = counts.get(category, 0) + 1

    print(f"\n=== {label} ({path}) ===")
    print("Counts:", counts)
    shown = 0
    for slug, value in results.items():
        if value and shown < 10:
            print(f"  {slug}: {value}")
            shown += 1

    if preview:
        print(f"  (preview only -- nothing written for {label})")
        return

    updated = 0
    for slug, value in results.items():
        if value:
            data[slug]["how_to_redeem_short"] = value
            updated += 1
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote how_to_redeem_short for {updated} {label} brands into {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    for label, path in SOURCES.items():
        process_file(path, label, args.preview)


if __name__ == "__main__":
    main()
