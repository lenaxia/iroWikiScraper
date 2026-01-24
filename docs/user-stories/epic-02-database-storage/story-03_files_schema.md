# Story 03: Files Table Schema

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-03  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 0.5 days  
**Assignee**: TBD

## User Story

As a **database developer**,  
I want **a SQL schema for file metadata**,  
So that **I can track all uploaded files with checksums for duplicate detection and efficient queries**.

## Description

Design and implement the SQL schema for the `files` table, which stores metadata about files uploaded to the wiki (images, PDFs, etc.). The schema must support ~4,000 files with efficient lookups by filename and SHA1 hash for duplicate detection.

This table stores metadata only, not the actual file data (files are downloaded separately to disk).

## Background & Context

**What is the files table?**
- Stores metadata for uploaded files (images, documents, etc.)
- One row per file (unique by filename)
- Includes dimensions, MIME type, uploader, timestamps
- SHA1 hash enables duplicate detection
- Actual file content stored on disk, not in database

**iRO Wiki Scale:**
- ~4,000 files total
- Mostly images: PNG, JPG, GIF
- Some documents: PDF
- File sizes: 1KB - 10MB
- Dimensions: mostly 800x600 or smaller

**Why This Story Matters:**
- Track downloaded file metadata
- Enable duplicate detection via SHA1
- Support file discovery and searching
- Coordinate with file download system (Epic 01)

## Acceptance Criteria

### 1. Schema File Creation
- [ ] Create `schema/sqlite/003_files.sql`
- [ ] File contains complete table definition
- [ ] Includes all indexes
- [ ] Includes comments explaining fields

### 2. Table Structure
- [ ] Column: `filename` (TEXT PRIMARY KEY)
- [ ] Column: `url` (TEXT NOT NULL)
- [ ] Column: `descriptionurl` (TEXT NOT NULL)
- [ ] Column: `sha1` (TEXT NOT NULL)
- [ ] Column: `size` (INTEGER NOT NULL)
- [ ] Column: `width` (INTEGER NULL)
- [ ] Column: `height` (INTEGER NULL)
- [ ] Column: `mime_type` (TEXT NOT NULL)
- [ ] Column: `timestamp` (TIMESTAMP NOT NULL)
- [ ] Column: `uploader` (TEXT NULL)

### 3. Constraints
- [ ] Primary key on `filename`
- [ ] NOT NULL on required fields
- [ ] Check constraint: `size >= 0`
- [ ] Check constraint: `width IS NULL OR width > 0`
- [ ] Check constraint: `height IS NULL OR height > 0`

### 4. Indexes
- [ ] Index: `idx_files_sha1` on `sha1` for duplicate detection
- [ ] Index: `idx_files_timestamp` on `timestamp` for temporal queries
- [ ] Index: `idx_files_mime` on `mime_type` for filtering by type

### 5. SQL Compatibility
- [ ] Valid SQLite SQL syntax
- [ ] Uses standard SQL types
- [ ] Comments for design decisions

### 6. Performance
- [ ] Supports 4,000 files efficiently
- [ ] Filename lookup < 1ms
- [ ] SHA1 lookup < 5ms
- [ ] Bulk inserts (1000 files) < 1 second

## Tasks

### Schema Design
- [ ] Design table structure based on MediaWiki API response
- [ ] Determine which fields are required vs optional
- [ ] Plan index strategy for common queries
- [ ] Handle NULL dimensions for non-image files

### SQL File Creation
- [ ] Create `003_files.sql` with CREATE TABLE statement
- [ ] Add all column definitions
- [ ] Add constraints for data validation
- [ ] Add indexes for performance
- [ ] Add inline comments

### Validation
- [ ] Test schema creation in SQLite
- [ ] Test insert with complete metadata (image)
- [ ] Test insert with NULL dimensions (PDF)
- [ ] Test unique constraint on filename
- [ ] Verify index usage with EXPLAIN QUERY PLAN

### Documentation
- [ ] Document each field's purpose
- [ ] Explain when width/height can be NULL
- [ ] Document SHA1 usage for deduplication
- [ ] Note file storage coordination

## Technical Details

### File Structure
```
schema/
└── sqlite/
    ├── 001_pages.sql
    ├── 002_revisions.sql
    └── 003_files.sql
```

### Schema Implementation

```sql
-- schema/sqlite/003_files.sql
-- Files table: Stores metadata for uploaded files
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 12+

CREATE TABLE IF NOT EXISTS files (
    -- Unique filename (e.g., "Example.png", "Document.pdf")
    -- Primary key ensures uniqueness
    filename TEXT PRIMARY KEY,
    
    -- Full URL to file on wiki server
    -- Example: https://irowiki.org/w/images/a/ab/Example.png
    url TEXT NOT NULL,
    
    -- URL to file description page
    -- Example: https://irowiki.org/wiki/File:Example.png
    descriptionurl TEXT NOT NULL,
    
    -- SHA1 hash of file content (for duplicate detection)
    -- 40 character hex string
    sha1 TEXT NOT NULL,
    
    -- File size in bytes
    size INTEGER NOT NULL,
    
    -- Image width in pixels (NULL for non-image files)
    width INTEGER,
    
    -- Image height in pixels (NULL for non-image files)
    height INTEGER,
    
    -- MIME type (e.g., "image/png", "image/jpeg", "application/pdf")
    mime_type TEXT NOT NULL,
    
    -- Upload timestamp (UTC)
    timestamp TIMESTAMP NOT NULL,
    
    -- Username of uploader (NULL if user deleted)
    uploader TEXT,
    
    -- Validation constraints
    CHECK(size >= 0),
    CHECK(width IS NULL OR width > 0),
    CHECK(height IS NULL OR height > 0)
);

-- Index for duplicate detection by content hash
-- Used by: find_by_sha1(), deduplication
CREATE INDEX IF NOT EXISTS idx_files_sha1 
ON files(sha1);

-- Index for temporal queries (recent uploads, date ranges)
-- Used by: list_recent_files(), statistics
CREATE INDEX IF NOT EXISTS idx_files_timestamp 
ON files(timestamp);

-- Index for filtering by file type
-- Used by: list_images(), get_pdfs(), statistics by type
CREATE INDEX IF NOT EXISTS idx_files_mime 
ON files(mime_type);

-- Index for uploader statistics
-- Used by: contributor file counts
CREATE INDEX IF NOT EXISTS idx_files_uploader
ON files(uploader) WHERE uploader IS NOT NULL;
```

### Query Examples

```sql
-- Get file metadata by filename
SELECT *
FROM files
WHERE filename = 'Example.png';

-- Find duplicate files by SHA1
SELECT filename, url, size
FROM files
WHERE sha1 = 'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3'
ORDER BY timestamp;

-- List recent uploads
SELECT filename, uploader, timestamp, size
FROM files
ORDER BY timestamp DESC
LIMIT 20;

-- Get all images (by MIME type)
SELECT filename, width, height, size
FROM files
WHERE mime_type LIKE 'image/%'
ORDER BY size DESC;

-- Find large files (> 1MB)
SELECT filename, size, mime_type
FROM files
WHERE size > 1048576
ORDER BY size DESC;

-- Get files by uploader
SELECT filename, timestamp, size
FROM files
WHERE uploader = 'Alice'
ORDER BY timestamp DESC;

-- Statistics by MIME type
SELECT mime_type, COUNT(*) as count, SUM(size) as total_bytes
FROM files
GROUP BY mime_type
ORDER BY count DESC;
```

### Test Script

```bash
#!/bin/bash
# test_files_schema.sh
# Validates files schema

set -e

DB="test_files.db"
SCHEMA="schema/sqlite/003_files.sql"

rm -f "$DB"

echo "Creating schema..."
sqlite3 "$DB" < "$SCHEMA"

# Test inserts
echo "Testing inserts..."
sqlite3 "$DB" <<EOF
-- Insert image file
INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader)
VALUES ('Example.png', 
        'https://irowiki.org/w/images/Example.png',
        'https://irowiki.org/wiki/File:Example.png',
        'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3',
        12345,
        800,
        600,
        'image/png',
        '2024-01-15 10:00:00',
        'Alice');

-- Insert PDF (no dimensions)
INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp, uploader)
VALUES ('Document.pdf', 
        'https://irowiki.org/w/images/Document.pdf',
        'https://irowiki.org/wiki/File:Document.pdf',
        'b94a8fe5ccb19ba61c4c0873d391e987982fbbd4',
        54321,
        'application/pdf',
        '2024-01-16 11:00:00',
        'Bob');

-- Insert with NULL uploader
INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp)
VALUES ('Anonymous.jpg', 
        'https://irowiki.org/w/images/Anonymous.jpg',
        'https://irowiki.org/wiki/File:Anonymous.jpg',
        'c94a8fe5ccb19ba61c4c0873d391e987982fbbd5',
        9876,
        400,
        300,
        'image/jpeg',
        '2024-01-17 12:00:00');
EOF

# Test unique constraint
echo "Testing unique constraint..."
if sqlite3 "$DB" "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) VALUES ('Example.png', 'http://test.com', 'http://test.com', 'abc', 100, 'image/png', '2024-01-01');" 2>&1 | grep -q UNIQUE; then
    echo "✓ Unique constraint works"
else
    echo "✗ Unique constraint failed"
    exit 1
fi

# Test check constraints
echo "Testing check constraints..."
if sqlite3 "$DB" "INSERT INTO files (filename, url, descriptionurl, sha1, size, mime_type, timestamp) VALUES ('Negative.png', 'http://test.com', 'http://test.com', 'abc', -100, 'image/png', '2024-01-01');" 2>&1 | grep -q CHECK; then
    echo "✓ Size check constraint works"
else
    echo "✗ Size check constraint failed"
    exit 1
fi

# Test indexes
echo "Checking indexes..."
INDEX_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='files';")
if [ "$INDEX_COUNT" -ge 4 ]; then
    echo "✓ Indexes created: $INDEX_COUNT"
else
    echo "✗ Expected at least 4 indexes, found $INDEX_COUNT"
    exit 1
fi

# Test SHA1 index usage
echo "Testing SHA1 index usage..."
sqlite3 "$DB" "EXPLAIN QUERY PLAN SELECT * FROM files WHERE sha1 = 'test';"

rm -f "$DB"
echo "✓ All tests passed"
```

### Field Mapping from MediaWiki API

| API Field | DB Column | Notes |
|-----------|-----------|-------|
| name | filename | Primary key |
| url | url | Download URL |
| descriptionurl | descriptionurl | File page URL |
| sha1 | sha1 | Content hash |
| size | size | Bytes |
| width | width | Pixels (NULL for non-images) |
| height | height | Pixels (NULL for non-images) |
| mime | mime_type | MIME type string |
| timestamp | timestamp | ISO 8601 → TIMESTAMP |
| user | uploader | Can be NULL |

## Dependencies

### Requires
- SQLite 3.35+
- Directory: `schema/sqlite/` created

### Blocks
- Story 06: Database Initialization
- Story 09: File CRUD Operations
- Epic 01 Story 08: File Download (coordinates with this table)

## Testing Requirements

### Schema Validation Tests
- [ ] SQL file executes without errors
- [ ] All columns created with correct types
- [ ] Primary key on filename enforced
- [ ] Check constraints validated (size, width, height)

### Index Tests
- [ ] Verify 4 indexes created
- [ ] SHA1 index used for duplicate queries
- [ ] Timestamp index used for temporal queries
- [ ] MIME type index used for filtering

### Data Integrity Tests
- [ ] Insert image with all fields succeeds
- [ ] Insert non-image with NULL dimensions succeeds
- [ ] Duplicate filename rejected
- [ ] Negative size rejected
- [ ] Zero or negative width/height rejected
- [ ] NULL width/height allowed

### Performance Tests
- [ ] Insert 1,000 files < 1 second (bulk)
- [ ] Single insert < 10ms
- [ ] Filename lookup < 1ms
- [ ] SHA1 lookup < 5ms

## Definition of Done

- [ ] SQL file created and committed
- [ ] Schema executes without errors
- [ ] All constraints and indexes verified
- [ ] Test script passes all validations
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Code review completed

## Notes for Implementation

### Design Decisions

**Why filename as primary key?**
- Filenames are unique in MediaWiki
- Natural primary key (meaningful identifier)
- Direct lookup by filename is most common query

**Why store dimensions separately?**
- Easy to query images by size
- NULL for non-images (PDFs, documents)
- No need to parse from content

**Why index SHA1?**
- Enables duplicate detection
- Supports file deduplication workflows
- Useful for integrity verification

**Why NOT foreign key to pages?**
- Files exist independently of pages
- Many files not linked from any page
- Pages can link to non-existent files

### Common Pitfalls

- **Forgetting NULL dimensions**: PDFs, text files have no width/height
- **Not validating dimensions**: Zero or negative dimensions are invalid
- **Wrong MIME types**: Must match actual file content
- **Not handling deleted uploaders**: Uploader can be NULL

### Storage Considerations

**File Metadata:**
- ~4,000 files
- ~500 bytes per row (average)
- Total metadata: ~2MB
- Negligible compared to actual files (100MB - 1GB)

**Actual File Storage:**
- Files stored on disk (not in database)
- Path determined by downloader (Epic 01 Story 08)
- Database only tracks metadata
- Coordinate filename between DB and filesystem

### Future Considerations

- May add `download_status` (pending, completed, failed)
- May add `local_path` to track file location on disk
- May add `thumbnail_path` for cached thumbnails
- May add `last_checked` for integrity verification
- Consider `deleted` flag for soft deletes

## References

- MediaWiki File Table: https://www.mediawiki.org/wiki/Manual:Image_table
- MediaWiki API:imageinfo: https://www.mediawiki.org/wiki/API:Imageinfo
- MIME Types: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types
- Epic 01 Models: `scraper/models/file.py`
