"""The link checklist: rerun every hand-checked listing after every change.

`tests/fixtures/match_checklist.json` holds 29 real pasted links from the
25 Sep 2026 test and 409 shop listings, each marked by hand as the exact
product, a similar one, or a wrong one. This test asks the matching code
(`product_identity`) to mark them all again.

Some answers were already off when the checklist was made. They are listed in
`tests/fixtures/match_checklist_known.json` so the checklist starts green. The
test fails only when an answer that was right goes wrong, or a known miss gets
a different answer. When a fix makes a known miss right, run with --accept to
lock it in.

Run:  .venv/bin/python -m pytest tests/test_match_checklist.py -q
or:   .venv/bin/python tests/test_match_checklist.py           (scoreboard)
      .venv/bin/python tests/test_match_checklist.py --accept  (save current misses as known)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.product_identity import build_identity, match_tier  # noqa: E402

CHECKLIST = ROOT / "tests" / "fixtures" / "match_checklist.json"
KNOWN = ROOT / "tests" / "fixtures" / "match_checklist_known.json"

# What a miss costs a shopper, in plain words.
_HARM = {
    ("wrong", "exact"): "wrong product let through as exact",
    ("wrong", "similar"): "wrong product let through as similar",
    ("similar", "exact"): "similar product treated as exact",
    ("exact", "wrong"): "right product thrown out (a cheaper shop could be missed)",
    ("exact", "similar"): "right product marked only similar",
    ("similar", "wrong"): "similar product thrown out",
}


def _key(m: dict) -> tuple:
    return (m["url"], m["title"], m["shop"])


def run_checklist() -> tuple[int, list[dict]]:
    links = json.loads(CHECKLIST.read_text())["links"]
    checks, misses = 0, []
    for link in links:
        ident = build_identity(link["page_title"], link["url"])
        for row in link["listings"]:
            checks += 1
            said = match_tier(ident, row["title"], row["shop"])[0]
            if said != row["answer"]:
                misses.append({"product": link["product"], "url": link["url"], "title": row["title"],
                               "shop": row["shop"], "answer": row["answer"], "dealo_says": said})
    return checks, misses


def compare(misses: list[dict]) -> tuple[list[dict], list[dict]]:
    """(new misses, known misses that are now right)."""
    known = {_key(m): m for m in json.loads(KNOWN.read_text())} if KNOWN.exists() else {}
    now = {_key(m): m for m in misses}
    new = [m for k, m in now.items() if k not in known or known[k]["dealo_says"] != m["dealo_says"]]
    fixed = [m for k, m in known.items() if k not in now]
    return new, fixed


def _line(m: dict) -> str:
    harm = _HARM.get((m["answer"], m["dealo_says"]), f'{m["answer"]} marked {m["dealo_says"]}')
    return f'  - {m["product"]}: "{m["title"][:80]}" ({m["shop"]}) -> {harm}'


def test_no_new_misses():
    _, misses = run_checklist()
    new, _ = compare(misses)
    assert not new, ("The matching code now gets these listings wrong (they were right before):\n"
                     + "\n".join(_line(m) for m in new))


def main() -> int:
    checks, misses = run_checklist()
    if "--accept" in sys.argv:
        KNOWN.write_text(json.dumps(misses, indent=1, ensure_ascii=False) + "\n")
        print(f"Saved {len(misses)} known misses to {KNOWN.relative_to(ROOT)}")
        return 0
    new, fixed = compare(misses)
    print(f"{checks} listings checked across 29 links: {checks - len(misses)} right, {len(misses)} missed")
    for (answer, said), n in sorted(Counter((m["answer"], m["dealo_says"]) for m in misses).items()):
        print(f"  {n:>3}  {_HARM.get((answer, said), f'{answer} marked {said}')}")
    if fixed:
        print(f"\n{len(fixed)} known misses are now right. Run with --accept to lock them in:")
        print("\n".join(_line(m) for m in fixed))
    if new:
        print(f"\nFAIL: {len(new)} new misses:")
        print("\n".join(_line(m) for m in new))
        return 1
    print("\nPASS: nothing that was right has gone wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
