"""Data models for wiki content."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


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


@dataclass(frozen=True)
class Revision:
    """
    Represents a single revision of a MediaWiki page.

    A revision captures a specific version of a page at a point in time,
    including the complete wikitext content, metadata about the edit,
    and information about the user who made the change.

    Attributes:
        revision_id: Unique identifier for this revision
        page_id: ID of the page this revision belongs to
        parent_id: ID of the previous revision (None for first revision)
        timestamp: When this revision was made (UTC)
        user: Username who made the edit (empty string if deleted/hidden)
        user_id: Numeric user ID (None if user is deleted/hidden)
        comment: Edit summary/comment
        content: Complete wikitext content of the page at this revision
        size: Size of content in bytes
        sha1: SHA1 hash of the content
        minor: Whether this was marked as a minor edit
        tags: List of tags applied to this edit (e.g., "visual edit")

    Raises:
        ValueError: If validation fails (invalid IDs, timestamps, etc.)
    """

    revision_id: int
    page_id: int
    parent_id: Optional[int]
    timestamp: datetime
    user: str
    user_id: Optional[int]
    comment: str
    content: str
    size: int
    sha1: str
    minor: bool = False
    tags: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Validate revision data after initialization."""
        # Validate revision_id
        if not isinstance(self.revision_id, int) or self.revision_id <= 0:
            raise ValueError(
                f"revision_id must be a positive integer, got: {self.revision_id}"
            )

        # Validate page_id
        if not isinstance(self.page_id, int) or self.page_id <= 0:
            raise ValueError(f"page_id must be a positive integer, got: {self.page_id}")

        # Validate parent_id (can be None for first revision, or positive int)
        if self.parent_id is not None:
            if not isinstance(self.parent_id, int) or self.parent_id <= 0:
                raise ValueError(
                    f"parent_id must be a positive integer or None, got: {self.parent_id}"
                )
            # Parent ID should be less than current revision ID (temporal ordering)
            if self.parent_id >= self.revision_id:
                raise ValueError(
                    f"parent_id ({self.parent_id}) must be less than revision_id ({self.revision_id})"
                )

        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError(
                f"timestamp must be a datetime object, got: {type(self.timestamp)}"
            )

        # Validate user (can be empty string for deleted users)
        if not isinstance(self.user, str):
            raise ValueError(f"user must be a string, got: {type(self.user)}")

        # Validate user_id (can be None for deleted/anonymous users)
        if self.user_id is not None and (
            not isinstance(self.user_id, int) or self.user_id <= 0
        ):
            raise ValueError(
                f"user_id must be a positive integer or None, got: {self.user_id}"
            )

        # Validate comment (can be empty string)
        if not isinstance(self.comment, str):
            raise ValueError(f"comment must be a string, got: {type(self.comment)}")

        # Validate content (can be empty string for blank pages)
        if not isinstance(self.content, str):
            raise ValueError(f"content must be a string, got: {type(self.content)}")

        # Validate size
        if not isinstance(self.size, int) or self.size < 0:
            raise ValueError(f"size must be a non-negative integer, got: {self.size}")

        # Validate sha1
        if not isinstance(self.sha1, str) or len(self.sha1) == 0:
            raise ValueError(f"sha1 must be a non-empty string, got: {self.sha1}")

        # Validate minor flag
        if not isinstance(self.minor, bool):
            raise ValueError(f"minor must be a boolean, got: {type(self.minor)}")

        # Validate tags (convert None to empty list, ensure all items are strings)
        if self.tags is None:
            object.__setattr__(self, "tags", [])
        else:
            if not isinstance(self.tags, list):
                raise ValueError(f"tags must be a list or None, got: {type(self.tags)}")
            if not all(isinstance(tag, str) for tag in self.tags):
                raise ValueError("All tags must be strings")

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"Revision(id={self.revision_id}, page={self.page_id}, "
            f"user='{self.user}', timestamp={self.timestamp.isoformat()})"
        )
