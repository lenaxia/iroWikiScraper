"""Modified page detector for incremental updates."""

import logging
from typing import List

from scraper.storage.database import Database
from scraper.api.exceptions import PageNotFoundError
from scraper.incremental.models import PageUpdateInfo

logger = logging.getLogger(__name__)


class ModifiedPageDetector:
    """
    Detects which existing pages need revision updates.

    Queries the database to determine the current state of modified pages,
    including which revisions are already stored, so we can fetch only
    new revisions from the API.

    Example:
        >>> db = Database("irowiki.db")
        >>> detector = ModifiedPageDetector(db)
        >>> info = detector.get_page_update_info(123)
        >>> print(f"Page has {info.total_revisions_stored} revisions")
        >>> print(f"Last revision: {info.highest_revision_id}")
    """

    def __init__(self, database: Database):
        """
        Initialize modified page detector.

        Args:
            database: Database instance for querying page state
        """
        self.db = database

    def get_page_update_info(self, page_id: int) -> PageUpdateInfo:
        """
        Get update information for a single modified page.

        Args:
            page_id: Page ID to query

        Returns:
            PageUpdateInfo with current page state

        Raises:
            PageNotFoundError: If page not found in database

        Example:
            >>> info = detector.get_page_update_info(123)
            >>> print(f"Fetch revisions after {info.highest_revision_id}")
        """
        query = """
            SELECT 
                p.page_id,
                p.namespace,
                p.title,
                p.is_redirect,
                COALESCE(MAX(r.revision_id), 0) as highest_revision_id,
                COALESCE(MAX(r.timestamp), datetime('now')) as last_revision_timestamp,
                COUNT(r.revision_id) as total_revisions
            FROM pages p
            LEFT JOIN revisions r ON p.page_id = r.page_id
            WHERE p.page_id = ?
            GROUP BY p.page_id
        """

        result = self.db.get_connection().execute(query, (page_id,)).fetchone()

        if result is None:
            raise PageNotFoundError(f"Page {page_id} not found in database")

        # Unpack result
        (
            page_id,
            namespace,
            title,
            is_redirect,
            highest_rev_id,
            last_timestamp,
            total_revs,
        ) = result

        # Warn if page has no revisions (data integrity issue)
        if total_revs == 0:
            logger.warning(f"Page {page_id} ({title}) has no revisions in database")

        # Parse datetime from SQLite (ISO 8601 string)
        from datetime import datetime

        if isinstance(last_timestamp, str):
            last_timestamp = datetime.fromisoformat(
                last_timestamp.replace("Z", "+00:00")
            )

        return PageUpdateInfo(
            page_id=page_id,
            namespace=namespace,
            title=title,
            is_redirect=bool(is_redirect),
            highest_revision_id=highest_rev_id,
            last_revision_timestamp=last_timestamp,
            total_revisions_stored=total_revs,
        )

    def get_batch_update_info(self, page_ids: List[int]) -> List[PageUpdateInfo]:
        """
        Get update information for multiple pages efficiently.

        Uses a single query with JOIN to fetch all page information at once.
        Skips pages not found in database (logs warning).

        Args:
            page_ids: List of page IDs to query

        Returns:
            List of PageUpdateInfo objects (may be shorter than input if pages missing)

        Example:
            >>> page_ids = [100, 101, 102, 103, 104]
            >>> infos = detector.get_batch_update_info(page_ids)
            >>> print(f"Found {len(infos)} pages in database")
        """
        if not page_ids:
            return []

        logger.info(f"Querying update info for {len(page_ids)} pages")

        # Build query with IN clause
        placeholders = ",".join("?" * len(page_ids))
        query = f"""
            SELECT 
                p.page_id,
                p.namespace,
                p.title,
                p.is_redirect,
                COALESCE(MAX(r.revision_id), 0) as highest_revision_id,
                COALESCE(MAX(r.timestamp), datetime('now')) as last_revision_timestamp,
                COUNT(r.revision_id) as total_revisions
            FROM pages p
            LEFT JOIN revisions r ON p.page_id = r.page_id
            WHERE p.page_id IN ({placeholders})
            GROUP BY p.page_id
        """

        results = self.db.get_connection().execute(query, page_ids).fetchall()

        # Warn if some pages missing
        found_ids = {row[0] for row in results}
        missing_ids = set(page_ids) - found_ids
        if missing_ids:
            logger.warning(
                f"{len(missing_ids)} pages not found in database: {missing_ids}"
            )

        # Convert rows to PageUpdateInfo objects
        infos = []
        for row in results:
            (
                page_id,
                namespace,
                title,
                is_redirect,
                highest_rev_id,
                last_timestamp,
                total_revs,
            ) = row

            if total_revs == 0:
                logger.warning(f"Page {page_id} ({title}) has no revisions")

            # Parse datetime from SQLite
            from datetime import datetime

            if isinstance(last_timestamp, str):
                last_timestamp = datetime.fromisoformat(
                    last_timestamp.replace("Z", "+00:00")
                )

            infos.append(
                PageUpdateInfo(
                    page_id=page_id,
                    namespace=namespace,
                    title=title,
                    is_redirect=bool(is_redirect),
                    highest_revision_id=highest_rev_id,
                    last_revision_timestamp=last_timestamp,
                    total_revisions_stored=total_revs,
                )
            )

        logger.info(f"Retrieved update info for {len(infos)} pages")
        return infos
