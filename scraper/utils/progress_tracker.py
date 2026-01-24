"""Progress tracking and logging for scraper operations.

This module provides progress tracking with tqdm progress bars, configurable
logging intervals, ETA calculations, and statistics tracking.

Example:
    >>> from scraper.utils.progress_tracker import ProgressTracker
    >>>
    >>> # Initialize tracker
    >>> tracker = ProgressTracker(total_pages=100, log_interval=10)
    >>>
    >>> # Update progress
    >>> tracker.update_page(revision_count=5)
    >>> tracker.update_file()
    >>>
    >>> # Get ETA
    >>> eta = tracker.get_eta_string()
    >>> print(f"ETA: {eta}")
    >>>
    >>> # Get final summary
    >>> print(tracker.get_summary())
    >>> tracker.close()
"""

import logging
import time
from typing import Dict, Optional

from tqdm import tqdm

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Tracks scraping progress with progress bar and statistics.

    Provides visual progress tracking with tqdm, configurable logging,
    ETA calculation, and detailed statistics about pages, revisions,
    files, and errors.

    Attributes:
        total_pages: Total number of pages to process
        log_interval: Log progress every N pages
        pbar: tqdm progress bar instance
        stats: Dictionary tracking pages, revisions, files, errors
        start_time: Timestamp when tracking started

    Example:
        >>> tracker = ProgressTracker(total_pages=100, log_interval=10)
        >>> for page_id in range(100):
        ...     # Process page
        ...     tracker.update_page(revision_count=5)
        ...     tracker.update_file()
        >>> print(tracker.get_summary())
        >>> tracker.close()
    """

    def __init__(self, total_pages: int, log_interval: int = 10):
        """
        Initialize progress tracker.

        Args:
            total_pages: Total number of pages to process (0 if unknown)
            log_interval: Log progress every N pages (default 10)

        Raises:
            ValueError: If total_pages is negative or log_interval is not positive
            TypeError: If arguments are not integers

        Example:
            >>> tracker = ProgressTracker(total_pages=100, log_interval=10)
        """
        # Type validation
        if not isinstance(total_pages, int):
            raise TypeError("total_pages must be an integer")
        if not isinstance(log_interval, int):
            raise TypeError("log_interval must be an integer")

        # Value validation
        if total_pages < 0:
            raise ValueError("total_pages must be non-negative")
        if log_interval <= 0:
            raise ValueError("log_interval must be positive")

        self.total_pages = total_pages
        self.log_interval = log_interval

        # Initialize statistics
        self.stats: Dict[str, int] = {
            "pages": 0,
            "revisions": 0,
            "files": 0,
            "errors": 0,
        }

        # Track timing for ETA
        self.start_time = time.time()
        self.last_log_time = self.start_time

        # Create progress bar
        self.pbar = tqdm(
            total=total_pages if total_pages > 0 else None,
            desc="Pages",
            unit="page",
        )

        logger.info(
            f"Progress tracker initialized: total_pages={total_pages}, log_interval={log_interval}"
        )

    def update_page(self, revision_count: int) -> None:
        """
        Update progress for a completed page.

        Increments page count, adds revisions, updates progress bar,
        and logs if at logging interval.

        Args:
            revision_count: Number of revisions fetched for this page

        Raises:
            ValueError: If revision_count is negative
            TypeError: If revision_count is not an integer

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_page(revision_count=5)
        """
        # Type validation
        if not isinstance(revision_count, int):
            raise TypeError("revision_count must be an integer")

        # Value validation
        if revision_count < 0:
            raise ValueError("revision_count must be non-negative")

        # Update statistics
        self.stats["pages"] += 1
        self.stats["revisions"] += revision_count

        # Update progress bar
        self.pbar.update(1)

        # Log at interval
        if self.stats["pages"] % self.log_interval == 0:
            self._log_progress()

    def update_file(self) -> None:
        """
        Update progress for a downloaded file.

        Increments file count in statistics.

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_file()
        """
        self.stats["files"] += 1

    def update_error(self) -> None:
        """
        Update progress for an error.

        Increments error count in statistics.

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_error()
        """
        self.stats["errors"] += 1

    def _log_progress(self) -> None:
        """
        Log current progress with statistics.

        Logs pages completed, revisions fetched, files downloaded,
        errors encountered, and ETA.
        """
        eta_string = self.get_eta_string()

        if self.total_pages > 0:
            progress_msg = (
                f"Progress: {self.stats['pages']}/{self.total_pages} pages, "
                f"{self.stats['revisions']} revisions, "
                f"{self.stats['files']} files, "
                f"{self.stats['errors']} errors, "
                f"ETA: {eta_string}"
            )
        else:
            progress_msg = (
                f"Progress: {self.stats['pages']} pages, "
                f"{self.stats['revisions']} revisions, "
                f"{self.stats['files']} files, "
                f"{self.stats['errors']} errors"
            )

        logger.info(progress_msg)

    def get_eta(self) -> Optional[float]:
        """
        Calculate estimated time remaining in seconds.

        Uses elapsed time and completed pages to estimate time for
        remaining pages. Returns None if no progress has been made
        or if complete.

        Returns:
            Estimated seconds remaining, or None if not calculable

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_page(revision_count=5)
            >>> eta = tracker.get_eta()
            >>> if eta:
            ...     print(f"ETA: {eta:.1f} seconds")
        """
        # Can't calculate ETA if no pages processed
        if self.stats["pages"] == 0:
            return None

        # Can't calculate if total is unknown
        if self.total_pages == 0:
            return None

        # Already complete
        if self.stats["pages"] >= self.total_pages:
            return 0.0

        # Calculate elapsed time
        elapsed = time.time() - self.start_time

        # Calculate average time per page
        avg_time_per_page = elapsed / self.stats["pages"]

        # Calculate remaining pages
        remaining_pages = self.total_pages - self.stats["pages"]

        # Estimate remaining time
        eta = avg_time_per_page * remaining_pages

        return eta

    def get_eta_string(self) -> str:
        """
        Get formatted ETA string.

        Returns human-readable ETA string with appropriate units
        (seconds, minutes, hours).

        Returns:
            Formatted ETA string or "Unknown" if not calculable

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_page(revision_count=5)
            >>> print(tracker.get_eta_string())
            "1 minute 30 seconds"
        """
        eta = self.get_eta()

        if eta is None:
            return "Unknown"

        if eta == 0.0:
            return "Complete"

        # Format based on duration
        if eta < 60:
            return f"{int(eta)} seconds"
        elif eta < 3600:
            minutes = int(eta / 60)
            seconds = int(eta % 60)
            if seconds == 0:
                return f"{minutes} minutes"
            return f"{minutes} minutes {seconds} seconds"
        else:
            hours = int(eta / 3600)
            minutes = int((eta % 3600) / 60)
            if minutes == 0:
                return f"{hours} hours"
            return f"{hours} hours {minutes} minutes"

    def get_stats(self) -> Dict[str, int]:
        """
        Get current statistics dictionary.

        Returns:
            Dictionary with pages, revisions, files, errors counts

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_page(revision_count=5)
            >>> stats = tracker.get_stats()
            >>> print(stats['pages'])
            1
        """
        return self.stats.copy()

    def get_summary(self) -> str:
        """
        Get final summary statistics string.

        Returns formatted summary with all statistics.

        Returns:
            Formatted summary string

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.update_page(revision_count=5)
            >>> tracker.update_file()
            >>> print(tracker.get_summary())
            "Pages: 1, Revisions: 5, Files: 1, Errors: 0"
        """
        return (
            f"Pages: {self.stats['pages']}, "
            f"Revisions: {self.stats['revisions']}, "
            f"Files: {self.stats['files']}, "
            f"Errors: {self.stats['errors']}"
        )

    def close(self) -> None:
        """
        Close progress bar and finalize tracking.

        Closes the tqdm progress bar. Safe to call multiple times.

        Example:
            >>> tracker = ProgressTracker(total_pages=100)
            >>> tracker.close()
        """
        if hasattr(self.pbar, "close"):
            self.pbar.close()
        logger.debug("Progress tracker closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False
