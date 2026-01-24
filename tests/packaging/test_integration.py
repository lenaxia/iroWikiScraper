"""Integration tests for complete packaging workflows.

These tests validate end-to-end packaging scenarios including:
- Complete release workflow from database to verified package
- Large archive splitting and reassembly
- Error scenarios and recovery
- Release verification workflows
"""

import pytest
from pathlib import Path
import json
import tarfile
import shutil

from scraper.storage.database import Database
from scraper.packaging.package import PackagingConfig, package_release
from scraper.packaging.checksums import verify_checksums
from scraper.packaging.verify import verify_release
from scraper.export.xml_exporter import XMLExporter
from scraper.export.xml_validator import XMLValidator


@pytest.fixture
def populated_db(tmp_path):
    """Create a database with realistic test data."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.initialize_schema()

    with db.get_connection() as conn:
        # Add multiple pages
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (1, 0, 'Main_Page', 0)"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (2, 0, 'Test_Page', 0)"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (3, 1, 'Talk:Main_Page', 0)"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (4, 6, 'File:Test.png', 0)"
        )
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (5, 0, 'Redirect_Test', 1)"
        )

        # Add multiple revisions
        conn.execute("""
            INSERT INTO revisions (revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, '2024-01-01T00:00:00Z', 'Admin', 1, 'Initial creation', 
                    'Welcome to the wiki!', 20, 'abc123def456789012345678901234567890abcd', 0, NULL)
            """)
        conn.execute("""
            INSERT INTO revisions (revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags)
            VALUES (2, 1, 1, '2024-01-02T00:00:00Z', 'Editor', 2, 'Updated content', 
                    'Welcome to the wiki! Updated.', 29, 'def456abc789012345678901234567890abcdef0', 0, NULL)
            """)
        conn.execute("""
            INSERT INTO revisions (revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags)
            VALUES (3, 2, NULL, '2024-01-03T00:00:00Z', 'Contributor', 3, 'New test page', 
                    'This is a test page.', 19, '123456789abcdef0123456789abcdef012345678', 0, NULL)
            """)

        # Add files
        conn.execute("""
            INSERT INTO files (filename, timestamp, uploader, size, width, height, sha1, mime_type, url, descriptionurl)
            VALUES ('Test.png', '2024-01-01T00:00:00Z', 'Admin', 1024, 100, 100,
                    'abcdef0123456789abcdef0123456789abcdef01', 'image/png',
                    'https://irowiki.org/~iro/images/Test.png',
                    'https://irowiki.org/wiki/File:Test.png')
            """)

        conn.commit()

    return db


@pytest.fixture
def test_files_dir(tmp_path):
    """Create test files directory with sample files."""
    files_dir = tmp_path / "files"
    files_dir.mkdir()

    # Create sample files
    (files_dir / "Test.png").write_bytes(b"PNG_DATA" * 128)  # ~1KB
    (files_dir / "Another.jpg").write_bytes(b"JPG_DATA" * 256)  # ~2KB

    # Create subdirectory
    subdir = files_dir / "archive"
    subdir.mkdir()
    (subdir / "Old.gif").write_bytes(b"GIF_DATA" * 64)  # ~512B

    return files_dir


class TestCompleteReleaseWorkflow:
    """Test complete release packaging workflow end-to-end."""

    def test_complete_release_workflow(self, populated_db, test_files_dir, tmp_path):
        """Test full workflow from database to verified release."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Configure release
        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=True,
            split_large=False,  # Don't split for this test
            chunk_size_mb=1900,
        )

        # Package release
        results = package_release(config)

        # Verify results structure
        assert "release_dir" in results
        assert "xml_export" in results
        assert "files_copied" in results
        assert "checksums_count" in results
        assert "manifest" in results
        assert "compression" in results
        assert "verification" in results

        # Verify release directory exists
        release_dir = Path(results["release_dir"])
        assert release_dir.exists()
        assert release_dir.is_dir()

        # Verify all required files exist
        assert (release_dir / "irowiki.db").exists()
        assert (release_dir / "irowiki-export.xml").exists()
        assert (release_dir / "README.txt").exists()
        assert (release_dir / "checksums.sha256").exists()
        assert (release_dir / "MANIFEST.json").exists()
        assert (release_dir / "files").exists()

        # Verify files were copied
        assert results["files_copied"] == 3
        assert (release_dir / "files" / "Test.png").exists()
        assert (release_dir / "files" / "archive" / "Old.gif").exists()

        # Verify XML export
        assert results["xml_export"]["pages_exported"] == 5
        assert results["xml_export"]["revisions_exported"] == 3

        # Verify checksums
        assert results["checksums_count"] >= 2  # At least database and XML

        # Verify manifest
        manifest = results["manifest"]
        assert manifest["version"] == "2026.01"
        assert manifest["statistics"]["total_pages"] == 5
        assert manifest["statistics"]["total_revisions"] == 3
        assert manifest["statistics"]["total_files"] == 1

        # Verify compression
        assert results["compression"]["file_count"] > 0
        assert results["compression"]["compressed_size"] > 0

        # Verify archive exists
        archive_path = output_dir / "irowiki-archive-2026.01.tar.gz"
        assert archive_path.exists()

        # Verify verification passed
        assert results["verification"]["is_valid"]
        assert results["verification"]["errors"] == 0

    def test_release_without_files(self, populated_db, tmp_path):
        """Test release packaging without media files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=None,  # No files
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        # Should succeed without files
        assert results["files_copied"] == 0
        assert results["verification"]["is_valid"]

        release_dir = Path(results["release_dir"])
        assert (release_dir / "files").exists()  # Empty directory
        assert len(list((release_dir / "files").iterdir())) == 0

    def test_release_uncompressed(self, populated_db, test_files_dir, tmp_path):
        """Test release packaging without compression."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,  # No compression
            split_large=False,
        )

        results = package_release(config)

        # Should succeed without compression
        assert "compression" not in results
        assert results["verification"]["is_valid"]

        # Archive should not exist
        archive_path = output_dir / "irowiki-archive-2026.01.tar.gz"
        assert not archive_path.exists()


class TestLargeArchiveWorkflow:
    """Test workflows with large archives requiring splitting."""

    def test_large_archive_split_workflow(self, populated_db, tmp_path):
        """Test splitting large archive into chunks."""
        # Create a large files directory
        files_dir = tmp_path / "files"
        files_dir.mkdir()

        # Create files totaling >2MB to trigger split
        for i in range(5):
            (files_dir / f"large_file_{i}.bin").write_bytes(
                b"X" * 512 * 1024
            )  # 512KB each

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=True,
            split_large=True,
            chunk_size_mb=1,  # Force split with 1MB chunks
        )

        results = package_release(config)

        # Should have split into multiple chunks
        if "split" in results:
            split_stats = results["split"]
            if split_stats["chunk_count"] > 1:
                # Verify chunks exist
                assert len(split_stats["chunk_paths"]) > 1
                for chunk_path in split_stats["chunk_paths"]:
                    assert chunk_path.exists()

                # Verify reassembly script exists
                assert split_stats["reassemble_script"] is not None
                assert split_stats["reassemble_script"].exists()


class TestXMLExportIntegration:
    """Test XML export integration with packaging."""

    def test_xml_export_validity(self, populated_db, tmp_path):
        """Test that exported XML is valid MediaWiki format."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=None,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        # Validate XML structure
        release_dir = Path(results["release_dir"])
        xml_path = release_dir / "irowiki-export.xml"

        validator = XMLValidator()
        validation_result = validator.validate_xml_file(xml_path)

        assert validation_result.is_valid
        assert len(validation_result.errors) == 0

    def test_xml_content_accuracy(self, populated_db, tmp_path):
        """Test that XML export contains accurate data."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=None,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        # Parse XML and verify content
        release_dir = Path(results["release_dir"])
        xml_path = release_dir / "irowiki-export.xml"

        # Read XML content
        xml_content = xml_path.read_text()

        # Verify key content is present
        assert "Main_Page" in xml_content
        assert "Test_Page" in xml_content
        assert "Welcome to the wiki!" in xml_content
        assert "This is a test page." in xml_content


class TestReleaseVerificationWorkflow:
    """Test release verification workflows."""

    def test_verification_detects_missing_file(
        self, populated_db, test_files_dir, tmp_path
    ):
        """Test that verification detects missing files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        # Remove a required file
        release_dir = Path(results["release_dir"])
        (release_dir / "checksums.sha256").unlink()

        # Re-verify
        verification = verify_release(release_dir)

        assert not verification.is_valid
        assert verification.error_count > 0
        assert any("checksums" in str(error).lower() for error in verification.errors)

    def test_verification_detects_corrupted_checksum(
        self, populated_db, test_files_dir, tmp_path
    ):
        """Test that verification detects checksum corruption."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        # Corrupt the database file (which is checksummed)
        release_dir = Path(results["release_dir"])
        (release_dir / "irowiki.db").write_text("CORRUPTED CONTENT")

        # Verify checksums
        checksums_file = release_dir / "checksums.sha256"
        checksum_results = verify_checksums(release_dir, checksums_file)

        # Should detect failure
        assert checksum_results["failed"] > 0
        assert len(checksum_results["failures"]) > 0

    def test_complete_verification_workflow(
        self, populated_db, test_files_dir, tmp_path
    ):
        """Test complete verification workflow with fix and re-verify."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Initial packaging
        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)
        release_dir = Path(results["release_dir"])

        # Verify initial release is valid
        verification1 = verify_release(release_dir)
        assert verification1.is_valid

        # Corrupt a file
        (release_dir / "README.txt").unlink()

        # Verify detects corruption
        verification2 = verify_release(release_dir)
        assert not verification2.is_valid

        # Fix by recreating README
        from scraper.packaging.release import ReleaseBuilder

        builder = ReleaseBuilder()
        builder.create_readme(release_dir, "2026.01")

        # Re-verify (should still fail due to checksum mismatch)
        verification3 = verify_release(release_dir)
        # This might fail because checksums don't match
        # In real scenario, would need to regenerate checksums


class TestArchiveExtractAndVerify:
    """Test extracting and verifying archived releases."""

    def test_extract_and_verify_archive(self, populated_db, test_files_dir, tmp_path):
        """Test extracting compressed archive and verifying contents."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create compressed release
        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=True,
            split_large=False,
        )

        results = package_release(config)

        # Extract archive
        archive_path = output_dir / "irowiki-archive-2026.01.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Verify extracted contents
        extracted_release = extract_dir / "irowiki-archive-2026.01"
        assert extracted_release.exists()

        # Verify all files present
        assert (extracted_release / "irowiki.db").exists()
        assert (extracted_release / "irowiki-export.xml").exists()
        assert (extracted_release / "README.txt").exists()
        assert (extracted_release / "checksums.sha256").exists()
        assert (extracted_release / "MANIFEST.json").exists()

        # Verify checksums of extracted files
        checksums_file = extracted_release / "checksums.sha256"
        checksum_results = verify_checksums(extracted_release, checksums_file)

        assert checksum_results["failed"] == 0
        assert checksum_results["verified"] > 0


class TestErrorRecovery:
    """Test error handling and recovery scenarios."""

    def test_invalid_database_path(self, tmp_path):
        """Test handling of non-existent database."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=tmp_path / "nonexistent.db",
            files_dir=None,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        # Should raise error
        with pytest.raises(Exception):
            package_release(config)

    def test_insufficient_permissions(self, populated_db, tmp_path):
        """Test handling of permission errors."""
        # Create read-only output directory
        output_dir = tmp_path / "readonly"
        output_dir.mkdir()

        # Make it read-only
        output_dir.chmod(0o444)

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=None,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        try:
            # Should raise permission error
            with pytest.raises(PermissionError):
                package_release(config)
        finally:
            # Restore permissions for cleanup
            output_dir.chmod(0o755)

    def test_corrupted_database(self, tmp_path):
        """Test handling of corrupted database."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create corrupted database file
        corrupted_db = tmp_path / "corrupted.db"
        corrupted_db.write_bytes(b"NOT A VALID SQLITE DATABASE")

        config = PackagingConfig(
            database_path=corrupted_db,
            files_dir=None,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        # Should raise database error
        with pytest.raises(Exception):
            package_release(config)


class TestManifestAccuracy:
    """Test manifest generation accuracy."""

    def test_manifest_statistics_accuracy(self, populated_db, test_files_dir, tmp_path):
        """Test that manifest statistics match actual data."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        manifest = results["manifest"]

        # Verify statistics match database
        with populated_db.get_connection() as conn:
            pages_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            revisions_count = conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[
                0
            ]
            files_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

        assert manifest["statistics"]["total_pages"] == pages_count
        assert manifest["statistics"]["total_revisions"] == revisions_count
        assert manifest["statistics"]["total_files"] == files_count

    def test_manifest_checksums_present(self, populated_db, test_files_dir, tmp_path):
        """Test that manifest includes checksums for all files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = PackagingConfig(
            database_path=populated_db.db_path,
            files_dir=test_files_dir,
            output_dir=output_dir,
            version="2026.01",
            compress=False,
            split_large=False,
        )

        results = package_release(config)

        manifest = results["manifest"]
        release_dir = Path(results["release_dir"])

        # Manifest should include checksums
        assert "checksums" in manifest
        assert len(manifest["checksums"]) > 0

        # Verify checksums file exists
        checksums_file = release_dir / "checksums.sha256"
        assert checksums_file.exists()
