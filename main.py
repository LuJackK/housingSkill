#!/usr/bin/env python3
"""Command-line interface for the housing skill."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from housing_skill import HousingSkill
from housing_skill.models import ListingCriteria
from housing_skill.scheduler import ReportScheduler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="housing-skill",
        description=(
            "Scrape Slovenian real-estate websites for rental listings, "
            "rank them by your criteria, and generate reports."
        ),
    )

    # Search filters
    parser.add_argument("--max-price", type=float, help="Maximum monthly rent in EUR")
    parser.add_argument("--min-price", type=float, help="Minimum monthly rent in EUR")
    parser.add_argument("--min-size", type=float, help="Minimum apartment size in m²")
    parser.add_argument("--max-size", type=float, help="Maximum apartment size in m²")
    parser.add_argument("--min-rooms", type=float, help="Minimum number of rooms")
    parser.add_argument("--max-rooms", type=float, help="Maximum number of rooms")
    parser.add_argument(
        "--location",
        action="append",
        dest="locations",
        metavar="LOCATION",
        help="Filter by location (can be repeated)",
    )
    parser.add_argument(
        "--prefer-location",
        action="append",
        dest="preferred_locations",
        metavar="LOCATION",
        help="Preferred location (higher score, can be repeated)",
    )
    parser.add_argument(
        "--furnished",
        choices=["yes", "no"],
        help="Filter by furnished status",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        metavar="KEYWORD",
        help="Keyword to search for in listings (can be repeated)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum number of results to return (default: 20)",
    )

    # Scoring weights
    parser.add_argument(
        "--price-weight",
        type=float,
        default=0.5,
        help="Weight given to price when scoring (0-1, default: 0.5)",
    )
    parser.add_argument(
        "--size-weight",
        type=float,
        default=0.5,
        help="Weight given to size when scoring (0-1, default: 0.5)",
    )

    # Output
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save report files (text + JSON)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "both"],
        default="text",
        help="Report format to print to stdout (default: text)",
    )

    # Scheduling
    parser.add_argument(
        "--schedule",
        type=int,
        metavar="SECONDS",
        help="Run repeatedly every SECONDS seconds (0 = run once)",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    criteria = ListingCriteria(
        max_price_eur=args.max_price,
        min_price_eur=args.min_price,
        min_size_m2=args.min_size,
        max_size_m2=args.max_size,
        min_rooms=args.min_rooms,
        max_rooms=args.max_rooms,
        locations=args.locations or [],
        preferred_locations=args.preferred_locations or [],
        furnished=True if args.furnished == "yes" else False if args.furnished == "no" else None,
        keywords=args.keywords or [],
        max_results=args.max_results,
        price_weight=args.price_weight,
        size_weight=args.size_weight,
    )

    skill = HousingSkill()

    if args.schedule:
        print(f"Starting scheduler (interval={args.schedule}s). Press Ctrl-C to stop.")

        def run_and_print() -> None:
            result = skill.run(criteria, output_dir=args.output_dir)
            _print_result(result, args.format)

        scheduler = ReportScheduler(
            callback=run_and_print,
            interval_seconds=args.schedule,
        )
        scheduler.start()
        try:
            import time
            while scheduler.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
    else:
        result = skill.run(criteria, output_dir=args.output_dir)
        _print_result(result, args.format)

    return 0


def _print_result(result: dict, fmt: str) -> None:
    if fmt in ("text", "both"):
        print(result["text_report"])
    if fmt in ("json", "both"):
        print(json.dumps(result["json_report"], indent=2, ensure_ascii=False))
    if result.get("text_report_path"):
        print(f"Text report saved: {result['text_report_path']}", file=sys.stderr)
    if result.get("json_report_path"):
        print(f"JSON report saved: {result['json_report_path']}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
