"""
Database initialization and connection management.

This module provides the Database class for creating and managing
SQLite database connections with automatic schema initialization.
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database with automatic schema initialization.

    Usage:
        # Basic usage
        db = Database("wiki.db")
        db.initialize_schema()
        conn = db.get_connection()
        # ... use connection ...
        db.close()

        # Context manager usage (recommended)
        with Database("wiki.db") as db:
            conn = db.get_connection()
            # ... use connection ...
            # automatically closed on exit
    """

    def __init__(self, db_path: str, read_only: bool = False):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file (will be created if doesn't exist)
            read_only: If True, open database in read-only mode

        Raises:
            ValueError: If db_path is invalid
            PermissionError: If db_path directory is not writable
        """
        self.db_path = Path(db_path)
        self.read_only = read_only
        self._connection: Optional[sqlite3.Connection] = None
        self._schema_dir = Path(__file__).parent.parent.parent / "schema" / "sqlite"

        # Validate path
        if not self.db_path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {self.db_path.parent}")

        if not self.db_path.parent.is_dir():
            raise ValueError(f"Parent path is not a directory: {self.db_path.parent}")

        # Check write permission (only if not read-only and directory exists)
        if not read_only and not os.access(self.db_path.parent, os.W_OK):
            raise PermissionError(f"No write permission: {self.db_path.parent}")

        logger.info(f"Database initialized: {self.db_path}")

    def initialize_schema(self) -> None:
        """
        Load and execute SQL schema files.

        This method is idempotent - safe to call multiple times.
        It will only create tables if they don't already exist.

        Raises:
            FileNotFoundError: If schema directory or files not found
            sqlite3.Error: If SQL execution fails
        """
        if not self._schema_dir.exists():
            raise FileNotFoundError(f"Schema directory not found: {self._schema_dir}")

        # Find all SQL files (001_*.sql, 002_*.sql, etc.)
        schema_files = sorted(self._schema_dir.glob("*.sql"))

        if not schema_files:
            raise FileNotFoundError(f"No schema files found in: {self._schema_dir}")

        conn = self.get_connection()

        # Enable foreign key enforcement
        conn.execute("PRAGMA foreign_keys = ON")

        # Load and execute each schema file
        for schema_file in schema_files:
            logger.info(f"Loading schema: {schema_file.name}")

            with open(schema_file, "r") as f:
                sql = f.read()

            try:
                conn.executescript(sql)
                conn.commit()
                logger.info(f"Schema loaded successfully: {schema_file.name}")
            except sqlite3.Error as e:
                logger.error(f"Failed to load schema {schema_file.name}: {e}")
                raise

        # Verify schema version table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if not cursor.fetchone():
            raise RuntimeError(
                "Schema initialization failed: schema_version table not found"
            )

        # Check current schema version
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]
        logger.info(f"Database schema version: {version}")

    def get_connection(self) -> sqlite3.Connection:
        """
        Get SQLite connection (creates if doesn't exist).

        The connection is configured with:
        - Row factory for dict-like access
        - WAL mode for better concurrency (if not read-only)
        - Foreign key enforcement
        - Performance pragmas

        Returns:
            sqlite3.Connection: Database connection
        """
        if self._connection is None:
            # Open in read-only mode if requested
            if self.read_only:
                uri = f"file:{self.db_path}?mode=ro"
                self._connection = sqlite3.connect(
                    uri, uri=True, check_same_thread=False
                )
            else:
                self._connection = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,  # Allow use from multiple threads
                )

            # Enable dict-like row access
            self._connection.row_factory = sqlite3.Row

            # Enable foreign key enforcement
            self._connection.execute("PRAGMA foreign_keys = ON")

            if not self.read_only:
                # Enable WAL mode for better concurrency
                self._connection.execute("PRAGMA journal_mode = WAL")

                # Performance pragmas
                self._connection.execute("PRAGMA synchronous = NORMAL")
                self._connection.execute("PRAGMA temp_store = MEMORY")
                self._connection.execute("PRAGMA cache_size = -64000")  # 64MB cache

            logger.debug("Database connection established")

        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (closes connection)."""
        self.close()
        return False  # Don't suppress exceptions
