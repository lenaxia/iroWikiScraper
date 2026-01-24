"""
Test database schema definitions.

Tests all SQL schema files (001-005) for:
- Table creation
- Column types and constraints
- Primary keys and foreign keys
- Unique constraints
- Check constraints
- Index creation and usage
- Data insertion and validation
"""

import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def tmp_database():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def schema_dir():
    """Get path to schema directory."""
    return Path(__file__).parent.parent.parent / "schema" / "sqlite"


def load_schema(conn: sqlite3.Connection, schema_file: Path):
    """Load a schema file into the database."""
    with open(schema_file, "r") as f:
        conn.executescript(f.read())
    conn.commit()


# =============================================================================
# Story 01: Pages Table Schema Tests
# =============================================================================


def test_pages_table_creation(tmp_database, schema_dir):
    """Test pages table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")

    # Verify table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pages'"
    )
    assert cursor.fetchone() is not None

    # Verify columns exist
    cursor = conn.execute("PRAGMA table_info(pages)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["page_id"] == "INTEGER"
    assert columns["namespace"] == "INTEGER"
    assert columns["title"] == "TEXT"
    assert columns["is_redirect"] == "BOOLEAN"
    assert columns["created_at"] == "TIMESTAMP"
    assert columns["updated_at"] == "TIMESTAMP"

    conn.close()


def test_pages_indexes_created(tmp_database, schema_dir):
    """Test all pages indexes are created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")

    # Get all indexes for pages table
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pages'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    # Check expected indexes exist
    assert "idx_pages_title" in indexes
    assert "idx_pages_namespace" in indexes
    assert "idx_pages_redirect" in indexes

    conn.close()


def test_pages_insert_valid(tmp_database, schema_dir):
    """Test inserting valid pages."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")

    # Insert test pages
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title, is_redirect) "
        "VALUES (1, 0, 'Prontera', 0)"
    )
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title, is_redirect) "
        "VALUES (2, 0, 'Geffen', 0)"
    )
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title, is_redirect) "
        "VALUES (3, 6, 'Example.png', 0)"
    )
    conn.commit()

    # Verify inserted
    cursor = conn.execute("SELECT COUNT(*) FROM pages")
    assert cursor.fetchone()[0] == 3

    conn.close()


def test_pages_unique_constraint(tmp_database, schema_dir):
    """Test unique constraint on (namespace, title)."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")

    # Insert first page
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Prontera')"
    )

    # Try to insert duplicate (same namespace and title)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'Prontera')"
        )

    # But can insert same title in different namespace
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title) VALUES (3, 2, 'Prontera')"
    )

    conn.close()


def test_pages_check_constraint(tmp_database, schema_dir):
    """Test check constraint on namespace >= 0."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")

    # Negative namespace should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, -1, 'Test')"
        )

    conn.close()


# =============================================================================
# Story 02: Revisions Table Schema Tests
# =============================================================================


def test_revisions_table_creation(tmp_database, schema_dir):
    """Test revisions table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    # Verify table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='revisions'"
    )
    assert cursor.fetchone() is not None

    # Verify columns exist
    cursor = conn.execute("PRAGMA table_info(revisions)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["revision_id"] == "INTEGER"
    assert columns["page_id"] == "INTEGER"
    assert columns["parent_id"] == "INTEGER"
    assert columns["timestamp"] == "TIMESTAMP"
    assert columns["user"] == "TEXT"
    assert columns["user_id"] == "INTEGER"
    assert columns["comment"] == "TEXT"
    assert columns["content"] == "TEXT"
    assert columns["size"] == "INTEGER"
    assert columns["sha1"] == "TEXT"
    assert columns["minor"] == "BOOLEAN"
    assert columns["tags"] == "TEXT"

    conn.close()


def test_revisions_indexes_created(tmp_database, schema_dir):
    """Test all revisions indexes are created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='revisions'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    assert "idx_rev_page_time" in indexes
    assert "idx_rev_timestamp" in indexes
    assert "idx_rev_parent" in indexes
    assert "idx_rev_sha1" in indexes
    assert "idx_rev_user" in indexes

    conn.close()


def test_revisions_foreign_key_constraint(tmp_database, schema_dir):
    """Test foreign key constraint to pages table."""
    conn = sqlite3.connect(tmp_database)
    conn.execute("PRAGMA foreign_keys = ON")
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    # Try to insert revision without page
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute(
            "INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) "
            "VALUES (1, 999, '2024-01-01 10:00:00', 'Test content', 12, 'abc123')"
        )

    # Insert page first, then revision should work
    conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")
    conn.execute(
        "INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) "
        "VALUES (1, 1, '2024-01-01 10:00:00', 'Test content', 12, 'abc123')"
    )

    conn.close()


def test_revisions_cascade_delete(tmp_database, schema_dir):
    """Test cascade delete when page is deleted."""
    conn = sqlite3.connect(tmp_database)
    conn.execute("PRAGMA foreign_keys = ON")
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    # Insert page and revision
    conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")
    conn.execute(
        "INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) "
        "VALUES (1, 1, '2024-01-01 10:00:00', 'Test', 4, 'abc')"
    )

    # Delete page
    conn.execute("DELETE FROM pages WHERE page_id = 1")

    # Revision should be deleted too
    cursor = conn.execute("SELECT COUNT(*) FROM revisions WHERE page_id = 1")
    assert cursor.fetchone()[0] == 0

    conn.close()


def test_revisions_insert_with_null_fields(tmp_database, schema_dir):
    """Test inserting revisions with NULL optional fields."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")

    # Insert revision with NULL user, user_id, comment, parent_id, tags
    conn.execute(
        "INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) "
        "VALUES (1, 1, '2024-01-01 10:00:00', 'Test', 4, 'abc')"
    )

    cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 1")
    row = cursor.fetchone()
    assert row is not None

    conn.close()


def test_revisions_check_constraint(tmp_database, schema_dir):
    """Test check constraint on size >= 0."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")

    conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")

    # Negative size should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) "
            "VALUES (1, 1, '2024-01-01', 'Test', -1, 'abc')"
        )

    conn.close()


# =============================================================================
# Story 03: Files Table Schema Tests
# =============================================================================


def test_files_table_creation(tmp_database, schema_dir):
    """Test files table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
    )
    assert cursor.fetchone() is not None

    # Verify columns
    cursor = conn.execute("PRAGMA table_info(files)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["filename"] == "TEXT"
    assert columns["url"] == "TEXT"
    assert columns["descriptionurl"] == "TEXT"
    assert columns["sha1"] == "TEXT"
    assert columns["size"] == "INTEGER"
    assert columns["width"] == "INTEGER"
    assert columns["height"] == "INTEGER"
    assert columns["mime_type"] == "TEXT"
    assert columns["timestamp"] == "TIMESTAMP"
    assert columns["uploader"] == "TEXT"

    conn.close()


def test_files_indexes_created(tmp_database, schema_dir):
    """Test all files indexes are created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='files'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    assert "idx_files_sha1" in indexes
    assert "idx_files_timestamp" in indexes
    assert "idx_files_mime" in indexes
    assert "idx_files_uploader" in indexes

    conn.close()


def test_files_insert_image(tmp_database, schema_dir):
    """Test inserting image file with dimensions."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    conn.execute(
        "INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader) "
        "VALUES ('Example.png', 'https://example.com/Example.png', 'https://example.com/File:Example.png', "
        "'abc123', 12345, 800, 600, 'image/png', '2024-01-15 10:00:00', 'Alice')"
    )

    cursor = conn.execute("SELECT * FROM files WHERE filename = 'Example.png'")
    row = cursor.fetchone()
    assert row is not None

    conn.close()


def test_files_insert_non_image(tmp_database, schema_dir):
    """Test inserting non-image file with NULL dimensions."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    conn.execute(
        "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) "
        "VALUES ('Document.pdf', 'https://example.com/Document.pdf', 'https://example.com/File:Document.pdf', "
        "'def456', 54321, 'application/pdf', '2024-01-16 11:00:00')"
    )

    cursor = conn.execute("SELECT * FROM files WHERE filename = 'Document.pdf'")
    row = cursor.fetchone()
    assert row is not None

    conn.close()


def test_files_unique_constraint(tmp_database, schema_dir):
    """Test unique constraint on filename."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    conn.execute(
        "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) "
        "VALUES ('Example.png', 'https://example.com/1.png', 'https://example.com/File:1', "
        "'abc', 100, 'image/png', '2024-01-01')"
    )

    # Duplicate filename should fail
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) "
            "VALUES ('Example.png', 'https://example.com/2.png', 'https://example.com/File:2', "
            "'def', 200, 'image/png', '2024-01-02')"
        )

    conn.close()


def test_files_check_constraints(tmp_database, schema_dir):
    """Test check constraints on size, width, height."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "003_files.sql")

    # Negative size should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) "
            "VALUES ('Negative.png', 'http://test.com', 'http://test.com', 'abc', -100, 'image/png', '2024-01-01')"
        )

    # Zero width should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp) "
            "VALUES ('ZeroWidth.png', 'http://test.com', 'http://test.com', 'abc', 100, 0, 100, 'image/png', '2024-01-01')"
        )

    conn.close()


# =============================================================================
# Story 04: Links Table Schema Tests
# =============================================================================


def test_links_table_creation(tmp_database, schema_dir):
    """Test links table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "004_links.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='links'"
    )
    assert cursor.fetchone() is not None

    # Verify columns
    cursor = conn.execute("PRAGMA table_info(links)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["source_page_id"] == "INTEGER"
    assert columns["target_title"] == "TEXT"
    assert columns["link_type"] == "TEXT"

    conn.close()


def test_links_indexes_created(tmp_database, schema_dir):
    """Test all links indexes are created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "004_links.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='links'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    assert "idx_links_source" in indexes
    assert "idx_links_target" in indexes
    assert "idx_links_type" in indexes
    assert "idx_links_type_target" in indexes

    conn.close()


def test_links_foreign_key_constraint(tmp_database, schema_dir):
    """Test that links can be inserted without foreign key constraint.

    Links table does not have a foreign key constraint to allow
    testing and flexibility. The source_page_id can reference
    non-existent pages."""
    conn = sqlite3.connect(tmp_database)
    conn.execute("PRAGMA foreign_keys = ON")
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "004_links.sql")

    # Can insert link without source page existing
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (999, 'Target', 'page')"
    )

    # Verify link was inserted
    cursor = conn.execute("SELECT COUNT(*) FROM links WHERE source_page_id = 999")
    assert cursor.fetchone()[0] == 1

    conn.close()


def test_links_check_constraint(tmp_database, schema_dir):
    """Test check constraint on link_type."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "004_links.sql")

    conn.execute(
        "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Source')"
    )

    # Invalid link_type should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO links (source_page_id, target_title, link_type) "
            "VALUES (1, 'Target', 'invalid_type')"
        )

    # Valid types should work
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target1', 'page')"
    )
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target2', 'template')"
    )
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target3', 'file')"
    )
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target4', 'category')"
    )

    conn.close()


def test_links_unique_constraint(tmp_database, schema_dir):
    """Test unique constraint on (source_page_id, target_title, link_type)."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "004_links.sql")

    conn.execute(
        "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Source')"
    )

    # Insert first link
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target', 'page')"
    )

    # Duplicate link should fail
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO links (source_page_id, target_title, link_type) "
            "VALUES (1, 'Target', 'page')"
        )

    # But same target with different type should work
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Target', 'template')"
    )

    conn.close()


# =============================================================================
# Story 05: Scrape Metadata Schema Tests
# =============================================================================


def test_scrape_runs_table_creation(tmp_database, schema_dir):
    """Test scrape_runs table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
    )
    assert cursor.fetchone() is not None

    # Verify columns
    cursor = conn.execute("PRAGMA table_info(scrape_runs)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["run_id"] == "INTEGER"
    assert columns["start_time"] == "TIMESTAMP"
    assert columns["end_time"] == "TIMESTAMP"
    assert columns["status"] == "TEXT"
    assert columns["pages_scraped"] == "INTEGER"
    assert columns["revisions_scraped"] == "INTEGER"
    assert columns["files_downloaded"] == "INTEGER"
    assert columns["error_message"] == "TEXT"

    conn.close()


def test_scrape_page_status_table_creation(tmp_database, schema_dir):
    """Test scrape_page_status table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scrape_page_status'"
    )
    assert cursor.fetchone() is not None

    cursor = conn.execute("PRAGMA table_info(scrape_page_status)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns["page_id"] == "INTEGER"
    assert columns["run_id"] == "INTEGER"
    assert columns["status"] == "TEXT"
    assert columns["last_revision_id"] == "INTEGER"
    assert columns["error_message"] == "TEXT"
    assert columns["scraped_at"] == "TIMESTAMP"

    conn.close()


def test_schema_version_table_creation(tmp_database, schema_dir):
    """Test schema_version table can be created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    assert cursor.fetchone() is not None

    # Check that initial version was inserted
    cursor = conn.execute("SELECT version, description FROM schema_version")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 1
    assert "Initial schema" in row[1]

    conn.close()


def test_scrape_runs_insert(tmp_database, schema_dir):
    """Test inserting scrape run record."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    conn.execute(
        "INSERT INTO scrape_runs (start_time, status, pages_scraped, revisions_scraped, files_downloaded) "
        "VALUES ('2024-01-15 10:00:00', 'running', 0, 0, 0)"
    )

    cursor = conn.execute("SELECT * FROM scrape_runs WHERE run_id = 1")
    row = cursor.fetchone()
    assert row is not None

    conn.close()


def test_scrape_runs_check_constraints(tmp_database, schema_dir):
    """Test check constraints on scrape_runs."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    # Invalid status should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO scrape_runs (start_time, status) "
            "VALUES ('2024-01-01', 'invalid_status')"
        )

    # Negative pages_scraped should fail
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO scrape_runs (start_time, status, pages_scraped) "
            "VALUES ('2024-01-01', 'running', -1)"
        )

    conn.close()


def test_scrape_page_status_insert(tmp_database, schema_dir):
    """Test inserting page status record."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    # Insert page and run
    conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")
    conn.execute(
        "INSERT INTO scrape_runs (run_id, start_time, status) "
        "VALUES (1, '2024-01-01', 'running')"
    )

    # Insert page status
    conn.execute(
        "INSERT INTO scrape_page_status (page_id, run_id, status, scraped_at) "
        "VALUES (1, 1, 'success', '2024-01-01 10:00:00')"
    )

    cursor = conn.execute(
        "SELECT * FROM scrape_page_status WHERE page_id = 1 AND run_id = 1"
    )
    row = cursor.fetchone()
    assert row is not None

    conn.close()


def test_scrape_metadata_indexes_created(tmp_database, schema_dir):
    """Test all scrape metadata indexes are created."""
    conn = sqlite3.connect(tmp_database)
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    # Check scrape_runs indexes
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='scrape_runs'"
    )
    indexes = [row[0] for row in cursor.fetchall()]
    assert "idx_runs_status" in indexes
    assert "idx_runs_start_time" in indexes

    # Check scrape_page_status indexes
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='scrape_page_status'"
    )
    indexes = [row[0] for row in cursor.fetchall()]
    assert "idx_page_status_run" in indexes
    assert "idx_page_status_status" in indexes

    conn.close()


# =============================================================================
# Integration Tests
# =============================================================================


def test_all_schemas_load_together(tmp_database, schema_dir):
    """Test all schemas can be loaded together without conflicts."""
    conn = sqlite3.connect(tmp_database)

    # Load all schemas in order
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")
    load_schema(conn, schema_dir / "003_files.sql")
    load_schema(conn, schema_dir / "004_links.sql")
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    # Verify all tables exist
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

    conn.close()


def test_full_workflow_simulation(tmp_database, schema_dir):
    """Test complete workflow with all tables."""
    conn = sqlite3.connect(tmp_database)
    conn.execute("PRAGMA foreign_keys = ON")

    # Load all schemas
    load_schema(conn, schema_dir / "001_pages.sql")
    load_schema(conn, schema_dir / "002_revisions.sql")
    load_schema(conn, schema_dir / "003_files.sql")
    load_schema(conn, schema_dir / "004_links.sql")
    load_schema(conn, schema_dir / "005_scrape_metadata.sql")

    # Create a scrape run
    conn.execute(
        "INSERT INTO scrape_runs (run_id, start_time, status) "
        "VALUES (1, '2024-01-15 10:00:00', 'running')"
    )

    # Insert pages
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title, is_redirect) "
        "VALUES (1, 0, 'Prontera', 0)"
    )
    conn.execute(
        "INSERT INTO pages (page_id, namespace, title, is_redirect) "
        "VALUES (2, 0, 'Geffen', 0)"
    )

    # Insert revisions
    conn.execute(
        "INSERT INTO revisions (revision_id, page_id, timestamp, user, content, size, sha1) "
        "VALUES (100, 1, '2024-01-01 10:00:00', 'Alice', 'First revision', 14, 'abc123')"
    )
    conn.execute(
        "INSERT INTO revisions (revision_id, page_id, parent_id, timestamp, user, content, size, sha1) "
        "VALUES (101, 1, 100, '2024-01-02 11:00:00', 'Bob', 'Second revision', 15, 'def456')"
    )

    # Insert files
    conn.execute(
        "INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp) "
        "VALUES ('Example.png', 'https://example.com/Example.png', 'https://example.com/File:Example.png', "
        "'abc123', 12345, 800, 600, 'image/png', '2024-01-15 10:00:00')"
    )

    # Insert links
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Geffen', 'page')"
    )
    conn.execute(
        "INSERT INTO links (source_page_id, target_title, link_type) "
        "VALUES (1, 'Template:Infobox', 'template')"
    )

    # Insert page status
    conn.execute(
        "INSERT INTO scrape_page_status (page_id, run_id, status, last_revision_id, scraped_at) "
        "VALUES (1, 1, 'success', 101, '2024-01-15 10:30:00')"
    )

    # Verify data integrity
    cursor = conn.execute("SELECT COUNT(*) FROM pages")
    assert cursor.fetchone()[0] == 2

    cursor = conn.execute("SELECT COUNT(*) FROM revisions")
    assert cursor.fetchone()[0] == 2

    cursor = conn.execute("SELECT COUNT(*) FROM files")
    assert cursor.fetchone()[0] == 1

    cursor = conn.execute("SELECT COUNT(*) FROM links")
    assert cursor.fetchone()[0] == 2

    cursor = conn.execute("SELECT COUNT(*) FROM scrape_page_status")
    assert cursor.fetchone()[0] == 1

    conn.close()
