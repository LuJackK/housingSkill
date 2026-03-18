"""Tests for housing_skill.reporter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from housing_skill.models.listing import ListingCriteria
from housing_skill.reporter import ReportGenerator
from tests.conftest import make_listing


@pytest.fixture()
def reporter():
    return ReportGenerator()


@pytest.fixture()
def listings():
    return [
        make_listing(
            id="1",
            title="Apartment A",
            url="https://example.com/1",
            price_eur=700.0,
            size_m2=55.0,
            location="Ljubljana",
            rooms=2.0,
            furnished=True,
        ),
        make_listing(
            id="2",
            title="Apartment B",
            url="https://example.com/2",
            price_eur=500.0,
            size_m2=35.0,
            location="Maribor",
            rooms=1.0,
            furnished=False,
        ),
    ]


@pytest.fixture()
def criteria():
    return ListingCriteria(max_price_eur=800, locations=["Ljubljana", "Maribor"])


class TestReportGenerator:
    def test_text_report_contains_titles(self, reporter, listings, criteria):
        report = reporter.generate_text_report(listings, criteria)
        assert "Apartment A" in report
        assert "Apartment B" in report

    def test_text_report_contains_criteria(self, reporter, listings, criteria):
        report = reporter.generate_text_report(listings, criteria)
        assert "800" in report
        assert "Ljubljana" in report

    def test_text_report_has_header(self, reporter, listings, criteria):
        report = reporter.generate_text_report(listings, criteria)
        assert "SLOVENIAN RENTAL MARKET REPORT" in report

    def test_text_report_shows_price(self, reporter, listings, criteria):
        report = reporter.generate_text_report(listings, criteria)
        assert "700" in report

    def test_json_report_structure(self, reporter, listings, criteria):
        data = reporter.generate_json_report(listings, criteria)
        assert "generated_at" in data
        assert "criteria" in data
        assert "listings" in data
        assert data["total_results"] == 2
        assert len(data["listings"]) == 2

    def test_json_report_listing_fields(self, reporter, listings, criteria):
        data = reporter.generate_json_report(listings, criteria)
        first = data["listings"][0]
        assert first["title"] == "Apartment A"
        assert first["price_eur"] == 700.0

    def test_save_text_report(self, reporter, listings, criteria, tmp_path):
        out = tmp_path / "report.txt"
        saved = reporter.save_text_report(listings, criteria, out)
        assert saved.exists()
        content = saved.read_text(encoding="utf-8")
        assert "Apartment A" in content

    def test_save_json_report(self, reporter, listings, criteria, tmp_path):
        out = tmp_path / "report.json"
        saved = reporter.save_json_report(listings, criteria, out)
        assert saved.exists()
        data = json.loads(saved.read_text(encoding="utf-8"))
        assert data["total_results"] == 2

    def test_save_creates_parent_dirs(self, reporter, listings, criteria, tmp_path):
        out = tmp_path / "nested" / "dir" / "report.txt"
        reporter.save_text_report(listings, criteria, out)
        assert out.exists()

    def test_empty_listings(self, reporter, criteria):
        report = reporter.generate_text_report([], criteria)
        assert "0 listings found" in report

    def test_text_report_with_generated_at(self, reporter, listings, criteria):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        report = reporter.generate_text_report(listings, criteria, generated_at=dt)
        assert "2024-03-15" in report
