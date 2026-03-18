"""Tests for the CLI entry point (main.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from main import main


class TestCLI:
    def test_default_run(self):
        """CLI should run without errors when scrapers return nothing."""
        with patch("main.HousingSkill") as MockSkill:
            instance = MockSkill.return_value
            instance.run.return_value = {
                "listings": [],
                "text_report": "No results.",
                "json_report": {"listings": [], "total_results": 0},
                "text_report_path": None,
                "json_report_path": None,
            }
            rc = main(["--max-price", "1000", "--location", "Ljubljana"])
        assert rc == 0

    def test_json_format(self, capsys):
        with patch("main.HousingSkill") as MockSkill:
            instance = MockSkill.return_value
            instance.run.return_value = {
                "listings": [],
                "text_report": "No results.",
                "json_report": {"listings": [], "total_results": 0, "generated_at": "2024-01-01T00:00:00"},
                "text_report_path": None,
                "json_report_path": None,
            }
            rc = main(["--format", "json"])
        captured = capsys.readouterr()
        assert '"total_results"' in captured.out
        assert rc == 0

    def test_criteria_passed_correctly(self):
        with patch("main.HousingSkill") as MockSkill:
            instance = MockSkill.return_value
            instance.run.return_value = {
                "listings": [],
                "text_report": "",
                "json_report": {},
                "text_report_path": None,
                "json_report_path": None,
            }
            main([
                "--max-price", "900",
                "--min-size", "40",
                "--min-rooms", "2",
                "--furnished", "yes",
                "--location", "Ljubljana",
                "--keyword", "parking",
                "--max-results", "5",
            ])
            call_args = instance.run.call_args
            criteria = call_args[0][0]
            assert criteria.max_price_eur == 900
            assert criteria.min_size_m2 == 40
            assert criteria.min_rooms == 2
            assert criteria.furnished is True
            assert "Ljubljana" in criteria.locations
            assert "parking" in criteria.keywords
            assert criteria.max_results == 5

    def test_furnished_no(self):
        with patch("main.HousingSkill") as MockSkill:
            instance = MockSkill.return_value
            instance.run.return_value = {
                "listings": [],
                "text_report": "",
                "json_report": {},
                "text_report_path": None,
                "json_report_path": None,
            }
            main(["--furnished", "no"])
            criteria = instance.run.call_args[0][0]
            assert criteria.furnished is False
