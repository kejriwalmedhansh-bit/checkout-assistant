"""Read each voucher's rules with the model instead of pattern-matching them.

Regexes were the wrong tool here. Gyftr's Tanishq page says "10 vouchers can be
used in a single transaction" and the extractor missed it, because it demanded
the words "up to" or "maximum" in front of the number — while a different page's
"up to 45% off on vouchers" sailed through as a 45-voucher limit. 204 of Gyftr's
366 brands state a per-bill limit in plain English; the pattern matcher found
none of them.

Every field must come back with the sentence it came from, quoted verbatim.
A rule Dealo cannot quote is a rule Dealo should not state.

Resumable: results are checkpointed, and a listing already read is skipped.
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import threading
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "voucher_rules_read.json"
MODEL = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "works_online": {"type": "string", "enum": ["yes", "no", "not_stated"]},
        "works_in_store": {"type": "string", "enum": ["yes", "no", "not_stated"]},
        "one_time_use": {"type": "string", "enum": ["yes", "no", "not_stated"]},
        "max_vouchers_per_bill": {"type": ["integer", "string"],
                                  "description": "a number, \"unlimited\", or \"not_stated\""},
        "can_combine_with_store_offers": {"type": "string", "enum": ["yes", "no", "not_stated"]},
        "spend_scope": {"type": "string",
                        "description": "what the voucher may be spent on, or not_stated"},
        "excludes": {"type": "array", "items": {"type": "string"},
                     "description": "products or categories it will not buy"},
        "min_order_value": {"type": ["number", "string"]},
        "max_spend_per_purchase": {"type": ["number", "string"]},
        "monthly_purchase_cap": {"type": ["number", "string"]},
        "validity": {"type": "string"},
        "delivery_wait": {"type": "string"},
        "partial_redemption": {"type": "string", "enum": ["yes", "no", "not_stated"]},
        "quotes": {
            "type": "object",
            "description": "field name -> the exact sentence from the source that supports it",
            "additionalProperties": {"type": "string"},
        },
    },
    "required": ["works_online", "works_in_store", "one_time_use", "max_vouchers_per_bill",
                 "can_combine_with_store_offers", "spend_scope", "excludes", "min_order_value",
                 "max_spend_per_purchase", "monthly_purchase_cap", "validity", "delivery_wait",
                 "partial_redemption", "quotes"],
    "additionalProperties": False,
}

SYSTEM = """You read gift-card terms and report what they say, for a shopping
assistant that tells people which voucher to buy and how to use it.

Rules:
- Report only what the text states. Never infer, never fill a gap with what is
  usually true. Anything the text does not address is "not_stated" (or an empty
  list, for excludes).
- For every field you do not mark not_stated, put the exact sentence that
  supports it in "quotes", copied verbatim from the source. No sentence, no
  claim.
- max_vouchers_per_bill is how many gift vouchers the shop accepts in ONE bill.
  "10 vouchers can be used in a single transaction" is 10. "Multiple Gift
  Vouchers CAN be used in one bill" is "unlimited". A percentage discount
  ("up to 45% off on vouchers") is not a voucher count — that is not_stated.
- spend_scope is what the voucher may be spent on when that is narrower than
  the brand as a whole: "Seat Selection, Extra Baggage and Sports Equipment",
  "Food & Non-Alcoholic beverages", "Gold Jewellery only". If it buys anything
  the brand sells, that is not_stated.
- monthly_purchase_cap is a limit on buying vouchers; max_spend_per_purchase is
  a limit on spending them. Keep them apart.
- partial_redemption is whether unused balance survives. "Unused balance will be
  forfeited" is no. "Valid for partial redemption" is yes.
- Terms are written by three different platforms and are often repetitive or
  contradictory. Where a page contradicts itself, prefer the more specific
  statement and quote that one."""

_lock = threading.Lock()


def source_text(rec: dict) -> str:
    raw = rec["raw"]
    parts = []
    for label, key in (("IMPORTANT INSTRUCTIONS", "important_instruction"),
                       ("CHECKOUT INSTRUCTIONS", "checkout_instruction"),
                       ("VOUCHER RESTRICTIONS", "restrictions"),
                       ("HOW TO REDEEM", "how_to_redeem"),
                       ("FAQS", "faqs"),
                       ("TERMS & CONDITIONS", "full_terms")):
        v = raw.get(key)
        if v:
            parts.append(f"## {label}\n{v}")
    if boxes := raw.get("info_boxes"):
        parts.append("## STATED ANSWERS\n" + "\n".join(f"{k} {v}" for k, v in boxes.items()))
    return "\n\n".join(parts)


def read_one(client, key: str, rec: dict) -> tuple[str, dict]:
    text = source_text(rec)
    if not text.strip():
        return key, {"error": "no terms text collected"}
    msg = (f"Gift card: {rec['brand_name']} (sold on {rec['source']})\n\n"
           f"{text}\n\n"
           "Report what these terms state, following your instructions exactly.")
    resp = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": msg}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    out["_usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    return key, out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["gyftr", "buyhatke", "maximize"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", help="comma-separated brand names, for spot checks")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
    client = anthropic.Anthropic()

    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = []
    for src in ([args.source] if args.source else ["gyftr", "buyhatke", "maximize"]):
        path = REPO / "data" / f"voucher_terms_raw_{src}.json"
        for key, rec in json.loads(path.read_text()).items():
            if "error" in rec or key in out:
                continue
            if args.only and rec["brand_name"].lower() not in {
                    n.strip().lower() for n in args.only.split(",")}:
                continue
            todo.append((key, rec))
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} listings to read | {len(out)} already done", flush=True)

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(read_one, client, k, r) for k, r in todo]
        for f in concurrent.futures.as_completed(futures):
            try:
                key, result = f.result()
            except Exception as exc:
                print(f"  ! {str(exc)[:120]}", flush=True)
                continue
            with _lock:
                out[key] = result
                done += 1
                if done % 25 == 0:
                    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
                    print(f"  {done}/{len(todo)}", flush=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    tin = sum(v.get("_usage", {}).get("in", 0) for v in out.values())
    tout = sum(v.get("_usage", {}).get("out", 0) for v in out.values())
    print(f"done — {len(out)} listings | {tin:,} in / {tout:,} out tokens "
          f"| ${tin/1e6*5 + tout/1e6*25:.2f} at Opus 5 rates", flush=True)


if __name__ == "__main__":
    sys.exit(main())
