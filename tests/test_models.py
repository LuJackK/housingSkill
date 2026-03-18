"""Tests for housing_skill.models.listing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from housing_skill.models.listing import Listing, ListingCriteria


class TestListing:
    def test_price_per_m2_calculated(self):
        listing = Listing(
            id="1",
            title="Test",
            url="https://example.com/1",
            source="test",
            price_eur=600.0,
            size_m2=50.0,
            location="Ljubljana",
            address=None,
            rooms=2.0,
            floor=1,
            furnished=True,
            description="",
        )
        assert listing.price_per_m2 == 12.0

    def test_price_per_m2_none_when_no_price(self):
        listing = Listing(
            id="2",
            title="Test",
            url="https://example.com/2",
            source="test",
            price_eur=None,
            size_m2=50.0,
            location="Ljubljana",
            address=None,
            rooms=None,
            floor=None,
            furnished=None,
            description="",
        )
        assert listing.price_per_m2 is None

    def test_to_dict_roundtrip(self):
        listing = Listing(
            id="3",
            title="Round-trip test",
            url="https://example.com/3",
            source="test",
            price_eur=850.0,
            size_m2=70.0,
            location="Maribor",
            address="Ulica 5",
            rooms=3.0,
            floor=2,
            furnished=False,
            description="Great flat",
            images=["https://img.example.com/a.jpg"],
            scraped_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        d = listing.to_dict()
        restored = Listing.from_dict(d)

        assert restored.id == listing.id
        assert restored.title == listing.title
        assert restored.price_eur == listing.price_eur
        assert restored.size_m2 == listing.size_m2
        assert restored.price_per_m2 == listing.price_per_m2
        assert restored.furnished == listing.furnished
        assert restored.scraped_at == listing.scraped_at

    def test_from_dict_missing_optional_fields(self):
        d = {
            "id": "x",
            "title": "Minimal",
            "url": "https://example.com/x",
            "source": "test",
        }
        listing = Listing.from_dict(d)
        assert listing.price_eur is None
        assert listing.size_m2 is None
        assert listing.rooms is None
        assert listing.score == 0.0


class TestListingCriteria:
    def test_defaults(self):
        c = ListingCriteria()
        assert c.max_price_eur is None
        assert c.locations == []
        assert c.price_weight == 0.5
        assert c.max_results == 20

    def test_to_dict(self):
        c = ListingCriteria(max_price_eur=800, locations=["Ljubljana"])
        d = c.to_dict()
        assert d["max_price_eur"] == 800
        assert d["locations"] == ["Ljubljana"]
