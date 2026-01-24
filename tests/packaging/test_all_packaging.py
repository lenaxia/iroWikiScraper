"""Comprehensive tests for packaging modules."""

import json
import tarfile
from pathlib import Path

import pytest

from scraper.packaging.checksums import (
    generate_checksums,
    verify_checksums,
    write_checksums_file,
)
from scraper.packaging.compression import compress_directory, split_archive
from scraper.packaging.manifest import ManifestGenerator
from scraper.packaging.release import ReleaseBuilder
from scraper.packaging.release_notes import ReleaseNotesGenerator
from scraper.packaging.verify import verify_release
from scraper.storage.database import Database


@pytest.fixture
def test_db(tmp_path):
    """Create test database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.initialize_schema()

    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (1, 0, 'Test', 0)"
        )
        conn.execute("""
            INSERT INTO revisions (revision_id, page_id, parent_id, timestamp,
                user, user_id, comment, content, size, sha1, minor, tags)
            VALUES (1, 1, NULL, '2024-01-01T00:00:00', 'User', 1, 'Test', 'Content', 7, 
                    'abc123def456789012345678901234567890abcd', 0, NULL)
            """)
        conn.commit()

    return db


class TestReleaseBuilder:
    """Test ReleaseBuilder."""

    def test_create_release_directory(self, tmp_path):
        """Test creating release directory."""
        builder = ReleaseBuilder()
        release_dir = builder.create_release_directory("2026.01", tmp_path)

        assert release_dir.exists()
        assert release_dir.is_dir()
        assert release_dir.name == "irowiki-archive-2026.01"
        assert (release_dir / "files").exists()

    def test_copy_database(self, tmp_path, test_db):
        """Test copying database."""
        builder = ReleaseBuilder()
        release_dir = builder.create_release_directory("2026.01", tmp_path)

        db_copy = builder.copy_database(test_db.db_path, release_dir)

        assert db_copy.exists()
        assert db_copy.name == "irowiki.db"
        assert db_copy.stat().st_size > 0

    def test_copy_files(self, tmp_path):
        """Test copying files."""
        # Create source files
        files_dir = tmp_path / "source_files"
        files_dir.mkdir()
        (files_dir / "test1.txt").write_text("test1")
        (files_dir / "subdir").mkdir()
        (files_dir / "subdir" / "test2.txt").write_text("test2")

        builder = ReleaseBuilder()
        release_dir = builder.create_release_directory("2026.01", tmp_path / "output")

        count = builder.copy_files(files_dir, release_dir)

        assert count == 2
        assert (release_dir / "files" / "test1.txt").exists()
        assert (release_dir / "files" / "subdir" / "test2.txt").exists()

    def test_create_readme(self, tmp_path):
        """Test creating README."""
        builder = ReleaseBuilder()
        release_dir = builder.create_release_directory("2026.01", tmp_path)

        readme_path = builder.create_readme(release_dir, "2026.01")

        assert readme_path.exists()
        content = readme_path.read_text()
        assert "2026.01" in content
        assert "iRO Wiki Archive" in content


class TestCompression:
    """Test compression functions."""

    def test_compress_directory(self, tmp_path):
        """Test compressing directory."""
        # Create source directory
        source_dir = tmp_path / "irowiki-archive-2026.01"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file.txt").write_text("file content")

        output_tar = tmp_path / "archive.tar.gz"

        stats = compress_directory(source_dir, output_tar)

        assert output_tar.exists()
        assert stats["compressed_size"] > 0
        assert stats["file_count"] == 2
        assert stats["compression_ratio"] > 0  # Can be >1 for small files

    def test_split_archive_not_needed(self, tmp_path):
        """Test splitting when archive is small."""
        # Create small archive
        archive_path = tmp_path / "small.tar.gz"
        archive_path.write_bytes(b"small data")

        stats = split_archive(archive_path, chunk_size_mb=1)

        assert stats["chunk_count"] == 1
        assert stats["chunk_paths"] == [archive_path]

    def test_split_archive_needed(self, tmp_path):
        """Test splitting large archive."""
        # Create "large" archive (2MB)
        archive_path = tmp_path / "large.tar.gz"
        archive_path.write_bytes(b"x" * (2 * 1024 * 1024))

        stats = split_archive(archive_path, chunk_size_mb=1)

        assert stats["chunk_count"] == 2
        assert len(stats["chunk_paths"]) == 2
        assert stats["reassemble_script"] is not None
        assert stats["reassemble_script"].exists()


class TestChecksums:
    """Test checksum functions."""

    def test_generate_checksums(self, tmp_path):
        """Test generating checksums."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        checksums = generate_checksums(tmp_path)

        assert len(checksums) == 2
        assert "file1.txt" in checksums
        assert "file2.txt" in checksums
        assert len(checksums["file1.txt"]) == 64  # SHA256 is 64 hex chars

    def test_write_checksums_file(self, tmp_path):
        """Test writing checksums file."""
        checksums = {
            "file1.txt": "a" * 64,
            "file2.txt": "b" * 64,
        }

        output_path = tmp_path / "checksums.sha256"
        write_checksums_file(checksums, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "file1.txt" in content
        assert "file2.txt" in content
        assert "a" * 64 in content

    def test_verify_checksums_pass(self, tmp_path):
        """Test verifying checksums (success)."""
        # Create files
        (tmp_path / "file1.txt").write_text("content1")

        # Generate and write checksums
        checksums = generate_checksums(tmp_path)
        checksums_file = tmp_path / "checksums.sha256"
        write_checksums_file(checksums, checksums_file)

        # Verify
        results = verify_checksums(tmp_path, checksums_file)

        assert results["verified"] == 1
        assert results["failed"] == 0
        assert results["missing"] == 0

    def test_verify_checksums_fail(self, tmp_path):
        """Test verifying checksums (failure)."""
        # Create file and checksums
        file_path = tmp_path / "file1.txt"
        file_path.write_text("original")

        checksums = generate_checksums(tmp_path)
        checksums_file = tmp_path / "checksums.sha256"
        write_checksums_file(checksums, checksums_file)

        # Modify file
        file_path.write_text("modified")

        # Verify
        results = verify_checksums(tmp_path, checksums_file)

        assert results["verified"] == 0
        assert results["failed"] == 1
        assert len(results["failures"]) == 1


class TestManifest:
    """Test manifest generation."""

    def test_generate_manifest(self, tmp_path, test_db):
        """Test generating manifest."""
        release_dir = tmp_path / "irowiki-archive-2026.01"
        release_dir.mkdir()

        # Create dummy files
        (release_dir / "irowiki.db").write_bytes(b"x" * 1000)
        (release_dir / "irowiki-export.xml").write_bytes(b"x" * 500)

        generator = ManifestGenerator(test_db)
        manifest = generator.generate_manifest("2026.01", release_dir)

        assert manifest["version"] == "2026.01"
        assert "statistics" in manifest
        assert manifest["statistics"]["total_pages"] == 1
        assert manifest["statistics"]["total_revisions"] == 1

    def test_write_manifest(self, tmp_path, test_db):
        """Test writing manifest to file."""
        release_dir = tmp_path / "release"
        release_dir.mkdir()

        generator = ManifestGenerator(test_db)
        manifest = generator.generate_manifest("2026.01", release_dir)

        output_path = tmp_path / "MANIFEST.json"
        generator.write_manifest(manifest, output_path)

        assert output_path.exists()

        # Verify it's valid JSON
        with open(output_path, "r") as f:
            loaded = json.load(f)
        assert loaded["version"] == "2026.01"


class TestVerify:
    """Test release verification."""

    def test_verify_release_missing_directory(self, tmp_path):
        """Test verifying non-existent directory."""
        report = verify_release(tmp_path / "nonexistent")

        assert not report.is_valid
        assert report.error_count > 0

    def test_verify_release_missing_files(self, tmp_path):
        """Test verifying release with missing files."""
        release_dir = tmp_path / "release"
        release_dir.mkdir()

        report = verify_release(release_dir)

        assert not report.is_valid
        assert report.error_count >= 5  # Missing required files

    def test_verify_release_complete(self, tmp_path, test_db):
        """Test verifying complete release."""
        release_dir = tmp_path / "irowiki-archive-2026.01"
        release_dir.mkdir()
        (release_dir / "files").mkdir()

        # Create required files
        (release_dir / "irowiki.db").write_bytes(test_db.db_path.read_bytes())
        (release_dir / "README.txt").write_text("README")

        # Create XML export
        from scraper.export.xml_exporter import XMLExporter

        exporter = XMLExporter(test_db)
        exporter.export_to_file(release_dir / "irowiki-export.xml", show_progress=False)

        # Generate checksums
        checksums = generate_checksums(release_dir)
        write_checksums_file(checksums, release_dir / "checksums.sha256")

        # Generate manifest
        generator = ManifestGenerator(test_db)
        manifest = generator.generate_manifest("2026.01", release_dir, checksums)
        generator.write_manifest(manifest, release_dir / "MANIFEST.json")

        # Verify
        report = verify_release(release_dir)

        assert report.is_valid or report.error_count == 0


class TestReleaseNotes:
    """Test release notes generation."""

    def test_generate_release_notes_no_previous(self, test_db):
        """Test generating release notes without previous release."""
        generator = ReleaseNotesGenerator(test_db)
        notes = generator.generate_release_notes("2026.01")

        assert "2026.01" in notes
        assert "Statistics" in notes
        assert "Total Pages" in notes

    def test_generate_release_notes_with_previous(self, tmp_path, test_db):
        """Test generating release notes with previous release."""
        # Create previous manifest
        previous_manifest = {
            "version": "2025.12",
            "statistics": {
                "total_pages": 0,
                "total_revisions": 0,
                "total_files": 0,
            },
        }
        prev_path = tmp_path / "prev_MANIFEST.json"
        with open(prev_path, "w") as f:
            json.dump(previous_manifest, f)

        generator = ReleaseNotesGenerator(test_db)
        notes = generator.generate_release_notes("2026.01", prev_path)

        assert "2026.01" in notes
        assert "Changes Since Last Release" in notes
        assert "+1" in notes  # 1 new page

    def test_write_release_notes(self, tmp_path, test_db):
        """Test writing release notes to file."""
        generator = ReleaseNotesGenerator(test_db)
        notes = generator.generate_release_notes("2026.01")

        output_path = tmp_path / "RELEASE_NOTES.md"
        generator.write_release_notes(notes, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "2026.01" in content
