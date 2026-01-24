# Story 09: File CRUD Operations

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-09  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 0.5 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **CRUD operations for files**,  
So that **I can track downloaded file metadata with SHA1-based duplicate detection**.

## Description

Implement a `FileRepository` class that provides CRUD operations for the files table. This repository handles file metadata (not actual file content) and supports SHA1-based duplicate detection.

## Acceptance Criteria

### 1. FileRepository Implementation
- [ ] Create `scraper/storage/file_repository.py`
- [ ] Method: `insert_file(file: FileMetadata) -> None`
- [ ] Method: `insert_files_batch(files: List[FileMetadata]) -> None`
- [ ] Method: `get_file(filename: str) -> Optional[FileMetadata]`
- [ ] Method: `find_by_sha1(sha1: str) -> List[FileMetadata]`
- [ ] Method: `list_files(mime_type: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[FileMetadata]`
- [ ] Method: `update_file(file: FileMetadata) -> None`
- [ ] Method: `delete_file(filename: str) -> None`
- [ ] Method: `count_files(mime_type: Optional[str] = None) -> int`

### 2. Data Conversion
- [ ] Convert FileMetadata dataclass to SQL parameters
- [ ] Convert SQLite Row to FileMetadata dataclass
- [ ] Handle NULL dimensions (non-image files)
- [ ] Handle datetime serialization

### 3. Duplicate Detection
- [ ] `find_by_sha1()` returns all files with matching hash
- [ ] Use SHA1 index for efficient queries
- [ ] Support deduplication workflows

### 4. Testing
- [ ] Test insert file
- [ ] Test batch insert
- [ ] Test get by filename
- [ ] Test find by SHA1 (duplicates)
- [ ] Test list files with MIME type filter
- [ ] Test NULL dimensions handling
- [ ] Test coverage: 80%+

## Technical Details

### Implementation Outline

```python
# scraper/storage/file_repository.py
"""Repository for file metadata CRUD operations."""

import sqlite3
import logging
from typing import List, Optional
from datetime import datetime

from scraper.models.file import FileMetadata

logger = logging.getLogger(__name__)


class FileRepository:
    """Repository for files table operations."""
    
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
    
    def insert_file(self, file: FileMetadata) -> None:
        """Insert single file metadata."""
        self.conn.execute("""
            INSERT OR REPLACE INTO files
            (filename, url, descriptionurl, sha1, size, width, height, 
             mime_type, timestamp, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file.filename,
            file.url,
            file.descriptionurl,
            file.sha1,
            file.size,
            file.width,
            file.height,
            file.mime_type,
            file.timestamp,
            file.uploader
        ))
        self.conn.commit()
    
    def find_by_sha1(self, sha1: str) -> List[FileMetadata]:
        """Find files by SHA1 hash (for duplicate detection)."""
        cursor = self.conn.execute("""
            SELECT * FROM files WHERE sha1 = ?
        """, (sha1,))
        
        return [self._row_to_file(row) for row in cursor.fetchall()]
    
    def _row_to_file(self, row: sqlite3.Row) -> FileMetadata:
        """Convert database row to FileMetadata instance."""
        return FileMetadata(
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
```

## Dependencies

### Requires
- Story 03: Files Table Schema
- Story 06: Database Initialization
- Epic 01: FileMetadata model

### Blocks
- Epic 01: File download integration

## Testing Requirements

- [ ] Insert file with all fields
- [ ] Insert file with NULL dimensions
- [ ] Find duplicates by SHA1
- [ ] List with MIME type filter
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] FileRepository implemented
- [ ] All methods working
- [ ] All tests passing
- [ ] Code coverage ≥80%
- [ ] Code review completed
