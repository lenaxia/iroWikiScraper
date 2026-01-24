"""File discovery and download functionality.

This module provides functionality to discover all uploaded media files
on a MediaWiki wiki using the allimages API endpoint, and to download
files with SHA1 verification and retry logic.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

import requests

from scraper.api.client import MediaWikiAPIClient
from scraper.api.pagination import PaginatedQuery
from scraper.storage.models import FileMetadata

logger = logging.getLogger(__name__)


class FileDiscovery:
    """Discovers all uploaded files on the wiki.

    Uses MediaWiki's allimages API to iterate through all uploaded files
    with pagination support. Handles images, videos, PDFs, and other media types.

    Attributes:
        api: MediaWiki API client instance
        batch_size: Number of files per API request (max 500)
        progress_interval: Log progress every N files

    Example:
        >>> from scraper.api.client import MediaWikiAPIClient
        >>> api = MediaWikiAPIClient("https://irowiki.org")
        >>> discovery = FileDiscovery(api)
        >>> files = discovery.discover_files()
        >>> len(files)
        4000
        >>> files[0].filename
        'Example.png'
    """

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        batch_size: int = 500,
        progress_interval: int = 100,
    ) -> None:
        """Initialize file discovery.

        Args:
            api_client: MediaWiki API client instance
            batch_size: Files per API request (max 500, default 500)
            progress_interval: Log progress every N files (default 100)

        Example:
            >>> api = MediaWikiAPIClient("https://irowiki.org")
            >>> discovery = FileDiscovery(api, batch_size=250, progress_interval=50)
        """
        self.api = api_client
        # Cap batch_size at API maximum of 500
        self.batch_size = min(max(batch_size, 1), 500)
        self.progress_interval = progress_interval

    def discover_files(self) -> List[FileMetadata]:
        """Discover all files uploaded to the wiki.

        Uses the allimages API with pagination to fetch all file metadata.
        Handles images (with dimensions), videos, PDFs, and other media types.

        Returns:
            List of FileMetadata objects for all discovered files

        Raises:
            APIError: If the API request fails

        Example:
            >>> discovery = FileDiscovery(api)
            >>> files = discovery.discover_files()
            >>> len(files)
            4000
            >>> # Filter for images only
            >>> images = [f for f in files if f.mime_type.startswith('image/')]
            >>> len(images)
            3800
        """
        files: List[FileMetadata] = []

        logger.info("Starting file discovery")

        # Set up pagination parameters
        params = {
            "list": "allimages",
            "ailimit": self.batch_size,
            "aiprop": "url|size|sha1|mime|timestamp|user|dimensions",
            "aisort": "name",
            "aidir": "ascending",
        }

        # Create paginated query
        query = PaginatedQuery(
            api_client=self.api,
            initial_params=params,
            result_path=["query", "allimages"],
            progress_callback=self._progress_callback,
        )

        # Iterate through all results
        for file_data in query:
            try:
                file_metadata = self._parse_file_data(file_data)
                files.append(file_metadata)

                # Log progress at intervals
                if len(files) % self.progress_interval == 0:
                    logger.info(f"Discovered {len(files)} files so far...")

            except Exception as e:
                logger.error(
                    f"Failed to parse file data: {file_data}. Error: {e}",
                    exc_info=True,
                )
                # Continue with other files
                continue

        logger.info(f"File discovery complete: {len(files)} total files discovered")
        return files

    def _parse_file_data(self, file_data: Dict[str, Any]) -> FileMetadata:
        """Parse raw API response data into FileMetadata object.

        Uses defensive parsing with .get() to handle missing optional fields.

        Args:
            file_data: Raw file data dictionary from API response

        Returns:
            FileMetadata object

        Raises:
            ValueError: If required fields are missing or invalid
            KeyError: If required fields are missing

        Example:
            >>> data = {
            ...     'name': 'Example.png',
            ...     'url': 'https://irowiki.org/images/Example.png',
            ...     'descriptionurl': 'https://irowiki.org/wiki/File:Example.png',
            ...     'sha1': 'abc123...',
            ...     'size': 123456,
            ...     'width': 800,
            ...     'height': 600,
            ...     'mime': 'image/png',
            ...     'timestamp': '2024-01-15T10:30:00Z',
            ...     'user': 'Uploader'
            ... }
            >>> file = self._parse_file_data(data)
            >>> file.filename
            'Example.png'
        """
        # Parse timestamp from ISO format
        timestamp_str = file_data["timestamp"]
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")

        # Use defensive parsing with .get() for optional fields
        # width and height may not be present for non-images (videos, PDFs, etc.)
        width = file_data.get("width")
        height = file_data.get("height")

        # User may be empty string for deleted users
        uploader = file_data.get("user", "")

        return FileMetadata(
            filename=file_data["name"],
            url=file_data["url"],
            descriptionurl=file_data["descriptionurl"],
            sha1=file_data["sha1"],
            size=file_data["size"],
            width=width,
            height=height,
            mime_type=file_data["mime"],
            timestamp=timestamp,
            uploader=uploader,
        )

    def _progress_callback(self, batch_num: int, items_count: int) -> None:
        """Callback invoked by PaginatedQuery after each batch.

        Args:
            batch_num: Current batch number (1-indexed)
            items_count: Number of items in this batch

        Example:
            >>> # Called automatically by PaginatedQuery
            >>> # Logs: "Batch 1: Retrieved 500 files"
        """
        logger.info(f"Batch {batch_num}: Retrieved {items_count} files")


@dataclass
class DownloadStats:
    """Statistics for batch file downloads.

    Attributes:
        total: Total number of files to download
        downloaded: Number of files successfully downloaded
        skipped: Number of files skipped (already exist with correct checksum)
        failed: Number of files that failed to download
        bytes_downloaded: Total bytes downloaded

    Example:
        >>> stats = DownloadStats(total=100, downloaded=95, skipped=3, failed=2, bytes_downloaded=1024000)
        >>> stats.downloaded
        95
    """

    total: int
    downloaded: int
    skipped: int
    failed: int
    bytes_downloaded: int


class FileDownloader:
    """Downloads files from MediaWiki with SHA1 verification and retry logic.

    Handles file downloading with streaming, checksum verification, directory
    organization, resume capability, and automatic retry on transient failures.

    Files are organized in subdirectories by first letter:
        files/File/A/Apple.png
        files/File/B/Banana.jpg
        files/File/1/123.png

    Attributes:
        files_dir: Base directory for downloaded files
        max_retries: Maximum number of retry attempts for failed downloads
        timeout: HTTP request timeout in seconds
        chunk_size: Size of chunks for streaming downloads

    Example:
        >>> from pathlib import Path
        >>> from scraper.storage.models import FileMetadata
        >>> from datetime import datetime
        >>>
        >>> files_dir = Path("./files")
        >>> downloader = FileDownloader(files_dir=files_dir, max_retries=3)
        >>>
        >>> file_meta = FileMetadata(
        ...     filename="Example.png",
        ...     url="https://example.com/Example.png",
        ...     descriptionurl="https://example.com/File:Example.png",
        ...     sha1="abc123...",
        ...     size=1024,
        ...     width=800,
        ...     height=600,
        ...     mime_type="image/png",
        ...     timestamp=datetime(2024, 1, 15),
        ...     uploader="User"
        ... )
        >>>
        >>> # Download single file
        >>> path = downloader.download_file(file_meta)
        >>> path
        PosixPath('files/File/E/Example.png')
        >>>
        >>> # Download multiple files with progress tracking
        >>> def progress(downloaded, total):
        ...     print(f"Progress: {downloaded}/{total}")
        >>> stats = downloader.download_files([file_meta], progress_callback=progress)
        >>> stats.downloaded
        1
    """

    def __init__(
        self,
        files_dir: Path,
        max_retries: int = 3,
        timeout: int = 60,
        chunk_size: int = 8192,
    ) -> None:
        """Initialize file downloader.

        Args:
            files_dir: Base directory for downloaded files
            max_retries: Maximum retry attempts for failed downloads (default 3)
            timeout: HTTP request timeout in seconds (default 60)
            chunk_size: Size of chunks for streaming downloads (default 8192)

        Example:
            >>> files_dir = Path("./files")
            >>> downloader = FileDownloader(
            ...     files_dir=files_dir,
            ...     max_retries=5,
            ...     timeout=120,
            ...     chunk_size=16384
            ... )
        """
        self.files_dir = files_dir
        self.max_retries = max_retries
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.session = requests.Session()

    def download_file(self, file_meta: FileMetadata) -> Path:
        """Download a single file with SHA1 verification.

        Downloads the file to the appropriate subdirectory based on the first
        letter of the filename. If the file already exists with the correct
        checksum, the download is skipped (resume capability).

        Args:
            file_meta: File metadata containing URL and checksum

        Returns:
            Path to the downloaded file

        Raises:
            ValueError: If SHA1 checksum verification fails
            requests.HTTPError: If HTTP request fails (404, 500, etc.)
            requests.ConnectionError: If network connection fails after retries
            requests.Timeout: If request times out after retries

        Example:
            >>> file_meta = FileMetadata(
            ...     filename="Example.png",
            ...     url="https://example.com/Example.png",
            ...     descriptionurl="https://example.com/File:Example.png",
            ...     sha1="abc123...",
            ...     size=1024,
            ...     width=800,
            ...     height=600,
            ...     mime_type="image/png",
            ...     timestamp=datetime(2024, 1, 15),
            ...     uploader="User"
            ... )
            >>> downloader = FileDownloader(files_dir=Path("./files"))
            >>> path = downloader.download_file(file_meta)
            >>> path.exists()
            True
        """
        file_path = self._get_file_path(file_meta)

        # Check if file already exists with correct checksum (resume capability)
        if file_path.exists():
            if self._verify_checksum(file_path, file_meta.sha1):
                logger.debug(
                    f"File already exists with correct checksum, skipping: {file_meta.filename}"
                )
                return file_path
            else:
                logger.warning(
                    f"File exists but checksum mismatch, re-downloading: {file_meta.filename}"
                )

        # Create directory structure
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Download with retry logic
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Downloading {file_meta.filename} (attempt {attempt + 1}/{self.max_retries})"
                )

                # Download with streaming
                response = self.session.get(
                    file_meta.url, stream=True, timeout=self.timeout
                )
                response.raise_for_status()

                # Write to file in chunks
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)

                logger.debug(f"Downloaded {file_meta.filename} successfully")

                # Verify checksum
                if not self._verify_checksum(file_path, file_meta.sha1):
                    # Delete corrupted file
                    file_path.unlink()
                    raise ValueError(
                        f"SHA1 checksum mismatch for {file_meta.filename}. "
                        f"Expected: {file_meta.sha1}, "
                        f"Got: {self._calculate_sha1(file_path) if file_path.exists() else 'file deleted'}"
                    )

                logger.info(f"Verified checksum for {file_meta.filename}")
                return file_path

            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Failed to download {file_meta.filename} after {self.max_retries} attempts: {e}"
                    )
                    raise

                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    f"Download failed for {file_meta.filename}, "
                    f"retrying in {wait_time}s ({attempt + 1}/{self.max_retries}): {e}"
                )
                time.sleep(wait_time)

        # Should never reach here due to raise in loop
        raise RuntimeError(f"Failed to download {file_meta.filename}")

    def download_files(
        self,
        files: List[FileMetadata],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadStats:
        """Download multiple files with progress tracking.

        Downloads files in sequence, tracking statistics and optionally
        invoking a progress callback after each file.

        Args:
            files: List of file metadata to download
            progress_callback: Optional callback(downloaded_count, total_count)
                invoked after each file is processed

        Returns:
            DownloadStats object with download statistics

        Example:
            >>> files = [file_meta1, file_meta2, file_meta3]
            >>> def progress(current, total):
            ...     print(f"Downloaded {current}/{total} files")
            >>> stats = downloader.download_files(files, progress_callback=progress)
            Downloaded 1/3 files
            Downloaded 2/3 files
            Downloaded 3/3 files
            >>> stats.downloaded
            3
            >>> stats.failed
            0
        """
        stats = DownloadStats(
            total=len(files),
            downloaded=0,
            skipped=0,
            failed=0,
            bytes_downloaded=0,
        )

        logger.info(f"Starting batch download of {len(files)} files")

        for i, file_meta in enumerate(files, 1):
            try:
                file_path = self._get_file_path(file_meta)
                file_existed = file_path.exists()
                file_size_before = file_path.stat().st_size if file_existed else 0

                # Download file (will skip if already valid)
                result_path = self.download_file(file_meta)

                # Check if file was actually downloaded or skipped
                if file_existed and file_size_before == result_path.stat().st_size:
                    stats.skipped += 1
                else:
                    stats.downloaded += 1
                    stats.bytes_downloaded += result_path.stat().st_size

            except Exception as e:
                stats.failed += 1
                logger.error(
                    f"Failed to download {file_meta.filename}: {e}", exc_info=True
                )

            # Invoke progress callback
            if progress_callback:
                progress_callback(i, len(files))

        logger.info(
            f"Batch download complete: {stats.downloaded} downloaded, "
            f"{stats.skipped} skipped, {stats.failed} failed"
        )

        return stats

    def _verify_checksum(self, file_path: Path, expected_sha1: str) -> bool:
        """Verify file SHA1 checksum.

        Args:
            file_path: Path to file to verify
            expected_sha1: Expected SHA1 hash (40 character hex string)

        Returns:
            True if checksum matches, False otherwise

        Example:
            >>> file_path = Path("test.bin")
            >>> file_path.write_bytes(b"test content")
            >>> downloader = FileDownloader(files_dir=Path("."))
            >>> downloader._verify_checksum(file_path, "expected_sha1")
            False
        """
        actual_sha1 = self._calculate_sha1(file_path)
        matches = actual_sha1 == expected_sha1

        if matches:
            logger.debug(f"Checksum verified for {file_path.name}")
        else:
            logger.warning(
                f"Checksum mismatch for {file_path.name}: "
                f"expected {expected_sha1}, got {actual_sha1}"
            )

        return matches

    def _calculate_sha1(self, file_path: Path) -> str:
        """Calculate SHA1 hash of a file.

        Reads file in chunks to support large files without loading
        entire file into memory.

        Args:
            file_path: Path to file to hash

        Returns:
            SHA1 hash as lowercase hex string (40 characters)

        Example:
            >>> file_path = Path("test.bin")
            >>> file_path.write_bytes(b"test")
            >>> downloader = FileDownloader(files_dir=Path("."))
            >>> downloader._calculate_sha1(file_path)
            'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3'
        """
        sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            while chunk := f.read(self.chunk_size):
                sha1.update(chunk)
        return sha1.hexdigest()

    def _get_file_path(self, file_meta: FileMetadata) -> Path:
        """Determine the file path based on filename.

        Files are organized in subdirectories by first character:
            files/File/A/Apple.png
            files/File/B/Banana.jpg
            files/File/1/123.png

        Args:
            file_meta: File metadata containing filename

        Returns:
            Path where file should be stored

        Example:
            >>> downloader = FileDownloader(files_dir=Path("./files"))
            >>> file_meta = FileMetadata(
            ...     filename="Apple.png",
            ...     url="https://example.com/Apple.png",
            ...     descriptionurl="https://example.com/File:Apple.png",
            ...     sha1="abc123" + "0" * 34,
            ...     size=1024,
            ...     width=800,
            ...     height=600,
            ...     mime_type="image/png",
            ...     timestamp=datetime(2024, 1, 15),
            ...     uploader="User"
            ... )
            >>> downloader._get_file_path(file_meta)
            PosixPath('files/File/A/Apple.png')
        """
        # Get first character of filename (uppercase)
        first_char = file_meta.filename[0].upper()

        # Build path: files/File/{first_char}/{filename}
        file_dir = self.files_dir / "File" / first_char
        file_path = file_dir / file_meta.filename

        return file_path
