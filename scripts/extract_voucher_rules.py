"""Read each voucher's own terms and turn them into a standard set of answers.

Why this exists
---------------
Every rule Dealo needs is written down in the brands' terms, which we already
scrape and store. The problem has never been missing text — it's that we
compress that text into a few numeric fields with hand-written patterns, and
everything downstream then trusts the numbers over the words.

Two live examples of that going wrong (both found by the user, 2026-09-02):

  * Amazon's "Gift Vouchers over INR 50,000 CANNOT be added to wallet per
    calendar month" sat in the terms while the structured data recorded no
    ceiling at all — so Dealo told a shopper to buy ₹60,403 of credit.
  * BuyHatke's Myntra listing carried a ₹2,500 "cap" from a broken API field
    while its own terms said "Multiple E-Gift Cards can be clubbed in a single
    order" — costing ₹80 of savings on a single basket.

A regex scan of Gyftr alone shows the scale: 282 brands' terms discuss whether
vouchers combine with store offers; the parser recorded 117 of them. Of the 165
it missed, 54 say *no* — brands like Titan ("not applicable on discounted
products and cannot be clubbed with any other offer"), where Dealo would
currently recommend a voucher that the store will refuse.

What this does
--------------
Reads the terms with a model and fills one standard schema per brand per
source. Every answer carries the verbatim sentence it came from, and any quote
that does not appear in the source text is REJECTED and the field falls back to
"not stated" — so a rule cannot be invented, only cited.

Three states everywhere: yes / no / not_stated. "The terms don't say" is a real
answer, never silently converted into a guess — collapsing it is exactly how
both bugs above happened.

Store rules vs seller rules are kept apart, because the same brand genuinely
differs across sellers: Maximize's Myntra card is one-time-use where Gyftr's
isn't, Gyftr's Nykaa card works in store where BuyHatke's is online only, and
BuyHatke's AJIO card is not valid on H&M products — a restriction that appears
on no other source.

Usage
-----
    export ANTHROPIC_API_KEY=...          # or `ant auth login`
    python3.11 scripts/extract_voucher_rules.py --limit 20        # pilot
    python3.11 scripts/extract_voucher_rules.py                   # everything

Writes data/voucher_rules.json, keyed "{source}:{slug}".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
SOURCES = {"gyftr": "Gyftr", "maximize": "Maximize", "buyhatke": "BuyHatke"}
OUT_PATH = REPO / "data" / "voucher_rules.json"

# Trimmed hard, because terms run to thousands of characters of boilerplate
# about issuing banks and RBI authorisation that answer none of our questions.
MAX_TERMS_CHARS = 12_000

TRISTATE = {"type": "string", "enum": ["yes", "no", "not_stated"]}


def field(description: str, value_schema: dict) -> dict:
    """One answer plus the sentence that justifies it."""
    return {
        "type": "object",
        "description": description,
        "properties": {
            "value": value_schema,
            "evidence": {
                "type": "string",
                "description": (
                    "The exact sentence from the terms that states this, copied "
                    "verbatim. Empty string when the terms do not state it."
                ),
            },
        },
        "required": ["value", "evidence"],
        "additionalProperties": False,
    }


NUMBER_OR_NULL = {"type": ["number", "null"]}

SCHEMA = {
    "type": "object",
    "properties": {
        # --- what the STORE allows (true whoever sold the voucher) ---
        "can_combine": field(
            "Can several gift cards be used together on one order at the store?",
            TRISTATE,
        ),
        "max_cards_per_order": field(
            "How many gift cards the store accepts on one order. null if not stated.",
            NUMBER_OR_NULL,
        ),
        "ceiling_amount": field(
            "A rupee ceiling on how much can be loaded or redeemed in a period, "
            "e.g. Amazon's 50000 per calendar month. null if not stated.",
            NUMBER_OR_NULL,
        ),
        "ceiling_period": field(
            "The period that ceiling applies over, e.g. 'calendar month'.",
            {"type": ["string", "null"]},
        ),
        "one_time_use": field(
            "Must the whole value be spent at once, losing any balance?",
            TRISTATE,
        ),
        "works_online": field("Can it be used on the website or app?", TRISTATE),
        "works_in_store": field("Can it be used at a physical store?", TRISTATE),
        "works_on_sale_items": field(
            "Can it be used on discounted or sale-price items?", TRISTATE
        ),
        "combines_with_store_offers": field(
            "Can it be used together with the store's own offers, coupons or promotions?",
            TRISTATE,
        ),
        "min_order_value": field(
            "A minimum order value required to use it. null if not stated.",
            NUMBER_OR_NULL,
        ),
        "excludes": {
            "type": "object",
            "description": "Product categories or brands this voucher cannot buy.",
            "properties": {
                "value": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "string"},
            },
            "required": ["value", "evidence"],
            "additionalProperties": False,
        },
        # --- what the SELLER allows (only for vouchers bought from them) ---
        "max_spend_per_purchase": field(
            "A limit on how much can be bought in one order FROM THE SELLER, as "
            "opposed to a limit on redeeming at the store. null if not stated.",
            NUMBER_OR_NULL,
        ),
        "delivery_wait_days": field(
            "How many days before the code arrives. 0 for instant. null if not stated. "
            "This matters: a voucher that takes days cannot be used on a checkout today.",
            NUMBER_OR_NULL,
        ),
    },
    "required": [
        "can_combine", "max_cards_per_order", "ceiling_amount", "ceiling_period",
        "one_time_use", "works_online", "works_in_store", "works_on_sale_items",
        "combines_with_store_offers", "min_order_value", "excludes",
        "max_spend_per_purchase", "delivery_wait_days",
    ],
    "additionalProperties": False,
}

SYSTEM = """You read Indian gift-voucher terms and conditions and answer a fixed set of questions about them.

Rules you must follow:

1. Answer ONLY from the text given. Never use outside knowledge about the brand.
2. If the text does not state something, the answer is "not_stated" (or null). This
   is a normal, expected answer — do not infer, do not assume the common case.
3. Every answer must carry `evidence`: the exact sentence from the text, copied
   character for character. Do not paraphrase, do not trim, do not fix typos.
   If the answer is "not_stated" or null, evidence must be an empty string.
4. Distinguish two different things carefully:
   - limits on REDEEMING at the store (how many cards the store accepts, monthly
     wallet ceilings)
   - limits on BUYING from the voucher seller (how much you may purchase in one
     order on their site)
   A seller's purchase limit is NOT a store redemption limit.
5. "Multiple gift cards can be clubbed" means can_combine = yes.
   "Cannot be clubbed with other offers" is about combines_with_store_offers,
   which is a different question from can_combine.
6. Answer "no" when the text says something is NOT allowed. Do not soften a
   stated prohibition into "not_stated"."""


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s or ""))).strip()


def terms_text(record: dict) -> str:
    parts = [
        record.get("important_instructions_raw"),
        record.get("full_terms_and_conditions"),
    ]
    seen, out = set(), []
    for p in parts:
        t = normalise(p)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return "\n".join(out)[:MAX_TERMS_CHARS]


def verify(extracted: dict, source_text: str) -> tuple[dict, list[str]]:
    """Drop any answer whose quote isn't actually in the terms.

    This is what makes the output trustworthy rather than plausible: a rule can
    only survive if the sentence supporting it really exists in the source.
    """
    haystack = normalise(source_text).lower()
    rejected = []
    for name, ans in extracted.items():
        if not isinstance(ans, dict):
            continue
        quote = normalise(ans.get("evidence")).lower()
        has_value = ans.get("value") not in (None, "not_stated", [])
        if not has_value:
            ans["evidence"] = ""
            continue
        if not quote or quote not in haystack:
            rejected.append(f"{name} (claimed: {str(ans.get('value'))[:40]})")
            ans["value"] = None if name.endswith(("_amount", "_days", "_value", "_order", "_purchase", "_period")) else "not_stated"
            if name == "excludes":
                ans["value"] = []
            ans["evidence"] = ""
            ans["rejected"] = True
    return extracted, rejected


def extract_one(client, model, source, slug, record) -> dict | None:
    text = terms_text(record)
    if len(text) < 80:
        return None
    brand = record.get("brand_name") or slug
    result = client.messages.parse(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": (
                f"Brand: {brand}\nSold by: {SOURCES[source]}\n\n"
                f"Terms and conditions:\n---\n{text}\n---"
            ),
        }],
    )
    parsed, rejected = verify(result.parsed, text)
    return {
        "brand_name": brand,
        "source": source,
        "slug": slug,
        "rules": parsed,
        "rejected_fields": rejected,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--limit", type=int, help="only this many brands per source (pilot runs)")
    ap.add_argument("--source", choices=list(SOURCES), help="just one source")
    ap.add_argument("--brands", help="comma-separated brand names to include")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    client = anthropic.Anthropic()
    wanted = [b.strip().lower() for b in args.brands.split(",")] if args.brands else None

    jobs = []
    for source in ([args.source] if args.source else SOURCES):
        data = json.loads((REPO / "data" / f"{source}_master.json").read_text())
        picked = 0
        for slug, record in data.items():
            name = (record.get("brand_name") or "").lower()
            if wanted and not any(w == name or w in name for w in wanted):
                continue
            jobs.append((source, slug, record))
            picked += 1
            if args.limit and picked >= args.limit:
                break

    print(f"reading the terms of {len(jobs)} listings with {args.model}\n", flush=True)
    out, failures = {}, 0

    def run(job):
        source, slug, record = job
        try:
            return extract_one(client, args.model, source, slug, record)
        except Exception as exc:  # one bad listing must not sink the run
            print(f"  ! {record.get('brand_name')} ({source}): {exc}", flush=True)
            return None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for job, result in zip(jobs, pool.map(run, jobs)):
            if result is None:
                failures += 1
                continue
            out[f"{result['source']}:{result['slug']}"] = result
            flag = f"  [rejected: {', '.join(result['rejected_fields'])}]" if result["rejected_fields"] else ""
            print(f"  {result['source']:9} {result['brand_name'][:34]:36}{flag}", flush=True)

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    rejected_total = sum(len(r["rejected_fields"]) for r in out.values())
    print(f"\nwrote {len(out)} listings to {args.out}")
    print(f"unusable listings: {failures}   answers rejected for a bad quote: {rejected_total}")


if __name__ == "__main__":
    sys.exit(main())
