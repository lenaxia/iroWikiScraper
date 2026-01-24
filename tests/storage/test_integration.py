"""
Integration tests for Epic 02 database storage (Story 15).

These tests validate complete workflows with realistic data volumes:
- Complete scrape workflow
- Incremental update simulation
- Full-text search integration
- Timeline queries integration
- Performance benchmarks
- Foreign key enforcement
"""

import pytest
import time
from datetime import datetime, timedelta
from scraper.storage.database import Database
from scraper.storage.models import Page, Revision, FileMetadata, Link
from scraper.storage.search import search, rebuild_index
from scraper.storage.queries import (
    get_page_at_time,
    get_changes_in_range,
    get_db_stats,
    get_namespace_stats,
)


class TestCompleteScrapeWorkflow:
    """Test complete scrape workflow (Story 15)."""

    def test_complete_workflow(self, db: Database):
        """Test discover → store → query workflow."""
        conn = db.get_connection()

        # Step 1: Discover and store pages
        pages = [
            Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(1, 101)
        ]

        for page in pages:
            conn.execute(
                """
                INSERT INTO pages (page_id, namespace, title, is_redirect)
                VALUES (?, ?, ?, ?)
            """,
                page.to_db_params(),
            )

        conn.commit()

        # Verify pages stored
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        assert cursor.fetchone()[0] == 100

        # Step 2: Store revisions (10 per page)
        for page_id in range(1, 101):
            for rev_num in range(10):
                revision = Revision(
                    revision_id=page_id * 1000 + rev_num,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime.now() - timedelta(days=10 - rev_num),
                    user=f"User{rev_num}",
                    user_id=rev_num + 1 + 1,
                    comment=f"Edit {rev_num}",
                    content=f"Content for page {page_id} rev {rev_num}",
                    size=50,
                    sha1=f"sha{page_id}{rev_num}",
                    minor=False,
                    tags=None,
                )

                conn.execute(
                    """
                    INSERT INTO revisions 
                    (revision_id, page_id, parent_id, timestamp, user, user_id,
                     comment, content, size, sha1, minor, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    revision.to_db_params(),
                )

        conn.commit()

        # Verify revisions stored
        cursor = conn.execute("SELECT COUNT(*) FROM revisions")
        assert cursor.fetchone()[0] == 1000  # 100 pages × 10 revisions

        # Step 3: Query and verify
        cursor = conn.execute("""
            SELECT * FROM revisions 
            WHERE page_id = 1 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        latest = Revision.from_db_row(cursor.fetchone())
        assert latest is not None
        assert latest.page_id == 1


class TestIncrementalUpdate:
    """Test incremental update workflow."""

    def test_incremental_update(self, db: Database):
        """Test initial scrape + incremental update."""
        conn = db.get_connection()

        # Initial scrape: 10 pages with 5 revisions each
        for i in range(1, 11):
            page = Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            conn.execute(
                """
                INSERT INTO pages (page_id, namespace, title, is_redirect)
                VALUES (?, ?, ?, ?)
            """,
                page.to_db_params(),
            )

            for rev_num in range(5):
                revision = Revision(
                    revision_id=i * 100 + rev_num,
                    page_id=i,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 1) + timedelta(days=rev_num),
                    user=f"User{rev_num}",
                    user_id=rev_num + 1 + 1,
                    comment=f"Initial edit {rev_num}",
                    content=f"Initial content {rev_num}",
                    size=20,
                    sha1=f"initial{i}{rev_num}",
                    minor=False,
                    tags=None,
                )

                conn.execute(
                    """
                    INSERT INTO revisions 
                    (revision_id, page_id, parent_id, timestamp, user, user_id,
                     comment, content, size, sha1, minor, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    revision.to_db_params(),
                )

        conn.commit()

        initial_count = conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
        assert initial_count == 50

        # Simulate new edits (3 new revisions on page 1)
        for rev_num in range(5, 8):
            revision = Revision(
                revision_id=100 + rev_num,
                page_id=1,
                parent_id=100 + rev_num - 1,
                timestamp=datetime(2024, 1, 10) + timedelta(days=rev_num),
                user=f"User{rev_num}",
                user_id=rev_num + 1 + 1,
                comment=f"New edit {rev_num}",
                content=f"New content {rev_num}",
                size=20,
                sha1=f"new{rev_num}",
                minor=False,
                tags=None,
            )

            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                revision.to_db_params(),
            )

        conn.commit()

        # Verify only new revisions added
        final_count = conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
        assert final_count == 53  # 50 + 3

        # Verify page 1 now has 8 revisions
        page1_count = conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE page_id = 1"
        ).fetchone()[0]
        assert page1_count == 8


class TestSearchIntegration:
    """Test full-text search integration."""

    def test_search_workflow(self, db: Database):
        """Test FTS5 search on real data."""
        conn = db.get_connection()

        # Create pages with searchable content
        pages = [
            Page(page_id=1, namespace=0, title="Prontera", is_redirect=False),
            Page(page_id=2, namespace=0, title="Geffen", is_redirect=False),
            Page(page_id=3, namespace=0, title="Payon", is_redirect=False),
        ]

        for page in pages:
            conn.execute(
                """
                INSERT INTO pages (page_id, namespace, title, is_redirect)
                VALUES (?, ?, ?, ?)
            """,
                page.to_db_params(),
            )

        # Add content
        revisions = [
            Revision(
                revision_id=1,
                page_id=1,
                parent_id=None,
                timestamp=datetime.now(),
                user="User1",
                user_id=1,
                comment="",
                content="Prontera is the capital city of Rune-Midgarts Kingdom",
                size=55,
                sha1="abc1",
                minor=False,
                tags=None,
            ),
            Revision(
                revision_id=2,
                page_id=2,
                parent_id=None,
                timestamp=datetime.now(),
                user="User2",
                user_id=2,
                comment="",
                content="Geffen is the magical city of wizards",
                size=40,
                sha1="abc2",
                minor=False,
                tags=None,
            ),
            Revision(
                revision_id=3,
                page_id=3,
                parent_id=None,
                timestamp=datetime.now(),
                user="User3",
                user_id=3,
                comment="",
                content="Payon is a village in the mountains",
                size=36,
                sha1="abc3",
                minor=False,
                tags=None,
            ),
        ]

        for rev in revisions:
            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                rev.to_db_params(),
            )

        conn.commit()

        # Rebuild FTS index
        rebuild_index(conn)

        # Search for "capital"
        results = search(conn, "capital")
        assert len(results) >= 1
        assert results[0].title == "Prontera"

        # Search for "city"
        results = search(conn, "city")
        assert len(results) >= 2


class TestTimelineIntegration:
    """Test temporal query integration."""

    def test_timeline_queries(self, db: Database):
        """Test timeline queries on realistic data."""
        conn = db.get_connection()

        # Create page
        page = Page(page_id=1, namespace=0, title="TestPage", is_redirect=False)
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page.to_db_params(),
        )

        # Create revisions at different times
        for i in range(1, 11):
            revision = Revision(
                revision_id=i,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, i),
                user=f"User{i}",
                user_id=i,
                comment="",
                content=f"Version {i}",
                size=10,
                sha1=f"sha{i}",
                minor=False,
                tags=None,
            )

            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                revision.to_db_params(),
            )

        conn.commit()

        # Test get page at time
        rev_at_time = get_page_at_time(conn, 1, datetime(2024, 1, 5))
        assert rev_at_time is not None
        assert rev_at_time.content == "Version 5"

        # Test get changes in range
        changes = get_changes_in_range(conn, datetime(2024, 1, 1), datetime(2024, 1, 5))
        assert len(changes) == 5


class TestPerformanceBenchmarks:
    """Test performance with realistic data volumes."""

    def test_bulk_insert_performance(self, db: Database):
        """Test performance of bulk inserts."""
        conn = db.get_connection()

        # Benchmark: Insert 500 pages
        start = time.time()

        for i in range(1, 501):
            page = Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            conn.execute(
                """
                INSERT INTO pages (page_id, namespace, title, is_redirect)
                VALUES (?, ?, ?, ?)
            """,
                page.to_db_params(),
            )

        conn.commit()
        duration = time.time() - start

        # Should complete in reasonable time
        assert duration < 2.0, f"Page insert took {duration}s, expected < 2s"

        # Verify count
        count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        assert count == 500

    def test_query_performance(self, db: Database):
        """Test query performance on moderate dataset."""
        conn = db.get_connection()

        # Insert test data
        for i in range(1, 101):
            page = Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            conn.execute(
                """
                INSERT INTO pages (page_id, namespace, title, is_redirect)
                VALUES (?, ?, ?, ?)
            """,
                page.to_db_params(),
            )

            revision = Revision(
                revision_id=i,
                page_id=i,
                parent_id=None,
                timestamp=datetime.now(),
                user="User",
                user_id=1,
                comment="",
                content=f"Content {i}",
                size=10,
                sha1=f"sha{i}",
                minor=False,
                tags=None,
            )

            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                revision.to_db_params(),
            )

        conn.commit()

        # Benchmark: Get database stats
        start = time.time()
        stats = get_db_stats(conn)
        duration = time.time() - start

        assert duration < 0.1, f"Stats query took {duration}s, expected < 0.1s"
        assert stats["total_pages"] == 100


class TestForeignKeyEnforcement:
    """Test foreign key constraints."""

    def test_fk_prevents_orphaned_revisions(self, db: Database):
        """Test FK prevents revisions for non-existent pages."""
        conn = db.get_connection()

        # Try to insert revision for non-existent page
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            revision = Revision(
                revision_id=1,
                page_id=999,  # Does not exist
                parent_id=None,
                timestamp=datetime.now(),
                user="User",
                user_id=1,
                comment="",
                content="Test",
                size=4,
                sha1="abc",
                minor=False,
                tags=None,
            )

            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                revision.to_db_params(),
            )
            conn.commit()

    def test_cascade_delete_removes_revisions(self, db: Database):
        """Test CASCADE DELETE removes related records."""
        conn = db.get_connection()

        # Create page with revisions
        page = Page(page_id=1, namespace=0, title="TestPage", is_redirect=False)
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page.to_db_params(),
        )

        for i in range(1, 6):
            revision = Revision(
                revision_id=i,
                page_id=1,
                parent_id=None,
                timestamp=datetime.now(),
                user="User1",
                user_id=1,
                comment="",
                content=f"Rev {i}",
                size=5,
                sha1=f"sha{i}",
                minor=False,
                tags=None,
            )

            conn.execute(
                """
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 comment, content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                revision.to_db_params(),
            )

        conn.commit()

        # Verify revisions exist
        count = conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE page_id = 1"
        ).fetchone()[0]
        assert count == 5

        # Delete page
        conn.execute("DELETE FROM pages WHERE page_id = 1")
        conn.commit()

        # Verify revisions deleted
        count = conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE page_id = 1"
        ).fetchone()[0]
        assert count == 0


class TestCrossComponentIntegration:
    """Test multiple components working together."""

    def test_pages_revisions_fts_integration(self, db: Database):
        """Test Pages + Revisions + FTS5 all working together."""
        conn = db.get_connection()

        # Insert page
        page = Page(page_id=1, namespace=0, title="Integration Test", is_redirect=False)
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page.to_db_params(),
        )

        # Insert revision (should trigger FTS update)
        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime.now(),
            user="User",
            user_id=1,
            comment="",
            content="This page tests integration across all components",
            size=50,
            sha1="abc123",
            minor=False,
            tags=None,
        )

        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            revision.to_db_params(),
        )
        conn.commit()

        # Verify searchable
        results = search(conn, "integration")
        assert len(results) >= 1
        assert results[0].page_id == 1

        # Verify stats
        stats = get_db_stats(conn)
        assert stats["total_pages"] == 1
        assert stats["total_revisions"] == 1

        # Verify namespace stats
        ns_stats = get_namespace_stats(conn)
        assert 0 in ns_stats
        assert ns_stats[0].page_count == 1
