"""Repository for revision CRUD operations."""

import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from scraper.storage.database import Database
from scraper.storage.models import Revision

logger = logging.getLogger(__name__)


class RevisionRepository:
    """Repository for revisions table operations."""

    def __init__(self, db: Database):
        """
        Initialize repository with database.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def insert_revision(self, revision: Revision) -> None:
        """
        Insert single revision.

        Args:
            revision: Revision instance to insert
        """
        # Convert tags list to JSON
        tags_json = json.dumps(revision.tags) if revision.tags else None

        self.conn.execute(
            """
            INSERT OR REPLACE INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                revision.revision_id,
                revision.page_id,
                revision.parent_id,
                revision.timestamp.isoformat(),
                revision.user,
                revision.user_id,
                revision.comment,
                revision.content,
                revision.size,
                revision.sha1,
                1 if revision.minor else 0,
                tags_json,
            ),
        )
        self.conn.commit()
        logger.debug(f"Inserted revision: {revision.revision_id}")

    def insert_revisions_batch(self, revisions: List[Revision]) -> None:
        """
        Batch insert revisions (efficient).

        Args:
            revisions: List of Revision instances
        """
        if not revisions:
            return

        data = [
            (
                r.revision_id,
                r.page_id,
                r.parent_id,
                r.timestamp.isoformat(),
                r.user,
                r.user_id,
                r.comment,
                r.content,
                r.size,
                r.sha1,
                1 if r.minor else 0,
                json.dumps(r.tags) if r.tags else None,
            )
            for r in revisions
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO revisions
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        self.conn.commit()
        logger.info(f"Inserted {len(revisions)} revisions in batch")

    def get_revision(self, revision_id: int) -> Optional[Revision]:
        """
        Get revision by ID.

        Args:
            revision_id: Revision ID to lookup

        Returns:
            Revision instance or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM revisions
            WHERE revision_id = ?
        """,
            (revision_id,),
        )

        row = cursor.fetchone()
        return self._row_to_revision(row) if row else None

    def get_revisions_by_page(
        self, page_id: int, limit: int = 50, offset: int = 0
    ) -> List[Revision]:
        """
        Get revisions for a page (newest first).

        Args:
            page_id: Page ID
            limit: Maximum number of revisions to return
            offset: Number of revisions to skip

        Returns:
            List of Revision instances
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM revisions
            WHERE page_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (page_id, limit, offset),
        )

        return [self._row_to_revision(row) for row in cursor.fetchall()]

    def get_latest_revision(self, page_id: int) -> Optional[Revision]:
        """
        Get most recent revision for a page.

        Args:
            page_id: Page ID

        Returns:
            Latest Revision instance or None if no revisions
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM revisions
            WHERE page_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (page_id,),
        )

        row = cursor.fetchone()
        return self._row_to_revision(row) if row else None

    def get_revisions_in_range(self, start: datetime, end: datetime) -> List[Revision]:
        """
        Get revisions in time range.

        Args:
            start: Start datetime (inclusive)
            end: End datetime (exclusive)

        Returns:
            List of Revision instances
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM revisions
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp
        """,
            (start.isoformat(), end.isoformat()),
        )

        return [self._row_to_revision(row) for row in cursor.fetchall()]

    def get_page_at_time(self, page_id: int, timestamp: datetime) -> Optional[Revision]:
        """
        Get page state at specific time (temporal query).

        Args:
            page_id: Page ID
            timestamp: Time to query

        Returns:
            Revision instance representing page state at that time, or None
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM revisions
            WHERE page_id = ? AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (page_id, timestamp.isoformat()),
        )

        row = cursor.fetchone()
        return self._row_to_revision(row) if row else None

    def count_revisions(self, page_id: Optional[int] = None) -> int:
        """
        Count revisions.

        Args:
            page_id: Count revisions for specific page (None = all revisions)

        Returns:
            Number of revisions
        """
        if page_id is not None:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM revisions WHERE page_id = ?", (page_id,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM revisions")

        return cursor.fetchone()[0]

    def _row_to_revision(self, row: sqlite3.Row) -> Revision:
        """
        Convert database row to Revision instance.

        Args:
            row: SQLite row

        Returns:
            Revision instance
        """
        # Parse tags JSON
        tags = None
        if row["tags"]:
            tags = json.loads(row["tags"])

        return Revision(
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
