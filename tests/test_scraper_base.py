"""Tests for housing_skill.scrapers.base."""

from __future__ import annotations

import pytest

from housing_skill.models.listing import ListingCriteria
from housing_skill.scrapers.base import BaseScraper
from tests.conftest import make_listing


class _DummyScraper(BaseScraper):
    """Minimal concrete scraper for testing the base class."""

    source_name = "dummy"

    def __init__(self, listings=None):
        super().__init__()
        self._listings = listings or []

    def _fetch_listings(self, criteria):
        return list(self._listings)


class TestBaseScraper:
    def test_scrape_returns_filtered_results(self):
        listings = [
            make_listing(id="a", price_eur=500, size_m2=40),
            make_listing(id="b", price_eur=1200, size_m2=60),  # over max price
            make_listing(id="c", price_eur=800, size_m2=20),   # under min size
        ]
        scraper = _DummyScraper(listings=listings)
        criteria = ListingCriteria(max_price_eur=1000, min_size_m2=30)
        result = scraper.scrape(criteria)
        ids = [l.id for l in result]
        assert "a" in ids
        assert "b" not in ids
        assert "c" not in ids

    def test_hard_filter_min_price(self):
        listings = [
            make_listing(id="cheap", price_eur=200),
            make_listing(id="ok", price_eur=600),
        ]
        scraper = _DummyScraper(listings=listings)
        result = scraper.scrape(ListingCriteria(min_price_eur=500))
        ids = [l.id for l in result]
        assert "cheap" not in ids
        assert "ok" in ids

    def test_hard_filter_rooms(self):
        listings = [
            make_listing(id="studio", rooms=0.5),
            make_listing(id="tworoom", rooms=2.0),
        ]
        scraper = _DummyScraper(listings=listings)
        result = scraper.scrape(ListingCriteria(min_rooms=1.0))
        ids = [l.id for l in result]
        assert "studio" not in ids
        assert "tworoom" in ids

    def test_hard_filter_location(self):
        listings = [
            make_listing(id="lj", location="Ljubljana"),
            make_listing(id="mb", location="Maribor"),
        ]
        scraper = _DummyScraper(listings=listings)
        result = scraper.scrape(ListingCriteria(locations=["Ljubljana"]))
        ids = [l.id for l in result]
        assert "lj" in ids
        assert "mb" not in ids

    def test_hard_filter_furnished(self):
        listings = [
            make_listing(id="furn", furnished=True),
            make_listing(id="unfurn", furnished=False),
        ]
        scraper = _DummyScraper(listings=listings)
        result = scraper.scrape(ListingCriteria(furnished=True))
        ids = [l.id for l in result]
        assert "furn" in ids
        assert "unfurn" not in ids

    def test_none_values_not_filtered_out(self):
        """Listings with None for a filtered field should pass through."""
        listings = [
            make_listing(id="unknown_price", price_eur=None),
        ]
        scraper = _DummyScraper(listings=listings)
        result = scraper.scrape(ListingCriteria(max_price_eur=500))
        assert len(result) == 1

    def test_parse_price(self):
        assert BaseScraper._parse_price("1.200,00 €") == 1200.0
        assert BaseScraper._parse_price("850€") == 850.0
        assert BaseScraper._parse_price("no price here") is None

    def test_parse_size(self):
        assert BaseScraper._parse_size("55 m²") == 55.0
        assert BaseScraper._parse_size("55m2") == 55.0
        assert BaseScraper._parse_size("no size") is None
