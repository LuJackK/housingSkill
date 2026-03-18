"""Tests for housing_skill.analyzer."""

from __future__ import annotations

import pytest

from housing_skill.analyzer import ListingAnalyzer
from housing_skill.models.listing import ListingCriteria
from tests.conftest import make_listing


class TestListingAnalyzer:
    def setup_method(self):
        self.analyzer = ListingAnalyzer()

    def test_empty_list_returns_empty(self):
        result = self.analyzer.analyze([], ListingCriteria())
        assert result == []

    def test_scores_are_set(self):
        listings = [
            make_listing(id="a", price_eur=500, size_m2=40),
            make_listing(id="b", price_eur=800, size_m2=70),
        ]
        result = self.analyzer.analyze(listings, ListingCriteria())
        for l in result:
            assert 0.0 <= l.score <= 1.0

    def test_cheaper_listing_scores_higher_with_price_weight(self):
        """When price_weight > size_weight the cheaper listing should win."""
        listings = [
            make_listing(id="cheap", price_eur=400, size_m2=40),
            make_listing(id="exp", price_eur=1000, size_m2=40),
        ]
        criteria = ListingCriteria(price_weight=1.0, size_weight=0.0)
        result = self.analyzer.analyze(listings, criteria)
        assert result[0].id == "cheap"

    def test_larger_listing_scores_higher_with_size_weight(self):
        """When size_weight > price_weight the larger listing should win."""
        listings = [
            make_listing(id="small", price_eur=400, size_m2=30),
            make_listing(id="large", price_eur=400, size_m2=90),
        ]
        criteria = ListingCriteria(price_weight=0.0, size_weight=1.0)
        result = self.analyzer.analyze(listings, criteria)
        assert result[0].id == "large"

    def test_preferred_location_boosts_score(self):
        listings = [
            make_listing(id="preferred", location="Ljubljana Center"),
            make_listing(id="other", location="Maribor"),
        ]
        criteria = ListingCriteria(
            preferred_locations=["Ljubljana Center"],
            price_weight=0.0,
            size_weight=0.0,
        )
        result = self.analyzer.analyze(listings, criteria)
        assert result[0].id == "preferred"

    def test_keyword_match_boosts_score(self):
        listings = [
            make_listing(id="match", title="Spacious flat with parking", description="garage included"),
            make_listing(id="no_match", title="Small studio", description="no extras"),
        ]
        criteria = ListingCriteria(
            keywords=["parking"],
            price_weight=0.0,
            size_weight=0.0,
        )
        result = self.analyzer.analyze(listings, criteria)
        assert result[0].id == "match"

    def test_max_results_respected(self):
        listings = [
            make_listing(id=str(i), price_eur=float(500 + i * 10))
            for i in range(30)
        ]
        criteria = ListingCriteria(max_results=5)
        result = self.analyzer.analyze(listings, criteria)
        assert len(result) <= 5

    def test_furnished_preference(self):
        listings = [
            make_listing(id="furn", furnished=True),
            make_listing(id="unfurn", furnished=False),
        ]
        criteria = ListingCriteria(
            furnished=True,
            price_weight=0.0,
            size_weight=0.0,
        )
        result = self.analyzer.analyze(listings, criteria)
        assert result[0].id == "furn"

    def test_listings_with_no_price_still_scored(self):
        listings = [
            make_listing(id="no_price", price_eur=None, size_m2=50),
        ]
        result = self.analyzer.analyze(listings, ListingCriteria())
        assert len(result) == 1
        assert result[0].score >= 0.0

    def test_sorted_descending(self):
        listings = [
            make_listing(id="a", price_eur=900, size_m2=30),
            make_listing(id="b", price_eur=400, size_m2=30),
            make_listing(id="c", price_eur=600, size_m2=30),
        ]
        criteria = ListingCriteria(price_weight=1.0, size_weight=0.0)
        result = self.analyzer.analyze(listings, criteria)
        scores = [l.score for l in result]
        assert scores == sorted(scores, reverse=True)
