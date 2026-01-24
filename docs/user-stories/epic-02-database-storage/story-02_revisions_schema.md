# Story 02: Revisions Table Schema

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-02  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **database developer**,  
I want **a SQL schema for the revisions table**,  
So that **I can store complete edit history with efficient temporal indexing and per-page queries**.

## Description

Design and implement the SQL schema for the `revisions` table, which stores the complete edit history of all wiki pages. Each revision represents a snapshot of a page at a specific point in time. The schema must support ~86,500 revisions with efficient temporal queries and per-page history lookups.

This is the largest table in the database by both row count and data volume (content field can be ~10KB per revision).

## Background & Context

**What is the revisions table?**
- Stores complete edit history for all pages
- Each row is one edit/revision
- Contains: metadata (timestamp, user, comment) + full content
- Parent-child relationships form revision chain
- Multiple revisions per page (avg ~36 per page)

**iRO Wiki Scale:**
- ~86,500 total revisions
- ~2,400 pages = avg 36 revisions per page
- Content size: ~10KB average per revision
- Total data volume: ~865MB of content
- Date range: 2005-2024 (19 years of history)

**Why This Story Matters:**
- Enables historical page reconstruction
- Foundation for timeline queries (Story 12)
- Critical for incremental scraping (Epic 03)
- Performance directly impacts user experience

## Acceptance Criteria

### 1. Schema File Creation
- [ ] Create `schema/sqlite/002_revisions.sql`
- [ ] File contains complete table definition
- [ ] Includes all indexes for query optimization
- [ ] Includes foreign key constraints
- [ ] Includes comments explaining fields

### 2. Table Structure
- [ ] Column: `revision_id` (INTEGER PRIMARY KEY)
- [ ] Column: `page_id` (INTEGER NOT NULL, foreign key to pages)
- [ ] Column: `parent_id` (INTEGER NULL, self-reference)
- [ ] Column: `timestamp` (TIMESTAMP NOT NULL)
- [ ] Column: `user` (TEXT, nullable for anonymous/deleted)
- [ ] Column: `user_id` (INTEGER NULL)
- [ ] Column: `comment` (TEXT NULL)
- [ ] Column: `content` (TEXT NOT NULL)
- [ ] Column: `size` (INTEGER NOT NULL, content byte size)
- [ ] Column: `sha1` (TEXT NOT NULL, content hash)
- [ ] Column: `minor` (BOOLEAN DEFAULT FALSE)
- [ ] Column: `tags` (TEXT NULL, JSON array)

### 3. Constraints
- [ ] Primary key on `revision_id`
- [ ] Foreign key: `page_id` → `pages(page_id)` with CASCADE
- [ ] NOT NULL on required fields (revision_id, page_id, timestamp, content, size, sha1)
- [ ] Check constraint: `size >= 0`

### 4. Indexes
- [ ] Composite index: `idx_rev_page_time` on `(page_id, timestamp DESC)` for page history
- [ ] Index: `idx_rev_timestamp` on `timestamp` for temporal queries
- [ ] Index: `idx_rev_parent` on `parent_id` for chain traversal
- [ ] Index: `idx_rev_sha1` on `sha1` for duplicate detection

### 5. SQL Compatibility
- [ ] Valid SQLite SQL syntax
- [ ] Uses standard SQL types
- [ ] Foreign key enforcement enabled
- [ ] Comments for any database-specific features

### 6. Performance
- [ ] Supports 86,500 revisions efficiently
- [ ] Per-page history query < 10ms (using composite index)
- [ ] Temporal range query < 50ms
- [ ] Bulk inserts (10,000 revisions) < 5 seconds

## Tasks

### Schema Design
- [ ] Design table structure with all revision fields
- [ ] Map MediaWiki API fields to database columns
- [ ] Plan index strategy for temporal and per-page queries
- [ ] Determine foreign key cascade behavior
- [ ] Document field nullability requirements

### SQL File Creation
- [ ] Create `002_revisions.sql` with CREATE TABLE statement
- [ ] Add all column definitions with appropriate types
- [ ] Add foreign key constraint to pages table
- [ ] Add self-referencing parent_id constraint
- [ ] Add composite index for page history
- [ ] Add temporal index for time-based queries
- [ ] Add inline comments for each field

### Validation
- [ ] Test schema creation in SQLite
- [ ] Test foreign key enforcement
- [ ] Test insert operations with realistic data
- [ ] Verify index usage with EXPLAIN QUERY PLAN
- [ ] Test NULL handling for optional fields
- [ ] Test JSON storage in tags field

### Documentation
- [ ] Document each column's purpose and source
- [ ] Explain index choices and query patterns
- [ ] Document tags JSON format
- [ ] Note content storage considerations

## Technical Details

### File Structure
```
schema/
└── sqlite/
    ├── 001_pages.sql
    └── 002_revisions.sql
```

### Schema Implementation

```sql
-- schema/sqlite/002_revisions.sql
-- Revisions table: Stores complete edit history for all pages
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 12+

CREATE TABLE IF NOT EXISTS revisions (
    -- MediaWiki revision ID (globally unique)
    revision_id INTEGER PRIMARY KEY,
    
    -- Foreign key to pages table
    -- CASCADE: if page deleted, all revisions deleted
    page_id INTEGER NOT NULL,
    
    -- Parent revision ID (forms chain)
    -- NULL for first revision of page
    parent_id INTEGER NULL,
    
    -- When this edit was made (UTC)
    timestamp TIMESTAMP NOT NULL,
    
    -- Username (NULL for deleted/suppressed users)
    user TEXT,
    
    -- User ID from MediaWiki (NULL for anonymous edits)
    user_id INTEGER,
    
    -- Edit summary/comment (NULL if no comment provided)
    comment TEXT,
    
    -- Full wikitext content at this revision
    -- Can be large (~10KB average, max ~1MB)
    content TEXT NOT NULL,
    
    -- Content size in bytes
    size INTEGER NOT NULL,
    
    -- SHA1 hash of content (for duplicate detection)
    sha1 TEXT NOT NULL,
    
    -- Whether edit was marked as minor
    minor BOOLEAN DEFAULT FALSE,
    
    -- Edit tags as JSON array: ["visual edit", "mobile edit"]
    -- NULL if no tags
    tags TEXT,
    
    -- Foreign key constraints
    FOREIGN KEY (page_id) REFERENCES pages(page_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES revisions(revision_id) ON DELETE SET NULL,
    
    -- Validation constraints
    CHECK(size >= 0)
);

-- Composite index for per-page history queries (most common)
-- Ordered by timestamp DESC for "latest first" queries
-- Used by: get_revisions_by_page(), get_latest_revision()
CREATE INDEX IF NOT EXISTS idx_rev_page_time 
ON revisions(page_id, timestamp DESC);

-- Index for temporal queries across all pages
-- Used by: get_revisions_in_range(), timeline queries
CREATE INDEX IF NOT EXISTS idx_rev_timestamp 
ON revisions(timestamp);

-- Index for traversing revision chains
-- Used by: parent-child relationship queries
CREATE INDEX IF NOT EXISTS idx_rev_parent 
ON revisions(parent_id) WHERE parent_id IS NOT NULL;

-- Index for duplicate content detection
-- Used by: finding identical revisions, deduplication
CREATE INDEX IF NOT EXISTS idx_rev_sha1 
ON revisions(sha1);

-- Index for user contribution queries
-- Used by: contributor statistics, user activity
CREATE INDEX IF NOT EXISTS idx_rev_user
ON revisions(user_id) WHERE user_id IS NOT NULL;
```

### Query Examples

```sql
-- Get revision history for a page (most recent first)
SELECT revision_id, timestamp, user, comment, size
FROM revisions
WHERE page_id = 123
ORDER BY timestamp DESC
LIMIT 50;

-- Get latest revision for a page
SELECT *
FROM revisions
WHERE page_id = 123
ORDER BY timestamp DESC
LIMIT 1;

-- Get page state at specific time
SELECT *
FROM revisions
WHERE page_id = 123 AND timestamp <= '2024-01-15 12:00:00'
ORDER BY timestamp DESC
LIMIT 1;

-- Get all edits in date range
SELECT r.revision_id, p.title, r.timestamp, r.user
FROM revisions r
JOIN pages p ON r.page_id = p.page_id
WHERE r.timestamp BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY r.timestamp;

-- Find revisions with specific tag
SELECT revision_id, page_id, timestamp
FROM revisions
WHERE tags LIKE '%"visual edit"%'
ORDER BY timestamp DESC;

-- Get contributor statistics
SELECT user, COUNT(*) as edit_count, SUM(size) as total_bytes
FROM revisions
WHERE user IS NOT NULL
GROUP BY user
ORDER BY edit_count DESC
LIMIT 10;
```

### Test Script

```bash
#!/bin/bash
# test_revisions_schema.sh
# Validates revisions schema

set -e

DB="test_revisions.db"
SCHEMA_DIR="schema/sqlite"

rm -f "$DB"

# Create both schemas (revisions depends on pages)
echo "Creating schemas..."
sqlite3 "$DB" < "$SCHEMA_DIR/001_pages.sql"
sqlite3 "$DB" < "$SCHEMA_DIR/002_revisions.sql"

# Enable foreign key enforcement
sqlite3 "$DB" "PRAGMA foreign_keys = ON;"

# Test inserts
echo "Testing inserts..."
sqlite3 "$DB" <<EOF
-- Insert test page
INSERT INTO pages (page_id, namespace, title) VALUES (1, 0, 'TestPage');

-- Insert revisions
INSERT INTO revisions (revision_id, page_id, timestamp, user, content, size, sha1) 
VALUES (100, 1, '2024-01-01 10:00:00', 'Alice', 'First revision', 14, 'abc123');

INSERT INTO revisions (revision_id, page_id, parent_id, timestamp, user, content, size, sha1, minor) 
VALUES (101, 1, 100, '2024-01-02 11:00:00', 'Bob', 'Second revision', 15, 'def456', TRUE);

-- Insert with NULL user (deleted/anonymous)
INSERT INTO revisions (revision_id, page_id, parent_id, timestamp, content, size, sha1) 
VALUES (102, 1, 101, '2024-01-03 12:00:00', 'Third revision', 14, 'ghi789');

-- Insert with tags
INSERT INTO revisions (revision_id, page_id, parent_id, timestamp, user, content, size, sha1, tags) 
VALUES (103, 1, 102, '2024-01-04 13:00:00', 'Charlie', 'Fourth revision', 15, 'jkl012', '["visual edit", "mobile edit"]');
EOF

# Test foreign key constraint
echo "Testing foreign key constraint..."
if sqlite3 "$DB" "PRAGMA foreign_keys = ON; INSERT INTO revisions (revision_id, page_id, timestamp, content, size, sha1) VALUES (200, 999, '2024-01-01', 'test', 4, 'abc');" 2>&1 | grep -q "FOREIGN KEY"; then
    echo "✓ Foreign key constraint works"
else
    echo "✗ Foreign key constraint failed"
    exit 1
fi

# Test indexes
echo "Checking indexes..."
INDEX_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='revisions';")
if [ "$INDEX_COUNT" -ge 5 ]; then
    echo "✓ Indexes created: $INDEX_COUNT"
else
    echo "✗ Expected at least 5 indexes, found $INDEX_COUNT"
    exit 1
fi

# Test composite index usage
echo "Testing composite index usage..."
sqlite3 "$DB" "EXPLAIN QUERY PLAN SELECT * FROM revisions WHERE page_id = 1 ORDER BY timestamp DESC;"

# Test cascade delete
echo "Testing cascade delete..."
sqlite3 "$DB" "PRAGMA foreign_keys = ON; DELETE FROM pages WHERE page_id = 1;"
COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM revisions WHERE page_id = 1;")
if [ "$COUNT" -eq 0 ]; then
    echo "✓ Cascade delete works"
else
    echo "✗ Cascade delete failed, found $COUNT revisions"
    exit 1
fi

rm -f "$DB"
echo "✓ All tests passed"
```

### Field Mapping from MediaWiki API

| API Field | DB Column | Notes |
|-----------|-----------|-------|
| revid | revision_id | Primary key |
| pageid | page_id | Foreign key |
| parentid | parent_id | Self-reference |
| timestamp | timestamp | ISO 8601 → SQLite TIMESTAMP |
| user | user | Can be NULL |
| userid | user_id | Can be NULL (anonymous) |
| comment | comment | Can be NULL (no comment) |
| * (content) | content | Full wikitext |
| size | size | Bytes |
| sha1 | sha1 | Content hash |
| minor | minor | Boolean flag |
| tags | tags | Array → JSON TEXT |

## Dependencies

### Requires
- Story 01: Pages Table Schema (foreign key dependency)
- SQLite 3.35+
- Foreign key enforcement enabled

### Blocks
- Story 06: Database Initialization
- Story 08: Revision CRUD Operations
- Story 11: Full-Text Search (indexes revision content)
- Story 12: Timeline Queries
- Epic 03: Incremental Updates

## Testing Requirements

### Schema Validation Tests
- [ ] SQL file executes without errors
- [ ] All columns created with correct types
- [ ] Foreign key to pages enforced
- [ ] Self-referencing parent_id works
- [ ] Check constraint validates size >= 0

### Index Tests
- [ ] Verify all 5 indexes created
- [ ] Composite index used for page history queries
- [ ] Timestamp index used for temporal queries
- [ ] Parent index used for chain traversal
- [ ] SHA1 index used for duplicate detection

### Data Integrity Tests
- [ ] Cannot insert revision with invalid page_id
- [ ] Can insert revision with NULL parent_id (first revision)
- [ ] Can insert revision with NULL user/user_id
- [ ] Can insert revision with NULL comment
- [ ] Tags stored as valid JSON string
- [ ] Cascade delete removes revisions when page deleted

### Performance Tests
- [ ] Insert 10,000 revisions < 5 seconds (bulk)
- [ ] Single insert < 10ms
- [ ] Page history query (50 revisions) < 10ms
- [ ] Temporal range query < 50ms
- [ ] Latest revision query < 5ms

## Definition of Done

- [ ] SQL file created and committed
- [ ] Schema executes without errors
- [ ] All constraints and indexes verified
- [ ] Test script passes all validations
- [ ] Foreign key enforcement tested
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Code review completed

## Notes for Implementation

### Design Decisions

**Why store full content in each revision?**
- Enables point-in-time reconstruction
- No need to apply diffs (simpler, faster)
- Disk space is cheap (865MB is acceptable)
- Easier to query and export

**Why composite index (page_id, timestamp)?**
- Most common query: "get history for page X"
- Ordering by timestamp DESC is natural for history
- Single index serves both filter and sort

**Why store tags as JSON TEXT?**
- SQLite doesn't have native array type
- JSON is queryable with LIKE or json_extract()
- Preserves tag order from API
- Easy to parse in application code

**Why NOT use MediaWiki's revision_id as autoincrement?**
- We get revision_id from API (not generated)
- Must preserve original IDs for incremental updates
- Allows linking back to source wiki

### Common Pitfalls

- **Forgetting foreign keys**: Data integrity violations
- **Not enabling foreign key enforcement**: Constraints not checked
- **Wrong index order**: Composite index must be (page_id, timestamp) not (timestamp, page_id)
- **Storing arrays as comma-separated**: Use JSON for structured data
- **Not handling NULL users**: Anonymous/deleted editors have no username

### Storage Considerations

**Content Size:**
- Average: ~10KB per revision
- 86,500 revisions × 10KB = ~865MB
- Largest revisions: ~1MB
- SQLite handles this fine (max DB size: 281TB)

**Index Size:**
- Composite index: ~10MB (page_id + timestamp for 86,500 rows)
- All indexes combined: ~30MB
- Total DB size: ~900MB (content + indexes + overhead)

### Future Considerations

- May add `content_model` field (default 'wikitext')
- May add `deleted` flag for revision suppression
- May compress content with zlib (save ~70% space)
- Consider separate table for revision content (normalize)
- May add full-text search index on content (Story 11)

## References

- MediaWiki Revision Table: https://www.mediawiki.org/wiki/Manual:Revision_table
- SQLite Foreign Keys: https://www.sqlite.org/foreignkeys.html
- SQLite JSON Functions: https://www.sqlite.org/json1.html
- Epic 01 Models: `scraper/models/revision.py`
