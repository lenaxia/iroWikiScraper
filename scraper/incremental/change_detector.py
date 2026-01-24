"""Change detector for incremental updates."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from scraper.api.recentchanges import RecentChange, RecentChangesClient
from scraper.incremental.models import ChangeSet, MovedPage
from scraper.storage.database import Database

logger = logging.getLogger(__name__)


class ChangeDetector:
    """
    Detects changes between scrape runs for incremental updates.

    Coordinates between the database (last scrape time) and recent changes
    API to determine which pages need to be updated.

    Example:
        >>> db = Database("irowiki.db")
        >>> rc_client = RecentChangesClient(api)
        >>> detector = ChangeDetector(db, rc_client)
        >>> changes = detector.detect_changes()
        >>> print(f"New: {len(changes.new_page_ids)}, "
        ...       f"Modified: {len(changes.modified_page_ids)}")
    """

    def __init__(self, database: Database, rc_client: RecentChangesClient):
        """
        Initialize change detector.

        Args:
            database: Database instance for querying scrape history
            rc_client: Recent changes client for fetching changes
        """
        self.db = database
        self.rc_client = rc_client

    def detect_changes(self) -> ChangeSet:
        """
        Detect all changes since last scrape.

        Returns:
            ChangeSet with categorized changes

        Raises:
            APIError: If recent changes API call fails
        """
        logger.info("Starting change detection")

        # Get last successful scrape timestamp
        last_scrape = self._get_last_scrape_timestamp()

        if last_scrape is None:
            logger.info("No previous scrape found, full scrape required")
            return ChangeSet(
                requires_full_scrape=True, detection_time=datetime.now(timezone.utc)
            )

        logger.info(f"Last scrape: {last_scrape}")

        # Fetch recent changes since last scrape
        now = datetime.now(timezone.utc)
        recent_changes = self.rc_client.get_recent_changes(start=last_scrape, end=now)

        logger.info(f"Fetched {len(recent_changes)} recent changes")

        # Categorize changes
        changeset = self._categorize_changes(recent_changes, last_scrape)

        logger.info(f"Change detection complete: {changeset}")
        return changeset

    def _get_last_scrape_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of last successful scrape.

        Returns:
            Timestamp of last completed scrape, or None if no previous scrape
        """
        # Query most recent completed scrape run
        query = """
            SELECT end_time
            FROM scrape_runs
            WHERE status = 'completed'
            ORDER BY end_time DESC
            LIMIT 1
        """

        result = self.db.get_connection().execute(query).fetchone()

        if result is None:
            return None

        timestamp_str = result[0]

        # Parse datetime from SQLite (ISO 8601 string)
        if isinstance(timestamp_str, str):
            # SQLite stores as ISO string, parse it
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            # Already a datetime object
            timestamp = timestamp_str

        return timestamp

    def _categorize_changes(
        self, changes: List[RecentChange], last_scrape: datetime
    ) -> ChangeSet:
        """
        Categorize recent changes into change sets.

        Args:
            changes: List of recent changes from API
            last_scrape: Timestamp of last scrape

        Returns:
            ChangeSet with categorized changes
        """
        new_pages = set()
        modified_pages = set()
        deleted_pages = set()
        moved_pages = []

        # Track pages created then deleted (net zero)
        created_page_ids = set()

        for change in changes:
            page_id = change.pageid

            # Skip invalid page IDs (except for log entries which may have pageid=0)
            if page_id == 0 and change.type != "log":
                logger.warning(f"Skipping change with page_id=0: {change}")
                continue

            # Categorize by change type
            if change.is_new_page:
                new_pages.add(page_id)
                created_page_ids.add(page_id)

            elif change.is_edit:
                # Only add to modified if not a new page
                if page_id not in created_page_ids:
                    modified_pages.add(page_id)

            elif change.is_deletion:
                deleted_pages.add(page_id)
                # If page was created then deleted, remove from new_pages
                if page_id in new_pages:
                    new_pages.remove(page_id)

            elif change.type == "log" and change.log_action == "move":
                # Parse move: need old and new titles
                # Note: MediaWiki API provides move details in log params
                moved_page = MovedPage(
                    page_id=page_id,
                    old_title=change.comment,  # Simplified; real impl parses log params
                    new_title=change.title,
                    namespace=change.namespace,
                    timestamp=change.timestamp,
                )
                moved_pages.append(moved_page)

        # Remove deleted pages from modified set
        modified_pages -= deleted_pages

        return ChangeSet(
            new_page_ids=new_pages,
            modified_page_ids=modified_pages,
            deleted_page_ids=deleted_pages,
            moved_pages=moved_pages,
            last_scrape_time=last_scrape,
            detection_time=datetime.now(timezone.utc),
            requires_full_scrape=False,
        )
