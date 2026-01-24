# Story 11: Full-Text Search (FTS5)

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-11  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **user**,  
I want **to search wiki content by keywords**,  
So that **I can quickly find pages containing specific terms with ranking and snippets**.

## Description

Implement full-text search using SQLite's FTS5 (Full-Text Search) extension. This enables fast keyword search across all page content with ranking, snippet extraction, and support for complex queries (AND, OR, NOT, phrases).

## Background & Context

**What is FTS5?**
- SQLite virtual table for full-text indexing
- Much faster than LIKE '%keyword%'
- Supports ranking (BM25 algorithm)
- Generates snippets with match highlighting
- Supports boolean queries: "prontera AND geffen"

**Why This Story Matters:**
- Enable content discovery
- Find pages by keywords
- Support research use cases
- Foundation for search UI

## Acceptance Criteria

### 1. FTS5 Virtual Table
- [ ] Create `schema/sqlite/006_fts.sql`
- [ ] Virtual table: `pages_fts(page_id UNINDEXED, title, content)`
- [ ] Triggers to sync data from pages/revisions to pages_fts
- [ ] Populate FTS table on schema init

### 2. Search Module
- [ ] Create `scraper/storage/search.py`
- [ ] Dataclass: `SearchResult(page_id, title, snippet, rank)`
- [ ] Function: `search(db, query, limit=10, offset=0) -> List[SearchResult]`
- [ ] Function: `search_titles(db, query, limit=10) -> List[SearchResult]`
- [ ] Function: `index_page(db, page_id)` - Reindex single page
- [ ] Function: `rebuild_index(db)` - Rebuild entire FTS index

### 3. Query Support
- [ ] Simple queries: "prontera"
- [ ] Boolean AND: "prontera AND geffen"
- [ ] Boolean OR: "prontera OR geffen"
- [ ] Boolean NOT: "prontera NOT classic"
- [ ] Phrase queries: '"prontera castle"'
- [ ] Prefix queries: "pron*"

### 4. Snippet Extraction
- [ ] Extract relevant text excerpts
- [ ] Highlight matching terms
- [ ] Configurable snippet length
- [ ] Smart truncation (full words)

### 5. Performance
- [ ] Search 2,400 pages < 50ms
- [ ] Index build < 10 seconds
- [ ] Incremental updates efficient

### 6. Testing
- [ ] Test simple keyword search
- [ ] Test boolean queries (AND, OR, NOT)
- [ ] Test phrase queries
- [ ] Test ranking (relevant results first)
- [ ] Test snippet extraction
- [ ] Test index updates
- [ ] Test coverage: 80%+

## Technical Details

### FTS Schema

```sql
-- schema/sqlite/006_fts.sql
-- Full-text search using FTS5
-- Version: 1.0

-- Create FTS5 virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    page_id UNINDEXED,  -- Don't index page_id (we'll join on it)
    title,               -- Page title (searchable)
    content,             -- Page content (searchable)
    tokenize='porter unicode61'  -- Porter stemming + Unicode support
);

-- Trigger to sync new revisions to FTS
CREATE TRIGGER IF NOT EXISTS revisions_fts_insert
AFTER INSERT ON revisions
BEGIN
    -- Delete old FTS entry for this page
    DELETE FROM pages_fts WHERE page_id = NEW.page_id;
    
    -- Insert new FTS entry with latest content
    INSERT INTO pages_fts (page_id, title, content)
    SELECT p.page_id, p.title, NEW.content
    FROM pages p
    WHERE p.page_id = NEW.page_id;
END;

-- Trigger to sync page title updates to FTS
CREATE TRIGGER IF NOT EXISTS pages_fts_update
AFTER UPDATE OF title ON pages
BEGIN
    -- Update title in FTS
    UPDATE pages_fts
    SET title = NEW.title
    WHERE page_id = NEW.page_id;
END;

-- Trigger to remove deleted pages from FTS
CREATE TRIGGER IF NOT EXISTS pages_fts_delete
AFTER DELETE ON pages
BEGIN
    DELETE FROM pages_fts WHERE page_id = OLD.page_id;
END;

-- Initial population: populate FTS with latest revision for each page
INSERT INTO pages_fts (page_id, title, content)
SELECT 
    p.page_id,
    p.title,
    (
        SELECT r.content
        FROM revisions r
        WHERE r.page_id = p.page_id
        ORDER BY r.timestamp DESC
        LIMIT 1
    ) as content
FROM pages p
WHERE EXISTS (
    SELECT 1 FROM revisions r WHERE r.page_id = p.page_id
);
```

### Search Module Implementation

```python
# scraper/storage/search.py
"""Full-text search functionality using FTS5."""

import sqlite3
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result with ranking and snippet."""
    page_id: int
    title: str
    snippet: str
    rank: float


def search(
    connection: sqlite3.Connection,
    query: str,
    limit: int = 10,
    offset: int = 0
) -> List[SearchResult]:
    """
    Search page content using FTS5.
    
    Args:
        connection: Database connection
        query: Search query (supports FTS5 syntax)
        limit: Maximum results to return
        offset: Number of results to skip
    
    Returns:
        List of SearchResult instances, ordered by relevance
    
    Examples:
        >>> search(db, "prontera")  # Simple search
        >>> search(db, "prontera AND geffen")  # Boolean AND
        >>> search(db, '"prontera castle"')  # Phrase search
        >>> search(db, "pron*")  # Prefix search
    """
    cursor = connection.execute("""
        SELECT 
            pf.page_id,
            pf.title,
            snippet(pages_fts, 2, '<mark>', '</mark>', '...', 32) as snippet,
            rank as rank
        FROM pages_fts pf
        WHERE pages_fts MATCH ?
        ORDER BY rank
        LIMIT ? OFFSET ?
    """, (query, limit, offset))
    
    results = []
    for row in cursor.fetchall():
        results.append(SearchResult(
            page_id=row['page_id'],
            title=row['title'],
            snippet=row['snippet'],
            rank=row['rank']
        ))
    
    logger.debug(f"Search '{query}' returned {len(results)} results")
    return results


def search_titles(
    connection: sqlite3.Connection,
    query: str,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search only page titles (faster than full content search).
    
    Args:
        connection: Database connection
        query: Search query
        limit: Maximum results
    
    Returns:
        List of SearchResult instances
    """
    cursor = connection.execute("""
        SELECT 
            pf.page_id,
            pf.title,
            '' as snippet,
            rank as rank
        FROM pages_fts pf
        WHERE title MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit))
    
    results = []
    for row in cursor.fetchall():
        results.append(SearchResult(
            page_id=row['page_id'],
            title=row['title'],
            snippet='',
            rank=row['rank']
        ))
    
    return results


def index_page(connection: sqlite3.Connection, page_id: int) -> None:
    """
    Reindex a single page in FTS.
    
    Args:
        connection: Database connection
        page_id: Page ID to reindex
    """
    # Delete existing entry
    connection.execute("DELETE FROM pages_fts WHERE page_id = ?", (page_id,))
    
    # Insert new entry with latest content
    connection.execute("""
        INSERT INTO pages_fts (page_id, title, content)
        SELECT 
            p.page_id,
            p.title,
            (
                SELECT r.content
                FROM revisions r
                WHERE r.page_id = p.page_id
                ORDER BY r.timestamp DESC
                LIMIT 1
            )
        FROM pages p
        WHERE p.page_id = ?
    """, (page_id,))
    
    connection.commit()
    logger.info(f"Reindexed page {page_id}")


def rebuild_index(connection: sqlite3.Connection) -> None:
    """
    Rebuild entire FTS index from scratch.
    
    Useful if FTS table gets corrupted or out of sync.
    
    Args:
        connection: Database connection
    """
    logger.info("Rebuilding FTS index...")
    
    # Clear existing index
    connection.execute("DELETE FROM pages_fts")
    
    # Repopulate with latest revisions
    connection.execute("""
        INSERT INTO pages_fts (page_id, title, content)
        SELECT 
            p.page_id,
            p.title,
            (
                SELECT r.content
                FROM revisions r
                WHERE r.page_id = p.page_id
                ORDER BY r.timestamp DESC
                LIMIT 1
            ) as content
        FROM pages p
        WHERE EXISTS (
            SELECT 1 FROM revisions r WHERE r.page_id = p.page_id
        )
    """)
    
    connection.commit()
    
    # Get index size
    cursor = connection.execute("SELECT COUNT(*) FROM pages_fts")
    count = cursor.fetchone()[0]
    
    logger.info(f"FTS index rebuilt: {count} pages indexed")


def optimize_index(connection: sqlite3.Connection) -> None:
    """
    Optimize FTS index (merge segments, reduce size).
    
    Run periodically for best performance.
    
    Args:
        connection: Database connection
    """
    connection.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    connection.commit()
    logger.info("FTS index optimized")
```

### Test Implementation

```python
# tests/storage/test_search.py
import pytest
from scraper.storage.search import search, search_titles, rebuild_index
from scraper.models.page import Page
from scraper.models.revision import Revision
from datetime import datetime


class TestSearch:
    """Test full-text search functionality."""
    
    @pytest.fixture
    def search_db(self, db):
        """Setup database with test data."""
        conn = db.get_connection()
        
        # Insert test pages and revisions
        pages_data = [
            (1, 0, 'Prontera'),
            (2, 0, 'Geffen'),
            (3, 0, 'Payon'),
        ]
        
        for page_id, namespace, title in pages_data:
            conn.execute(
                "INSERT INTO pages (page_id, namespace, title) VALUES (?, ?, ?)",
                (page_id, namespace, title)
            )
        
        revisions_data = [
            (1, 1, None, datetime.now(), 'User1', None, 
             'Prontera is the capital city of Rune-Midgarts Kingdom', 
             55, 'abc', False, None),
            (2, 2, None, datetime.now(), 'User2', None,
             'Geffen is the city of magic and wizards',
             42, 'def', False, None),
            (3, 3, None, datetime.now(), 'User3', None,
             'Payon is a small village in the mountains',
             45, 'ghi', False, None),
        ]
        
        for rev_data in revisions_data:
            conn.execute("""
                INSERT INTO revisions 
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rev_data)
        
        conn.commit()
        
        # Rebuild FTS index
        rebuild_index(conn)
        
        return conn
    
    def test_simple_search(self, search_db):
        """Test simple keyword search."""
        results = search(search_db, "prontera")
        
        assert len(results) >= 1
        assert results[0].title == "Prontera"
        assert "capital" in results[0].snippet.lower()
    
    def test_boolean_and(self, search_db):
        """Test AND query."""
        results = search(search_db, "city AND magic")
        
        assert len(results) >= 1
        assert results[0].title == "Geffen"
    
    def test_phrase_search(self, search_db):
        """Test phrase query."""
        results = search(search_db, '"capital city"')
        
        assert len(results) >= 1
        assert results[0].title == "Prontera"
    
    def test_title_search(self, search_db):
        """Test title-only search."""
        results = search_titles(search_db, "geffen")
        
        assert len(results) >= 1
        assert results[0].title == "Geffen"
    
    def test_ranking(self, search_db):
        """Test that results are ranked by relevance."""
        results = search(search_db, "city")
        
        # Should return multiple results, ranked by relevance
        assert len(results) >= 2
        
        # First result should have best rank
        if len(results) > 1:
            assert results[0].rank <= results[1].rank
    
    def test_no_results(self, search_db):
        """Test search with no matches."""
        results = search(search_db, "nonexistent_term_xyz")
        
        assert len(results) == 0
    
    def test_rebuild_index(self, search_db):
        """Test index rebuild."""
        # Rebuild should succeed without error
        rebuild_index(search_db)
        
        # Search should still work
        results = search(search_db, "prontera")
        assert len(results) >= 1
```

## Dependencies

### Requires
- Story 01: Pages Table Schema
- Story 02: Revisions Table Schema
- Story 06: Database Initialization
- SQLite with FTS5 compiled (standard in Python 3.11+)

### Blocks
- Epic 04: Export with search functionality
- Future: Web UI with search

## Testing Requirements

- [ ] Simple keyword search works
- [ ] Boolean queries work (AND, OR, NOT)
- [ ] Phrase queries work
- [ ] Ranking produces relevant results first
- [ ] Snippet extraction works
- [ ] Index updates correctly
- [ ] Search performance < 50ms for 2,400 pages
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] FTS5 schema created
- [ ] Triggers sync data automatically
- [ ] Search module implemented
- [ ] All query types supported
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Code coverage ≥80%
- [ ] Code review completed

## Notes

**FTS5 advantages:**
- Much faster than LIKE '%keyword%'
- Ranking by relevance
- Snippet generation with highlights
- Boolean queries
- Porter stemming (finds "cities" when searching "city")

**Snippet format:**
- `<mark>matched term</mark>` for highlighting
- `...` for truncation
- Configurable length (default 32 tokens)

**Index maintenance:**
- Triggers keep index in sync automatically
- Can rebuild if needed
- Optimize periodically for best performance

**Future enhancements:**
- Add autocomplete/suggestions
- Add category/namespace filters
- Add date range filters
- Expose via CLI or web API
