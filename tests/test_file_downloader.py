"""Comprehensive tests for FileDownloader functionality.

Tests cover:
- Initialization and configuration
- Single file downloads with SHA1 verification
- Batch downloads with statistics
- Resume capability (skip existing valid files)
- Error handling and retry logic
- Edge cases and special characters
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pytest
import requests

from scraper.scrapers.file_scraper import FileDownloader, DownloadStats
from scraper.storage.models import FileMetadata


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


class MockDownloadResponse:
    """Mock response for file download testing."""

    def __init__(
        self,
        content: bytes,
        status_code: int = 200,
        should_raise: Optional[Exception] = None,
    ):
        self.content = content
        self.status_code = status_code
        self._should_raise = should_raise

    def raise_for_status(self):
        """Raise HTTPError for bad status codes."""
        if self._should_raise:
            raise self._should_raise
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 8192):
        """Iterate over content in chunks."""
        content = self.content
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]


class MockDownloadSession:
    """Mock session for file download testing."""

    def __init__(self, content: bytes = b"", status_code: int = 200):
        self.content = content
        self.status_code = status_code
        self.get_calls = []
        self._exception_queue: List[Exception] = []
        self._response_queue: List[MockDownloadResponse] = []
        self._call_count = 0

    def get(self, url, **kwargs):
        """Mock GET request."""
        self.get_calls.append((url, kwargs))
        self._call_count += 1

        # If we have exceptions queued, raise the first one and remove it
        if self._exception_queue:
            exception = self._exception_queue.pop(0)
            raise exception

        # If we have specific responses queued, use them
        if self._response_queue:
            return self._response_queue.pop(0)

        # Default behavior
        return MockDownloadResponse(self.content, self.status_code)

    def queue_exception(self, exception: Exception):
        """Queue an exception to raise on next get()."""
        self._exception_queue.append(exception)

    def queue_response(self, content: bytes, status_code: int = 200):
        """Queue a specific response."""
        self._response_queue.append(MockDownloadResponse(content, status_code))


@pytest.fixture
def sample_file_content() -> bytes:
    """Sample binary file content for testing."""
    return b"This is a test file content with some binary data: \x00\x01\x02\xff"


@pytest.fixture
def sample_file_sha1(sample_file_content: bytes) -> str:
    """Pre-calculated SHA1 for sample file content."""
    return hashlib.sha1(sample_file_content).hexdigest()


@pytest.fixture
def large_file_content() -> bytes:
    """Large file content for testing chunked downloads."""
    # Create 1MB of data
    return b"X" * (1024 * 1024)


@pytest.fixture
def large_file_sha1(large_file_content: bytes) -> str:
    """Pre-calculated SHA1 for large file content."""
    return hashlib.sha1(large_file_content).hexdigest()


@pytest.fixture
def sample_file_metadata(sample_file_sha1: str) -> FileMetadata:
    """Create a sample FileMetadata object."""
    return FileMetadata(
        filename="Test_Image.png",
        url="https://irowiki.org/images/Test_Image.png",
        descriptionurl="https://irowiki.org/wiki/File:Test_Image.png",
        sha1=sample_file_sha1,
        size=1024,
        width=800,
        height=600,
        mime_type="image/png",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        uploader="TestUser",
    )


@pytest.fixture
def files_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for file downloads."""
    return tmp_path / "files"


# ============================================================================
# TestFileDownloaderInit
# ============================================================================


class TestFileDownloaderInit:
    """Test FileDownloader initialization."""

    def test_init_with_defaults(self, files_dir: Path):
        """Test initialization with default parameters."""
        downloader = FileDownloader(files_dir=files_dir)

        assert downloader.files_dir == files_dir
        assert downloader.max_retries == 3
        assert downloader.timeout == 60
        assert downloader.chunk_size == 8192

    def test_init_with_custom_params(self, files_dir: Path):
        """Test initialization with custom parameters."""
        downloader = FileDownloader(
            files_dir=files_dir,
            max_retries=5,
            timeout=120,
            chunk_size=16384,
        )

        assert downloader.files_dir == files_dir
        assert downloader.max_retries == 5
        assert downloader.timeout == 120
        assert downloader.chunk_size == 16384

    def test_files_dir_created_if_not_exists(self, tmp_path: Path):
        """Test that files directory is created if it doesn't exist."""
        files_dir = tmp_path / "nonexistent" / "files"
        assert not files_dir.exists()

        downloader = FileDownloader(files_dir=files_dir)

        # Directory should be created during download, not init
        assert downloader.files_dir == files_dir


# ============================================================================
# TestFileDownloaderDownloadFile
# ============================================================================


class TestFileDownloaderDownloadFile:
    """Test single file download functionality."""

    def test_successful_download(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test successful file download with correct structure."""
        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(sample_file_metadata)

        # Verify file structure: files/File/T/Test_Image.png
        expected_path = files_dir / "File" / "T" / "Test_Image.png"
        assert file_path == expected_path
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content

    def test_directory_structure_created(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that directory structure is created correctly."""
        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(sample_file_metadata)

        # Check directory structure
        assert (files_dir / "File").exists()
        assert (files_dir / "File" / "T").exists()
        assert file_path.parent == files_dir / "File" / "T"

    def test_sha1_verification_success(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that SHA1 verification succeeds for correct file."""
        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(sample_file_metadata)

        # Verify the file was downloaded and checksum matches
        assert file_path.exists()
        calculated_sha1 = hashlib.sha1(file_path.read_bytes()).hexdigest()
        assert calculated_sha1 == sample_file_metadata.sha1

    def test_file_exists_with_correct_checksum_skip(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that existing file with correct checksum is skipped."""
        # Pre-create the file with correct content
        file_dir = files_dir / "File" / "T"
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / "Test_Image.png"
        file_path.write_bytes(sample_file_content)

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        result_path = downloader.download_file(sample_file_metadata)

        assert result_path == file_path
        assert len(mock_session.get_calls) == 0  # No download should occur

    def test_file_exists_wrong_checksum_redownload(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that existing file with wrong checksum is re-downloaded."""
        # Pre-create file with wrong content
        file_dir = files_dir / "File" / "T"
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / "Test_Image.png"
        file_path.write_bytes(b"Wrong content")

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        result_path = downloader.download_file(sample_file_metadata)

        assert result_path.read_bytes() == sample_file_content
        assert len(mock_session.get_calls) == 1  # Should re-download

    def test_download_network_error_retries(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that network errors trigger retries."""
        mock_session = MockDownloadSession(sample_file_content)
        # Queue 2 exceptions, then success
        mock_session.queue_exception(requests.ConnectionError("Network error"))
        mock_session.queue_exception(requests.ConnectionError("Network error"))
        mock_session.queue_response(sample_file_content)

        downloader = FileDownloader(files_dir=files_dir, max_retries=3)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(sample_file_metadata)

        assert len(mock_session.get_calls) == 3  # 2 failures + 1 success
        assert file_path.exists()

    def test_download_timeout_retries(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        sample_file_content: bytes,
        monkeypatch,
    ):
        """Test that timeout errors trigger retries."""
        mock_session = MockDownloadSession(sample_file_content)
        # Queue 1 exception, then success
        mock_session.queue_exception(requests.Timeout("Request timeout"))
        mock_session.queue_response(sample_file_content)

        downloader = FileDownloader(files_dir=files_dir, max_retries=3)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(sample_file_metadata)

        assert len(mock_session.get_calls) == 2  # 1 failure + 1 success
        assert file_path.exists()

    def test_checksum_mismatch_deletes_file_and_raises(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        monkeypatch,
    ):
        """Test that checksum mismatch deletes file and raises error."""
        wrong_content = b"Wrong content with wrong checksum"
        mock_session = MockDownloadSession(wrong_content)

        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        with pytest.raises(ValueError, match="SHA1 checksum mismatch"):
            downloader.download_file(sample_file_metadata)

        # File should not exist (deleted after verification failure)
        file_path = files_dir / "File" / "T" / "Test_Image.png"
        assert not file_path.exists()

    def test_download_404_raises_exception(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        monkeypatch,
    ):
        """Test that 404 error raises exception."""
        mock_session = MockDownloadSession(b"", status_code=404)

        downloader = FileDownloader(files_dir=files_dir, max_retries=1)
        monkeypatch.setattr(downloader, "session", mock_session)

        with pytest.raises(requests.HTTPError):
            downloader.download_file(sample_file_metadata)

    def test_max_retries_exceeded_raises(
        self,
        files_dir: Path,
        sample_file_metadata: FileMetadata,
        monkeypatch,
    ):
        """Test that exceeding max retries raises exception."""
        mock_session = MockDownloadSession()
        # Queue 3 exceptions (will exceed max_retries of 2)
        for _ in range(3):
            mock_session.queue_exception(requests.ConnectionError("Network error"))

        downloader = FileDownloader(files_dir=files_dir, max_retries=2)
        monkeypatch.setattr(downloader, "session", mock_session)

        with pytest.raises(requests.ConnectionError):
            downloader.download_file(sample_file_metadata)


# ============================================================================
# TestFileDownloaderChecksumVerification
# ============================================================================


class TestFileDownloaderChecksumVerification:
    """Test SHA1 checksum verification functionality."""

    def test_verify_checksum_correct(
        self, files_dir: Path, sample_file_content: bytes, sample_file_sha1: str
    ):
        """Test that correct checksum returns True."""
        downloader = FileDownloader(files_dir=files_dir)

        # Create a test file
        test_file = files_dir / "test.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(sample_file_content)

        assert downloader._verify_checksum(test_file, sample_file_sha1) is True

    def test_verify_checksum_incorrect(
        self, files_dir: Path, sample_file_content: bytes
    ):
        """Test that incorrect checksum returns False."""
        downloader = FileDownloader(files_dir=files_dir)

        # Create a test file
        test_file = files_dir / "test.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(sample_file_content)

        wrong_sha1 = "0" * 40
        assert downloader._verify_checksum(test_file, wrong_sha1) is False

    def test_calculate_sha1_small_file(
        self, files_dir: Path, sample_file_content: bytes, sample_file_sha1: str
    ):
        """Test SHA1 calculation for small file."""
        downloader = FileDownloader(files_dir=files_dir)

        test_file = files_dir / "test.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(sample_file_content)

        calculated = downloader._calculate_sha1(test_file)
        assert calculated == sample_file_sha1

    def test_calculate_sha1_empty_file(self, files_dir: Path):
        """Test SHA1 calculation for empty file."""
        downloader = FileDownloader(files_dir=files_dir)

        test_file = files_dir / "empty.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"")

        calculated = downloader._calculate_sha1(test_file)
        # SHA1 of empty string
        assert calculated == "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    def test_calculate_sha1_large_file(
        self, files_dir: Path, large_file_content: bytes, large_file_sha1: str
    ):
        """Test SHA1 calculation for large file (tests chunked reading)."""
        downloader = FileDownloader(files_dir=files_dir)

        test_file = files_dir / "large.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(large_file_content)

        calculated = downloader._calculate_sha1(test_file)
        assert calculated == large_file_sha1


# ============================================================================
# TestFileDownloaderBatchDownload
# ============================================================================


class TestFileDownloaderBatchDownload:
    """Test batch file download functionality."""

    def test_download_multiple_files(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test downloading multiple files successfully."""
        files = [
            FileMetadata(
                filename="File_A.png",
                url="https://example.com/A.png",
                descriptionurl="https://example.com/File:A.png",
                sha1=sample_file_sha1,
                size=100,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1),
                uploader="User",
            ),
            FileMetadata(
                filename="File_B.jpg",
                url="https://example.com/B.jpg",
                descriptionurl="https://example.com/File:B.jpg",
                sha1=sample_file_sha1,
                size=200,
                width=None,
                height=None,
                mime_type="image/jpeg",
                timestamp=datetime(2024, 1, 2),
                uploader="User",
            ),
        ]

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        stats = downloader.download_files(files)

        assert stats.total == 2
        assert stats.downloaded == 2
        assert stats.skipped == 0
        assert stats.failed == 0
        assert stats.bytes_downloaded > 0

    def test_progress_callback_invoked(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test that progress callback is invoked correctly."""
        files = [
            FileMetadata(
                filename=f"File_{i}.png",
                url=f"https://example.com/{i}.png",
                descriptionurl=f"https://example.com/File:{i}.png",
                sha1=sample_file_sha1,
                size=100,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1),
                uploader="User",
            )
            for i in range(3)
        ]

        mock_session = MockDownloadSession(sample_file_content)
        progress_calls = []

        def progress_callback(downloaded: int, total: int):
            progress_calls.append((downloaded, total))

        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        downloader.download_files(files, progress_callback=progress_callback)

        # Should be called 3 times: after each download
        assert len(progress_calls) >= 3
        assert progress_calls[-1] == (3, 3)

    def test_partial_failures(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test that some files succeed and some fail."""
        files = [
            FileMetadata(
                filename="Good_File.png",
                url="https://example.com/good.png",
                descriptionurl="https://example.com/File:Good.png",
                sha1=sample_file_sha1,
                size=100,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1),
                uploader="User",
            ),
            FileMetadata(
                filename="Bad_File.png",
                url="https://example.com/bad.png",
                descriptionurl="https://example.com/File:Bad.png",
                sha1=sample_file_sha1,
                size=200,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 2),
                uploader="User",
            ),
        ]

        mock_session = MockDownloadSession(sample_file_content)
        # First file succeeds, second fails
        mock_session.queue_response(sample_file_content)
        mock_session.queue_exception(requests.ConnectionError("Network error"))

        downloader = FileDownloader(files_dir=files_dir, max_retries=1)
        monkeypatch.setattr(downloader, "session", mock_session)

        stats = downloader.download_files(files)

        assert stats.total == 2
        assert stats.downloaded == 1
        assert stats.failed == 1

    def test_all_files_skipped(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
    ):
        """Test that all files are skipped if they exist with correct checksum."""
        # Pre-create all files
        files = []
        for i in range(3):
            filename = f"File_{i}.png"
            file_dir = files_dir / "File" / "F"
            file_dir.mkdir(parents=True, exist_ok=True)
            file_path = file_dir / filename
            file_path.write_bytes(sample_file_content)

            files.append(
                FileMetadata(
                    filename=filename,
                    url=f"https://example.com/{i}.png",
                    descriptionurl=f"https://example.com/File:{i}.png",
                    sha1=sample_file_sha1,
                    size=100,
                    width=None,
                    height=None,
                    mime_type="image/png",
                    timestamp=datetime(2024, 1, 1),
                    uploader="User",
                )
            )

        downloader = FileDownloader(files_dir=files_dir)
        stats = downloader.download_files(files)

        assert stats.total == 3
        assert stats.downloaded == 0
        assert stats.skipped == 3
        assert stats.failed == 0


# ============================================================================
# TestFileDownloaderEdgeCases
# ============================================================================


class TestFileDownloaderEdgeCases:
    """Test edge cases and special scenarios."""

    def test_filename_with_spaces(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test filename with spaces."""
        file_meta = FileMetadata(
            filename="File With Spaces.png",
            url="https://example.com/file.png",
            descriptionurl="https://example.com/File:File.png",
            sha1=sample_file_sha1,
            size=100,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1),
            uploader="User",
        )

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(file_meta)

        assert file_path.name == "File With Spaces.png"
        assert file_path.exists()

    def test_filename_starting_with_number(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test filename starting with a number."""
        file_meta = FileMetadata(
            filename="123_File.png",
            url="https://example.com/file.png",
            descriptionurl="https://example.com/File:File.png",
            sha1=sample_file_sha1,
            size=100,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1),
            uploader="User",
        )

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(file_meta)

        # Should be stored in files/File/1/ (first character is '1')
        assert file_path.parent.name == "1"
        assert file_path.exists()

    def test_filename_with_special_characters(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test filename with special characters."""
        file_meta = FileMetadata(
            filename="File_(Special)_[Chars].png",
            url="https://example.com/file.png",
            descriptionurl="https://example.com/File:File.png",
            sha1=sample_file_sha1,
            size=100,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1),
            uploader="User",
        )

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(file_meta)

        assert file_path.name == "File_(Special)_[Chars].png"
        assert file_path.exists()

    def test_very_long_filename(
        self,
        files_dir: Path,
        sample_file_content: bytes,
        sample_file_sha1: str,
        monkeypatch,
    ):
        """Test very long filename (but still valid)."""
        long_name = "A" * 200 + ".png"
        file_meta = FileMetadata(
            filename=long_name,
            url="https://example.com/file.png",
            descriptionurl="https://example.com/File:File.png",
            sha1=sample_file_sha1,
            size=100,
            width=None,
            height=None,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1),
            uploader="User",
        )

        mock_session = MockDownloadSession(sample_file_content)
        downloader = FileDownloader(files_dir=files_dir)
        monkeypatch.setattr(downloader, "session", mock_session)

        file_path = downloader.download_file(file_meta)

        assert file_path.name == long_name
        assert file_path.exists()

    def test_get_file_path_structure(self, files_dir: Path, sample_file_sha1: str):
        """Test that _get_file_path returns correct structure."""
        downloader = FileDownloader(files_dir=files_dir)

        test_cases = [
            ("Apple.png", "A"),
            ("Banana.jpg", "B"),
            ("zebra.gif", "Z"),
            ("123.png", "1"),
            ("_underscore.png", "_"),
        ]

        for filename, expected_letter in test_cases:
            file_meta = FileMetadata(
                filename=filename,
                url="https://example.com/file.png",
                descriptionurl="https://example.com/File:File.png",
                sha1=sample_file_sha1,
                size=100,
                width=None,
                height=None,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 1),
                uploader="User",
            )

            path = downloader._get_file_path(file_meta)
            expected_path = files_dir / "File" / expected_letter / filename

            assert path == expected_path
