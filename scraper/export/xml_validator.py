"""Validate MediaWiki XML export files.

This module provides validation for exported MediaWiki XML files to ensure
they conform to the expected structure and format.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

from scraper.export.schema import MEDIAWIKI_NS


class ValidationError:
    """Represents a validation error or warning."""

    def __init__(self, level: str, message: str, location: Optional[str] = None):
        """
        Initialize validation error.

        Args:
            level: Error level ('error' or 'warning')
            message: Error message
            location: Optional location information (e.g., element path)
        """
        self.level = level
        self.message = message
        self.location = location

    def __repr__(self) -> str:
        """Return string representation."""
        loc = f" at {self.location}" if self.location else ""
        return f"{self.level.upper()}{loc}: {self.message}"


class ValidationReport:
    """Report of validation results."""

    def __init__(self):
        """Initialize empty validation report."""
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def add_error(self, message: str, location: Optional[str] = None):
        """Add an error to the report."""
        self.errors.append(ValidationError("error", message, location))

    def add_warning(self, message: str, location: Optional[str] = None):
        """Add a warning to the report."""
        self.warnings.append(ValidationError("warning", message, location))

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def error_count(self) -> int:
        """Get number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get number of warnings."""
        return len(self.warnings)

    def __repr__(self) -> str:
        """Return string representation."""
        status = "PASS" if self.is_valid else "FAIL"
        return (
            f"ValidationReport({status}, {self.error_count} errors, "
            f"{self.warning_count} warnings)"
        )


class XMLValidator:
    """Validates MediaWiki XML export files."""

    # ISO 8601 timestamp pattern
    TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$")

    def __init__(self):
        """Initialize validator."""
        self.ns = {"mw": MEDIAWIKI_NS}

    def validate_xml_file(self, xml_path: Path) -> ValidationReport:
        """
        Validate MediaWiki XML export file.

        Args:
            xml_path: Path to XML file to validate

        Returns:
            ValidationReport with errors and warnings
        """
        report = ValidationReport()

        # Check file exists
        if not xml_path.exists():
            report.add_error(f"File not found: {xml_path}")
            return report

        # Check file is readable and not empty
        if xml_path.stat().st_size == 0:
            report.add_error("File is empty")
            return report

        # Try to parse XML
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except ET.ParseError as e:
            report.add_error(f"XML parse error: {e}")
            return report
        except Exception as e:
            report.add_error(f"Error reading file: {e}")
            return report

        # Validate structure
        self._validate_root_element(root, report)
        self._validate_siteinfo(root, report)
        self._validate_pages(root, report)

        return report

    def _validate_root_element(self, root: ET.Element, report: ValidationReport):
        """Validate root mediawiki element."""
        # Check root tag
        if not root.tag.endswith("mediawiki"):
            report.add_error(
                f"Root element should be 'mediawiki', got '{root.tag}'", "root"
            )
            return

        # Check namespace
        if MEDIAWIKI_NS not in root.tag:
            report.add_warning(
                f"Root element namespace doesn't match expected: {MEDIAWIKI_NS}", "root"
            )

        # Check version attribute
        version = root.get("version")
        if not version:
            report.add_error("Root element missing 'version' attribute", "root")
        elif version != "0.11":
            report.add_warning(
                f"Unexpected version '{version}', expected '0.11'", "root"
            )

        # Check xml:lang attribute
        lang = root.get("{http://www.w3.org/XML/1998/namespace}lang")
        if not lang:
            report.add_warning("Root element missing 'xml:lang' attribute", "root")

    def _validate_siteinfo(self, root: ET.Element, report: ValidationReport):
        """Validate siteinfo element."""
        siteinfo = root.find("mw:siteinfo", self.ns)
        if siteinfo is None:
            report.add_error("Missing required element: siteinfo", "mediawiki")
            return

        # Check required child elements
        required = ["sitename", "dbname", "base", "generator", "case", "namespaces"]
        for element_name in required:
            element = siteinfo.find(f"mw:{element_name}", self.ns)
            if element is None:
                report.add_error(
                    f"Missing required element: {element_name}", "siteinfo"
                )

        # Validate namespaces
        namespaces = siteinfo.find("mw:namespaces", self.ns)
        if namespaces is not None:
            ns_elements = namespaces.findall("mw:namespace", self.ns)
            if len(ns_elements) == 0:
                report.add_warning("No namespaces defined", "siteinfo/namespaces")

            # Check for main namespace (key="0")
            main_ns = False
            for ns_elem in ns_elements:
                key = ns_elem.get("key")
                if key == "0":
                    main_ns = True
                    break
            if not main_ns:
                report.add_error(
                    "Main namespace (key=0) not found", "siteinfo/namespaces"
                )

    def _validate_pages(self, root: ET.Element, report: ValidationReport):
        """Validate page elements."""
        pages = root.findall("mw:page", self.ns)

        if len(pages) == 0:
            report.add_warning("No pages found in export", "mediawiki")
            return

        # Validate each page
        for i, page in enumerate(pages):
            page_location = f"page[{i}]"
            self._validate_page(page, report, page_location)

    def _validate_page(self, page: ET.Element, report: ValidationReport, location: str):
        """Validate a single page element."""
        # Check required elements
        title = page.find("mw:title", self.ns)
        if title is None:
            report.add_error("Missing required element: title", location)
        elif not title.text or not title.text.strip():
            report.add_error("Page title is empty", location)

        ns = page.find("mw:ns", self.ns)
        if ns is None:
            report.add_error("Missing required element: ns", location)
        else:
            try:
                ns_value = int(ns.text)
                if ns_value < -2:
                    report.add_warning(f"Unusual namespace value: {ns_value}", location)
            except (ValueError, TypeError):
                report.add_error(f"Invalid namespace value: {ns.text}", location)

        page_id = page.find("mw:id", self.ns)
        if page_id is None:
            report.add_error("Missing required element: id", location)
        else:
            try:
                id_value = int(page_id.text)
                if id_value <= 0:
                    report.add_error(f"Page ID must be positive: {id_value}", location)
            except (ValueError, TypeError):
                report.add_error(f"Invalid page ID value: {page_id.text}", location)

        # Validate revisions
        revisions = page.findall("mw:revision", self.ns)
        if len(revisions) == 0:
            report.add_warning("Page has no revisions", location)

        for j, revision in enumerate(revisions):
            rev_location = f"{location}/revision[{j}]"
            self._validate_revision(revision, report, rev_location)

    def _validate_revision(
        self, revision: ET.Element, report: ValidationReport, location: str
    ):
        """Validate a single revision element."""
        # Check required elements
        rev_id = revision.find("mw:id", self.ns)
        if rev_id is None:
            report.add_error("Missing required element: id", location)
        else:
            try:
                id_value = int(rev_id.text)
                if id_value <= 0:
                    report.add_error(
                        f"Revision ID must be positive: {id_value}", location
                    )
            except (ValueError, TypeError):
                report.add_error(f"Invalid revision ID value: {rev_id.text}", location)

        # Check timestamp
        timestamp = revision.find("mw:timestamp", self.ns)
        if timestamp is None:
            report.add_error("Missing required element: timestamp", location)
        elif timestamp.text:
            if not self.TIMESTAMP_PATTERN.match(timestamp.text):
                report.add_error(
                    f"Invalid timestamp format: {timestamp.text} (expected ISO 8601)",
                    location,
                )
            else:
                # Try to parse timestamp
                try:
                    # Remove trailing Z if present
                    ts_str = timestamp.text.rstrip("Z")
                    datetime.fromisoformat(ts_str)
                except ValueError:
                    report.add_error(
                        f"Invalid timestamp value: {timestamp.text}", location
                    )

        # Check contributor
        contributor = revision.find("mw:contributor", self.ns)
        if contributor is None:
            report.add_error("Missing required element: contributor", location)

        # Check text element
        text = revision.find("mw:text", self.ns)
        if text is None:
            report.add_error("Missing required element: text", location)
        else:
            # Check bytes attribute
            bytes_attr = text.get("bytes")
            if bytes_attr is None:
                report.add_warning("Text element missing 'bytes' attribute", location)
            else:
                try:
                    bytes_value = int(bytes_attr)
                    if bytes_value < 0:
                        report.add_error(
                            f"Text bytes attribute must be non-negative: {bytes_value}",
                            location,
                        )
                except (ValueError, TypeError):
                    report.add_error(
                        f"Invalid bytes attribute value: {bytes_attr}", location
                    )

        # Check sha1
        sha1 = revision.find("mw:sha1", self.ns)
        if sha1 is None:
            report.add_warning("Missing sha1 element", location)
        elif sha1.text and len(sha1.text) != 40:
            report.add_error(
                f"Invalid sha1 length: {len(sha1.text)} (expected 40)", location
            )


def main():
    """Command-line interface for XML validation."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate MediaWiki XML export file")
    parser.add_argument(
        "xml_file",
        type=Path,
        help="Path to XML file to validate",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all warnings",
    )

    args = parser.parse_args()

    # Validate
    validator = XMLValidator()
    report = validator.validate_xml_file(args.xml_file)

    # Print results
    print(f"Validating: {args.xml_file}")
    print()

    if report.error_count > 0:
        print("ERRORS:")
        for error in report.errors:
            print(f"  {error}")
        print()

    if report.warning_count > 0 and args.verbose:
        print("WARNINGS:")
        for warning in report.warnings:
            print(f"  {warning}")
        print()

    print(f"Result: {report}")
    print()

    if report.is_valid:
        print("✓ Validation passed")
        sys.exit(0)
    else:
        print("✗ Validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
