"""Checkpoint management for incremental scrapes."""

from dataclasses import dataclass, field
from typing import Set
from datetime import datetime
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class IncrementalCheckpointState:
    """
    State for resuming incremental scrapes after interruption.

    Tracks which pages have been processed in each phase to allow
    resuming from where we left off if the scrape is interrupted.

    Attributes:
        completed_new_pages: Set of new page IDs already processed
        completed_modified_pages: Set of modified page IDs already processed
        completed_deleted_pages: Set of deleted page IDs already processed
        completed_moved_pages: Set of moved page IDs already processed
        current_phase: Current processing phase
        last_updated: When checkpoint was last saved
        run_id: Associated scrape_run ID
    """

    completed_new_pages: Set[int] = field(default_factory=set)
    completed_modified_pages: Set[int] = field(default_factory=set)
    completed_deleted_pages: Set[int] = field(default_factory=set)
    completed_moved_pages: Set[int] = field(default_factory=set)
    current_phase: str = "init"  # init, new_pages, modified_pages, deleted_pages, moved_pages, files, complete
    last_updated: datetime = field(default_factory=datetime.utcnow)
    run_id: int = 0

    @property
    def total_completed(self) -> int:
        """Total number of pages completed across all phases."""
        return (
            len(self.completed_new_pages)
            + len(self.completed_modified_pages)
            + len(self.completed_deleted_pages)
            + len(self.completed_moved_pages)
        )


class IncrementalCheckpoint:
    """
    Manages checkpoint state for incremental scrapes.

    Allows saving and loading scrape progress so that interrupted
    scrapes can resume from where they left off instead of starting over.

    Example:
        >>> checkpoint = IncrementalCheckpoint(Path("checkpoints"))
        >>> state = checkpoint.load()
        >>> # ... process pages ...
        >>> state.completed_new_pages.add(123)
        >>> checkpoint.save(state)
    """

    def __init__(self, checkpoint_dir: Path):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_file = self.checkpoint_dir / "incremental_checkpoint.json"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        """
        Check if checkpoint exists.

        Returns:
            True if checkpoint file exists, False otherwise
        """
        return self.checkpoint_file.exists()

    def load(self) -> IncrementalCheckpointState:
        """
        Load checkpoint state from file.

        Returns:
            IncrementalCheckpointState with saved progress, or empty state if no checkpoint

        Example:
            >>> checkpoint = IncrementalCheckpoint(Path("checkpoints"))
            >>> state = checkpoint.load()
            >>> if state.run_id > 0:
            ...     print(f"Resuming run {state.run_id}")
        """
        if not self.checkpoint_file.exists():
            logger.info("No checkpoint found, starting fresh")
            return IncrementalCheckpointState()

        try:
            data = json.loads(self.checkpoint_file.read_text())

            state = IncrementalCheckpointState(
                completed_new_pages=set(data.get("completed_new_pages", [])),
                completed_modified_pages=set(data.get("completed_modified_pages", [])),
                completed_deleted_pages=set(data.get("completed_deleted_pages", [])),
                completed_moved_pages=set(data.get("completed_moved_pages", [])),
                current_phase=data.get("current_phase", "init"),
                last_updated=datetime.fromisoformat(data["last_updated"]),
                run_id=data.get("run_id", 0),
            )

            logger.info(
                f"Loaded checkpoint: run_id={state.run_id}, "
                f"phase={state.current_phase}, "
                f"completed={state.total_completed} pages"
            )

            return state

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return IncrementalCheckpointState()

    def save(self, state: IncrementalCheckpointState):
        """
        Save checkpoint state to file.

        Args:
            state: Current checkpoint state to save

        Example:
            >>> state = IncrementalCheckpointState(run_id=123)
            >>> state.completed_new_pages.add(456)
            >>> checkpoint.save(state)
        """
        try:
            state.last_updated = datetime.utcnow()

            data = {
                "completed_new_pages": list(state.completed_new_pages),
                "completed_modified_pages": list(state.completed_modified_pages),
                "completed_deleted_pages": list(state.completed_deleted_pages),
                "completed_moved_pages": list(state.completed_moved_pages),
                "current_phase": state.current_phase,
                "last_updated": state.last_updated.isoformat(),
                "run_id": state.run_id,
            }

            self.checkpoint_file.write_text(json.dumps(data, indent=2))

            logger.debug(f"Saved checkpoint: {state.total_completed} pages completed")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def clear(self):
        """
        Remove checkpoint file.

        Called after successful completion to clean up checkpoint.

        Example:
            >>> checkpoint = IncrementalCheckpoint(Path("checkpoints"))
            >>> # ... complete scrape successfully ...
            >>> checkpoint.clear()
        """
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("Cleared checkpoint")
