"""Base scraper interface for Slovenian real-estate websites."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

from housing_skill.models.listing import Listing, ListingCriteria

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "sl-SI,sl;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 20  # seconds


class BaseScraper(ABC):
    """Abstract base class for all real-estate scrapers."""

    source_name: str = "unknown"

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self, criteria: ListingCriteria) -> list[Listing]:
        """Scrape listings matching *criteria* and return them as a list.

        Sub-classes should implement :meth:`_fetch_listings` which returns
        raw :class:`Listing` objects.  This method applies hard filters
        defined in *criteria* before returning results.
        """
        try:
            listings = self._fetch_listings(criteria)
        except Exception as exc:  # pragma: no cover
            logger.error("Error scraping %s: %s", self.source_name, exc)
            return []

        return self._apply_hard_filters(listings, criteria)

    # ------------------------------------------------------------------
    # Protected helpers for sub-classes
    # ------------------------------------------------------------------

    @abstractmethod
    def _fetch_listings(self, criteria: ListingCriteria) -> list[Listing]:
        """Fetch raw listings from the source.  Must be implemented by sub-classes."""

    def _get(self, url: str, params: Optional[dict] = None) -> BeautifulSoup:
        """Perform a GET request and return a :class:`BeautifulSoup` object."""
        resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_hard_filters(
        listings: list[Listing], criteria: ListingCriteria
    ) -> list[Listing]:
        """Remove listings that violate hard constraints in *criteria*."""
        result = []
        for listing in listings:
            if (
                criteria.max_price_eur is not None
                and listing.price_eur is not None
                and listing.price_eur > criteria.max_price_eur
            ):
                continue
            if (
                criteria.min_price_eur is not None
                and listing.price_eur is not None
                and listing.price_eur < criteria.min_price_eur
            ):
                continue
            if (
                criteria.min_size_m2 is not None
                and listing.size_m2 is not None
                and listing.size_m2 < criteria.min_size_m2
            ):
                continue
            if (
                criteria.max_size_m2 is not None
                and listing.size_m2 is not None
                and listing.size_m2 > criteria.max_size_m2
            ):
                continue
            if (
                criteria.min_rooms is not None
                and listing.rooms is not None
                and listing.rooms < criteria.min_rooms
            ):
                continue
            if (
                criteria.max_rooms is not None
                and listing.rooms is not None
                and listing.rooms > criteria.max_rooms
            ):
                continue
            if criteria.furnished is not None and listing.furnished is not None:
                if listing.furnished != criteria.furnished:
                    continue
            if criteria.locations:
                if not any(
                    loc.lower() in listing.location.lower()
                    for loc in criteria.locations
                ):
                    continue
            result.append(listing)
        return result

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        """Extract a numeric EUR price from a text string."""
        import re

        cleaned = re.sub(r"[^\d,.]", "", text.replace(".", "").replace(",", "."))
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _parse_size(text: str) -> Optional[float]:
        """Extract a numeric size in m² from a text string."""
        import re

        match = re.search(r"([\d]+[,.]?[\d]*)\s*m", text.replace(",", "."))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
