#!/usr/bin/env python3
"""LLM analysis of pre-filtered housing listings.

Reads filtered JSON files from score.py and analyzes each listing
with the Hunter model via OpenRouter API. Writes analysis JSON files
that report.py consumes.
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
REPORTS_DIR = BASE_DIR / 'reports'
INQUIRIES_DIR = BASE_DIR / 'inquiries'

# OpenRouter config
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/hunter-alpha"

ANALYSIS_PROMPT = """You are analyzing apartment rental listings for a student group.

INQUIRY: {inquiry_desc}

LISTING #{idx} of {total}:
Title: {title}
URL: {url}
Price: {price_eur} EUR total, ~{price_pp} EUR/person
Capacity: {capacity} people
Size: {size_sqm} m²
Location: {address}
Description: {description}

Analyze this listing and respond with ONLY valid JSON (no markdown, no explanation):
{{
  "verdict": "Recommended" | "Decent" | "Skip",
  "positives": ["positive aspect 1", ...],
  "negatives": ["negative aspect 1", ...],
  "restrictions": ["any restrictions", ...],
  "rental_period": "description of rental period",
  "who_allowed": "who can rent (students, anyone, etc.)",
  "people_offered": "how many people / room arrangement",
  "costs_included": "utilities status",
  "avg_utilities": null or "estimated utilities cost"
}}

Verdict criteria:
- Recommended: matches dates, budget, capacity, good location/value
- Decent: partially matches, has some issues but worth considering
- Skip: wrong dates, over budget, girls-only, too small, or other dealbreakers

Focus on: date compatibility, price per person vs budget, capacity fit, location."""


def get_openrouter_key() -> str:
    """Get OpenRouter API key from OpenClaw auth profiles."""
    # Primary: OpenClaw auth profiles
    auth_path = Path.home() / '.openclaw' / 'agents' / 'main' / 'agent' / 'auth-profiles.json'
    if auth_path.exists():
        with open(auth_path) as f:
            data = json.load(f)
        profiles = data.get('profiles', {})
        for v in profiles.values():
            if isinstance(v, dict) and v.get('provider') == 'openrouter':
                return v.get('key', '')
    # Fallback: env var
    return os.environ.get('OPENROUTER_API_KEY', '')


def analyze_listing(listing: dict, inquiry: dict, idx: int, total: int, api_key: str) -> dict:
    """Send a listing to Hunter for analysis, return parsed result."""
    desc = listing.get('description_en', '') or listing.get('description_full', '') or listing.get('description', '')
    price = listing.get('price_eur') or listing.get('price') or 0
    capacity = listing.get('capacity') or 1
    price_pp = round(price / capacity) if capacity else price

    inquiry_desc = f"{inquiry.get('name', inquiry.get('inquiry', 'Unknown'))} - {inquiry.get('people', 1)} people, max €{inquiry.get('max_price_per_person', 300)}/pp"

    prompt = ANALYSIS_PROMPT.format(
        inquiry_desc=inquiry_desc,
        idx=idx,
        total=total,
        title=listing.get('title', 'Unknown'),
        url=listing.get('url', ''),
        price_eur=price,
        price_pp=price_pp,
        capacity=capacity,
        size_sqm=listing.get('size_sqm', '?'),
        address=listing.get('address', '') or listing.get('location_raw', 'Unknown'),
        description=desc[:1500] if desc else 'No description',
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)
        result["url"] = listing.get('url', '')
        result["title"] = listing.get('title', '')
        # Map verdict_class for report template
        v = result.get('verdict', 'Decent').lower()
        result["verdict_class"] = {"recommended": "good", "decent": "decent", "skip": "bad"}.get(v, "decent")
        return result

    except Exception as e:
        print(f"  ⚠ Error analyzing listing {idx}: {e}", file=sys.stderr, flush=True)
        return {
            "url": listing.get('url', ''),
            "title": listing.get('title', ''),
            "verdict": "Decent",
            "verdict_class": "decent",
            "positives": [],
            "negatives": [f"Analysis error: {str(e)[:100]}"],
            "restrictions": [],
            "rental_period": "",
            "who_allowed": "",
            "people_offered": "",
            "costs_included": "",
            "avg_utilities": None,
        }


def analyze_inquiry(inquiry_name: str, inquiry: dict, today_str: str, api_key: str):
    """Analyze all filtered listings for one inquiry."""
    filtered_path = DATA_DIR / f"filtered_{inquiry_name}_{today_str}.json"
    if not filtered_path.exists():
        print(f"  No filtered data for {inquiry_name}", file=sys.stderr, flush=True)
        return

    with open(filtered_path) as f:
        data = json.load(f)

    listings = data.get('listings', [])
    if not listings:
        print(f"  No listings to analyze for {inquiry_name}", file=sys.stderr, flush=True)
        return

    print(f"\nAnalyzing {inquiry_name}: {len(listings)} listings", file=sys.stderr, flush=True)
    analyses = []

    for i, listing in enumerate(listings, 1):
        print(f"  [{i}/{len(listings)}] {listing.get('title', '?')[:50]}", file=sys.stderr, flush=True)
        result = analyze_listing(listing, inquiry, i, len(listings), api_key)
        analyses.append(result)
        # Rate limit: small delay between calls
        if i < len(listings):
            time.sleep(1)

    # Count verdicts
    verdicts = [a.get('verdict', 'Decent') for a in analyses]
    output = {
        "inquiry": inquiry_name,
        "date": today_str,
        "total_analyzed": len(analyses),
        "recommended": verdicts.count("Recommended"),
        "decent": verdicts.count("Decent"),
        "skip": verdicts.count("Skip"),
        "analysis": analyses,
    }

    output_path = REPORTS_DIR / f"analysis_{inquiry_name}_{today_str}.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Saved: {output_path}", file=sys.stderr, flush=True)
    print(f"  Verdicts: {output['recommended']} recommended, {output['decent']} decent, {output['skip']} skip", file=sys.stderr, flush=True)


def main():
    today_str = date.today().strftime('%Y-%m-%d')
    api_key = get_openrouter_key()
    if not api_key:
        print("ERROR: No OpenRouter API key found", file=sys.stderr, flush=True)
        sys.exit(1)

    print(f"=== LLM Analysis for {today_str} ===", file=sys.stderr, flush=True)

    for inquiry_file in sorted(INQUIRIES_DIR.glob('*.yaml')):
        import yaml
        with open(inquiry_file) as f:
            inquiry = yaml.safe_load(f)
        name = inquiry_file.stem
        analyze_inquiry(name, inquiry, today_str, api_key)

    print("\n=== Analysis complete ===", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
