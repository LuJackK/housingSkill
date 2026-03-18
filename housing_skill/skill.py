"""Main HousingSkill interface – the entry point for AI agents."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from housing_skill.analyzer import ListingAnalyzer
from housing_skill.models.listing import Listing, ListingCriteria
from housing_skill.reporter import ReportGenerator
from housing_skill.scrapers import BolhaScraper, NepremicnineScraper
from housing_skill.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HousingSkill:
    """Housing skill for AI agents.

    Orchestrates scraping Slovenian real-estate sites, analysing and ranking
    the results against user-defined criteria, and generating reports.

    Typical usage::

        from housing_skill import HousingSkill
        from housing_skill.models import ListingCriteria

        skill = HousingSkill()
        criteria = ListingCriteria(
            max_price_eur=900,
            min_size_m2=40,
            locations=["Ljubljana"],
            furnished=True,
        )
        result = skill.run(criteria, output_dir=Path("reports"))
        print(result["text_report"])
    """

    def __init__(
        self,
        scrapers: Optional[list[BaseScraper]] = None,
        analyzer: Optional[ListingAnalyzer] = None,
        reporter: Optional[ReportGenerator] = None,
    ) -> None:
        self.scrapers: list[BaseScraper] = scrapers or [
            NepremicnineScraper(),
            BolhaScraper(),
        ]
        self.analyzer = analyzer or ListingAnalyzer()
        self.reporter = reporter or ReportGenerator()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def search(self, criteria: ListingCriteria) -> list[Listing]:
        """Scrape all sources and return ranked listings for *criteria*.

        This is the primary method for AI agents to call.  It:
        1. Scrapes all configured sources in order.
        2. De-duplicates results by URL.
        3. Analyses and scores every listing against *criteria*.
        4. Returns the top results sorted by score.
        """
        raw: list[Listing] = []
        for scraper in self.scrapers:
            logger.info("Scraping %s …", scraper.source_name)
            fetched = scraper.scrape(criteria)
            logger.info("  → %d listings from %s", len(fetched), scraper.source_name)
            raw.extend(fetched)

        # De-duplicate by URL
        seen: set[str] = set()
        unique: list[Listing] = []
        for listing in raw:
            if listing.url not in seen:
                seen.add(listing.url)
                unique.append(listing)

        logger.info("Total unique listings before analysis: %d", len(unique))
        ranked = self.analyzer.analyze(unique, criteria)
        logger.info("Returning %d ranked listings.", len(ranked))
        return ranked

    def run(
        self,
        criteria: ListingCriteria,
        output_dir: Optional[Path] = None,
    ) -> dict:
        """Execute a full search-analyse-report cycle.

        Returns a dictionary with keys:
        * ``listings`` – list of :class:`Listing` objects
        * ``text_report`` – formatted text report
        * ``json_report`` – dict representation of the report
        * ``text_report_path`` – :class:`Path` if saved, else ``None``
        * ``json_report_path`` – :class:`Path` if saved, else ``None``
        """
        generated_at = datetime.now(timezone.utc)
        listings = self.search(criteria)

        text_report = self.reporter.generate_text_report(
            listings, criteria, generated_at=generated_at
        )
        json_report = self.reporter.generate_json_report(
            listings, criteria, generated_at=generated_at
        )

        text_path: Optional[Path] = None
        json_path: Optional[Path] = None
        if output_dir is not None:
            output_dir = Path(output_dir)
            timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
            text_path = self.reporter.save_text_report(
                listings,
                criteria,
                output_dir / f"report_{timestamp}.txt",
                generated_at=generated_at,
            )
            json_path = self.reporter.save_json_report(
                listings,
                criteria,
                output_dir / f"report_{timestamp}.json",
                generated_at=generated_at,
            )

        return {
            "listings": listings,
            "text_report": text_report,
            "json_report": json_report,
            "text_report_path": text_path,
            "json_report_path": json_path,
        }

    def schedule(
        self,
        criteria: ListingCriteria,
        interval_seconds: int = 3600,
        output_dir: Optional[Path] = None,
    ):
        """Return a :class:`~housing_skill.scheduler.ReportScheduler` for *criteria*.

        The caller is responsible for starting and stopping the scheduler::

            scheduler = skill.schedule(criteria, interval_seconds=3600, output_dir=Path("reports"))
            scheduler.start()
        """
        from housing_skill.scheduler import build_scheduler

        return build_scheduler(
            self, criteria, interval_seconds=interval_seconds, output_dir=output_dir
        )
