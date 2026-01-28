"""Tests for US-0706: Error Handling and Recovery.

Tests comprehensive error handling including:
- Error classification (transient vs permanent)
- Retry logic with exponential backoff
- Namespace-level error recovery
- Page-level error recovery
- Partial success handling
- User interruption handling
"""

import logging
import sqlite3
import time
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from scraper.api.exceptions import (
    APIResponseError,
    NetworkError,
    PageNotFoundError,
    RateLimitError,
    ServerError,
)
from scraper.cli.commands import full_scrape_command
from scraper.orchestration.full_scraper import FullScraper, ScrapeResult
from scraper.storage.models import Page, Revision
from tests.mocks.mock_cli_components import MockConfig, MockDatabase


class TestErrorClassification:
    """Test error classification into transient vs permanent."""

    def test_transient_errors_are_retryable(self):
        """Test that transient errors should be retried."""
        from scraper.orchestration.retry import is_transient_error

        # Network errors are transient
        assert is_transient_error(NetworkError("Connection timeout"))
        assert is_transient_error(requests.exceptions.Timeout())
        assert is_transient_error(requests.exceptions.ConnectionError())

        # Rate limits are transient
        assert is_transient_error(RateLimitError("Too many requests"))

        # Server errors are transient
        assert is_transient_error(ServerError("Internal server error"))

        # Database locks are transient
        assert is_transient_error(sqlite3.OperationalError("database is locked"))

    def test_permanent_errors_are_not_retryable(self):
        """Test that permanent errors should not be retried."""
        from scraper.orchestration.retry import is_transient_error

        # 404 errors are permanent
        assert not is_transient_error(PageNotFoundError("Page not found"))

        # Validation errors are permanent
        assert not is_transient_error(ValueError("Invalid data"))
        assert not is_transient_error(APIResponseError("Invalid response structure"))

        # Type errors are permanent
        assert not is_transient_error(TypeError("Wrong type"))


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_retry_succeeds_on_second_attempt(self, monkeypatch):
        """Test successful retry after transient error."""
        from scraper.orchestration.retry import retry_with_backoff

        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("First attempt fails")
            return "success"

        # Mock time.sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = retry_with_backoff(operation, max_retries=3)

        assert result == "success"
        assert call_count == 2

    def test_retry_exhausts_all_attempts(self, monkeypatch):
        """Test that retry gives up after max attempts."""
        from scraper.orchestration.retry import retry_with_backoff

        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Always fails")

        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(NetworkError):
            retry_with_backoff(operation, max_retries=3)

        assert call_count == 3

    def test_retry_uses_exponential_backoff(self, monkeypatch):
        """Test that retry delays increase exponentially."""
        from scraper.orchestration.retry import retry_with_backoff

        delays = []

        def mock_sleep(seconds):
            delays.append(seconds)

        def operation():
            raise NetworkError("Always fails")

        monkeypatch.setattr(time, "sleep", mock_sleep)

        with pytest.raises(NetworkError):
            retry_with_backoff(operation, max_retries=3, base_delay=1.0)

        # Should have delays: 1.0, 2.0, 4.0 (but only 2 sleeps for 3 attempts)
        assert len(delays) == 2
        assert delays[0] == 1.0
        assert delays[1] == 2.0

    def test_retry_does_not_retry_permanent_errors(self, monkeypatch):
        """Test that permanent errors are not retried."""
        from scraper.orchestration.retry import retry_with_backoff

        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise PageNotFoundError("Page does not exist")

        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(PageNotFoundError):
            retry_with_backoff(operation, max_retries=3)

        # Should only call once, no retries
        assert call_count == 1


class TestNamespaceLevelErrors:
    """Test namespace-level error handling."""

    def test_namespace_error_continues_with_others(self, api_client, db):
        """Test that namespace discovery error continues with other namespaces."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock page discovery to fail on namespace 0
        original_discover = scraper.page_discovery.discover_namespace

        def mock_discover(namespace):
            if namespace == 0:
                raise NetworkError("Failed to discover namespace 0")
            return original_discover(namespace)

        scraper.page_discovery.discover_namespace = mock_discover

        # Scrape namespaces 0 and 4
        result = scraper.scrape(namespaces=[0, 4])

        # Should have error for namespace 0
        assert len(result.errors) > 0
        assert "namespace 0" in str(result.errors).lower()

        # Should still complete (namespace 4 should succeed if mocked properly)
        # Note: This test might need API mocking for namespace 4

    def test_namespace_error_logged_with_context(self, api_client, db, caplog):
        """Test that namespace errors are logged with namespace details."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock page discovery to fail
        def mock_discover(namespace):
            raise NetworkError("Connection failed")

        scraper.page_discovery.discover_namespace = mock_discover

        with caplog.at_level(logging.ERROR):
            result = scraper.scrape(namespaces=[0])

        # Check that error was logged with namespace context
        assert any("namespace 0" in record.message.lower() for record in caplog.records)


class TestPageLevelErrors:
    """Test page-level error handling."""

    def test_page_error_continues_with_others(self, api_client, db):
        """Test that page scraping error continues with other pages."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Insert test pages
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Page 3", is_redirect=False),
        ]
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch(pages)

        # Mock revision scraper to fail on page 2
        original_fetch = scraper.revision_scraper.fetch_revisions

        def mock_fetch(page_id):
            if page_id == 2:
                raise NetworkError("Failed to fetch page 2")
            # Return empty list for simplicity
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        # Scrape all pages
        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Should have error for page 2
        assert 2 in result.failed_pages
        assert len(result.errors) > 0

    def test_page_error_recorded_with_details(self, api_client, db):
        """Test that page errors are recorded with page ID and title."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Insert test page
        page = Page(page_id=42, namespace=0, title="Test_Page", is_redirect=False)
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch([page])

        # Mock revision scraper to fail
        def mock_fetch(page_id):
            raise APIResponseError("Invalid response")

        scraper.revision_scraper.fetch_revisions = mock_fetch

        # Scrape page
        result = ScrapeResult()
        scraper._scrape_revisions([page], result=result)

        # Check error contains page details
        assert 42 in result.failed_pages
        assert any("42" in error for error in result.errors)
        assert any("Test_Page" in error for error in result.errors)


class TestPartialSuccess:
    """Test partial success handling."""

    def test_high_success_rate_returns_exit_code_zero(
        self, cli_args_full, mock_config, monkeypatch
    ):
        """Test that >90% success returns exit code 0."""
        from scraper.cli.commands import full_scrape_command
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # Create result with 5% failure (acceptable)
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=["Error 1", "Error 2", "Error 3", "Error 4", "Error 5"],
            failed_pages=[1, 2, 3, 4, 5],  # 5% failure
        )

        mock_scraper = MockFullScraper(mock_config, None, None)
        mock_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch("scraper.cli.commands.MediaWikiAPIClient"):
                    with patch("scraper.cli.commands.RateLimiter"):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_scraper,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        # Should return 0 (partial success is acceptable)
        assert exit_code == 0

    def test_low_success_rate_returns_exit_code_one(
        self, cli_args_full, mock_config, monkeypatch
    ):
        """Test that <90% success returns exit code 1."""
        from scraper.cli.commands import full_scrape_command
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # Create result with 15% failure (unacceptable)
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=["Error"] * 15,
            failed_pages=list(range(1, 16)),  # 15% failure
        )

        mock_scraper = MockFullScraper(mock_config, None, None)
        mock_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch("scraper.cli.commands.MediaWikiAPIClient"):
                    with patch("scraper.cli.commands.RateLimiter"):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_scraper,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        # Should return 1 (too many failures)
        assert exit_code == 1

    def test_partial_failure_logs_warning(self, api_client, db, caplog):
        """Test that partial failures log warning."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock to cause some failures
        def mock_fetch(page_id):
            if page_id % 3 == 0:  # Fail every 3rd page
                raise NetworkError("Simulated failure")
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 11)
        ]

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Should have some failures but continue
        assert len(result.failed_pages) > 0
        assert len(result.failed_pages) < len(pages)


class TestUserInterruption:
    """Test user interruption (Ctrl+C) handling."""

    def test_keyboard_interrupt_returns_exit_code_130(
        self, cli_args_full, mock_config, monkeypatch
    ):
        """Test that Ctrl+C returns exit code 130."""
        from scraper.cli.commands import full_scrape_command
        from tests.mocks.mock_cli_components import MockFullScraper

        mock_scraper = MockFullScraper(mock_config, None, None)
        mock_scraper.set_exception(KeyboardInterrupt())

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch("scraper.cli.commands.MediaWikiAPIClient"):
                    with patch("scraper.cli.commands.RateLimiter"):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_scraper,
                        ):
                            exit_code = full_scrape_command(cli_args_full)

        assert exit_code == 130

    def test_keyboard_interrupt_logs_progress(
        self, cli_args_full, mock_config, caplog, monkeypatch
    ):
        """Test that Ctrl+C logs partial progress."""
        from scraper.cli.commands import full_scrape_command
        from tests.mocks.mock_cli_components import MockFullScraper

        mock_scraper = MockFullScraper(mock_config, None, None)
        mock_scraper.set_exception(KeyboardInterrupt())

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch("scraper.cli.commands.MediaWikiAPIClient"):
                    with patch("scraper.cli.commands.RateLimiter"):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_scraper,
                        ):
                            with caplog.at_level(logging.INFO):
                                full_scrape_command(cli_args_full)

        # Check that interruption was logged
        assert any("interrupted" in record.message.lower() for record in caplog.records)


class TestErrorReporting:
    """Test error reporting in ScrapeResult."""

    def test_errors_collected_in_result(self, api_client, db):
        """Test that all errors are collected in ScrapeResult."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 6)
        ]
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch(pages)

        # Mock to fail on specific pages
        def mock_fetch(page_id):
            if page_id in [2, 4]:
                raise NetworkError(f"Failed page {page_id}")
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Should have 2 errors
        assert len(result.errors) == 2
        assert len(result.failed_pages) == 2
        assert 2 in result.failed_pages
        assert 4 in result.failed_pages

    def test_error_messages_include_context(self, api_client, db):
        """Test that error messages include page ID and title."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        page = Page(page_id=123, namespace=0, title="Example_Page", is_redirect=False)
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch([page])

        def mock_fetch(page_id):
            raise NetworkError("Connection timeout")

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions([page], result=result)

        # Error should include both page_id and title
        assert len(result.errors) == 1
        error_msg = result.errors[0]
        assert "123" in error_msg
        assert "Example_Page" in error_msg

    def test_cli_limits_displayed_errors(self, cli_args_full, mock_config, capsys):
        """Test that CLI limits displayed errors to first 5."""
        from scraper.cli.commands import full_scrape_command
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # Create result with many errors
        errors = [f"Error {i}" for i in range(1, 11)]
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=errors,
            failed_pages=list(range(1, 11)),
        )

        mock_scraper = MockFullScraper(mock_config, None, None)
        mock_scraper.set_result(result)

        with patch("scraper.cli.commands._load_config", return_value=mock_config):
            with patch("scraper.cli.commands._create_database"):
                with patch("scraper.cli.commands.MediaWikiAPIClient"):
                    with patch("scraper.cli.commands.RateLimiter"):
                        with patch(
                            "scraper.cli.commands.FullScraper",
                            return_value=mock_scraper,
                        ):
                            full_scrape_command(cli_args_full)

        captured = capsys.readouterr()

        # US-0709: Errors are limited to first 3, not 5
        assert "Error 1" in captured.out
        assert "Error 2" in captured.out
        assert "Error 3" in captured.out
        # Should show truncation indicator (7 more: 10 total - 3 shown)
        assert "7 more errors" in captured.out or "and 7 more" in captured.out


class TestRetryWithTransientErrors:
    """Test retry logic integration with scraper."""

    def test_transient_error_retried_successfully(self, api_client, db, monkeypatch):
        """Test that transient errors are retried and can succeed."""
        from scraper.config import Config
        from scraper.orchestration.full_scraper import FullScraper
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        page = Page(page_id=1, namespace=0, title="Test_Page", is_redirect=False)
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch([page])

        call_count = 0

        def mock_fetch(page_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("Transient failure")
            # Return a revision on retry
            from datetime import datetime

            return [
                Revision(
                    revision_id=1,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 1, 0, 0, 0),
                    user="TestUser",
                    user_id=1,
                    comment="Test",
                    content="Test content",
                    size=12,
                    sha1="a" * 40,
                    minor=False,
                    tags=None,
                )
            ]

        scraper.revision_scraper.fetch_revisions = mock_fetch

        # Mock time.sleep
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = ScrapeResult()
        scraper._scrape_revisions([page], result=result)

        # Should succeed after retry
        assert call_count == 2
        assert len(result.failed_pages) == 0
        assert len(result.errors) == 0
