# Story 08: Revision CRUD Operations

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-08  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1.5 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **CRUD operations for revisions**,  
So that **I can persist complete edit history with efficient batch operations and temporal queries**.

## Description

Implement a `RevisionRepository` class that provides CRUD operations for the revisions table. This is the most complex repository due to large data volumes (86,500+ revisions), JSON tag handling, and temporal query requirements.

## Acceptance Criteria

### 1. RevisionRepository Implementation
- [ ] Create `scraper/storage/revision_repository.py`
- [ ] Method: `insert_revision(revision: Revision) -> None`
- [ ] Method: `insert_revisions_batch(revisions: List[Revision]) -> None`
- [ ] Method: `get_revision(revision_id: int) -> Optional[Revision]`
- [ ] Method: `get_revisions_by_page(page_id: int, limit: int = 50, offset: int = 0) -> List[Revision]`
- [ ] Method: `get_latest_revision(page_id: int) -> Optional[Revision]`
- [ ] Method: `get_revisions_in_range(start: datetime, end: datetime) -> List[Revision]`
- [ ] Method: `get_page_at_time(page_id: int, timestamp: datetime) -> Optional[Revision]`
- [ ] Method: `count_revisions(page_id: Optional[int] = None) -> int`

### 2. Data Conversion
- [ ] Convert Revision dataclass to SQL parameters
- [ ] Convert SQLite Row to Revision dataclass
- [ ] Handle tags: List[str] ↔ JSON TEXT
- [ ] Handle NULL fields (parent_id, user, user_id, comment, tags)
- [ ] Handle datetime serialization

### 3. Performance Optimizations
- [ ] Batch insert 10,000 revisions < 5 seconds
- [ ] Use composite index for per-page queries
- [ ] Use timestamp index for temporal queries
- [ ] Efficient JSON encoding/decoding for tags

### 4. Testing
- [ ] Test insert single revision
- [ ] Test batch insert (10,000 revisions)
- [ ] Test get by revision_id
- [ ] Test get revisions by page (with pagination)
- [ ] Test get latest revision
- [ ] Test temporal queries
- [ ] Test page state at specific time
- [ ] Test NULL field handling
- [ ] Test tags JSON conversion
- [ ] Test coverage: 80%+

## Technical Details

### Implementation Outline

```python
# scraper/storage/revision_repository.py
"""Repository for revision CRUD operations."""

import json
import sqlite3
import logging
from typing import List, Optional
from datetime import datetime

from scraper.models.revision import Revision

logger = logging.getLogger(__name__)


class RevisionRepository:
    """Repository for revisions table operations."""
    
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
    
    def insert_revision(self, revision: Revision) -> None:
        """Insert single revision."""
        # Convert tags list to JSON
        tags_json = json.dumps(revision.tags) if revision.tags else None
        
        self.conn.execute("""
            INSERT OR REPLACE INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id, 
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            revision.revision_id,
            revision.page_id,
            revision.parent_id,
            revision.timestamp,
            revision.user,
            revision.user_id,
            revision.comment,
            revision.content,
            revision.size,
            revision.sha1,
            revision.minor,
            tags_json
        ))
        self.conn.commit()
    
    def insert_revisions_batch(self, revisions: List[Revision]) -> None:
        """Batch insert revisions (efficient)."""
        if not revisions:
            return
        
        data = [
            (
                r.revision_id, r.page_id, r.parent_id, r.timestamp,
                r.user, r.user_id, r.comment, r.content, r.size,
                r.sha1, r.minor,
                json.dumps(r.tags) if r.tags else None
            )
            for r in revisions
        ]
        
        self.conn.executemany("""
            INSERT OR REPLACE INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id, 
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        self.conn.commit()
        logger.info(f"Inserted {len(revisions)} revisions in batch")
    
    def get_revisions_by_page(
        self,
        page_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Revision]:
        """Get revisions for a page (newest first)."""
        cursor = self.conn.execute("""
            SELECT * FROM revisions
            WHERE page_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (page_id, limit, offset))
        
        return [self._row_to_revision(row) for row in cursor.fetchall()]
    
    def get_latest_revision(self, page_id: int) -> Optional[Revision]:
        """Get most recent revision for a page."""
        cursor = self.conn.execute("""
            SELECT * FROM revisions
            WHERE page_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (page_id,))
        
        row = cursor.fetchone()
        return self._row_to_revision(row) if row else None
    
    def get_page_at_time(
        self,
        page_id: int,
        timestamp: datetime
    ) -> Optional[Revision]:
        """Get page state at specific time (temporal query)."""
        cursor = self.conn.execute("""
            SELECT * FROM revisions
            WHERE page_id = ? AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (page_id, timestamp))
        
        row = cursor.fetchone()
        return self._row_to_revision(row) if row else None
    
    def _row_to_revision(self, row: sqlite3.Row) -> Revision:
        """Convert database row to Revision instance."""
        # Parse tags JSON
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

## Dependencies

### Requires
- Story 01: Pages Table Schema
- Story 02: Revisions Table Schema
- Story 06: Database Initialization
- Epic 01: Revision model

### Blocks
- Story 12: Timeline Queries (uses these methods)
- Epic 03: Incremental Updates (uses latest revision tracking)

## Testing Requirements

- [ ] Batch insert 10,000 revisions < 5 seconds
- [ ] Per-page queries use composite index (EXPLAIN QUERY PLAN)
- [ ] Temporal queries use timestamp index
- [ ] Tags round-trip correctly (List[str] ↔ JSON)
- [ ] NULL fields handled correctly
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] RevisionRepository implemented
- [ ] All methods working
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Code coverage ≥80%
- [ ] Code review completed

## Notes

**Performance critical:**
- This table has 86,500+ rows
- Batch operations essential
- Index usage must be verified

**JSON handling:**
- Tags stored as JSON TEXT
- Use json.dumps/loads
- Handle NULL (no tags)
