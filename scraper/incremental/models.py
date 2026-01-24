"""Data models for incremental update functionality."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set


@dataclass
class MovedPage:
    """
    Represents a page that was moved/renamed.

    Attributes:
        page_id: Page ID
        old_title: Previous page title
        new_title: New page title
        namespace: Namespace ID
        timestamp: When the move occurred
    """

    page_id: int
    old_title: str
    new_title: str
    namespace: int
    timestamp: datetime


@dataclass
class ChangeSet:
    """
    Result of change detection, categorizing all changes since last scrape.

    Attributes:
        new_page_ids: Pages created since last scrape (need full scrape)
        modified_page_ids: Pages edited since last scrape (need revision update)
        deleted_page_ids: Pages deleted since last scrape (mark as deleted)
        moved_pages: Pages that were renamed/moved
        last_scrape_time: Timestamp used for change detection
        detection_time: When change detection was performed
        requires_full_scrape: True if this is the first scrape
    """

    new_page_ids: Set[int] = field(default_factory=set)
    modified_page_ids: Set[int] = field(default_factory=set)
    deleted_page_ids: Set[int] = field(default_factory=set)
    moved_pages: List[MovedPage] = field(default_factory=list)
    last_scrape_time: Optional[datetime] = None
    detection_time: datetime = field(default_factory=datetime.utcnow)
    requires_full_scrape: bool = False

    @property
    def total_changes(self) -> int:
        """Total number of unique pages affected by changes."""
        return (
            len(self.new_page_ids)
            + len(self.modified_page_ids)
            + len(self.deleted_page_ids)
            + len(self.moved_pages)
        )

    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return self.total_changes > 0 or self.requires_full_scrape

    def __repr__(self) -> str:
        return (
            f"ChangeSet(new={len(self.new_page_ids)}, "
            f"modified={len(self.modified_page_ids)}, "
            f"deleted={len(self.deleted_page_ids)}, "
            f"moved={len(self.moved_pages)}, "
            f"full_scrape={self.requires_full_scrape})"
        )


@dataclass
class PageUpdateInfo:
    """
    Information about a page's current state for incremental updates.

    Used to determine which revisions to fetch from the API.

    Attributes:
        page_id: Page ID in database
        namespace: Namespace ID
        title: Page title
        is_redirect: Whether page is currently a redirect
        highest_revision_id: Highest revision ID stored in database
        last_revision_timestamp: Timestamp of most recent revision stored
        total_revisions_stored: Count of revisions in database
    """

    page_id: int
    namespace: int
    title: str
    is_redirect: bool
    highest_revision_id: int
    last_revision_timestamp: datetime
    total_revisions_stored: int

    @property
    def needs_update(self) -> bool:
        """Always True for modified pages (why else would we query?)"""
        return True

    def get_revision_filter(self) -> Dict[str, Any]:
        """
        Get API parameters to fetch only new revisions.

        Returns:
            Dict of parameters for MediaWiki revisions API

        Example:
            >>> info = detector.get_page_update_info(123)
            >>> params = info.get_revision_filter()
            >>> # params = {'rvstartid': 100000, 'rvdir': 'newer'}
        """
        return {
            "rvstartid": self.highest_revision_id + 1,  # Start after last known
            "rvdir": "newer",  # Fetch newer revisions
        }

    def __repr__(self) -> str:
        return (
            f"PageUpdateInfo(page_id={self.page_id}, title={self.title}, "
            f"highest_rev={self.highest_revision_id}, "
            f"total_revs={self.total_revisions_stored})"
        )


@dataclass
class NewPageInfo:
    """
    Information about a newly created page for incremental scraping.

    Unlike PageUpdateInfo (for modified pages), this has minimal metadata
    since the page doesn't exist in our database yet.

    Attributes:
        page_id: Page ID from MediaWiki
        namespace: Namespace ID
        title: Page title
        detected_at: When we discovered this new page
    """

    page_id: int
    namespace: int
    title: str
    detected_at: datetime

    @property
    def needs_full_scrape(self) -> bool:
        """New pages always need full scrape of all revisions."""
        return True

    def to_scrape_params(self) -> Dict[str, Any]:
        """
        Get API parameters for scraping this new page.

        Returns:
            Dict of parameters for MediaWiki API

        Example:
            >>> info = NewPageInfo(123, 0, "New_Page", datetime.now())
            >>> params = info.to_scrape_params()
            >>> # params = {'pageids': 123, 'rvdir': 'newer'}
        """
        return {
            "pageids": self.page_id,
            "rvdir": "newer",  # Oldest revisions first
            "rvlimit": 500,  # Get all revisions (new pages typically have few)
        }

    def __repr__(self) -> str:
        return f"NewPageInfo(page_id={self.page_id}, title={self.title}, namespace={self.namespace})"


@dataclass
class IncrementalStats:
    """
    Statistics from an incremental scrape run.

    Tracks progress and performance metrics for incremental updates.

    Attributes:
        pages_new: Number of new pages scraped
        pages_modified: Number of modified pages updated
        pages_deleted: Number of pages marked as deleted
        pages_moved: Number of pages with title changes
        revisions_added: Total number of new revisions added
        files_downloaded: Number of files downloaded
        start_time: When incremental scrape started
        end_time: When incremental scrape completed
        api_calls: Total API calls made
    """

    pages_new: int = 0
    pages_modified: int = 0
    pages_deleted: int = 0
    pages_moved: int = 0
    revisions_added: int = 0
    files_downloaded: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    api_calls: int = 0

    @property
    def total_pages_affected(self) -> int:
        """Total number of pages affected by changes."""
        return (
            self.pages_new + self.pages_modified + self.pages_deleted + self.pages_moved
        )

    @property
    def duration(self) -> timedelta:
        """Duration of incremental scrape."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return timedelta(0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary for logging/storage."""
        return {
            "pages_new": self.pages_new,
            "pages_modified": self.pages_modified,
            "pages_deleted": self.pages_deleted,
            "pages_moved": self.pages_moved,
            "revisions_added": self.revisions_added,
            "files_downloaded": self.files_downloaded,
            "duration_seconds": self.duration.total_seconds(),
            "api_calls": self.api_calls,
            "total_pages": self.total_pages_affected,
        }

    def __repr__(self) -> str:
        return (
            f"IncrementalStats(new={self.pages_new}, modified={self.pages_modified}, "
            f"deleted={self.pages_deleted}, revisions={self.revisions_added})"
        )


@dataclass
class FileInfo:
    """
    Information about a file from the MediaWiki API.

    Used for file change detection by comparing SHA1 checksums.

    Attributes:
        title: File title (e.g., "Example.png")
        sha1: SHA1 checksum of file content
        size: File size in bytes
        url: Direct URL to download file
        timestamp: When file was last modified/uploaded
    """

    title: str
    sha1: str
    size: int
    url: str
    timestamp: datetime

    def __repr__(self) -> str:
        return (
            f"FileInfo(title={self.title}, sha1={self.sha1[:8]}..., size={self.size})"
        )


@dataclass
class FileChangeSet:
    """
    Result of file change detection.

    Categorizes files into new, modified (SHA1 changed), and deleted.

    Attributes:
        new_files: Files that don't exist in database
        modified_files: Files with different SHA1 (new version uploaded)
        deleted_files: File titles that exist in DB but not in API
    """

    new_files: List[FileInfo] = field(default_factory=list)
    modified_files: List[FileInfo] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total number of file changes detected."""
        return len(self.new_files) + len(self.modified_files) + len(self.deleted_files)

    @property
    def has_changes(self) -> bool:
        """Check if any file changes were detected."""
        return self.total_changes > 0

    def __repr__(self) -> str:
        return (
            f"FileChangeSet(new={len(self.new_files)}, "
            f"modified={len(self.modified_files)}, "
            f"deleted={len(self.deleted_files)})"
        )
