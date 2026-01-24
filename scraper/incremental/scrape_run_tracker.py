"""Scrape run tracking for incremental updates."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from scraper.storage.database import Database

logger = logging.getLogger(__name__)


class ScrapeRunTracker:
    """
    Tracks scrape runs and provides last scrape timestamp.

    This class manages scrape_runs table operations, including:
    - Creating new scrape runs
    - Completing runs with statistics
    - Marking runs as failed
    - Querying for last successful scrape timestamp

    The last scrape timestamp is critical for incremental updates—it
    determines which changes to fetch from the RecentChanges API.

    Example:
        >>> tracker = ScrapeRunTracker(db)
        >>> run_id = tracker.create_scrape_run('incremental')
        >>> # ... perform scraping ...
        >>> stats = {'pages_new': 10, 'pages_modified': 5}
        >>> tracker.complete_scrape_run(run_id, stats)
        >>> last = tracker.get_last_scrape_timestamp()
    """

    def __init__(self, database: Database):
        """
        Initialize scrape run tracker.

        Args:
            database: Database instance with initialized schema
        """
        self.db = database
        self.conn = database.get_connection()

    def get_last_scrape_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of last successful scrape.

        Queries scrape_runs table for the most recent completed run
        and returns its end_time. This timestamp is used to determine
        which changes to fetch from RecentChanges API.

        Returns:
            Timestamp of last successful scrape, or None if no completed
            scrapes exist (first run scenario)

        Example:
            >>> tracker.get_last_scrape_timestamp()
            datetime.datetime(2026, 1, 23, 10, 30, 0)

        Note:
            - Ignores failed and interrupted runs
            - Only considers runs with status='completed'
            - Returns None for brand new database (first scrape)
        """
        query = """
            SELECT end_time
            FROM scrape_runs
            WHERE status = 'completed'
            ORDER BY end_time DESC
            LIMIT 1
        """

        result = self.conn.execute(query).fetchone()

        if result and result[0]:
            # Parse ISO timestamp from SQLite
            timestamp_str = result[0]
            return datetime.fromisoformat(timestamp_str)

        return None

    def create_scrape_run(self, run_type: str = "incremental") -> int:
        """
        Create new scrape run record.

        Inserts a new row in scrape_runs table with status='running'
        and returns the auto-generated run_id for later updates.

        Args:
            run_type: Type of scrape ('incremental' or 'full')

        Returns:
            run_id for the newly created scrape run

        Example:
            >>> run_id = tracker.create_scrape_run('incremental')
            >>> print(f"Started scrape run {run_id}")

        Note:
            - start_time is automatically set to CURRENT_TIMESTAMP
            - status defaults to 'running'
            - Statistics (pages_scraped, etc.) default to 0
        """
        query = """
            INSERT INTO scrape_runs (start_time, status)
            VALUES (?, 'running')
        """

        cursor = self.conn.execute(query, (datetime.utcnow().isoformat(),))
        self.conn.commit()

        run_id = cursor.lastrowid
        logger.info(f"Created scrape run {run_id} (type={run_type})")

        return run_id

    def complete_scrape_run(self, run_id: int, stats: Dict[str, Any]) -> None:
        """
        Mark scrape run as completed with statistics.

        Updates the scrape run record with final statistics and sets
        status to 'completed' and end_time to current timestamp.

        Args:
            run_id: ID of the scrape run to complete
            stats: Dictionary with statistics (pages_new, pages_modified, etc.)

        Example:
            >>> stats = {
            ...     'pages_new': 10,
            ...     'pages_modified': 20,
            ...     'pages_deleted': 2,
            ...     'revisions_added': 45,
            ...     'files_downloaded': 5
            ... }
            >>> tracker.complete_scrape_run(run_id, stats)

        Note:
            - Sets status='completed'
            - Sets end_time to current timestamp
            - Stores all provided statistics
            - This completed run becomes the new "last scrape" timestamp
        """
        query = """
            UPDATE scrape_runs
            SET status = 'completed',
                end_time = ?,
                pages_scraped = ?,
                revisions_scraped = ?,
                files_downloaded = ?
            WHERE run_id = ?
        """

        self.conn.execute(
            query,
            (
                datetime.utcnow().isoformat(),
                stats.get("pages_new", 0)
                + stats.get("pages_modified", 0)
                + stats.get("pages_deleted", 0)
                + stats.get("pages_moved", 0),
                stats.get("revisions_added", 0),
                stats.get("files_downloaded", 0),
                run_id,
            ),
        )
        self.conn.commit()

        logger.info(
            f"Completed scrape run {run_id}: "
            f"pages={stats.get('pages_new', 0) + stats.get('pages_modified', 0)}, "
            f"revisions={stats.get('revisions_added', 0)}"
        )

    def fail_scrape_run(self, run_id: int, error: str) -> None:
        """
        Mark scrape run as failed.

        Sets status to 'failed', records the error message, and sets
        end_time. Failed runs do NOT update the last scrape timestamp—
        only successful runs count for incremental updates.

        Args:
            run_id: ID of the scrape run that failed
            error: Error message describing the failure

        Example:
            >>> try:
            ...     # ... scraping code ...
            ... except Exception as e:
            ...     tracker.fail_scrape_run(run_id, str(e))
            ...     raise

        Note:
            - Sets status='failed'
            - Sets end_time to current timestamp
            - Records error message
            - Does NOT update last_scrape_timestamp (failed runs don't count)
        """
        query = """
            UPDATE scrape_runs
            SET status = 'failed',
                end_time = ?,
                error_message = ?
            WHERE run_id = ?
        """

        self.conn.execute(query, (datetime.utcnow().isoformat(), error, run_id))
        self.conn.commit()

        logger.error(f"Failed scrape run {run_id}: {error}")

    def get_scrape_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        """
        Get status and statistics for a scrape run.

        Retrieves complete information about a scrape run including
        status, timestamps, and statistics.

        Args:
            run_id: ID of the scrape run to query

        Returns:
            Dictionary with run information, or None if not found

        Example:
            >>> info = tracker.get_scrape_run_status(123)
            >>> print(f"Status: {info['status']}")
            >>> print(f"Pages: {info['pages_scraped']}")
        """
        query = """
            SELECT run_id, start_time, end_time, status,
                   pages_scraped, revisions_scraped, files_downloaded,
                   error_message
            FROM scrape_runs
            WHERE run_id = ?
        """

        result = self.conn.execute(query, (run_id,)).fetchone()

        if not result:
            return None

        return {
            "run_id": result[0],
            "start_time": datetime.fromisoformat(result[1]) if result[1] else None,
            "end_time": datetime.fromisoformat(result[2]) if result[2] else None,
            "status": result[3],
            "pages_scraped": result[4],
            "revisions_scraped": result[5],
            "files_downloaded": result[6],
            "error_message": result[7],
        }

    def list_recent_runs(self, limit: int = 10) -> list[dict]:
        """
        Get list of recent scrape runs.

        Args:
            limit: Maximum number of runs to return (default 10)

        Returns:
            List of dictionaries with run information, ordered by most recent first

        Example:
            >>> recent = tracker.list_recent_runs(5)
            >>> for run in recent:
            ...     print(f"Run {run['run_id']}: {run['status']}")
        """
        query = """
            SELECT run_id, start_time, end_time, status,
                   pages_scraped, revisions_scraped, files_downloaded
            FROM scrape_runs
            ORDER BY start_time DESC
            LIMIT ?
        """

        results = self.conn.execute(query, (limit,)).fetchall()

        return [
            {
                "run_id": r[0],
                "start_time": r[1],
                "end_time": r[2],
                "status": r[3],
                "pages_scraped": r[4],
                "revisions_scraped": r[5],
                "files_downloaded": r[6],
            }
            for r in results
        ]

    def get_run_statistics(self) -> dict:
        """
        Get aggregate statistics across all scrape runs.

        Returns:
            Dictionary with aggregate statistics including:
            - total_runs: Total number of runs
            - completed_runs: Number of successful runs
            - failed_runs: Number of failed runs
            - total_pages: Total pages scraped across all runs
            - total_revisions: Total revisions scraped across all runs
            - total_files: Total files downloaded across all runs

        Example:
            >>> stats = tracker.get_run_statistics()
            >>> print(f"Total runs: {stats['total_runs']}")
            >>> print(f"Success rate: {stats['completed_runs']}/{stats['total_runs']}")
        """
        query = """
            SELECT 
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                SUM(pages_scraped) as total_pages,
                SUM(revisions_scraped) as total_revisions,
                SUM(files_downloaded) as total_files
            FROM scrape_runs
        """

        result = self.conn.execute(query).fetchone()

        return {
            "total_runs": result[0] or 0,
            "completed_runs": result[1] or 0,
            "failed_runs": result[2] or 0,
            "total_pages": result[3] or 0,
            "total_revisions": result[4] or 0,
            "total_files": result[5] or 0,
        }
