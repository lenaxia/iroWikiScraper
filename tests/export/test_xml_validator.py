"""Tests for XML validator."""

import pytest

from scraper.export.xml_exporter import XMLExporter
from scraper.export.xml_validator import ValidationReport, XMLValidator
from scraper.storage.database import Database


@pytest.fixture
def validator():
    """Create XMLValidator instance."""
    return XMLValidator()


@pytest.fixture
def valid_xml_file(tmp_path, test_db):
    """Create a valid XML export file."""
    exporter = XMLExporter(test_db)
    output_path = tmp_path / "valid.xml"
    exporter.export_to_file(output_path, show_progress=False)
    return output_path


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with sample data."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.initialize_schema()

    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO pages (page_id, namespace, title, is_redirect)
            VALUES (1, 0, 'Test Page', 0)
            """)
        conn.execute("""
            INSERT INTO revisions (
                revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags
            ) VALUES
                (100, 1, NULL, '2024-01-15T10:00:00', 'User1', 1, 'Test', 'Content', 7, 'abc123def456789012345678901234567890abcd', 0, NULL)  # noqa: E501
            """)
        conn.commit()

    return db


class TestValidationReport:
    """Test ValidationReport class."""

    def test_init(self):
        """Test report initialization."""
        report = ValidationReport()
        assert report.is_valid
        assert report.error_count == 0
        assert report.warning_count == 0

    def test_add_error(self):
        """Test adding errors."""
        report = ValidationReport()
        report.add_error("Test error")
        assert not report.is_valid
        assert report.error_count == 1
        assert report.warning_count == 0

    def test_add_warning(self):
        """Test adding warnings."""
        report = ValidationReport()
        report.add_warning("Test warning")
        assert report.is_valid  # Warnings don't fail validation
        assert report.error_count == 0
        assert report.warning_count == 1

    def test_multiple_errors_and_warnings(self):
        """Test multiple errors and warnings."""
        report = ValidationReport()
        report.add_error("Error 1")
        report.add_error("Error 2")
        report.add_warning("Warning 1")
        assert not report.is_valid
        assert report.error_count == 2
        assert report.warning_count == 1

    def test_repr(self):
        """Test string representation."""
        report = ValidationReport()
        assert "PASS" in str(report)
        report.add_error("Test")
        assert "FAIL" in str(report)


class TestXMLValidator:
    """Test XMLValidator class."""

    def test_init(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert validator.ns is not None

    def test_validate_nonexistent_file(self, validator, tmp_path):
        """Test validating nonexistent file."""
        report = validator.validate_xml_file(tmp_path / "nonexistent.xml")
        assert not report.is_valid
        assert report.error_count == 1
        assert "not found" in report.errors[0].message.lower()

    def test_validate_empty_file(self, validator, tmp_path):
        """Test validating empty file."""
        empty_file = tmp_path / "empty.xml"
        empty_file.write_text("")
        report = validator.validate_xml_file(empty_file)
        assert not report.is_valid
        assert report.error_count == 1
        assert "empty" in report.errors[0].message.lower()

    def test_validate_malformed_xml(self, validator, tmp_path):
        """Test validating malformed XML."""
        malformed_file = tmp_path / "malformed.xml"
        malformed_file.write_text("<mediawiki><page>unclosed")
        report = validator.validate_xml_file(malformed_file)
        assert not report.is_valid
        assert report.error_count == 1
        assert "parse error" in report.errors[0].message.lower()

    def test_validate_valid_xml_file(self, validator, valid_xml_file):
        """Test validating valid XML file."""
        report = validator.validate_xml_file(valid_xml_file)
        assert report.is_valid or report.error_count == 0
        # May have warnings, but should have no errors

    def test_validate_wrong_root_element(self, validator, tmp_path):
        """Test validating XML with wrong root element."""
        wrong_root = tmp_path / "wrong_root.xml"
        wrong_root.write_text('<?xml version="1.0"?><html></html>')
        report = validator.validate_xml_file(wrong_root)
        assert not report.is_valid
        assert any("mediawiki" in e.message.lower() for e in report.errors)

    def test_validate_missing_siteinfo(self, validator, tmp_path):
        """Test validating XML with missing siteinfo."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_siteinfo.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("siteinfo" in e.message.lower() for e in report.errors)

    def test_validate_missing_version_attribute(self, validator, tmp_path):
        """Test validating XML with missing version attribute."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case><namespaces></namespaces></siteinfo>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_version.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("version" in e.message.lower() for e in report.errors)

    def test_validate_missing_namespace_zero(self, validator, tmp_path):
        """Test validating XML with missing main namespace."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            "<namespaces>"
            '<namespace key="1">Talk</namespace>'
            "</namespaces></siteinfo>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_ns_zero.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("main namespace" in e.message.lower() for e in report.errors)

    def test_validate_page_missing_title(self, validator, tmp_path):
        """Test validating page with missing title."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><ns>0</ns><id>1</id></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_title.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("title" in e.message.lower() for e in report.errors)

    def test_validate_page_empty_title(self, validator, tmp_path):
        """Test validating page with empty title."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title></title><ns>0</ns><id>1</id></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "empty_title.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("empty" in e.message.lower() for e in report.errors)

    def test_validate_page_invalid_namespace(self, validator, tmp_path):
        """Test validating page with invalid namespace."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title>Test</title><ns>invalid</ns><id>1</id></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "invalid_ns.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("namespace" in e.message.lower() for e in report.errors)

    def test_validate_page_negative_id(self, validator, tmp_path):
        """Test validating page with negative ID."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title>Test</title><ns>0</ns><id>-1</id></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "negative_id.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("positive" in e.message.lower() for e in report.errors)

    def test_validate_revision_invalid_timestamp(self, validator, tmp_path):
        """Test validating revision with invalid timestamp."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title>Test</title><ns>0</ns><id>1</id>"
            "<revision><id>1</id><timestamp>invalid-date</timestamp>"
            "<contributor><username>User</username></contributor>"
            '<text bytes="7">Content</text><sha1>abc123def456789012345678901234567890abcd</sha1>'
            "</revision></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "invalid_timestamp.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("timestamp" in e.message.lower() for e in report.errors)

    def test_validate_revision_missing_text(self, validator, tmp_path):
        """Test validating revision with missing text element."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title>Test</title><ns>0</ns><id>1</id>"
            "<revision><id>1</id><timestamp>2024-01-15T10:00:00Z</timestamp>"
            "<contributor><username>User</username></contributor>"
            "<sha1>abc123def456789012345678901234567890abcd</sha1>"
            "</revision></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_text.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("text" in e.message.lower() for e in report.errors)

    def test_validate_revision_invalid_sha1_length(self, validator, tmp_path):
        """Test validating revision with invalid SHA1 length."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "<page><title>Test</title><ns>0</ns><id>1</id>"
            "<revision><id>1</id><timestamp>2024-01-15T10:00:00Z</timestamp>"
            "<contributor><username>User</username></contributor>"
            '<text bytes="7">Content</text><sha1>tooshort</sha1>'
            "</revision></page>"
            "</mediawiki>"
        )
        xml_file = tmp_path / "invalid_sha1.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        assert not report.is_valid
        assert any("sha1" in e.message.lower() for e in report.errors)

    def test_validate_no_pages_warning(self, validator, tmp_path):
        """Test validating XML with no pages generates warning."""
        xml_content = (
            '<?xml version="1.0"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">'
            "<siteinfo><sitename>Test</sitename><dbname>test</dbname>"
            "<base>http://test.com</base><generator>Test</generator>"
            "<case>first-letter</case>"
            '<namespaces><namespace key="0" /></namespaces></siteinfo>'
            "</mediawiki>"
        )
        xml_file = tmp_path / "no_pages.xml"
        xml_file.write_text(xml_content)
        report = validator.validate_xml_file(xml_file)
        # Should be valid (no errors) but have a warning
        assert report.is_valid
        assert report.warning_count > 0
        assert any("no pages" in w.message.lower() for w in report.warnings)
