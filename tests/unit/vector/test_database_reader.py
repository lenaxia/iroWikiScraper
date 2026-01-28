"""
Unit tests for DatabaseReader class

Tests database querying, filtering, and iteration.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from vectorize_wiki import DatabaseReader


class TestDatabaseReader:
    """Test DatabaseReader class"""

    def test_count_pages_default_namespace(self, test_database):
        """Test counting pages in default namespace (0)"""
        with DatabaseReader(str(test_database)) as db:
            count = db.count_pages()

            # Should count only namespace 0 pages that aren't redirects
            # Main_Page, Poring, Izlude, Empty_Page (not Redirect_Page)
            assert count == 4

    def test_count_pages_multiple_namespaces(self, test_database):
        """Test counting pages in multiple namespaces"""
        with DatabaseReader(str(test_database), namespaces=[0, 10]) as db:
            count = db.count_pages()

            # Should include namespace 0 and 10 (Template)
            # 4 from namespace 0 + 1 from namespace 10
            assert count == 5

    def test_count_pages_single_namespace(self, test_database):
        """Test counting pages in single specific namespace"""
        with DatabaseReader(str(test_database), namespaces=[10]) as db:
            count = db.count_pages()

            # Only Template:Infobox
            assert count == 1

    def test_iter_pages_default(self, test_database):
        """Test iterating pages with default settings"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            # Should have 3 pages (excluding redirects and empty)
            # Main_Page, Poring, Izlude (Empty_Page has no content)
            assert len(pages) == 3

            # Check structure
            for page in pages:
                assert "page_id" in page
                assert "page_title" in page
                assert "namespace" in page
                assert "revision_id" in page
                assert "content" in page
                assert "metadata" in page

    def test_iter_pages_excludes_redirects(self, test_database):
        """Test that redirects are excluded"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())
            page_titles = [p["page_title"] for p in pages]

            # Redirect_Page should not be included
            assert "Redirect_Page" not in page_titles

    def test_iter_pages_excludes_empty_content(self, test_database):
        """Test that pages with empty content are excluded"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())
            page_titles = [p["page_title"] for p in pages]

            # Empty_Page should not be included
            assert "Empty_Page" not in page_titles

    def test_iter_pages_content(self, test_database):
        """Test that actual content is retrieved"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            # Find Poring page
            poring = [p for p in pages if p["page_title"] == "Poring"][0]

            # Check content
            assert "Poring" in poring["content"]
            assert "monster" in poring["content"]
            assert len(poring["content"]) > 0

    def test_iter_pages_metadata(self, test_database):
        """Test that metadata is included"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            for page in pages:
                assert "timestamp" in page["metadata"]
                assert "contributor" in page["metadata"]
                assert "is_redirect" in page["metadata"]

    def test_iter_pages_ordered_by_page_id(self, test_database):
        """Test that pages are returned in page_id order"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())
            page_ids = [p["page_id"] for p in pages]

            # Should be in ascending order
            assert page_ids == sorted(page_ids)

    def test_iter_pages_specific_namespace(self, test_database):
        """Test iterating pages from specific namespace"""
        with DatabaseReader(str(test_database), namespaces=[10]) as db:
            pages = list(db.iter_pages())

            # Should only have Template namespace pages
            assert len(pages) == 1
            assert pages[0]["namespace"] == 10
            assert pages[0]["page_title"] == "Template:Infobox"

    def test_context_manager(self, test_database):
        """Test DatabaseReader as context manager"""
        db = DatabaseReader(str(test_database))

        assert db.conn is None

        with db:
            assert db.conn is not None
            # Can execute queries
            count = db.count_pages()
            assert count > 0

        # Connection should be closed after context
        assert db.conn is None or not db.conn


class TestDatabaseReaderEdgeCases:
    """Test edge cases and error conditions"""

    def test_nonexistent_database(self, tmp_path):
        """Test opening non-existent database"""
        db_path = tmp_path / "nonexistent.db"

        with pytest.raises(Exception):
            with DatabaseReader(str(db_path)) as db:
                db.count_pages()

    def test_empty_database(self, tmp_path):
        """Test database with no tables"""
        import sqlite3

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(db_path)
        conn.close()

        with pytest.raises(Exception):
            with DatabaseReader(str(db_path)) as db:
                db.count_pages()

    def test_database_with_no_pages(self, tmp_path):
        """Test database with tables but no data"""
        import sqlite3

        db_path = tmp_path / "empty_tables.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables but don't insert data
        cursor.execute("""
            CREATE TABLE pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                namespace INTEGER NOT NULL,
                latest_revision_id INTEGER,
                is_redirect INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE revisions (
                revision_id INTEGER PRIMARY KEY,
                page_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        with DatabaseReader(str(db_path)) as db:
            assert db.count_pages() == 0
            assert list(db.iter_pages()) == []

    def test_invalid_namespace_filter(self, test_database):
        """Test with namespace that doesn't exist"""
        with DatabaseReader(str(test_database), namespaces=[999]) as db:
            count = db.count_pages()
            assert count == 0

            pages = list(db.iter_pages())
            assert len(pages) == 0

    def test_empty_namespace_list(self, test_database):
        """Test with empty namespace list (should use default)"""
        with DatabaseReader(str(test_database), namespaces=None) as db:
            count = db.count_pages()
            assert count > 0  # Should default to namespace 0

    def test_duplicate_namespace_values(self, test_database):
        """Test with duplicate namespace values"""
        with DatabaseReader(str(test_database), namespaces=[0, 0, 0]) as db:
            count = db.count_pages()
            # Should handle duplicates gracefully
            assert count > 0

    def test_negative_namespace(self, test_database):
        """Test with negative namespace (special namespaces)"""
        with DatabaseReader(str(test_database), namespaces=[-1]) as db:
            # Should not crash, just return no results
            count = db.count_pages()
            assert count == 0


class TestDatabaseReaderPerformance:
    """Test performance characteristics"""

    def test_iter_pages_is_generator(self, test_database):
        """Test that iter_pages returns a generator/iterator"""
        with DatabaseReader(str(test_database)) as db:
            result = db.iter_pages()

            # Should be an iterator
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

    def test_iter_pages_lazy_loading(self, test_database):
        """Test that pages are loaded lazily"""
        with DatabaseReader(str(test_database)) as db:
            pages_iter = db.iter_pages()

            # Getting iterator shouldn't load all data
            # Just verify we can get first item without loading everything
            first_page = next(pages_iter)
            assert first_page is not None

            # Can continue iterating
            second_page = next(pages_iter)
            assert second_page is not None

    def test_multiple_iterations(self, test_database):
        """Test that multiple iterations work correctly"""
        with DatabaseReader(str(test_database)) as db:
            # First iteration
            pages1 = list(db.iter_pages())

            # Second iteration
            pages2 = list(db.iter_pages())

            # Should get same results
            assert len(pages1) == len(pages2)
            assert [p["page_id"] for p in pages1] == [p["page_id"] for p in pages2]


class TestDatabaseReaderDataIntegrity:
    """Test data integrity and consistency"""

    def test_page_revision_relationship(self, test_database):
        """Test that pages reference valid revisions"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            for page in pages:
                # Each page should have a revision_id
                assert page["revision_id"] is not None
                assert page["revision_id"] > 0

                # Page ID should match
                assert page["page_id"] > 0

    def test_content_encoding(self, test_database):
        """Test that content is properly encoded/decoded"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            for page in pages:
                # Content should be string
                assert isinstance(page["content"], str)

                # Should be able to handle the content
                assert len(page["content"]) >= 0

    def test_metadata_structure(self, test_database):
        """Test that metadata has expected structure"""
        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            for page in pages:
                metadata = page["metadata"]

                # Should be a dict
                assert isinstance(metadata, dict)

                # Should have required keys
                assert "timestamp" in metadata
                assert "contributor" in metadata
                assert "is_redirect" in metadata

                # Values should be correct types
                assert isinstance(metadata["timestamp"], str)
                assert metadata["contributor"] is None or isinstance(
                    metadata["contributor"], str
                )
                assert isinstance(metadata["is_redirect"], int)

    def test_special_characters_in_titles(self, test_database):
        """Test handling of special characters in page titles"""
        import sqlite3

        # Add page with special characters
        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pages VALUES (100, 'Test/Page:With-Special_Chars', 0, 200, 0)
        """)
        cursor.execute("""
            INSERT INTO revisions VALUES (200, 100, NULL, '2024-01-01T00:00:00Z', 
                                         'Editor', 'Content with unicode: é ñ ü')
        """)
        conn.commit()
        conn.close()

        with DatabaseReader(str(test_database)) as db:
            pages = list(db.iter_pages())

            # Find our special page
            special = [p for p in pages if p["page_id"] == 100]
            assert len(special) == 1
            assert "Special" in special[0]["page_title"]
            assert "unicode" in special[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
