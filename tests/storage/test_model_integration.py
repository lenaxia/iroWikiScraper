"""
Tests for model-database integration methods.

Tests cover:
- from_db_row() conversion for all models
- to_db_params() conversion for all models
- Round-trip fidelity (model → DB → model)
- NULL handling
- Type conversions (datetime, JSON, boolean)
- Edge cases
"""

import json
import sqlite3
from datetime import datetime

import pytest

from scraper.storage.database import Database
from scraper.storage.models import FileMetadata, Link, Page, Revision


class TestPageIntegration:
    """Test Page model database integration."""

    def test_page_from_db_row(self, db: Database):
        """Test Page.from_db_row() conversion."""
        conn = db.get_connection()

        # Insert page directly
        conn.execute("""
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (1, 0, 'Test Page', 1)
        """)
        conn.commit()

        # Retrieve and convert
        cursor = conn.execute("SELECT * FROM pages WHERE page_id = 1")
        row = cursor.fetchone()

        page = Page.from_db_row(row)

        assert page.page_id == 1
        assert page.namespace == 0
        assert page.title == "Test Page"
        assert page.is_redirect is True

    def test_page_to_db_params(self):
        """Test Page.to_db_params() conversion."""
        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)

        params = page.to_db_params()

        # Should return tuple in correct order for INSERT
        assert isinstance(params, tuple)
        assert len(params) == 4  # page_id, namespace, title, is_redirect
        assert params[0] == 1  # page_id
        assert params[1] == 0  # namespace
        assert params[2] == "Test"  # title
        assert params[3] == 0  # is_redirect as int

    def test_page_round_trip(self, db: Database):
        """Test Page round-trip conversion."""
        conn = db.get_connection()

        # Original page
        original = Page(page_id=1, namespace=0, title="Round Trip", is_redirect=True)

        # Insert using to_db_params()
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve using from_db_row()
        cursor = conn.execute("SELECT * FROM pages WHERE page_id = 1")
        row = cursor.fetchone()
        loaded = Page.from_db_row(row)

        # Verify fidelity
        assert loaded.page_id == original.page_id
        assert loaded.namespace == original.namespace
        assert loaded.title == original.title
        assert loaded.is_redirect == original.is_redirect

    def test_page_boolean_conversion(self, db: Database):
        """Test boolean is_redirect converts correctly."""
        conn = db.get_connection()

        # Test False → 0 → False
        page_false = Page(
            page_id=1, namespace=0, title="Not Redirect", is_redirect=False
        )
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page_false.to_db_params(),
        )

        # Test True → 1 → True
        page_true = Page(page_id=2, namespace=0, title="Is Redirect", is_redirect=True)
        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page_true.to_db_params(),
        )
        conn.commit()

        # Retrieve and verify
        cursor = conn.execute("SELECT * FROM pages WHERE page_id = 1")
        loaded_false = Page.from_db_row(cursor.fetchone())
        assert loaded_false.is_redirect is False

        cursor = conn.execute("SELECT * FROM pages WHERE page_id = 2")
        loaded_true = Page.from_db_row(cursor.fetchone())
        assert loaded_true.is_redirect is True


class TestRevisionIntegration:
    """Test Revision model database integration."""

    @pytest.fixture
    def page_id(self, db: Database) -> int:
        """Create a page for revision tests."""
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')"
        )
        conn.commit()
        return 1

    def test_revision_from_db_row(self, db: Database, page_id: int):
        """Test Revision.from_db_row() conversion."""
        conn = db.get_connection()

        # Insert revision with all fields
        conn.execute("""
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, '2024-01-15T10:00:00', 'Alice', 101,
                    'Test comment', 'Test content', 12, 'abc123', 1, '["tag1", "tag2"]')
        """)
        conn.commit()

        # Retrieve and convert
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        row = cursor.fetchone()

        revision = Revision.from_db_row(row)

        assert revision.revision_id == 1
        assert revision.page_id == 1
        assert revision.parent_id is None
        assert revision.timestamp == datetime(2024, 1, 15, 10, 0, 0)
        assert revision.user == "Alice"
        assert revision.user_id == 101
        assert revision.comment == "Test comment"
        assert revision.content == "Test content"
        assert revision.size == 12
        assert revision.sha1 == "abc123"
        assert revision.minor is True
        assert revision.tags == ["tag1", "tag2"]

    def test_revision_to_db_params(self):
        """Test Revision.to_db_params() conversion."""
        revision = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            user="Alice",
            user_id=101,
            comment="Test",
            content="Content",
            size=7,
            sha1="abc",
            minor=False,
            tags=["visual-edit"],
        )

        params = revision.to_db_params()

        assert isinstance(params, tuple)
        assert len(params) == 12
        assert params[0] == 1  # revision_id
        assert params[1] == 1  # page_id
        assert params[2] is None  # parent_id
        assert params[3] == "2024-01-15T10:00:00"  # timestamp as ISO string
        assert params[4] == "Alice"  # user
        assert params[5] == 101  # user_id
        assert params[6] == "Test"  # comment
        assert params[7] == "Content"  # content
        assert params[8] == 7  # size
        assert params[9] == "abc"  # sha1
        assert params[10] == 0  # minor as int
        assert params[11] == '["visual-edit"]'  # tags as JSON

    def test_revision_round_trip_with_tags(self, db: Database, page_id: int):
        """Test Revision round-trip with tags."""
        conn = db.get_connection()

        original = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            user="Alice",
            user_id=101,
            comment="Test edit",
            content="Test content",
            size=12,
            sha1="abc123",
            minor=False,
            tags=["visual-edit", "mobile-edit"],
        )

        # Insert
        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        loaded = Revision.from_db_row(cursor.fetchone())

        # Verify
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

    def test_revision_null_handling(self, db: Database, page_id: int):
        """Test NULL field handling."""
        conn = db.get_connection()

        # Create revision with NULL fields
        original = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,  # NULL
            timestamp=datetime(2024, 1, 15),
            user="",  # Empty user (deleted)
            user_id=None,  # NULL
            comment="",  # Empty comment
            content="Test",
            size=4,
            sha1="abc",
            minor=False,
            tags=None,  # NULL
        )

        # Insert
        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        loaded = Revision.from_db_row(cursor.fetchone())

        # Verify NULLs preserved
        assert loaded.parent_id is None
        assert loaded.user_id is None
        # Tags should be empty list (not None) after from_db_row conversion
        # This is per the Revision model's __post_init__ behavior
        assert loaded.tags == [] or loaded.tags is None

    def test_revision_datetime_conversion(self, db: Database, page_id: int):
        """Test datetime ISO string conversion."""
        conn = db.get_connection()

        # Test various datetime formats
        test_time = datetime(2024, 1, 15, 10, 30, 45)

        original = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=test_time,
            user="User",
            user_id=1,
            comment="",
            content="Test",
            size=4,
            sha1="abc",
            minor=False,
            tags=None,
        )

        # Insert
        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        loaded = Revision.from_db_row(cursor.fetchone())

        # Verify datetime conversion
        assert loaded.timestamp == test_time
        assert loaded.timestamp.year == 2024
        assert loaded.timestamp.month == 1
        assert loaded.timestamp.day == 15
        assert loaded.timestamp.hour == 10
        assert loaded.timestamp.minute == 30
        assert loaded.timestamp.second == 45

    def test_revision_tags_json_conversion(self, db: Database, page_id: int):
        """Test tags JSON conversion."""
        conn = db.get_connection()

        # Test with empty list
        rev_empty = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1),
            user="User",
            user_id=1,
            comment="",
            content="Test",
            size=4,
            sha1="abc1",
            minor=False,
            tags=[],
        )

        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            rev_empty.to_db_params(),
        )

        # Test with multiple tags
        rev_tags = Revision(
            revision_id=2,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 2),
            user="User",
            user_id=1,
            comment="",
            content="Test",
            size=4,
            sha1="abc2",
            minor=False,
            tags=["tag1", "tag2", "tag3"],
        )

        conn.execute(
            """
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            rev_tags.to_db_params(),
        )
        conn.commit()

        # Retrieve and verify
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        loaded_empty = Revision.from_db_row(cursor.fetchone())
        assert loaded_empty.tags == []

        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 2")
        loaded_tags = Revision.from_db_row(cursor.fetchone())
        assert loaded_tags.tags == ["tag1", "tag2", "tag3"]


class TestFileMetadataIntegration:
    """Test FileMetadata model database integration."""

    def test_file_from_db_row(self, db: Database):
        """Test FileMetadata.from_db_row() conversion."""
        conn = db.get_connection()

        # Insert file
        conn.execute("""
            INSERT INTO files 
            (filename, url, descriptionurl, sha1, size, width, height,
             mime_type, timestamp, uploader)
            VALUES ('Test.png', 'https://example.com/Test.png',
                    'https://example.com/File:Test.png',
                    '1234567890abcdef1234567890abcdef12345678',
                    102400, 800, 600, 'image/png',
                    '2024-01-15T10:00:00', 'Alice')
        """)
        conn.commit()

        # Retrieve and convert
        cursor = conn.execute("SELECT * FROM files WHERE filename = 'Test.png'")
        row = cursor.fetchone()

        file = FileMetadata.from_db_row(row)

        assert file.filename == "Test.png"
        assert file.url == "https://example.com/Test.png"
        assert file.descriptionurl == "https://example.com/File:Test.png"
        assert file.sha1 == "1234567890abcdef1234567890abcdef12345678"
        assert file.size == 102400
        assert file.width == 800
        assert file.height == 600
        assert file.mime_type == "image/png"
        assert file.timestamp == datetime(2024, 1, 15, 10, 0, 0)
        assert file.uploader == "Alice"

    def test_file_to_db_params(self):
        """Test FileMetadata.to_db_params() conversion."""
        file = FileMetadata(
            filename="Test.png",
            url="https://example.com/Test.png",
            descriptionurl="https://example.com/File:Test.png",
            sha1="1234567890abcdef1234567890abcdef12345678",
            size=102400,
            width=800,
            height=600,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            uploader="Alice",
        )

        params = file.to_db_params()

        assert isinstance(params, tuple)
        assert len(params) == 10
        assert params[0] == "Test.png"
        assert params[8] == "2024-01-15T10:00:00"  # timestamp as ISO string

    def test_file_round_trip(self, db: Database):
        """Test FileMetadata round-trip conversion."""
        conn = db.get_connection()

        original = FileMetadata(
            filename="Round.png",
            url="https://example.com/Round.png",
            descriptionurl="https://example.com/File:Round.png",
            sha1="abcdef1234567890abcdef1234567890abcdef12",
            size=50000,
            width=1024,
            height=768,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 20, 15, 30, 0),
            uploader="Bob",
        )

        # Insert
        conn.execute(
            """
            INSERT INTO files 
            (filename, url, descriptionurl, sha1, size, width, height,
             mime_type, timestamp, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM files WHERE filename = 'Round.png'")
        loaded = FileMetadata.from_db_row(cursor.fetchone())

        # Verify
        assert loaded.filename == original.filename
        assert loaded.url == original.url
        assert loaded.descriptionurl == original.descriptionurl
        assert loaded.sha1 == original.sha1
        assert loaded.size == original.size
        assert loaded.width == original.width
        assert loaded.height == original.height
        assert loaded.mime_type == original.mime_type
        assert loaded.timestamp == original.timestamp
        assert loaded.uploader == original.uploader

    def test_file_null_dimensions(self, db: Database):
        """Test NULL width/height for non-images."""
        conn = db.get_connection()

        # PDF with no dimensions
        original = FileMetadata(
            filename="Document.pdf",
            url="https://example.com/Document.pdf",
            descriptionurl="https://example.com/File:Document.pdf",
            sha1="1234567890abcdef1234567890abcdef12345678",
            size=500000,
            width=None,
            height=None,
            mime_type="application/pdf",
            timestamp=datetime(2024, 1, 15),
            uploader="User",
        )

        # Insert
        conn.execute(
            """
            INSERT INTO files 
            (filename, url, descriptionurl, sha1, size, width, height,
             mime_type, timestamp, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM files WHERE filename = 'Document.pdf'")
        loaded = FileMetadata.from_db_row(cursor.fetchone())

        # Verify NULL dimensions
        assert loaded.width is None
        assert loaded.height is None


class TestLinkIntegration:
    """Test Link model database integration."""

    @pytest.fixture
    def page_id(self, db: Database) -> int:
        """Create a page for link tests."""
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Source')"
        )
        conn.commit()
        return 1

    def test_link_from_db_row(self, db: Database, page_id: int):
        """Test Link.from_db_row() conversion."""
        conn = db.get_connection()

        # Insert link
        conn.execute("""
            INSERT INTO links (source_page_id, target_title, link_type)
            VALUES (1, 'Target Page', 'page')
        """)
        conn.commit()

        # Retrieve and convert
        cursor = conn.execute("""
            SELECT * FROM links 
            WHERE source_page_id = 1 AND target_title = 'Target Page'
        """)
        row = cursor.fetchone()

        link = Link.from_db_row(row)

        assert link.source_page_id == 1
        assert link.target_title == "Target Page"
        assert link.link_type == "page"

    def test_link_to_db_params(self):
        """Test Link.to_db_params() conversion."""
        link = Link(source_page_id=1, target_title="Target", link_type="template")

        params = link.to_db_params()

        assert isinstance(params, tuple)
        assert len(params) == 3
        assert params[0] == 1  # source_page_id
        assert params[1] == "Target"  # target_title
        assert params[2] == "template"  # link_type

    def test_link_round_trip(self, db: Database, page_id: int):
        """Test Link round-trip conversion."""
        conn = db.get_connection()

        original = Link(
            source_page_id=1, target_title="Round Trip Link", link_type="category"
        )

        # Insert
        conn.execute(
            """
            INSERT INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
        """,
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("""
            SELECT * FROM links 
            WHERE source_page_id = 1 AND target_title = 'Round Trip Link'
        """)
        loaded = Link.from_db_row(cursor.fetchone())

        # Verify
        assert loaded.source_page_id == original.source_page_id
        assert loaded.target_title == original.target_title
        assert loaded.link_type == original.link_type

    def test_link_all_types(self, db: Database, page_id: int):
        """Test all link types round-trip correctly."""
        conn = db.get_connection()

        link_types = ["page", "template", "file", "category"]

        for i, link_type in enumerate(link_types):
            link = Link(
                source_page_id=1, target_title=f"Target {i}", link_type=link_type
            )

            # Insert
            conn.execute(
                """
                INSERT INTO links (source_page_id, target_title, link_type)
                VALUES (?, ?, ?)
            """,
                link.to_db_params(),
            )

        conn.commit()

        # Retrieve all
        cursor = conn.execute("SELECT * FROM links WHERE source_page_id = 1")
        loaded_links = [Link.from_db_row(row) for row in cursor.fetchall()]

        # Verify all types present
        loaded_types = [link.link_type for link in loaded_links]
        for link_type in link_types:
            assert link_type in loaded_types


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_strings_vs_null(self, db: Database):
        """Test distinction between empty strings and NULL."""
        conn = db.get_connection()

        # Create page
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')"
        )

        # Revision with empty strings (not NULL)
        original = Revision(
            revision_id=1,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1),
            user="",  # Empty string
            user_id=None,  # NULL
            comment="",  # Empty string
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
            original.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
        loaded = Revision.from_db_row(cursor.fetchone())

        # Empty strings should be preserved as empty strings
        assert loaded.user == ""
        assert loaded.comment == ""
        # NULL should be preserved as None
        assert loaded.user_id is None

    def test_special_characters_in_strings(self, db: Database):
        """Test special characters are preserved."""
        conn = db.get_connection()

        # Page with special characters
        page = Page(
            page_id=1,
            namespace=0,
            title="Test: Page with 'quotes' and \"double quotes\" & ampersand",
            is_redirect=False,
        )

        conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (?, ?, ?, ?)
        """,
            page.to_db_params(),
        )
        conn.commit()

        # Retrieve
        cursor = conn.execute("SELECT * FROM pages WHERE page_id = 1")
        loaded = Page.from_db_row(cursor.fetchone())

        # Special characters should be preserved
        assert loaded.title == page.title
        assert "'" in loaded.title
        assert '"' in loaded.title
        assert "&" in loaded.title
