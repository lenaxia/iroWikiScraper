"""
Tests for timeline and statistics query functions (Stories 12 & 13).

Tests cover:
- Timeline queries (get page at time, list pages, changes in range)
- Statistics queries (database stats, page stats, namespace stats)
- Contributor statistics
- Activity timeline
- Edge cases and NULL handling
"""

from datetime import datetime

import pytest

from scraper.storage.database import Database
from scraper.storage.queries import (  # Timeline functions; Statistics functions
    ActivityPoint,
    Change,
    ContributorStats,
    NamespaceStats,
    get_activity_timeline,
    get_changes_in_range,
    get_contributor_stats,
    get_db_stats,
    get_namespace_stats,
    get_page_at_time,
    get_page_history,
    get_page_stats,
    list_pages_at_time,
)


class TestTimelineQueries:
    """Test temporal query functions (Story 12)."""

    @pytest.fixture
    def timeline_db(self, db: Database):
        """Setup database with timeline data."""
        conn = db.get_connection()

        # Insert page
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'TestPage')"
        )

        # Insert revisions at different times
        revisions = [
            (
                1,
                1,
                None,
                "2024-01-01T10:00:00",
                "Alice",
                101,
                "Rev 1",
                "Version 1",
                9,
                "abc1",
                0,
                None,
            ),
            (
                2,
                1,
                1,
                "2024-01-02T11:00:00",
                "Bob",
                102,
                "Rev 2",
                "Version 2",
                9,
                "abc2",
                0,
                None,
            ),
            (
                3,
                1,
                2,
                "2024-01-03T12:00:00",
                "Charlie",
                103,
                "Rev 3",
                "Version 3",
                9,
                "abc3",
                0,
                None,
            ),
        ]

        for rev in revisions:
            conn.execute(
                """
                INSERT INTO revisions
                (revision_id, page_id, parent_id, timestamp, user, user_id, comment,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                rev,
            )

        conn.commit()
        return db

    def test_get_page_at_time(self, timeline_db: Database):
        """Test retrieving page at specific time."""
        conn = timeline_db.get_connection()

        # Get page as of 2024-01-01 (should get revision 1)
        rev = get_page_at_time(conn, 1, datetime(2024, 1, 1, 12, 0))
        assert rev is not None
        assert rev.content == "Version 1"

        # Get page as of 2024-01-02 (should get revision 2)
        rev = get_page_at_time(conn, 1, datetime(2024, 1, 2, 12, 0))
        assert rev is not None
        assert rev.content == "Version 2"

        # Get page before it existed (should be None)
        rev = get_page_at_time(conn, 1, datetime(2023, 12, 31))
        assert rev is None

    def test_list_pages_at_time(self, timeline_db: Database):
        """Test listing all pages at specific time."""
        conn = timeline_db.get_connection()

        pages = list_pages_at_time(conn, datetime(2024, 1, 2, 12, 0))

        assert len(pages) == 1
        page, revision = pages[0]
        assert page.title == "TestPage"
        assert revision.content == "Version 2"

    def test_get_changes_in_range(self, timeline_db: Database):
        """Test getting changes in date range."""
        conn = timeline_db.get_connection()

        changes = get_changes_in_range(
            conn, datetime(2024, 1, 1), datetime(2024, 1, 2, 23, 59)
        )

        assert len(changes) == 2  # Revisions 1 and 2
        assert changes[0].user == "Alice"
        assert changes[1].user == "Bob"

    def test_get_page_history(self, timeline_db: Database):
        """Test getting complete page history."""
        conn = timeline_db.get_connection()

        history = get_page_history(conn, 1)

        assert len(history) == 3
        # Should be in reverse chronological order
        assert history[0].content == "Version 3"
        assert history[1].content == "Version 2"
        assert history[2].content == "Version 1"

    def test_page_at_time_exact_timestamp(self, timeline_db: Database):
        """Test exact timestamp matching."""
        conn = timeline_db.get_connection()

        # Exact match should return that revision
        rev = get_page_at_time(conn, 1, datetime(2024, 1, 2, 11, 0, 0))
        assert rev is not None
        assert rev.revision_id == 2

    def test_list_pages_pagination(self, timeline_db: Database):
        """Test pagination in list_pages_at_time."""
        conn = timeline_db.get_connection()

        # Insert more pages
        for i in range(2, 6):
            conn.execute(
                f"INSERT INTO pages (page_id, namespace, title) VALUES ({i}, 0, 'Page{i}')"
            )
            # fmt: off
            conn.execute(
                """
                INSERT INTO revisions
                (revision_id, page_id, parent_id, timestamp, user, user_id, comment,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, NULL, '2024-01-01T10:00:00', 'User', 1, '', 'Content', 7, 'abc', 0, NULL)
            """,  # noqa: E501
                (i * 10, i),
            )
            # fmt: on
        conn.commit()

        # Test limit
        pages = list_pages_at_time(conn, datetime(2024, 1, 2), limit=2)
        assert len(pages) == 2

        # Test offset
        pages_offset = list_pages_at_time(conn, datetime(2024, 1, 2), limit=2, offset=2)
        assert len(pages_offset) == 2
        # Should be different pages
        assert pages[0][0].page_id != pages_offset[0][0].page_id

    def test_changes_size_delta(self, timeline_db: Database):
        """Test size delta calculation in changes."""
        conn = timeline_db.get_connection()

        changes = get_changes_in_range(
            conn, datetime(2024, 1, 1), datetime(2024, 1, 3, 23, 59)
        )

        # First revision should have size_delta == size (no previous revision)
        assert changes[0].size_delta == 9

        # Subsequent revisions have delta = 0 (same size)
        for change in changes[1:]:
            assert change.size_delta == 0


class TestStatisticsQueries:
    """Test statistics query functions (Story 13)."""

    @pytest.fixture
    def stats_db(self, db: Database):
        """Setup database with statistical data."""
        conn = db.get_connection()

        # Insert pages in different namespaces
        for i in range(1, 11):
            namespace = 0 if i <= 5 else 1
            # fmt: off
            conn.execute(
                f"INSERT INTO pages (page_id, namespace, title) VALUES ({i}, {namespace}, 'Page{i}')"  # noqa: E501
            )
            # fmt: on

        # Insert revisions with varied data
        for page_id in range(1, 11):
            for rev_num in range(3):
                conn.execute(
                    """
                    INSERT INTO revisions
                    (revision_id, page_id, parent_id, timestamp, user, user_id, comment,
                     content, size, sha1, minor, tags)
                    VALUES (?, ?, NULL, ?, ?, ?, '', 'Content', ?, 'abc', 0, NULL)
                """,
                    (
                        page_id * 100 + rev_num,
                        page_id,
                        datetime(2024, 1, 1 + rev_num).isoformat(),
                        f"User{page_id % 3}",
                        page_id % 3,
                        50 + rev_num * 10,
                    ),
                )

        conn.commit()
        return db

    def test_get_db_stats(self, stats_db: Database):
        """Test overall database statistics."""
        conn = stats_db.get_connection()

        stats = get_db_stats(conn)

        assert stats["total_pages"] == 10
        assert stats["total_revisions"] == 30  # 10 pages × 3 revisions
        assert stats["total_files"] == 0
        assert stats["total_links"] == 0
        assert stats["avg_content_size"] > 0
        assert stats["first_edit"] is not None
        assert stats["last_edit"] is not None
        assert stats["db_size_mb"] >= 0  # May be 0 for temp/in-memory databases

    def test_get_db_stats_empty_database(self, db: Database):
        """Test stats on empty database."""
        conn = db.get_connection()

        stats = get_db_stats(conn)

        assert stats["total_pages"] == 0
        assert stats["total_revisions"] == 0
        assert stats["first_edit"] is None
        assert stats["last_edit"] is None

    def test_get_page_stats(self, stats_db: Database):
        """Test per-page statistics."""
        conn = stats_db.get_connection()

        stats = get_page_stats(conn, 1)

        assert stats["revision_count"] == 3
        assert stats["contributor_count"] == 1  # All by User1
        assert stats["first_edit"] is not None
        assert stats["last_edit"] is not None
        assert stats["avg_edit_size"] > 0
        assert stats["total_size"] > 0

    def test_get_page_stats_nonexistent_page(self, stats_db: Database):
        """Test stats for nonexistent page."""
        conn = stats_db.get_connection()

        stats = get_page_stats(conn, 999)

        assert stats["revision_count"] == 0
        assert stats["contributor_count"] == 0
        assert stats["first_edit"] is None

    def test_get_namespace_stats(self, stats_db: Database):
        """Test namespace statistics."""
        conn = stats_db.get_connection()

        stats = get_namespace_stats(conn)

        # Should have stats for namespace 0 and 1
        assert 0 in stats
        assert 1 in stats

        ns0 = stats[0]
        assert ns0.namespace == 0
        assert ns0.page_count == 5
        assert ns0.revision_count == 15  # 5 pages × 3 revisions
        assert ns0.total_size > 0

        ns1 = stats[1]
        assert ns1.namespace == 1
        assert ns1.page_count == 5
        assert ns1.revision_count == 15

    def test_get_contributor_stats(self, stats_db: Database):
        """Test contributor statistics."""
        conn = stats_db.get_connection()

        contributors = get_contributor_stats(conn, top_n=3)

        # Should have 3 contributors (User0, User1, User2)
        assert len(contributors) == 3

        for contrib in contributors:
            assert isinstance(contrib, ContributorStats)
            assert contrib.user.startswith("User")
            assert contrib.edit_count > 0
            assert contrib.total_bytes > 0
            assert contrib.first_edit is not None
            assert contrib.last_edit is not None

    def test_get_activity_timeline_day(self, stats_db: Database):
        """Test activity timeline by day."""
        conn = stats_db.get_connection()

        timeline = get_activity_timeline(conn, granularity="day")

        # Should have 3 days of activity
        assert len(timeline) == 3

        for point in timeline:
            assert isinstance(point, ActivityPoint)
            assert point.edit_count > 0
            assert point.contributor_count > 0

    def test_get_activity_timeline_month(self, stats_db: Database):
        """Test activity timeline by month."""
        conn = stats_db.get_connection()

        timeline = get_activity_timeline(conn, granularity="month")

        # All edits in same month
        assert len(timeline) == 1
        assert timeline[0].edit_count == 30  # All revisions


class TestDataClasses:
    """Test query result data classes."""

    def test_change_dataclass(self):
        """Test Change dataclass."""
        change = Change(
            page_id=1,
            page_title="Test",
            revision_id=100,
            timestamp=datetime(2024, 1, 1),
            user="Alice",
            comment="Test edit",
            size_delta=50,
        )

        assert change.page_id == 1
        assert change.page_title == "Test"
        assert change.size_delta == 50
        # Frozen dataclass
        with pytest.raises(AttributeError):
            change.page_id = 2

    def test_namespace_stats_dataclass(self):
        """Test NamespaceStats dataclass."""
        stats = NamespaceStats(
            namespace=0, page_count=100, revision_count=1000, total_size=50000
        )

        assert stats.namespace == 0
        assert stats.page_count == 100

    def test_contributor_stats_dataclass(self):
        """Test ContributorStats dataclass."""
        stats = ContributorStats(
            user="Alice",
            edit_count=100,
            total_bytes=5000,
            first_edit=datetime(2024, 1, 1),
            last_edit=datetime(2024, 1, 31),
        )

        assert stats.user == "Alice"
        assert stats.edit_count == 100

    def test_activity_point_dataclass(self):
        """Test ActivityPoint dataclass."""
        point = ActivityPoint(
            timestamp=datetime(2024, 1, 1), edit_count=50, contributor_count=5
        )

        assert point.edit_count == 50
        assert point.contributor_count == 5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_timeline_query_with_no_pages(self, db: Database):
        """Test timeline query on empty database."""
        conn = db.get_connection()

        pages = list_pages_at_time(conn, datetime(2024, 1, 1))
        assert len(pages) == 0

    def test_changes_in_empty_range(self, db: Database):
        """Test changes query with no results."""
        conn = db.get_connection()

        changes = get_changes_in_range(conn, datetime(2024, 1, 1), datetime(2024, 1, 2))
        assert len(changes) == 0

    def test_namespace_stats_with_no_revisions(self, db: Database):
        """Test namespace stats when pages have no revisions."""
        conn = db.get_connection()

        # Insert page without revisions
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Empty')"
        )
        conn.commit()

        stats = get_namespace_stats(conn)

        assert 0 in stats
        assert stats[0].page_count == 1
        assert stats[0].revision_count == 0
        assert stats[0].total_size == 0

    def test_contributor_stats_with_empty_users(self, db: Database):
        """Test contributor stats filters empty usernames."""
        conn = db.get_connection()

        # Insert page and revision with empty user
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')"
        )
        conn.execute("""
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id, comment,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, '2024-01-01T10:00:00', '', NULL, '', 'Content', 7, 'abc', 0, NULL)
        """)
        conn.commit()

        contributors = get_contributor_stats(conn)

        # Empty user should be filtered out
        assert len(contributors) == 0
