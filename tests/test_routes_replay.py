"""Replay recorded searches + comparisons and check the shops that must appear.

Each file in tests/fixtures/routes/ is one shopper journey recorded by
tests/routes_replay.py (search, pick, compare) with every outside answer on
tape. `must_include` lists shops that a human confirmed sell the exact
product, with the price seen at capture; the comparison must list each of
them at that price. No network, no credits.

Run:  .venv/bin/python -m pytest tests/test_routes_replay.py -q
      .venv/bin/python tests/test_routes_replay.py          (prints every journey's shops)
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.routes_replay import OUT, Tape, replaying, run_case, shops  # noqa: E402

FIXTURES = sorted(OUT.glob("*.json")) if OUT.exists() else []


def _journey(path: pathlib.Path) -> tuple[dict, dict]:
    data = json.loads(path.read_text())
    tape = Tape(data["calls"])
    with replaying(tape):
        result = run_case(data["input"])
    assert not tape.missed, f"{path.name}: asked for something not on the tape:\n" + "\n".join(tape.missed[:5])
    return data, result


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_confirmed_shops_are_listed(path: pathlib.Path):
    data, result = _journey(path)
    listed = {(m, p) for m, p, _ in shops(result)}
    missing = [w for w in data.get("must_include", []) if (w["shop"], w["price"]) not in listed]
    if missing and data.get("known_failure"):
        pytest.xfail(f"{path.name}: {data['known_failure']}")
    assert not missing, (
        f"{path.name}: missing {[(w['shop'], w['price']) for w in missing]}. Listed: {sorted(listed)}")


if __name__ == "__main__":
    for p in FIXTURES:
        data, result = _journey(p)
        print(f"{p.stem}\n  pick: {result['pick']}\n  shops: {shops(result)}")
