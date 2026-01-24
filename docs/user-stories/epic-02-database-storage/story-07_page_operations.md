# Story 07: Page CRUD Operations

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-07  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **CRUD operations for pages**,  
So that **I can persist discovered pages to the database with efficient batch operations**.

## Description

Implement a `PageRepository` class that provides Create, Read, Update, Delete operations for the pages table. This class will handle conversions between Page dataclass instances and database rows, with support for efficient batch inserts.

## Background & Context

**What is a repository?**
- Data access layer between application and database
- Encapsulates SQL queries
- Handles model ↔ database conversions
- Provides type-safe interface

**Why This Story Matters:**
- Foundation for page persistence
- Used by scraper to store discovered pages
- Supports both single and batch operations
- Clean separation of concerns

## Acceptance Criteria

### 1. PageRepository Implementation
- [ ] Create `scraper/storage/page_repository.py`
- [ ] Class: `PageRepository(connection: sqlite3.Connection)`
- [ ] Method: `insert_page(page: Page) -> int` - Insert single page, return page_id
- [ ] Method: `insert_pages_batch(pages: List[Page]) -> None` - Batch insert
- [ ] Method: `get_page_by_id(page_id: int) -> Optional[Page]`
- [ ] Method: `get_page_by_title(namespace: int, title: str) -> Optional[Page]`
- [ ] Method: `list_pages(namespace: Optional[int] = None, limit: int = 100, offset: int = 0) -> List[Page]`
- [ ] Method: `update_page(page: Page) -> None`
- [ ] Method: `delete_page(page_id: int) -> None`
- [ ] Method: `count_pages(namespace: Optional[int] = None) -> int`

### 2. Data Conversion
- [ ] Convert Page dataclass to SQL parameters
- [ ] Convert SQLite Row to Page dataclass
- [ ] Handle NULL values correctly
- [ ] Handle datetime serialization
- [ ] Preserve all fields in round-trip conversion

### 3. Upsert Logic
- [ ] Use INSERT OR REPLACE for idempotency
- [ ] Handle unique constraint violations gracefully
- [ ] Batch operations use executemany() for efficiency

### 4. Testing
- [ ] Test insert single page
- [ ] Test insert batch (2,400 pages)
- [ ] Test get page by ID
- [ ] Test get page by title
- [ ] Test list pages with pagination
- [ ] Test update page
- [ ] Test delete page
- [ ] Test count pages
- [ ] Test duplicate handling (upsert)
- [ ] Test coverage: 80%+

## Technical Details

### Implementation

```python
# scraper/storage/page_repository.py
"""Repository for page CRUD operations."""

import sqlite3
import logging
from typing import List, Optional
from datetime import datetime

from scraper.models.page import Page

logger = logging.getLogger(__name__)


class PageRepository:
    """Repository for pages table operations."""
    
    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize repository with database connection.
        
        Args:
            connection: SQLite database connection
        """
        self.conn = connection
    
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
        cursor = self.conn.execute("""
            INSERT INTO pages (namespace, title, is_redirect, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            page.namespace,
            page.title,
            page.is_redirect,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        self.conn.commit()
        page_id = cursor.lastrowid
        
        logger.debug(f"Inserted page: {page.namespace}:{page.title} (id={page_id})")
        return page_id
    
    def insert_pages_batch(self, pages: List[Page]) -> None:
        """
        Insert multiple pages in batch (efficient).
        
        Uses INSERT OR REPLACE for idempotency.
        
        Args:
            pages: List of Page instances to insert
        """
        if not pages:
            return
        
        now = datetime.utcnow()
        
        data = [
            (p.namespace, p.title, p.is_redirect, now, now)
            for p in pages
        ]
        
        self.conn.executemany("""
            INSERT OR REPLACE INTO pages (namespace, title, is_redirect, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, data)
        
        self.conn.commit()
        logger.info(f"Inserted {len(pages)} pages in batch")
    
    def get_page_by_id(self, page_id: int) -> Optional[Page]:
        """
        Get page by ID.
        
        Args:
            page_id: Page ID to lookup
        
        Returns:
            Page instance or None if not found
        """
        cursor = self.conn.execute("""
            SELECT page_id, namespace, title, is_redirect, created_at, updated_at
            FROM pages
            WHERE page_id = ?
        """, (page_id,))
        
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
        cursor = self.conn.execute("""
            SELECT page_id, namespace, title, is_redirect, created_at, updated_at
            FROM pages
            WHERE namespace = ? AND title = ?
        """, (namespace, title))
        
        row = cursor.fetchone()
        
        if row:
            return self._row_to_page(row)
        return None
    
    def list_pages(
        self,
        namespace: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
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
            cursor = self.conn.execute("""
                SELECT page_id, namespace, title, is_redirect, created_at, updated_at
                FROM pages
                WHERE namespace = ?
                ORDER BY title
                LIMIT ? OFFSET ?
            """, (namespace, limit, offset))
        else:
            cursor = self.conn.execute("""
                SELECT page_id, namespace, title, is_redirect, created_at, updated_at
                FROM pages
                ORDER BY namespace, title
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        return [self._row_to_page(row) for row in cursor.fetchall()]
    
    def update_page(self, page: Page) -> None:
        """
        Update existing page.
        
        Args:
            page: Page instance with page_id set
        
        Raises:
            ValueError: If page_id is None
        """
        if not hasattr(page, 'page_id') or page.page_id is None:
            raise ValueError("Page must have page_id to update")
        
        self.conn.execute("""
            UPDATE pages
            SET namespace = ?,
                title = ?,
                is_redirect = ?,
                updated_at = ?
            WHERE page_id = ?
        """, (
            page.namespace,
            page.title,
            page.is_redirect,
            datetime.utcnow(),
            page.page_id
        ))
        
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
                "SELECT COUNT(*) FROM pages WHERE namespace = ?",
                (namespace,)
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
        page = Page(
            page_id=row['page_id'],
            namespace=row['namespace'],
            title=row['title'],
            is_redirect=bool(row['is_redirect'])
        )
        return page
```

### Test Implementation

```python
# tests/storage/test_page_repository.py
import pytest
from scraper.models.page import Page
from scraper.storage.page_repository import PageRepository


class TestPageRepository:
    """Test PageRepository class."""
    
    @pytest.fixture
    def repo(self, db):
        """Provide PageRepository instance."""
        return PageRepository(db.get_connection())
    
    def test_insert_page(self, repo):
        """Test inserting single page."""
        page = Page(namespace=0, title="TestPage", is_redirect=False)
        page_id = repo.insert_page(page)
        
        assert page_id > 0
        
        # Verify inserted
        loaded = repo.get_page_by_id(page_id)
        assert loaded is not None
        assert loaded.title == "TestPage"
        assert loaded.namespace == 0
    
    def test_insert_pages_batch(self, repo):
        """Test batch insert performance."""
        pages = [
            Page(namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(100)
        ]
        
        repo.insert_pages_batch(pages)
        
        count = repo.count_pages()
        assert count == 100
    
    def test_get_page_by_title(self, repo):
        """Test lookup by title."""
        page = Page(namespace=0, title="TestPage", is_redirect=False)
        repo.insert_page(page)
        
        loaded = repo.get_page_by_title(0, "TestPage")
        assert loaded is not None
        assert loaded.title == "TestPage"
    
    def test_list_pages_pagination(self, repo):
        """Test pagination."""
        pages = [
            Page(namespace=0, title=f"Page{i:03d}", is_redirect=False)
            for i in range(50)
        ]
        repo.insert_pages_batch(pages)
        
        # First page
        page1 = repo.list_pages(limit=20, offset=0)
        assert len(page1) == 20
        
        # Second page
        page2 = repo.list_pages(limit=20, offset=20)
        assert len(page2) == 20
        
        # No overlap
        titles1 = {p.title for p in page1}
        titles2 = {p.title for p in page2}
        assert len(titles1 & titles2) == 0
    
    def test_upsert_idempotency(self, repo):
        """Test that inserting same page twice works."""
        page = Page(namespace=0, title="TestPage", is_redirect=False)
        
        repo.insert_pages_batch([page])
        repo.insert_pages_batch([page])  # Should not error
        
        count = repo.count_pages()
        assert count == 1  # Only one copy
```

## Dependencies

### Requires
- Story 01: Pages Table Schema
- Story 06: Database Initialization
- Epic 01: Page model (scraper/models/page.py)

### Blocks
- Story 10: Link Database Operations (needs page lookups)
- Epic 01: PageDiscovery integration
- All scraper components that store pages

## Testing Requirements

- [ ] Insert single page
- [ ] Batch insert 2,400 pages < 1 second
- [ ] Get by ID < 1ms
- [ ] Get by title < 1ms
- [ ] List with pagination
- [ ] Update page
- [ ] Delete page
- [ ] Count pages
- [ ] Duplicate handling
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] PageRepository class implemented
- [ ] All CRUD methods working
- [ ] All tests passing
- [ ] Batch insert < 1s for 2,400 pages
- [ ] Code coverage ≥80%
- [ ] Type hints complete
- [ ] Docstrings complete
- [ ] Code review completed

## Notes

**Why INSERT OR REPLACE?**
- Idempotent batch inserts
- Handles duplicate title gracefully
- Simpler than checking existence first

**Performance tip:**
- Use `executemany()` for batch operations
- Commit once after batch, not per row
- 100x faster than individual inserts
