# Story 10: Link Database Operations

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-10  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **database-backed link storage**,  
So that **link data persists between runs and I can query page relationships efficiently**.

## Description

Migrate the existing `LinkStorage` class from in-memory storage to SQLite-backed storage. This maintains the same API but adds persistence, enabling resume capability and relationship queries.

## Background & Context

**Current state (Epic 01):**
- LinkStorage uses in-memory dictionaries
- Data lost when program exits
- Works fine for single run, but no persistence

**New requirements:**
- Persist links to database
- Support incremental scraping (remember what's linked)
- Enable "what links here" queries
- Maintain existing API for backwards compatibility

## Acceptance Criteria

### 1. Migrate LinkStorage to Database Backend
- [ ] Update `scraper/storage/link_storage.py`
- [ ] Add `connection: sqlite3.Connection` parameter to `__init__`
- [ ] Replace in-memory dicts with database queries
- [ ] Keep existing method signatures unchanged
- [ ] Method: `add_link(source_page_id, target_title, link_type)`
- [ ] Method: `get_links_by_source(page_id) -> List[Link]`
- [ ] Method: `get_backlinks(target_title) -> List[int]`
- [ ] Method: `get_links_by_type(page_id, link_type) -> List[str]`

### 2. Batch Operations
- [ ] Add `add_links_batch(links: List[Tuple]) -> None`
- [ ] Use INSERT OR IGNORE for deduplication
- [ ] Use executemany() for efficiency

### 3. Backwards Compatibility
- [ ] All existing tests still pass
- [ ] Same API as in-memory version
- [ ] Performance comparable (within 2x)

### 4. New Query Methods
- [ ] `get_backlinks(target_title: str) -> List[int]` - "what links here"
- [ ] `get_category_members(category: str) -> List[int]`
- [ ] `get_template_users(template: str) -> List[int]`
- [ ] `count_links(page_id: Optional[int] = None) -> int`

### 5. Testing
- [ ] All existing LinkStorage tests pass
- [ ] Test persistence (insert, restart, query)
- [ ] Test batch operations
- [ ] Test backlinks query
- [ ] Test category/template queries
- [ ] Test coverage: 80%+

## Tasks

### Migration
- [ ] Read existing `scraper/storage/link_storage.py`
- [ ] Add database connection parameter
- [ ] Replace dict operations with SQL queries
- [ ] Update `add_link()` to use INSERT
- [ ] Update `get_links_by_source()` to use SELECT
- [ ] Ensure backwards compatibility

### Batch Operations
- [ ] Implement `add_links_batch()`
- [ ] Use executemany() for efficiency
- [ ] Handle duplicates with INSERT OR IGNORE

### New Query Methods
- [ ] Implement `get_backlinks()`
- [ ] Implement `get_category_members()`
- [ ] Implement `get_template_users()`
- [ ] Use indexes for performance

### Testing
- [ ] Run existing tests to verify compatibility
- [ ] Add tests for new methods
- [ ] Add persistence test
- [ ] Add performance benchmarks

## Technical Details

### Updated Implementation

```python
# scraper/storage/link_storage.py
"""Link storage with database persistence."""

import sqlite3
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Link:
    """Link relationship."""
    source_page_id: int
    target_title: str
    link_type: str


class LinkStorage:
    """
    Storage for wiki link relationships.
    
    Supports wikilinks, template inclusions, and category memberships.
    Database-backed for persistence across runs.
    """
    
    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize link storage with database connection.
        
        Args:
            connection: SQLite database connection
        """
        self.conn = connection
    
    def add_link(
        self,
        source_page_id: int,
        target_title: str,
        link_type: str
    ) -> None:
        """
        Add a link relationship.
        
        Args:
            source_page_id: Source page ID
            target_title: Target page title
            link_type: Type ('wikilink', 'template', 'category')
        """
        self.conn.execute("""
            INSERT OR IGNORE INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
        """, (source_page_id, target_title, link_type))
        
        self.conn.commit()
    
    def add_links_batch(self, links: List[Tuple[int, str, str]]) -> None:
        """
        Add multiple links in batch (efficient).
        
        Args:
            links: List of (source_page_id, target_title, link_type) tuples
        """
        if not links:
            return
        
        self.conn.executemany("""
            INSERT OR IGNORE INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
        """, links)
        
        self.conn.commit()
        logger.info(f"Added {len(links)} links in batch")
    
    def get_links_by_source(self, page_id: int) -> List[Link]:
        """
        Get all links from a page.
        
        Args:
            page_id: Source page ID
        
        Returns:
            List of Link instances
        """
        cursor = self.conn.execute("""
            SELECT source_page_id, target_title, link_type
            FROM links
            WHERE source_page_id = ?
            ORDER BY link_type, target_title
        """, (page_id,))
        
        return [
            Link(row[0], row[1], row[2])
            for row in cursor.fetchall()
        ]
    
    def get_links_by_type(self, page_id: int, link_type: str) -> List[str]:
        """
        Get links of specific type from a page.
        
        Args:
            page_id: Source page ID
            link_type: Type filter
        
        Returns:
            List of target titles
        """
        cursor = self.conn.execute("""
            SELECT target_title
            FROM links
            WHERE source_page_id = ? AND link_type = ?
            ORDER BY target_title
        """, (page_id, link_type))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_backlinks(self, target_title: str) -> List[int]:
        """
        Get pages that link to target ("what links here").
        
        Args:
            target_title: Target page title
        
        Returns:
            List of source page IDs
        """
        cursor = self.conn.execute("""
            SELECT DISTINCT source_page_id
            FROM links
            WHERE target_title = ?
            ORDER BY source_page_id
        """, (target_title,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_category_members(self, category: str) -> List[int]:
        """
        Get pages in a category.
        
        Args:
            category: Category name (with or without "Category:" prefix)
        
        Returns:
            List of page IDs in category
        """
        # Normalize category name
        if not category.startswith('Category:'):
            category = f'Category:{category}'
        
        cursor = self.conn.execute("""
            SELECT source_page_id
            FROM links
            WHERE target_title = ? AND link_type = 'category'
            ORDER BY source_page_id
        """, (category,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_template_users(self, template: str) -> List[int]:
        """
        Get pages that use a template.
        
        Args:
            template: Template name (with or without "Template:" prefix)
        
        Returns:
            List of page IDs using template
        """
        # Normalize template name
        if not template.startswith('Template:'):
            template = f'Template:{template}'
        
        cursor = self.conn.execute("""
            SELECT source_page_id
            FROM links
            WHERE target_title = ? AND link_type = 'template'
            ORDER BY source_page_id
        """, (template,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def count_links(self, page_id: Optional[int] = None) -> int:
        """
        Count links.
        
        Args:
            page_id: Count links from specific page (None = all links)
        
        Returns:
            Number of links
        """
        if page_id is not None:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM links WHERE source_page_id = ?",
                (page_id,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM links")
        
        return cursor.fetchone()[0]
```

### Test Updates

```python
# tests/storage/test_link_storage.py
import pytest
from scraper.storage.link_storage import LinkStorage


class TestLinkStorage:
    """Test LinkStorage class."""
    
    @pytest.fixture
    def storage(self, db):
        """Provide LinkStorage instance."""
        # Assume pages exist
        conn = db.get_connection()
        conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'PageA')")
        conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (2, 0, 'PageB')")
        conn.commit()
        
        return LinkStorage(conn)
    
    def test_add_link(self, storage):
        """Test adding single link."""
        storage.add_link(1, 'PageB', 'wikilink')
        
        links = storage.get_links_by_source(1)
        assert len(links) == 1
        assert links[0].target_title == 'PageB'
    
    def test_batch_operations(self, storage):
        """Test batch link insertion."""
        links = [
            (1, 'Page1', 'wikilink'),
            (1, 'Page2', 'wikilink'),
            (1, 'Template:Info', 'template'),
            (1, 'Category:Test', 'category'),
        ]
        
        storage.add_links_batch(links)
        
        all_links = storage.get_links_by_source(1)
        assert len(all_links) == 4
    
    def test_get_backlinks(self, storage):
        """Test backlinks query."""
        storage.add_link(1, 'PageB', 'wikilink')
        storage.add_link(2, 'PageB', 'wikilink')
        
        backlinks = storage.get_backlinks('PageB')
        assert len(backlinks) == 2
        assert 1 in backlinks
        assert 2 in backlinks
    
    def test_persistence(self, db, storage):
        """Test that data persists across instances."""
        storage.add_link(1, 'PageB', 'wikilink')
        
        # Create new storage instance with same connection
        storage2 = LinkStorage(db.get_connection())
        links = storage2.get_links_by_source(1)
        
        assert len(links) == 1
```

## Dependencies

### Requires
- Story 01: Pages Table Schema
- Story 04: Links Table Schema
- Story 06: Database Initialization
- Epic 01: LinkStorage (existing in-memory version)

### Blocks
- Epic 03: Incremental Updates (needs persisted link data)

## Testing Requirements

- [ ] All existing tests pass (backwards compatibility)
- [ ] New tests for database-specific features
- [ ] Persistence test
- [ ] Performance within 2x of in-memory
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] LinkStorage migrated to database
- [ ] All existing tests pass
- [ ] New query methods implemented
- [ ] Performance acceptable
- [ ] Code coverage ≥80%
- [ ] Code review completed

## Notes

**Migration strategy:**
- Keep same API
- Add database parameter
- Replace dict operations with SQL
- Test thoroughly for compatibility

**Performance:**
- Database may be slightly slower than in-memory
- Use batch operations for efficiency
- Indexes make queries fast enough
