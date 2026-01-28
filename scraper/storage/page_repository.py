"""Repository for page CRUD operations."""

import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from scraper.storage.database import Database
from scraper.storage.models import Page

logger = logging.getLogger(__name__)


class PageRepository:
    """Repository for pages table operations."""

    def __init__(self, db: Database):
        """
        Initialize repository with database.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def insert_page(self, page: Page) -> int:
        """
        Insert a single page.

        Args:
            page: Page instance to insert

        Returns:
            page_id of inserted page

        Raises:
            sqlite3.IntegrityError: If unique constraint violated
        """
        cursor = self.conn.execute(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                namespace = excluded.namespace,
                title = excluded.title,
                is_redirect = excluded.is_redirect,
                updated_at = excluded.updated_at
        """,
            (
                page.page_id,
                page.namespace,
                page.title,
                1 if page.is_redirect else 0,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )

        self.conn.commit()

        # Return the page_id (either newly inserted or existing)
        page_id = page.page_id

        logger.debug(
            f"Inserted/updated page: {page.namespace}:{page.title} (id={page_id})"
        )
        return page_id

    def insert_pages_batch(self, pages: List[Page]) -> None:
        """
        Insert multiple pages in batch (efficient).

        Uses ON CONFLICT on page_id to handle duplicates idempotently.

        Args:
            pages: List of Page instances to insert
        """
        if not pages:
            return

        now = datetime.utcnow().isoformat()

        data = [
            (p.page_id, p.namespace, p.title, 1 if p.is_redirect else 0, now, now)
            for p in pages
        ]

        # Use page_id as the primary conflict resolution key
        self.conn.executemany(
            """
            INSERT INTO pages (page_id, namespace, title, is_redirect, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                namespace = excluded.namespace,
                title = excluded.title,
                is_redirect = excluded.is_redirect,
                updated_at = excluded.updated_at
        """,
            data,
        )

        self.conn.commit()
        logger.info(f"Inserted/updated {len(pages)} pages in batch")

    def get_page_by_id(self, page_id: int) -> Optional[Page]:
        """
        Get page by ID.

        Args:
            page_id: Page ID to lookup

        Returns:
            Page instance or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT page_id, namespace, title, is_redirect, created_at, updated_at
            FROM pages
            WHERE page_id = ?
        """,
            (page_id,),
        )

        row = cursor.fetchone()

        if row:
            return self._row_to_page(row)
        return None

    def get_page_by_title(self, namespace: int, title: str) -> Optional[Page]:
        """
        Get page by namespace and title.

        Args:
            namespace: Page namespace
            title: Page title

        Returns:
            Page instance or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT page_id, namespace, title, is_redirect, created_at, updated_at
            FROM pages
            WHERE namespace = ? AND title = ?
        """,
            (namespace, title),
        )

        row = cursor.fetchone()

        if row:
            return self._row_to_page(row)
        return None

    def list_pages(
        self, namespace: Optional[int] = None, limit: int = 100, offset: int = 0
    ) -> List[Page]:
        """
        List pages with optional filtering and pagination.

        Args:
            namespace: Filter by namespace (None = all namespaces)
            limit: Maximum number of pages to return
            offset: Number of pages to skip

        Returns:
            List of Page instances
        """
        if namespace is not None:
            cursor = self.conn.execute(
                """
                SELECT page_id, namespace, title, is_redirect, created_at, updated_at
                FROM pages
                WHERE namespace = ?
                ORDER BY title
                LIMIT ? OFFSET ?
            """,
                (namespace, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT page_id, namespace, title, is_redirect, created_at, updated_at
                FROM pages
                ORDER BY namespace, title
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

        return [self._row_to_page(row) for row in cursor.fetchall()]

    def update_page(self, page: Page) -> None:
        """
        Update existing page.

        Args:
            page: Page instance with page_id set

        Raises:
            ValueError: If page_id is None
        """
        if not hasattr(page, "page_id") or page.page_id is None:
            raise ValueError("Page must have page_id to update")

        self.conn.execute(
            """
            UPDATE pages
            SET namespace = ?,
                title = ?,
                is_redirect = ?,
                updated_at = ?
            WHERE page_id = ?
        """,
            (
                page.namespace,
                page.title,
                1 if page.is_redirect else 0,
                datetime.utcnow().isoformat(),
                page.page_id,
            ),
        )

        self.conn.commit()
        logger.debug(f"Updated page: {page.page_id}")

    def delete_page(self, page_id: int) -> None:
        """
        Delete page by ID.

        Args:
            page_id: Page ID to delete
        """
        self.conn.execute("DELETE FROM pages WHERE page_id = ?", (page_id,))
        self.conn.commit()
        logger.debug(f"Deleted page: {page_id}")

    def count_pages(self, namespace: Optional[int] = None) -> int:
        """
        Count pages.

        Args:
            namespace: Filter by namespace (None = all namespaces)

        Returns:
            Number of pages
        """
        if namespace is not None:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM pages WHERE namespace = ?", (namespace,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM pages")

        return cursor.fetchone()[0]

    def _row_to_page(self, row: sqlite3.Row) -> Page:
        """
        Convert database row to Page instance.

        Args:
            row: SQLite row

        Returns:
            Page instance
        """
        return Page(
            page_id=row["page_id"],
            namespace=row["namespace"],
            title=row["title"],
            is_redirect=bool(row["is_redirect"]),
        )
