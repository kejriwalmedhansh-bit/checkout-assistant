"""Offline regression check for the Product Picker filter.

Runs `_filter_and_group_candidates` against saved SearchApi snapshots in
`tests/fixtures/search/` instead of the live API. The real search cache is
in-memory and dies with the process (see src/cache.py), so every live call
costs SearchApi budget and returns slightly different listings each time —
which makes "did my change break anything?" impossible to answer against the
network. Fixtures make it deterministic and free.

    .venv/bin/python tests/check_picker.py            # print current results
    .venv/bin/python tests/check_picker.py --baseline # write baseline.json
    .venv/bin/python tests/check_picker.py --compare  # diff against baseline

Refresh the fixtures with tests/capture_fixtures.py when listings go stale.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.services import search_service as S  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "search"
BASELINE = pathlib.Path(__file__).parent / "fixtures" / "baseline.json"


def run_all() -> dict:
    out: dict = {}
    for path in sorted(FIXTURES.glob("*.json")):
        payload = json.loads(path.read_text())
        query = payload["query"]
        candidates = [
            S._product_candidate(p)
            for p in payload.get("shopping_results", [])
            if p.get("product_token")
        ]
        result = S._filter_and_group_candidates(candidates, query)
        # Tolerate both shapes so a baseline can be captured from the older
        # revision (which returned a bare list) and compared against the
        # current one (which returns `(products, approximate)`).
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
            products, approximate = result
        else:
            products, approximate = result, False
        out[query] = {
            "count": len(products),
            "approximate": approximate,
            "titles": [f"{p.get('source')} | {p.get('price')} | {p.get('title')}" for p in products],
        }
    return out


def main() -> int:
    results = run_all()

    if "--baseline" in sys.argv:
        BASELINE.write_text(json.dumps(results, indent=1))
        print(f"baseline written: {BASELINE}")
        return 0

    if "--compare" in sys.argv:
        if not BASELINE.exists():
            print("no baseline — run with --baseline first")
            return 1
        before = json.loads(BASELINE.read_text())
        failed = False
        for query, now in results.items():
            was = before.get(query)
            if was is None:
                print(f"NEW   {query}: {now['count']} results")
                continue
            if was["count"] == now["count"] and was["titles"] == now["titles"]:
                flag = "  (approximate)" if now["approximate"] else ""
                print(f"SAME  {query}: {now['count']}{flag}")
                continue
            failed = True
            print(f"DIFF  {query}: {was['count']} -> {now['count']}")
            for t in was["titles"]:
                if t not in now["titles"]:
                    print(f"        removed: {t}")
            for t in now["titles"]:
                if t not in was["titles"]:
                    print(f"        added:   {t}")
        print("\nDIFFERENCES FOUND" if failed else "\nno change")
        return 1 if failed else 0

    for query, r in results.items():
        flag = "  [approximate]" if r["approximate"] else ""
        print(f"\n{query} -> {r['count']}{flag}")
        for t in r["titles"]:
            print(f"    {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
