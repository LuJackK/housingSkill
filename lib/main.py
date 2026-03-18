#!/usr/bin/env python3
"""Main CLI for housing scraper."""

import json
import sys
from typing import List, Dict, Any

# Add lib directory to path so sibling modules are importable
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent))

from config import (
    MAX_PRICE_PER_PERSON,
    TARGET_LOCATION,
    MAX_DISTANCE_FROM_CENTER_KM,
    DATE_RANGES,
)
from mojcimer import scrape_all_listings
from parser import parse_listings
from filter import apply_all_filters


def run_pipeline(
    scrape_details: bool = True,
    max_price_per_person: int = MAX_PRICE_PER_PERSON,
    location: str = TARGET_LOCATION,
    max_km: float = MAX_DISTANCE_FROM_CENTER_KM,
    date_ranges = DATE_RANGES,
) -> List[Dict[str, Any]]:
    """
    Run the full pipeline: scrape -> parse -> filter.
    
    Args:
        scrape_details: Whether to scrape detail pages for contact info
        max_price_per_person: Maximum acceptable price per person
        location: Target location
        max_km: Maximum distance from center
        date_ranges: List of acceptable date ranges
        
    Returns:
        List of filtered, standardized listings
    """
    # Step 1: Scrape
    print("Scraping mojcimer.si...", file=sys.stderr)
    raw_listings = scrape_all_listings(scrape_details=scrape_details)
    print(f"Found {len(raw_listings)} raw listings", file=sys.stderr)
    
    # Step 2: Parse
    print("Normalizing data...", file=sys.stderr)
    parsed_listings = parse_listings(raw_listings)
    print(f"Parsed {len(parsed_listings)} listings", file=sys.stderr)
    
    # Step 3: Filter
    print(f"Applying filters: max €{max_price_per_person}/person, location={location}, max {max_km}km...", file=sys.stderr)
    filtered_listings = apply_all_filters(
        parsed_listings,
        max_price_per_person=max_price_per_person,
        location=location,
        max_km=max_km,
        date_ranges=date_ranges,
    )
    print(f"After filtering: {len(filtered_listings)} listings", file=sys.stderr)
    
    return filtered_listings


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scrape and filter housing listings from mojcimer.si"
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Skip scraping detail pages (faster, less info)",
    )
    parser.add_argument(
        "--max-price",
        type=int,
        default=MAX_PRICE_PER_PERSON,
        help=f"Maximum price per person (default: {MAX_PRICE_PER_PERSON})",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=TARGET_LOCATION,
        help=f"Target location (default: {TARGET_LOCATION})",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output",
    )
    
    args = parser.parse_args()
    
    # Run pipeline
    results = run_pipeline(
        scrape_details=not args.no_details,
        max_price_per_person=args.max_price,
        location=args.location,
        max_km=MAX_DISTANCE_FROM_CENTER_KM,
        date_ranges=DATE_RANGES,
    )
    
    # Output results
    json_output = json.dumps(
        results,
        indent=2 if args.pretty else None,
        ensure_ascii=False,
        default=str,
    )
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
