"""New page detector for incremental updates."""

import logging
from datetime import datetime, timezone
from typing import List, Set

from scraper.incremental.models import NewPageInfo
from scraper.storage.database import Database

logger = logging.getLogger(__name__)


class NewPageDetector:
    """
    Detects which pages are genuinely new (not in database).

    Used during incremental updates to distinguish new pages (need full scrape)
    from modified pages (need only new revisions).

    Example:
        >>> db = Database("irowiki.db")
        >>> detector = NewPageDetector(db)
        >>> is_new = detector.verify_new_page(12345)
        >>> if is_new:
        ...     print("Need to scrape full page history")
    """

    def __init__(self, database: Database):
        """
        Initialize new page detector.

        Args:
            database: Database instance for checking page existence
        """
        self.db = database

    def verify_new_page(self, page_id: int) -> bool:
        """
        Check if a page is genuinely new (not in database).

        Args:
            page_id: Page ID to check

        Returns:
            True if page not in database, False if it exists

        Example:
            >>> is_new = detector.verify_new_page(12345)
            >>> if is_new:
            ...     print("This is a new page")
        """
        query = "SELECT 1 FROM pages WHERE page_id = ? LIMIT 1"
        result = self.db.get_connection().execute(query, (page_id,)).fetchone()

        exists = result is not None

        if exists:
            logger.debug(f"Page {page_id} already exists in database")
        else:
            logger.debug(f"Page {page_id} is new (not in database)")

        return not exists

    def verify_new_pages(self, page_ids: List[int]) -> Set[int]:
        """
        Check which pages are genuinely new (batch operation).

        Efficiently checks multiple pages in a single query.

        Args:
            page_ids: List of page IDs to check

        Returns:
            Set of page IDs that don't exist in database

        Example:
            >>> candidate_ids = [100, 101, 102, 103]
            >>> new_ids = detector.verify_new_pages(candidate_ids)
            >>> print(f"{len(new_ids)} pages are genuinely new")
        """
        if not page_ids:
            logger.debug("No page IDs to verify")
            return set()

        logger.info(f"Verifying {len(page_ids)} pages for newness")

        # Query existing pages
        placeholders = ",".join("?" * len(page_ids))
        query = f"SELECT page_id FROM pages WHERE page_id IN ({placeholders})"

        results = self.db.get_connection().execute(query, page_ids).fetchall()
        existing_ids = {row[0] for row in results}

        # Calculate new pages (in input but not in database)
        candidate_ids = set(page_ids)
        new_ids = candidate_ids - existing_ids

        logger.info(
            f"Found {len(new_ids)} new pages, {len(existing_ids)} already exist"
        )

        if existing_ids:
            logger.warning(
                f"Pages marked as 'new' but already in database: {existing_ids}"
            )

        return new_ids

    def filter_new_pages(self, page_ids: List[int]) -> Set[int]:
        """
        Filter list to only genuinely new pages.

        Alias for verify_new_pages with clearer intent.

        Args:
            page_ids: List of candidate page IDs

        Returns:
            Set of page IDs not in database
        """
        return self.verify_new_pages(page_ids)

    def get_new_page_info(
        self, page_id: int, title: str, namespace: int
    ) -> NewPageInfo:
        """
        Create NewPageInfo for a new page.

        Does not query database (page doesn't exist yet). Uses metadata
        from recent changes or other source.

        Args:
            page_id: Page ID from recent changes
            title: Page title from recent changes
            namespace: Namespace ID from recent changes

        Returns:
            NewPageInfo object ready for scraping

        Example:
            >>> # From recent change entry
            >>> change = recent_changes[0]
            >>> info = detector.get_new_page_info(
            ...     page_id=change.pageid,
            ...     title=change.title,
            ...     namespace=change.namespace
            ... )
            >>> print(info.to_scrape_params())
        """
        return NewPageInfo(
            page_id=page_id,
            namespace=namespace,
            title=title,
            detected_at=datetime.now(timezone.utc),
        )
