"""Report generator – formats analysis results into human-readable reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from housing_skill.models.listing import Listing, ListingCriteria

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates text and JSON reports from a list of scored listings."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_text_report(
        self,
        listings: list[Listing],
        criteria: ListingCriteria,
        generated_at: Optional[datetime] = None,
    ) -> str:
        """Return a formatted plain-text report string."""
        now = (generated_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = [
            "=" * 70,
            f"  SLOVENIAN RENTAL MARKET REPORT — {now}",
            "=" * 70,
            "",
            "SEARCH CRITERIA",
            "-" * 40,
        ]
        lines.extend(self._format_criteria(criteria))
        lines += [
            "",
            f"RESULTS  ({len(listings)} listings found)",
            "-" * 40,
            "",
        ]
        for rank, listing in enumerate(listings, start=1):
            lines.extend(self._format_listing(rank, listing))
            lines.append("")

        lines += [
            "=" * 70,
            "  End of report",
            "=" * 70,
        ]
        return "\n".join(lines)

    def generate_json_report(
        self,
        listings: list[Listing],
        criteria: ListingCriteria,
        generated_at: Optional[datetime] = None,
    ) -> dict:
        """Return a dictionary representation of the report (JSON-serialisable)."""
        return {
            "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
            "criteria": criteria.to_dict(),
            "total_results": len(listings),
            "listings": [l.to_dict() for l in listings],
        }

    def save_text_report(
        self,
        listings: list[Listing],
        criteria: ListingCriteria,
        path: Path,
        generated_at: Optional[datetime] = None,
    ) -> Path:
        """Write a text report to *path* and return the resolved path."""
        text = self.generate_text_report(listings, criteria, generated_at)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("Text report saved to %s", path)
        return path

    def save_json_report(
        self,
        listings: list[Listing],
        criteria: ListingCriteria,
        path: Path,
        generated_at: Optional[datetime] = None,
    ) -> Path:
        """Write a JSON report to *path* and return the resolved path."""
        data = self.generate_json_report(listings, criteria, generated_at)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("JSON report saved to %s", path)
        return path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_criteria(criteria: ListingCriteria) -> list[str]:
        lines: list[str] = []
        if criteria.max_price_eur:
            lines.append(f"  Max price:      €{criteria.max_price_eur:,.0f}/month")
        if criteria.min_price_eur:
            lines.append(f"  Min price:      €{criteria.min_price_eur:,.0f}/month")
        if criteria.min_size_m2:
            lines.append(f"  Min size:       {criteria.min_size_m2} m²")
        if criteria.max_size_m2:
            lines.append(f"  Max size:       {criteria.max_size_m2} m²")
        if criteria.min_rooms:
            lines.append(f"  Min rooms:      {criteria.min_rooms}")
        if criteria.max_rooms:
            lines.append(f"  Max rooms:      {criteria.max_rooms}")
        if criteria.locations:
            lines.append(f"  Locations:      {', '.join(criteria.locations)}")
        if criteria.preferred_locations:
            lines.append(
                f"  Preferred loc:  {', '.join(criteria.preferred_locations)}"
            )
        if criteria.furnished is not None:
            lines.append(
                f"  Furnished:      {'yes' if criteria.furnished else 'no'}"
            )
        if criteria.keywords:
            lines.append(f"  Keywords:       {', '.join(criteria.keywords)}")
        if not lines:
            lines.append("  (no filters applied)")
        return lines

    @staticmethod
    def _format_listing(rank: int, listing: Listing) -> list[str]:
        price_str = f"€{listing.price_eur:,.0f}/mo" if listing.price_eur else "N/A"
        size_str = f"{listing.size_m2} m²" if listing.size_m2 else "N/A"
        rooms_str = str(listing.rooms) if listing.rooms else "N/A"
        ppm2_str = (
            f"€{listing.price_per_m2:.1f}/m²" if listing.price_per_m2 else "N/A"
        )
        furnished_str = (
            "yes" if listing.furnished
            else "no" if listing.furnished is False
            else "unknown"
        )
        return [
            f"  #{rank:>2}  [{listing.score:.2f}]  {listing.title}",
            f"       Price:    {price_str}  |  Size: {size_str}  |  Rooms: {rooms_str}  |  {ppm2_str}",
            f"       Location: {listing.location}",
            f"       Furnished: {furnished_str}",
            f"       URL:      {listing.url}",
            f"       Source:   {listing.source}",
        ]
