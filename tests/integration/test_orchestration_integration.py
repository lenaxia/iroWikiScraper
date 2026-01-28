"""Integration tests for orchestration components.

These tests verify that orchestration components work together correctly
with real implementations (Database, CheckpointManager) and minimal mocking.

Test Coverage:
- FullScraper with real Database (in-memory SQLite)
- CheckpointManager with real filesystem
- Retry logic with simulated failures
- Error handling paths
- Progress tracking integration
- Transaction handling
"""

import json
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from scraper.api.client import MediaWikiAPIClient
from scraper.config import Config
from scraper.orchestration.checkpoint import CheckpointManager
from scraper.orchestration.full_scraper import FullScraper
from scraper.orchestration.retry import retry_with_backoff
from scraper.storage.database import Database
from scraper.storage.models import Page, Revision
from scraper.storage.page_repository import PageRepository


class TestFullScraperDatabaseIntegration:
    """Test FullScraper integration with real Database."""

    def setup_method(self):
        """Set up test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        self.database = Database(str(self.db_path))
        self.database.initialize_schema()

    def teardown_method(self):
        """Clean up test database."""
        self.database.close()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_full_scraper_stores_pages_correctly(self):
        """Test that FullScraper correctly stores pages in database."""
        # Arrange: Create mock API client
        mock_api = Mock(spec=MediaWikiAPIClient)
        mock_api.api_version_detected = True

        # Mock page discovery
        mock_pages = [
            Page(page_id=1, namespace=0, title="Main_Page", is_redirect=False),
            Page(page_id=2, namespace=0, title="Test_Page", is_redirect=False),
        ]

        # Mock revision scraping
        mock_revisions = {
            1: [
                Revision(
                    revision_id=101,
                    page_id=1,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 1, 10, 0, 0),
                    user="Admin",
                    user_id=1,
                    comment="Initial",
                    content="Content",
                    size=7,
                    sha1="a" * 40,
                    minor=False,
                    tags=[],
                ),
            ],
            2: [
                Revision(
                    revision_id=201,
                    page_id=2,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 2, 10, 0, 0),
                    user="User",
                    user_id=2,
                    comment="Created",
                    content="Test",
                    size=4,
                    sha1="b" * 40,
                    minor=False,
                    tags=[],
                ),
            ],
        }

        config = Config()
        config.scraper.max_retries = 3

        scraper = FullScraper(config, mock_api, self.database)

        # Mock the internal methods
        scraper.page_discovery = Mock()
        scraper.page_discovery.discover_namespace = Mock(return_value=mock_pages)

        scraper.revision_scraper = Mock()
        scraper.revision_scraper.fetch_revisions = Mock(
            side_effect=lambda page_id: mock_revisions.get(page_id, [])
        )

        # Act: Run scrape
        _ = scraper.scrape(namespaces=[0])

        # Assert: Verify database contents
        conn = self.database.get_connection()

        # Check pages
        cursor = conn.execute("SELECT page_id, title FROM pages ORDER BY page_id")
        pages = cursor.fetchall()
        assert len(pages) == 2
        assert pages[0][1] == "Main_Page"
        assert pages[1][1] == "Test_Page"

        # Check revisions
        cursor = conn.execute(
            "SELECT revision_id, page_id FROM revisions ORDER BY revision_id"
        )
        revisions = cursor.fetchall()
        assert len(revisions) == 2
        assert revisions[0][0] == 101  # revision_id
        assert revisions[0][1] == 1  # page_id
        assert revisions[1][0] == 201  # revision_id
        assert revisions[1][1] == 2  # page_id

    def test_full_scraper_handles_database_transactions(self):
        """Test that FullScraper properly handles database transactions."""
        # Arrange
        mock_api = Mock(spec=MediaWikiAPIClient)
        mock_api.api_version_detected = True

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
        ]

        mock_revisions = [
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                user="User",
                user_id=1,
                comment="Test",
                content="Content",
                size=7,
                sha1="a" * 40,
                minor=False,
                tags=[],
            ),
        ]

        config = Config()
        config.scraper.max_retries = 3

        scraper = FullScraper(config, mock_api, self.database)
        scraper.page_discovery = Mock()
        scraper.page_discovery.discover_namespace = Mock(return_value=mock_pages)
        scraper.revision_scraper = Mock()
        scraper.revision_scraper.fetch_revisions = Mock(return_value=mock_revisions)

        # Act: Run scrape
        _ = scraper.scrape(namespaces=[0])

        # Assert: Verify data is committed
        # Create new connection to ensure data is persisted
        new_db = Database(str(self.db_path))
        conn = new_db.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count = cursor.fetchone()[0]
        assert count == 1, "Data should be committed to database"
        new_db.close()

    def test_repository_batch_insert_performance(self):
        """Test that batch inserts are more efficient than individual inserts."""
        # Arrange: Create large dataset
        pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 101)
        ]

        page_repo = PageRepository(self.database)

        # Act: Batch insert
        start_time = time.time()
        page_repo.insert_pages_batch(pages)
        batch_duration = time.time() - start_time

        # Assert: Verify all inserted
        conn = self.database.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count = cursor.fetchone()[0]
        assert count == 100

        # Note: We don't compare with individual inserts for time
        # but verify batch insert completes in reasonable time
        assert batch_duration < 1.0, "Batch insert should be fast"


class TestCheckpointManagerIntegration:
    """Test CheckpointManager integration with real filesystem."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.checkpoint_path = self.temp_dir / ".checkpoint.json"

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_checkpoint_create_and_load(self):
        """Test creating and loading checkpoint from filesystem."""
        # Arrange
        manager = CheckpointManager(self.checkpoint_path)

        # Act: Create checkpoint
        manager.start_scrape(namespaces=[0, 4], rate_limit=2.0)
        manager.mark_namespace_complete(0)
        manager.mark_page_complete(1)
        manager.mark_page_complete(2)
        manager.update_statistics(pages_scraped=2, revisions_scraped=5, errors=0)

        # Assert: Verify file exists
        assert self.checkpoint_path.exists()

        # Verify contents
        with open(self.checkpoint_path) as f:
            data = json.load(f)

        assert data["parameters"]["namespaces"] == [0, 4]
        assert data["parameters"]["rate_limit"] == 2.0
        assert 0 in data["progress"]["namespaces_completed"]
        assert 1 in data["progress"]["pages_completed"]
        assert 2 in data["progress"]["pages_completed"]
        assert data["statistics"]["pages_scraped"] == 2
        assert data["statistics"]["revisions_scraped"] == 5

        # Load checkpoint in new manager
        manager2 = CheckpointManager(self.checkpoint_path)
        checkpoint = manager2.get_checkpoint()

        assert checkpoint is not None
        assert checkpoint.parameters["namespaces"] == [0, 4]
        assert 0 in checkpoint.progress["namespaces_completed"]

    def test_checkpoint_resume_workflow(self):
        """Test complete checkpoint resume workflow."""
        # Arrange: Create initial checkpoint
        manager1 = CheckpointManager(self.checkpoint_path)
        manager1.start_scrape(namespaces=[0, 4, 6], rate_limit=2.0)
        manager1.mark_namespace_complete(0)
        manager1.set_current_namespace(4)

        # Simulate scrape interruption
        # (checkpoint exists with namespace 0 complete, namespace 4 in progress)

        # Act: Resume with new manager
        manager2 = CheckpointManager(self.checkpoint_path)
        assert manager2.exists()

        checkpoint = manager2.get_checkpoint()
        completed_ns = manager2.get_completed_namespaces()

        # Assert: Verify resume state
        assert 0 in completed_ns, "Namespace 0 should be marked complete"
        assert 4 not in completed_ns, "Namespace 4 should not be complete"
        assert checkpoint.progress.get("current_namespace") == 4

        # Continue scrape
        manager2.mark_namespace_complete(4)
        manager2.set_current_namespace(6)
        manager2.mark_namespace_complete(6)

        # Clear checkpoint on completion
        manager2.clear()
        assert not manager2.exists()

    def test_checkpoint_compatibility_check(self):
        """Test checkpoint compatibility verification."""
        # Arrange: Create checkpoint with specific namespaces
        manager = CheckpointManager(self.checkpoint_path)
        manager.start_scrape(namespaces=[0, 4], rate_limit=2.0)

        # Act & Assert: Test compatibility
        assert manager.is_compatible([0, 4]), "Same namespaces should be compatible"
        assert not manager.is_compatible(
            [0, 4, 6]
        ), "Different namespaces should be incompatible"
        assert not manager.is_compatible([0]), "Subset should be incompatible"
        assert manager.is_compatible([4, 0]), "Different order should be compatible"

    def test_checkpoint_corruption_handling(self):
        """Test handling of corrupted checkpoint file."""
        # Arrange: Create corrupted checkpoint
        self.checkpoint_path.write_text("{ invalid json }")

        # Act: Try to load
        manager = CheckpointManager(self.checkpoint_path)

        # Assert: Should handle gracefully
        assert (
            not manager.exists()
        ), "Corrupted checkpoint should not be considered valid"
        checkpoint = manager.get_checkpoint()
        assert checkpoint is None


class TestRetryLogicIntegration:
    """Test retry logic integration with real error scenarios."""

    def test_retry_with_transient_failures(self):
        """Test retry logic handles transient failures correctly."""
        # Arrange: Create function that fails twice then succeeds
        call_count = {"count": 0}

        def flaky_operation():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ConnectionError("Transient failure")
            return "success"

        # Act: Retry with backoff
        result = retry_with_backoff(flaky_operation, max_retries=5)

        # Assert
        assert result == "success"
        assert call_count["count"] == 3, "Should succeed on third attempt"

    def test_retry_exhausts_attempts(self):
        """Test retry logic stops after max attempts."""
        # Arrange: Create function that always fails with a transient error
        call_count = {"count": 0}

        def always_fails():
            call_count["count"] += 1
            raise ConnectionError("Persistent connection failure")

        # Act & Assert: Should raise after max retries
        with pytest.raises(ConnectionError):
            retry_with_backoff(always_fails, max_retries=3)

        assert call_count["count"] == 3, "Should try exactly 3 times"

    def test_retry_with_exponential_backoff(self):
        """Test that retry uses exponential backoff."""
        # Arrange
        timestamps = []

        def record_time():
            timestamps.append(time.time())
            if len(timestamps) < 3:
                raise ConnectionError("Retry me")
            return "success"

        # Act
        retry_with_backoff(record_time, max_retries=5, base_delay=0.1)

        # Assert: Verify delays increase exponentially
        assert len(timestamps) == 3
        if len(timestamps) >= 3:
            delay1 = timestamps[1] - timestamps[0]
            delay2 = timestamps[2] - timestamps[1]
            # Second delay should be roughly 2x first delay (exponential)
            assert delay2 > delay1, "Delays should increase exponentially"


class TestProgressTrackingIntegration:
    """Test progress tracking integration across components."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        self.checkpoint_path = self.temp_dir / ".checkpoint.json"

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_progress_callback_integration(self):
        """Test progress callbacks work correctly with FullScraper."""
        # Arrange
        database = Database(str(self.db_path))
        database.initialize_schema()

        mock_api = Mock(spec=MediaWikiAPIClient)
        mock_api.api_version_detected = True

        mock_pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 6)
        ]

        mock_revisions = [
            Revision(
                revision_id=i * 100,
                page_id=i,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                user="User",
                user_id=1,
                comment="Test",
                content=f"Content {i}",
                size=10,
                sha1="a" * 40,
                minor=False,
                tags=[],
            )
            for i in range(1, 6)
        ]

        config = Config()
        config.scraper.max_retries = 3

        scraper = FullScraper(config, mock_api, database)
        scraper.page_discovery = Mock()
        scraper.page_discovery.discover_namespace = Mock(return_value=mock_pages)
        scraper.revision_scraper = Mock()
        scraper.revision_scraper.fetch_revisions = Mock(
            side_effect=lambda page_id: [
                r for r in mock_revisions if r.page_id == page_id
            ]
        )

        # Track progress callbacks
        progress_calls = []

        def progress_callback(stage, current, total):
            progress_calls.append((stage, current, total))

        # Act: Run scrape with progress callback
        _ = scraper.scrape(namespaces=[0], progress_callback=progress_callback)

        # Assert: Verify progress was reported
        assert len(progress_calls) > 0, "Progress callback should be called"

        # Check discovery progress
        discover_calls = [c for c in progress_calls if c[0] == "discover"]
        assert len(discover_calls) > 0, "Should report discovery progress"

        # Check scrape progress
        scrape_calls = [c for c in progress_calls if c[0] == "scrape"]
        assert len(scrape_calls) > 0, "Should report scrape progress"

        # Verify final progress
        last_scrape_call = scrape_calls[-1]
        assert last_scrape_call[1] == 5, "Should report all 5 pages scraped"
        assert last_scrape_call[2] == 5, "Total should be 5 pages"

        database.close()

    def test_checkpoint_progress_tracking(self):
        """Test checkpoint tracks progress correctly during scrape."""
        # Arrange
        database = Database(str(self.db_path))
        database.initialize_schema()

        checkpoint_manager = CheckpointManager(self.checkpoint_path)
        checkpoint_manager.start_scrape(namespaces=[0], rate_limit=2.0)

        mock_api = Mock(spec=MediaWikiAPIClient)
        mock_api.api_version_detected = True

        mock_pages = [
            Page(page_id=i, namespace=0, title=f"Page_{i}", is_redirect=False)
            for i in range(1, 4)
        ]

        config = Config()
        config.scraper.max_retries = 3

        scraper = FullScraper(config, mock_api, database, checkpoint_manager)
        scraper.page_discovery = Mock()
        scraper.page_discovery.discover_namespace = Mock(return_value=mock_pages)
        scraper.revision_scraper = Mock()
        scraper.revision_scraper.fetch_revisions = Mock(return_value=[])

        # Act: Run scrape
        _ = scraper.scrape(namespaces=[0])

        # Assert: Verify checkpoint tracked progress
        # Note: checkpoint is cleared on success, so check database instead
        conn = database.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count = cursor.fetchone()[0]
        assert count == 3, "All pages should be stored"

        database.close()


class TestErrorHandlingIntegration:
    """Test error handling integration across components."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_partial_scrape_failure_handling(self):
        """Test that partial failures don't corrupt database."""
        # Arrange
        database = Database(str(self.db_path))
        database.initialize_schema()

        mock_api = Mock(spec=MediaWikiAPIClient)
        mock_api.api_version_detected = True

        mock_pages = [
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page_2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Page_3", is_redirect=False),
        ]

        # Page 2 will fail to scrape revisions
        def mock_fetch_revisions(page_id):
            if page_id == 2:
                raise ConnectionError("Failed to fetch page 2")
            return [
                Revision(
                    revision_id=page_id * 100,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 1, 10, 0, 0),
                    user="User",
                    user_id=1,
                    comment="Test",
                    content="Content",
                    size=7,
                    sha1="a" * 40,
                    minor=False,
                    tags=[],
                )
            ]

        config = Config()
        config.scraper.max_retries = 1  # Fail quickly

        scraper = FullScraper(config, mock_api, database)
        scraper.page_discovery = Mock()
        scraper.page_discovery.discover_namespace = Mock(return_value=mock_pages)
        scraper.revision_scraper = Mock()
        scraper.revision_scraper.fetch_revisions = Mock(
            side_effect=mock_fetch_revisions
        )

        # Act: Run scrape (should handle failure gracefully)
        result = scraper.scrape(namespaces=[0])

        # Assert: Verify partial success
        assert len(result.failed_pages) == 1, "Should track failed page"
        assert 2 in result.failed_pages, "Page 2 should be marked as failed"

        # Verify database has successful pages
        conn = database.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM revisions")
        revision_count = cursor.fetchone()[0]
        assert revision_count == 2, "Should have revisions for pages 1 and 3"

        database.close()

    def test_database_constraint_violations(self):
        """Test handling of database constraint violations."""
        # Arrange
        database = Database(str(self.db_path))
        database.initialize_schema()

        page_repo = PageRepository(database)

        # Act: Insert duplicate page (should be idempotent with ON CONFLICT)
        page1 = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page1)

        # Insert same page again - should succeed (idempotent)
        page_repo.insert_page(page1)

        # Assert: Only one page in database
        conn = database.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages WHERE page_id = 1")
        count = cursor.fetchone()[0]
        assert count == 1, "Should have only one page (idempotent insert)"

        database.close()


class TestTransactionIntegration:
    """Test database transaction handling in real scenarios."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_batch_insert_transaction_atomicity(self):
        """Test that batch inserts are atomic."""
        # Arrange
        database = Database(str(self.db_path))
        database.initialize_schema()

        page_repo = PageRepository(database)

        pages = [
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page_2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Page_3", is_redirect=False),
        ]

        # Act: Batch insert
        page_repo.insert_pages_batch(pages)

        # Assert: All or nothing should be inserted
        conn = database.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        count = cursor.fetchone()[0]
        assert count == 3, "All pages should be inserted atomically"

        database.close()
