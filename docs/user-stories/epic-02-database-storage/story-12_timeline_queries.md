# Story 12: Timeline Queries

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-12  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **researcher**,  
I want **to query historical page states**,  
So that **I can analyze wiki evolution and reconstruct pages as they appeared at specific times**.

## Description

Implement temporal query functions that enable time-travel through wiki history. These functions retrieve page states at specific timestamps and analyze changes over time periods.

## Acceptance Criteria

### 1. Timeline Query Functions
- [ ] Create `scraper/storage/queries.py`
- [ ] Function: `get_page_at_time(db, page_id, timestamp) -> Optional[Revision]`
- [ ] Function: `list_pages_at_time(db, timestamp) -> List[Tuple[Page, Revision]]`
- [ ] Function: `get_changes_in_range(db, start, end) -> List[Change]`
- [ ] Function: `get_page_history(db, page_id) -> List[Revision]`
- [ ] Dataclass: `Change(page_id, revision_id, timestamp, user, comment, size_delta)`

### 2. Query Optimization
- [ ] Use temporal index on timestamp
- [ ] Use composite index on (page_id, timestamp)
- [ ] Verify index usage with EXPLAIN QUERY PLAN
- [ ] Queries run in < 50ms

### 3. Edge Cases
- [ ] Handle page doesn't exist at timestamp
- [ ] Handle page created after timestamp
- [ ] Handle page deleted before timestamp
- [ ] Handle empty date ranges

### 4. Testing
- [ ] Test get page at specific time
- [ ] Test list all pages at time
- [ ] Test changes in date range
- [ ] Test page history
- [ ] Test edge cases
- [ ] Verify index usage
- [ ] Test coverage: 80%+

## Technical Details

### Implementation

```python
# scraper/storage/queries.py
"""Advanced query functions for temporal and statistical analysis."""

import sqlite3
import logging
from typing import List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from scraper.models.page import Page
from scraper.models.revision import Revision

logger = logging.getLogger(__name__)


@dataclass
class Change:
    """Represents a change (edit) to a page."""
    page_id: int
    page_title: str
    revision_id: int
    timestamp: datetime
    user: Optional[str]
    comment: Optional[str]
    size_delta: int  # Change in size (bytes)


def get_page_at_time(
    connection: sqlite3.Connection,
    page_id: int,
    timestamp: datetime
) -> Optional[Revision]:
    """
    Get page state at specific time (time-travel query).
    
    Returns the most recent revision before or at the given timestamp.
    
    Args:
        connection: Database connection
        page_id: Page ID
        timestamp: Point in time to query
    
    Returns:
        Revision instance or None if page didn't exist yet
    
    Example:
        # Get "Prontera" page as it was on 2020-01-01
        rev = get_page_at_time(db, page_id=1, timestamp=datetime(2020, 1, 1))
        if rev:
            print(rev.content)  # Content as of 2020-01-01
    """
    cursor = connection.execute("""
        SELECT *
        FROM revisions
        WHERE page_id = ? AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (page_id, timestamp))
    
    row = cursor.fetchone()
    
    if not row:
        logger.debug(f"Page {page_id} did not exist at {timestamp}")
        return None
    
    return _row_to_revision(row)


def list_pages_at_time(
    connection: sqlite3.Connection,
    timestamp: datetime,
    limit: int = 100,
    offset: int = 0
) -> List[Tuple[Page, Revision]]:
    """
    List all pages as they existed at specific time.
    
    For each page, returns the page metadata and its latest revision
    before the given timestamp.
    
    Args:
        connection: Database connection
        timestamp: Point in time to query
        limit: Maximum pages to return
        offset: Number of pages to skip
    
    Returns:
        List of (Page, Revision) tuples
    
    Example:
        # Get all pages as they were on 2020-01-01
        pages = list_pages_at_time(db, datetime(2020, 1, 1))
        for page, revision in pages:
            print(f"{page.title}: {len(revision.content)} bytes")
    """
    cursor = connection.execute("""
        SELECT 
            p.page_id,
            p.namespace,
            p.title,
            p.is_redirect,
            r.*
        FROM pages p
        INNER JOIN (
            -- Get latest revision before timestamp for each page
            SELECT 
                page_id,
                MAX(timestamp) as max_timestamp
            FROM revisions
            WHERE timestamp <= ?
            GROUP BY page_id
        ) latest ON p.page_id = latest.page_id
        INNER JOIN revisions r 
            ON r.page_id = latest.page_id 
            AND r.timestamp = latest.max_timestamp
        ORDER BY p.namespace, p.title
        LIMIT ? OFFSET ?
    """, (timestamp, limit, offset))
    
    results = []
    for row in cursor.fetchall():
        page = Page(
            page_id=row['page_id'],
            namespace=row['namespace'],
            title=row['title'],
            is_redirect=bool(row['is_redirect'])
        )
        
        revision = _row_to_revision(row)
        
        results.append((page, revision))
    
    logger.debug(f"Found {len(results)} pages at {timestamp}")
    return results


def get_changes_in_range(
    connection: sqlite3.Connection,
    start: datetime,
    end: datetime,
    limit: int = 100,
    offset: int = 0
) -> List[Change]:
    """
    Get all changes (edits) in date range.
    
    Args:
        connection: Database connection
        start: Start of date range (inclusive)
        end: End of date range (inclusive)
        limit: Maximum changes to return
        offset: Number of changes to skip
    
    Returns:
        List of Change instances, ordered by timestamp
    
    Example:
        # Get all edits in January 2024
        changes = get_changes_in_range(
            db,
            datetime(2024, 1, 1),
            datetime(2024, 1, 31, 23, 59, 59)
        )
        for change in changes:
            print(f"{change.timestamp}: {change.user} edited {change.page_title}")
    """
    cursor = connection.execute("""
        SELECT 
            r.page_id,
            p.title as page_title,
            r.revision_id,
            r.timestamp,
            r.user,
            r.comment,
            r.size as size,
            COALESCE(
                r.size - (
                    SELECT size 
                    FROM revisions 
                    WHERE page_id = r.page_id 
                      AND timestamp < r.timestamp 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ),
                r.size
            ) as size_delta
        FROM revisions r
        INNER JOIN pages p ON r.page_id = p.page_id
        WHERE r.timestamp BETWEEN ? AND ?
        ORDER BY r.timestamp
        LIMIT ? OFFSET ?
    """, (start, end, limit, offset))
    
    changes = []
    for row in cursor.fetchall():
        changes.append(Change(
            page_id=row['page_id'],
            page_title=row['page_title'],
            revision_id=row['revision_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            user=row['user'],
            comment=row['comment'],
            size_delta=row['size_delta']
        ))
    
    logger.debug(f"Found {len(changes)} changes between {start} and {end}")
    return changes


def get_page_history(
    connection: sqlite3.Connection,
    page_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[Revision]:
    """
    Get complete edit history for a page.
    
    Args:
        connection: Database connection
        page_id: Page ID
        limit: Maximum revisions to return
        offset: Number of revisions to skip
    
    Returns:
        List of Revision instances, newest first
    """
    cursor = connection.execute("""
        SELECT *
        FROM revisions
        WHERE page_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (page_id, limit, offset))
    
    return [_row_to_revision(row) for row in cursor.fetchall()]


def _row_to_revision(row: sqlite3.Row) -> Revision:
    """Convert database row to Revision instance."""
    import json
    
    tags = None
    if row['tags']:
        tags = json.loads(row['tags'])
    
    return Revision(
        revision_id=row['revision_id'],
        page_id=row['page_id'],
        parent_id=row['parent_id'],
        timestamp=datetime.fromisoformat(row['timestamp']),
        user=row['user'],
        user_id=row['user_id'],
        comment=row['comment'],
        content=row['content'],
        size=row['size'],
        sha1=row['sha1'],
        minor=bool(row['minor']),
        tags=tags
    )
```

### Test Implementation

```python
# tests/storage/test_queries.py
import pytest
from datetime import datetime
from scraper.storage.queries import (
    get_page_at_time,
    list_pages_at_time,
    get_changes_in_range,
    get_page_history
)


class TestTimelineQueries:
    """Test temporal query functions."""
    
    @pytest.fixture
    def timeline_db(self, db):
        """Setup database with timeline data."""
        conn = db.get_connection()
        
        # Insert page
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'TestPage')"
        )
        
        # Insert revisions at different times
        revisions = [
            (1, 1, None, datetime(2024, 1, 1, 10, 0), 'Alice', None, 
             'Version 1', 9, 'abc', False, None),
            (2, 1, 1, datetime(2024, 1, 2, 11, 0), 'Bob', None,
             'Version 2', 9, 'def', False, None),
            (3, 1, 2, datetime(2024, 1, 3, 12, 0), 'Charlie', None,
             'Version 3', 9, 'ghi', False, None),
        ]
        
        for rev in revisions:
            conn.execute("""
                INSERT INTO revisions
                (revision_id, page_id, parent_id, timestamp, user, user_id,
                 content, size, sha1, minor, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rev)
        
        conn.commit()
        return conn
    
    def test_get_page_at_time(self, timeline_db):
        """Test retrieving page at specific time."""
        # Get page as of 2024-01-01 (should get revision 1)
        rev = get_page_at_time(timeline_db, 1, datetime(2024, 1, 1, 12, 0))
        assert rev is not None
        assert rev.content == 'Version 1'
        
        # Get page as of 2024-01-02 (should get revision 2)
        rev = get_page_at_time(timeline_db, 1, datetime(2024, 1, 2, 12, 0))
        assert rev is not None
        assert rev.content == 'Version 2'
        
        # Get page before it existed (should be None)
        rev = get_page_at_time(timeline_db, 1, datetime(2023, 12, 31))
        assert rev is None
    
    def test_list_pages_at_time(self, timeline_db):
        """Test listing all pages at specific time."""
        pages = list_pages_at_time(timeline_db, datetime(2024, 1, 2, 12, 0))
        
        assert len(pages) == 1
        page, revision = pages[0]
        assert page.title == 'TestPage'
        assert revision.content == 'Version 2'
    
    def test_get_changes_in_range(self, timeline_db):
        """Test getting changes in date range."""
        changes = get_changes_in_range(
            timeline_db,
            datetime(2024, 1, 1),
            datetime(2024, 1, 2, 23, 59)
        )
        
        assert len(changes) == 2  # Revisions 1 and 2
        assert changes[0].user == 'Alice'
        assert changes[1].user == 'Bob'
    
    def test_get_page_history(self, timeline_db):
        """Test getting complete page history."""
        history = get_page_history(timeline_db, 1)
        
        assert len(history) == 3
        # Should be in reverse chronological order
        assert history[0].content == 'Version 3'
        assert history[1].content == 'Version 2'
        assert history[2].content == 'Version 1'
```

## Dependencies

### Requires
- Story 02: Revisions Table Schema
- Story 06: Database Initialization
- Story 08: Revision CRUD Operations

### Blocks
- Epic 04: Export with historical snapshots

## Testing Requirements

- [ ] Time-travel queries work correctly
- [ ] Edge cases handled (page doesn't exist yet)
- [ ] Queries use indexes (verify with EXPLAIN QUERY PLAN)
- [ ] Performance < 50ms per query
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] All query functions implemented
- [ ] All tests passing
- [ ] Index usage verified
- [ ] Performance benchmarks met
- [ ] Code coverage ≥80%
- [ ] Code review completed

## Notes

**Use cases:**
- Research wiki evolution
- Compare versions over time
- Analyze editing patterns
- Reconstruct deleted content
- Generate historical snapshots

**Performance:**
- Temporal index critical for these queries
- Composite index optimizes per-page queries
- Most queries should be < 50ms
