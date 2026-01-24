"""Tests for XML exporter."""

from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scraper.export.xml_exporter import XMLExporter
from scraper.storage.database import Database
from scraper.storage.models import Page, Revision


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with sample data."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Initialize schema
    db.initialize_schema()

    with db.get_connection() as conn:
        # Insert test pages
        conn.execute("""
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES
                (1, 0, 'Main Page', 0),
                (2, 0, 'Test Page', 0),
                (3, 0, 'Redirect Page', 1),
                (4, 10, 'Test Template', 0)
            """)

        # Insert test revisions
        conn.execute("""
            INSERT INTO revisions (
                revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags
            ) VALUES
                (100, 1, NULL, '2024-01-15T10:00:00', 'User1', 1, 'Initial', 'Main page content', 17, 'abc123def456789012345678901234567890abcd', 0, NULL),
                (101, 1, 100, '2024-01-15T11:00:00', 'User2', 2, 'Update', 'Updated main page', 17, 'def456abc789012345678901234567890abcdef1', 0, NULL),
                (200, 2, NULL, '2024-01-15T10:00:00', 'User1', 1, 'Created', 'Test page content', 17, 'aaa123def456789012345678901234567890abcd', 0, NULL),
                (300, 3, NULL, '2024-01-15T10:00:00', 'User1', 1, 'Redirect', '#REDIRECT [[Main Page]]', 23, 'bbb123def456789012345678901234567890abcd', 0, NULL),
                (400, 4, NULL, '2024-01-15T10:00:00', 'User1', 1, 'Template', '{{Template content}}', 20, 'ccc123def456789012345678901234567890abcd', 0, NULL)
            """)
        conn.commit()

    return db


class TestXMLExporter:
    """Test XMLExporter class."""

    def test_init(self, test_db):
        """Test exporter initialization."""
        exporter = XMLExporter(test_db)
        assert exporter.database is test_db
        assert exporter.generator is not None

    def test_count_pages(self, test_db):
        """Test counting pages in database."""
        exporter = XMLExporter(test_db)
        count = exporter._count_pages()
        assert count == 4

    def test_stream_pages(self, test_db):
        """Test streaming pages from database."""
        exporter = XMLExporter(test_db)

        pages_list = list(exporter._stream_pages())

        # Should get 4 pages
        assert len(pages_list) == 4

        # Check first page
        page, revisions = pages_list[0]
        assert page.page_id == 1
        assert page.title == "Main Page"
        assert len(revisions) == 2  # Main Page has 2 revisions

        # Check revisions are in chronological order
        assert revisions[0].revision_id == 100
        assert revisions[1].revision_id == 101

    def test_export_to_file(self, test_db, tmp_path):
        """Test exporting database to XML file."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        stats = exporter.export_to_file(output_path, show_progress=False)

        # Check file was created
        assert output_path.exists()

        # Check statistics
        assert stats["pages_exported"] == 4
        assert stats["revisions_exported"] == 5
        assert stats["output_size_bytes"] > 0

    def test_export_generates_valid_xml(self, test_db, tmp_path):
        """Test exported XML is valid and parseable."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML to verify it's valid
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Check root is mediawiki element
        assert root.tag.endswith("mediawiki")

        # Check has siteinfo
        siteinfo = root.find("{http://www.mediawiki.org/xml/export-0.11/}siteinfo")
        assert siteinfo is not None

        # Check has pages
        pages = root.findall("{http://www.mediawiki.org/xml/export-0.11/}page")
        assert len(pages) == 4

    def test_export_includes_all_pages(self, test_db, tmp_path):
        """Test all pages are included in export."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        pages = root.findall("{http://www.mediawiki.org/xml/export-0.11/}page")
        page_titles = [
            p.find("{http://www.mediawiki.org/xml/export-0.11/}title").text
            for p in pages
        ]

        assert "Main Page" in page_titles
        assert "Test Page" in page_titles
        assert "Redirect Page" in page_titles
        assert "Test Template" in page_titles

    def test_export_includes_all_revisions(self, test_db, tmp_path):
        """Test all revisions are included for each page."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find Main Page (has 2 revisions)
        ns = "{http://www.mediawiki.org/xml/export-0.11/}"
        pages = root.findall(f"{ns}page")
        main_page = None
        for page in pages:
            if page.find(f"{ns}title").text == "Main Page":
                main_page = page
                break

        assert main_page is not None

        # Check has 2 revisions
        revisions = main_page.findall(f"{ns}revision")
        assert len(revisions) == 2

    def test_export_revision_content(self, test_db, tmp_path):
        """Test revision content is exported correctly."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find Test Page
        ns = "{http://www.mediawiki.org/xml/export-0.11/}"
        pages = root.findall(f"{ns}page")
        test_page = None
        for page in pages:
            if page.find(f"{ns}title").text == "Test Page":
                test_page = page
                break

        assert test_page is not None

        # Get revision content
        revision = test_page.find(f"{ns}revision")
        text = revision.find(f"{ns}text").text

        assert text == "Test page content"

    def test_export_redirect_page(self, test_db, tmp_path):
        """Test redirect page is marked correctly."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find Redirect Page
        ns = "{http://www.mediawiki.org/xml/export-0.11/}"
        pages = root.findall(f"{ns}page")
        redirect_page = None
        for page in pages:
            if page.find(f"{ns}title").text == "Redirect Page":
                redirect_page = page
                break

        assert redirect_page is not None

        # Check has redirect tag
        redirect_tag = redirect_page.find(f"{ns}redirect")
        assert redirect_tag is not None

    def test_export_namespace_handling(self, test_db, tmp_path):
        """Test pages in different namespaces are exported correctly."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        exporter.export_to_file(output_path, show_progress=False)

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find Template page (namespace 10)
        ns = "{http://www.mediawiki.org/xml/export-0.11/}"
        pages = root.findall(f"{ns}page")
        template_page = None
        for page in pages:
            if page.find(f"{ns}title").text == "Test Template":
                template_page = page
                break

        assert template_page is not None

        # Check namespace is 10
        namespace = template_page.find(f"{ns}ns").text
        assert namespace == "10"

    def test_export_empty_database(self, tmp_path):
        """Test exporting empty database."""
        db_path = tmp_path / "empty.db"
        db = Database(db_path)
        db.initialize_schema()  # Initialize schema for empty database

        exporter = XMLExporter(db)
        output_path = tmp_path / "export.xml"

        stats = exporter.export_to_file(output_path, show_progress=False)

        # Should create file with header and footer but no pages
        assert output_path.exists()
        assert stats["pages_exported"] == 0
        assert stats["revisions_exported"] == 0

        # Verify XML is still valid
        tree = ET.parse(output_path)
        root = tree.getroot()
        assert root.tag.endswith("mediawiki")

    def test_export_output_size(self, test_db, tmp_path):
        """Test export calculates output size correctly."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        stats = exporter.export_to_file(output_path, show_progress=False)

        # Check size matches actual file size
        actual_size = output_path.stat().st_size
        assert stats["output_size_bytes"] == actual_size
        assert actual_size > 1000  # Should be at least 1KB with our test data

    def test_export_with_progress_disabled(self, test_db, tmp_path):
        """Test export with progress bar disabled."""
        exporter = XMLExporter(test_db)
        output_path = tmp_path / "export.xml"

        # Should not raise error
        stats = exporter.export_to_file(output_path, show_progress=False)
        assert stats["pages_exported"] == 4
