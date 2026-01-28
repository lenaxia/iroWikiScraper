"""Comprehensive unit tests for FullScraper orchestrator.

Tests initialization, scraping workflow, progress tracking, error handling,
and result calculation.
"""

from datetime import datetime
from unittest.mock import Mock, patch

from scraper.orchestration.full_scraper import FullScraper, ScrapeResult
from scraper.storage.models import Page, Revision
from tests.mocks.mock_components import (
    MockPageDiscovery,
    MockPageRepository,
    MockRevisionRepository,
    MockRevisionScraper,
)


class TestScrapeResult:
    """Test ScrapeResult dataclass properties."""

    def test_duration_with_valid_times(self):
        """Test duration calculation with valid start and end times."""
        result = ScrapeResult(
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 5, 30),
        )
        assert result.duration == 330.0  # 5 minutes 30 seconds

    def test_duration_without_times(self):
        """Test duration returns 0.0 when times are not set."""
        result = ScrapeResult()
        assert result.duration == 0.0

    def test_duration_with_only_start_time(self):
        """Test duration returns 0.0 when only start time is set."""
        result = ScrapeResult(start_time=datetime(2024, 1, 1, 10, 0, 0))
        assert result.duration == 0.0

    def test_success_no_errors(self):
        """Test success property returns True when no errors."""
        result = ScrapeResult(pages_count=10, revisions_count=50)
        assert result.success is True

    def test_success_with_errors(self):
        """Test success property returns False when errors present."""
        result = ScrapeResult(errors=["Error 1", "Error 2"])
        assert result.success is False

    def test_default_values(self):
        """Test ScrapeResult initializes with correct defaults."""
        result = ScrapeResult()
        assert result.pages_count == 0
        assert result.revisions_count == 0
        assert result.namespaces_scraped == []
        assert result.start_time is None
        assert result.end_time is None
        assert result.errors == []
        assert result.failed_pages == []


class TestFullScraperInitialization:
    """Test FullScraper initialization."""

    def test_init_with_all_components(self):
        """Test FullScraper initializes with all required components."""
        config = Mock()
        api_client = Mock()
        database = Mock()

        scraper = FullScraper(config, api_client, database)

        assert scraper.config is config
        assert scraper.api is api_client
        assert scraper.db is database
        assert scraper.page_discovery is not None
        assert scraper.revision_scraper is not None
        assert scraper.page_repo is not None
        assert scraper.revision_repo is not None

    def test_components_initialized_with_correct_dependencies(self):
        """Test that internal components receive correct dependencies."""
        config = Mock()
        api_client = Mock()
        database = Mock()

        with (
            patch("scraper.orchestration.full_scraper.PageDiscovery") as mock_pd,
            patch("scraper.orchestration.full_scraper.RevisionScraper") as mock_rs,
            patch("scraper.orchestration.full_scraper.PageRepository") as mock_pr,
            patch("scraper.orchestration.full_scraper.RevisionRepository") as mock_rr,
        ):
            _ = FullScraper(config, api_client, database)

            mock_pd.assert_called_once_with(api_client)
            mock_rs.assert_called_once_with(api_client)
            mock_pr.assert_called_once_with(database)
            mock_rr.assert_called_once_with(database)


class TestFullScraperScrapeMethod:
    """Test FullScraper.scrape() method with various scenarios."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.config = Mock()
        self.api_client = Mock()
        self.database = Mock()

        # Create scraper with mocked components
        self.scraper = FullScraper(self.config, self.api_client, self.database)

        # Replace components with mocks
        self.mock_page_discovery = MockPageDiscovery()
        self.mock_revision_scraper = MockRevisionScraper()
        self.mock_page_repo = MockPageRepository()
        self.mock_revision_repo = MockRevisionRepository()

        self.scraper.page_discovery = self.mock_page_discovery
        self.scraper.revision_scraper = self.mock_revision_scraper
        self.scraper.page_repo = self.mock_page_repo
        self.scraper.revision_repo = self.mock_revision_repo

    def test_scrape_success_single_namespace(self):
        """Test successful scrape of a single namespace."""
        # Set up test data
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        revisions_page1 = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content 1",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]
        revisions_page2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content 2",
                size=200,
                sha1="b" * 40,
                minor=False,
                tags=[],
            ),
            Revision(
                revision_id=202,
                page_id=2,
                parent_id=201,
                timestamp=datetime(2024, 1, 3),
                user="User2",
                user_id=2,
                comment="Update",
                content="Content 2 updated",
                size=220,
                sha1="c" * 40,
                minor=False,
                tags=[],
            ),
        ]

        self.mock_page_discovery.set_pages_for_namespace(0, pages)
        self.mock_revision_scraper.set_revisions_for_page(1, revisions_page1)
        self.mock_revision_scraper.set_revisions_for_page(2, revisions_page2)

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0])

        # Verify result
        assert result.pages_count == 2
        assert result.revisions_count == 3
        assert result.namespaces_scraped == [0]
        assert result.success is True
        assert len(result.errors) == 0
        assert len(result.failed_pages) == 0
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration > 0

        # Verify component calls
        assert self.mock_page_discovery.discover_namespace_calls == [0]
        assert self.mock_page_repo.insert_pages_batch_calls == [2]
        assert set(self.mock_revision_scraper.fetch_revisions_calls) == {1, 2}
        assert self.mock_revision_repo.insert_revisions_batch_calls == [1, 2]

    def test_scrape_success_multiple_namespaces(self):
        """Test successful scrape across multiple namespaces."""
        # Set up test data for multiple namespaces
        pages_ns0 = [Page(page_id=1, namespace=0, title="Main Page", is_redirect=False)]
        pages_ns4 = [
            Page(page_id=2, namespace=4, title="Project Page", is_redirect=False)
        ]

        revisions1 = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]
        revisions2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content",
                size=100,
                sha1="b" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_page_discovery.set_pages_for_namespace(0, pages_ns0)
        self.mock_page_discovery.set_pages_for_namespace(4, pages_ns4)
        self.mock_revision_scraper.set_revisions_for_page(1, revisions1)
        self.mock_revision_scraper.set_revisions_for_page(2, revisions2)

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0, 4])

        # Verify result
        assert result.pages_count == 2
        assert result.revisions_count == 2
        assert result.namespaces_scraped == [0, 4]
        assert result.success is True

        # Verify both namespaces were processed
        assert set(self.mock_page_discovery.discover_namespace_calls) == {0, 4}

    def test_scrape_default_namespaces(self):
        """Test scrape uses default namespaces when none specified."""
        # Set up empty pages for all default namespaces
        for ns in MockPageDiscovery.DEFAULT_NAMESPACES:
            self.mock_page_discovery.set_pages_for_namespace(ns, [])

        # Execute scrape without specifying namespaces
        result = self.scraper.scrape()

        # Verify default namespaces were used
        assert result.namespaces_scraped == MockPageDiscovery.DEFAULT_NAMESPACES
        assert set(self.mock_page_discovery.discover_namespace_calls) == set(
            MockPageDiscovery.DEFAULT_NAMESPACES
        )

    def test_scrape_with_progress_callback(self):
        """Test progress callback is invoked correctly."""
        # Set up test data
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]
        revisions = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_page_discovery.set_pages_for_namespace(0, pages)
        self.mock_revision_scraper.set_revisions_for_page(1, revisions)

        # Track callback invocations
        callback_calls = []

        def progress_callback(stage: str, current: int, total: int):
            callback_calls.append((stage, current, total))

        # Execute scrape with callback
        _ = self.scraper.scrape(namespaces=[0], progress_callback=progress_callback)

        # Verify callback was called
        assert len(callback_calls) > 0

        # Check for discovery phase callback
        discover_calls = [c for c in callback_calls if c[0] == "discover"]
        assert len(discover_calls) == 1
        assert discover_calls[0] == ("discover", 1, 1)

        # Check for scrape phase callback
        scrape_calls = [c for c in callback_calls if c[0] == "scrape"]
        assert len(scrape_calls) == 1
        assert scrape_calls[0] == ("scrape", 1, 1)

    def test_scrape_namespace_discovery_failure(self):
        """Test scrape continues when namespace discovery fails."""
        # Set up one namespace to fail and one to succeed
        pages_ns4 = [
            Page(page_id=2, namespace=4, title="Project Page", is_redirect=False)
        ]
        revisions2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content",
                size=100,
                sha1="b" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_page_discovery.set_namespace_failure(0, Exception("API Error"))
        self.mock_page_discovery.set_pages_for_namespace(4, pages_ns4)
        self.mock_revision_scraper.set_revisions_for_page(2, revisions2)

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0, 4])

        # Verify scrape continued despite failure
        assert result.pages_count == 1  # Only namespace 4 pages
        assert result.revisions_count == 1
        # Namespace failures are now recorded as errors (US-0706)
        assert len(result.errors) == 1
        assert "namespace 0" in result.errors[0].lower()

    def test_scrape_page_revision_failure(self):
        """Test scrape handles individual page revision failures."""
        # Set up one page to fail and one to succeed
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        revisions2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content",
                size=100,
                sha1="b" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_page_discovery.set_pages_for_namespace(0, pages)
        self.mock_revision_scraper.set_page_failure(1, Exception("API timeout"))
        self.mock_revision_scraper.set_revisions_for_page(2, revisions2)

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0])

        # Verify error was recorded
        assert result.pages_count == 2
        assert result.revisions_count == 1  # Only page 2 succeeded
        assert result.success is False
        assert len(result.errors) == 1
        assert "Failed to scrape page 1" in result.errors[0]
        assert result.failed_pages == [1]

    def test_scrape_empty_namespace(self):
        """Test scrape handles namespaces with no pages."""
        self.mock_page_discovery.set_pages_for_namespace(0, [])

        result = self.scraper.scrape(namespaces=[0])

        assert result.pages_count == 0
        assert result.revisions_count == 0
        assert result.success is True

    def test_scrape_page_with_no_revisions(self):
        """Test scrape handles pages with no revisions."""
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]

        self.mock_page_discovery.set_pages_for_namespace(0, pages)
        self.mock_revision_scraper.set_revisions_for_page(1, [])  # No revisions

        result = self.scraper.scrape(namespaces=[0])

        assert result.pages_count == 1
        assert result.revisions_count == 0
        assert result.success is True

    def test_scrape_database_insert_error(self):
        """Test scrape handles database insertion errors."""
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]
        revisions = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_page_discovery.set_pages_for_namespace(0, pages)
        self.mock_revision_scraper.set_revisions_for_page(1, revisions)

        # Make revision insert fail
        self.mock_revision_repo.set_batch_insert_failure(Exception("Database error"))

        result = self.scraper.scrape(namespaces=[0])

        # The implementation doesn't catch database errors at the revision insert level
        # So this would propagate as a general scrape failure
        assert result.success is False
        assert len(result.errors) > 0

    def test_scrape_complete_failure(self):
        """Test scrape handles complete failure gracefully."""
        # Make page discovery raise an exception that propagates
        with patch.object(
            self.scraper, "_discover_pages", side_effect=Exception("Critical failure")
        ):
            result = self.scraper.scrape(namespaces=[0])

        assert result.success is False
        assert len(result.errors) == 1
        assert "Full scrape failed" in result.errors[0]
        assert result.start_time is not None
        assert result.end_time is not None


class TestFullScraperDiscoverPages:
    """Test FullScraper._discover_pages() internal method."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.config = Mock()
        self.api_client = Mock()
        self.database = Mock()

        self.scraper = FullScraper(self.config, self.api_client, self.database)

        self.mock_page_discovery = MockPageDiscovery()
        self.mock_page_repo = MockPageRepository()

        self.scraper.page_discovery = self.mock_page_discovery
        self.scraper.page_repo = self.mock_page_repo

    def test_discover_pages_single_namespace(self):
        """Test discovering pages from a single namespace."""
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        self.mock_page_discovery.set_pages_for_namespace(0, pages)

        result = self.scraper._discover_pages([0])

        assert len(result) == 2
        assert result == pages
        assert self.mock_page_repo.insert_pages_batch_calls == [2]

    def test_discover_pages_multiple_namespaces(self):
        """Test discovering pages from multiple namespaces."""
        pages_ns0 = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]
        pages_ns4 = [Page(page_id=2, namespace=4, title="Page 2", is_redirect=False)]

        self.mock_page_discovery.set_pages_for_namespace(0, pages_ns0)
        self.mock_page_discovery.set_pages_for_namespace(4, pages_ns4)

        result = self.scraper._discover_pages([0, 4])

        assert len(result) == 2
        assert result[0] in pages_ns0
        assert result[1] in pages_ns4

    def test_discover_pages_with_progress_callback(self):
        """Test progress callback is invoked during discovery."""
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]
        self.mock_page_discovery.set_pages_for_namespace(0, pages)

        callback_calls = []

        def progress_callback(stage: str, current: int, total: int):
            callback_calls.append((stage, current, total))

        self.scraper._discover_pages([0], progress_callback=progress_callback)

        assert callback_calls == [("discover", 1, 1)]

    def test_discover_pages_continues_on_namespace_failure(self):
        """Test discovery continues when one namespace fails."""
        pages_ns4 = [Page(page_id=2, namespace=4, title="Page 2", is_redirect=False)]

        self.mock_page_discovery.set_namespace_failure(0, Exception("API Error"))
        self.mock_page_discovery.set_pages_for_namespace(4, pages_ns4)

        result = self.scraper._discover_pages([0, 4])

        assert len(result) == 1  # Only namespace 4 succeeded
        assert result[0] == pages_ns4[0]


class TestFullScraperScrapeRevisions:
    """Test FullScraper._scrape_revisions() internal method."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.config = Mock()
        self.api_client = Mock()
        self.database = Mock()

        self.scraper = FullScraper(self.config, self.api_client, self.database)

        self.mock_revision_scraper = MockRevisionScraper()
        self.mock_revision_repo = MockRevisionRepository()

        self.scraper.revision_scraper = self.mock_revision_scraper
        self.scraper.revision_repo = self.mock_revision_repo

    def test_scrape_revisions_single_page(self):
        """Test scraping revisions for a single page."""
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]
        revisions = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_revision_scraper.set_revisions_for_page(1, revisions)

        total = self.scraper._scrape_revisions(pages)

        assert total == 1
        assert self.mock_revision_scraper.fetch_revisions_calls == [1]
        assert self.mock_revision_repo.insert_revisions_batch_calls == [1]

    def test_scrape_revisions_multiple_pages(self):
        """Test scraping revisions for multiple pages."""
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        revisions1 = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]
        revisions2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content",
                size=100,
                sha1="b" * 40,
                minor=False,
                tags=[],
            ),
            Revision(
                revision_id=202,
                page_id=2,
                parent_id=201,
                timestamp=datetime(2024, 1, 3),
                user="User2",
                user_id=2,
                comment="Update",
                content="Content updated",
                size=120,
                sha1="c" * 40,
                minor=False,
                tags=[],
            ),
        ]

        self.mock_revision_scraper.set_revisions_for_page(1, revisions1)
        self.mock_revision_scraper.set_revisions_for_page(2, revisions2)

        total = self.scraper._scrape_revisions(pages)

        assert total == 3
        assert set(self.mock_revision_scraper.fetch_revisions_calls) == {1, 2}

    def test_scrape_revisions_with_progress_callback(self):
        """Test progress callback is invoked during revision scraping."""
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        revisions = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1),
                user="User1",
                user_id=1,
                comment="Initial",
                content="Content",
                size=100,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_revision_scraper.set_revisions_for_page(1, revisions)
        self.mock_revision_scraper.set_revisions_for_page(2, revisions)

        callback_calls = []

        def progress_callback(stage: str, current: int, total: int):
            callback_calls.append((stage, current, total))

        self.scraper._scrape_revisions(pages, progress_callback=progress_callback)

        assert len(callback_calls) == 2
        assert callback_calls[0] == ("scrape", 1, 2)
        assert callback_calls[1] == ("scrape", 2, 2)

    def test_scrape_revisions_handles_page_failure(self):
        """Test revision scraping continues when individual pages fail."""
        pages = [
            Page(page_id=1, namespace=0, title="Page 1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page 2", is_redirect=False),
        ]
        revisions2 = [
            Revision(
                revision_id=201,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 2),
                user="User2",
                user_id=2,
                comment="Initial",
                content="Content",
                size=100,
                sha1="b" * 40,
                minor=False,
                tags=[],
            )
        ]

        self.mock_revision_scraper.set_page_failure(1, Exception("API timeout"))
        self.mock_revision_scraper.set_revisions_for_page(2, revisions2)

        result_obj = ScrapeResult()
        total = self.scraper._scrape_revisions(pages, result=result_obj)

        assert total == 1  # Only page 2 succeeded
        assert len(result_obj.errors) == 1
        assert result_obj.failed_pages == [1]

    def test_scrape_revisions_no_revisions_warning(self):
        """Test warning logged when page has no revisions."""
        pages = [Page(page_id=1, namespace=0, title="Page 1", is_redirect=False)]

        self.mock_revision_scraper.set_revisions_for_page(1, [])

        total = self.scraper._scrape_revisions(pages)

        assert total == 0
        # Should not insert empty batch
        assert len(self.mock_revision_repo.insert_revisions_batch_calls) == 0
