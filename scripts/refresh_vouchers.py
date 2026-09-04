"""Fortnightly refresh — re-read only what actually changed.

The first build took most of a day because every listing was scraped and then
read from scratch. Almost none of that work needs repeating: prices move often,
terms almost never. A full re-harvest of Maximize's catalogue on 2026-09-04
returned exactly the same 410 products it had in August, and the terms text of a
typical brand is unchanged between scrapes.

So the refresh is staged by how fast each layer actually moves:

  every run     rates, denominations, stock      cheap, and the part that moves
  on change     the rules for a listing whose    the expensive part, skipped
                terms text differs from last     for the ~95% that did not move
  monthly       Maximize's catalogue harvest     ~3 hours, and it found nothing

This script does the middle layer: it fingerprints every listing's terms,
compares against the manifest from last time, and writes chunk files containing
ONLY the listings whose terms changed, plus brands that are new. Feed those to
the reading pass; carry everything else forward untouched.

  python scripts/refresh_vouchers.py --plan     what changed, no files written
  python scripts/refresh_vouchers.py           write chunks for the changed set
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
MANIFEST = DATA / "terms_manifest.json"
CHUNKS = DATA / "rules_chunks"
SOURCES = ("gyftr", "buyhatke", "maximize")
CHUNK_SIZE = 50

TERM_FIELDS = ("important_instruction", "checkout_instruction", "restrictions",
               "how_to_redeem", "faqs", "full_terms")


def terms_of(rec: dict) -> str:
    raw = rec.get("raw", {})
    parts = []
    for label, key in (("IMPORTANT INSTRUCTIONS", "important_instruction"),
                       ("CHECKOUT INSTRUCTIONS", "checkout_instruction"),
                       ("VOUCHER RESTRICTIONS", "restrictions"),
                       ("HOW TO REDEEM", "how_to_redeem"),
                       ("FAQS", "faqs"),
                       ("TERMS & CONDITIONS", "full_terms")):
        if v := raw.get(key):
            parts.append(f"## {label}\n{v}")
    if boxes := raw.get("info_boxes"):
        parts.append("## STATED ANSWERS\n" + "\n".join(f"{k} {v}" for k, v in boxes.items()))
    return "\n\n".join(parts).strip()


def fingerprint(text: str) -> str:
    """Whitespace and typographic noise must not count as a change, or every
    refresh re-reads the whole catalogue."""
    norm = re.sub(r"\s+", " ", text).replace("’", "'").replace("“", '"').replace("”", '"')
    return hashlib.sha256(norm.strip().lower().encode()).hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="report only, write nothing")
    ap.add_argument("--seed", action="store_true",
                    help="record today's terms as the baseline without queuing any reading")
    args = ap.parse_args()

    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    current, to_read = {}, []
    for source in SOURCES:
        path = DATA / f"voucher_terms_raw_{source}.json"
        if not path.exists():
            print(f"{source}: no scrape found — run scrape_voucher_terms.py first")
            continue
        for key, rec in json.loads(path.read_text()).items():
            if "error" in rec:
                continue
            text = terms_of(rec)
            if not text:
                continue
            fp = fingerprint(text)
            current[key] = fp
            if old.get(key) != fp:
                to_read.append({"key": key, "brand": rec["brand_name"],
                                "source": source, "terms": text[:12000]})

    new = [k for k in current if k not in old]
    changed = [k for k in current if k in old and old[k] != current[k]]
    gone = [k for k in old if k not in current]

    print(f"listings now      : {len(current)}")
    print(f"  new brands      : {len(new)}")
    print(f"  terms changed   : {len(changed)}")
    print(f"  gone from sale  : {len(gone)}")
    print(f"  unchanged       : {len(current) - len(new) - len(changed)}"
          f"  <- carried forward, not re-read")
    if changed[:5]:
        print("  changed sample  :", ", ".join(changed[:5]))

    if args.plan:
        print("\n--plan: nothing written")
        return

    if args.seed:
        MANIFEST.write_text(json.dumps(current, indent=1) + "\n")
        print(f"\nbaseline recorded for {len(current)} listings -> {MANIFEST.name}")
        print("the next refresh will queue only what has moved since")
        return

    for f in CHUNKS.glob("refresh_*.json"):
        f.unlink()
    to_read.sort(key=lambda x: x["key"])
    for i in range(0, len(to_read), CHUNK_SIZE):
        n = i // CHUNK_SIZE + 1
        (CHUNKS / f"refresh_{n:03d}.json").write_text(
            json.dumps(to_read[i:i + CHUNK_SIZE], indent=1, ensure_ascii=False))
    agents = -(-len(to_read) // (CHUNK_SIZE * 3))  # three chunks per reader
    print(f"\nwrote {-(-len(to_read) // CHUNK_SIZE)} chunk files for {len(to_read)} listings")
    print(f"that is roughly {agents} reading agent(s), against 10 for a full rebuild")
    MANIFEST.write_text(json.dumps(current, indent=1) + "\n")
    print(f"manifest updated -> {MANIFEST.name}")


if __name__ == "__main__":
    main()
