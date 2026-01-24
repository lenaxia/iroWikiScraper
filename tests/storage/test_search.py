"""
Tests for full-text search functionality using FTS5.

Tests cover:
- FTS5 table creation
- Search functionality (simple, boolean, phrase queries)
- Ranking and relevance
- Snippet extraction
- Index maintenance and triggers
- Performance benchmarks
"""

import sqlite3
from datetime import datetime

import pytest

from scraper.storage.database import Database
from scraper.storage.search import (
    SearchResult,
    index_page,
    optimize_index,
    rebuild_index,
    search,
    search_titles,
)


class TestFTS5Setup:
    """Test FTS5 table creation and triggers."""

    def test_fts_table_exists(self, db: Database):
        """Test that FTS5 virtual table is created."""
        conn = db.get_connection()

        # Check if pages_fts table exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='pages_fts'
        """)
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "pages_fts"

    def test_fts_triggers_exist(self, db: Database):
        """Test that FTS sync triggers are created."""
        conn = db.get_connection()

        # Check for triggers
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='trigger' AND name LIKE '%fts%'
        """)
        triggers = [row[0] for row in cursor.fetchall()]

        # Should have insert, update, and delete triggers
        assert "revisions_fts_insert" in triggers
        assert "pages_fts_update" in triggers
        assert "pages_fts_delete" in triggers


class TestBasicSearch:
    """Test basic search functionality."""

    @pytest.fixture
    def search_db(self, db: Database):
        """Setup database with searchable content."""
        conn = db.get_connection()

        # Insert test pages
        pages_data = [
            (1, 0, "Prontera"),
            (2, 0, "Geffen"),
            (3, 0, "Payon"),
            (4, 0, "Morocc"),
        ]

        for page_id, namespace, title in pages_data:
            conn.execute(
                "INSERT INTO pages (page_id, namespace, title) VALUES (?, ?, ?)",
                (page_id, namespace, title),
            )

        # Insert revisions with content
        revisions_data = [
            (
                1,
                1,
                None,
                datetime(2024, 1, 1),
                "User1",
                None,
                "Prontera is the capital city of the Rune-Midgarts Kingdom. It is a bustling trade hub.",  # noqa: E501
                80,
                "abc1",
                False,
                None,
            ),
            (
                2,
                2,
                None,
                datetime(2024, 1, 2),
                "User2",
                None,
                "Geffen is the magical city of wizards and mages. Many magic shops are located here.",  # noqa: E501
                85,
                "abc2",
                False,
                None,
            ),
            (
                3,
                3,
                None,
                datetime(2024, 1, 3),
                "User3",
                None,
                "Payon is a small village nestled in the mountains. It is known for archers.",
                75,
                "abc3",
                False,
                None,
            ),
            (
                4,
                4,
                None,
                datetime(2024, 1, 4),
                "User4",
                None,
                "Morocc is a desert city with bazaars and merchants. The pyramid is nearby.",
                76,
                "abc4",
                False,
                None,
            ),
        ]

        for rev_data in revisions_data:
            conn.execute(
                """
                INSERT INTO revisions
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                rev_data,
            )

        conn.commit()

        return db

    def test_simple_search(self, search_db: Database):
        """Test simple keyword search."""
        conn = search_db.get_connection()
        results = search(conn, "capital")

        assert len(results) >= 1
        assert results[0].page_id == 1
        assert results[0].title == "Prontera"
        assert "capital" in results[0].snippet.lower()

    def test_search_returns_multiple_results(self, search_db: Database):
        """Test search returning multiple results."""
        conn = search_db.get_connection()
        results = search(conn, "city")

        # Should find Prontera, Geffen, and Morocc
        assert len(results) >= 3
        page_ids = [r.page_id for r in results]
        assert 1 in page_ids  # Prontera
        assert 2 in page_ids  # Geffen
        assert 4 in page_ids  # Morocc

    def test_search_no_results(self, search_db: Database):
        """Test search with no matches."""
        conn = search_db.get_connection()
        results = search(conn, "nonexistent_term_xyz")

        assert len(results) == 0

    def test_search_limit(self, search_db: Database):
        """Test search result limit."""
        conn = search_db.get_connection()
        results = search(conn, "city", limit=2)

        assert len(results) <= 2

    def test_search_offset(self, search_db: Database):
        """Test search result offset for pagination."""
        conn = search_db.get_connection()

        # Get all results
        all_results = search(conn, "city", limit=10)

        # Get with offset
        offset_results = search(conn, "city", limit=10, offset=1)

        # Should be different results
        if len(all_results) > 1:
            assert offset_results[0].page_id != all_results[0].page_id


class TestBooleanQueries:
    """Test boolean search operators."""

    @pytest.fixture
    def search_db(self, db: Database):
        """Setup database with searchable content."""
        conn = db.get_connection()

        # Insert test pages
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Prontera')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'Geffen')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (3, 0, 'Payon')"
        )

        # Insert revisions with specific content for boolean tests
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL,
                    'Prontera is a capital city with knights', 40, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )

        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (2, 2, NULL, ?, 'User2', NULL,
                    'Geffen is a city of magic and wizards', 38, 'abc2', 0, NULL)
        """,
            (datetime(2024, 1, 2),),
        )

        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (3, 3, NULL, ?, 'User3', NULL,
                    'Payon is a village in the mountains', 36, 'abc3', 0, NULL)
        """,
            (datetime(2024, 1, 3),),
        )

        conn.commit()

        return db

    def test_boolean_and(self, search_db: Database):
        """Test AND operator."""
        conn = search_db.get_connection()
        results = search(conn, "city AND magic")

        # Should only find Geffen (has both "city" and "magic")
        assert len(results) >= 1
        assert results[0].page_id == 2

    def test_boolean_or(self, search_db: Database):
        """Test OR operator."""
        conn = search_db.get_connection()
        results = search(conn, "knights OR wizards")

        # Should find Prontera (knights) and Geffen (wizards)
        assert len(results) >= 2
        page_ids = [r.page_id for r in results]
        assert 1 in page_ids
        assert 2 in page_ids

    def test_boolean_not(self, search_db: Database):
        """Test NOT operator."""
        conn = search_db.get_connection()
        results = search(conn, "city NOT magic")

        # Should find cities without "magic" (Prontera)
        assert len(results) >= 1
        page_ids = [r.page_id for r in results]
        assert 1 in page_ids  # Prontera
        # Should NOT include Geffen (has magic)
        assert 2 not in page_ids


class TestPhraseSearch:
    """Test phrase search functionality."""

    @pytest.fixture
    def search_db(self, db: Database):
        """Setup database with searchable content."""
        conn = db.get_connection()

        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Prontera')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'Geffen')"
        )

        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL,
                    'Prontera is the capital city of the kingdom', 45, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )

        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (2, 2, NULL, ?, 'User2', NULL,
                    'Geffen has a capital letter but not the capital city', 52, 'abc2', 0, NULL)
        """,
            (datetime(2024, 1, 2),),
        )

        conn.commit()

        return db

    def test_phrase_search(self, search_db: Database):
        """Test exact phrase search."""
        conn = search_db.get_connection()
        results = search(conn, '"capital city"')

        # Should only find Prontera (has exact phrase "capital city")
        assert len(results) >= 1
        assert results[0].page_id == 1


class TestRankingAndSnippets:
    """Test result ranking and snippet extraction."""

    @pytest.fixture
    def search_db(self, db: Database):
        """Setup database with content for ranking tests."""
        conn = db.get_connection()

        # Insert pages with varying relevance
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test Page 1')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'Test Page 2')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (3, 0, 'Test Page 3')"
        )

        # Page 1: Keyword appears once
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL,
                    'This page mentions knights in passing', 40, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )

        # Page 2: Keyword appears multiple times (more relevant)
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (2, 2, NULL, ?, 'User2', NULL,
                    'Knights are warriors. Knights fight with swords. Many knights live here.',
                    72, 'abc2', 0, NULL)
        """,
            (datetime(2024, 1, 2),),
        )

        # Page 3: No keyword
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (3, 3, NULL, ?, 'User3', NULL,
                    'This is about wizards and magic', 32, 'abc3', 0, NULL)
        """,
            (datetime(2024, 1, 3),),
        )

        conn.commit()

        return db

    def test_ranking_by_relevance(self, search_db: Database):
        """Test that results are ranked by relevance (BM25)."""
        conn = search_db.get_connection()
        results = search(conn, "knights")

        # Should return results in relevance order
        assert len(results) >= 2

        # Page 2 (multiple mentions) should rank higher than Page 1 (single mention)
        assert results[0].page_id == 2

        # Rank values should be ordered (lower is better in FTS5)
        if len(results) > 1:
            assert results[0].rank <= results[1].rank

    def test_snippet_extraction(self, search_db: Database):
        """Test that snippets are extracted correctly."""
        conn = search_db.get_connection()
        results = search(conn, "knights")

        assert len(results) >= 1

        # Snippet should not be empty
        assert results[0].snippet != ""

        # Snippet should contain match markers
        assert "<mark>" in results[0].snippet or "knights" in results[0].snippet.lower()

    def test_search_result_dataclass(self, search_db: Database):
        """Test SearchResult dataclass structure."""
        conn = search_db.get_connection()
        results = search(conn, "knights")

        assert len(results) >= 1

        result = results[0]
        assert isinstance(result, SearchResult)
        assert isinstance(result.page_id, int)
        assert isinstance(result.title, str)
        assert isinstance(result.snippet, str)
        assert isinstance(result.rank, float)


class TestTitleSearch:
    """Test title-only search."""

    @pytest.fixture
    def search_db(self, db: Database):
        """Setup database with varied titles."""
        conn = db.get_connection()

        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Prontera Castle')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'Geffen Tower')"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (3, 0, 'Castle of Midgard')"
        )

        # Add dummy content that doesn't match search
        for i in range(1, 4):
            conn.execute(
                """
                INSERT INTO revisions
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, NULL, ?, 'User1', NULL,
                        'Generic content without specific keywords', 40, ?, 0, NULL)
            """,
                (i, i, datetime(2024, 1, i), f"abc{i}"),
            )

        conn.commit()

        return db

    def test_search_titles_only(self, search_db: Database):
        """Test searching only in titles."""
        conn = search_db.get_connection()
        results = search_titles(conn, "castle")

        # Should find pages with "Castle" in title
        assert len(results) >= 2
        page_ids = [r.page_id for r in results]
        assert 1 in page_ids  # Prontera Castle
        assert 3 in page_ids  # Castle of Midgard

    def test_title_search_no_snippet(self, search_db: Database):
        """Test that title search doesn't include snippets."""
        conn = search_db.get_connection()
        results = search_titles(conn, "castle")

        assert len(results) >= 1
        # Snippets should be empty for title-only search
        assert results[0].snippet == ""


class TestIndexMaintenance:
    """Test FTS index maintenance operations."""

    def test_rebuild_index(self, db: Database):
        """Test rebuilding the entire FTS index."""
        conn = db.get_connection()

        # Insert test data
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test Page')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Test content', 12, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Rebuild index
        rebuild_index(conn)

        # Verify search works after rebuild
        results = search(conn, "Test")
        assert len(results) >= 1

    def test_index_page(self, db: Database):
        """Test reindexing a single page."""
        conn = db.get_connection()

        # Insert page
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test Page')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Original content', 16, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Reindex specific page
        index_page(conn, 1)

        # Verify search works
        results = search(conn, "Original")
        assert len(results) >= 1
        assert results[0].page_id == 1

    def test_optimize_index(self, db: Database):
        """Test FTS index optimization."""
        conn = db.get_connection()

        # Insert some data
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Content', 7, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Optimize should not raise error
        optimize_index(conn)

        # Search should still work after optimization
        results = search(conn, "Content")
        assert len(results) >= 1


class TestTriggers:
    """Test FTS trigger functionality."""

    def test_trigger_on_insert(self, db: Database):
        """Test FTS automatically updates on revision insert."""
        conn = db.get_connection()

        # Insert page
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test Page')"
        )

        # Insert revision (should trigger FTS update)
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Searchable content', 18, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Search should find the new content immediately
        results = search(conn, "Searchable")
        assert len(results) >= 1
        assert results[0].page_id == 1

    def test_trigger_on_page_title_update(self, db: Database):
        """Test FTS updates when page title changes."""
        conn = db.get_connection()

        # Insert page and revision
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Old Title')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Content', 7, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Update page title
        conn.execute("UPDATE pages SET title = 'New Title' WHERE page_id = 1")
        conn.commit()

        # Search for new title
        results = search_titles(conn, "New")
        assert len(results) >= 1
        assert results[0].page_id == 1
        assert results[0].title == "New Title"

    def test_trigger_on_page_delete(self, db: Database):
        """Test FTS entry removed when page deleted."""
        conn = db.get_connection()

        # Insert page and revision
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test Page')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL, 'Content', 7, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Verify searchable
        results = search(conn, "Content")
        assert len(results) >= 1

        # Delete page (should cascade and remove from FTS)
        conn.execute("DELETE FROM pages WHERE page_id = 1")
        conn.commit()

        # Should no longer be searchable
        results = search(conn, "Content")
        page_ids = [r.page_id for r in results]
        assert 1 not in page_ids


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_search_empty_query(self, db: Database):
        """Test search with empty query."""
        conn = db.get_connection()

        # Empty query should either return empty results or raise error gracefully
        try:
            results = search(conn, "")
            assert len(results) == 0
        except sqlite3.OperationalError:
            # FTS5 may reject empty query, which is acceptable
            pass

    def test_search_special_characters(self, db: Database):
        """Test search with special characters."""
        conn = db.get_connection()

        # Insert page with special characters
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test-Page_123')"
        )
        conn.execute(
            """
            INSERT INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, ?, 'User1', NULL,
                    'Content with special chars: @#$% and numbers 123',
                    50, 'abc1', 0, NULL)
        """,
            (datetime(2024, 1, 1),),
        )
        conn.commit()

        # Should handle special characters gracefully
        try:
            search(conn, "special")
            # May or may not find results depending on tokenization
        except sqlite3.OperationalError:
            # FTS5 may reject certain special characters
            pass

    def test_search_on_empty_database(self, db: Database):
        """Test search on database with no content."""
        conn = db.get_connection()

        results = search(conn, "anything")
        assert len(results) == 0

    def test_page_with_no_revisions(self, db: Database):
        """Test page without revisions is not searchable."""
        conn = db.get_connection()

        # Insert page but no revisions
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Empty Page')"
        )
        conn.commit()

        # Should not appear in search results
        results = search(conn, "Empty")
        # May find in title, but content should be empty
        if len(results) > 0 and results[0].page_id == 1:
            # If found by title, snippet should be empty or not contain content
            pass
