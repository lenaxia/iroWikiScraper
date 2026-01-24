"""Integration tests for complete incremental update workflow."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scraper.incremental.models import ChangeSet, IncrementalStats
from scraper.incremental.page_scraper import (
    FirstRunRequiresFullScrapeError,
    IncrementalPageScraper,
)
from scraper.incremental.verification import IncrementalVerifier
from scraper.storage.models import Page, Revision
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository


@pytest.fixture
def temp_download_dir(tmp_path):
    """Create temporary download directory."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


class TestFullIncrementalWorkflow:
    """Test complete end-to-end incremental update workflow."""

    def test_first_run_requires_full_scrape(self, db, temp_download_dir):
        """Test first run with no previous scrape raises appropriate error."""
        mock_api = Mock()
        scraper = IncrementalPageScraper(mock_api, db, temp_download_dir)

        # Mock change detector to return first run
        changeset = ChangeSet(requires_full_scrape=True)
        with patch.object(
            scraper.change_detector, "detect_changes", return_value=changeset
        ):
            with pytest.raises(FirstRunRequiresFullScrapeError):
                scraper.scrape_incremental()

    def test_verification_after_successful_scrape(self, db, temp_download_dir):
        """Test integrity verification after successful incremental update."""
        # Setup: Add some data
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test_Page", is_redirect=False)
        page_repo.insert_page(page)

        rev = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2026, 1, 1),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Test content",
            size=100,
            sha1="a" * 40,
            minor=False,
            tags=None,
        )
        rev_repo.insert_revision(rev)

        # Run verification
        verifier = IncrementalVerifier(db)
        issues = verifier.verify_all()

        # Should have no issues
        total_issues = sum(len(v) for v in issues.values())
        assert total_issues == 0


class TestPerformance:
    """Test performance benchmarks for incremental operations."""

    def test_verification_performance(self, db, temp_download_dir):
        """Test that verification completes in reasonable time."""
        # Add some test data
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        # Add 100 pages with revisions
        for i in range(100):
            page = Page(
                page_id=i + 1, namespace=0, title=f"Page_{i}", is_redirect=False
            )
            page_repo.insert_page(page)

            rev = Revision(
                revision_id=(i + 1) * 1000,
                page_id=i + 1,
                parent_id=None,
                timestamp=datetime(2026, 1, 1),
                user="TestUser",
                user_id=1,
                comment="Test",
                content=f"Content for page {i}",
                size=100 + i,
                sha1=f"{i:040d}",
                minor=False,
                tags=None,
            )
            rev_repo.insert_revision(rev)

        # Time verification
        import time

        verifier = IncrementalVerifier(db)

        start = time.time()
        issues = verifier.verify_all()
        duration = time.time() - start

        # Should complete in under 5 seconds for 100 pages
        assert duration < 5.0

        # Should have no issues
        total_issues = sum(len(v) for v in issues.values())
        assert total_issues == 0


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_database_verification(self, db):
        """Test verification on empty database."""
        verifier = IncrementalVerifier(db)

        issues = verifier.verify_all()

        # Should not crash, should return empty issues
        assert isinstance(issues, dict)
        total_issues = sum(len(v) for v in issues.values())
        assert total_issues == 0

    def test_page_without_revisions_detected(self, db):
        """Test that verification detects pages without revisions."""
        page_repo = PageRepository(db)

        # Insert page but no revisions
        page = Page(page_id=1, namespace=0, title="Orphan_Page", is_redirect=False)
        page_repo.insert_page(page)

        verifier = IncrementalVerifier(db)
        issues = verifier.verify_all()

        # Should detect the issue
        assert len(issues["revision_continuity"]) > 0
        assert "pages with no revisions" in issues["revision_continuity"][0]
