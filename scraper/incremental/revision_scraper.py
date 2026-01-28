"""Incremental revision scraper for fetching only new revisions."""

import logging
from typing import Dict, List

from scraper.api.client import MediaWikiAPIClient
from scraper.incremental.models import PageUpdateInfo
from scraper.storage.database import Database
from scraper.storage.models import Revision
from scraper.storage.revision_repository import RevisionRepository

logger = logging.getLogger(__name__)


class IncrementalRevisionScraper:
    """
    Scrapes only new revisions for modified pages.

    Uses the highest_revision_id to fetch revisions newer than what's stored,
    dramatically reducing API calls and bandwidth.

    Example:
        >>> scraper = IncrementalRevisionScraper(api_client, db)
        >>> info = PageUpdateInfo(page_id=123, highest_revision_id=1000, ...)
        >>> new_revs = scraper.fetch_new_revisions(info)
        >>> print(f"Found {len(new_revs)} new revisions")
    """

    def __init__(self, api_client: MediaWikiAPIClient, database: Database):
        """
        Initialize incremental revision scraper.

        Args:
            api_client: MediaWiki API client
            database: Database instance
        """
        self.api = api_client
        self.db = database
        self.revision_repo = RevisionRepository(database)

    def fetch_new_revisions(self, info: PageUpdateInfo) -> List[Revision]:
        """
        Fetch revisions newer than the highest known revision.

        Args:
            info: Page update info containing highest_revision_id

        Returns:
            List of new Revision objects

        Example:
            >>> info = PageUpdateInfo(page_id=123, highest_revision_id=1000, ...)
            >>> revisions = scraper.fetch_new_revisions(info)
        """
        logger.info(
            f"Fetching new revisions for page {info.page_id} "
            f"(after revision {info.highest_revision_id})"
        )

        # Build API query parameters
        params = {
            "pageids": info.page_id,
            "prop": "revisions",
            "rvprop": "ids|timestamp|user|userid|comment|content|sha1|size|tags",
            "rvstartid": info.highest_revision_id + 1,  # Start AFTER highest known
            "rvdir": "newer",  # Chronological order
            "rvlimit": 500,
        }

        revisions = []

        while True:
            response = self.api.query(params)

            # Check if page exists in response
            pages = response.get("query", {}).get("pages", {})
            if not pages:
                logger.warning(f"No page data returned for page {info.page_id}")
                break

            # Get page data (key is page_id as string)
            page_data = pages.get(str(info.page_id))
            if not page_data:
                logger.warning(f"Page {info.page_id} not found in response")
                break

            # Check for missing page
            if "missing" in page_data:
                logger.warning(f"Page {info.page_id} is missing (may be deleted)")
                break

            # Get revisions
            if "revisions" not in page_data:
                logger.debug(f"No new revisions for page {info.page_id}")
                break

            # Parse each revision
            for rev_data in page_data["revisions"]:
                revision = self._parse_revision(rev_data, info.page_id)
                revisions.append(revision)

            # Check for continuation
            if "continue" not in response:
                break

            params.update(response["continue"])

        logger.info(f"Fetched {len(revisions)} new revisions for page {info.page_id}")
        return revisions

    def fetch_new_revisions_batch(
        self, infos: List[PageUpdateInfo]
    ) -> Dict[int, List[Revision]]:
        """
        Fetch new revisions for multiple pages.

        Args:
            infos: List of PageUpdateInfo objects

        Returns:
            Dictionary mapping page_id to list of new revisions

        Example:
            >>> infos = [info1, info2, info3]
            >>> results = scraper.fetch_new_revisions_batch(infos)
            >>> print(f"Page 123 has {len(results[123])} new revisions")
        """
        logger.info(f"Fetching new revisions for {len(infos)} pages (batch)")

        results = {}
        for info in infos:
            try:
                revisions = self.fetch_new_revisions(info)
                results[info.page_id] = revisions
            except Exception as e:
                logger.error(f"Failed to fetch revisions for page {info.page_id}: {e}")
                results[info.page_id] = []

        total_revisions = sum(len(revs) for revs in results.values())
        logger.info(
            f"Fetched {total_revisions} total new revisions across {len(infos)} pages"
        )
        return results

    def insert_new_revisions(self, page_id: int, revisions: List[Revision]) -> int:
        """
        Insert new revisions, checking for duplicates.

        Args:
            page_id: Page ID
            revisions: List of revisions to insert

        Returns:
            Number of revisions actually inserted (after deduplication)
        """
        if not revisions:
            return 0

        # Get existing revision IDs for this page
        existing_revisions = self.revision_repo.get_revisions_by_page(page_id)
        existing_ids = {rev.revision_id for rev in existing_revisions}

        # Filter out duplicates
        new_revisions = [
            rev for rev in revisions if rev.revision_id not in existing_ids
        ]

        if len(new_revisions) < len(revisions):
            duplicates = len(revisions) - len(new_revisions)
            logger.warning(
                f"Skipped {duplicates} duplicate revisions for page {page_id}"
            )

        # Insert new revisions
        for revision in new_revisions:
            self.revision_repo.insert_revision(revision)

        logger.info(f"Inserted {len(new_revisions)} new revisions for page {page_id}")
        return len(new_revisions)

    def _parse_revision(self, rev_data: dict, page_id: int) -> Revision:
        """
        Parse revision data from API response.

        Args:
            rev_data: Raw revision data from API
            page_id: Page ID

        Returns:
            Parsed Revision object
        """
        from datetime import datetime

        # Parse timestamp
        timestamp_str = rev_data.get("timestamp", "")
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Parse tags
        tags = rev_data.get("tags", []) or []

        # Get content
        slots = rev_data.get("slots", {})
        main_slot = slots.get("main", {})
        content = main_slot.get("*", "") if main_slot else rev_data.get("*", "")

        return Revision(
            revision_id=rev_data["revid"],
            page_id=page_id,
            parent_id=rev_data.get("parentid") or None,  # Convert 0 to None
            timestamp=timestamp,
            user=rev_data.get("user", ""),
            user_id=(
                rev_data.get("userid") if "userid" in rev_data else None
            ),  # 0 is valid for anonymous edits
            comment=rev_data.get("comment", ""),
            content=content,
            size=rev_data.get("size", 0),
            sha1=rev_data.get("sha1", ""),
            minor=rev_data.get("minor", False),
            tags=tags if tags else None,
        )
