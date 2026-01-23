"""Data models for wiki content."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Page:
    """Represents a wiki page.

    Attributes:
        page_id: Unique page identifier
        namespace: Namespace ID (0=Main, 1=Talk, etc.)
        title: Full page title including namespace prefix
        is_redirect: Whether this page is a redirect
    """

    page_id: int
    namespace: int
    title: str
    is_redirect: bool = False

    def __post_init__(self):
        """Validate page data."""
        if self.page_id <= 0:
            raise ValueError(f"page_id must be positive, got {self.page_id}")
        if self.namespace < 0:
            raise ValueError(f"namespace must be non-negative, got {self.namespace}")
        if not self.title or not self.title.strip():
            raise ValueError("title cannot be empty")

        # Normalize title (strip whitespace)
        self.title = self.title.strip()
