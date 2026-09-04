"""Check that every rule read from a voucher's terms is backed by a real quote.

A rule Dealo cannot quote is a rule Dealo should not state, so this is the gate
between reading the terms and using them. Typographic normalisation is allowed —
curly apostrophes rewritten straight, whitespace collapsed — because that is a
transcription difference, not a claim. Anything else is treated as unsupported.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

CHUNKS = Path(__file__).resolve().parent.parent / "data" / "rules_chunks"
PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"',
         "–": "-", "—": "-", " ": " "}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    # Maximize's own pages contain doubled apostrophes ("can''t"); a faithful
    # transcription writes one. Collapse them rather than call it unsupported.
    s = re.sub(r"'{2,}", "'", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> int:
    total = claims = unsupported = 0
    missing_listings = []
    bad = []
    for out_path in sorted(CHUNKS.glob("out_*.json")):
        chunk = CHUNKS / f"chunk_{out_path.stem.split('_')[1]}.json"
        src = {x["key"]: x for x in json.loads(chunk.read_text())}
        got = json.loads(out_path.read_text())
        missing = [k for k in src if k not in got]
        if missing:
            missing_listings += missing
        for key, rec in got.items():
            total += 1
            terms = norm(src.get(key, {}).get("terms", ""))
            for field, quote in (rec.get("quotes") or {}).items():
                if not quote:
                    continue
                claims += 1
                if norm(quote) not in terms:
                    unsupported += 1
                    bad.append((key, field, quote[:90]))

    print(f"listings read : {total}")
    print(f"quoted claims : {claims}")
    print(f"unsupported   : {unsupported}")
    if missing_listings:
        print(f"MISSING from output: {len(missing_listings)} — {missing_listings[:5]}")
    for b in bad[:15]:
        print(f"  ! {b[0]} [{b[1]}] {b[2]}")
    return 1 if (unsupported or missing_listings) else 0


if __name__ == "__main__":
    sys.exit(main())
