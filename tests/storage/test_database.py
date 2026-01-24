"""
Test Database initialization and connection management (Story 06).

Tests the Database class for:
- Schema initialization
- Connection management
- Context manager support
- Idempotency
- Error handling
"""

import sqlite3
import pytest
import os
from pathlib import Path

from scraper.storage.database import Database


class TestDatabaseInitialization:
    """Test Database class initialization and schema loading."""

    def test_initialize_new_database(self, temp_db_path):
        """Test creating new database with schema."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()

        # Check tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "pages" in tables
        assert "revisions" in tables
        assert "files" in tables
        assert "links" in tables
        assert "scrape_runs" in tables
        assert "scrape_page_status" in tables
        assert "schema_version" in tables

        db.close()

    def test_idempotent_initialization(self, temp_db_path):
        """Test that initializing twice doesn't cause errors."""
        db = Database(temp_db_path)
        db.initialize_schema()
        db.initialize_schema()  # Should not raise error

        # Verify tables still exist
        conn = db.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cursor.fetchone()[0]
        assert count >= 7  # At least 7 tables

        db.close()

    def test_foreign_keys_enabled(self, temp_db_path):
        """Test that foreign key enforcement is enabled."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()
        cursor = conn.execute("PRAGMA foreign_keys")
        enabled = cursor.fetchone()[0]

        assert enabled == 1, "Foreign keys should be enabled"
        db.close()

    def test_schema_version_recorded(self, temp_db_path):
        """Test that schema version is recorded."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]

        assert version >= 1, "Schema version should be recorded"
        db.close()

    def test_invalid_path(self):
        """Test error handling for invalid path."""
        with pytest.raises(ValueError):
            Database("/nonexistent/directory/db.sqlite")

    def test_readonly_mode(self, temp_db_path):
        """Test read-only mode."""
        # Create and initialize database first
        db = Database(temp_db_path)
        db.initialize_schema()
        db.close()

        # Open in read-only mode
        db_readonly = Database(temp_db_path, read_only=True)
        conn = db_readonly.get_connection()

        # Should be able to read
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        assert cursor.fetchone()[0] == 0

        # Should not be able to write
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO pages (namespace, title) VALUES (0, 'Test')")

        db_readonly.close()


class TestConnectionManagement:
    """Test Database connection management."""

    def test_get_connection_creates_connection(self, temp_db_path):
        """Test that get_connection creates connection."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        db.close()

    def test_connection_reuse(self, temp_db_path):
        """Test that connection is reused."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn1 = db.get_connection()
        conn2 = db.get_connection()

        assert conn1 is conn2, "Should reuse connection"
        db.close()

    def test_row_factory_enabled(self, temp_db_path):
        """Test that row factory is enabled for dict-like access."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()

        # Insert test data
        conn.execute(
            "INSERT INTO pages (namespace, title, is_redirect, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            (0, "Test", 0),
        )
        conn.commit()

        # Query with row factory
        cursor = conn.execute("SELECT * FROM pages")
        row = cursor.fetchone()

        # Should be able to access by column name
        assert row["title"] == "Test"
        assert row["namespace"] == 0

        db.close()

    def test_close_connection(self, temp_db_path):
        """Test closing connection."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()
        db.close()

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_wal_mode_enabled(self, temp_db_path):
        """Test that WAL journal mode is enabled."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

        assert mode.upper() == "WAL", "Should use WAL journal mode"
        db.close()


class TestContextManager:
    """Test Database context manager support."""

    def test_context_manager(self, temp_db_path):
        """Test context manager usage."""
        with Database(temp_db_path) as db:
            db.initialize_schema()
            conn = db.get_connection()
            assert conn is not None

            # Use connection
            cursor = conn.execute("SELECT COUNT(*) FROM pages")
            assert cursor.fetchone()[0] == 0

        # Connection should be closed after exit
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_context_manager_with_exception(self, temp_db_path):
        """Test context manager handles exceptions properly."""
        try:
            with Database(temp_db_path) as db:
                db.initialize_schema()
                raise ValueError("Test error")
        except ValueError:
            pass

        # Database should still be closed
        # Create new instance to verify database is intact
        with Database(temp_db_path) as db2:
            conn = db2.get_connection()
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "pages" in tables


class TestSchemaLoading:
    """Test schema file loading."""

    def test_schema_files_loaded_in_order(self, temp_db_path):
        """Test that schema files are loaded in numerical order."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()

        # Check that all tables from all schema files exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        # From 001_pages.sql
        assert "pages" in tables

        # From 002_revisions.sql
        assert "revisions" in tables

        # From 003_files.sql
        assert "files" in tables

        # From 004_links.sql
        assert "links" in tables

        # From 005_scrape_metadata.sql
        assert "scrape_runs" in tables
        assert "scrape_page_status" in tables

        db.close()

    def test_missing_schema_directory(self):
        """Test error when schema directory is missing."""
        db = Database(":memory:")

        # Manually set invalid schema directory
        db._schema_dir = Path("/nonexistent/schema/dir")

        with pytest.raises(FileNotFoundError):
            db.initialize_schema()


class TestDatabasePragmas:
    """Test database pragmas and configuration."""

    def test_performance_pragmas(self, temp_db_path):
        """Test that performance pragmas are set correctly."""
        db = Database(temp_db_path)
        db.initialize_schema()

        conn = db.get_connection()

        # Check synchronous mode
        cursor = conn.execute("PRAGMA synchronous")
        sync_mode = cursor.fetchone()[0]
        assert sync_mode == 1, "Should use NORMAL synchronous mode"

        # Check temp store
        cursor = conn.execute("PRAGMA temp_store")
        temp_store = cursor.fetchone()[0]
        assert temp_store == 2, "Should use MEMORY temp store"

        db.close()
