"""The link checklist: rerun every hand-checked listing after every change.

`tests/fixtures/match_checklist.json` holds real searches and pasted links
with their shop listings, each marked by hand as the exact product, a similar
one (other size/pack/bundle), or a wrong one. Three sets:

  main 30 + hold-out 19   29 links from the 25 Sep 2026 test, 409 listings
  27 Oct AI club          the two Calcutta AI Club failures, 80 listings
  fresh 25                23 searches captured 27 Oct 2026 and marked blind

This test asks the matching code (`product_identity`) to mark them all again.
The matcher may also answer "unconfirmed" (nothing contradicts, but the model
isn't stated); for scoring that counts as not shown, i.e. like "wrong".

Some answers were already off when a set was added. They are listed in
`tests/fixtures/match_checklist_known.json` so the checklist starts green. The
test fails only when an answer that was right goes wrong, or a known miss gets
a different answer. When a fix makes a known miss right, run with --accept to
lock it in.

Entries marked kind "category" (a search for a kind of thing, not a product)
are scored and reported separately: the live code never runs the matcher on
those, so they don't count towards the go/no-go number.

Run:  .venv/bin/python -m pytest tests/test_match_checklist.py -q
or:   .venv/bin/python tests/test_match_checklist.py           (scoreboard)
      .venv/bin/python tests/test_match_checklist.py --accept  (save current misses as known)
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import product_identity  # noqa: E402
from src.services.product_identity import build_identity, match_tier  # noqa: E402

CHECKLIST = ROOT / "tests" / "fixtures" / "match_checklist.json"
KNOWN = ROOT / "tests" / "fixtures" / "match_checklist_known.json"

ORIGINAL_SETS = {"main 30", "hold-out 19"}

# What a miss costs a shopper, in plain words.
_HARM = {
    ("wrong", "exact"): "wrong product let through as exact",
    ("wrong", "similar"): "wrong product let through as similar",
    ("similar", "exact"): "similar product treated as exact",
    ("exact", "wrong"): "right product thrown out (a cheaper shop could be missed)",
    ("exact", "unconfirmed"): "right product shown only when nothing else matches",
    ("exact", "similar"): "right product marked only similar",
    ("similar", "wrong"): "similar product thrown out",
    ("similar", "unconfirmed"): "similar product shown only when nothing else matches",
}


def _key(m: dict) -> tuple:
    return (m["url"], m["title"], m["shop"])


def _merchant_names() -> set[str]:
    try:
        from src.services.search_service import _load_trusted_merchants
        return set(_load_trusted_merchants())
    except Exception:  # the matcher must stay testable without the catalogue
        return set()


def identity_for(link: dict, merchants: set[str] | None = None) -> dict:
    """The ID card the live code would build for this entry: a typed search
    gets `typed`, and, once the matcher has it, the result set's titles."""
    ident = build_identity(link["page_title"], None if link.get("typed") else link["url"])
    if link.get("typed"):
        ident["typed"] = True
    weigh = getattr(product_identity, "weigh_identity", None)
    if weigh is not None:
        ident = weigh(ident, [r["title"] for r in link["listings"]], merchants or set())
    return ident


def run_checklist() -> tuple[int, list[dict], dict]:
    """(listings checked, misses, per-set tallies). A tally is
    {set: {kind: [right, total]}}."""
    links = json.loads(CHECKLIST.read_text())["links"]
    merchants = _merchant_names()
    checks, misses = 0, []
    tally: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for link in links:
        ident = identity_for(link, merchants)
        kind = link.get("kind", "product")
        for row in link["listings"]:
            checks += 1
            said = match_tier(ident, row["title"], row["shop"])[0]
            right = said == row["answer"]
            tally[link["set"]][kind][1] += 1
            if right:
                tally[link["set"]][kind][0] += 1
            else:
                misses.append({"product": link["product"], "url": link["url"], "title": row["title"],
                               "shop": row["shop"], "answer": row["answer"], "dealo_says": said})
    return checks, misses, tally


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
    _, misses, _ = run_checklist()
    new, _ = compare(misses)
    assert not new, ("The matching code now gets these listings wrong (they were right before):\n"
                     + "\n".join(_line(m) for m in new))


def _scoreboard(checks: int, misses: list[dict], tally: dict) -> None:
    print(f"{checks} listings checked: {checks - len(misses)} right, {len(misses)} missed\n")
    for set_name, kinds in tally.items():
        for kind, (right, total) in kinds.items():
            label = f"{set_name} ({kind})" if kind != "product" else set_name
            print(f"  {label:<28} {right:>4}/{total:<4} {100 * right / total:5.1f}%")
    print()
    for (answer, said), n in sorted(Counter((m["answer"], m["dealo_says"]) for m in misses).items()):
        print(f"  {n:>3}  {_HARM.get((answer, said), f'{answer} marked {said}')}")


def main() -> int:
    checks, misses, tally = run_checklist()
    if "--accept" in sys.argv:
        KNOWN.write_text(json.dumps(misses, indent=1, ensure_ascii=False) + "\n")
        print(f"Saved {len(misses)} known misses to {KNOWN.relative_to(ROOT)}")
        return 0
    new, fixed = compare(misses)
    _scoreboard(checks, misses, tally)
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
