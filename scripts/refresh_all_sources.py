"""
refresh_all_sources.py — Safe, automated re-scrape + refresh for BuyHatke and
Gyftr voucher data. Maximize is deliberately NOT included here: it requires a
real, manually logged-in Chrome window (Cloudflare blocks headless/automated
browsers), which no scheduled/cloud job can provide — that refresh stays a
manual, on-demand thing between the user and Claude.

Usage:
    /usr/local/bin/python3.11 scripts/refresh_all_sources.py

What it does, in order:
1. Snapshots the CURRENT data/buyhatke_master.json and data/gyftr_master.json
   (brand count, per-brand best rate) as the "before" picture.
2. Clears each scraper's own checkpoint file first — without this,
   scrape_buyhatke_details.py and scrape_all_gyftr.py would see every brand
   already "done" from the last run and scrape nothing new at all, silently
   turning every re-run after the first into a no-op.
3. Runs the full BuyHatke pipeline (brand list -> detail scrape -> normalize)
   and the full Gyftr pipeline (brand list -> Playwright T&C scrape -> build
   master -> normalize).
4. Compares "before" vs "after" per source. Safety check: if a source's live
   brand count collapses below SAFETY_MIN_RATIO of its previous count (a
   real scrape failure — site change, block, network issue — not normal
   day-to-day drift), the new data for THAT SOURCE is discarded (git
   checkout -- restores the last-known-good file) and the run is reported
   as a FAILURE for that source. Never silently commits broken/incomplete
   data over good data (CLAUDE.md rule #1).
5. Whatever sources are safe get committed and pushed together, with a real
   diff summary in the commit message.
6. Writes a structured report to db/refresh_report_latest.json (machine-
   readable) and db/refresh_report_latest.txt (plain text — what gets
   emailed). The report always says what succeeded, what failed, what
   individual brands within a "successful" run still failed, and every
   notable per-brand rate change — nothing is glossed over.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_DIR = ROOT / "db"

SAFETY_MIN_RATIO = 0.7  # a source dropping below 70% of its prior brand count is treated as a scrape failure, not normal drift
RATE_CHANGE_THRESHOLD = 1.0  # percentage points — smaller moves aren't worth flagging individually

REPORT_JSON = DB_DIR / "refresh_report_latest.json"
REPORT_TXT = DB_DIR / "refresh_report_latest.txt"


def run(cmd: list[str], label: str) -> tuple[bool, str]:
    print(f"--- {label} ---")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    ok = result.returncode == 0
    tail = (result.stdout[-3000:] + result.stderr[-1500:]).strip()
    print(tail[-2000:])
    if not ok:
        print(f"!!! {label} FAILED (exit {result.returncode})")
    return ok, tail


def snapshot(source: str) -> dict[str, float]:
    """{brand_name: best_discount_pct} across all products for a source."""
    path = DATA_DIR / f"{source}_master.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for rec in data.values():
        rates = [p.get("best_discount_pct") for p in rec.get("products") or [] if p.get("best_discount_pct") is not None]
        if rates:
            out[rec["brand_name"]] = max(rates)
    return out


def diff_snapshots(before: dict[str, float], after: dict[str, float]) -> dict:
    before_names, after_names = set(before), set(after)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)
    changed = []
    for name in sorted(before_names & after_names):
        delta = round(after[name] - before[name], 2)
        if abs(delta) >= RATE_CHANGE_THRESHOLD:
            changed.append({"brand": name, "before_pct": before[name], "after_pct": after[name], "delta": delta})
    changed.sort(key=lambda c: -abs(c["delta"]))
    return {
        "before_count": len(before_names),
        "after_count": len(after_names),
        "added": added,
        "removed": removed,
        "rate_changes": changed,
    }


def refresh_buyhatke() -> dict:
    report = {"source": "BuyHatke", "status": "unknown", "steps": []}
    before = snapshot("buyhatke")

    progress_file = DB_DIR / "buyhatke_scrape_progress.json"
    if progress_file.exists():
        progress_file.unlink()  # force a genuine full re-scrape, not a no-op resume

    ok, log = run([sys.executable, "scripts/scrape_buyhatke_brands.py"], "BuyHatke brand list")
    report["steps"].append({"step": "brand_list", "ok": ok})
    if not ok:
        report["status"] = "failed"
        report["reason"] = "brand list scrape failed"
        return report

    ok, log = run([sys.executable, "scripts/scrape_buyhatke_details.py"], "BuyHatke detail scrape")
    report["steps"].append({"step": "detail_scrape", "ok": ok, "log_tail": log[-800:]})

    failures_file = DB_DIR / "buyhatke_scrape_failures.json"
    scrape_failures = json.loads(failures_file.read_text()) if failures_file.exists() else []
    report["individual_scrape_failures"] = scrape_failures

    ok, log = run([sys.executable, "scripts/normalize_buyhatke_master.py"], "BuyHatke normalize")
    report["steps"].append({"step": "normalize", "ok": ok, "log_tail": log[-800:]})
    if not ok:
        report["status"] = "failed"
        report["reason"] = "normalize step failed"
        return report

    after = snapshot("buyhatke")
    report["diff"] = diff_snapshots(before, after)

    if before and len(after) < SAFETY_MIN_RATIO * len(before):
        subprocess.run(["git", "checkout", "--", "data/buyhatke_master.json"], cwd=ROOT)
        report["status"] = "failed"
        report["reason"] = (
            f"safety check tripped: brand count dropped from {len(before)} to {len(after)} "
            f"(below {int(SAFETY_MIN_RATIO*100)}% threshold) — new data discarded, old data kept"
        )
        return report

    report["status"] = "ok"
    return report


def refresh_gyftr() -> dict:
    report = {"source": "Gyftr", "status": "unknown", "steps": []}
    before = snapshot("gyftr")

    progress_file = DB_DIR / "gyftr_full_scrape_progress.json"
    if progress_file.exists():
        progress_file.unlink()

    ok, log = run([sys.executable, "scripts/scrape_gyftr.py"], "Gyftr brand+rate scrape (API)")
    report["steps"].append({"step": "api_scrape", "ok": ok})
    if not ok:
        report["status"] = "failed"
        report["reason"] = "API brand/rate scrape failed"
        return report

    ok, log = run([sys.executable, "scripts/scrape_all_gyftr.py"], "Gyftr T&C scrape (Playwright)")
    report["steps"].append({"step": "playwright_scrape", "ok": ok, "log_tail": log[-800:]})

    failures_file = DB_DIR / "gyftr_scrape_failures.json"
    scrape_failures = json.loads(failures_file.read_text()) if failures_file.exists() else []
    report["individual_scrape_failures"] = scrape_failures

    ok, log = run([sys.executable, "scripts/build_master.py"], "Gyftr build_master")
    report["steps"].append({"step": "build_master", "ok": ok, "log_tail": log[-800:]})
    if not ok:
        report["status"] = "failed"
        report["reason"] = "build_master step failed"
        return report

    ok, log = run([sys.executable, "scripts/normalize_existing_masters.py"], "Normalize Gyftr+Maximize masters")
    report["steps"].append({"step": "normalize", "ok": ok, "log_tail": log[-800:]})
    if not ok:
        report["status"] = "failed"
        report["reason"] = "normalize step failed"
        return report

    after = snapshot("gyftr")
    report["diff"] = diff_snapshots(before, after)

    if before and len(after) < SAFETY_MIN_RATIO * len(before):
        subprocess.run(["git", "checkout", "--", "data/gyftr_master.json"], cwd=ROOT)
        report["status"] = "failed"
        report["reason"] = (
            f"safety check tripped: brand count dropped from {len(before)} to {len(after)} "
            f"(below {int(SAFETY_MIN_RATIO*100)}% threshold) — new data discarded, old data kept"
        )
        return report

    report["status"] = "ok"
    return report


def format_report_text(run_id: str, reports: list[dict]) -> str:
    lines = [f"Dealo voucher data refresh — {run_id}", "=" * 50, ""]
    any_failed = any(r["status"] == "failed" for r in reports)
    lines.append("OVERALL: " + ("SOME SOURCES FAILED — see below" if any_failed else "All sources refreshed successfully"))
    lines.append("")
    for r in reports:
        lines.append(f"## {r['source']}: {r['status'].upper()}")
        if r["status"] == "failed":
            lines.append(f"  Reason: {r.get('reason', 'unknown')}")
            for step in r.get("steps", []):
                mark = "ok" if step["ok"] else "FAILED"
                lines.append(f"  - {step['step']}: {mark}")
            lines.append("")
            continue
        d = r.get("diff", {})
        lines.append(f"  Brands before: {d.get('before_count')}  ->  after: {d.get('after_count')}")
        fails = r.get("individual_scrape_failures") or []
        lines.append(f"  Individual brand scrape failures this run: {len(fails)}" + (f" ({', '.join(fails[:15])}{'...' if len(fails) > 15 else ''})" if fails else ""))
        added = d.get("added") or []
        removed = d.get("removed") or []
        lines.append(f"  New brands: {len(added)}" + (f" ({', '.join(added[:10])}{'...' if len(added) > 10 else ''})" if added else ""))
        lines.append(f"  Removed brands: {len(removed)}" + (f" ({', '.join(removed[:10])}{'...' if len(removed) > 10 else ''})" if removed else ""))
        changes = d.get("rate_changes") or []
        lines.append(f"  Notable rate changes (>= {RATE_CHANGE_THRESHOLD}pp): {len(changes)}")
        for c in changes[:20]:
            sign = "+" if c["delta"] > 0 else ""
            lines.append(f"    - {c['brand']}: {c['before_pct']}% -> {c['after_pct']}% ({sign}{c['delta']}pp)")
        if len(changes) > 20:
            lines.append(f"    ... and {len(changes) - 20} more")
        lines.append("")
    lines.append("(Maximize is not part of this automated refresh — needs a manually logged-in browser session, done separately.)")
    return "\n".join(lines)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reports = [refresh_buyhatke(), refresh_gyftr()]

    ok_sources = [r["source"] for r in reports if r["status"] == "ok"]
    if ok_sources:
        subprocess.run(["git", "add"] + [f"data/{s.lower()}_master.json" for s in ok_sources]
                        + ["db/buyhatke_brands.json", "db/buyhatke_scrape_progress.json", "db/buyhatke_scrape_failures.json",
                           "db/gyftr_full_scrape_progress.json", "db/gyftr_scrape_failures.json", "db/gyftr_vouchers.json"],
                        cwd=ROOT)
        summary = ", ".join(f"{r['source']} {r['diff']['before_count']}->{r['diff']['after_count']}" for r in reports if r["status"] == "ok")
        commit_msg = f"Scheduled data refresh ({run_id}): {summary}\n\nAutomated biweekly refresh via scheduled cloud routine."
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT)
        subprocess.run(["git", "push"], cwd=ROOT)

    text_report = format_report_text(run_id, reports)
    REPORT_JSON.write_text(json.dumps({"run_id": run_id, "reports": reports}, indent=2))
    REPORT_TXT.write_text(text_report)
    print("\n" + text_report)


if __name__ == "__main__":
    main()
