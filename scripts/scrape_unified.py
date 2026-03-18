#!/usr/bin/env python3
"""Unified multi-source housing scraper.

Scrapes mojcimer and nepremicnine, normalizes to common format,
deduplicates, and outputs a single JSON file for the enrichment pipeline.

Usage:
    python3 scrape_unified.py [--output data/raw_YYYY-MM-DD.json]
    python3 scrape_unified.py --sources mojcimer,nepremicnine --region koper
"""

import sys
import os
import json
import re
import time
import argparse
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Set

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
LIB_DIR = BASE_DIR / 'lib'
SCRAPER_DIR = Path(__file__).parent.parent.parent / 'slovenia-housing-scraper' / 'scripts'

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRAPER_DIR))


def scrape_mojcimer() -> List[Dict[str, Any]]:
    """Scrape mojcimer.si using existing curl-based scraper."""
    from mojcimer import scrape_all_listings
    from parser import parse_listings as normalize
    
    print("━" * 50, file=sys.stderr)
    print("Source: mojcimer.si", file=sys.stderr)
    print("━" * 50, file=sys.stderr)
    
    try:
        raw = scrape_all_listings(scrape_details=False)
        normalized = normalize(raw)
        for l in normalized:
            l['source'] = 'mojcimer'
        print(f"  ✅ {len(normalized)} listings", file=sys.stderr)
        return normalized
    except Exception as e:
        print(f"  ❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []


def scrape_nepremicnine(region_code: str = "2", categories: List[str] = None) -> List[Dict[str, Any]]:
    """Scrape nepremicnine.net using Camoufox stealth browser.
    
    Args:
        region_code: nepremicnine region code (2=J.Primorska/Koper, 14=LJ-mesto)
        categories: List of category slugs (default: stanovanje, soba, garsonjera)
    """
    from scraper import HousingScraper
    from nepremicnine import parse_listings_page, fetch_listing_detail
    
    if categories is None:
        categories = ["stanovanje", "soba", "garsonjera"]
    
    print("━" * 50, file=sys.stderr)
    print("Source: nepremicnine.net", file=sys.stderr)
    print("━" * 50, file=sys.stderr)
    
    all_listings = []
    seen_urls: Set[str] = set()
    
    try:
        with HousingScraper(headless=True, warm_up=True) as scraper:
            for cat in categories:
                url = f"https://www.nepremicnine.net/oglasi-oddaja/{cat}/?r={region_code}"
                print(f"  Fetching {cat}...", file=sys.stderr)
                
                try:
                    html = scraper.fetch(url, wait_seconds=4.0)
                    listings = parse_listings_page(html, cat)
                    
                    new = 0
                    for l in listings:
                        if l['url'] not in seen_urls:
                            seen_urls.add(l['url'])
                            l['source'] = 'nepremicnine'
                            all_listings.append(l)
                            new += 1
                    print(f"    {cat}: {len(listings)} found, {new} new", file=sys.stderr)
                except Exception as e:
                    print(f"    {cat}: error - {e}", file=sys.stderr)
                
                time.sleep(1)
            
            # Fetch details for top listings
            detail_limit = min(15, len(all_listings))
            print(f"\n  Fetching details for top {detail_limit}...", file=sys.stderr)
            for i, listing in enumerate(all_listings[:detail_limit]):
                try:
                    detail = fetch_listing_detail(scraper, listing['url'])
                    if detail:
                        for k, v in detail.items():
                            if v and k not in listing:
                                listing[k] = v
                    print(f"    [{i+1}/{detail_limit}] {listing.get('title', '?')[:40]}", file=sys.stderr)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"    [{i+1}] error: {e}", file=sys.stderr)
        
        print(f"  ✅ {len(all_listings)} listings", file=sys.stderr)
        
    except Exception as e:
        print(f"  ❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    
    return all_listings


def normalize_for_enrichment(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a listing to the format expected by enrich.py and score.py."""
    source = listing.get('source', 'unknown')
    
    price = listing.get('price') or listing.get('price_eur')
    capacity = listing.get('capacity')
    size = listing.get('size_sqm')
    location = listing.get('location', '')
    address = listing.get('address', location)
    
    url = listing.get('url', '')
    listing_id = ''
    if source == 'mojcimer':
        listing_id = url.rstrip('/').split('/')[-1] if url else ''
    elif source == 'nepremicnine':
        id_match = re.search(r'_(\d{5,})/?$', url)
        listing_id = id_match.group(1) if id_match else url.split('/')[-1]
    
    return {
        'title': listing.get('title', ''),
        'location': location,
        'address': address,
        'price': price,
        'price_per_person': listing.get('price_per_person'),
        'capacity': capacity,
        'size_sqm': size,
        'baths': listing.get('baths'),
        'who_allowed': listing.get('who_allowed', 'all'),
        'room_type': listing.get('room_type', ''),
        'contact_name': listing.get('contact_name', ''),
        'contact_phone': listing.get('contact_phone', ''),
        'contact_email': listing.get('contact_email', ''),
        'description': listing.get('description', ''),
        'description_full': listing.get('description_full', ''),
        'description_en': listing.get('description_en', ''),
        'thumbnail': listing.get('thumbnail', ''),
        'images': listing.get('images', []),
        'images_local': listing.get('images_local', []),
        'amenities': listing.get('amenities', []),
        'url': url,
        'listing_id': listing_id,
        'source': source,
        'year': listing.get('year'),
        'floor': listing.get('floor'),
        'energy_class': listing.get('energy_class'),
        'has_parking': listing.get('has_parking', False),
        'has_balcony': listing.get('has_balcony', False),
        'has_elevator': listing.get('has_elevator', False),
        'furnished': listing.get('furnished', False),
    }


def deduplicate(all_listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate listings across sources. Mojcimer takes priority."""
    source_priority = {'mojcimer': 0, 'nepremicnine': 1}
    
    seen_urls: Dict[str, int] = {}
    seen_keys: Dict[tuple, int] = {}
    unique = []
    
    sorted_listings = sorted(all_listings, key=lambda l: source_priority.get(l.get('source', ''), 99))
    
    for listing in sorted_listings:
        url = listing.get('url', '')
        title = listing.get('title', '').lower().strip()
        price = listing.get('price') or listing.get('price_eur')
        
        if url and url in seen_urls:
            continue
        
        key = (title[:30], price)
        if key in seen_keys:
            continue
        
        if url:
            seen_urls[url] = len(unique)
        seen_keys[key] = len(unique)
        unique.append(listing)
    
    return unique


def main():
    parser = argparse.ArgumentParser(description="Unified housing scraper")
    parser.add_argument("--sources", default="mojcimer,nepremicnine",
                        help="Sources: mojcimer,nepremicnine (default: both)")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file")
    parser.add_argument("--region", default="koper",
                        help="Target region: koper or ljubljana (default: koper)")
    parser.add_argument("--no-details", action="store_true",
                        help="Skip fetching detail pages")
    args = parser.parse_args()
    
    sources = [s.strip() for s in args.sources.split(",")]
    region = args.region.lower()
    nep_region = "2" if region == "koper" else "14"
    
    today = date.today().strftime('%Y-%m-%d')
    output_path = Path(args.output) if args.output else DATA_DIR / f"raw_{today}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    all_listings = []
    
    print(f"\n🏠 Unified Housing Scraper", file=sys.stderr)
    print(f"   Region: {region}", file=sys.stderr)
    print(f"   Sources: {', '.join(sources)}", file=sys.stderr)
    print(f"   Date: {today}\n", file=sys.stderr)
    
    start_time = time.time()
    
    if "mojcimer" in sources:
        all_listings.extend(scrape_mojcimer())
    
    if "nepremicnine" in sources:
        all_listings.extend(scrape_nepremicnine(region_code=nep_region))
    
    # Normalize and deduplicate
    print(f"\n{'━' * 50}", file=sys.stderr)
    print(f"Normalizing {len(all_listings)} listings...", file=sys.stderr)
    normalized = [normalize_for_enrichment(l) for l in all_listings]
    
    print(f"Deduplicating...", file=sys.stderr)
    unique = deduplicate(normalized)
    print(f"  Removed {len(normalized) - len(unique)} duplicates", file=sys.stderr)
    
    by_source = {}
    for l in unique:
        src = l.get('source', 'unknown')
        by_source[src] = by_source.get(src, 0) + 1
    
    elapsed = time.time() - start_time
    
    print(f"\n{'━' * 50}", file=sys.stderr)
    print(f"✅ Results ({elapsed:.1f}s total)", file=sys.stderr)
    for src, count in sorted(by_source.items()):
        print(f"   {src}: {count}", file=sys.stderr)
    print(f"   Total unique: {len(unique)}", file=sys.stderr)
    
    output = {
        'date': today,
        'region': region,
        'total': len(unique),
        'by_source': by_source,
        'listings': unique,
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n   Saved: {output_path}", file=sys.stderr)
    return unique


if __name__ == "__main__":
    main()
