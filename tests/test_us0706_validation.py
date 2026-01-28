"""Comprehensive validation tests for US-0706: Error Handling and Recovery.

This test suite validates ALL acceptance criteria comprehensively:
1. Error Categories - 4 types properly classified
2. Namespace-Level Errors - catch and continue
3. Page-Level Errors - catch and continue
4. Retry Logic - exponential backoff working, max retries respected
5. Error Reporting - errors collected with context
6. Partial Success - exit code logic correct, >10% failure = exit 1
7. User Interruption - Ctrl+C exits 130, DB safe

Tests edge cases including:
- All retries exhausted
- Mix of transient and permanent errors
- Namespace failure doesn't stop others
- Page failure doesn't stop others
- Boundary conditions (exactly 10%, 9%, 11% failure)
- Interrupt during different phases
- Database rollback on interrupt
"""

import logging
import sqlite3
import time
from unittest.mock import patch

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
from scraper.orchestration.retry import is_transient_error, retry_with_backoff
from scraper.storage.models import Page


class TestAcceptanceCriteria1ErrorCategories:
    """AC1: Error Categories - 4 types properly classified."""

    def test_network_errors_classified_as_transient(self):
        """Test all network error types are classified as transient."""
        # Timeouts are transient
        assert is_transient_error(requests.exceptions.Timeout())
        assert is_transient_error(NetworkError("Connection timeout"))

        # Connection failures are transient
        assert is_transient_error(requests.exceptions.ConnectionError())

    def test_api_errors_classified_correctly(self):
        """Test API errors are classified based on type."""
        # Rate limiting is transient (can retry after backoff)
        assert is_transient_error(RateLimitError("Too many requests"))

        # Server errors are transient (server might recover)
        assert is_transient_error(ServerError("Internal server error"))

        # Invalid responses are permanent (won't fix itself)
        assert not is_transient_error(APIResponseError("Invalid JSON"))

    def test_database_errors_classified_correctly(self):
        """Test database errors are classified based on type."""
        # Database locks are transient (will release eventually)
        assert is_transient_error(sqlite3.OperationalError("database is locked"))
        assert is_transient_error(sqlite3.OperationalError("Database Is LOCKED"))

        # Other database errors might not be transient
        # (depends on the specific error, but we're conservative)

    def test_validation_errors_classified_as_permanent(self):
        """Test data validation errors are permanent."""
        # Malformed content won't fix itself
        assert not is_transient_error(ValueError("Invalid data format"))
        assert not is_transient_error(TypeError("Wrong type"))

        # 404 Not Found is permanent
        assert not is_transient_error(PageNotFoundError("Page not found"))


class TestAcceptanceCriteria2NamespaceLevelErrors:
    """AC2: Namespace-Level Errors - catch and continue."""

    def test_namespace_exception_caught_and_logged(self, api_client, db, caplog):
        """Test that namespace exceptions are caught and logged."""
        from scraper.config import Config

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock discovery to fail on namespace 0
        def mock_discover(namespace):
            if namespace == 0:
                raise NetworkError("Namespace 0 failed")
            return []

        scraper.page_discovery.discover_namespace = mock_discover

        with caplog.at_level(logging.ERROR):
            _ = scraper.scrape(namespaces=[0, 4])

        # Error should be logged
        assert any("namespace 0" in msg.lower() for msg in caplog.messages)

    def test_namespace_failure_continues_with_remaining(self, api_client, db):
        """Test that namespace failure doesn't abort scrape."""
        from scraper.config import Config

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock discovery to fail on namespace 0 but succeed on 4
        call_count = 0

        def mock_discover(namespace):
            nonlocal call_count
            call_count += 1
            if namespace == 0:
                raise NetworkError("Namespace 0 failed")
            return []

        scraper.page_discovery.discover_namespace = mock_discover

        _ = scraper.scrape(namespaces=[0, 4])

        # Both namespaces should be attempted
        assert call_count == 2

    def test_namespace_failure_recorded_in_result(self, api_client, db):
        """Test that namespace failures are recorded in ScrapeResult."""
        from scraper.config import Config

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Mock discovery to fail
        def mock_discover(namespace):
            raise NetworkError(f"Failed namespace {namespace}")

        scraper.page_discovery.discover_namespace = mock_discover

        result = scraper.scrape(namespaces=[0])

        # Error should be in result
        assert len(result.errors) > 0
        assert "namespace 0" in str(result.errors).lower()


class TestAcceptanceCriteria3PageLevelErrors:
    """AC3: Page-Level Errors - catch and continue."""

    def test_page_exception_caught_and_logged(self, api_client, db, caplog):
        """Test that page exceptions are caught and logged."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Insert test pages
        pages = [
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page_2", is_redirect=False),
        ]
        PageRepository(db).insert_pages_batch(pages)

        # Mock to fail on page 1
        def mock_fetch(page_id):
            if page_id == 1:
                raise NetworkError("Page 1 failed")
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        with caplog.at_level(logging.ERROR):
            result = ScrapeResult()
            scraper._scrape_revisions(pages, result=result)

        # Error should be logged
        assert any(
            "page 1" in msg.lower() or "page_1" in msg.lower()
            for msg in caplog.messages
        )

    def test_page_failure_continues_with_remaining(self, api_client, db, monkeypatch):
        """Test that page failure doesn't abort scrape."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Insert test pages
        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 6)
        ]
        PageRepository(db).insert_pages_batch(pages)

        call_count = 0

        def mock_fetch(page_id):
            nonlocal call_count
            call_count += 1
            if page_id == 3:
                # Use permanent error to avoid retries for this test
                raise PageNotFoundError("Page 3 not found")
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # All 5 pages should be attempted (page 3 fails but doesn't stop others)
        assert call_count == 5

    def test_page_failure_recorded_with_id(self, api_client, db):
        """Test that failed page IDs are recorded."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        pages = [
            Page(page_id=42, namespace=0, title="Test", is_redirect=False),
        ]
        PageRepository(db).insert_pages_batch(pages)

        def mock_fetch(page_id):
            raise NetworkError("Failed")

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Page 42 should be in failed list
        assert 42 in result.failed_pages


class TestAcceptanceCriteria4RetryLogic:
    """AC4: Retry Logic - exponential backoff working, max retries respected."""

    def test_transient_errors_are_retried(self, monkeypatch):
        """Test that transient errors trigger retry logic."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Transient failure")
            return "success"

        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = retry_with_backoff(operation, max_retries=3)

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third

    def test_exponential_backoff_delays(self, monkeypatch):
        """Test that retry delays follow exponential backoff pattern."""
        delays = []

        def mock_sleep(seconds):
            delays.append(seconds)

        def operation():
            raise NetworkError("Always fails")

        monkeypatch.setattr(time, "sleep", mock_sleep)

        with pytest.raises(NetworkError):
            retry_with_backoff(operation, max_retries=4, base_delay=1.0)

        # Should have 3 delays (for 4 attempts)
        assert len(delays) == 3
        # Delays should be: 1.0, 2.0, 4.0 (exponential)
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    def test_max_retries_respected(self, monkeypatch):
        """Test that retry logic respects max_retries limit."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Always fails")

        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(NetworkError):
            retry_with_backoff(operation, max_retries=5)

        # Should attempt exactly 5 times
        assert call_count == 5

    def test_permanent_errors_not_retried(self, monkeypatch):
        """Test that permanent errors are not retried."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise PageNotFoundError("Permanent failure")

        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(PageNotFoundError):
            retry_with_backoff(operation, max_retries=3)

        # Should only call once (no retries)
        assert call_count == 1

    def test_all_retries_exhausted_raises_last_error(self, monkeypatch):
        """Test that exhausting retries raises the last error."""

        def operation():
            raise RateLimitError("Rate limit exceeded")

        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(RateLimitError) as exc_info:
            retry_with_backoff(operation, max_retries=3)

        assert "rate limit" in str(exc_info.value).lower()


class TestAcceptanceCriteria5ErrorReporting:
    """AC5: Error Reporting - errors collected with context."""

    def test_errors_collected_in_scrape_result(self, api_client, db):
        """Test that all errors are collected in ScrapeResult."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 6)
        ]
        PageRepository(db).insert_pages_batch(pages)

        def mock_fetch(page_id):
            if page_id in [2, 4]:
                raise NetworkError(f"Failed {page_id}")
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Should have exactly 2 errors
        assert len(result.errors) == 2
        assert len(result.failed_pages) == 2

    def test_error_messages_include_page_id(self, api_client, db):
        """Test that error messages include page ID."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        page = Page(page_id=123, namespace=0, title="Test", is_redirect=False)
        PageRepository(db).insert_pages_batch([page])

        def mock_fetch(page_id):
            raise NetworkError("Connection failed")

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions([page], result=result)

        # Error message should contain page ID
        assert any("123" in error for error in result.errors)

    def test_error_messages_include_page_title(self, api_client, db):
        """Test that error messages include page title."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        page = Page(page_id=1, namespace=0, title="Example_Page", is_redirect=False)
        PageRepository(db).insert_pages_batch([page])

        def mock_fetch(page_id):
            raise NetworkError("Failed")

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        scraper._scrape_revisions([page], result=result)

        # Error message should contain title
        assert any("Example_Page" in error for error in result.errors)

    def test_cli_limits_displayed_errors_to_5(self, cli_args_full, mock_config):
        """Test that CLI displays max 5 errors."""
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # Create result with 10 errors
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
                            import sys
                            from io import StringIO

                            old_stdout = sys.stdout
                            sys.stdout = StringIO()
                            try:
                                full_scrape_command(cli_args_full)
                                output = sys.stdout.getvalue()
                            finally:
                                sys.stdout = old_stdout

        # US-0709: Errors limited to first 3, not 5
        assert "Error 1" in output
        assert "Error 2" in output
        assert "Error 3" in output
        # Should indicate more errors exist (7 more: 10 total - 3 shown)
        assert "7 more" in output or "more errors" in output


class TestAcceptanceCriteria6PartialSuccess:
    """AC6: Partial Success - exit code logic correct."""

    def test_boundary_exactly_10_percent_failure_returns_0(
        self, cli_args_full, mock_config
    ):
        """Test that exactly 10% failure (boundary) returns exit 0."""
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # 10 out of 100 = exactly 10%
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=450,
            namespaces_scraped=[0],
            errors=["Error"] * 10,
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
                            exit_code = full_scrape_command(cli_args_full)

        # Exactly 10% should be acceptable
        assert exit_code == 0

    def test_boundary_9_percent_failure_returns_0(self, cli_args_full, mock_config):
        """Test that 9% failure returns exit 0."""
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # 9 out of 100 = 9%
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=455,
            namespaces_scraped=[0],
            errors=["Error"] * 9,
            failed_pages=list(range(1, 10)),
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

        assert exit_code == 0

    def test_boundary_11_percent_failure_returns_1(self, cli_args_full, mock_config):
        """Test that 11% failure returns exit 1."""
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        # 11 out of 100 = 11%
        result = MockScrapeResult(
            pages_count=100,
            revisions_count=445,
            namespaces_scraped=[0],
            errors=["Error"] * 11,
            failed_pages=list(range(1, 12)),
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

        # More than 10% should fail
        assert exit_code == 1

    def test_complete_success_returns_0(self, cli_args_full, mock_config):
        """Test that 100% success returns exit 0."""
        from tests.mocks.mock_cli_components import MockFullScraper, MockScrapeResult

        result = MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=[0],
            errors=[],
            failed_pages=[],
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

        assert exit_code == 0


class TestAcceptanceCriteria7UserInterruption:
    """AC7: User Interruption - Ctrl+C exits 130, DB safe."""

    def test_keyboard_interrupt_returns_exit_130(self, cli_args_full, mock_config):
        """Test that KeyboardInterrupt (Ctrl+C) returns exit code 130."""
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

        # Standard SIGINT exit code
        assert exit_code == 130

    def test_keyboard_interrupt_logs_message(self, cli_args_full, mock_config, caplog):
        """Test that KeyboardInterrupt logs an informative message."""
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

        # Should log that scrape was interrupted
        assert any("interrupt" in msg.lower() for msg in caplog.messages)

    def test_database_remains_consistent_after_interrupt(self, api_client, db):
        """Test that database transactions are not corrupted by interruption."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        # Insert some pages
        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 6)
        ]
        page_repo = PageRepository(db)
        page_repo.insert_pages_batch(pages)

        # Verify pages were inserted
        conn = db.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count_before = cursor.fetchone()[0]
        assert count_before == 5

        # Simulate interrupt during revision scraping
        def mock_fetch(page_id):
            if page_id == 3:
                raise KeyboardInterrupt()
            return []

        scraper.revision_scraper.fetch_revisions = mock_fetch

        result = ScrapeResult()
        try:
            scraper._scrape_revisions(pages, result=result)
        except KeyboardInterrupt:
            pass  # Expected

        # Database should still be consistent (pages still there)
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count_after = cursor.fetchone()[0]
        assert count_after == 5


class TestMixedErrorScenarios:
    """Test mixed scenarios with both transient and permanent errors."""

    def test_mix_of_transient_and_permanent_errors(self, api_client, db, monkeypatch):
        """Test handling of both transient and permanent errors in one scrape."""
        from scraper.config import Config
        from scraper.storage.page_repository import PageRepository

        config = Config()
        scraper = FullScraper(config, api_client, db)

        pages = [
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page_2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Page_3", is_redirect=False),
        ]
        PageRepository(db).insert_pages_batch(pages)

        call_counts = {1: 0, 2: 0, 3: 0}

        def mock_fetch(page_id):
            call_counts[page_id] += 1
            if page_id == 1:
                # Transient error - will be retried
                if call_counts[1] < 2:
                    raise NetworkError("Transient")
                return []
            elif page_id == 2:
                # Permanent error - won't be retried
                raise PageNotFoundError("Permanent")
            else:
                # Success
                return []

        scraper.revision_scraper.fetch_revisions = mock_fetch
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = ScrapeResult()
        scraper._scrape_revisions(pages, result=result)

        # Page 1 should be retried (called 2 times)
        assert call_counts[1] == 2
        # Page 2 should not be retried (called 1 time)
        assert call_counts[2] == 1
        # Page 3 should succeed (called 1 time)
        assert call_counts[3] == 1

        # Only page 2 should fail (permanent error)
        assert len(result.failed_pages) == 1
        assert 2 in result.failed_pages
