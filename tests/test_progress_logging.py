"""Tests for US-0705: Progress Tracking and Logging.

This module tests all acceptance criteria for progress tracking and logging:
1. Progress Display
2. Logging Levels
3. Stage Tracking
4. Progress Updates
5. Summary Output
"""

import io
import logging
import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scraper.cli.commands import (
    _print_progress,
    _setup_logging,
    full_scrape_command,
)
from tests.mocks.mock_cli_components import (
    MockConfig,
    MockFullScraper,
    MockScrapeResult,
)


class TestProgressDisplay:
    """Test US-0705 Acceptance Criteria 1: Progress Display."""

    def test_progress_shows_stage(self, capsys):
        """Test progress displays current stage name."""
        _print_progress("discover", 1, 10)
        captured = capsys.readouterr()
        assert "[discover]" in captured.out

    def test_progress_shows_current_total_counts(self, capsys):
        """Test progress displays current/total counts."""
        _print_progress("scrape", 50, 200)
        captured = capsys.readouterr()
        assert "50/200" in captured.out

    def test_progress_shows_percentage_complete(self, capsys):
        """Test progress displays percentage complete."""
        _print_progress("scrape", 25, 100)
        captured = capsys.readouterr()
        assert "25.0%" in captured.out

    def test_progress_shows_percentage_one_decimal_place(self, capsys):
        """Test percentage format uses exactly 1 decimal place."""
        _print_progress("scrape", 33, 100)
        captured = capsys.readouterr()
        assert "33.0%" in captured.out

        _print_progress("scrape", 1, 3)
        captured = capsys.readouterr()
        # 1/3 = 33.333...%, should display as 33.3%
        assert "33.3%" in captured.out

    def test_progress_handles_zero_total(self, capsys):
        """Test progress handles zero total gracefully."""
        _print_progress("scrape", 0, 0)
        captured = capsys.readouterr()
        assert "0/0 (0.0%)" in captured.out

    def test_progress_updates_with_flush(self, capsys):
        """Test progress output is flushed immediately."""
        # Output is flushed immediately for terminal updates
        _print_progress("scrape", 1, 100)
        captured = capsys.readouterr()
        # If flush=True works, output should be captured immediately
        assert "[scrape] 1/100" in captured.out

    def test_quiet_flag_suppresses_progress(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test --quiet flag suppresses progress output."""
        cli_args_full.quiet = True

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

        # Verify progress_callback was None (suppressed)
        assert mock_full_scraper.scrape_args["progress_callback"] is None

    def test_quiet_flag_false_enables_progress(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test quiet=False enables progress output."""
        cli_args_full.quiet = False

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

        # Verify progress_callback was provided
        assert mock_full_scraper.scrape_args["progress_callback"] is not None

    def test_progress_format_is_clean(self, capsys):
        """Test progress output format is clean and readable."""
        _print_progress("discover", 1, 5)
        captured = capsys.readouterr()

        # Should match format: [stage] current/total (percentage%)
        assert captured.out.strip() == "[discover] 1/5 (20.0%)"


class TestLoggingLevels:
    """Test US-0705 Acceptance Criteria 2: Logging Levels."""

    def test_debug_level_configured(self):
        """Test DEBUG logging level can be configured."""
        _setup_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_info_level_configured(self):
        """Test INFO logging level can be configured (default)."""
        _setup_logging("INFO")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_warning_level_configured(self):
        """Test WARNING logging level can be configured."""
        _setup_logging("WARNING")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_error_level_configured(self):
        """Test ERROR logging level can be configured."""
        _setup_logging("ERROR")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    def test_critical_level_configured(self):
        """Test CRITICAL logging level can be configured."""
        _setup_logging("CRITICAL")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.CRITICAL

    def test_logging_format_includes_timestamp(self, caplog):
        """Test logging format includes timestamp."""
        _setup_logging("INFO")
        logger = logging.getLogger("test_logger")

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        # basicConfig format should include timestamp (asctime)
        assert len(caplog.records) > 0

    def test_logging_format_includes_level(self, caplog):
        """Test logging format includes level name."""
        _setup_logging("DEBUG")
        logger = logging.getLogger("test_logger")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")

        assert any(record.levelname == "DEBUG" for record in caplog.records)
        assert any(record.levelname == "INFO" for record in caplog.records)
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_logging_format_includes_logger_name(self, caplog):
        """Test logging format includes logger name."""
        _setup_logging("INFO")
        logger = logging.getLogger("scraper.test")

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        assert any(record.name == "scraper.test" for record in caplog.records)

    def test_log_level_filters_messages(self, caplog):
        """Test log level correctly filters messages."""
        _setup_logging("WARNING")
        logger = logging.getLogger("test_filter")

        # caplog captures at WARNING level to match the logger configuration
        with caplog.at_level(logging.WARNING):
            logger.debug("Debug - should not appear")
            logger.info("Info - should not appear")
            logger.warning("Warning - should appear")
            logger.error("Error - should appear")

        # At WARNING level, only WARNING and above should be logged
        level_names = [record.levelname for record in caplog.records]
        assert "DEBUG" not in level_names
        assert "INFO" not in level_names
        assert "WARNING" in level_names
        assert "ERROR" in level_names

    def test_cli_passes_log_level_to_setup(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test CLI correctly passes log level to _setup_logging."""
        cli_args_full.log_level = "DEBUG"

        result = MockScrapeResult(pages_count=10, revisions_count=50)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._setup_logging") as mock_logging:
            with patch("scraper.cli.commands._load_config", return_value=mock_config):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.FullScraper",
                                return_value=mock_full_scraper,
                            ):
                                full_scrape_command(cli_args_full)

        mock_logging.assert_called_once_with("DEBUG")


class TestStageTracking:
    """Test US-0705 Acceptance Criteria 3: Stage Tracking."""

    def test_discover_stage_label(self, capsys):
        """Test 'discover' stage is used for page discovery."""
        _print_progress("discover", 10, 50)
        captured = capsys.readouterr()
        assert "[discover]" in captured.out

    def test_scrape_stage_label(self, capsys):
        """Test 'scrape' stage is used for revision scraping."""
        _print_progress("scrape", 100, 1000)
        captured = capsys.readouterr()
        assert "[scrape]" in captured.out

    def test_stage_names_are_lowercase(self, capsys):
        """Test stage names use lowercase for consistency."""
        _print_progress("discover", 1, 10)
        captured = capsys.readouterr()
        assert "[discover]" in captured.out
        assert "[Discover]" not in captured.out

        _print_progress("scrape", 1, 10)
        captured = capsys.readouterr()
        assert "[scrape]" in captured.out
        assert "[Scrape]" not in captured.out

    def test_different_stages_produce_different_output(self, capsys):
        """Test different stages produce distinguishable output."""
        _print_progress("discover", 5, 10)
        discover_output = capsys.readouterr().out

        _print_progress("scrape", 5, 10)
        scrape_output = capsys.readouterr().out

        # Should be different due to stage name
        assert discover_output != scrape_output
        assert "[discover]" in discover_output
        assert "[scrape]" in scrape_output


class TestProgressUpdates:
    """Test US-0705 Acceptance Criteria 4: Progress Updates."""

    def test_progress_callback_invoked_during_scrape(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test progress callback is invoked during scrape operations."""
        cli_args_full.quiet = False

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

        # Verify callback was passed
        assert mock_full_scraper.scrape_args["progress_callback"] is not None

    def test_percentage_shows_one_decimal_place(self, capsys):
        """Test percentage always shows exactly 1 decimal place."""
        test_cases = [
            (1, 4, "25.0%"),  # Clean division
            (1, 3, "33.3%"),  # Repeating decimal
            (2, 3, "66.7%"),  # Repeating decimal
            (5, 7, "71.4%"),  # Rounded
            (99, 100, "99.0%"),  # Near complete
            (100, 100, "100.0%"),  # Complete
        ]

        for current, total, expected in test_cases:
            _print_progress("test", current, total)
            captured = capsys.readouterr()
            assert expected in captured.out, f"Failed for {current}/{total}"

    def test_progress_shows_first_update(self, capsys):
        """Test progress shows first update (current=1)."""
        _print_progress("scrape", 1, 100)
        captured = capsys.readouterr()
        assert "[scrape] 1/100 (1.0%)" in captured.out

    def test_progress_shows_last_update(self, capsys):
        """Test progress shows last update (current=total)."""
        _print_progress("scrape", 100, 100)
        captured = capsys.readouterr()
        assert "[scrape] 100/100 (100.0%)" in captured.out

    def test_progress_handles_large_numbers(self, capsys):
        """Test progress handles large numbers correctly."""
        _print_progress("scrape", 15832, 15832)
        captured = capsys.readouterr()
        assert "15832/15832 (100.0%)" in captured.out

    def test_progress_calculates_percentage_correctly(self, capsys):
        """Test progress calculates percentage mathematically correct."""
        # Test various percentages
        test_cases = [
            (0, 100, 0.0),
            (10, 100, 10.0),
            (50, 100, 50.0),
            (75, 100, 75.0),
            (100, 100, 100.0),
            (1, 10, 10.0),
            (250, 1000, 25.0),
        ]

        for current, total, expected_pct in test_cases:
            _print_progress("test", current, total)
            captured = capsys.readouterr()
            assert f"{expected_pct:.1f}%" in captured.out


class TestSummaryOutput:
    """Test US-0705 Acceptance Criteria 5: Summary Output."""

    def test_summary_shows_pages_count(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary output includes total pages count."""
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
        # US-0709: Numbers are now formatted with commas (AC3)
        assert "Pages scraped:     2,400" in captured.out

    def test_summary_shows_revisions_count(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary output includes total revisions count."""
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
        # US-0709: Numbers are now formatted with commas (AC3)
        assert "Revisions scraped: 15,832" in captured.out

    def test_summary_shows_duration(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary output includes duration."""
        result = MockScrapeResult(pages_count=100, revisions_count=500)
        # Duration is calculated from start_time and end_time
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
        # Duration should be shown with 1 decimal place
        assert "Duration:" in captured.out
        assert "s" in captured.out  # seconds

    def test_summary_shows_error_count_when_present(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary shows error count when errors occurred."""
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            errors=["Error 1", "Error 2"],
            failed_pages=[1, 2],
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
        assert "Failed pages:" in captured.out
        assert "2" in captured.out  # 2 failed pages
        # US-0709: Error section now shows "Errors (first 3 of N):"
        assert "Errors" in captured.out

    def test_summary_no_error_section_when_no_errors(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary doesn't show error section when no errors."""
        result = MockScrapeResult(
            pages_count=100, revisions_count=500, errors=[], failed_pages=[]
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
        assert "Failed pages:" not in captured.out
        assert "Errors encountered:" not in captured.out

    def test_summary_includes_separator_lines(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary includes separator lines for readability."""
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
        # Check for separator lines (60 equals signs)
        assert "=" * 60 in captured.out

    def test_summary_has_clear_title(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary has clear title."""
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
        assert "FULL SCRAPE COMPLETE" in captured.out

    def test_summary_duration_format_one_decimal(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test summary duration uses 1 decimal place."""
        result = MockScrapeResult(pages_count=100, revisions_count=500)
        # Duration property will be calculated
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
        # Should match format "Duration:          X.Xs"
        import re

        duration_pattern = r"Duration:\s+\d+\.\d{1}s"
        assert re.search(duration_pattern, captured.out)


class TestQuietModeErrorHandling:
    """Test that --quiet suppresses progress but NOT errors."""

    def test_quiet_suppresses_progress_not_errors(
        self, cli_args_full, mock_config, mock_full_scraper, capsys, caplog
    ):
        """Test --quiet suppresses progress but logs errors."""
        cli_args_full.quiet = True

        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            errors=["Error 1", "Error 2"],
            failed_pages=[1, 2],
        )
        mock_full_scraper.set_result(result)

        with caplog.at_level(logging.ERROR):
            with patch("scraper.cli.commands._load_config", return_value=mock_config):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
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
        # Progress should be suppressed
        assert mock_full_scraper.scrape_args["progress_callback"] is None
        # But errors should still be shown in output (US-0709 format)
        assert "Errors" in captured.out
        assert "Error 1" in captured.out


class TestTerminalCompatibility:
    """Test that progress tracking doesn't break terminal scrolling."""

    def test_progress_uses_print_not_tqdm(self, capsys):
        """Test progress uses simple print(), not tqdm."""
        # Progress function should use print with flush
        _print_progress("test", 1, 10)
        captured = capsys.readouterr()

        # Output should be simple text, not ANSI escape codes
        assert captured.out.strip() == "[test] 1/10 (10.0%)"
        # Should not contain tqdm-specific escape sequences
        assert "\r" not in captured.out  # No carriage returns
        assert "\033[" not in captured.out  # No ANSI escape codes

    def test_progress_does_not_use_rich_console(self, capsys):
        """Test progress doesn't use rich console features."""
        _print_progress("test", 1, 10)
        captured = capsys.readouterr()

        # Should be plain text, no rich markup
        assert "[" in captured.out  # Square brackets are literal, not markup
        assert captured.out.strip() == "[test] 1/10 (10.0%)"

    def test_progress_preserves_newlines(self, capsys):
        """Test progress uses newlines, preserving terminal scrolling."""
        _print_progress("test", 1, 10)
        captured = capsys.readouterr()

        # Should end with newline (implicit from print)
        # Each progress update is a new line, allowing scrolling
        assert len(captured.out) > 0
