"""Checkpoint manager for orchestrating full scrape resume capability.

This module provides the CheckpointManager class for tracking scrape progress
and enabling resume functionality for interrupted full scrapes.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    """Structured checkpoint data for full scrape operations.

    Attributes:
        version: Checkpoint format version
        scrape_type: Type of scrape (full, incremental)
        started_at: ISO timestamp when scrape started
        last_update: ISO timestamp of last update
        parameters: Dict of scrape parameters (namespaces, rate_limit)
        progress: Dict tracking completion progress
        statistics: Dict with scrape statistics
    """

    version: str = "1.0"
    scrape_type: str = "full"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_update: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    parameters: Dict[str, Any] = field(default_factory=dict)
    progress: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "scrape_type": self.scrape_type,
            "started_at": self.started_at,
            "last_update": self.last_update,
            "parameters": self.parameters,
            "progress": self.progress,
            "statistics": self.statistics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Create from dictionary loaded from JSON."""
        return cls(
            version=data.get("version", "1.0"),
            scrape_type=data.get("scrape_type", "full"),
            started_at=data.get("started_at", datetime.now(UTC).isoformat()),
            last_update=data.get("last_update", datetime.now(UTC).isoformat()),
            parameters=data.get("parameters", {}),
            progress=data.get("progress", {}),
            statistics=data.get("statistics", {}),
        )


class CheckpointManager:
    """Manages checkpoint and resume functionality for full scrape operations.

    This class handles checkpoint tracking, validation, and resume logic for
    full scrape operations. It works with the existing Checkpoint utility but
    adds orchestration-level logic for scrape parameters and progress tracking.

    Example:
        >>> from pathlib import Path
        >>> manager = CheckpointManager(Path("data/.checkpoint.json"))
        >>> manager.start_scrape(namespaces=[0, 4, 6], rate_limit=2.0)
        >>> manager.mark_namespace_complete(0)
        >>> manager.mark_page_complete(1234)
        >>> checkpoint = manager.get_checkpoint()
        >>> manager.clear()
    """

    def __init__(self, checkpoint_file: Path):
        """Initialize checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = checkpoint_file
        self.data: Optional[CheckpointData] = None

        # Load existing checkpoint if present
        if checkpoint_file.exists():
            self._load()

    def _load(self) -> None:
        """Load checkpoint from file."""
        try:
            with open(self.checkpoint_file, "r") as f:
                raw_data = json.load(f)
                self.data = CheckpointData.from_dict(raw_data)
                logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse checkpoint file: {e}, starting fresh")
            self.data = None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}, starting fresh")
            self.data = None

    def _save(self) -> None:
        """Save checkpoint to file atomically."""
        if self.data is None:
            return

        # Update timestamp
        self.data.last_update = datetime.now(UTC).isoformat()

        # Atomic write pattern
        temp_file = self.checkpoint_file.with_suffix(".tmp")

        try:
            # Ensure parent directory exists
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_file, "w") as f:
                json.dump(self.data.to_dict(), f, indent=2)

            # Atomic rename
            temp_file.rename(self.checkpoint_file)

            logger.debug(f"Saved checkpoint to {self.checkpoint_file}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise

    def start_scrape(
        self,
        namespaces: List[int],
        rate_limit: float = 2.0,
        scrape_type: str = "full",
    ) -> None:
        """Start a new scrape and initialize checkpoint.

        Args:
            namespaces: List of namespace IDs to scrape
            rate_limit: Rate limit in requests per second
            scrape_type: Type of scrape (full, incremental)
        """
        self.data = CheckpointData(
            scrape_type=scrape_type,
            parameters={
                "namespaces": namespaces,
                "rate_limit": rate_limit,
            },
            progress={
                "namespaces_completed": [],
                "current_namespace": namespaces[0] if namespaces else 0,
                "pages_completed": [],
                "last_page_id": 0,
            },
            statistics={
                "pages_scraped": 0,
                "revisions_scraped": 0,
                "errors": 0,
            },
        )

        self._save()
        logger.info(f"Started {scrape_type} scrape with namespaces: {namespaces}")

    def mark_namespace_complete(self, namespace: int) -> None:
        """Mark a namespace as completed.

        Args:
            namespace: Namespace ID
        """
        if self.data is None:
            return

        completed = self.data.progress.get("namespaces_completed", [])
        if namespace not in completed:
            completed.append(namespace)
            self.data.progress["namespaces_completed"] = sorted(completed)

        self._save()
        logger.debug(f"Marked namespace {namespace} as complete")

    def mark_page_complete(self, page_id: int) -> None:
        """Mark a page as completed.

        Args:
            page_id: Page ID
        """
        if self.data is None:
            return

        completed = self.data.progress.get("pages_completed", [])
        if page_id not in completed:
            completed.append(page_id)
            self.data.progress["pages_completed"] = completed
            self.data.progress["last_page_id"] = page_id

        # Update statistics
        self.data.statistics["pages_scraped"] = len(completed)

        self._save()

    def set_current_namespace(self, namespace: int) -> None:
        """Set the current namespace being processed.

        Args:
            namespace: Current namespace ID
        """
        if self.data is None:
            return

        self.data.progress["current_namespace"] = namespace
        self._save()

    def update_statistics(
        self, pages_scraped: int, revisions_scraped: int, errors: int = 0
    ) -> None:
        """Update scrape statistics.

        Args:
            pages_scraped: Total pages scraped
            revisions_scraped: Total revisions scraped
            errors: Total errors encountered
        """
        if self.data is None:
            return

        self.data.statistics.update(
            {
                "pages_scraped": pages_scraped,
                "revisions_scraped": revisions_scraped,
                "errors": errors,
            }
        )

        self._save()

    def is_namespace_complete(self, namespace: int) -> bool:
        """Check if namespace is complete.

        Args:
            namespace: Namespace ID

        Returns:
            True if namespace completed, False otherwise
        """
        if self.data is None:
            return False

        completed = self.data.progress.get("namespaces_completed", [])
        return namespace in completed

    def is_page_complete(self, page_id: int) -> bool:
        """Check if page is complete.

        Args:
            page_id: Page ID

        Returns:
            True if page completed, False otherwise
        """
        if self.data is None:
            return False

        completed = self.data.progress.get("pages_completed", [])
        return page_id in completed

    def is_compatible(self, namespaces: List[int], scrape_type: str = "full") -> bool:
        """Check if checkpoint is compatible with requested scrape.

        Args:
            namespaces: Requested namespace list
            scrape_type: Requested scrape type

        Returns:
            True if compatible, False otherwise
        """
        if self.data is None:
            return False

        # Check scrape type matches
        if self.data.scrape_type != scrape_type:
            logger.warning(
                f"Checkpoint scrape_type '{self.data.scrape_type}' does not match "
                f"requested '{scrape_type}'"
            )
            return False

        # Check namespaces match (order doesn't matter)
        checkpoint_ns = self.data.parameters.get("namespaces", [])
        if sorted(checkpoint_ns) != sorted(namespaces):
            logger.warning(
                f"Checkpoint namespaces {checkpoint_ns} do not match "
                f"requested {namespaces}"
            )
            return False

        return True

    def get_checkpoint(self) -> Optional[CheckpointData]:
        """Get current checkpoint data.

        Returns:
            CheckpointData if exists, None otherwise
        """
        return self.data

    def get_completed_namespaces(self) -> List[int]:
        """Get list of completed namespaces.

        Returns:
            List of completed namespace IDs
        """
        if self.data is None:
            return []

        return self.data.progress.get("namespaces_completed", [])

    def get_completed_pages(self) -> List[int]:
        """Get list of completed page IDs.

        Returns:
            List of completed page IDs
        """
        if self.data is None:
            return []

        return self.data.progress.get("pages_completed", [])

    def clear(self) -> None:
        """Clear checkpoint file and internal state."""
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info(f"Cleared checkpoint file: {self.checkpoint_file}")
            except Exception as e:
                logger.error(f"Failed to remove checkpoint file: {e}")
                raise

        self.data = None
        logger.debug("Reset checkpoint data to None")

    def exists(self) -> bool:
        """Check if checkpoint exists and is valid.

        Returns:
            True if checkpoint file exists and contains valid data, False otherwise
        """
        if not self.checkpoint_file.exists():
            return False

        # If data was loaded successfully, checkpoint is valid
        return self.data is not None
