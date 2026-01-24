"""
Test Revision CRUD operations (Story 08).

Tests the RevisionRepository class for:
- Insert single revision
- Batch insert
- Get by revision_id
- Get revisions by page
- Get latest revision
- Temporal queries
- NULL field handling
- Tags JSON conversion
"""

from datetime import datetime

import pytest

from scraper.storage.models import Revision
from scraper.storage.revision_repository import RevisionRepository


@pytest.fixture(autouse=True)
def setup_pages_for_revisions(db):
    """Insert required pages for revisions (foreign key constraint).

    This fixture runs automatically for all tests in this module.
    """
    from scraper.storage.models import Page
    from scraper.storage.page_repository import PageRepository

    repo = PageRepository(db)
    # Create pages 1-1000 to support all revision tests
    pages = [
        Page(page_id=i, namespace=0, title=f"Page {i}", is_redirect=False)
        for i in range(1, 1001)
    ]
    repo.insert_pages_batch(pages)


class TestRevisionInsertion:
    """Test revision insertion operations."""

    def test_insert_single_revision(self, db, sample_revisions):
        """Test inserting single revision."""
        repo = RevisionRepository(db)
        revision = sample_revisions[0]

        repo.insert_revision(revision)

        # Verify inserted
        loaded = repo.get_revision(revision.revision_id)
        assert loaded is not None
        assert loaded.revision_id == revision.revision_id
        assert loaded.content == revision.content

    def test_insert_revisions_batch(self, db, sample_revisions):
        """Test batch insert."""
        repo = RevisionRepository(db)

        repo.insert_revisions_batch(sample_revisions)

        count = repo.count_revisions()
        assert count == 3

    def test_insert_revisions_batch_large(self, db):
        """Test batch insert with 1000 revisions."""
        repo = RevisionRepository(db)
        revisions = [
            Revision(
                revision_id=i,
                page_id=1,
                parent_id=i - 1 if i > 1 else None,
                timestamp=datetime(2024, 1, 1, i % 24, i % 60, 0),
                user=f"User{i % 10}",
                user_id=i % 10 + 100,
                comment=f"Edit {i}",
                content=f"Content version {i}" * 10,
                size=len(f"Content version {i}" * 10),
                sha1=f"{i:040d}",
                minor=i % 2 == 0,
                tags=["tag1", "tag2"] if i % 3 == 0 else [],
            )
            for i in range(1, 1001)
        ]

        repo.insert_revisions_batch(revisions)

        count = repo.count_revisions()
        assert count == 1000

    def test_insert_revisions_batch_empty(self, db):
        """Test batch insert with empty list."""
        repo = RevisionRepository(db)

        # Should not raise error
        repo.insert_revisions_batch([])

        count = repo.count_revisions()
        assert count == 0


class TestRevisionRetrieval:
    """Test revision retrieval operations."""

    def test_get_revision_exists(self, db, sample_revisions):
        """Test get revision by ID when it exists."""
        repo = RevisionRepository(db)
        repo.insert_revisions_batch(sample_revisions)

        loaded = repo.get_revision(1001)
        assert loaded is not None
        assert loaded.revision_id == 1001
        assert loaded.user == "Alice"

    def test_get_revision_not_exists(self, db):
        """Test get revision by ID when it doesn't exist."""
        repo = RevisionRepository(db)

        loaded = repo.get_revision(999)
        assert loaded is None

    def test_get_revisions_by_page(self, db, sample_revisions):
        """Test get revisions for a page."""
        repo = RevisionRepository(db)
        repo.insert_revisions_batch(sample_revisions)

        # Get revisions for page 1
        revisions = repo.get_revisions_by_page(page_id=1)
        assert len(revisions) == 2  # Two revisions for page 1
        assert all(r.page_id == 1 for r in revisions)

        # Should be ordered newest first
        assert revisions[0].timestamp > revisions[1].timestamp

    def test_get_revisions_by_page_pagination(self, db):
        """Test pagination of page revisions."""
        repo = RevisionRepository(db)

        # Create 50 revisions for same page
        revisions = [
            Revision(
                revision_id=i,
                page_id=1,
                parent_id=i - 1 if i > 1 else None,
                timestamp=datetime(2024, 1, 1, 0, i, 0),
                user="User",
                user_id=100,
                comment=f"Edit {i}",
                content=f"Content {i}",
                size=len(f"Content {i}"),
                sha1=f"{i:040d}",
                minor=False,
            )
            for i in range(1, 51)
        ]
        repo.insert_revisions_batch(revisions)

        # First page
        page1 = repo.get_revisions_by_page(page_id=1, limit=20, offset=0)
        assert len(page1) == 20

        # Second page
        page2 = repo.get_revisions_by_page(page_id=1, limit=20, offset=20)
        assert len(page2) == 20

        # No overlap
        ids1 = {r.revision_id for r in page1}
        ids2 = {r.revision_id for r in page2}
        assert len(ids1 & ids2) == 0

    def test_get_latest_revision(self, db):
        """Test getting latest revision for a page."""
        repo = RevisionRepository(db)

        # Create revisions with different timestamps
        revisions = [
            Revision(
                revision_id=1,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                user="User1",
                user_id=100,
                comment="First",
                content="First version",
                size=13,
                sha1="a" * 40,
                minor=False,
            ),
            Revision(
                revision_id=2,
                page_id=1,
                parent_id=1,
                timestamp=datetime(2024, 1, 2, 10, 0, 0),
                user="User2",
                user_id=101,
                comment="Second",
                content="Second version",
                size=14,
                sha1="b" * 40,
                minor=False,
            ),
            Revision(
                revision_id=3,
                page_id=1,
                parent_id=2,
                timestamp=datetime(2024, 1, 3, 10, 0, 0),
                user="User3",
                user_id=102,
                comment="Latest",
                content="Latest version",
                size=14,
                sha1="c" * 40,
                minor=False,
            ),
        ]
        repo.insert_revisions_batch(revisions)

        latest = repo.get_latest_revision(page_id=1)
        assert latest is not None
        assert latest.revision_id == 3
        assert latest.comment == "Latest"

    def test_get_latest_revision_no_revisions(self, db):
        """Test get latest revision when page has no revisions."""
        repo = RevisionRepository(db)

        latest = repo.get_latest_revision(page_id=999)
        assert latest is None


class TestRevisionTemporalQueries:
    """Test temporal (time-based) queries."""

    def test_get_revisions_in_range(self, db):
        """Test getting revisions in time range."""
        repo = RevisionRepository(db)

        revisions = [
            Revision(
                revision_id=1,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Jan 1",
                content="Content",
                size=7,
                sha1="a" * 40,
                minor=False,
            ),
            Revision(
                revision_id=2,
                page_id=1,
                parent_id=1,
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Jan 15",
                content="Content",
                size=7,
                sha1="b" * 40,
                minor=False,
            ),
            Revision(
                revision_id=3,
                page_id=1,
                parent_id=2,
                timestamp=datetime(2024, 2, 1, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Feb 1",
                content="Content",
                size=7,
                sha1="c" * 40,
                minor=False,
            ),
        ]
        repo.insert_revisions_batch(revisions)

        # Query January revisions
        jan_revisions = repo.get_revisions_in_range(
            start=datetime(2024, 1, 1, 0, 0, 0), end=datetime(2024, 2, 1, 0, 0, 0)
        )

        assert len(jan_revisions) == 2
        assert all(r.timestamp.month == 1 for r in jan_revisions)

    def test_get_page_at_time(self, db):
        """Test getting page state at specific time."""
        repo = RevisionRepository(db)

        revisions = [
            Revision(
                revision_id=1,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Version 1",
                content="Content v1",
                size=10,
                sha1="a" * 40,
                minor=False,
            ),
            Revision(
                revision_id=2,
                page_id=1,
                parent_id=1,
                timestamp=datetime(2024, 1, 10, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Version 2",
                content="Content v2",
                size=10,
                sha1="b" * 40,
                minor=False,
            ),
            Revision(
                revision_id=3,
                page_id=1,
                parent_id=2,
                timestamp=datetime(2024, 1, 20, 10, 0, 0),
                user="User",
                user_id=100,
                comment="Version 3",
                content="Content v3",
                size=10,
                sha1="c" * 40,
                minor=False,
            ),
        ]
        repo.insert_revisions_batch(revisions)

        # Get page state on Jan 5 (should be revision 1)
        rev_jan5 = repo.get_page_at_time(
            page_id=1, timestamp=datetime(2024, 1, 5, 0, 0, 0)
        )
        assert rev_jan5 is not None
        assert rev_jan5.revision_id == 1

        # Get page state on Jan 15 (should be revision 2)
        rev_jan15 = repo.get_page_at_time(
            page_id=1, timestamp=datetime(2024, 1, 15, 0, 0, 0)
        )
        assert rev_jan15 is not None
        assert rev_jan15.revision_id == 2

        # Get page state on Jan 25 (should be revision 3)
        rev_jan25 = repo.get_page_at_time(
            page_id=1, timestamp=datetime(2024, 1, 25, 0, 0, 0)
        )
        assert rev_jan25 is not None
        assert rev_jan25.revision_id == 3

    def test_get_page_at_time_before_creation(self, db):
        """Test getting page state before it was created."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 10, 10, 0, 0),
            user="User",
            user_id=100,
            comment="Created",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
        )
        repo.insert_revision(revision)

        # Query before creation
        result = repo.get_page_at_time(
            page_id=1, timestamp=datetime(2024, 1, 1, 0, 0, 0)
        )
        assert result is None


class TestRevisionNullHandling:
    """Test handling of NULL fields."""

    def test_insert_revision_with_null_parent(self, db):
        """Test inserting revision with NULL parent_id."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,  # NULL
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="User",
            user_id=100,
            comment="First revision",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
        )

        repo.insert_revision(revision)

        loaded = repo.get_revision(1)
        assert loaded.parent_id is None

    def test_insert_revision_with_null_user_id(self, db):
        """Test inserting revision with NULL user_id."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="AnonymousUser",
            user_id=None,  # NULL (anonymous/deleted user)
            comment="Anonymous edit",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
        )

        repo.insert_revision(revision)

        loaded = repo.get_revision(1)
        assert loaded.user_id is None
        assert loaded.user == "AnonymousUser"

    def test_insert_revision_with_null_tags(self, db):
        """Test inserting revision with NULL tags."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="User",
            user_id=100,
            comment="No tags",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
            tags=None,  # NULL
        )

        repo.insert_revision(revision)

        loaded = repo.get_revision(1)
        assert loaded.tags == [] or loaded.tags is None


class TestRevisionTagsJson:
    """Test tags JSON serialization/deserialization."""

    def test_tags_roundtrip(self, db):
        """Test tags survive roundtrip conversion."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="User",
            user_id=100,
            comment="Tagged edit",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
            tags=["visual-edit", "mobile-edit", "mw-reverted"],
        )

        repo.insert_revision(revision)

        loaded = repo.get_revision(1)
        assert loaded.tags == ["visual-edit", "mobile-edit", "mw-reverted"]

    def test_empty_tags_list(self, db):
        """Test empty tags list."""
        repo = RevisionRepository(db)

        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="User",
            user_id=100,
            comment="No tags",
            content="Content",
            size=7,
            sha1="a" * 40,
            minor=False,
            tags=[],
        )

        repo.insert_revision(revision)

        loaded = repo.get_revision(1)
        assert loaded.tags == [] or loaded.tags is None


class TestRevisionCount:
    """Test revision counting operations."""

    def test_count_revisions_empty(self, db):
        """Test count on empty database."""
        repo = RevisionRepository(db)

        count = repo.count_revisions()
        assert count == 0

    def test_count_revisions_all(self, db, sample_revisions):
        """Test count all revisions."""
        repo = RevisionRepository(db)
        repo.insert_revisions_batch(sample_revisions)

        count = repo.count_revisions()
        assert count == 3

    def test_count_revisions_by_page(self, db):
        """Test count revisions for specific page."""
        repo = RevisionRepository(db)

        revisions = [
            Revision(
                revision_id=i,
                page_id=1 if i <= 3 else 2,
                parent_id=None,
                timestamp=datetime(2024, 1, 1, i, 0, 0),
                user="User",
                user_id=100,
                comment=f"Edit {i}",
                content=f"Content {i}",
                size=len(f"Content {i}"),
                sha1=f"{i:040d}",
                minor=False,
            )
            for i in range(1, 6)
        ]
        repo.insert_revisions_batch(revisions)

        assert repo.count_revisions(page_id=1) == 3
        assert repo.count_revisions(page_id=2) == 2
        assert repo.count_revisions() == 5


class TestRevisionDataConversion:
    """Test Revision dataclass <-> database row conversion."""

    def test_roundtrip_conversion(self, db):
        """Test that all fields survive roundtrip conversion."""
        from scraper.storage.models import Page
        from scraper.storage.page_repository import PageRepository

        # Create page 678 for the revision
        page_repo = PageRepository(db)
        page_repo.insert_page(
            Page(page_id=678, namespace=0, title="Test Page 678", is_redirect=False)
        )

        repo = RevisionRepository(db)

        original = Revision(
            revision_id=12345,
            page_id=678,
            parent_id=None,  # First revision, no parent
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            user="TestUser",
            user_id=999,
            comment="Test edit comment",
            content="This is the page content",
            size=24,
            sha1="abcdef1234567890abcdef1234567890abcdef12",
            minor=True,
            tags=["tag1", "tag2", "tag3"],
        )

        repo.insert_revision(original)
        loaded = repo.get_revision(12345)

        assert loaded.revision_id == original.revision_id
        assert loaded.page_id == original.page_id
        assert loaded.parent_id == original.parent_id
        assert loaded.timestamp == original.timestamp
        assert loaded.user == original.user
        assert loaded.user_id == original.user_id
        assert loaded.comment == original.comment
        assert loaded.content == original.content
        assert loaded.size == original.size
        assert loaded.sha1 == original.sha1
        assert loaded.minor == original.minor
        assert loaded.tags == original.tags
