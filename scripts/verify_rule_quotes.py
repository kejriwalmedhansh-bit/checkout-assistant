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


def pieced(quote: str, terms: str, min_words: int = 4) -> bool:
    """True when a quote is several real sentences run together. Some readings
    joined every sentence behind an `excludes` list into one quote; each part
    is on the page, just not side by side. Walk the quote left to right taking
    the longest run of words (at least four) that appears in the terms; it
    passes only if those runs cover every word. A paraphrased word anywhere
    breaks the run and fails it."""
    words = quote.split()
    i = 0
    while i < len(words):
        j = len(words)
        while j - i >= min_words and " ".join(words[i:j]) not in terms:
            j -= 1
        if j - i < min_words:
            return False
        i = j
    return True


def main() -> int:
    total = claims = unsupported = stitched = 0
    missing_listings = []
    bad = []
    # First and second readings both, and a refresh's tagged readings
    # (out_r0928_001 / out2_r0928_001 read chunk_r0928_001) as well as the full
    # build's (out_001 / out2_001 read chunk_001). Checking only the first
    # reading let the second one's quotes through unchecked into the merge.
    for out_path in sorted([*CHUNKS.glob("out_*.json"), *CHUNKS.glob("out2_*.json")]):
        chunk = CHUNKS / f"chunk_{out_path.stem.split('_', 1)[1]}.json"
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
                if norm(quote) in terms:
                    continue
                if pieced(norm(quote), terms):
                    stitched += 1
                    continue
                unsupported += 1
                bad.append((key, field, quote[:90]))

    print(f"listings read : {total}")
    print(f"quoted claims : {claims}")
    print(f"stitched      : {stitched}  (several verbatim sentences joined — each part checked)")
    print(f"unsupported   : {unsupported}")
    if missing_listings:
        print(f"MISSING from output: {len(missing_listings)} — {missing_listings[:5]}")
    for b in bad[:15]:
        print(f"  ! {b[0]} [{b[1]}] {b[2]}")
    return 1 if (unsupported or missing_listings) else 0


if __name__ == "__main__":
    sys.exit(main())
