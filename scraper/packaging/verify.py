"""Verify release package integrity.

This module provides verification tools to check release archives.
"""

import json
from pathlib import Path
from typing import Dict, List

from scraper.export.xml_validator import XMLValidator
from scraper.packaging.checksums import verify_checksums


class VerificationError:
    """Represents a verification error."""

    def __init__(self, message: str, severity: str = "error"):
        """
        Initialize verification error.

        Args:
            message: Error message
            severity: Error severity ('error' or 'warning')
        """
        self.message = message
        self.severity = severity

    def __repr__(self) -> str:
        """Return string representation."""
        return f"{self.severity.upper()}: {self.message}"


class VerificationReport:
    """Report of verification results."""

    def __init__(self):
        """Initialize empty report."""
        self.errors: List[VerificationError] = []
        self.warnings: List[VerificationError] = []
        self.checks_passed: List[str] = []

    def add_error(self, message: str):
        """Add an error."""
        self.errors.append(VerificationError(message, "error"))

    def add_warning(self, message: str):
        """Add a warning."""
        self.warnings.append(VerificationError(message, "warning"))

    def add_passed(self, check_name: str):
        """Mark a check as passed."""
        self.checks_passed.append(check_name)

    @property
    def is_valid(self) -> bool:
        """Check if verification passed."""
        return len(self.errors) == 0

    @property
    def error_count(self) -> int:
        """Get error count."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get warning count."""
        return len(self.warnings)

    def __repr__(self) -> str:
        """Return string representation."""
        status = "PASS" if self.is_valid else "FAIL"
        return (
            f"VerificationReport({status}, "
            f"{self.error_count} errors, {self.warning_count} warnings, "
            f"{len(self.checks_passed)} checks passed)"
        )


def verify_release(release_dir: Path) -> VerificationReport:
    """
    Verify release package integrity.

    Checks:
    - All expected files are present
    - Checksums match
    - Manifest is valid JSON
    - XML export is valid

    Args:
        release_dir: Path to release directory

    Returns:
        VerificationReport with results
    """
    report = VerificationReport()

    # Check directory exists
    if not release_dir.exists():
        report.add_error(f"Release directory not found: {release_dir}")
        return report

    if not release_dir.is_dir():
        report.add_error(f"Path is not a directory: {release_dir}")
        return report

    # Check required files exist
    _check_required_files(release_dir, report)

    # Verify checksums
    _verify_checksums(release_dir, report)

    # Verify manifest
    _verify_manifest(release_dir, report)

    # Verify XML
    _verify_xml(release_dir, report)

    return report


def _check_required_files(release_dir: Path, report: VerificationReport):
    """Check that all required files are present."""
    required_files = [
        "irowiki.db",
        "irowiki-export.xml",
        "MANIFEST.json",
        "README.txt",
        "checksums.sha256",
    ]

    required_dirs = ["files"]

    for filename in required_files:
        file_path = release_dir / filename
        if file_path.exists():
            report.add_passed(f"File exists: {filename}")
        else:
            report.add_error(f"Missing required file: {filename}")

    for dirname in required_dirs:
        dir_path = release_dir / dirname
        if dir_path.exists() and dir_path.is_dir():
            report.add_passed(f"Directory exists: {dirname}")
        else:
            report.add_warning(f"Missing directory: {dirname}")


def _verify_checksums(release_dir: Path, report: VerificationReport):
    """Verify file checksums."""
    checksums_file = release_dir / "checksums.sha256"
    if not checksums_file.exists():
        report.add_error("Cannot verify checksums: checksums.sha256 not found")
        return

    try:
        results = verify_checksums(release_dir, checksums_file)

        if results["verified"] > 0:
            report.add_passed(f"Checksums verified: {results['verified']} files")

        if results["failed"] > 0:
            for filename, expected, actual in results["failures"]:
                report.add_error(
                    f"Checksum mismatch for {filename}: "
                    f"expected {expected[:8]}..., got {actual[:8]}..."
                )

        if results["missing"] > 0:
            for filename in results["missing_files"]:
                report.add_error(f"File listed in checksums but not found: {filename}")

    except Exception as e:
        report.add_error(f"Checksum verification failed: {e}")


def _verify_manifest(release_dir: Path, report: VerificationReport):
    """Verify manifest file."""
    manifest_path = release_dir / "MANIFEST.json"
    if not manifest_path.exists():
        report.add_error("Cannot verify manifest: MANIFEST.json not found")
        return

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Check required fields
        required_fields = [
            "version",
            "scrape_date",
            "wiki_url",
            "statistics",
            "schema_version",
        ]

        for field in required_fields:
            if field in manifest:
                report.add_passed(f"Manifest has field: {field}")
            else:
                report.add_error(f"Manifest missing required field: {field}")

        # Check statistics
        if "statistics" in manifest:
            stats = manifest["statistics"]
            required_stats = [
                "total_pages",
                "total_revisions",
                "total_files",
                "database_size_mb",
            ]

            for stat in required_stats:
                if stat in stats:
                    report.add_passed(f"Manifest statistics has: {stat}")
                else:
                    report.add_warning(f"Manifest statistics missing: {stat}")

    except json.JSONDecodeError as e:
        report.add_error(f"Manifest is not valid JSON: {e}")
    except Exception as e:
        report.add_error(f"Manifest verification failed: {e}")


def _verify_xml(release_dir: Path, report: VerificationReport):
    """Verify XML export."""
    xml_path = release_dir / "irowiki-export.xml"
    if not xml_path.exists():
        report.add_error("Cannot verify XML: irowiki-export.xml not found")
        return

    try:
        validator = XMLValidator()
        validation_report = validator.validate_xml_file(xml_path)

        if validation_report.is_valid:
            report.add_passed("XML export is valid")
        else:
            for error in validation_report.errors[:5]:  # Show first 5 errors
                report.add_error(f"XML validation error: {error.message}")

            if validation_report.error_count > 5:
                report.add_error(
                    f"... and {validation_report.error_count - 5} more XML errors"
                )

        # Add warnings from XML validation
        for warning in validation_report.warnings[:3]:  # Show first 3 warnings
            report.add_warning(f"XML validation warning: {warning.message}")

    except Exception as e:
        report.add_error(f"XML verification failed: {e}")


def main():
    """Command-line interface for release verification."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Verify iRO Wiki release package integrity"
    )
    parser.add_argument(
        "release_dir",
        type=Path,
        help="Path to release directory",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all checks",
    )

    args = parser.parse_args()

    # Verify
    print(f"Verifying release: {args.release_dir}")
    print()

    report = verify_release(args.release_dir)

    # Print results
    if args.verbose and report.checks_passed:
        print(f"PASSED CHECKS ({len(report.checks_passed)}):")
        for check in report.checks_passed:
            print(f"  ✓ {check}")
        print()

    if report.error_count > 0:
        print(f"ERRORS ({report.error_count}):")
        for error in report.errors:
            print(f"  ✗ {error.message}")
        print()

    if report.warning_count > 0:
        print(f"WARNINGS ({report.warning_count}):")
        for warning in report.warnings:
            print(f"  ! {warning.message}")
        print()

    print(f"Result: {report}")
    print()

    if report.is_valid:
        print("✓ Release verification PASSED")
        sys.exit(0)
    else:
        print("✗ Release verification FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
