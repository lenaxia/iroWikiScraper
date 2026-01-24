"""Tests for XML generator."""

import pytest
from datetime import datetime
from xml.etree import ElementTree as ET

from scraper.export.xml_generator import XMLGenerator
from scraper.storage.models import Page, Revision


class TestXMLGenerator:
    """Test XMLGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = XMLGenerator()

    def test_escape_xml(self):
        """Test XML escaping for special characters."""
        # Test basic escaping
        assert self.generator.escape_xml("<tag>") == "&lt;tag&gt;"
        assert self.generator.escape_xml("&amp;") == "&amp;amp;"
        assert self.generator.escape_xml('"quote"') == "&quot;quote&quot;"
        assert self.generator.escape_xml("'apostrophe'") == "&#x27;apostrophe&#x27;"

        # Test normal text unchanged
        assert self.generator.escape_xml("Normal text") == "Normal text"

    def test_generate_xml_header(self):
        """Test XML header generation."""
        header = self.generator.generate_xml_header()

        # Check XML declaration
        assert '<?xml version="1.0" encoding="UTF-8"?>' in header

        # Check mediawiki tag with namespace
        assert '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"' in header
        assert 'version="0.11"' in header
        assert 'xml:lang="en"' in header

    def test_generate_siteinfo(self):
        """Test siteinfo generation."""
        siteinfo = self.generator.generate_siteinfo()

        # Parse XML to verify structure
        # Wrap in root element for parsing
        xml_str = "<root>" + siteinfo + "</root>"
        root = ET.fromstring(xml_str)
        siteinfo_elem = root.find("siteinfo")

        assert siteinfo_elem is not None
        assert siteinfo_elem.find("sitename").text == "iRO Wiki"
        assert siteinfo_elem.find("dbname").text == "irowiki"
        assert siteinfo_elem.find("base").text == "https://irowiki.org/wiki/Main_Page"

        # Check namespaces
        namespaces_elem = siteinfo_elem.find("namespaces")
        assert namespaces_elem is not None

        # Check specific namespaces exist
        ns_elements = namespaces_elem.findall("namespace")
        ns_dict = {int(ns.get("key")): ns.text for ns in ns_elements}

        assert 0 in ns_dict  # Main namespace
        assert ns_dict[1] == "Talk"
        assert ns_dict[6] == "File"
        assert ns_dict[10] == "Template"

    def test_generate_revision_xml(self):
        """Test revision XML generation."""
        # Create test revision
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=99,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=42,
            comment="Test edit",
            content="Page content here",
            size=17,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Parse XML
        xml_str = "<root>" + revision_xml + "</root>"
        root = ET.fromstring(xml_str)
        rev_elem = root.find("revision")

        assert rev_elem is not None
        assert rev_elem.find("id").text == "100"
        assert rev_elem.find("parentid").text == "99"
        assert rev_elem.find("timestamp").text == "2024-01-15T10:30:00Z"

        # Check contributor
        contributor = rev_elem.find("contributor")
        assert contributor.find("username").text == "TestUser"
        assert contributor.find("id").text == "42"

        # Check comment
        assert rev_elem.find("comment").text == "Test edit"

        # Check content
        text_elem = rev_elem.find("text")
        assert text_elem.text == "Page content here"
        assert text_elem.get("bytes") is not None

        # Check sha1
        assert rev_elem.find("sha1").text == "abc123def456789012345678901234567890abcd"

    def test_generate_revision_xml_minor_edit(self):
        """Test revision XML generation with minor edit flag."""
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=42,
            comment="Minor fix",
            content="Content",
            size=7,
            sha1="abc123def456789012345678901234567890abcd",
            minor=True,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Check minor tag exists
        assert "<minor />" in revision_xml

    def test_generate_revision_xml_no_parent(self):
        """Test revision XML generation without parent (first revision)."""
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=42,
            comment="Initial version",
            content="First content",
            size=13,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Parse XML
        xml_str = "<root>" + revision_xml + "</root>"
        root = ET.fromstring(xml_str)
        rev_elem = root.find("revision")

        # Check no parentid element
        assert rev_elem.find("parentid") is None

    def test_generate_revision_xml_deleted_user(self):
        """Test revision XML generation with deleted user."""
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="",  # Deleted user
            user_id=None,
            comment="Edit by deleted user",
            content="Content",
            size=7,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Check empty username tag
        assert "<username />" in revision_xml

    def test_generate_revision_xml_empty_comment(self):
        """Test revision XML generation with empty comment."""
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=42,
            comment="",  # Empty comment
            content="Content",
            size=7,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Check empty comment tag
        assert "<comment />" in revision_xml

    def test_generate_revision_xml_special_characters(self):
        """Test revision XML generation with special characters in content."""
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=42,
            comment='Comment with <tag> and "quotes"',
            content='Content with <tags>, &amp;, and "quotes"',
            size=40,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        revision_xml = self.generator.generate_revision_xml(revision)

        # Verify XML is valid (no unescaped characters)
        xml_str = "<root>" + revision_xml + "</root>"
        root = ET.fromstring(xml_str)  # Should not raise

        # Verify content is escaped
        assert "&lt;tags&gt;" in revision_xml
        assert "&amp;amp;" in revision_xml
        assert "&quot;quotes&quot;" in revision_xml

    def test_generate_page_xml(self):
        """Test page XML generation."""
        # Create test page
        page = Page(
            page_id=1,
            namespace=0,
            title="Main Page",
            is_redirect=False,
        )

        # Create test revisions
        revisions = [
            Revision(
                revision_id=100,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                user="User1",
                user_id=1,
                comment="Initial version",
                content="First content",
                size=13,
                sha1="abc123def456789012345678901234567890abcd",
                minor=False,
            ),
            Revision(
                revision_id=101,
                page_id=1,
                parent_id=100,
                timestamp=datetime(2024, 1, 15, 11, 0, 0),
                user="User2",
                user_id=2,
                comment="Updated content",
                content="Second content",
                size=14,
                sha1="def456abc789012345678901234567890abcdef1",
                minor=False,
            ),
        ]

        page_xml = self.generator.generate_page_xml(page, revisions)

        # Parse XML
        xml_str = "<root>" + page_xml + "</root>"
        root = ET.fromstring(xml_str)
        page_elem = root.find("page")

        assert page_elem is not None
        assert page_elem.find("title").text == "Main Page"
        assert page_elem.find("ns").text == "0"
        assert page_elem.find("id").text == "1"

        # Check both revisions are present
        revision_elems = page_elem.findall("revision")
        assert len(revision_elems) == 2
        assert revision_elems[0].find("id").text == "100"
        assert revision_elems[1].find("id").text == "101"

    def test_generate_page_xml_redirect(self):
        """Test page XML generation for redirect page."""
        page = Page(
            page_id=2,
            namespace=0,
            title="Redirect Page",
            is_redirect=True,
        )

        revisions = [
            Revision(
                revision_id=200,
                page_id=2,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                user="User1",
                user_id=1,
                comment="Created redirect",
                content="#REDIRECT [[Target Page]]",
                size=25,
                sha1="abc123def456789012345678901234567890abcd",
                minor=False,
            ),
        ]

        page_xml = self.generator.generate_page_xml(page, revisions)

        # Check redirect tag is present
        assert "<redirect />" in page_xml

    def test_generate_page_xml_no_revisions(self):
        """Test page XML generation with no revisions."""
        page = Page(
            page_id=3,
            namespace=0,
            title="Empty Page",
            is_redirect=False,
        )

        page_xml = self.generator.generate_page_xml(page, [])

        # Parse XML
        xml_str = "<root>" + page_xml + "</root>"
        root = ET.fromstring(xml_str)
        page_elem = root.find("page")

        assert page_elem is not None
        # Should have no revision elements
        assert len(page_elem.findall("revision")) == 0

    def test_generate_xml_footer(self):
        """Test XML footer generation."""
        footer = self.generator.generate_xml_footer()
        assert footer == "</mediawiki>\n"

    def test_full_xml_document_structure(self):
        """Test generating a complete valid XML document."""
        page = Page(page_id=1, namespace=0, title="Test Page", is_redirect=False)
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            user="TestUser",
            user_id=1,
            comment="Test",
            content="Content",
            size=7,
            sha1="abc123def456789012345678901234567890abcd",
            minor=False,
        )

        # Build complete XML document
        xml_doc = (
            self.generator.generate_xml_header()
            + self.generator.generate_siteinfo()
            + self.generator.generate_page_xml(page, [revision])
            + self.generator.generate_xml_footer()
        )

        # Validate it's valid XML
        root = ET.fromstring(xml_doc)
        assert root.tag.endswith("mediawiki")  # Should be {namespace}mediawiki

        # Check structure
        assert (
            root.find("{http://www.mediawiki.org/xml/export-0.11/}siteinfo") is not None
        )
        assert root.find("{http://www.mediawiki.org/xml/export-0.11/}page") is not None
