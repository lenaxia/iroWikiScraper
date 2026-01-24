# Story 06: Database Initialization

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-06  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1.5 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **a database initialization module**,  
So that **I can automatically create tables and indexes with proper connection management**.

## Description

Implement a `Database` class that handles SQLite database initialization, connection management, and schema loading. This class will be the foundation for all database operations in the scraper.

The implementation must load SQL schema files in correct order, handle idempotency (safe to run multiple times), and provide clean connection management with context manager support.

## Background & Context

**What does database initialization do?**
- Creates SQLite database file
- Loads and executes schema files (001-005)
- Enables foreign key enforcement
- Provides connection pooling/reuse
- Detects existing schema (idempotent)

**Why This Story Matters:**
- Foundation for all database operations
- Ensures consistent schema across environments
- Simplifies database setup for users
- Enables automated testing with fresh databases

## Acceptance Criteria

### 1. Database Class Implementation
- [ ] Create `scraper/storage/database.py`
- [ ] Class: `Database` with connection management
- [ ] Method: `__init__(db_path: str)` - Initialize with path
- [ ] Method: `initialize_schema()` - Load and execute schema files
- [ ] Method: `get_connection()` - Return SQLite connection
- [ ] Method: `close()` - Close connection
- [ ] Context manager support: `with Database(path) as db:`

### 2. Schema Loading
- [ ] Load SQL files from `schema/sqlite/` directory
- [ ] Execute files in numerical order (001, 002, 003, 004, 005)
- [ ] Enable foreign key enforcement: `PRAGMA foreign_keys = ON`
- [ ] Handle schema already exists (idempotent)
- [ ] Log schema creation steps

### 3. Connection Management
- [ ] Create connection on initialization
- [ ] Reuse connection across operations
- [ ] Enable WAL mode for concurrency: `PRAGMA journal_mode=WAL`
- [ ] Set pragmas for performance
- [ ] Close connection on cleanup

### 4. Error Handling
- [ ] Raise clear error if schema files not found
- [ ] Raise clear error if SQL execution fails
- [ ] Handle permission errors (can't create database file)
- [ ] Validate database path is writable

### 5. Testing
- [ ] Unit test: Initialize new database
- [ ] Unit test: Initialize existing database (idempotent)
- [ ] Unit test: Schema version recorded correctly
- [ ] Unit test: Foreign keys enabled
- [ ] Unit test: Context manager works
- [ ] Unit test: Connection reuse
- [ ] Test coverage: 80%+

## Tasks

### Module Implementation
- [ ] Create `scraper/storage/__init__.py`
- [ ] Create `scraper/storage/database.py`
- [ ] Implement `Database` class
- [ ] Implement `__init__()` method
- [ ] Implement `initialize_schema()` method
- [ ] Implement `get_connection()` method
- [ ] Implement `close()` method
- [ ] Implement `__enter__()` and `__exit__()` for context manager

### Schema Loading Logic
- [ ] Find schema files in `schema/sqlite/`
- [ ] Sort files numerically
- [ ] Read SQL file contents
- [ ] Execute SQL statements
- [ ] Handle multi-statement SQL files
- [ ] Log each step

### Connection Management
- [ ] Create SQLite connection
- [ ] Set connection pragmas
- [ ] Enable foreign keys
- [ ] Enable WAL mode
- [ ] Provide connection accessor

### Testing
- [ ] Write tests in `tests/storage/test_database.py`
- [ ] Test with temporary database files
- [ ] Test schema creation
- [ ] Test idempotency
- [ ] Test error handling
- [ ] Run tests: `pytest tests/storage/test_database.py -v`

### Documentation
- [ ] Add module docstring
- [ ] Add class docstring with usage examples
- [ ] Add method docstrings
- [ ] Add type hints

## Technical Details

### File Structure
```
scraper/
├── storage/
│   ├── __init__.py
│   └── database.py

tests/
└── storage/
    ├── __init__.py
    └── test_database.py
```

### Database Class Implementation

```python
# scraper/storage/database.py
"""
Database initialization and connection management.

This module provides the Database class for creating and managing
SQLite database connections with automatic schema initialization.
"""

import sqlite3
import logging
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
    
    def __init__(self, db_path: str):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file (will be created if doesn't exist)
        
        Raises:
            ValueError: If db_path is invalid
            PermissionError: If db_path directory is not writable
        """
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self._schema_dir = Path(__file__).parent.parent.parent / "schema" / "sqlite"
        
        # Validate path
        if not self.db_path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {self.db_path.parent}")
        
        if not self.db_path.parent.is_dir():
            raise ValueError(f"Parent path is not a directory: {self.db_path.parent}")
        
        # Check write permission
        if not os.access(self.db_path.parent, os.W_OK):
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
            
            with open(schema_file, 'r') as f:
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
            raise RuntimeError("Schema initialization failed: schema_version table not found")
        
        # Check current schema version
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]
        logger.info(f"Database schema version: {version}")
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get SQLite connection (creates if doesn't exist).
        
        The connection is configured with:
        - Row factory for dict-like access
        - WAL mode for better concurrency
        - Foreign key enforcement
        
        Returns:
            sqlite3.Connection: Database connection
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False  # Allow use from multiple threads
            )
            
            # Enable dict-like row access
            self._connection.row_factory = sqlite3.Row
            
            # Enable foreign key enforcement
            self._connection.execute("PRAGMA foreign_keys = ON")
            
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
```

### Usage Examples

```python
# Basic usage
from scraper.storage.database import Database

db = Database("wiki.db")
db.initialize_schema()

conn = db.get_connection()
cursor = conn.execute("SELECT COUNT(*) FROM pages")
print(f"Pages: {cursor.fetchone()[0]}")

db.close()

# Context manager (recommended)
with Database("wiki.db") as db:
    db.initialize_schema()
    conn = db.get_connection()
    
    cursor = conn.execute("SELECT COUNT(*) FROM pages")
    print(f"Pages: {cursor.fetchone()[0]}")
    # Connection automatically closed

# Testing with temporary database
import tempfile

with tempfile.NamedTemporaryFile(suffix=".db") as f:
    with Database(f.name) as db:
        db.initialize_schema()
        # ... test operations ...
        # Database deleted after test
```

### Test Implementation

```python
# tests/storage/test_database.py
import pytest
import tempfile
import sqlite3
from pathlib import Path
from scraper.storage.database import Database


class TestDatabase:
    """Test Database class."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Provide temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        # Cleanup
        Path(f.name).unlink(missing_ok=True)
    
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
        
        assert 'pages' in tables
        assert 'revisions' in tables
        assert 'files' in tables
        assert 'links' in tables
        assert 'scrape_runs' in tables
        assert 'scrape_page_status' in tables
        assert 'schema_version' in tables
        
        db.close()
    
    def test_idempotent_initialization(self, temp_db_path):
        """Test that initializing twice doesn't cause errors."""
        db = Database(temp_db_path)
        db.initialize_schema()
        db.initialize_schema()  # Should not raise error
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
    
    def test_context_manager(self, temp_db_path):
        """Test context manager usage."""
        with Database(temp_db_path) as db:
            db.initialize_schema()
            conn = db.get_connection()
            assert conn is not None
        
        # Connection should be closed after exit
        # Verify by trying to use connection
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
    
    def test_connection_reuse(self, temp_db_path):
        """Test that connection is reused."""
        db = Database(temp_db_path)
        db.initialize_schema()
        
        conn1 = db.get_connection()
        conn2 = db.get_connection()
        
        assert conn1 is conn2, "Should reuse connection"
        db.close()
    
    def test_invalid_path(self):
        """Test error handling for invalid path."""
        with pytest.raises(ValueError):
            Database("/nonexistent/directory/db.sqlite")
    
    def test_row_factory_enabled(self, temp_db_path):
        """Test that row factory is enabled for dict-like access."""
        with Database(temp_db_path) as db:
            db.initialize_schema()
            conn = db.get_connection()
            
            # Insert test data
            conn.execute(
                "INSERT INTO pages (namespace, title) VALUES (?, ?)",
                (0, "Test")
            )
            conn.commit()
            
            # Query with row factory
            cursor = conn.execute("SELECT * FROM pages")
            row = cursor.fetchone()
            
            # Should be able to access by column name
            assert row['title'] == 'Test'
            assert row['namespace'] == 0
```

## Dependencies

### Requires
- Story 01: Pages Table Schema
- Story 02: Revisions Table Schema
- Story 03: Files Table Schema
- Story 04: Links Table Schema
- Story 05: Scrape Metadata Schema
- Python 3.11+ (built-in sqlite3 module)

### Blocks
- Story 07: Page CRUD Operations
- Story 08: Revision CRUD Operations
- Story 09: File CRUD Operations
- Story 10: Link Database Operations
- All other database stories

## Testing Requirements

- [ ] Test new database creation
- [ ] Test idempotent initialization
- [ ] Test foreign key enforcement enabled
- [ ] Test schema version recorded
- [ ] Test context manager
- [ ] Test connection reuse
- [ ] Test invalid path handling
- [ ] Test row factory enabled
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] Database class implemented
- [ ] All methods working
- [ ] Schema loading works
- [ ] All tests passing
- [ ] Code coverage ≥80%
- [ ] Type hints on all methods
- [ ] Docstrings complete
- [ ] Code review completed

## Notes

**Why WAL mode?**
- Better concurrency (readers don't block writers)
- Faster for most workloads
- Standard for modern SQLite apps

**Why row factory?**
- Dict-like access: `row['title']` instead of `row[0]`
- More readable code
- Easier to refactor schema

**Performance pragmas:**
- `synchronous=NORMAL`: Balance safety and speed
- `temp_store=MEMORY`: Faster temp tables
- `cache_size=-64000`: 64MB page cache

**Future considerations:**
- Add connection pooling for multi-threaded access
- Add backup/restore methods
- Add database compaction (VACUUM)
- Add integrity checks
