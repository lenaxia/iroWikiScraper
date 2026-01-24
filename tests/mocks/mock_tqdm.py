"""Mock tqdm progress bar for testing without actual progress display.

This module provides a mock tqdm implementation that tracks progress
without rendering to the terminal during tests.
"""

from typing import Any, Optional


class MockTqdm:
    """Mock tqdm progress bar for testing.

    Provides the same interface as tqdm but doesn't render anything.
    Tracks all calls for test verification.

    Example:
        >>> pbar = MockTqdm(total=100, desc="Test")
        >>> pbar.update(10)
        >>> pbar.n
        10
        >>> pbar.close()
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        unit: str = "it",
        **kwargs: Any,
    ):
        """Initialize mock progress bar.

        Args:
            total: Total number of items
            desc: Description prefix
            unit: Unit name for items
            **kwargs: Additional args (ignored, for compatibility)
        """
        self.total = total
        self.desc = desc
        self.unit = unit
        self.n = 0  # Current position
        self.closed = False
        self.updates = []  # Track all update calls

    def update(self, n: int = 1) -> None:
        """Update progress by n steps.

        Args:
            n: Number of steps to advance
        """
        self.n += n
        self.updates.append(n)

    def close(self) -> None:
        """Close progress bar."""
        self.closed = True

    def set_description(self, desc: str) -> None:
        """Update description.

        Args:
            desc: New description text
        """
        self.desc = desc

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()
        return False
