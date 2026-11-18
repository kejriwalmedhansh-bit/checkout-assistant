"""The morning Hubble check (scripts/hubble_daily_check.py) and the name
review it relies on.

Run:  .venv/bin/python -m pytest tests/test_hubble_daily_check.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import hubble_daily_check as daily  # noqa: E402
import hubble_name_candidates  # noqa: E402
from src.services import hubble_service as h  # noqa: E402

PROD = ROOT / "data" / "hubble_catalogue.json"


@pytest.fixture(autouse=True)
def _production(monkeypatch):
    monkeypatch.setattr(h, "_catalogue_path", lambda: PROD)
    monkeypatch.setattr(h, "_live", {"brands": None, "index": None, "at": 0.0})


def test_every_lookalike_partner_name_has_a_decision():
    """The Steam problem, caught before merge: a partner card whose name
    starts like a Hubble card's but doesn't reach it must be linked (alias)
    or marked different in data/hubble_name_review.json."""
    undecided = hubble_name_candidates.candidates(json.loads(PROD.read_text()))
    assert not undecided, "\n".join(f"{c['name']} -> {c['hubble']}" for c in undecided)


def test_review_file_and_aliases_never_disagree():
    review = hubble_name_candidates.reviewed()
    aliases = {k for k in json.loads((ROOT / "data" / "hubble_aliases.json").read_text()) if not k.startswith("_")}
    assert not (set(review) & aliases)
    assert set(review.values()) <= {"different", "owner"}


def _result(**kw):
    base = {"checked_at": "19 Nov 2026, 08:30 IST", "hubble_count": 474, "sellable": 470, "added": [], "removed": [],
            "dealo_problem": [], "no_answer": [], "hubble_not_selling": [], "names": [], "waiting": []}
    return {**base, **kw}


def test_quiet_day_needs_nobody():
    r = _result(hubble_not_selling=["Zepto"], added=["Zudio"], waiting=["tanishqdiamond"])
    assert not daily.needs_a_person(r)
    assert "Nothing needs a person today" in daily.report(r)


def test_dealo_problem_or_new_name_needs_a_person():
    r = _result(dealo_problem=["Steam wallet"])
    assert daily.needs_a_person(r) and "Steam wallet" in daily.report(r)
    r = _result(names=[{"name": "Steam", "sellers": ["maximize"], "hubble": ["Steam wallet"]}])
    assert daily.needs_a_person(r) and "**Steam** (maximize) → Hubble: Steam wallet" in daily.report(r)


def test_site_down_needs_a_person():
    assert daily.needs_a_person(_result(no_answer=[str(i) for i in range(11)]))
