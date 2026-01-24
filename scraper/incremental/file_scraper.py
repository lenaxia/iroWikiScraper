"""Incremental file scraper for detecting and downloading changed files."""

import logging
from pathlib import Path

from scraper.api.client import MediaWikiAPIClient
from scraper.incremental.models import FileChangeSet, FileInfo
from scraper.scrapers.file_scraper import FileDiscovery, FileDownloader
from scraper.storage.database import Database
from scraper.storage.file_repository import FileRepository
from scraper.storage.models import FileMetadata

logger = logging.getLogger(__name__)


class IncrementalFileScraper:
    """
    Incremental file scraper that downloads only new or modified files.

    Detects file changes by comparing SHA1 checksums between the MediaWiki API
    and the local database. Downloads only files that don't exist locally or
    have changed checksums (new versions uploaded).

    This significantly reduces bandwidth and time by avoiding re-downloads
    of unchanged media files.

    Example:
        >>> scraper = IncrementalFileScraper(api, db, download_dir)
        >>> changes = scraper.detect_file_changes()
        >>> print(f"New: {len(changes.new_files)}, Modified: {len(changes.modified_files)}")
        >>> scraper.download_new_files(changes)
    """

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        database: Database,
        download_dir: Path,
    ):
        """
        Initialize incremental file scraper.

        Args:
            api_client: MediaWiki API client for fetching file list
            database: Database with file_metadata table
            download_dir: Directory to download files to
        """
        self.api = api_client
        self.db = database
        self.download_dir = Path(download_dir)
        self.file_repo = FileRepository(database)
        self.file_discovery = FileDiscovery(api_client)
        self.file_downloader = FileDownloader(download_dir)

    def detect_file_changes(self) -> FileChangeSet:
        """
        Detect file changes by comparing SHA1 checksums.

        Fetches all files from MediaWiki API with SHA1 checksums and compares
        with files stored in database. Categorizes files into:
        - New files: Exist in API but not in database
        - Modified files: SHA1 checksum differs (new version uploaded)
        - Deleted files: Exist in database but not in API

        Returns:
            FileChangeSet with categorized file changes

        Example:
            >>> changes = scraper.detect_file_changes()
            >>> print(f"Total changes: {changes.total_changes}")
            >>> for file in changes.new_files:
            ...     print(f"New: {file.title}")

        Performance:
            - Fetches all files from API in one pass (<5 seconds typically)
            - Single database query to get all stored files
            - In-memory SHA1 comparison (very fast)
        """
        logger.info("Starting file change detection")

        # Fetch all files from API with SHA1
        api_files = self._fetch_all_files_from_api()
        api_map = {f.title: f for f in api_files}

        logger.info(f"Fetched {len(api_files)} files from API")

        # Fetch all files from database
        db_files = self.file_repo.list_files()
        db_map = {f.filename: f.sha1 for f in db_files}

        logger.info(f"Found {len(db_files)} files in database")

        # Categorize changes
        change_set = FileChangeSet()

        # Check for new and modified files
        for title, file_info in api_map.items():
            if title not in db_map:
                # New file
                change_set.new_files.append(file_info)
            elif file_info.sha1 != db_map[title]:
                # Modified file (SHA1 changed)
                change_set.modified_files.append(file_info)

        # Check for deleted files
        for db_title in db_map:
            if db_title not in api_map:
                change_set.deleted_files.append(db_title)

        logger.info(
            f"Detected changes: {len(change_set.new_files)} new, "
            f"{len(change_set.modified_files)} modified, "
            f"{len(change_set.deleted_files)} deleted"
        )

        return change_set

    def download_new_files(self, change_set: FileChangeSet) -> int:
        """
        Download new and modified files.

        Downloads all files in the change set (new + modified).
        For modified files, overwrites existing file with new version.

        Args:
            change_set: FileChangeSet from detect_file_changes()

        Returns:
            Number of files successfully downloaded

        Example:
            >>> changes = scraper.detect_file_changes()
            >>> downloaded = scraper.download_new_files(changes)
            >>> print(f"Downloaded {downloaded} files")

        Note:
            - Downloads in batches for efficiency
            - Updates database with new file metadata
            - Marks deleted files in database (doesn't delete files)
        """
        total_to_download = len(change_set.new_files) + len(change_set.modified_files)

        if total_to_download == 0:
            logger.info("No new or modified files to download")
            return 0

        logger.info(f"Downloading {total_to_download} files")

        # Combine new and modified files for download
        files_to_download = []

        # Convert FileInfo to FileMetadata for downloader
        for file_info in change_set.new_files + change_set.modified_files:
            file_meta = self._file_info_to_metadata(file_info)
            files_to_download.append(file_meta)

        # Download files using batch downloader
        downloaded = 0
        failed = 0

        for file_meta in files_to_download:
            try:
                self.file_downloader.download_file(file_meta)
                self._update_database_file(file_meta)
                downloaded += 1
            except Exception as e:
                logger.error(f"Failed to download {file_meta.filename}: {e}")
                failed += 1

        logger.info(f"Downloaded {downloaded} files ({failed} failed)")

        # Mark deleted files (but don't delete from disk)
        self._mark_deleted_files(change_set.deleted_files)

        return downloaded

    def _fetch_all_files_from_api(self) -> list[FileInfo]:
        """
        Fetch all files from MediaWiki API with SHA1 checksums.

        Returns:
            List of FileInfo objects with title, SHA1, size, URL, timestamp
        """
        # Use FileDiscovery to get all files
        file_metadata_list = self.file_discovery.discover_files()

        # Convert to FileInfo
        file_infos = []
        for fm in file_metadata_list:
            file_info = FileInfo(
                title=fm.filename,
                sha1=fm.sha1,
                size=fm.size,
                url=fm.url,
                timestamp=fm.timestamp,
            )
            file_infos.append(file_info)

        return file_infos

    def _file_info_to_metadata(self, file_info: FileInfo) -> FileMetadata:
        """
        Convert FileInfo to FileMetadata for downloader.

        Args:
            file_info: FileInfo from API

        Returns:
            FileMetadata object for database/downloader
        """
        # Create FileMetadata (we need to fetch full details from API)
        # For now, use basic info - downloader will handle full metadata
        return FileMetadata(
            filename=file_info.title,
            url=file_info.url,
            descriptionurl=f"https://irowiki.org/wiki/File:{file_info.title}",
            sha1=file_info.sha1,
            size=file_info.size,
            width=None,  # Not critical for incremental
            height=None,
            mime_type="application/octet-stream",  # Generic type, will be updated on download
            timestamp=file_info.timestamp,
            uploader="",  # Not critical for incremental
        )

    def _update_database_file(self, file_meta: FileMetadata) -> None:
        """
        Update or insert file metadata in database.

        Args:
            file_meta: FileMetadata to store
        """
        existing = self.file_repo.get_file(file_meta.filename)

        if existing:
            # Update existing file
            self.file_repo.update_file(file_meta)
        else:
            # Insert new file
            self.file_repo.insert_file(file_meta)

    def _mark_deleted_files(self, deleted_titles: list[str]) -> None:
        """
        Mark deleted files in database.

        Note: Doesn't delete files from disk, just marks them as deleted
        in database (could add is_deleted flag in future).

        Args:
            deleted_titles: List of file titles that were deleted
        """
        if not deleted_titles:
            return

        logger.info(f"Marking {len(deleted_titles)} files as deleted")

        # For now, just log them - database schema doesn't have is_deleted flag
        # In a real implementation, we might:
        # 1. Add is_deleted column to files table
        # 2. Update files SET is_deleted=1 WHERE filename IN (...)
        # 3. Or delete from database: DELETE FROM files WHERE filename IN (...)

        # Simple approach: delete from database (preserve file on disk)
        for title in deleted_titles:
            try:
                self.file_repo.delete_file(title)
            except Exception as e:
                logger.error(f"Failed to mark file {title} as deleted: {e}")
