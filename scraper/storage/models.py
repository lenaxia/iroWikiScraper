"""Data models for wiki content."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Tuple


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

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Page":
        """
        Create Page from database row.

        Args:
            row: SQLite row from pages table

        Returns:
            Page instance
        """
        return cls(
            page_id=row["page_id"],
            namespace=row["namespace"],
            title=row["title"],
            is_redirect=bool(row["is_redirect"]),
        )

    def to_db_params(self) -> Tuple[int, int, str, int]:
        """
        Convert to database parameters for INSERT/UPDATE.

        Returns:
            Tuple of values for SQL query (page_id, namespace, title, is_redirect)
        """
        return (self.page_id, self.namespace, self.title, 1 if self.is_redirect else 0)


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
                    f"parent_id ({
                        self.parent_id}) must be less than revision_id ({
                        self.revision_id})")

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

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Revision":
        """
        Create Revision from database row.

        Handles type conversions:
        - timestamp: ISO string → datetime
        - tags: JSON string → List[str]
        - NULL handling for parent_id, user_id, tags

        Args:
            row: SQLite row from revisions table

        Returns:
            Revision instance
        """
        # Parse tags JSON
        tags = None
        if row["tags"]:
            tags = json.loads(row["tags"])

        return cls(
            revision_id=row["revision_id"],
            page_id=row["page_id"],
            parent_id=row["parent_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user=row["user"],
            user_id=row["user_id"],
            comment=row["comment"],
            content=row["content"],
            size=row["size"],
            sha1=row["sha1"],
            minor=bool(row["minor"]),
            tags=tags,
        )

    def to_db_params(self) -> Tuple[Any, ...]:
        """
        Convert to database parameters for INSERT/UPDATE.

        Returns:
            Tuple of values for SQL query in order:
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
        """
        # Convert tags to JSON
        tags_json = json.dumps(self.tags) if self.tags else None

        return (
            self.revision_id,
            self.page_id,
            self.parent_id,
            self.timestamp.isoformat(),
            self.user,
            self.user_id,
            self.comment,
            self.content,
            self.size,
            self.sha1,
            1 if self.minor else 0,
            tags_json,
        )


@dataclass(frozen=True)
class Link:
    """
    Represents an internal link from one wiki page to another resource.

    Links capture the navigation structure and relationships between wiki pages,
    templates, files, and categories. This enables graph analysis of the wiki
    structure and understanding of page relationships.

    Attributes:
        source_page_id: ID of the page containing this link
        target_title: Title of the linked resource (without namespace prefix for files/categories)
        link_type: Type of link - 'page', 'template', 'file', or 'category'

    Link Types:
        page: Regular internal link [[Page Name]]
        template: Template transclusion {{Template Name}}
        file: File reference [[File:Example.png]]
        category: Category membership [[Category:Monsters]]

    Raises:
        ValueError: If validation fails (invalid IDs, empty title, invalid link type)

    Example:
        >>> link = Link(
        ...     source_page_id=123,
        ...     target_title="Main Page",
        ...     link_type="page"
        ... )
    """

    source_page_id: int
    target_title: str
    link_type: str

    def __post_init__(self) -> None:
        """Validate link data after initialization."""
        # Validate source_page_id
        if not isinstance(self.source_page_id, int) or self.source_page_id <= 0:
            raise ValueError(
                f"source_page_id must be a positive integer, got: {self.source_page_id}"
            )

        # Validate target_title (cannot be empty)
        if not isinstance(self.target_title, str):
            raise ValueError(
                f"target_title must be a string, got: {type(self.target_title)}"
            )
        if not self.target_title or not self.target_title.strip():
            raise ValueError("target_title cannot be empty")

        # Validate link_type (must be one of the valid types)
        valid_types = ["page", "template", "file", "category"]
        if self.link_type not in valid_types:
            raise ValueError(
                f"link_type must be one of {valid_types}, got: {self.link_type}"
            )

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"Link(source={self.source_page_id}, target='{self.target_title}', "
            f"type='{self.link_type}')"
        )

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Link":
        """
        Create Link from database row.

        Args:
            row: SQLite row from links table

        Returns:
            Link instance
        """
        return cls(
            source_page_id=row["source_page_id"],
            target_title=row["target_title"],
            link_type=row["link_type"],
        )

    def to_db_params(self) -> Tuple[int, str, str]:
        """
        Convert to database parameters for INSERT/UPDATE.

        Returns:
            Tuple of values for SQL query (source_page_id, target_title, link_type)
        """
        return (self.source_page_id, self.target_title, self.link_type)


@dataclass(frozen=True)
class FileMetadata:
    """
    Represents metadata for a wiki file (image, video, document, etc.).

    A file represents uploaded media on the wiki, including images, videos,
    PDFs, and other document types. This class stores comprehensive metadata
    about each file including URLs, content hashes, dimensions, and uploader info.

    Attributes:
        filename: Name of the file (e.g., "Example.png")
        url: Direct URL to the file content
        descriptionurl: URL to the file description page on the wiki
        sha1: SHA1 hash of file content (40 character hex string)
        size: File size in bytes (non-negative)
        width: Image width in pixels (None for non-images)
        height: Image height in pixels (None for non-images)
        mime_type: MIME type (e.g., "image/png", "video/webm", "application/pdf")
        timestamp: Upload timestamp (UTC)
        uploader: Username who uploaded the file (empty string if deleted)

    Raises:
        ValueError: If validation fails (invalid filename, sha1, dimensions, etc.)

    Example:
        >>> file = FileMetadata(
        ...     filename="Example.png",
        ...     url="https://irowiki.org/images/Example.png",
        ...     descriptionurl="https://irowiki.org/wiki/File:Example.png",
        ...     sha1="abc123def456789012345678901234567890abcd",
        ...     size=123456,
        ...     width=800,
        ...     height=600,
        ...     mime_type="image/png",
        ...     timestamp=datetime(2024, 1, 15, 10, 30, 0),
        ...     uploader="User"
        ... )
    """

    filename: str
    url: str
    descriptionurl: str
    sha1: str
    size: int
    width: Optional[int]
    height: Optional[int]
    mime_type: str
    timestamp: datetime
    uploader: str

    def __post_init__(self) -> None:
        """Validate file metadata after initialization."""
        # Validate filename
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise ValueError("filename cannot be empty")

        # Validate url
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("url cannot be empty")

        # Validate descriptionurl
        if not isinstance(self.descriptionurl, str) or not self.descriptionurl.strip():
            raise ValueError("descriptionurl cannot be empty")

        # Validate sha1 (must be exactly 40 characters, hexadecimal)
        if not isinstance(self.sha1, str):
            raise ValueError(f"sha1 must be a string, got: {type(self.sha1)}")
        if len(self.sha1) != 40:
            raise ValueError(
                f"sha1 must be exactly 40 characters, got {len(self.sha1)} characters"
            )
        # Check if valid hex string
        try:
            int(self.sha1, 16)
        except ValueError:
            raise ValueError(
                f"sha1 must be a valid hexadecimal string, got: {self.sha1}"
            )

        # Validate size
        if not isinstance(self.size, int) or self.size < 0:
            raise ValueError(f"size must be non-negative, got: {self.size}")

        # Validate width (optional, but must be positive if provided)
        if self.width is not None:
            if not isinstance(self.width, int) or self.width <= 0:
                raise ValueError(
                    f"width must be positive if provided, got: {self.width}"
                )

        # Validate height (optional, but must be positive if provided)
        if self.height is not None:
            if not isinstance(self.height, int) or self.height <= 0:
                raise ValueError(
                    f"height must be positive if provided, got: {self.height}"
                )

        # Validate mime_type
        if not isinstance(self.mime_type, str) or not self.mime_type.strip():
            raise ValueError("mime_type cannot be empty")

        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError(
                f"timestamp must be a datetime object, got: {type(self.timestamp)}"
            )

        # Validate uploader (can be empty string for deleted users)
        if not isinstance(self.uploader, str):
            raise ValueError(f"uploader must be a string, got: {type(self.uploader)}")

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"FileMetadata(filename='{self.filename}', size={self.size}, "
            f"mime='{self.mime_type}', uploader='{self.uploader}')"
        )

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "FileMetadata":
        """
        Create FileMetadata from database row.

        Args:
            row: SQLite row from files table

        Returns:
            FileMetadata instance
        """
        return cls(
            filename=row["filename"],
            url=row["url"],
            descriptionurl=row["descriptionurl"],
            sha1=row["sha1"],
            size=row["size"],
            width=row["width"],
            height=row["height"],
            mime_type=row["mime_type"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            uploader=row["uploader"],
        )

    def to_db_params(
        self,
    ) -> Tuple[str, str, str, str, int, Optional[int], Optional[int], str, str, str]:
        """
        Convert to database parameters for INSERT/UPDATE.

        Returns:
            Tuple of values for SQL query (filename, url, descriptionurl, sha1,
            size, width, height, mime_type, timestamp, uploader)
        """
        return (
            self.filename,
            self.url,
            self.descriptionurl,
            self.sha1,
            self.size,
            self.width,
            self.height,
            self.mime_type,
            self.timestamp.isoformat(),
            self.uploader,
        )
