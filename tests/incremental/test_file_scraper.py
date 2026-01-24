"""Tests for IncrementalFileScraper."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scraper.incremental.file_scraper import IncrementalFileScraper
from scraper.incremental.models import FileChangeSet, FileInfo
from scraper.storage.models import FileMetadata


@pytest.fixture
def temp_download_dir(tmp_path):
    """Create temporary download directory."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


@pytest.fixture
def file_scraper(db, temp_download_dir):
    """Create IncrementalFileScraper with mocked API."""
    mock_api = Mock()
    scraper = IncrementalFileScraper(mock_api, db, temp_download_dir)
    return scraper


@pytest.fixture
def sample_file_infos():
    """Sample FileInfo objects from API."""
    return [
        FileInfo(
            title="File1.png",
            sha1="a" * 40,
            size=1000,
            url="https://example.com/File1.png",
            timestamp=datetime(2026, 1, 1, 10, 0, 0),
        ),
        FileInfo(
            title="File2.jpg",
            sha1="b" * 40,
            size=2000,
            url="https://example.com/File2.jpg",
            timestamp=datetime(2026, 1, 2, 10, 0, 0),
        ),
        FileInfo(
            title="File3.pdf",
            sha1="c" * 40,
            size=5000,
            url="https://example.com/File3.pdf",
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
        ),
    ]


class TestIncrementalFileScraper:
    """Tests for IncrementalFileScraper initialization and basic operations."""

    def test_init(self, db, temp_download_dir):
        """Test initialization."""
        mock_api = Mock()
        scraper = IncrementalFileScraper(mock_api, db, temp_download_dir)

        assert scraper.api is mock_api
        assert scraper.db is db
        assert scraper.download_dir == temp_download_dir
        assert scraper.file_repo is not None
        assert scraper.file_discovery is not None
        assert scraper.file_downloader is not None

    def test_detect_file_changes_all_new(self, file_scraper, sample_file_infos):
        """Test detecting changes when all files are new."""
        # Mock API to return files
        with patch.object(
            file_scraper, "_fetch_all_files_from_api", return_value=sample_file_infos
        ):
            changes = file_scraper.detect_file_changes()

        assert len(changes.new_files) == 3
        assert len(changes.modified_files) == 0
        assert len(changes.deleted_files) == 0
        assert changes.total_changes == 3

    def test_detect_file_changes_no_changes(self, file_scraper, db, sample_file_infos):
        """Test detecting changes when no files changed."""
        from scraper.storage.file_repository import FileRepository

        # Insert files into database
        file_repo = FileRepository(db)
        for file_info in sample_file_infos:
            file_meta = FileMetadata(
                filename=file_info.title,
                url=file_info.url,
                descriptionurl=f"https://example.com/wiki/File:{file_info.title}",
                sha1=file_info.sha1,
                size=file_info.size,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=file_info.timestamp,
                uploader="TestUser",
            )
            file_repo.insert_file(file_meta)

        # Mock API to return same files
        with patch.object(
            file_scraper, "_fetch_all_files_from_api", return_value=sample_file_infos
        ):
            changes = file_scraper.detect_file_changes()

        assert len(changes.new_files) == 0
        assert len(changes.modified_files) == 0
        assert len(changes.deleted_files) == 0
        assert changes.total_changes == 0

    def test_detect_file_changes_modified_sha1(
        self, file_scraper, db, sample_file_infos
    ):
        """Test detecting modified files (SHA1 changed)."""
        from scraper.storage.file_repository import FileRepository

        # Insert files with different SHA1
        file_repo = FileRepository(db)
        for file_info in sample_file_infos:
            file_meta = FileMetadata(
                filename=file_info.title,
                url=file_info.url,
                descriptionurl=f"https://example.com/wiki/File:{file_info.title}",
                sha1="0" + "1" * 39,  # 40 chars total, different from sample
                size=file_info.size,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=file_info.timestamp,
                uploader="TestUser",
            )
            file_repo.insert_file(file_meta)

        # Mock API to return files with new SHA1
        with patch.object(
            file_scraper, "_fetch_all_files_from_api", return_value=sample_file_infos
        ):
            changes = file_scraper.detect_file_changes()

        assert len(changes.new_files) == 0
        assert len(changes.modified_files) == 3  # All 3 modified
        assert len(changes.deleted_files) == 0

    def test_detect_file_changes_deleted_files(
        self, file_scraper, db, sample_file_infos
    ):
        """Test detecting deleted files."""
        from scraper.storage.file_repository import FileRepository

        # Insert extra file that won't be in API response
        file_repo = FileRepository(db)
        deleted_file = FileMetadata(
            filename="Deleted.png",
            url="https://example.com/Deleted.png",
            descriptionurl="https://example.com/wiki/File:Deleted.png",
            sha1="d" * 40,
            size=999,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2020, 1, 1),
            uploader="TestUser",
        )
        file_repo.insert_file(deleted_file)

        # Mock API to return only sample files (not deleted file)
        with patch.object(
            file_scraper, "_fetch_all_files_from_api", return_value=sample_file_infos
        ):
            changes = file_scraper.detect_file_changes()

        assert len(changes.new_files) == 3  # Sample files are new
        assert len(changes.modified_files) == 0
        assert len(changes.deleted_files) == 1
        assert "Deleted.png" in changes.deleted_files

    def test_detect_file_changes_mixed_scenario(
        self, file_scraper, db, sample_file_infos
    ):
        """Test detecting mixed changes (new, modified, deleted)."""
        from scraper.storage.file_repository import FileRepository

        file_repo = FileRepository(db)

        # Insert File1 (will be unchanged - same SHA1)
        file1_meta = FileMetadata(
            filename="File1.png",
            url="https://example.com/File1.png",
            descriptionurl="https://example.com/wiki/File:File1.png",
            sha1="a" * 40,  # Same SHA1
            size=1000,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2026, 1, 1, 10, 0, 0),
            uploader="TestUser",
        )
        file_repo.insert_file(file1_meta)

        # Insert File2 with different SHA1 (will be modified)
        file2_meta = FileMetadata(
            filename="File2.jpg",
            url="https://example.com/File2.jpg",
            descriptionurl="https://example.com/wiki/File:File2.jpg",
            sha1="0123456789abcdef" * 2 + "01234567",  # Different SHA1
            size=2000,
            width=None,
            height=None,
            mime_type="image/jpeg",
            timestamp=datetime(2026, 1, 2, 10, 0, 0),
            uploader="TestUser",
        )
        file_repo.insert_file(file2_meta)

        # Insert File4 that will be deleted
        file4_meta = FileMetadata(
            filename="File4_Deleted.png",
            url="https://example.com/File4.png",
            descriptionurl="https://example.com/wiki/File:File4.png",
            sha1="d" * 40,
            size=999,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2020, 1, 1),
            uploader="TestUser",
        )
        file_repo.insert_file(file4_meta)

        # File3 will be new (not in database)

        # Mock API to return sample files
        with patch.object(
            file_scraper, "_fetch_all_files_from_api", return_value=sample_file_infos
        ):
            changes = file_scraper.detect_file_changes()

        # File1: unchanged, File2: modified, File3: new, File4: deleted
        assert len(changes.new_files) == 1  # File3
        assert changes.new_files[0].title == "File3.pdf"

        assert len(changes.modified_files) == 1  # File2
        assert changes.modified_files[0].title == "File2.jpg"

        assert len(changes.deleted_files) == 1  # File4
        assert "File4_Deleted.png" in changes.deleted_files


class TestFileDownloading:
    """Tests for downloading files."""

    def test_download_new_files_empty_changeset(self, file_scraper):
        """Test downloading with empty change set."""
        changes = FileChangeSet()

        downloaded = file_scraper.download_new_files(changes)

        assert downloaded == 0

    def test_download_new_files_success(self, file_scraper, sample_file_infos):
        """Test successful download of new files."""
        changes = FileChangeSet(new_files=sample_file_infos[:2])  # 2 files

        # Mock downloader and database update
        with patch.object(file_scraper.file_downloader, "download_file"):
            with patch.object(file_scraper, "_update_database_file"):
                downloaded = file_scraper.download_new_files(changes)

        assert downloaded == 2

    def test_download_modified_files(self, file_scraper, sample_file_infos):
        """Test downloading modified files."""
        changes = FileChangeSet(modified_files=sample_file_infos)

        # Mock downloader and database update
        with patch.object(file_scraper.file_downloader, "download_file"):
            with patch.object(file_scraper, "_update_database_file"):
                downloaded = file_scraper.download_new_files(changes)

        assert downloaded == 3

    def test_download_continues_on_failure(self, file_scraper, sample_file_infos):
        """Test that download continues even if individual files fail."""
        changes = FileChangeSet(new_files=sample_file_infos)

        # Mock downloader to fail on second file
        def mock_download(file_meta):
            if file_meta.filename == "File2.jpg":
                raise Exception("Download failed")

        with patch.object(
            file_scraper.file_downloader, "download_file", side_effect=mock_download
        ):
            with patch.object(file_scraper, "_update_database_file"):
                downloaded = file_scraper.download_new_files(changes)

        # Should download 2 out of 3 (File2 failed)
        assert downloaded == 2


class TestDatabaseUpdates:
    """Tests for database update operations."""

    def test_update_database_file_new_file(self, file_scraper, db):
        """Test inserting new file into database."""
        from scraper.storage.file_repository import FileRepository

        file_meta = FileMetadata(
            filename="NewFile.png",
            url="https://example.com/NewFile.png",
            descriptionurl="https://example.com/wiki/File:NewFile.png",
            sha1="a" * 40,
            size=1000,
            width=800,
            height=600,
            mime_type="image/png",
            timestamp=datetime(2026, 1, 1),
            uploader="TestUser",
        )

        file_scraper._update_database_file(file_meta)

        # Verify in database
        file_repo = FileRepository(db)
        retrieved = file_repo.get_file("NewFile.png")

        assert retrieved is not None
        assert retrieved.filename == "NewFile.png"
        assert retrieved.sha1 == "a" * 40

    def test_update_database_file_existing_file(self, file_scraper, db):
        """Test updating existing file in database."""
        from scraper.storage.file_repository import FileRepository

        file_repo = FileRepository(db)

        # Insert initial file
        initial_file = FileMetadata(
            filename="ExistingFile.png",
            url="https://example.com/ExistingFile.png",
            descriptionurl="https://example.com/wiki/File:ExistingFile.png",
            sha1="0123456789abcdef" * 2 + "01234567",
            size=1000,
            width=800,
            height=600,
            mime_type="image/png",
            timestamp=datetime(2020, 1, 1),
            uploader="OldUser",
        )
        file_repo.insert_file(initial_file)

        # Update with new SHA1
        updated_file = FileMetadata(
            filename="ExistingFile.png",
            url="https://example.com/ExistingFile.png",
            descriptionurl="https://example.com/wiki/File:ExistingFile.png",
            sha1="fedcba9876543210" * 2 + "fedcba98",
            size=2000,
            width=1024,
            height=768,
            mime_type="image/png",
            timestamp=datetime(2026, 1, 1),
            uploader="NewUser",
        )

        file_scraper._update_database_file(updated_file)

        # Verify updated
        retrieved = file_repo.get_file("ExistingFile.png")

        assert retrieved is not None
        assert retrieved.sha1 == "fedcba9876543210" * 2 + "fedcba98"
        assert retrieved.size == 2000


class TestFileInfoConversion:
    """Tests for FileInfo conversion."""

    def test_file_info_to_metadata(self, file_scraper):
        """Test converting FileInfo to FileMetadata."""
        file_info = FileInfo(
            title="Test.png",
            sha1="a" * 40,
            size=5000,
            url="https://example.com/Test.png",
            timestamp=datetime(2026, 1, 1),
        )

        file_meta = file_scraper._file_info_to_metadata(file_info)

        assert file_meta.filename == "Test.png"
        assert file_meta.sha1 == "a" * 40
        assert file_meta.size == 5000
        assert file_meta.url == "https://example.com/Test.png"
        assert file_meta.timestamp == datetime(2026, 1, 1)


class TestMarkDeletedFiles:
    """Tests for marking deleted files."""

    def test_mark_deleted_files(self, file_scraper, db):
        """Test marking files as deleted."""
        from scraper.storage.file_repository import FileRepository

        file_repo = FileRepository(db)

        # Insert files
        for i in range(3):
            file_meta = FileMetadata(
                filename=f"File{i}.png",
                url=f"https://example.com/File{i}.png",
                descriptionurl=f"https://example.com/wiki/File:File{i}.png",
                sha1=f"{i:040d}",
                size=1000 * i,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2026, 1, i + 1),
                uploader="TestUser",
            )
            file_repo.insert_file(file_meta)

        assert file_repo.count_files() == 3

        # Mark 2 files as deleted
        file_scraper._mark_deleted_files(["File0.png", "File2.png"])

        # Verify deleted (removed from database)
        assert file_repo.count_files() == 1
        assert file_repo.get_file("File0.png") is None
        assert file_repo.get_file("File1.png") is not None  # Still exists
        assert file_repo.get_file("File2.png") is None

    def test_mark_deleted_files_empty_list(self, file_scraper, db):
        """Test marking deleted with empty list."""
        # Should not crash
        file_scraper._mark_deleted_files([])
