"""
Advanced query functions for temporal and statistical analysis.

This module provides functions for:
- Timeline queries (get page state at specific times)
- Statistics queries (database metrics and analytics)
- Activity analysis

Timeline Functions:
    get_page_at_time: Get page state at specific timestamp
    list_pages_at_time: List all pages as they existed at a time
    get_changes_in_range: Get all changes in date range
    get_page_history: Get complete edit history for a page

Statistics Functions:
    get_db_stats: Overall database statistics
    get_page_stats: Per-page statistics
    get_namespace_stats: Statistics by namespace
    get_contributor_stats: Top contributor metrics
    get_activity_timeline: Edit activity over time
"""

import sqlite3
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from scraper.storage.models import Page, Revision

logger = logging.getLogger(__name__)


# =============================================================================
# Timeline Query Data Classes
# =============================================================================


@dataclass(frozen=True)
class Change:
    """Represents a change (edit) to a page."""

    page_id: int
    page_title: str
    revision_id: int
    timestamp: datetime
    user: Optional[str]
    comment: Optional[str]
    size_delta: int  # Change in size (bytes)


# =============================================================================
# Statistics Query Data Classes
# =============================================================================


@dataclass(frozen=True)
class NamespaceStats:
    """Statistics for a namespace."""

    namespace: int
    page_count: int
    revision_count: int
    total_size: int  # Total bytes of content


@dataclass(frozen=True)
class ContributorStats:
    """Statistics for a contributor."""

    user: str
    edit_count: int
    total_bytes: int
    first_edit: datetime
    last_edit: datetime


@dataclass(frozen=True)
class ActivityPoint:
    """Activity data point for timeline."""

    timestamp: datetime
    edit_count: int
    contributor_count: int


# =============================================================================
# Timeline Query Functions
# =============================================================================


def get_page_at_time(
    connection: sqlite3.Connection, page_id: int, timestamp: datetime
) -> Optional[Revision]:
    """
    Get page state at specific time (time-travel query).

    Returns the most recent revision before or at the given timestamp.

    Args:
        connection: Database connection
        page_id: Page ID
        timestamp: Point in time to query

    Returns:
        Revision instance or None if page didn't exist yet

    Example:
        >>> # Get "Prontera" page as it was on 2020-01-01
        >>> rev = get_page_at_time(db, page_id=1, timestamp=datetime(2020, 1, 1))
        >>> if rev:
        ...     print(rev.content)  # Content as of 2020-01-01
    """
    sql = """
        SELECT *
        FROM revisions
        WHERE page_id = ? AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 1
    """

    cursor = connection.execute(sql, (page_id, timestamp.isoformat()))
    row = cursor.fetchone()

    if not row:
        logger.debug(f"Page {page_id} did not exist at {timestamp}")
        return None

    return Revision.from_db_row(row)


def list_pages_at_time(
    connection: sqlite3.Connection,
    timestamp: datetime,
    limit: int = 100,
    offset: int = 0,
) -> List[Tuple[Page, Revision]]:
    """
    List all pages as they existed at specific time.

    For each page, returns the page metadata and its latest revision
    before the given timestamp.

    Args:
        connection: Database connection
        timestamp: Point in time to query
        limit: Maximum pages to return
        offset: Number of pages to skip

    Returns:
        List of (Page, Revision) tuples

    Example:
        >>> # Get all pages as they were on 2020-01-01
        >>> pages = list_pages_at_time(db, datetime(2020, 1, 1))
        >>> for page, revision in pages:
        ...     print(f"{page.title}: {len(revision.content)} bytes")
    """
    sql = """
        SELECT 
            p.page_id,
            p.namespace,
            p.title,
            p.is_redirect,
            r.*
        FROM pages p
        INNER JOIN (
            -- Get latest revision before timestamp for each page
            SELECT 
                page_id,
                MAX(timestamp) as max_timestamp
            FROM revisions
            WHERE timestamp <= ?
            GROUP BY page_id
        ) latest ON p.page_id = latest.page_id
        INNER JOIN revisions r 
            ON r.page_id = latest.page_id 
            AND r.timestamp = latest.max_timestamp
        ORDER BY p.namespace, p.title
        LIMIT ? OFFSET ?
    """

    cursor = connection.execute(sql, (timestamp.isoformat(), limit, offset))

    results = []
    for row in cursor.fetchall():
        page = Page(
            page_id=row["page_id"],
            namespace=row["namespace"],
            title=row["title"],
            is_redirect=bool(row["is_redirect"]),
        )

        revision = Revision.from_db_row(row)

        results.append((page, revision))

    logger.debug(f"Found {len(results)} pages at {timestamp}")
    return results


def get_changes_in_range(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
    limit: int = 100,
    offset: int = 0,
) -> List[Change]:
    """
    Get all changes (edits) in date range.

    Args:
        connection: Database connection
        start: Start of date range (inclusive)
        end: End of date range (inclusive)
        limit: Maximum changes to return
        offset: Number of changes to skip

    Returns:
        List of Change instances, ordered by timestamp

    Example:
        >>> # Get all edits in January 2024
        >>> changes = get_changes_in_range(
        ...     db,
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 1, 31, 23, 59, 59)
        ... )
        >>> for change in changes:
        ...     print(f"{change.timestamp}: {change.user} edited {change.page_title}")
    """
    sql = """
        SELECT 
            r.page_id,
            p.title as page_title,
            r.revision_id,
            r.timestamp,
            r.user,
            r.comment,
            r.size as size,
            COALESCE(
                r.size - (
                    SELECT size 
                    FROM revisions 
                    WHERE page_id = r.page_id 
                      AND timestamp < r.timestamp 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ),
                r.size
            ) as size_delta
        FROM revisions r
        INNER JOIN pages p ON r.page_id = p.page_id
        WHERE r.timestamp BETWEEN ? AND ?
        ORDER BY r.timestamp
        LIMIT ? OFFSET ?
    """

    cursor = connection.execute(
        sql, (start.isoformat(), end.isoformat(), limit, offset)
    )

    changes = []
    for row in cursor.fetchall():
        changes.append(
            Change(
                page_id=row["page_id"],
                page_title=row["page_title"],
                revision_id=row["revision_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                user=row["user"],
                comment=row["comment"],
                size_delta=row["size_delta"],
            )
        )

    logger.debug(f"Found {len(changes)} changes between {start} and {end}")
    return changes


def get_page_history(
    connection: sqlite3.Connection, page_id: int, limit: int = 50, offset: int = 0
) -> List[Revision]:
    """
    Get complete edit history for a page.

    Args:
        connection: Database connection
        page_id: Page ID
        limit: Maximum revisions to return
        offset: Number of revisions to skip

    Returns:
        List of Revision instances, newest first
    """
    sql = """
        SELECT *
        FROM revisions
        WHERE page_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """

    cursor = connection.execute(sql, (page_id, limit, offset))
    return [Revision.from_db_row(row) for row in cursor.fetchall()]


# =============================================================================
# Statistics Query Functions
# =============================================================================


def get_db_stats(connection: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get overall database statistics.

    Returns:
        Dictionary with statistics:
        - total_pages: Number of pages
        - total_revisions: Number of revisions
        - total_files: Number of files
        - total_links: Number of links
        - db_size_mb: Database file size in MB
        - avg_content_size: Average revision content size
        - first_edit: Timestamp of oldest revision
        - last_edit: Timestamp of newest revision
    """
    sql = """
        SELECT 
            (SELECT COUNT(*) FROM pages) as total_pages,
            (SELECT COUNT(*) FROM revisions) as total_revisions,
            (SELECT COUNT(*) FROM files) as total_files,
            (SELECT COUNT(*) FROM links) as total_links,
            (SELECT AVG(size) FROM revisions) as avg_content_size,
            (SELECT MIN(timestamp) FROM revisions) as first_edit,
            (SELECT MAX(timestamp) FROM revisions) as last_edit
    """

    cursor = connection.execute(sql)
    row = cursor.fetchone()

    # Get database file size
    db_path_result = connection.execute("PRAGMA database_list").fetchone()
    db_path = db_path_result[2] if db_path_result else None
    db_size_mb = 0.0
    if db_path and Path(db_path).exists():
        db_size_mb = Path(db_path).stat().st_size / (1024 * 1024)

    return {
        "total_pages": row["total_pages"] or 0,
        "total_revisions": row["total_revisions"] or 0,
        "total_files": row["total_files"] or 0,
        "total_links": row["total_links"] or 0,
        "db_size_mb": round(db_size_mb, 2),
        "avg_content_size": (
            round(row["avg_content_size"], 2) if row["avg_content_size"] else 0
        ),
        "first_edit": (
            datetime.fromisoformat(row["first_edit"]) if row["first_edit"] else None
        ),
        "last_edit": (
            datetime.fromisoformat(row["last_edit"]) if row["last_edit"] else None
        ),
    }


def get_page_stats(connection: sqlite3.Connection, page_id: int) -> Dict[str, Any]:
    """
    Get statistics for a specific page.

    Args:
        connection: Database connection
        page_id: Page ID

    Returns:
        Dictionary with page statistics:
        - revision_count: Number of revisions
        - contributor_count: Number of unique contributors
        - first_edit: Timestamp of first revision
        - last_edit: Timestamp of last revision
        - avg_edit_size: Average bytes per edit
        - total_size: Current size in bytes
    """
    sql = """
        SELECT 
            COUNT(*) as revision_count,
            COUNT(DISTINCT user) as contributor_count,
            MIN(timestamp) as first_edit,
            MAX(timestamp) as last_edit,
            AVG(size) as avg_edit_size,
            (SELECT size FROM revisions WHERE page_id = ? ORDER BY timestamp DESC LIMIT 1) as total_size
        FROM revisions
        WHERE page_id = ?
    """

    cursor = connection.execute(sql, (page_id, page_id))
    row = cursor.fetchone()

    return {
        "revision_count": row["revision_count"] or 0,
        "contributor_count": row["contributor_count"] or 0,
        "first_edit": (
            datetime.fromisoformat(row["first_edit"]) if row["first_edit"] else None
        ),
        "last_edit": (
            datetime.fromisoformat(row["last_edit"]) if row["last_edit"] else None
        ),
        "avg_edit_size": round(row["avg_edit_size"], 2) if row["avg_edit_size"] else 0,
        "total_size": row["total_size"] or 0,
    }


def get_namespace_stats(connection: sqlite3.Connection) -> Dict[int, NamespaceStats]:
    """
    Get statistics by namespace.

    Returns:
        Dictionary mapping namespace ID to NamespaceStats
    """
    sql = """
        SELECT 
            p.namespace,
            COUNT(DISTINCT p.page_id) as page_count,
            COUNT(r.revision_id) as revision_count,
            SUM(r.size) as total_size
        FROM pages p
        LEFT JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.namespace
        ORDER BY p.namespace
    """

    cursor = connection.execute(sql)

    stats = {}
    for row in cursor.fetchall():
        stats[row["namespace"]] = NamespaceStats(
            namespace=row["namespace"],
            page_count=row["page_count"],
            revision_count=row["revision_count"] or 0,
            total_size=row["total_size"] or 0,
        )

    return stats


def get_contributor_stats(
    connection: sqlite3.Connection, top_n: int = 10
) -> List[ContributorStats]:
    """
    Get top contributors by edit count.

    Args:
        connection: Database connection
        top_n: Number of top contributors to return

    Returns:
        List of ContributorStats, ordered by edit count descending
    """
    sql = """
        SELECT 
            user,
            COUNT(*) as edit_count,
            SUM(size) as total_bytes,
            MIN(timestamp) as first_edit,
            MAX(timestamp) as last_edit
        FROM revisions
        WHERE user IS NOT NULL AND user != ''
        GROUP BY user
        ORDER BY edit_count DESC
        LIMIT ?
    """

    cursor = connection.execute(sql, (top_n,))

    contributors = []
    for row in cursor.fetchall():
        contributors.append(
            ContributorStats(
                user=row["user"],
                edit_count=row["edit_count"],
                total_bytes=row["total_bytes"],
                first_edit=datetime.fromisoformat(row["first_edit"]),
                last_edit=datetime.fromisoformat(row["last_edit"]),
            )
        )

    return contributors


def get_activity_timeline(
    connection: sqlite3.Connection, granularity: str = "day"
) -> List[ActivityPoint]:
    """
    Get edit activity over time.

    Args:
        connection: Database connection
        granularity: 'day', 'week', or 'month'

    Returns:
        List of ActivityPoint instances
    """
    # SQLite date truncation by granularity
    date_format = {"day": "%Y-%m-%d", "week": "%Y-%W", "month": "%Y-%m"}.get(
        granularity, "%Y-%m-%d"
    )

    sql = f"""
        SELECT 
            strftime('{date_format}', timestamp) as period,
            COUNT(*) as edit_count,
            COUNT(DISTINCT user) as contributor_count
        FROM revisions
        GROUP BY period
        ORDER BY period
    """

    cursor = connection.execute(sql)

    timeline = []
    for row in cursor.fetchall():
        # Parse period back to datetime
        if granularity == "day":
            timestamp = datetime.strptime(row["period"], "%Y-%m-%d")
        elif granularity == "month":
            timestamp = datetime.strptime(row["period"] + "-01", "%Y-%m-%d")
        else:  # week
            # Week format is YYYY-WW, parse accordingly
            year, week = row["period"].split("-")
            timestamp = datetime.strptime(f"{year}-{week}-1", "%Y-%W-%w")

        timeline.append(
            ActivityPoint(
                timestamp=timestamp,
                edit_count=row["edit_count"],
                contributor_count=row["contributor_count"],
            )
        )

    return timeline
