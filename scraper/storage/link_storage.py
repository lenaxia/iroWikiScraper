"""Link storage with database persistence.

This module provides the LinkStorage class for storing extracted wiki links
with database backend for persistence across runs.
"""

import logging
from typing import Dict, List

from scraper.storage.database import Database
from scraper.storage.models import Link

logger = logging.getLogger(__name__)


class LinkStorage:
    """
    Database-backed storage for wiki links with automatic deduplication.

    This class stores Link objects in a SQLite database for persistence
    across runs. It maintains the same API as the in-memory version for
    backwards compatibility.

    The storage supports:
    - Automatic deduplication (duplicate links are ignored)
    - Batch operations for efficiency
    - Fast queries by source page ID
    - Fast queries by link type
    - Persistence across program runs

    Example:
        >>> with Database("wiki.db") as db:
        ...     storage = LinkStorage(db)
        ...     link = Link(source_page_id=1, target_title="Main Page", link_type="page")
        ...     storage.add_link(link)
        ...     stats = storage.get_stats()
        ...     print(stats['total'])
        1
    """

    def __init__(self, db: Database) -> None:
        """
        Initialize database-backed link storage.

        Args:
            db: Database instance with initialized schema

        Example:
            >>> with Database("wiki.db") as db:
            ...     db.initialize_schema()
            ...     storage = LinkStorage(db)
        """
        self.db = db
        self.conn = db.get_connection()

    def add_link(self, link: Link) -> bool:
        """
        Add a single link to storage.

        If the link already exists (same source, target, and type), it will
        not be added again (deduplication via INSERT OR IGNORE).

        Args:
            link: Link object to add

        Returns:
            True if link was added (new), False if already exists (duplicate)

        Example:
            >>> storage.add_link(Link(1, "Main", "page"))
            True
            >>> storage.add_link(Link(1, "Main", "page"))  # Duplicate
            False
        """
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
        """,
            (link.source_page_id, link.target_title, link.link_type),
        )

        self.conn.commit()

        # Check if row was inserted (rowcount > 0) or ignored (rowcount == 0)
        added = cursor.rowcount > 0
        return added

    def add_links(self, links: List[Link]) -> int:
        """
        Add multiple links in batch.

        This is more efficient than calling add_link() repeatedly as it
        processes all links in one transaction. Duplicates are automatically
        handled via INSERT OR IGNORE.

        Args:
            links: List of Link objects to add

        Returns:
            Number of new links added (excludes duplicates)

        Example:
            >>> links = [
            ...     Link(1, "Page1", "page"),
            ...     Link(1, "Page2", "page"),
            ...     Link(1, "Page1", "page"),  # Duplicate
            ... ]
            >>> storage.add_links(links)
            2
        """
        if not links:
            return 0

        data = [
            (link.source_page_id, link.target_title, link.link_type) for link in links
        ]

        # Get count before insert
        count_before = self.get_link_count()

        self.conn.executemany(
            """
            INSERT OR IGNORE INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
        """,
            data,
        )

        self.conn.commit()

        # Get count after insert to determine how many were added
        count_after = self.get_link_count()
        added_count = count_after - count_before

        logger.info(
            f"Added {added_count} new links ({len(links) - added_count} duplicates ignored)"
        )
        return added_count

    def get_links(self) -> List[Link]:
        """
        Get all stored links.

        Returns:
            List of all Link objects in storage. Empty list if no links stored.

        Example:
            >>> storage.add_link(Link(1, "Page1", "page"))
            True
            >>> links = storage.get_links()
            >>> len(links)
            1
        """
        cursor = self.conn.execute("""
            SELECT source_page_id, target_title, link_type
            FROM links
            ORDER BY source_page_id, link_type, target_title
        """)

        return [Link(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_links_by_source(self, page_id: int) -> List[Link]:
        """
        Get all links from a specific source page.

        Uses an index for efficient lookup by page ID.

        Args:
            page_id: ID of the source page

        Returns:
            List of Link objects from the specified page. Empty list if
            no links from that page exist.

        Example:
            >>> storage.add_link(Link(1, "PageA", "page"))
            True
            >>> storage.add_link(Link(1, "PageB", "page"))
            True
            >>> links = storage.get_links_by_source(1)
            >>> len(links)
            2
        """
        cursor = self.conn.execute(
            """
            SELECT source_page_id, target_title, link_type
            FROM links
            WHERE source_page_id = ?
            ORDER BY link_type, target_title
        """,
            (page_id,),
        )

        return [Link(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_links_by_type(self, link_type: str) -> List[Link]:
        """
        Get all links of a specific type.

        Args:
            link_type: Type of links to retrieve ('page', 'template', 'file', 'category')

        Returns:
            List of Link objects of the specified type. Empty list if
            no links of that type exist.

        Example:
            >>> storage.add_link(Link(1, "Page1", "page"))
            True
            >>> storage.add_link(Link(1, "Template1", "template"))
            True
            >>> page_links = storage.get_links_by_type("page")
            >>> len(page_links)
            1
        """
        cursor = self.conn.execute(
            """
            SELECT source_page_id, target_title, link_type
            FROM links
            WHERE link_type = ?
            ORDER BY source_page_id, target_title
        """,
            (link_type,),
        )

        return [Link(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_link_count(self) -> int:
        """
        Get total number of unique links stored.

        Returns:
            Count of unique links in storage

        Example:
            >>> storage.get_link_count()
            0
            >>> storage.add_link(Link(1, "Page1", "page"))
            True
            >>> storage.get_link_count()
            1
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM links")
        return cursor.fetchone()[0]

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about stored links.

        Returns a dictionary with counts for total links and breakdown by type.
        All four link types (page, template, file, category) are always included
        in the result, even if their count is zero.

        Returns:
            Dictionary with keys:
                - 'total': Total number of unique links
                - 'page': Number of page links
                - 'template': Number of template links
                - 'file': Number of file links
                - 'category': Number of category links

        Example:
            >>> storage.add_link(Link(1, "Page1", "page"))
            True
            >>> storage.add_link(Link(1, "Template1", "template"))
            True
            >>> stats = storage.get_stats()
            >>> stats['total']
            2
            >>> stats['page']
            1
        """
        # Get counts for each type
        stats = {"total": self.get_link_count()}

        for link_type in ["page", "template", "file", "category"]:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM links WHERE link_type = ?", (link_type,)
            )
            stats[link_type] = cursor.fetchone()[0]

        return stats

    def clear(self) -> None:
        """
        Clear all stored links.

        Removes all links from storage. After calling this method, the
        storage will be empty.

        Example:
            >>> storage.add_link(Link(1, "Page1", "page"))
            True
            >>> storage.get_link_count()
            1
            >>> storage.clear()
            >>> storage.get_link_count()
            0
        """
        self.conn.execute("DELETE FROM links")
        self.conn.commit()
        logger.info("Cleared all links from storage")
