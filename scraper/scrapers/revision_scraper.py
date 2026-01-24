"""Revision history scraping functionality."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from scraper.api.client import MediaWikiAPIClient
from scraper.storage.models import Revision

logger = logging.getLogger(__name__)


class RevisionScraper:
    """Scrapes complete revision history for wiki pages.

    Uses MediaWiki's revisions API to fetch all historical edits
    for a given page with full metadata and content.
    """

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        revision_limit: int = 500,
        include_content: bool = True,
        progress_interval: int = 100,
    ):
        """Initialize revision scraper.

        Args:
            api_client: MediaWiki API client instance
            revision_limit: Revisions per API request (max 500)
            include_content: Whether to fetch full wikitext content
            progress_interval: Log progress every N revisions
        """
        self.api = api_client
        self.revision_limit = min(revision_limit, 500)  # API max is 500
        self.include_content = include_content
        self.progress_interval = progress_interval

    def fetch_revisions(self, page_id: int) -> List[Revision]:
        """Fetch all revisions for a specific page.

        Args:
            page_id: ID of the page to fetch revisions for

        Returns:
            List of Revision objects in chronological order (oldest first)

        Raises:
            APIError: If API request fails
            ValueError: If page_id is invalid

        Example:
            >>> scraper = RevisionScraper(api_client)
            >>> revisions = scraper.fetch_revisions(page_id=1)
            >>> len(revisions)
            42
            >>> revisions[0].revision_id  # First (oldest) revision
            1001
        """
        if not isinstance(page_id, int) or page_id <= 0:
            raise ValueError(f"page_id must be a positive integer, got: {page_id}")

        revisions = []
        continue_params: Optional[Dict[str, Any]] = None

        logger.info(f"Starting revision fetch for page {page_id}")

        while True:
            # Build request parameters
            params = {
                "prop": "revisions",
                "pageids": page_id,
                "rvprop": "ids|timestamp|user|userid|comment|size|sha1|tags",
                "rvlimit": self.revision_limit,
                "rvdir": "newer",  # Oldest first (chronological order)
                "rvslots": "main",  # Get main content slot
            }

            # Add content to properties if requested
            if self.include_content:
                params["rvprop"] += "|content"

            # Add continuation parameters if present
            if continue_params:
                params.update(continue_params)

            # Make API request
            response = self.api.query(params)

            # Extract revisions from response
            # Response structure: query.pages.<page_id>.revisions[]
            pages = response.get("query", {}).get("pages", {})

            # Get page data (key is page_id as string)
            page_data = pages.get(str(page_id))

            if not page_data:
                logger.warning(f"No data found for page {page_id}")
                break

            # Check if page exists
            if "missing" in page_data:
                logger.warning(f"Page {page_id} does not exist")
                break

            # Get revision list
            revision_list = page_data.get("revisions", [])

            if not revision_list:
                logger.info(f"No revisions found for page {page_id}")
                break

            # Parse each revision
            for rev_data in revision_list:
                revision = self._parse_revision(rev_data, page_id)
                revisions.append(revision)

            # Log progress
            if (
                len(revisions) % self.progress_interval == 0
                or len(revisions) < self.progress_interval
            ):
                logger.info(f"Page {page_id}: {len(revisions)} revisions fetched")

            # Check for continuation
            if "continue" not in response:
                break

            continue_params = response["continue"]

        logger.info(f"Page {page_id} complete: {len(revisions)} total revisions")
        return revisions

    def _parse_revision(self, rev_data: Dict[str, Any], page_id: int) -> Revision:
        """Parse a single revision from API response.

        Args:
            rev_data: Raw revision data from API
            page_id: ID of the page this revision belongs to

        Returns:
            Parsed Revision object
        """
        # Extract content from slots structure
        content = ""
        if self.include_content:
            slots = rev_data.get("slots", {})
            main_slot = slots.get("main", {})
            content = main_slot.get("content", "")

        # Parse timestamp (ISO 8601 format from MediaWiki)
        timestamp_str = rev_data.get("timestamp", "")
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Handle deleted/hidden users
        user = rev_data.get("user", "")
        user_id = rev_data.get("userid")

        # Check if user is hidden
        if "userhidden" in rev_data:
            user = ""
            user_id = None

        # Parent ID (None for first revision)
        parent_id = rev_data.get("parentid")
        if parent_id == 0:  # MediaWiki returns 0 for first revision
            parent_id = None

        # Minor edit flag
        minor = "minor" in rev_data

        # Tags (convert to list, default to empty)
        tags = rev_data.get("tags", [])

        return Revision(
            revision_id=rev_data["revid"],
            page_id=page_id,
            parent_id=parent_id,
            timestamp=timestamp,
            user=user,
            user_id=user_id,
            comment=rev_data.get("comment", ""),
            content=content,
            size=rev_data.get("size", 0),
            sha1=rev_data.get("sha1", ""),
            minor=minor,
            tags=tags if tags else None,
        )
