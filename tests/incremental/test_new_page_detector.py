"""Tests for NewPageDetector."""

from datetime import datetime, timezone

import pytest

from scraper.incremental.models import NewPageInfo
from scraper.incremental.new_page_detector import NewPageDetector


class TestNewPageDetectorInit:
    """Tests for NewPageDetector initialization."""

    def test_init_with_database(self, db):
        """Test NewPageDetector initializes with database."""
        detector = NewPageDetector(db)
        assert detector.db is db


class TestVerifyNewPage:
    """Tests for verify_new_page method."""

    def test_returns_true_for_nonexistent_page(self, db):
        """Test returns True for page not in database."""
        detector = NewPageDetector(db)

        # Page ID 99999 doesn't exist
        is_new = detector.verify_new_page(99999)

        assert is_new is True

    def test_returns_false_for_existing_page(self, db, sample_pages):
        """Test returns False for page in database."""
        # Insert a page
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        repo.insert_page(sample_pages[0])

        detector = NewPageDetector(db)
        is_new = detector.verify_new_page(sample_pages[0].page_id)

        assert is_new is False


class TestVerifyNewPages:
    """Tests for verify_new_pages batch method."""

    def test_empty_list_returns_empty_set(self, db):
        """Test empty input returns empty set."""
        detector = NewPageDetector(db)
        new_ids = detector.verify_new_pages([])

        assert new_ids == set()

    def test_all_new_pages(self, db):
        """Test returns all IDs when none exist in database."""
        detector = NewPageDetector(db)
        candidate_ids = [1001, 1002, 1003, 1004, 1005]

        new_ids = detector.verify_new_pages(candidate_ids)

        assert new_ids == set(candidate_ids)

    def test_all_existing_pages(self, db, sample_pages):
        """Test returns empty set when all pages exist."""
        # Insert pages
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        for page in sample_pages:
            repo.insert_page(page)

        detector = NewPageDetector(db)
        existing_ids = [p.page_id for p in sample_pages]

        new_ids = detector.verify_new_pages(existing_ids)

        assert new_ids == set()

    def test_mix_of_new_and_existing(self, db, sample_pages):
        """Test correctly identifies new vs existing pages."""
        # Insert some pages
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        repo.insert_page(sample_pages[0])  # page_id=1
        repo.insert_page(sample_pages[1])  # page_id=2

        detector = NewPageDetector(db)
        candidate_ids = [1, 2, 3, 4, 5]  # 1,2 exist, 3,4,5 are new

        new_ids = detector.verify_new_pages(candidate_ids)

        assert new_ids == {3, 4, 5}

    def test_logs_warning_for_already_existing(self, db, sample_pages, caplog):
        """Test logs warning when 'new' pages already exist."""
        import logging

        caplog.set_level(logging.WARNING)

        # Insert a page
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        repo.insert_page(sample_pages[0])

        detector = NewPageDetector(db)
        candidate_ids = [sample_pages[0].page_id, 999]

        new_ids = detector.verify_new_pages(candidate_ids)

        assert "already in database" in caplog.text
        assert new_ids == {999}


class TestFilterNewPages:
    """Tests for filter_new_pages alias method."""

    def test_alias_for_verify_new_pages(self, db):
        """Test filter_new_pages is alias for verify_new_pages."""
        detector = NewPageDetector(db)
        candidate_ids = [100, 101, 102]

        result1 = detector.verify_new_pages(candidate_ids)
        result2 = detector.filter_new_pages(candidate_ids)

        assert result1 == result2


class TestGetNewPageInfo:
    """Tests for get_new_page_info method."""

    def test_creates_new_page_info(self, db):
        """Test creates NewPageInfo with provided metadata."""
        detector = NewPageDetector(db)

        info = detector.get_new_page_info(page_id=123, title="Test_Page", namespace=0)

        assert isinstance(info, NewPageInfo)
        assert info.page_id == 123
        assert info.title == "Test_Page"
        assert info.namespace == 0
        assert info.detected_at is not None

    def test_detected_at_is_recent(self, db):
        """Test detected_at timestamp is current."""
        detector = NewPageDetector(db)
        before = datetime.now(timezone.utc)

        info = detector.get_new_page_info(123, "Test", 0)

        after = datetime.now(timezone.utc)
        assert before <= info.detected_at <= after

    def test_new_page_info_properties(self, db):
        """Test NewPageInfo properties work correctly."""
        detector = NewPageDetector(db)
        info = detector.get_new_page_info(123, "Test", 0)

        assert info.needs_full_scrape is True
        params = info.to_scrape_params()
        assert params["pageids"] == 123
        assert params["rvdir"] == "newer"


class TestPerformance:
    """Tests for performance requirements."""

    def test_single_page_query_fast(self, db, sample_pages):
        """Test single page query is fast (<1ms target)."""
        import time

        # Insert some pages for realistic test
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        for page in sample_pages[:10]:
            repo.insert_page(page)

        detector = NewPageDetector(db)

        start = time.time()
        detector.verify_new_page(99999)
        elapsed = time.time() - start

        # Should be very fast (allow 10ms for test overhead)
        assert elapsed < 0.01

    def test_batch_query_500_pages_fast(self, db):
        """Test batch query of 500 pages is fast (<50ms target)."""
        import time

        detector = NewPageDetector(db)
        # Generate 500 page IDs
        page_ids = list(range(1000, 1500))

        start = time.time()
        detector.verify_new_pages(page_ids)
        elapsed = time.time() - start

        # Should complete in <50ms (allow 100ms for test overhead)
        assert elapsed < 0.1
