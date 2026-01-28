"""Tests for US-0709: Statistics and Reporting.

Tests comprehensive statistics output for both full and incremental scrapes,
including formatting, error reporting, and JSON output functionality.
"""

import json
from argparse import Namespace
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scraper.cli.commands import full_scrape_command, incremental_scrape_command
from tests.mocks.mock_cli_components import (
    MockConfig,
    MockFullScraper,
    MockIncrementalPageScraper,
    MockIncrementalStats,
    MockScrapeResult,
)


class TestFullScrapeStatistics:
    """Test full scrape statistics output (AC1, AC3, AC4)."""

    def test_shows_average_revisions_per_page(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC1: Test average revisions per page is calculated and displayed."""
        result = MockScrapeResult(pages_count=100, revisions_count=650)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should show average as 6.5 revisions per page
        assert "Avg revisions:" in captured.out
        assert "6.5" in captured.out

    def test_shows_rate_pages_per_second(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC1: Test rate (pages/sec) is calculated and displayed."""
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            _duration=50.0,  # 50 seconds
        )
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should show rate as 2.0 pages/sec (100 pages / 50 seconds)
        assert "Rate:" in captured.out
        assert "2.0 pages/sec" in captured.out or "2.0pages/sec" in captured.out

    def test_shows_namespace_breakdown(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC1: Test namespace breakdown with page and revision counts."""
        result = MockScrapeResult(
            pages_count=150,
            revisions_count=750,
            namespaces_scraped=[0, 4, 6],
            namespace_stats={
                0: {"pages": 100, "revisions": 500},
                4: {"pages": 30, "revisions": 150},
                6: {"pages": 20, "revisions": 100},
            },
        )
        mock_full_scraper.set_result(result)

        # Mock _get_namespace_stats to return our test data
        def mock_get_namespace_stats(database):
            return {
                0: {"pages": 100, "revisions": 500},
                4: {"pages": 30, "revisions": 150},
                6: {"pages": 20, "revisions": 100},
            }

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            with patch(
                                "scraper.cli.commands._get_namespace_stats",
                                side_effect=mock_get_namespace_stats,
                            ):
                                full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert "Breakdown by namespace:" in captured.out
        assert "Main" in captured.out  # namespace 0 should show "Main"
        assert "100" in captured.out  # namespace 0 pages
        assert "500" in captured.out  # namespace 0 revisions

    def test_numbers_formatted_with_commas(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC3: Test large numbers are formatted with commas."""
        result = MockScrapeResult(pages_count=2400, revisions_count=15832)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert "2,400" in captured.out
        assert "15,832" in captured.out

    def test_error_samples_truncated_to_three(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC4: Test error messages are truncated to first 3 with indicator."""
        errors = [
            "Page 1: Error one",
            "Page 2: Error two",
            "Page 3: Error three",
            "Page 4: Error four",
            "Page 5: Error five",
        ]
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            errors=errors,
            failed_pages=[1, 2, 3, 4, 5],
        )
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should show first 3 errors
        assert "Error one" in captured.out
        assert "Error two" in captured.out
        assert "Error three" in captured.out
        # Should show truncation indicator
        assert "first 3 of 5" in captured.out or "and 2 more" in captured.out

    def test_failed_page_ids_truncated_to_five(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC4: Test failed page IDs are truncated to 5 with indicator."""
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            failed_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            errors=["Error"] * 10,
        )
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should show first 5 IDs
        assert "1, 2, 3, 4, 5" in captured.out
        # Should show truncation indicator
        assert "and 5 more" in captured.out or "..." in captured.out

    def test_output_has_visual_separators(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC3: Test output includes visual separators."""
        result = MockScrapeResult(pages_count=100, revisions_count=500)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should have separator lines
        assert "=" * 60 in captured.out

    def test_columns_are_aligned(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC3: Test columns are properly aligned."""
        result = MockScrapeResult(pages_count=100, revisions_count=500)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        lines = captured.out.split("\n")

        # Find statistics lines (those with colons)
        stat_lines = [
            line
            for line in lines
            if ":" in line and "=" not in line and "(" not in line
        ]

        # Check that colons are aligned (same position in multiple lines)
        if len(stat_lines) >= 2:
            colon_positions = [line.find(":") for line in stat_lines[:5]]
            # All colons should be at similar positions (within 10 characters)
            # This allows for some variation between regular stats and namespace breakdown
            assert max(colon_positions) - min(colon_positions) <= 10


class TestIncrementalScrapeStatistics:
    """Test incremental scrape statistics output (AC2, AC3)."""

    def test_shows_all_change_types(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """AC2: Test all change type statistics are displayed."""
        stats = MockIncrementalStats(
            pages_new=12,
            pages_modified=47,
            pages_deleted=3,
            pages_moved=2,
            revisions_added=89,
            files_downloaded=5,
        )
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                return_value=mock_incremental_scraper,
                            ):
                                incremental_scrape_command(cli_args_incremental)

        captured = capsys.readouterr()
        assert "Pages new:" in captured.out or "New pages:" in captured.out
        assert "12" in captured.out
        assert "Pages modified:" in captured.out or "Modified pages:" in captured.out
        assert "47" in captured.out
        assert "Pages deleted:" in captured.out or "Deleted pages:" in captured.out
        assert "3" in captured.out
        assert "Pages moved:" in captured.out or "Moved pages:" in captured.out
        assert "2" in captured.out

    def test_numbers_formatted_with_commas_incremental(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """AC3: Test incremental scrape formats large numbers with commas."""
        stats = MockIncrementalStats(
            pages_new=1200, pages_modified=3450, revisions_added=12789
        )
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                return_value=mock_incremental_scraper,
                            ):
                                incremental_scrape_command(cli_args_incremental)

        captured = capsys.readouterr()
        assert "1,200" in captured.out
        assert "3,450" in captured.out
        assert "12,789" in captured.out

    def test_shows_rate_for_incremental(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """AC2: Test incremental scrape shows rate calculation."""
        stats = MockIncrementalStats(
            pages_new=12,
            pages_modified=47,
            pages_deleted=3,
            pages_moved=2,
            duration=timedelta(seconds=18.7),
        )
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                return_value=mock_incremental_scraper,
                            ):
                                incremental_scrape_command(cli_args_incremental)

        captured = capsys.readouterr()
        # Should show rate (64 total affected / 18.7 seconds = 3.4 pages/sec)
        assert "Rate:" in captured.out
        assert "pages/sec" in captured.out


class TestJSONOutput:
    """Test JSON output format (AC5)."""

    def test_json_output_flag_full_scrape(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC5: Test --format json produces valid JSON for full scrape."""
        cli_args_full.format = "json"

        result = MockScrapeResult(
            pages_count=2400,
            revisions_count=15832,
            namespaces_scraped=[0, 4, 6, 10, 14],
            namespace_stats={
                0: {"pages": 1842, "revisions": 12431},
                4: {"pages": 234, "revisions": 1205},
                6: {"pages": 156, "revisions": 892},
                10: {"pages": 102, "revisions": 814},
                14: {"pages": 66, "revisions": 490},
            },
            failed_pages=[142, 589, 1023],
            errors=["Error 1", "Error 2", "Error 3"],
            _duration=245.3,
        )
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()

        # Should be valid JSON
        data = json.loads(captured.out)

        # Verify structure
        assert data["scrape_type"] == "full"
        assert data["success"] is True or data["success"] is False
        assert "timestamp" in data
        assert data["duration_seconds"] == 245.3

        # Verify statistics
        assert data["statistics"]["pages_count"] == 2400
        assert data["statistics"]["revisions_count"] == 15832

        # Verify errors
        assert data["errors"]["count"] == 3
        assert data["errors"]["failed_pages"] == [142, 589, 1023]
        assert len(data["errors"]["messages"]) == 3

    def test_json_output_incremental_scrape(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """AC5: Test --format json produces valid JSON for incremental scrape."""
        cli_args_incremental.format = "json"

        stats = MockIncrementalStats(
            pages_new=12,
            pages_modified=47,
            pages_deleted=3,
            pages_moved=2,
            revisions_added=89,
            files_downloaded=5,
            duration=timedelta(seconds=18.7),
        )
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                return_value=mock_incremental_scraper,
                            ):
                                incremental_scrape_command(cli_args_incremental)

        captured = capsys.readouterr()

        # Should be valid JSON
        data = json.loads(captured.out)

        # Verify structure
        assert data["scrape_type"] == "incremental"
        assert data["success"] is True
        assert "timestamp" in data

        # Verify statistics
        assert data["statistics"]["pages_new"] == 12
        assert data["statistics"]["pages_modified"] == 47
        assert data["statistics"]["pages_deleted"] == 3
        assert data["statistics"]["pages_moved"] == 2
        assert data["statistics"]["revisions_added"] == 89
        assert data["statistics"]["files_downloaded"] == 5

    def test_json_output_is_only_output(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """AC5: Test --format json produces ONLY JSON (no other text)."""
        cli_args_full.format = "json"

        result = MockScrapeResult(pages_count=100, revisions_count=500)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_full_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()

        # Should not contain text like "FULL SCRAPE COMPLETE"
        assert "FULL SCRAPE COMPLETE" not in captured.out
        assert "Starting full scrape" not in captured.out

        # Should be parseable as JSON
        data = json.loads(captured.out)
        assert isinstance(data, dict)
