"""Every morning: is every voucher Hubble sells actually sellable on Dealo,
and does every partner card name that looks like a Hubble card have a
decision? Writes a short report; the GitHub job opens (or updates) an issue
called "Hubble daily check" only when something needs a person, and closes
it when all is clear. Born from the 18 Nov 2026 audit (Steam was sold via
Maximize because of a name; Hubble's list was three weeks old).

    HUBBLE_ENV=production HUBBLE_ENABLED=true HUBBLE_CLIENT_ID=... \\
        python scripts/hubble_daily_check.py --out report.md

Checks:
1. Hubble's list today vs data/hubble_catalogue.json (new and gone vouchers;
   the live server reads the list itself, so this is information).
2. Every Hubble voucher on the live site (/hubble/brand). One Hubble itself
   sells today but Dealo can't is a Dealo problem; one Hubble isn't
   selling today is noted.
3. Partner card names that may be the same card as a Hubble one and have no
   decision yet (scripts/hubble_name_candidates.py).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.services import hubble_service as h  # noqa: E402
import hubble_name_candidates  # noqa: E402

LIVE_API = os.environ.get("DEALO_API", "https://dealo-backend.onrender.com").rstrip("/")
IST = timezone(timedelta(hours=5, minutes=30))


async def _hubble_sells(brand_id: str) -> bool:
    """Hubble's own answer: on sale, at a real discount."""
    product = await h._product(brand_id, background=True)
    return bool(product and product.get("status") == "ACTIVE" and h._discount_pct(product) > 0)


async def _dealo_sells(client: httpx.AsyncClient, brand: dict) -> bool | None:
    in_store = "ONLINE" not in brand["works"]
    params = {"slug": h.buy_slug(brand["name"])}
    if in_store:
        params["in_store"] = "true"
    for _ in range(3):
        try:
            r = await client.get(f"{LIVE_API}/hubble/brand", params=params)
            r.raise_for_status()
            found = r.json().get("brand")
            return bool(r.json().get("available")) and bool(found) and found.get("brand_id") == brand["id"]
        except (httpx.HTTPError, ValueError):
            await asyncio.sleep(5)
    return None  # the live site didn't answer


async def run() -> dict:
    file_list = json.loads((ROOT / "data" / "hubble_catalogue.json").read_text())
    today = await h.fetch_catalogue(file_list)
    file_ids, today_ids = {b["id"] for b in file_list}, {b["id"] for b in today}
    added = sorted(b["name"] for b in today if b["id"] not in file_ids)
    removed = sorted(b["name"] for b in file_list if b["id"] not in today_ids)

    gate = asyncio.Semaphore(6)
    async with httpx.AsyncClient(timeout=40) as client:
        # Wake the free Render server before asking it 470 questions.
        try:
            await client.get(f"{LIVE_API}/health", timeout=90)
        except httpx.HTTPError:
            pass

        async def check(brand: dict) -> tuple[dict, bool, bool | None]:
            async with gate:
                return brand, await _hubble_sells(brand["id"]), await _dealo_sells(client, brand)
        results = await asyncio.gather(*(check(b) for b in today))

    dealo_problem = sorted(b["name"] for b, hub, dealo in results if hub and dealo is False)
    no_answer = sorted(b["name"] for b, hub, dealo in results if hub and dealo is None)
    hubble_not_selling = sorted(b["name"] for b, hub, _ in results if not hub)
    sellable = sum(1 for _, hub, dealo in results if hub and dealo)

    names = hubble_name_candidates.candidates(today)
    waiting = sorted(k for k, v in hubble_name_candidates.reviewed().items() if v == "owner")
    return {
        "checked_at": datetime.now(IST).strftime("%d %b %Y, %H:%M IST"),
        "hubble_count": len(today), "sellable": sellable,
        "added": added, "removed": removed,
        "dealo_problem": dealo_problem, "no_answer": no_answer,
        "hubble_not_selling": hubble_not_selling,
        "names": names, "waiting": waiting,
    }


def needs_a_person(r: dict) -> bool:
    return bool(r["dealo_problem"] or r["names"] or len(r["no_answer"]) > 10)


def report(r: dict) -> str:
    lines = [f"**Hubble daily check · {r['checked_at']}**", "",
             f"{r['sellable']} of {r['hubble_count']} Hubble vouchers can be bought on getdealo.in right now.", ""]
    if r["dealo_problem"]:
        lines += ["### ❌ Hubble sells these, but Dealo can't (fix needed)", *[f"- {n}" for n in r["dealo_problem"]], ""]
    if r["names"]:
        lines += ["### ❓ Same card under another name? (decide once)",
                  "A partner sells a card whose name starts like a Hubble card, but Dealo doesn't link them. "
                  "If it's the same card, shoppers are being sent to the partner (the Steam problem).", ""]
        lines += [f"- [ ] **{c['name']}** ({', '.join(c['sellers'])}) → Hubble: {', '.join(c['hubble'])}" for c in r["names"]]
        lines += ["", "Link it in `data/hubble_aliases.json`, or mark it `different` in `data/hubble_name_review.json`.", ""]
    if len(r["no_answer"]) > 10:
        lines += [f"### ⚠️ The live site didn't answer for {len(r['no_answer'])} vouchers (server down or slow?)", ""]
    if r["added"] or r["removed"]:
        lines += ["### ℹ️ Hubble's list changed since the saved copy",
                  f"- New: {', '.join(r['added']) or 'none'}", f"- Gone: {', '.join(r['removed']) or 'none'}",
                  "The live server picks this up by itself; refresh the saved copy with "
                  "`scripts/build_hubble_catalogue.py` when convenient.", ""]
    if r["hubble_not_selling"]:
        lines += [f"### ℹ️ Hubble isn't selling {len(r['hubble_not_selling'])} of its listed vouchers today",
                  ", ".join(r["hubble_not_selling"]), ""]
    if r["waiting"]:
        lines += [f"### ⏳ Waiting for the owner's call: {len(r['waiting'])} jewellery card names",
                  "(gold vs diamond vs coin kinds; see `data/hubble_name_review.json`)", ""]
    if not needs_a_person(r):
        lines += ["✅ Nothing needs a person today."]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="write the report (markdown) here")
    parser.add_argument("--json", help="write the raw results here")
    args = parser.parse_args()
    r = asyncio.run(run())
    text = report(r)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({**r, "needs_a_person": needs_a_person(r)}, indent=1))


if __name__ == "__main__":
    main()
