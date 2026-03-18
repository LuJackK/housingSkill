"""Tests for housing_skill.skill (HousingSkill) and housing_skill.scheduler."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from housing_skill.models.listing import ListingCriteria
from housing_skill.skill import HousingSkill
from housing_skill.scheduler import ReportScheduler
from tests.conftest import make_listing


@pytest.fixture()
def mock_scrapers():
    listings = [
        make_listing(id="s1", price_eur=650, size_m2=50, location="Ljubljana"),
        make_listing(id="s2", price_eur=800, size_m2=70, location="Ljubljana"),
        make_listing(id="s3", price_eur=500, size_m2=35, location="Maribor"),
    ]
    scraper = MagicMock()
    scraper.source_name = "mock_source"
    scraper.scrape.return_value = listings
    return [scraper]


class TestHousingSkill:
    def test_search_returns_ranked_listings(self, mock_scrapers):
        skill = HousingSkill(scrapers=mock_scrapers)
        criteria = ListingCriteria(locations=["Ljubljana", "Maribor"], max_results=10)
        results = skill.search(criteria)
        assert len(results) > 0
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_search_deduplicates_by_url(self):
        listing = make_listing(id="dup", url="https://example.com/dup")
        scraper1 = MagicMock()
        scraper1.source_name = "src1"
        scraper1.scrape.return_value = [listing]
        scraper2 = MagicMock()
        scraper2.source_name = "src2"
        scraper2.scrape.return_value = [listing]  # same URL

        skill = HousingSkill(scrapers=[scraper1, scraper2])
        results = skill.search(ListingCriteria())
        assert len(results) == 1

    def test_run_returns_expected_keys(self, mock_scrapers):
        skill = HousingSkill(scrapers=mock_scrapers)
        result = skill.run(ListingCriteria())
        assert "listings" in result
        assert "text_report" in result
        assert "json_report" in result
        assert result["text_report_path"] is None
        assert result["json_report_path"] is None

    def test_run_saves_reports_when_output_dir_given(self, mock_scrapers, tmp_path):
        skill = HousingSkill(scrapers=mock_scrapers)
        result = skill.run(ListingCriteria(), output_dir=tmp_path)
        assert result["text_report_path"] is not None
        assert result["json_report_path"] is not None
        assert result["text_report_path"].exists()
        assert result["json_report_path"].exists()

    def test_run_text_report_is_string(self, mock_scrapers):
        skill = HousingSkill(scrapers=mock_scrapers)
        result = skill.run(ListingCriteria())
        assert isinstance(result["text_report"], str)
        assert len(result["text_report"]) > 0

    def test_schedule_returns_scheduler(self, mock_scrapers):
        skill = HousingSkill(scrapers=mock_scrapers)
        scheduler = skill.schedule(ListingCriteria(), interval_seconds=600)
        assert isinstance(scheduler, ReportScheduler)
        assert scheduler.interval_seconds == 600

    def test_empty_scrapers_returns_empty(self):
        skill = HousingSkill(scrapers=[])
        results = skill.search(ListingCriteria())
        assert results == []


class TestReportScheduler:
    def test_run_once_calls_callback(self):
        called = []
        scheduler = ReportScheduler(callback=lambda: called.append(1), interval_seconds=60)
        scheduler.run_once()
        assert len(called) == 1

    def test_start_stop(self):
        scheduler = ReportScheduler(callback=lambda: None, interval_seconds=100)
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    def test_callback_called_on_start(self):
        results = []

        def cb():
            results.append(1)

        scheduler = ReportScheduler(callback=cb, interval_seconds=1)
        scheduler.start()
        time.sleep(1.5)
        scheduler.stop()
        assert len(results) >= 1

    def test_double_start_does_not_create_extra_thread(self):
        scheduler = ReportScheduler(callback=lambda: None, interval_seconds=100)
        scheduler.start()
        thread_id = id(scheduler._thread)
        scheduler.start()  # second call should be a no-op
        assert id(scheduler._thread) == thread_id
        scheduler.stop()
