"""MediaWiki Recent Changes API client."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .client import MediaWikiAPIClient
from .exceptions import APIError

logger = logging.getLogger(__name__)


class RecentChange:
    """
    Represents a single change from MediaWiki recent changes feed.

    Attributes:
        rcid: Recent change ID (unique)
        type: Type of change ('edit', 'new', 'log')
        namespace: Namespace ID of affected page
        title: Page title (with namespace prefix)
        pageid: Page ID (0 for deleted pages)
        revid: New revision ID (0 for non-edit changes)
        old_revid: Previous revision ID (0 for new pages)
        timestamp: When the change occurred (UTC)
        user: Username who made the change
        userid: User ID (0 for anonymous users)
        comment: Edit comment or log comment
        oldlen: Previous content length in bytes
        newlen: New content length in bytes
        log_type: Log type (only for LOG changes)
        log_action: Log action type (only for LOG changes)
    """

    def __init__(
        self,
        rcid: int,
        type: str,
        namespace: int,
        title: str,
        pageid: int,
        revid: int,
        old_revid: int,
        timestamp: datetime,
        user: str,
        userid: int,
        comment: str,
        oldlen: int,
        newlen: int,
        log_type: Optional[str] = None,
        log_action: Optional[str] = None,
    ):
        self.rcid = rcid
        self.type = type
        self.namespace = namespace
        self.title = title
        self.pageid = pageid
        self.revid = revid
        self.old_revid = old_revid
        self.timestamp = timestamp
        self.user = user
        self.userid = userid
        self.comment = comment
        self.oldlen = oldlen
        self.newlen = newlen
        self.log_type = log_type
        self.log_action = log_action

    @property
    def is_new_page(self) -> bool:
        """Check if this change created a new page."""
        return self.type == "new"

    @property
    def is_edit(self) -> bool:
        """Check if this change edited an existing page."""
        return self.type == "edit"

    @property
    def is_deletion(self) -> bool:
        """Check if this change deleted a page."""
        return self.type == "log" and self.log_action == "delete"

    @property
    def size_change(self) -> int:
        """Calculate size change in bytes (positive = growth, negative = shrinkage)."""
        return self.newlen - self.oldlen

    def __repr__(self) -> str:
        return (
            f"RecentChange(type={self.type}, title={self.title}, "
            f"timestamp={self.timestamp}, user={self.user})"
        )


class RecentChangesClient:
    """
    Client for querying MediaWiki recent changes.

    Provides methods to fetch and parse recent changes from the MediaWiki
    recentchanges API, supporting time range filtering, namespace filtering,
    and automatic pagination.

    Example:
        >>> api = MediaWikiAPIClient("https://irowiki.org")
        >>> rc_client = RecentChangesClient(api)
        >>> changes = rc_client.get_recent_changes(
        ...     start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ...     end=datetime(2026, 1, 31, tzinfo=timezone.utc)
        ... )
        >>> print(f"Found {len(changes)} changes")
    """

    def __init__(self, api_client: MediaWikiAPIClient):
        """
        Initialize recent changes client.

        Args:
            api_client: MediaWiki API client instance
        """
        self.api = api_client

    def get_recent_changes(
        self,
        start: datetime,
        end: datetime,
        namespace: Optional[Union[int, List[int]]] = None,
        change_type: Optional[Union[str, List[str]]] = None,
        limit: int = 500,
    ) -> List[RecentChange]:
        """
        Fetch all recent changes within a time range.

        Automatically handles pagination to retrieve all changes. Results
        are returned in chronological order (oldest first).

        Args:
            start: Start of time range (inclusive)
            end: End of time range (inclusive)
            namespace: Filter to specific namespace(s) (optional)
            change_type: Filter to specific change type(s): 'new', 'edit', 'log' (optional)
            limit: Maximum results per API request (default 500)

        Returns:
            List of RecentChange objects, ordered chronologically

        Raises:
            ValueError: If start >= end
            APIError: If API request fails

        Example:
            >>> changes = client.get_recent_changes(
            ...     start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ...     end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            ...     namespace=0,
            ...     change_type='edit'
            ... )
        """
        if start >= end:
            raise ValueError(f"start must be before end: {start} >= {end}")

        logger.info(f"Fetching recent changes from {start} to {end}")

        # Build query parameters
        params: Dict[str, Any] = {
            "action": "query",
            "list": "recentchanges",
            "rcstart": self._format_timestamp(start),
            "rcend": self._format_timestamp(end),
            "rcdir": "newer",  # Oldest first
            "rclimit": min(limit, 500),  # Max per request
            "rcprop": "ids|title|timestamp|user|userid|comment|sizes|loginfo",
        }

        # Add namespace filter
        if namespace is not None:
            if isinstance(namespace, list):
                params["rcnamespace"] = "|".join(str(ns) for ns in namespace)
            else:
                params["rcnamespace"] = str(namespace)

        # Add type filter
        if change_type is not None:
            if isinstance(change_type, list):
                params["rctype"] = "|".join(change_type)
            else:
                params["rctype"] = change_type

        # Fetch all changes with pagination
        all_changes: List[RecentChange] = []
        continue_params: Dict[str, Any] = {}
        page_count = 0

        while True:
            # Add continue parameters for pagination
            request_params = {**params, **continue_params}

            # Make API request
            response = self.api._request("query", request_params)

            # Parse changes from response
            if "query" not in response or "recentchanges" not in response["query"]:
                logger.warning("No recentchanges in API response")
                break

            changes = response["query"]["recentchanges"]

            # Parse each change entry
            for change_data in changes:
                try:
                    change = self._parse_change_entry(change_data)
                    all_changes.append(change)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse change entry: {e}, data: {change_data}"
                    )

            page_count += 1
            logger.debug(
                f"Fetched page {page_count}, got {len(changes)} changes, "
                f"total {len(all_changes)}"
            )

            # Check for more pages
            if "continue" not in response:
                break

            continue_params = response["continue"]

        logger.info(f"Fetched {len(all_changes)} recent changes in {page_count} pages")
        return all_changes

    def _parse_change_entry(self, data: Dict[str, Any]) -> RecentChange:
        """
        Parse a single recent change entry from API response.

        Args:
            data: Raw change data from API

        Returns:
            Parsed RecentChange object

        Raises:
            ValueError: If required fields are missing
        """
        # Parse timestamp
        timestamp_str = data.get("timestamp", "")
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Parse log info for log entries
        log_type = data.get("logtype")
        log_action = data.get("logaction")

        return RecentChange(
            rcid=data["rcid"],
            type=data.get("type", "edit"),
            namespace=data["ns"],
            title=data["title"],
            pageid=data.get("pageid", 0),
            revid=data.get("revid", 0),
            old_revid=data.get("old_revid", 0),
            timestamp=timestamp,
            user=data.get("user", ""),
            userid=data.get("userid", 0),
            comment=data.get("comment", ""),
            oldlen=data.get("oldlen", 0),
            newlen=data.get("newlen", 0),
            log_type=log_type,
            log_action=log_action,
        )

    def _format_timestamp(self, dt: datetime) -> str:
        """
        Format datetime for MediaWiki API.

        Args:
            dt: Datetime to format

        Returns:
            ISO 8601 timestamp string in UTC
        """
        # Convert to UTC if timezone-aware
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)

        # Format as ISO 8601
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
