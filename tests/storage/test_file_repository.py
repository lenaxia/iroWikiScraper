"""
Test File CRUD operations (Story 09).

Tests the FileRepository class for:
- Insert file
- Batch insert
- Get by filename
- Find by SHA1
- List files
- Update/delete file
- Count files
- NULL dimension handling
"""

from datetime import datetime

import pytest

from scraper.storage.file_repository import FileRepository
from scraper.storage.models import FileMetadata


class TestFileInsertion:
    """Test file insertion operations."""

    def test_insert_file(self, db, sample_files):
        """Test inserting single file."""
        repo = FileRepository(db)
        file = sample_files[0]

        repo.insert_file(file)

        # Verify inserted
        loaded = repo.get_file(file.filename)
        assert loaded is not None
        assert loaded.filename == file.filename
        assert loaded.sha1 == file.sha1

    def test_insert_file_with_dimensions(self, db):
        """Test inserting file with width/height."""
        repo = FileRepository(db)

        file = FileMetadata(
            filename="Image.png",
            url="https://example.com/Image.png",
            descriptionurl="https://example.com/wiki/File:Image.png",
            sha1="a" * 40,
            size=100000,
            width=1920,
            height=1080,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="User",
        )

        repo.insert_file(file)

        loaded = repo.get_file("Image.png")
        assert loaded.width == 1920
        assert loaded.height == 1080

    def test_insert_file_without_dimensions(self, db):
        """Test inserting file without dimensions (non-image)."""
        repo = FileRepository(db)

        file = FileMetadata(
            filename="Document.pdf",
            url="https://example.com/Document.pdf",
            descriptionurl="https://example.com/wiki/File:Document.pdf",
            sha1="b" * 40,
            size=50000,
            width=None,  # No dimensions for PDFs
            height=None,
            mime_type="application/pdf",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="User",
        )

        repo.insert_file(file)

        loaded = repo.get_file("Document.pdf")
        assert loaded.width is None
        assert loaded.height is None

    def test_insert_files_batch(self, db, sample_files):
        """Test batch insert."""
        repo = FileRepository(db)

        repo.insert_files_batch(sample_files)

        count = repo.count_files()
        assert count == 2


class TestFileRetrieval:
    """Test file retrieval operations."""

    def test_get_file_exists(self, db, sample_files):
        """Test get file by filename when it exists."""
        repo = FileRepository(db)
        repo.insert_files_batch(sample_files)

        loaded = repo.get_file("Example.png")
        assert loaded is not None
        assert loaded.filename == "Example.png"

    def test_get_file_not_exists(self, db):
        """Test get file by filename when it doesn't exist."""
        repo = FileRepository(db)

        loaded = repo.get_file("NonexistentFile.png")
        assert loaded is None

    def test_find_by_sha1(self, db):
        """Test finding files by SHA1 hash."""
        repo = FileRepository(db)

        # Insert two files with same SHA1 (duplicates)
        file1 = FileMetadata(
            filename="File1.png",
            url="https://example.com/File1.png",
            descriptionurl="https://example.com/wiki/File:File1.png",
            sha1="a" * 40,
            size=100,
            width=100,
            height=100,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="User1",
        )

        file2 = FileMetadata(
            filename="File2.png",
            url="https://example.com/File2.png",
            descriptionurl="https://example.com/wiki/File:File2.png",
            sha1="a" * 40,  # Same SHA1 (duplicate content)
            size=100,
            width=100,
            height=100,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            uploader="User2",
        )

        repo.insert_file(file1)
        repo.insert_file(file2)

        # Find duplicates by SHA1
        duplicates = repo.find_by_sha1("a" * 40)
        assert len(duplicates) == 2
        filenames = {f.filename for f in duplicates}
        assert "File1.png" in filenames
        assert "File2.png" in filenames

    def test_find_by_sha1_no_matches(self, db):
        """Test finding files by SHA1 with no matches."""
        repo = FileRepository(db)

        results = repo.find_by_sha1("z" * 40)
        assert len(results) == 0

    def test_list_files(self, db, sample_files):
        """Test listing files."""
        repo = FileRepository(db)
        repo.insert_files_batch(sample_files)

        files = repo.list_files()
        assert len(files) == 2

    def test_list_files_pagination(self, db):
        """Test pagination."""
        repo = FileRepository(db)

        # Insert 50 files
        files = [
            FileMetadata(
                filename=f"File{i:03d}.png",
                url=f"https://example.com/File{i:03d}.png",
                descriptionurl=f"https://example.com/wiki/File:File{i:03d}.png",
                sha1=f"{i:040d}",
                size=1000,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            )
            for i in range(1, 51)
        ]
        repo.insert_files_batch(files)

        # First page
        page1 = repo.list_files(limit=20, offset=0)
        assert len(page1) == 20

        # Second page
        page2 = repo.list_files(limit=20, offset=20)
        assert len(page2) == 20

        # No overlap
        names1 = {f.filename for f in page1}
        names2 = {f.filename for f in page2}
        assert len(names1 & names2) == 0

    def test_list_files_by_mime_type(self, db):
        """Test list files filtered by MIME type."""
        repo = FileRepository(db)

        files = [
            FileMetadata(
                filename="Image.png",
                url="https://example.com/Image.png",
                descriptionurl="https://example.com/wiki/File:Image.png",
                sha1="a" * 40,
                size=1000,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            ),
            FileMetadata(
                filename="Photo.jpg",
                url="https://example.com/Photo.jpg",
                descriptionurl="https://example.com/wiki/File:Photo.jpg",
                sha1="b" * 40,
                size=1000,
                width=100,
                height=100,
                mime_type="image/jpeg",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            ),
            FileMetadata(
                filename="Doc.pdf",
                url="https://example.com/Doc.pdf",
                descriptionurl="https://example.com/wiki/File:Doc.pdf",
                sha1="c" * 40,
                size=5000,
                width=None,
                height=None,
                mime_type="application/pdf",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            ),
        ]
        repo.insert_files_batch(files)

        # List PNG files
        pngs = repo.list_files(mime_type="image/png")
        assert len(pngs) == 1
        assert pngs[0].filename == "Image.png"

        # List JPEGs
        jpegs = repo.list_files(mime_type="image/jpeg")
        assert len(jpegs) == 1

        # List PDFs
        pdfs = repo.list_files(mime_type="application/pdf")
        assert len(pdfs) == 1


class TestFileUpdate:
    """Test file update operations."""

    def test_update_file(self, db):
        """Test updating existing file."""
        repo = FileRepository(db)

        file = FileMetadata(
            filename="File.png",
            url="https://example.com/File.png",
            descriptionurl="https://example.com/wiki/File:File.png",
            sha1="a" * 40,
            size=1000,
            width=100,
            height=100,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="OriginalUser",
        )

        repo.insert_file(file)

        # Update file
        updated = FileMetadata(
            filename="File.png",
            url="https://example.com/File.png",
            descriptionurl="https://example.com/wiki/File:File.png",
            sha1="b" * 40,  # Changed
            size=2000,  # Changed
            width=200,  # Changed
            height=200,  # Changed
            mime_type="image/png",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            uploader="UpdatedUser",  # Changed
        )

        repo.update_file(updated)

        # Verify update
        loaded = repo.get_file("File.png")
        assert loaded.sha1 == "b" * 40
        assert loaded.size == 2000
        assert loaded.uploader == "UpdatedUser"


class TestFileDeletion:
    """Test file deletion operations."""

    def test_delete_file(self, db):
        """Test deleting file by filename."""
        repo = FileRepository(db)

        file = FileMetadata(
            filename="ToDelete.png",
            url="https://example.com/ToDelete.png",
            descriptionurl="https://example.com/wiki/File:ToDelete.png",
            sha1="a" * 40,
            size=1000,
            width=100,
            height=100,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="User",
        )

        repo.insert_file(file)

        # Verify it exists
        assert repo.get_file("ToDelete.png") is not None

        # Delete it
        repo.delete_file("ToDelete.png")

        # Verify deleted
        assert repo.get_file("ToDelete.png") is None

    def test_delete_nonexistent_file(self, db):
        """Test deleting nonexistent file doesn't raise error."""
        repo = FileRepository(db)

        # Should not raise error
        repo.delete_file("NonexistentFile.png")


class TestFileCount:
    """Test file counting operations."""

    def test_count_files_empty(self, db):
        """Test count on empty database."""
        repo = FileRepository(db)

        count = repo.count_files()
        assert count == 0

    def test_count_files_all(self, db, sample_files):
        """Test count all files."""
        repo = FileRepository(db)
        repo.insert_files_batch(sample_files)

        count = repo.count_files()
        assert count == 2

    def test_count_files_by_mime_type(self, db):
        """Test count files by MIME type."""
        repo = FileRepository(db)

        files = [
            FileMetadata(
                filename=f"Image{i}.png",
                url=f"https://example.com/Image{i}.png",
                descriptionurl=f"https://example.com/wiki/File:Image{i}.png",
                sha1=f"{i:040d}",
                size=1000,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            )
            for i in range(1, 4)
        ]

        files.append(
            FileMetadata(
                filename="Doc.pdf",
                url="https://example.com/Doc.pdf",
                descriptionurl="https://example.com/wiki/File:Doc.pdf",
                sha1="f" * 40,  # Valid hex string
                size=5000,
                width=None,
                height=None,
                mime_type="application/pdf",
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                uploader="User",
            )
        )

        repo.insert_files_batch(files)

        assert repo.count_files(mime_type="image/png") == 3
        assert repo.count_files(mime_type="application/pdf") == 1
        assert repo.count_files() == 4


class TestFileDataConversion:
    """Test FileMetadata dataclass <-> database row conversion."""

    def test_roundtrip_conversion(self, db):
        """Test that all fields survive roundtrip conversion."""
        repo = FileRepository(db)

        original = FileMetadata(
            filename="TestFile.png",
            url="https://example.com/TestFile.png",
            descriptionurl="https://example.com/wiki/File:TestFile.png",
            sha1="abcdef1234567890abcdef1234567890abcdef12",
            size=123456,
            width=1920,
            height=1080,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            uploader="TestUploader",
        )

        repo.insert_file(original)
        loaded = repo.get_file("TestFile.png")

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
