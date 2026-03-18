#!/usr/bin/env python3
"""Pre-filter and score listings programmatically before LLM analysis.

This script runs deterministic checks to rank listings, so the LLM
only needs to analyze the most promising candidates.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
REPORTS_DIR = BASE_DIR / 'reports'
INQUIRIES_DIR = BASE_DIR / 'inquiries'

import yaml


def load_inquiry(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def score_listing(listing: dict, inquiry: dict) -> dict:
    """
    Score a listing against an inquiry. Returns score breakdown.
    Higher = better match.
    """
    score = 0
    flags = []
    auto_reject = False

    price = listing.get('price_eur') or listing.get('price') or 0
    capacity = listing.get('capacity') or 0
    size = listing.get('size_sqm') or 0
    people = inquiry.get('people', 1)
    max_price_pp = inquiry.get('max_price_per_person', 300)
    desc = (listing.get('description_full', '') or listing.get('description', '') or '').lower()

    # === Price per person ===
    if capacity > 0:
        price_pp = price / capacity
    else:
        price_pp = price

    if price_pp <= max_price_pp:
        score += 30
        if price_pp <= max_price_pp * 0.7:
            score += 10  # Great deal
    elif price_pp <= max_price_pp * 1.2:
        score += 10  # Slightly over budget
        flags.append(f"€{round(price_pp)}/pp over budget")
    else:
        score -= 20
        flags.append(f"€{round(price_pp)}/pp way over budget")

    # === Capacity ===
    if capacity >= people:
        score += 20
    elif capacity >= people - 1:
        score += 5
        flags.append(f"Fits {capacity}, need {people}")
    else:
        score -= 30
        flags.append(f"Only {capacity} beds, need {people}")

    # === Size ===
    if size > 0:
        sqm_per_person = size / max(capacity, 1)
        if sqm_per_person >= 15:
            score += 10
        elif sqm_per_person >= 10:
            score += 5
        else:
            flags.append(f"Tight: {round(sqm_per_person)}m²/person")

    # === Date matching ===
    date_ranges = inquiry.get('date_ranges', [])
    is_school_year = any(
        dr.get('to', '') >= '2027' if isinstance(dr, dict) else False
        for dr in date_ranges
    )

    # Check description for date clues
    if 'do konca junija' in desc or 'do junija' in desc or 'do 6.2026' in desc or 'do 7.2026' in desc:
        if is_school_year:
            score -= 40
            flags.append("Only until June — no school year")
            auto_reject = True
        else:
            score += 20  # Good for summer

    if 'šolsko leto' in desc or 'od oktobra' in desc or 'od 10' in desc or '2026/2027' in desc or '2026/27' in desc:
        if is_school_year:
            score += 25
        else:
            score += 5  # Might also do summer

    if 'daljše obdobje' in desc or 'dolgoročno' in desc:
        score += 10

    # === Gender restrictions ===
    gender = inquiry.get('gender', '').lower()
    if 'punce' in desc or 'študentke' in desc or 'dekle' in desc or 'girl' in desc or 'female' in desc:
        if 'boy' in gender or 'male' in gender:
            score -= 50
            flags.append("Girls only — reject")
            auto_reject = True

    # === Utilities ===
    if 'stroški vključeni' in desc or 'vključeni stroški' in desc or 'brez stroškov' in desc:
        score += 15
        flags.append("Utilities included")
    elif 'stroški' in desc:
        # Try to extract utilities amount
        util_match = re.search(r'(\d+)\s*(?:€|eur|evrov?)\s*(?:stroški|stroškov)', desc)
        if util_match:
            util_cost = int(util_match.group(1))
            if util_cost <= 50:
                score += 10
            flags.append(f"Utilities ~€{util_cost}")

    # === Location bonus ===
    location = (listing.get('address', '') or listing.get('location', '') or '').lower()
    if 'center' in location or 'centr' in location:
        score += 10
    elif 'koper' in location:
        score += 5

    # === Freshness ===
    published = listing.get('published', '') or listing.get('date', '')
    # Listings from main page tend to be sorted by date

    return {
        'url': listing.get('url', ''),
        'score': score,
        'flags': flags,
        'auto_reject': auto_reject,
        'price_pp': round(price_pp) if price_pp else 0,
        'meets_capacity': capacity >= people,
    }


def filter_and_rank(listings: list, inquiry: dict, top_n: int = 25) -> tuple:
    """
    Score all listings, return (top_listings, rejected_count).
    """
    scored = []
    rejected = 0

    for listing in listings:
        result = score_listing(listing, inquiry)
        if result['auto_reject']:
            rejected += 1
            continue
        scored.append((listing, result))

    # Sort by score descending
    scored.sort(key=lambda x: x[1]['score'], reverse=True)

    # Attach score to listings
    top = []
    for listing, score_info in scored[:top_n]:
        listing['_score'] = score_info
        top.append(listing)

    return top, rejected


def main():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    enriched_path = DATA_DIR / f"enriched_{today_str}.json"
    if not enriched_path.exists():
        print(f"ERROR: No enriched data for {today_str}", file=sys.stderr)
        sys.exit(1)

    with open(enriched_path) as f:
        data = json.load(f)

    all_listings = data.get('listings', [])
    print(f"Total listings: {len(all_listings)}", file=sys.stderr)

    for inquiry_file in sorted(INQUIRIES_DIR.glob('*.yaml')):
        inquiry = load_inquiry(inquiry_file)
        name = inquiry_file.stem

        top, rejected = filter_and_rank(all_listings, inquiry, top_n=25)

        print(f"\n{name}:", file=sys.stderr)
        print(f"  Auto-rejected: {rejected}", file=sys.stderr)
        print(f"  Top {len(top)} for LLM analysis", file=sys.stderr)
        for i, l in enumerate(top[:5], 1):
            s = l.get('_score', {})
            print(f"  #{i}: {l.get('title', '?')} | score={s.get('score', 0)} | €{s.get('price_pp', '?')}/pp | {', '.join(s.get('flags', []))}", file=sys.stderr)

        # Save filtered listings for the LLM agent
        output = {
            'inquiry': name,
            'date': today_str,
            'total_listings': len(all_listings),
            'auto_rejected': rejected,
            'analyzed': len(top),
            'listings': [{k: v for k, v in l.items() if k != '_score'} for l in top],
            'scores': [l.get('_score', {}) for l in top],
        }

        output_path = DATA_DIR / f"filtered_{name}_{today_str}.json"
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
