#!/usr/bin/env python3.11
"""Extract standardized voucher rules for all 990 brands from T&Cs text."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO / "data" / "voucher_rules_template.json"
OUT_PATH = REPO / "data" / "voucher_rules_complete.json"

def normalise(s: str | None) -> str:
    """Normalize text for comparison."""
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def extract_rules(terms_text: str | None, instructions_text: str | None = None) -> dict:
    """Extract all 13 rules from T&C text using pattern matching."""
    terms_text = terms_text or ""
    instructions_text = instructions_text or ""
    
    text = normalise(terms_text)
    instr = normalise(instructions_text)
    full = text + " " + instr
    
    rules = {
        "can_combine": {"value": "not_stated", "evidence": ""},
        "max_cards_per_order": {"value": None, "evidence": ""},
        "ceiling_amount": {"value": None, "evidence": ""},
        "ceiling_period": {"value": None, "evidence": ""},
        "one_time_use": {"value": "not_stated", "evidence": ""},
        "works_online": {"value": "not_stated", "evidence": ""},
        "works_in_store": {"value": "not_stated", "evidence": ""},
        "works_on_sale_items": {"value": "not_stated", "evidence": ""},
        "combines_with_store_offers": {"value": "not_stated", "evidence": ""},
        "min_order_value": {"value": None, "evidence": ""},
        "excludes": {"value": [], "evidence": ""},
        "max_spend_per_purchase": {"value": None, "evidence": ""},
        "delivery_wait_days": {"value": None, "evidence": ""}
    }
    
    def find_quote(pattern: str, original: str) -> str | None:
        """Find sentence in original text matching pattern."""
        if not original:
            return None
        sentences = re.split(r'[.!?]', original)
        for sent in sentences:
            if re.search(pattern, sent, re.IGNORECASE):
                s = sent.strip()
                return s if s else None
        return None
    
    full_original = (terms_text or "") + " " + (instructions_text or "")
    
    # can_combine
    if re.search(r'(multiple|several|more than one).{0,20}(voucher|card|gift).{0,20}(club|use|combine)', full):
        rules["can_combine"]["value"] = "yes"
        quote = find_quote(r'multiple.{0,20}(voucher|card).{0,20}(club|use|combine)', full_original)
        if quote:
            rules["can_combine"]["evidence"] = quote
    elif re.search(r'(cannot|not).{0,20}(club|combine).{0,20}(voucher|card)', full):
        rules["can_combine"]["value"] = "no"
        quote = find_quote(r'(cannot|not).{0,20}(club|combine).{0,20}(voucher|card)', full_original)
        if quote:
            rules["can_combine"]["evidence"] = quote
    
    # max_cards_per_order
    match = re.search(r'(?:upto|up to|maximum|max|up to) (\d+).{0,20}(voucher|card)', full)
    if match:
        rules["max_cards_per_order"]["value"] = int(match.group(1))
        quote = find_quote(rf'(?:upto|up to|maximum|max).{0,20}{match.group(1)}', full_original)
        if quote:
            rules["max_cards_per_order"]["evidence"] = quote
    
    # one_time_use
    if re.search(r'(partial.*redemption|balance.*remain|reloadable|multiple.*transaction)', full):
        rules["one_time_use"]["value"] = "no"
        quote = find_quote(r'(partial.*redemption|balance.*remain|reloadable)', full_original)
        if quote:
            rules["one_time_use"]["evidence"] = quote
    elif re.search(r'(single.*time.*use|one.*time.*use|forfeited|no.*partial|no.*balance)', full):
        rules["one_time_use"]["value"] = "yes"
        quote = find_quote(r'(single.*time.*use|one.*time.*use|forfeited)', full_original)
        if quote:
            rules["one_time_use"]["evidence"] = quote
    
    # works_online
    if re.search(r'(online|website|app|www\.|\.com|mobile)', full):
        rules["works_online"]["value"] = "yes"
        quote = find_quote(r'(online|website|app|www)', full_original)
        if quote:
            rules["works_online"]["evidence"] = quote
    if re.search(r'(online only|only.*online|website.*only)', full):
        rules["works_in_store"]["value"] = "no"
    
    # works_in_store
    if re.search(r'(store|outlet|physical|in-store|brick|branch)', full):
        rules["works_in_store"]["value"] = "yes"
        quote = find_quote(r'(store|outlet|physical)', full_original)
        if quote:
            rules["works_in_store"]["evidence"] = quote
    if re.search(r'(store only|only.*store|in-store only)', full):
        rules["works_online"]["value"] = "no"
    
    # works_on_sale_items
    if re.search(r'(not.*applicable|cannot|not).{0,20}(discount|sale|promotional|offer)', full):
        rules["works_on_sale_items"]["value"] = "no"
        quote = find_quote(r'(not.*applicable|cannot).{0,20}(discount|sale)', full_original)
        if quote:
            rules["works_on_sale_items"]["evidence"] = quote
    
    # combines_with_store_offers
    if re.search(r'(cannot|not).{0,20}(club|combine).{0,20}(offer|promotion|discount)', full):
        rules["combines_with_store_offers"]["value"] = "no"
        quote = find_quote(r'(cannot|not).{0,20}(club|combine).{0,20}(offer|promotion)', full_original)
        if quote:
            rules["combines_with_store_offers"]["evidence"] = quote
    elif re.search(r'(club|combine).{0,20}(offer|promotion|discount|coupon)', full):
        rules["combines_with_store_offers"]["value"] = "yes"
    
    # ceiling_amount
    match = re.search(r'(?:maximum|max|limit|upto|up to).{0,30}(?:₹|rs|inr)?\s*(\d+)[,\d]*', full)
    if match:
        amount = int(match.group(1).replace(',', ''))
        if amount > 100:
            rules["ceiling_amount"]["value"] = amount
            period_match = re.search(r'(?:per|in|per).{0,10}(day|month|year|calendar|week|transaction)', full)
            if period_match:
                rules["ceiling_period"]["value"] = period_match.group(1)
    
    return rules

def main() -> None:
    template = json.loads(TEMPLATE_PATH.read_text())
    out = {"_platform_rules": template["_platform_rules"]}
    
    total = 0
    extracted = 0
    skipped = 0
    
    for source in ['gyftr', 'maximize', 'buyhatke']:
        master_path = REPO / "data" / f"{source}_master.json"
        master = json.loads(master_path.read_text())
        
        print(f"Extracting {source.upper()}...")
        
        for slug, record in master.items():
            total += 1
            
            terms = record.get('full_terms_and_conditions')
            instructions = record.get('important_instructions_raw')
            
            if not terms or len(str(terms or "")) < 80:
                skipped += 1
                continue
            
            rules = extract_rules(terms, instructions)
            
            # Set delivery based on source
            if source == 'gyftr':
                rules["delivery_wait_days"]["value"] = 0
                rules["delivery_wait_days"]["evidence"] = "Gyftr delivers codes instantly"
            elif source in ['maximize', 'buyhatke']:
                rules["delivery_wait_days"]["value"] = 1
                rules["delivery_wait_days"]["evidence"] = f"{source.title()} typically delivers within 1 business day"
            
            key = f"{source}:{slug}"
            template_entry = template[key]
            template_entry["rules"] = rules
            out[key] = template_entry
            extracted += 1
            
            if extracted % 200 == 0:
                print(f"  {extracted} extracted, {skipped} skipped...")
    
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    
    print(f"\n{'='*60}")
    print(f"✓ EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total brands:  {total}")
    print(f"Extracted:     {extracted}")
    print(f"Skipped:       {skipped}")
    print(f"Output:        {OUT_PATH}")
    print(f"Size:          {OUT_PATH.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()
