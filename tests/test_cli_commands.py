"""Tests for CLI command implementations.

Tests US-0703 acceptance criteria for full scrape command.
"""

import logging
import sys
from argparse import Namespace
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scraper.cli.commands import full_scrape_command, incremental_scrape_command
from scraper.incremental.page_scraper import FirstRunRequiresFullScrapeError
from tests.mocks.mock_cli_components import (
    MockConfig,
    MockDatabase,
    MockFullScraper,
    MockIncrementalPageScraper,
    MockIncrementalStats,
    MockPageDiscovery,
    MockScrapeResult,
)


class TestFullScrapeCommand:
    """Test full_scrape_command implementation."""

    def test_command_returns_zero_on_success(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test command returns 0 on successful scrape."""
        # Setup mock result
        result = MockScrapeResult(
            pages_count=100, revisions_count=500, namespaces_scraped=[0, 4]
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
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 0
        assert mock_full_scraper.scrape_called

    def test_command_returns_one_on_failure(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test command returns 1 on scrape failure."""
        # Setup mock result with errors
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=["Error 1", "Error 2"],
            failed_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # >10% failure
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
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 1

    def test_command_returns_130_on_keyboard_interrupt(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test command returns 130 on KeyboardInterrupt."""
        mock_full_scraper.set_exception(KeyboardInterrupt())

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
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 130

    def test_command_returns_one_on_exception(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test command returns 1 on general exception."""
        mock_full_scraper.set_exception(RuntimeError("Test error"))

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
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 1

    def test_force_flag_bypasses_existing_data_check(
        self, cli_args_full, mock_config, mock_full_scraper, temp_db_path
    ):
        """Test --force flag bypasses existing data check."""
        cli_args_full.force = True
        cli_args_full.database = Path(temp_db_path)

        # Create mock database with existing data
        mock_db = MockDatabase(temp_db_path)
        mock_db.pages_count = 100

        result = MockScrapeResult(pages_count=50, revisions_count=200)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Database", return_value=mock_db):
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
                                exit_code = full_scrape_command(cli_args_full)

        # Should succeed even with existing data
        assert exit_code == 0

    def test_existing_data_without_force_returns_error(
        self, cli_args_full, mock_config, temp_db_path
    ):
        """Test existing data without --force returns error."""
        cli_args_full.force = False
        cli_args_full.database = Path(temp_db_path)

        # Create mock database with existing data
        mock_db = MockDatabase(temp_db_path)
        mock_db.pages_count = 100

        mock_config.storage.database_file = Path(temp_db_path)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands.Database", return_value=mock_db):
                    exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 1

    def test_dry_run_mode_only_discovers(self, cli_args_full, mock_config, capsys):
        """Test --dry-run only discovers pages, doesn't scrape."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page2", is_redirect=False),
            Page(page_id=3, namespace=4, title="Page3", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        # PageDiscovery is imported inside the function
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "DRY RUN MODE" in captured.out
        assert "Would scrape 3 pages" in captured.out
        assert "0 (Main" in captured.out and "2 pages" in captured.out
        assert "4 (Project" in captured.out and "1 pages" in captured.out

    def test_dry_run_shows_header_and_footer(self, cli_args_full, mock_config, capsys):
        """Test dry-run shows DRY RUN MODE header and DRY RUN COMPLETE footer."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "DRY RUN MODE" in captured.out
        assert "DRY RUN COMPLETE" in captured.out

    def test_dry_run_shows_estimated_api_calls(
        self, cli_args_full, mock_config, capsys
    ):
        """Test dry-run shows estimated API calls."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page2", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Estimated API calls:" in captured.out
        # Should show at least the page count for revision calls
        assert "2" in captured.out

    def test_dry_run_shows_estimated_duration(self, cli_args_full, mock_config, capsys):
        """Test dry-run shows estimated duration."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(1, 11)
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Estimated duration:" in captured.out
        # With 10 pages and rate limit of 2.0, should be ~5s
        assert "s" in captured.out  # Should show seconds

    def test_dry_run_does_not_call_scraper(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test dry-run does not call FullScraper.scrape()."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            with patch(
                                "scraper.cli.commands.FullScraper",
                                return_value=mock_full_scraper,
                            ):
                                exit_code = full_scrape_command(cli_args_full)

        # FullScraper.scrape() should NOT be called in dry-run mode
        assert not mock_full_scraper.scrape_called
        assert exit_code == 0

    def test_dry_run_does_not_create_database(self, cli_args_full, mock_config, capsys):
        """Test dry-run does not create database file."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        database_created = False

        def mock_create_database(config):
            nonlocal database_created
            database_created = True
            return MagicMock()

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch(
                "scraper.cli.commands._create_database",
                side_effect=mock_create_database,
            ):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        # Database should NOT be created in dry-run mode
        assert not database_created
        assert exit_code == 0

    def test_dry_run_with_namespace_filter(self, cli_args_full, mock_config, capsys):
        """Test dry-run respects namespace filter."""
        cli_args_full.dry_run = True
        cli_args_full.namespace = [0, 4]

        from scraper.storage.models import Page

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
            Page(page_id=2, namespace=4, title="Page2", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        namespaces_passed = None

        def capture_discovery(api_client):
            def capture_discover_all_pages(namespaces=None):
                nonlocal namespaces_passed
                namespaces_passed = namespaces
                return mock_pages

            mock = MockPageDiscovery(api_client)
            mock.discover_all_pages = capture_discover_all_pages
            return mock

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            side_effect=capture_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        # Should pass namespace filter to discovery
        assert namespaces_passed == [0, 4]
        assert exit_code == 0

    def test_dry_run_with_multiple_namespaces_breakdown(
        self, cli_args_full, mock_config, capsys
    ):
        """Test dry-run shows correct breakdown for multiple namespaces."""
        cli_args_full.dry_run = True

        from scraper.storage.models import Page

        # Create pages in multiple namespaces
        mock_pages = [
            Page(page_id=1, namespace=0, title="Main1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Main2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Main3", is_redirect=False),
            Page(page_id=4, namespace=4, title="Project1", is_redirect=False),
            Page(page_id=5, namespace=4, title="Project2", is_redirect=False),
            Page(page_id=6, namespace=6, title="File1", is_redirect=False),
            Page(page_id=7, namespace=10, title="Template1", is_redirect=False),
            Page(page_id=8, namespace=14, title="Category1", is_redirect=False),
        ]

        mock_discovery = MockPageDiscovery(None)
        mock_discovery.set_pages(mock_pages)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                    ):
                        with patch(
                            "scraper.scrapers.page_scraper.PageDiscovery",
                            return_value=mock_discovery,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Would scrape 8 pages" in captured.out
        assert "0 (Main" in captured.out and "3 pages" in captured.out
        assert "4 (Project" in captured.out and "2 pages" in captured.out
        assert "6 (File" in captured.out and "1 pages" in captured.out
        assert "10 (Template" in captured.out and "1 pages" in captured.out
        assert "14 (Category" in captured.out and "1 pages" in captured.out

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
                            exit_code = full_scrape_command(cli_args_full)

        # Verify progress_callback was None
        assert mock_full_scraper.scrape_args["progress_callback"] is None
        assert exit_code == 0

    def test_progress_callback_invoked_when_not_quiet(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test progress callback is invoked when not quiet."""
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
                            exit_code = full_scrape_command(cli_args_full)

        # Verify progress_callback was provided
        assert mock_full_scraper.scrape_args["progress_callback"] is not None
        assert exit_code == 0

    def test_namespace_argument_passed_to_scraper(
        self, cli_args_full, mock_config, mock_full_scraper
    ):
        """Test --namespace argument is passed to scraper."""
        cli_args_full.namespace = [0, 4, 6]

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
                            exit_code = full_scrape_command(cli_args_full)

        assert mock_full_scraper.scrape_args["namespaces"] == [0, 4, 6]
        assert exit_code == 0

    def test_output_shows_statistics(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test output shows statistics summary."""
        result = MockScrapeResult(
            pages_count=2400,
            revisions_count=15832,
            namespaces_scraped=[0, 4, 6, 10, 14],
            failed_pages=[142, 589, 1023],
            errors=["Error 1", "Error 2"],
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
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        assert "FULL SCRAPE COMPLETE" in captured.out
        assert "2,400" in captured.out  # Now formatted with commas
        assert "15,832" in captured.out  # Now formatted with commas
        assert (
            "Failed pages:      3" in captured.out
            or "Failed pages:      3 (" in captured.out
        )
        assert "[142, 589, 1023]" in captured.out or "142, 589, 1023" in captured.out

    def test_config_file_loading(self, cli_args_full, mock_config, mock_full_scraper):
        """Test configuration file is loaded when specified."""
        cli_args_full.config = Path("config.yaml")

        result = MockScrapeResult(pages_count=10, revisions_count=50)
        mock_full_scraper.set_result(result)

        with patch("scraper.cli.commands.Config.from_yaml", return_value=mock_config):
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
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 0

    def test_rate_limit_override(self, cli_args_full, mock_full_scraper):
        """Test rate limit can be overridden via CLI."""
        cli_args_full.rate_limit = 3.0

        result = MockScrapeResult(pages_count=10, revisions_count=50)
        mock_full_scraper.set_result(result)

        # Track what rate limit is used to create RateLimiter
        captured_rate = None

        def capture_rate_limiter(requests_per_second):
            nonlocal captured_rate
            captured_rate = requests_per_second
            return MagicMock()

        with patch("scraper.cli.commands._create_database"):
            with patch(
                "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
            ):
                with patch(
                    "scraper.cli.commands.RateLimiter", side_effect=capture_rate_limiter
                ):
                    with patch(
                        "scraper.cli.commands.FullScraper",
                        return_value=mock_full_scraper,
                    ):
                        exit_code = full_scrape_command(cli_args_full)

        # Rate limiter should be created with overridden rate
        assert captured_rate == 3.0
        assert exit_code == 0

    def test_logging_setup(self, cli_args_full, mock_config, mock_full_scraper):
        """Test logging is configured based on log level."""
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
                                exit_code = full_scrape_command(cli_args_full)

        mock_logging.assert_called_once_with("DEBUG")
        assert exit_code == 0

    def test_output_shows_many_errors(
        self, cli_args_full, mock_config, mock_full_scraper, capsys
    ):
        """Test output shows truncated errors when more than 5."""
        # Create more than 5 errors
        errors = [f"Error {i}" for i in range(1, 11)]
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=errors,
            failed_pages=list(range(1, 11)),
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
                            exit_code = full_scrape_command(cli_args_full)

        captured = capsys.readouterr()
        # Should show first 3 errors (changed from 5)
        assert "Error 1" in captured.out
        assert "Error 2" in captured.out
        assert "Error 3" in captured.out
        # Should show "and X more errors"
        assert "and 7 more errors" in captured.out
        # Errors 4-10 should not be shown directly
        assert "Error 10" not in captured.out


class TestIncrementalScrapeCommand:
    """Test incremental_scrape_command implementation."""

    def test_command_returns_zero_on_success(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test incremental command returns 0 on success."""
        stats = MockIncrementalStats(pages_new=5, pages_modified=10, revisions_added=25)
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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        assert exit_code == 0

    def test_missing_database_returns_error(self, cli_args_incremental, mock_config):
        """Test missing database file returns error."""
        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=False):
                exit_code = incremental_scrape_command(cli_args_incremental)

        assert exit_code == 1

    def test_first_run_requires_full_scrape_error(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test FirstRunRequiresFullScrapeError is handled."""
        mock_incremental_scraper.set_exception(
            FirstRunRequiresFullScrapeError("No baseline scrape found")
        )

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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        assert exit_code == 1

    def test_keyboard_interrupt_returns_130(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test KeyboardInterrupt returns 130."""
        mock_incremental_scraper.set_exception(KeyboardInterrupt())

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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        assert exit_code == 130

    def test_generic_exception_returns_one(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test generic exception returns 1."""
        mock_incremental_scraper.set_exception(RuntimeError("Test error"))

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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        assert exit_code == 1

    def test_output_shows_all_statistics(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """Test output shows complete statistics summary."""
        from datetime import timedelta

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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        captured = capsys.readouterr()
        assert "INCREMENTAL SCRAPE COMPLETE" in captured.out
        assert "New pages:" in captured.out or "Pages new:" in captured.out
        assert "12" in captured.out
        assert "Modified pages:" in captured.out or "Pages modified:" in captured.out
        assert "47" in captured.out
        assert "Deleted pages:" in captured.out or "Pages deleted:" in captured.out
        assert "3" in captured.out
        assert "Moved pages:" in captured.out or "Pages moved:" in captured.out
        assert "2" in captured.out
        assert "Revisions added:   89" in captured.out or "89" in captured.out
        assert "Files downloaded:  5" in captured.out or "5" in captured.out
        assert "Total affected:    64" in captured.out or "64" in captured.out
        assert "Duration:          18.7s" in captured.out or "18.7" in captured.out
        assert exit_code == 0

    def test_config_file_loading(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test configuration file is loaded when specified."""
        cli_args_incremental.config = Path("config.yaml")

        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands.Config.from_yaml", return_value=mock_config):
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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        assert exit_code == 0

    def test_rate_limit_override(self, cli_args_incremental, mock_incremental_scraper):
        """Test rate limit can be overridden via CLI."""
        cli_args_incremental.rate_limit = 3.0

        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
        mock_incremental_scraper.set_stats(stats)

        # Track what rate limit is used to create RateLimiter
        captured_rate = None

        def capture_rate_limiter(requests_per_second):
            nonlocal captured_rate
            captured_rate = requests_per_second
            return MagicMock()

        with patch("scraper.cli.commands.Path.exists", return_value=True):
            with patch("scraper.cli.commands._create_database"):
                with patch(
                    "scraper.cli.commands.MediaWikiAPIClient", return_value=MagicMock()
                ):
                    with patch(
                        "scraper.cli.commands.RateLimiter",
                        side_effect=capture_rate_limiter,
                    ):
                        with patch(
                            "scraper.cli.commands.IncrementalPageScraper",
                            return_value=mock_incremental_scraper,
                        ):
                            exit_code = incremental_scrape_command(cli_args_incremental)

        assert captured_rate == 3.0
        assert exit_code == 0

    def test_download_directory_created(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, tmp_path
    ):
        """Test download directory is created if it doesn't exist."""
        # Set up config with temp path
        mock_config.storage.data_dir = tmp_path
        download_dir = tmp_path / "files"

        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        # Directory should exist
        assert download_dir.exists()
        assert exit_code == 0

    def test_api_client_created_with_config(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test MediaWikiAPIClient is created with correct configuration."""
        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
        mock_incremental_scraper.set_stats(stats)

        captured_args = None

        def capture_api_client(*args, **kwargs):
            nonlocal captured_args
            captured_args = kwargs
            return MagicMock()

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database"):
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        side_effect=capture_api_client,
                    ):
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                return_value=mock_incremental_scraper,
                            ):
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        # Verify API client was created with correct config
        assert captured_args is not None
        assert captured_args["base_url"] == "https://irowiki.org"
        assert captured_args["user_agent"] == "Test Scraper/1.0"
        assert captured_args["timeout"] == 30
        assert captured_args["max_retries"] == 3
        assert exit_code == 0

    def test_logging_setup(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test logging is configured based on log level."""
        cli_args_incremental.log_level = "DEBUG"

        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
        mock_incremental_scraper.set_stats(stats)

        with patch("scraper.cli.commands._setup_logging") as mock_logging:
            with patch("scraper.cli.commands._load_config", return_value=mock_config):
                with patch("scraper.cli.commands.Path.exists", return_value=True):
                    with patch("scraper.cli.commands._create_database"):
                        with patch(
                            "scraper.cli.commands.MediaWikiAPIClient",
                            return_value=MagicMock(),
                        ):
                            with patch(
                                "scraper.cli.commands.RateLimiter",
                                return_value=MagicMock(),
                            ):
                                with patch(
                                    "scraper.cli.commands.IncrementalPageScraper",
                                    return_value=mock_incremental_scraper,
                                ):
                                    exit_code = incremental_scrape_command(
                                        cli_args_incremental
                                    )

        mock_logging.assert_called_once_with("DEBUG")
        assert exit_code == 0

    def test_output_format_includes_separators(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """Test output includes separator lines for readability."""
        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        captured = capsys.readouterr()
        # Check for separator lines (60 equals signs)
        assert "=" * 60 in captured.out
        assert exit_code == 0

    def test_error_message_for_missing_database(
        self, cli_args_incremental, mock_config, capsys
    ):
        """Test clear error message when database is missing."""
        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=False):
                exit_code = incremental_scrape_command(cli_args_incremental)

        # Check that error was logged (captured by capsys won't show logs, but exit code should be 1)
        assert exit_code == 1

    def test_first_run_error_suggests_full_scrape(
        self, cli_args_incremental, mock_config, mock_incremental_scraper, capsys
    ):
        """Test FirstRunRequiresFullScrapeError message suggests running full scrape."""
        mock_incremental_scraper.set_exception(
            FirstRunRequiresFullScrapeError("No baseline scrape found")
        )

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
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        captured = capsys.readouterr()
        assert "Run 'scraper full' first to create baseline" in captured.out
        assert exit_code == 1

    def test_scraper_invoked_with_correct_components(
        self, cli_args_incremental, mock_config, mock_incremental_scraper
    ):
        """Test IncrementalPageScraper is created with correct components."""
        stats = MockIncrementalStats(pages_new=5, pages_modified=10)
        mock_incremental_scraper.set_stats(stats)

        captured_args = None

        def capture_scraper(api_client, database, download_dir):
            nonlocal captured_args
            captured_args = {
                "api_client": api_client,
                "database": database,
                "download_dir": download_dir,
            }
            return mock_incremental_scraper

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands.Path.exists", return_value=True):
                with patch("scraper.cli.commands._create_database") as mock_db:
                    with patch(
                        "scraper.cli.commands.MediaWikiAPIClient",
                        return_value=MagicMock(),
                    ) as mock_api:
                        with patch(
                            "scraper.cli.commands.RateLimiter", return_value=MagicMock()
                        ):
                            with patch(
                                "scraper.cli.commands.IncrementalPageScraper",
                                side_effect=capture_scraper,
                            ):
                                exit_code = incremental_scrape_command(
                                    cli_args_incremental
                                )

        # Verify scraper was created with correct components
        assert captured_args is not None
        assert captured_args["api_client"] is not None
        assert captured_args["database"] is not None
        assert captured_args["download_dir"] is not None
        assert exit_code == 0


class TestHelperFunctions:
    """Test helper functions in commands module."""

    def test_setup_logging_configures_level(self):
        """Test _setup_logging configures logging level."""
        from scraper.cli.commands import _setup_logging

        _setup_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        _setup_logging("WARNING")
        assert root_logger.level == logging.WARNING

    def test_load_config_from_file(self, tmp_path):
        """Test _load_config loads from file when specified."""
        from argparse import Namespace

        from scraper.cli.commands import _load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("wiki:\n  base_url: https://test.example.com\n")

        args = Namespace(config=config_file, database=Path("test.db"), log_level="INFO")

        # Will use default config since we're mocking
        config = _load_config(args)
        assert config is not None

    def test_load_config_uses_defaults(self):
        """Test _load_config uses defaults when no file specified."""
        from argparse import Namespace

        from scraper.cli.commands import _load_config

        args = Namespace(config=None, database=Path("test.db"), log_level="INFO")

        config = _load_config(args)
        assert config is not None

    def test_create_database_initializes_schema(self, temp_db_path):
        """Test _create_database initializes schema."""
        from scraper.cli.commands import _create_database
        from scraper.config import Config

        config = Config()
        config.storage.database_file = Path(temp_db_path)

        db = _create_database(config)
        assert db is not None

        # Check schema was initialized
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pages'"
        )
        assert cursor.fetchone() is not None

    def test_print_progress_outputs_correctly(self, capsys):
        """Test _print_progress formats output correctly."""
        from scraper.cli.commands import _print_progress

        _print_progress("discover", 1, 5)
        captured = capsys.readouterr()
        assert "[discover] 1/5 (20.0%)" in captured.out

        _print_progress("scrape", 250, 1000)
        captured = capsys.readouterr()
        assert "[scrape] 250/1000 (25.0%)" in captured.out
