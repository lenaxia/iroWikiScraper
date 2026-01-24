"""Tests for ChangeDetector."""

from datetime import datetime, timezone
from unittest.mock import Mock


from scraper.api.recentchanges import RecentChange
from scraper.incremental.change_detector import ChangeDetector
from scraper.incremental.models import ChangeSet, MovedPage


class TestChangeDetectorInit:
    """Tests for ChangeDetector initialization."""

    def test_init_with_database_and_client(self, db):
        """Test ChangeDetector initializes with database and RC client."""
        mock_rc_client = Mock()
        detector = ChangeDetector(db, mock_rc_client)

        assert detector.db is db
        assert detector.rc_client is mock_rc_client


class TestDetectChangesFirstRun:
    """Tests for first run scenario (no previous scrape)."""

    def test_first_run_returns_requires_full_scrape(self, db):
        """Test first run returns ChangeSet with requires_full_scrape=True."""
        mock_rc_client = Mock()
        detector = ChangeDetector(db, mock_rc_client)

        changeset = detector.detect_changes()

        assert changeset.requires_full_scrape is True
        assert len(changeset.new_page_ids) == 0
        assert len(changeset.modified_page_ids) == 0
        assert len(changeset.deleted_page_ids) == 0


class TestDetectChanges:
    """Tests for detect_changes with previous scrape."""

    def test_detects_new_pages(self, db):
        """Test detects new pages from recent changes."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client to return new page changes
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=1,
                type="new",
                namespace=0,
                title="New_Page",
                pageid=100,
                revid=1000,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
                user="User1",
                userid=1,
                comment="Created",
                oldlen=0,
                newlen=500,
            )
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert changeset.requires_full_scrape is False
        assert 100 in changeset.new_page_ids
        assert len(changeset.modified_page_ids) == 0

    def test_detects_modified_pages(self, db):
        """Test detects edited pages from recent changes."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=2,
                type="edit",
                namespace=0,
                title="Existing_Page",
                pageid=200,
                revid=2001,
                old_revid=2000,
                timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
                user="User2",
                userid=2,
                comment="Updated",
                oldlen=1000,
                newlen=1100,
            )
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert 200 in changeset.modified_page_ids
        assert len(changeset.new_page_ids) == 0

    def test_detects_deleted_pages(self, db):
        """Test detects deleted pages from recent changes."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=3,
                type="log",
                namespace=0,
                title="Deleted_Page",
                pageid=300,
                revid=0,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
                user="Admin",
                userid=1,
                comment="Spam",
                oldlen=0,
                newlen=0,
                log_type="delete",
                log_action="delete",
            )
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert 300 in changeset.deleted_page_ids
        assert len(changeset.new_page_ids) == 0
        assert len(changeset.modified_page_ids) == 0

    def test_detects_moved_pages(self, db):
        """Test detects moved/renamed pages."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=4,
                type="log",
                namespace=0,
                title="New_Title",
                pageid=400,
                revid=0,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
                user="Admin",
                userid=1,
                comment="moved Old_Title to New_Title",
                oldlen=0,
                newlen=0,
                log_type="move",
                log_action="move",
            )
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert len(changeset.moved_pages) == 1
        assert changeset.moved_pages[0].page_id == 400


class TestEdgeCases:
    """Tests for edge cases in change detection."""

    def test_deduplicates_multiple_edits_to_same_page(self, db):
        """Test same page edited multiple times appears once."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client with multiple edits to same page
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=5,
                type="edit",
                namespace=0,
                title="Page",
                pageid=500,
                revid=5001,
                old_revid=5000,
                timestamp=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
                user="User1",
                userid=1,
                comment="Edit 1",
                oldlen=1000,
                newlen=1100,
            ),
            RecentChange(
                rcid=6,
                type="edit",
                namespace=0,
                title="Page",
                pageid=500,
                revid=5002,
                old_revid=5001,
                timestamp=datetime(2026, 1, 3, 11, 0, tzinfo=timezone.utc),
                user="User2",
                userid=2,
                comment="Edit 2",
                oldlen=1100,
                newlen=1200,
            ),
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert len(changeset.modified_page_ids) == 1
        assert 500 in changeset.modified_page_ids

    def test_page_created_then_edited_only_in_new_pages(self, db):
        """Test page created then edited appears only in new_page_ids."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=7,
                type="new",
                namespace=0,
                title="Page",
                pageid=600,
                revid=6000,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
                user="User1",
                userid=1,
                comment="Created",
                oldlen=0,
                newlen=500,
            ),
            RecentChange(
                rcid=8,
                type="edit",
                namespace=0,
                title="Page",
                pageid=600,
                revid=6001,
                old_revid=6000,
                timestamp=datetime(2026, 1, 3, 11, 0, tzinfo=timezone.utc),
                user="User2",
                userid=2,
                comment="Fixed typo",
                oldlen=500,
                newlen=505,
            ),
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert 600 in changeset.new_page_ids
        assert 600 not in changeset.modified_page_ids

    def test_page_created_then_deleted_only_in_deleted_pages(self, db):
        """Test page created then deleted appears only in deleted_page_ids."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = [
            RecentChange(
                rcid=9,
                type="new",
                namespace=0,
                title="Temp_Page",
                pageid=700,
                revid=7000,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
                user="User1",
                userid=1,
                comment="Created",
                oldlen=0,
                newlen=500,
            ),
            RecentChange(
                rcid=10,
                type="log",
                namespace=0,
                title="Temp_Page",
                pageid=700,
                revid=0,
                old_revid=0,
                timestamp=datetime(2026, 1, 3, 11, 0, tzinfo=timezone.utc),
                user="Admin",
                userid=1,
                comment="Test page",
                oldlen=0,
                newlen=0,
                log_type="delete",
                log_action="delete",
            ),
        ]

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert 700 in changeset.deleted_page_ids
        assert 700 not in changeset.new_page_ids
        assert 700 not in changeset.modified_page_ids

    def test_handles_empty_recent_changes(self, db):
        """Test handles no changes since last scrape."""
        # Insert a scrape run
        db.get_connection().execute(
            "INSERT INTO scrape_runs (start_time, end_time, status) VALUES (?, ?, ?)",
            (
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "completed",
            ),
        )
        db.get_connection().commit()

        # Mock RC client with no changes
        mock_rc_client = Mock()
        mock_rc_client.get_recent_changes.return_value = []

        detector = ChangeDetector(db, mock_rc_client)
        changeset = detector.detect_changes()

        assert changeset.total_changes == 0
        assert changeset.requires_full_scrape is False


class TestChangeSetModel:
    """Tests for ChangeSet data model."""

    def test_total_changes_property(self):
        """Test total_changes calculates correctly."""
        changeset = ChangeSet(
            new_page_ids={1, 2, 3},
            modified_page_ids={4, 5},
            deleted_page_ids={6},
            moved_pages=[MovedPage(7, "Old", "New", 0, datetime.now(timezone.utc))],
        )

        assert changeset.total_changes == 7  # 3 + 2 + 1 + 1

    def test_has_changes_property(self):
        """Test has_changes property."""
        # With changes
        changeset1 = ChangeSet(new_page_ids={1, 2})
        assert changeset1.has_changes is True

        # With full scrape
        changeset2 = ChangeSet(requires_full_scrape=True)
        assert changeset2.has_changes is True

        # No changes
        changeset3 = ChangeSet()
        assert changeset3.has_changes is False

    def test_repr(self):
        """Test __repr__ includes key information."""
        changeset = ChangeSet(
            new_page_ids={1, 2},
            modified_page_ids={3},
            deleted_page_ids={4},
            moved_pages=[],
            requires_full_scrape=False,
        )

        repr_str = repr(changeset)
        assert "new=2" in repr_str
        assert "modified=1" in repr_str
        assert "deleted=1" in repr_str
        assert "moved=0" in repr_str
        assert "full_scrape=False" in repr_str
