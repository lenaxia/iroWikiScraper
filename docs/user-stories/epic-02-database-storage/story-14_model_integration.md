# Story 14: Database Integration for Models

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-14  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **developer**,  
I want **seamless model-database integration**,  
So that **conversions between dataclasses and database rows are automatic, type-safe, and preserve all data**.

## Description

Add database integration methods to all model classes (Page, Revision, File, Link). These methods handle conversion between Python dataclass instances and database rows, ensuring type safety and data fidelity.

## Acceptance Criteria

### 1. Model Methods
- [ ] Add `from_db_row(row: sqlite3.Row) -> Model` classmethod to all models
- [ ] Add `to_db_params() -> tuple` method to all models
- [ ] Handle type conversions (datetime, JSON, NULL)
- [ ] Ensure round-trip fidelity

### 2. Models to Update
- [ ] `scraper/models/page.py` - Page model
- [ ] `scraper/models/revision.py` - Revision model
- [ ] `scraper/models/file.py` - FileMetadata model
- [ ] `scraper/models/link.py` - Link model (if exists as separate model)

### 3. Type Conversions
- [ ] datetime: ISO 8601 string ↔ datetime object
- [ ] JSON: TEXT ↔ List[str] (for tags)
- [ ] NULL: Database NULL ↔ Python None
- [ ] Boolean: INTEGER (0/1) ↔ bool

### 4. Testing
- [ ] Test `from_db_row()` for each model
- [ ] Test `to_db_params()` for each model
- [ ] Test round-trip conversion (model → DB → model)
- [ ] Test NULL handling
- [ ] Test type conversions
- [ ] Test coverage: 80%+

## Technical Details

### Page Model Update

```python
# scraper/models/page.py

from dataclasses import dataclass
import sqlite3
from typing import Optional


@dataclass
class Page:
    """Wiki page model."""
    page_id: Optional[int]
    namespace: int
    title: str
    is_redirect: bool = False
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Page':
        """
        Create Page from database row.
        
        Args:
            row: SQLite row from pages table
        
        Returns:
            Page instance
        """
        return cls(
            page_id=row['page_id'],
            namespace=row['namespace'],
            title=row['title'],
            is_redirect=bool(row['is_redirect'])
        )
    
    def to_db_params(self) -> tuple:
        """
        Convert to database parameters for INSERT/UPDATE.
        
        Returns:
            Tuple of values for SQL query
        """
        return (
            self.namespace,
            self.title,
            self.is_redirect
        )
```

### Revision Model Update

```python
# scraper/models/revision.py

from dataclasses import dataclass
import sqlite3
import json
from datetime import datetime
from typing import Optional, List


@dataclass
class Revision:
    """Wiki revision model."""
    revision_id: int
    page_id: int
    parent_id: Optional[int]
    timestamp: datetime
    user: Optional[str]
    user_id: Optional[int]
    comment: Optional[str]
    content: str
    size: int
    sha1: str
    minor: bool
    tags: Optional[List[str]]
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Revision':
        """
        Create Revision from database row.
        
        Args:
            row: SQLite row from revisions table
        
        Returns:
            Revision instance
        """
        # Parse tags JSON
        tags = None
        if row['tags']:
            tags = json.loads(row['tags'])
        
        return cls(
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
    
    def to_db_params(self) -> tuple:
        """
        Convert to database parameters.
        
        Returns:
            Tuple of values for SQL query
        """
        # Convert tags to JSON
        tags_json = json.dumps(self.tags) if self.tags else None
        
        return (
            self.revision_id,
            self.page_id,
            self.parent_id,
            self.timestamp.isoformat(),
            self.user,
            self.user_id,
            self.comment,
            self.content,
            self.size,
            self.sha1,
            self.minor,
            tags_json
        )
```

### FileMetadata Model Update

```python
# scraper/models/file.py

from dataclasses import dataclass
import sqlite3
from datetime import datetime
from typing import Optional


@dataclass
class FileMetadata:
    """File metadata model."""
    filename: str
    url: str
    descriptionurl: str
    sha1: str
    size: int
    width: Optional[int]
    height: Optional[int]
    mime_type: str
    timestamp: datetime
    uploader: Optional[str]
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'FileMetadata':
        """Create FileMetadata from database row."""
        return cls(
            filename=row['filename'],
            url=row['url'],
            descriptionurl=row['descriptionurl'],
            sha1=row['sha1'],
            size=row['size'],
            width=row['width'],
            height=row['height'],
            mime_type=row['mime_type'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            uploader=row['uploader']
        )
    
    def to_db_params(self) -> tuple:
        """Convert to database parameters."""
        return (
            self.filename,
            self.url,
            self.descriptionurl,
            self.sha1,
            self.size,
            self.width,
            self.height,
            self.mime_type,
            self.timestamp.isoformat(),
            self.uploader
        )
```

### Test Implementation

```python
# tests/models/test_model_integration.py

import pytest
import sqlite3
from datetime import datetime
from scraper.models.page import Page
from scraper.models.revision import Revision
from scraper.models.file import FileMetadata


class TestModelDatabaseIntegration:
    """Test model-database integration methods."""
    
    def test_page_round_trip(self, db):
        """Test Page round-trip conversion."""
        # Create page
        page = Page(
            page_id=None,
            namespace=0,
            title="TestPage",
            is_redirect=False
        )
        
        # Insert to database
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO pages (namespace, title, is_redirect) VALUES (?, ?, ?)",
            page.to_db_params()
        )
        conn.commit()
        
        # Retrieve from database
        cursor = conn.execute("SELECT * FROM pages WHERE title = 'TestPage'")
        row = cursor.fetchone()
        
        # Convert back to model
        loaded_page = Page.from_db_row(row)
        
        # Verify round-trip fidelity
        assert loaded_page.namespace == page.namespace
        assert loaded_page.title == page.title
        assert loaded_page.is_redirect == page.is_redirect
        assert loaded_page.page_id is not None
    
    def test_revision_round_trip_with_tags(self, db):
        """Test Revision round-trip with tags."""
        conn = db.get_connection()
        
        # Insert page first
        conn.execute(
            "INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')"
        )
        
        # Create revision with tags
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            user="TestUser",
            user_id=123,
            comment="Test edit",
            content="Test content",
            size=12,
            sha1="abc123",
            minor=False,
            tags=["visual edit", "mobile edit"]
        )
        
        # Insert to database
        conn.execute("""
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, revision.to_db_params())
        conn.commit()
        
        # Retrieve from database
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 100")
        row = cursor.fetchone()
        
        # Convert back to model
        loaded_revision = Revision.from_db_row(row)
        
        # Verify all fields
        assert loaded_revision.revision_id == revision.revision_id
        assert loaded_revision.page_id == revision.page_id
        assert loaded_revision.timestamp == revision.timestamp
        assert loaded_revision.user == revision.user
        assert loaded_revision.content == revision.content
        assert loaded_revision.tags == revision.tags
    
    def test_null_handling(self, db):
        """Test NULL field handling."""
        conn = db.get_connection()
        conn.execute("INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'Test')")
        
        # Create revision with NULL fields
        revision = Revision(
            revision_id=100,
            page_id=1,
            parent_id=None,  # NULL
            timestamp=datetime(2024, 1, 15),
            user=None,  # NULL
            user_id=None,  # NULL
            comment=None,  # NULL
            content="Test",
            size=4,
            sha1="abc",
            minor=False,
            tags=None  # NULL
        )
        
        # Round-trip
        conn.execute("""
            INSERT INTO revisions 
            (revision_id, page_id, parent_id, timestamp, user, user_id,
             comment, content, size, sha1, minor, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, revision.to_db_params())
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM revisions WHERE revision_id = 100")
        loaded = Revision.from_db_row(cursor.fetchone())
        
        # Verify NULLs preserved
        assert loaded.parent_id is None
        assert loaded.user is None
        assert loaded.user_id is None
        assert loaded.comment is None
        assert loaded.tags is None
```

## Dependencies

### Requires
- All model classes from Epic 01
- All schema stories (01-05)
- Story 06: Database Initialization

### Blocks
- All repository classes (cleanup/simplification)

## Testing Requirements

- [ ] Test round-trip for each model
- [ ] Test NULL handling
- [ ] Test type conversions
- [ ] Test with realistic data
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] All models updated with methods
- [ ] All tests passing
- [ ] Round-trip fidelity verified
- [ ] Code coverage ≥80%
- [ ] Documentation updated
- [ ] Code review completed

## Notes

**Benefits:**
- Centralized conversion logic
- Type safety
- Easier to maintain
- Reduces code duplication in repositories

**Usage in repositories:**
```python
# Before (manual conversion)
page = Page(
    page_id=row['page_id'],
    namespace=row['namespace'],
    title=row['title'],
    is_redirect=bool(row['is_redirect'])
)

# After (use classmethod)
page = Page.from_db_row(row)
```
