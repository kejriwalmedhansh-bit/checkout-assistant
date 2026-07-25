"""Scrape every product page in db/maximize_catalog.json for full gift-card
details: denominations, per-payment-mode discount/earn rates (requires being
logged in), redemption type, stacking/clubbing rules, how-to-redeem steps,
and full terms & conditions.

Resumable: progress checkpointed to PROGRESS_FILE every CHECKPOINT_EVERY
products; failures logged to FAILED_LOG for manual review.
"""
import sys, json, os, re, time
sys.path.insert(0, os.path.dirname(__file__))
from _maximize_cdp import get_connected_page, close_all

CATALOG_FILE = "db/maximize_catalog.json"
PROGRESS_FILE = "db/maximize_scrape_progress.json"
FAILED_LOG = "db/maximize_scrape_failures.json"
CHECKPOINT_EVERY = 10
MAX_ATTEMPTS = 3
PAYMENT_MODES = ["UPI", "Debit Card", "Credit Card", "CC on UPI", "Diners Club", "Amex"]


def between(text, start_label, end_labels):
    """Return the first non-empty line after start_label and before any of end_labels."""
    lines = [l.strip() for l in text.split("\n")]
    try:
        idx = lines.index(start_label)
    except ValueError:
        return None
    for l in lines[idx + 1:]:
        if not l:
            continue
        if l in end_labels:
            return None
        return l
    return None


def parse_denominations(text):
    lines = [l.strip() for l in text.split("\n")]
    try:
        start = lines.index("Select your Shopping Amount")
    except ValueError:
        return [], False
    denoms = []
    custom = False
    for l in lines[start + 1:]:
        if l == "Quantity":
            break
        if l == "Custom":
            custom = True
        elif re.match(r"^₹[\d,]+$", l):
            denoms.append(int(l.replace("₹", "").replace(",", "")))
    return denoms, custom


def parse_baseline_fields(text):
    fields = {}
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # redemption type: line immediately before "How To Redeem"
    try:
        i = lines.index("How To Redeem")
        fields["redemption_type"] = lines[i - 1] if i > 0 else None
    except ValueError:
        fields["redemption_type"] = None

    # description: lines between "About this gift card" and "Where to Redeem?"
    try:
        i = lines.index("About this gift card")
        j = lines.index("Where to Redeem?") if "Where to Redeem?" in lines else i + 2
        fields["description"] = " ".join(lines[i + 1:j])
    except ValueError:
        fields["description"] = None

    fields["where_to_redeem"] = between(text, "Where to Redeem?",
                                         {"Multi-Use or Single Use?"})
    fields["multi_use_raw"] = between(text, "Multi-Use or Single Use?",
                                        {"Can be clubbed with other offers?"})
    fields["can_club_with_offers_raw"] = between(text, "Can be clubbed with other offers?",
                                                   {"Can the cards be clubbed?"})
    fields["cards_stackable_raw"] = between(text, "Can the cards be clubbed?",
                                              {"Validity"})
    fields["validity"] = between(text, "Validity", {"Recommended Cards"})

    m = re.search(r"Max:\s*(\d+)", text)
    fields["quantity_cap_per_order"] = int(m.group(1)) if m else None

    denoms, custom = parse_denominations(text)
    fields["denominations"] = denoms
    fields["custom_amount"] = custom

    # brand name: the line right before "Share"
    try:
        i = lines.index("Share")
        fields["brand_name"] = lines[i - 1] if i > 0 else None
    except ValueError:
        fields["brand_name"] = None

    fields["multi_use"] = (fields["multi_use_raw"] or "").lower().startswith("can be used multiple")
    fields["can_club_with_offers"] = bool(fields["can_club_with_offers_raw"]) and \
        fields["can_club_with_offers_raw"].lower().startswith("yes")
    fields["cards_stackable"] = (fields["cards_stackable_raw"] or "").lower().startswith("use several")

    return fields


def parse_current_rate(text):
    """Read the currently-displayed 'You Pay' block for whichever payment
    mode is selected."""
    off_m = re.search(r"(\d+(?:\.\d+)?)%\s*Off", text)
    earn_m = re.search(r"(\d+(?:\.\d+)?)%\s*Earn", text)
    return {
        "instant_discount_pct": float(off_m.group(1)) if off_m else None,
        "maxcoins_earn_pct": float(earn_m.group(1)) if earn_m else None,
    }


def read_dialog_lines(page, heading):
    """Read the modal's own text via its role=dialog container, dropping the
    heading (repeats the button label) and the trailing 'Close' button."""
    dialog = page.get_by_role("dialog").first
    text = dialog.inner_text(timeout=3000)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines and lines[0] == heading:
        lines = lines[1:]
    if lines and lines[-1] == "Close":
        lines = lines[:-1]
    return lines


def scrape_product(page, url):
    result = {"url": url}

    page.goto(url, wait_until="networkidle", timeout=25000)
    page.wait_for_timeout(1800)

    baseline_text = page.inner_text("body")
    result.update(parse_baseline_fields(baseline_text))
    result["logged_in"] = "Sign In" not in baseline_text

    # per-payment-mode discount/earn rates
    discounts = {}
    if "Select Your Payment Mode" in baseline_text:
        for mode in PAYMENT_MODES:
            try:
                page.get_by_text(mode, exact=True).first.click(timeout=3000)
                page.wait_for_timeout(900)
                mode_text = page.inner_text("body")
                discounts[mode] = parse_current_rate(mode_text)
            except Exception:
                discounts[mode] = None
    result["discounts"] = discounts

    if discounts:
        best_mode, best_pct = None, -1
        for mode, d in discounts.items():
            if d and d.get("instant_discount_pct") is not None and d["instant_discount_pct"] > best_pct:
                best_pct = d["instant_discount_pct"]
                best_mode = mode
        result["best_payment_method"] = best_mode
        result["best_discount_pct"] = best_pct if best_mode else None

    # How To Redeem modal
    try:
        page.get_by_text("How To Redeem", exact=True).first.click(timeout=3000)
        page.wait_for_timeout(900)
        result["how_to_redeem_steps"] = read_dialog_lines(page, "How To Redeem")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        result["how_to_redeem_steps"] = None

    # Terms & Conditions modal
    try:
        page.get_by_text("Terms & Conditions", exact=True).first.click(timeout=3000)
        page.wait_for_timeout(900)
        tc_lines = read_dialog_lines(page, "Terms & Conditions")
        result["full_terms_and_conditions"] = "\n".join(tc_lines)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        result["full_terms_and_conditions"] = None

    return result


def scrape_with_retry(page, url):
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            res = scrape_product(page, url)
            res["attempts"] = attempt
            return res
        except Exception as e:
            last_exc = e
            time.sleep(1.5)
    return {"url": url, "error": str(last_exc)[:300], "attempts": MAX_ATTEMPTS}


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def run():
    with open(CATALOG_FILE) as f:
        catalog = json.load(f)
    all_ids = list(catalog.keys())
    total = len(all_ids)

    progress = load_json(PROGRESS_FILE, {})
    remaining = [pid for pid in all_ids if pid not in progress]
    print(f"Total products: {total}. Already done: {len(progress)}. Remaining: {len(remaining)}.")

    p, browser, page = get_connected_page()
    failed = []

    for i, pid in enumerate(remaining, 1):
        entry = catalog[pid]
        url = entry["url"]
        done_so_far = total - len(remaining) + i
        print(f"[{done_so_far}/{total}] {entry.get('product_name')} ({pid})")

        res = scrape_with_retry(page, url)
        res["product_name"] = entry.get("product_name")
        res["maximize_product_id"] = pid
        from datetime import date
        res["last_scraped"] = date.today().isoformat()
        progress[pid] = res

        if res.get("error") or not res.get("brand_name"):
            failed.append(pid)
            print(f"    -> FAILED: {res.get('error', 'no brand_name parsed')}")

        if done_so_far % CHECKPOINT_EVERY == 0:
            save_json(PROGRESS_FILE, progress)
            save_json(FAILED_LOG, failed)

        time.sleep(0.6)

    save_json(PROGRESS_FILE, progress)
    save_json(FAILED_LOG, failed)
    close_all(p, browser, page)

    print(f"\nDone. {total - len(failed)}/{total} products scraped successfully.")
    if failed:
        print(f"{len(failed)} products need review — see {FAILED_LOG}")


if __name__ == "__main__":
    run()
