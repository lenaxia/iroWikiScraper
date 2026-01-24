"""Tests for IncrementalVerifier."""

import pytest
from scraper.incremental.verification import IncrementalVerifier
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository
from scraper.storage.link_storage import LinkStorage
from scraper.storage.models import Page, Revision, Link
from datetime import datetime


class TestIncrementalVerifier:
    """Tests for IncrementalVerifier."""

    def test_init(self, db):
        """Test initialization."""
        verifier = IncrementalVerifier(db)

        assert verifier.db is db
        assert verifier.conn is not None

    def test_verify_all_clean_database(self, db):
        """Test verify_all with no issues."""
        verifier = IncrementalVerifier(db)

        issues = verifier.verify_all()

        assert isinstance(issues, dict)
        assert "duplicates" in issues
        assert "referential_integrity" in issues
        assert "revision_continuity" in issues
        assert "link_consistency" in issues

        # All should be empty (no issues)
        assert len(issues["duplicates"]) == 0
        assert len(issues["referential_integrity"]) == 0
        assert len(issues["revision_continuity"]) == 0
        assert len(issues["link_consistency"]) == 0

    def test_verify_no_duplicates_clean(self, db):
        """Test duplicate check with no duplicates."""
        # Add some pages and revisions (no duplicates)
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        rev = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2026, 1, 1),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Content",
            size=100,
            sha1="a" * 40,
            minor=False,
            tags=None,
        )
        rev_repo.insert_revision(rev)

        verifier = IncrementalVerifier(db)
        issues = verifier.verify_no_duplicates()

        assert len(issues) == 0

    def test_verify_referential_integrity_clean(self, db):
        """Test referential integrity with no orphans."""
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        rev = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2026, 1, 1),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Content",
            size=100,
            sha1="a" * 40,
            minor=False,
            tags=None,
        )
        rev_repo.insert_revision(rev)

        verifier = IncrementalVerifier(db)
        issues = verifier.verify_referential_integrity()

        assert len(issues) == 0

    def test_verify_revision_continuity_with_page_no_revisions(self, db):
        """Test detecting pages without revisions."""
        page_repo = PageRepository(db)

        # Insert page but no revisions
        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        verifier = IncrementalVerifier(db)
        issues = verifier.verify_revision_continuity()

        assert len(issues) == 1
        assert "pages with no revisions" in issues[0]

    def test_verify_revision_continuity_clean(self, db):
        """Test revision continuity with all pages having revisions."""
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        rev = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2026, 1, 1),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Content",
            size=100,
            sha1="a" * 40,
            minor=False,
            tags=None,
        )
        rev_repo.insert_revision(rev)

        verifier = IncrementalVerifier(db)
        issues = verifier.verify_revision_continuity()

        assert len(issues) == 0

    def test_verify_link_consistency(self, db):
        """Test link consistency check."""
        verifier = IncrementalVerifier(db)
        issues = verifier.verify_link_consistency()

        # Link consistency check doesn't report issues (just logs info)
        assert len(issues) == 0

    def test_has_issues_property_clean(self, db):
        """Test has_issues property with clean database."""
        # Add some clean data
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        rev = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2026, 1, 1),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Content",
            size=100,
            sha1="a" * 40,
            minor=False,
            tags=None,
        )
        rev_repo.insert_revision(rev)

        verifier = IncrementalVerifier(db)

        assert not verifier.has_issues

    def test_has_issues_property_with_issues(self, db):
        """Test has_issues property with issues present."""
        page_repo = PageRepository(db)

        # Insert page without revisions (causes issue)
        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)

        verifier = IncrementalVerifier(db)

        assert verifier.has_issues
