"""Tests for ModifiedPageDetector."""

import pytest

from scraper.api.exceptions import PageNotFoundError
from scraper.incremental.models import PageUpdateInfo
from scraper.incremental.modified_page_detector import ModifiedPageDetector


class TestModifiedPageDetectorInit:
    """Tests for ModifiedPageDetector initialization."""

    def test_init_with_database(self, db):
        """Test ModifiedPageDetector initializes with database."""
        detector = ModifiedPageDetector(db)
        assert detector.db is db


class TestGetPageUpdateInfo:
    """Tests for get_page_update_info method."""

    def test_raises_error_for_nonexistent_page(self, db):
        """Test raises PageNotFoundError for missing page."""
        detector = ModifiedPageDetector(db)

        with pytest.raises(PageNotFoundError) as exc_info:
            detector.get_page_update_info(99999)

        assert "99999" in str(exc_info.value)

    def test_returns_info_for_page_with_revisions(
        self, db, sample_pages, sample_revisions
    ):
        """Test returns correct info for page with multiple revisions."""
        # Insert page and revisions
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page_repo.insert_page(sample_pages[0])  # page_id=1
        for rev in sample_revisions[:2]:  # 2 revisions for page 1
            rev_repo.insert_revision(rev)

        detector = ModifiedPageDetector(db)
        info = detector.get_page_update_info(1)

        assert isinstance(info, PageUpdateInfo)
        assert info.page_id == 1
        assert info.title == sample_pages[0].title
        assert info.namespace == sample_pages[0].namespace
        assert info.highest_revision_id == 1002  # Last revision
        assert info.total_revisions_stored == 2

    def test_handles_page_with_no_revisions(self, db, sample_pages, caplog):
        """Test handles page with no revisions (logs warning)."""
        import logging

        caplog.set_level(logging.WARNING)

        # Insert page but no revisions
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        repo.insert_page(sample_pages[0])

        detector = ModifiedPageDetector(db)
        info = detector.get_page_update_info(sample_pages[0].page_id)

        assert info.total_revisions_stored == 0
        assert info.highest_revision_id == 0
        assert "has no revisions" in caplog.text

    def test_page_update_info_properties(self, db, sample_pages, sample_revisions):
        """Test PageUpdateInfo properties work correctly."""
        # Setup
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(sample_pages[0])
        rev_repo.insert_revision(sample_revisions[0])

        detector = ModifiedPageDetector(db)
        info = detector.get_page_update_info(sample_pages[0].page_id)

        assert info.needs_update is True
        filter_params = info.get_revision_filter()
        assert filter_params["rvstartid"] == info.highest_revision_id + 1
        assert filter_params["rvdir"] == "newer"


class TestGetBatchUpdateInfo:
    """Tests for get_batch_update_info method."""

    def test_empty_list_returns_empty_list(self, db):
        """Test empty input returns empty list."""
        detector = ModifiedPageDetector(db)
        infos = detector.get_batch_update_info([])

        assert infos == []

    def test_returns_info_for_all_pages(self, db, sample_pages, sample_revisions):
        """Test returns info for all pages in batch."""
        # Insert pages and revisions
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        for page in sample_pages[:3]:
            page_repo.insert_page(page)
        for rev in sample_revisions[:3]:
            rev_repo.insert_revision(rev)

        detector = ModifiedPageDetector(db)
        page_ids = [1, 2, 3]
        infos = detector.get_batch_update_info(page_ids)

        assert len(infos) == 3
        assert all(isinstance(info, PageUpdateInfo) for info in infos)
        info_ids = {info.page_id for info in infos}
        assert info_ids == {1, 2, 3}

    def test_skips_missing_pages_with_warning(self, db, sample_pages, caplog):
        """Test skips pages not in database and logs warning."""
        import logging

        caplog.set_level(logging.WARNING)

        # Insert only one page
        from scraper.storage.page_repository import PageRepository

        repo = PageRepository(db)
        repo.insert_page(sample_pages[0])  # page_id=1

        detector = ModifiedPageDetector(db)
        page_ids = [1, 999, 1000]  # Only 1 exists

        infos = detector.get_batch_update_info(page_ids)

        assert len(infos) == 1
        assert infos[0].page_id == 1
        assert "not found in database" in caplog.text

    def test_handles_mix_of_pages_with_and_without_revisions(
        self, db, sample_pages, sample_revisions
    ):
        """Test handles pages with different revision counts."""
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        # Insert 3 pages
        for page in sample_pages[:3]:
            page_repo.insert_page(page)

        # Page 1: 2 revisions
        # Page 2: 1 revision
        # Page 3: 0 revisions
        rev_repo.insert_revision(sample_revisions[0])  # page_id=1
        rev_repo.insert_revision(sample_revisions[1])  # page_id=1
        rev_repo.insert_revision(sample_revisions[2])  # page_id=2

        detector = ModifiedPageDetector(db)
        infos = detector.get_batch_update_info([1, 2, 3])

        assert len(infos) == 3

        # Find each page's info
        info_by_id = {info.page_id: info for info in infos}

        assert info_by_id[1].total_revisions_stored == 2
        assert info_by_id[2].total_revisions_stored == 1
        assert info_by_id[3].total_revisions_stored == 0


class TestPerformance:
    """Tests for performance requirements."""

    def test_single_page_query_fast(self, db, sample_pages, sample_revisions):
        """Test single page query is fast (<10ms target)."""
        import time

        # Setup test data
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(sample_pages[0])
        rev_repo.insert_revision(sample_revisions[0])

        detector = ModifiedPageDetector(db)

        start = time.time()
        detector.get_page_update_info(sample_pages[0].page_id)
        elapsed = time.time() - start

        # Should complete in <10ms (allow 50ms for test overhead)
        assert elapsed < 0.05

    def test_batch_query_100_pages_fast(self, db):
        """Test batch query of 100 pages is fast (<100ms target)."""
        import time

        from scraper.storage.models import Page
        from scraper.storage.page_repository import PageRepository

        # Create 100 pages
        page_repo = PageRepository(db)
        for i in range(100):
            page = Page(
                page_id=i + 1, namespace=0, title=f"Test_Page_{i}", is_redirect=False
            )
            page_repo.insert_page(page)

        detector = ModifiedPageDetector(db)
        page_ids = list(range(1, 101))

        start = time.time()
        infos = detector.get_batch_update_info(page_ids)
        elapsed = time.time() - start

        assert len(infos) == 100
        # Should complete in <100ms (allow 200ms for test overhead)
        assert elapsed < 0.2
