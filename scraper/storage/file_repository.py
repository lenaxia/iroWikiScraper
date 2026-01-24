"""Repository for file metadata CRUD operations."""

import sqlite3
import logging
from typing import List, Optional
from datetime import datetime

from scraper.storage.models import FileMetadata
from scraper.storage.database import Database

logger = logging.getLogger(__name__)


class FileRepository:
    """Repository for files table operations."""

    def __init__(self, db: Database):
        """
        Initialize repository with database.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def insert_file(self, file: FileMetadata) -> None:
        """
        Insert single file metadata.

        Args:
            file: FileMetadata instance to insert
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO files
            (filename, url, descriptionurl, sha1, size, width, height, 
             mime_type, timestamp, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                file.filename,
                file.url,
                file.descriptionurl,
                file.sha1,
                file.size,
                file.width,
                file.height,
                file.mime_type,
                file.timestamp.isoformat(),
                file.uploader,
            ),
        )
        self.conn.commit()
        logger.debug(f"Inserted file: {file.filename}")

    def insert_files_batch(self, files: List[FileMetadata]) -> None:
        """
        Batch insert files (efficient).

        Args:
            files: List of FileMetadata instances
        """
        if not files:
            return

        data = [
            (
                f.filename,
                f.url,
                f.descriptionurl,
                f.sha1,
                f.size,
                f.width,
                f.height,
                f.mime_type,
                f.timestamp.isoformat(),
                f.uploader,
            )
            for f in files
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO files
            (filename, url, descriptionurl, sha1, size, width, height, 
             mime_type, timestamp, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        self.conn.commit()
        logger.info(f"Inserted {len(files)} files in batch")

    def get_file(self, filename: str) -> Optional[FileMetadata]:
        """
        Get file by filename.

        Args:
            filename: Filename to lookup

        Returns:
            FileMetadata instance or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM files WHERE filename = ?
        """,
            (filename,),
        )

        row = cursor.fetchone()
        return self._row_to_file(row) if row else None

    def find_by_sha1(self, sha1: str) -> List[FileMetadata]:
        """
        Find files by SHA1 hash (for duplicate detection).

        Args:
            sha1: SHA1 hash to search for

        Returns:
            List of FileMetadata instances with matching SHA1
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM files WHERE sha1 = ?
        """,
            (sha1,),
        )

        return [self._row_to_file(row) for row in cursor.fetchall()]

    def list_files(
        self, mime_type: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[FileMetadata]:
        """
        List files with optional filtering and pagination.

        Args:
            mime_type: Filter by MIME type (None = all types)
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of FileMetadata instances
        """
        if mime_type is not None:
            cursor = self.conn.execute(
                """
                SELECT * FROM files
                WHERE mime_type = ?
                ORDER BY filename
                LIMIT ? OFFSET ?
            """,
                (mime_type, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM files
                ORDER BY filename
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

        return [self._row_to_file(row) for row in cursor.fetchall()]

    def update_file(self, file: FileMetadata) -> None:
        """
        Update existing file.

        Args:
            file: FileMetadata instance with filename
        """
        self.conn.execute(
            """
            UPDATE files
            SET url = ?,
                descriptionurl = ?,
                sha1 = ?,
                size = ?,
                width = ?,
                height = ?,
                mime_type = ?,
                timestamp = ?,
                uploader = ?
            WHERE filename = ?
        """,
            (
                file.url,
                file.descriptionurl,
                file.sha1,
                file.size,
                file.width,
                file.height,
                file.mime_type,
                file.timestamp.isoformat(),
                file.uploader,
                file.filename,
            ),
        )

        self.conn.commit()
        logger.debug(f"Updated file: {file.filename}")

    def delete_file(self, filename: str) -> None:
        """
        Delete file by filename.

        Args:
            filename: Filename to delete
        """
        self.conn.execute("DELETE FROM files WHERE filename = ?", (filename,))
        self.conn.commit()
        logger.debug(f"Deleted file: {filename}")

    def count_files(self, mime_type: Optional[str] = None) -> int:
        """
        Count files.

        Args:
            mime_type: Filter by MIME type (None = all types)

        Returns:
            Number of files
        """
        if mime_type is not None:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM files WHERE mime_type = ?", (mime_type,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM files")

        return cursor.fetchone()[0]

    def _row_to_file(self, row: sqlite3.Row) -> FileMetadata:
        """
        Convert database row to FileMetadata instance.

        Args:
            row: SQLite row

        Returns:
            FileMetadata instance
        """
        return FileMetadata(
            filename=row["filename"],
            url=row["url"],
            descriptionurl=row["descriptionurl"],
            sha1=row["sha1"],
            size=row["size"],
            width=row["width"],
            height=row["height"],
            mime_type=row["mime_type"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            uploader=row["uploader"],
        )
