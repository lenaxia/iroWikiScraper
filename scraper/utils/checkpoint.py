"""Checkpoint and resume functionality for scraper operations.

This module provides checkpoint management to enable resuming interrupted
scraping operations without re-processing completed items.

Example:
    >>> from pathlib import Path
    >>> from scraper.utils.checkpoint import Checkpoint
    >>>
    >>> # Initialize checkpoint
    >>> checkpoint = Checkpoint(Path("data/checkpoint.json"))
    >>>
    >>> # Check if page already processed
    >>> if not checkpoint.is_page_complete(123):
    ...     scrape_page(123)
    ...     checkpoint.mark_page_complete(123)
    >>>
    >>> # Get statistics
    >>> stats = checkpoint.get_stats()
    >>> print(f"Progress: {stats['pages_completed']} pages")
    >>>
    >>> # Clear after completion
    >>> checkpoint.clear()
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class Checkpoint:
    """
    Manages checkpoint and resume functionality for scraping operations.

    Tracks completed pages and files to enable resuming after interruption.
    Uses atomic file writes to prevent corruption.

    Attributes:
        checkpoint_file: Path to checkpoint JSON file
        data: Internal checkpoint data structure

    Example:
        >>> checkpoint = Checkpoint(Path("checkpoint.json"))
        >>> checkpoint.mark_page_complete(123)
        >>> if checkpoint.is_page_complete(123):
        ...     print("Already processed")
        >>> checkpoint.clear()
    """

    # Valid phase values
    VALID_PHASES = {
        "scraping_pages",
        "downloading_files",
        "extracting_links",
        "complete",
    }

    def __init__(self, checkpoint_file: Path):
        """
        Initialize checkpoint manager.

        Loads existing checkpoint or creates empty one if file doesn't exist
        or is corrupted.

        Args:
            checkpoint_file: Path to checkpoint JSON file

        Example:
            >>> checkpoint = Checkpoint(Path("data/checkpoint.json"))
        """
        self.checkpoint_file = checkpoint_file
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        """
        Load checkpoint from file or create empty.

        Handles corrupted files gracefully by logging warning and starting fresh.

        Returns:
            Dictionary containing checkpoint data

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> data = checkpoint._load()
            >>> assert "version" in data
        """
        if not self.checkpoint_file.exists():
            logger.info(
                f"No checkpoint found at {self.checkpoint_file}, starting fresh"
            )
            return self._create_empty_checkpoint()

        try:
            with open(self.checkpoint_file, "r") as f:
                data = json.load(f)

            # Validate it's a dictionary
            if not isinstance(data, dict):
                logger.warning(
                    f"Checkpoint file contains invalid data type: {type(data)}, starting fresh"
                )
                return self._create_empty_checkpoint()

            # Apply defaults for missing fields
            defaults = self._create_empty_checkpoint()
            for key, default_value in defaults.items():
                if key not in data:
                    logger.warning(
                        f"Missing field '{key}' in checkpoint, using default: {default_value}"
                    )
                    data[key] = default_value

            # Ensure lists (not sets) in loaded data
            if not isinstance(data.get("completed_pages"), list):
                data["completed_pages"] = []
            if not isinstance(data.get("completed_files"), list):
                data["completed_files"] = []

            logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
            return data

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse checkpoint file {self.checkpoint_file}: {e}, starting fresh"
            )
            return self._create_empty_checkpoint()
        except Exception as e:
            logger.error(
                f"Failed to load checkpoint file {self.checkpoint_file}: {e}, starting fresh"
            )
            return self._create_empty_checkpoint()

    def _create_empty_checkpoint(self) -> Dict[str, Any]:
        """
        Create empty checkpoint data structure.

        Returns:
            Dictionary with default checkpoint structure

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> empty = checkpoint._create_empty_checkpoint()
            >>> assert empty["completed_pages"] == []
        """
        now = datetime.now(timezone.utc).isoformat()
        return {
            "version": "1.0",
            "created_at": now,
            "updated_at": now,
            "phase": "scraping_pages",
            "completed_pages": [],
            "completed_files": [],
            "current_namespace": 0,
            "total_pages": 0,
            "total_files": 0,
        }

    def _save(self) -> None:
        """
        Save checkpoint to file atomically.

        Uses temp file + rename pattern to prevent corruption from interruption.
        Updates the updated_at timestamp.

        Raises:
            OSError: If unable to write checkpoint file

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_page_complete(123)
            >>> checkpoint._save()
        """
        # Update timestamp
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Write to temp file first (atomic write pattern)
        temp_file = self.checkpoint_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w") as f:
                json.dump(self.data, f, indent=2)

            # Atomic rename (overwrites existing file)
            temp_file.rename(self.checkpoint_file)

            logger.debug(f"Saved checkpoint to {self.checkpoint_file}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint to {self.checkpoint_file}: {e}")
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise

    def mark_page_complete(self, page_id: int) -> None:
        """
        Mark a page as completed.

        Automatically saves checkpoint after marking. Operation is idempotent.

        Args:
            page_id: Page ID to mark as complete

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_page_complete(123)
            >>> assert checkpoint.is_page_complete(123)
        """
        # Convert to set for deduplication, then back to list
        pages_set: Set[int] = set(self.data["completed_pages"])
        pages_set.add(page_id)
        self.data["completed_pages"] = sorted(list(pages_set))

        self._save()
        logger.debug(f"Marked page {page_id} as complete")

    def mark_file_complete(self, filename: str) -> None:
        """
        Mark a file as completed.

        Automatically saves checkpoint after marking. Operation is idempotent.

        Args:
            filename: Filename to mark as complete

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_file_complete("File_A.png")
            >>> assert checkpoint.is_file_complete("File_A.png")
        """
        # Convert to set for deduplication, then back to list
        files_set: Set[str] = set(self.data["completed_files"])
        files_set.add(filename)
        self.data["completed_files"] = sorted(list(files_set))

        self._save()
        logger.debug(f"Marked file '{filename}' as complete")

    def is_page_complete(self, page_id: int) -> bool:
        """
        Check if page already processed.

        Args:
            page_id: Page ID to check

        Returns:
            True if page is complete, False otherwise

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_page_complete(123)
            >>> assert checkpoint.is_page_complete(123) is True
            >>> assert checkpoint.is_page_complete(999) is False
        """
        return page_id in self.data["completed_pages"]

    def is_file_complete(self, filename: str) -> bool:
        """
        Check if file already downloaded.

        Args:
            filename: Filename to check

        Returns:
            True if file is complete, False otherwise

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_file_complete("test.png")
            >>> assert checkpoint.is_file_complete("test.png") is True
            >>> assert checkpoint.is_file_complete("other.png") is False
        """
        return filename in self.data["completed_files"]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get checkpoint statistics.

        Returns:
            Dictionary with statistics including:
                - pages_completed: Number of completed pages
                - files_completed: Number of completed files
                - phase: Current phase
                - total_pages: Total pages (if set)
                - total_files: Total files (if set)

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_page_complete(1)
            >>> checkpoint.mark_page_complete(2)
            >>> stats = checkpoint.get_stats()
            >>> assert stats['pages_completed'] == 2
        """
        return {
            "pages_completed": len(self.data["completed_pages"]),
            "files_completed": len(self.data["completed_files"]),
            "phase": self.data.get("phase", "scraping_pages"),
            "total_pages": self.data.get("total_pages", 0),
            "total_files": self.data.get("total_files", 0),
        }

    def get_phase(self) -> str:
        """
        Get current phase.

        Returns:
            Current phase string

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> phase = checkpoint.get_phase()
            >>> assert phase in ["scraping_pages", "downloading_files", "extracting_links", "complete"]
        """
        return self.data.get("phase", "scraping_pages")

    def set_phase(self, phase: str) -> None:
        """
        Set current phase.

        Args:
            phase: Phase to set (must be one of: scraping_pages, downloading_files,
                   extracting_links, complete)

        Raises:
            ValueError: If phase is not valid

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.set_phase("downloading_files")
            >>> assert checkpoint.get_phase() == "downloading_files"
        """
        if phase not in self.VALID_PHASES:
            raise ValueError(
                f"Invalid phase: {phase}. Must be one of: {', '.join(sorted(self.VALID_PHASES))}"
            )

        self.data["phase"] = phase
        self._save()
        logger.info(f"Set phase to: {phase}")

    def clear(self) -> None:
        """
        Clear checkpoint file and reset internal state.

        Removes checkpoint file from disk and resets data to empty state.
        Safe to call even if checkpoint file doesn't exist.

        Example:
            >>> checkpoint = Checkpoint(Path("checkpoint.json"))
            >>> checkpoint.mark_page_complete(123)
            >>> checkpoint.clear()
            >>> assert not checkpoint.is_page_complete(123)
        """
        # Remove file if it exists
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info(f"Cleared checkpoint file: {self.checkpoint_file}")
            except Exception as e:
                logger.error(f"Failed to remove checkpoint file: {e}")
                raise

        # Reset internal state
        self.data = self._create_empty_checkpoint()
        logger.debug("Reset checkpoint data to empty state")
