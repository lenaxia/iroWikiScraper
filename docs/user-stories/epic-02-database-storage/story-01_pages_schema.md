# Story 01: Pages Table Schema

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-01  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **database developer**,  
I want **a SQL schema for the pages table**,  
So that **I can store page metadata with efficient indexing and query performance**.

## Description

Design and implement the SQL schema for the `pages` table, which stores metadata about wiki pages. This is the foundational table that all other tables reference via foreign keys. The schema must support efficient queries by title, namespace, and handle the ~2,400 pages from iRO Wiki.

The schema should be compatible with both SQLite (primary target) and PostgreSQL (future consideration), using standard SQL types and constraints.

## Background & Context

**What is the pages table?**
- Stores one row per wiki page
- Contains metadata but NOT content (content in revisions)
- Primary lookup by title and namespace
- Referenced by revisions, links, and other tables

**iRO Wiki Scale:**
- ~2,400 pages total
- Namespaces: 0 (Main), 2 (User), 4 (Project), 6 (File), 8 (MediaWiki), 10 (Template), 12 (Help), 14 (Category)
- Redirects must be tracked (is_redirect flag)
- Titles are unique within namespace

**Why This Story Matters:**
- Foundation for all database operations
- Proper indexing critical for query performance
- Unique constraints prevent duplicate entries
- Foreign key relationships ensure referential integrity

## Acceptance Criteria

### 1. Schema File Creation
- [ ] Create `schema/sqlite/001_pages.sql`
- [ ] File contains complete table definition
- [ ] Includes CREATE TABLE statement
- [ ] Includes all indexes
- [ ] Includes comments explaining purpose

### 2. Table Structure
- [ ] Column: `page_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- [ ] Column: `namespace` (INTEGER NOT NULL, default 0)
- [ ] Column: `title` (TEXT NOT NULL)
- [ ] Column: `is_redirect` (BOOLEAN DEFAULT FALSE)
- [ ] Column: `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- [ ] Column: `updated_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

### 3. Constraints
- [ ] Primary key on `page_id`
- [ ] Unique constraint on `(namespace, title)` combination
- [ ] NOT NULL constraints on required fields
- [ ] Check constraint: `namespace >= 0`

### 4. Indexes
- [ ] Index: `idx_pages_title` on `title` (for lookup by title)
- [ ] Index: `idx_pages_namespace` on `namespace` (for namespace filtering)
- [ ] Unique index automatically created by unique constraint

### 5. SQL Compatibility
- [ ] Valid SQLite SQL syntax
- [ ] Uses standard SQL types (portable to PostgreSQL)
- [ ] No SQLite-specific features that break portability
- [ ] Comments indicate any database-specific considerations

### 6. Performance
- [ ] Schema supports 2,400 pages without performance issues
- [ ] Insert/update operations < 10ms per page
- [ ] Lookup by title < 1ms (with index)
- [ ] Bulk inserts (1000 pages) < 1 second

### 7. Documentation
- [ ] Comments in SQL file explain each column
- [ ] Comments explain purpose of each index
- [ ] Comments note any design decisions

## Tasks

### Schema Design
- [ ] Design table structure with all required fields
- [ ] Identify primary key strategy (auto-increment vs UUID)
- [ ] Identify unique constraints
- [ ] Determine index requirements based on query patterns
- [ ] Document design decisions

### SQL File Creation
- [ ] Create `schema/sqlite/` directory
- [ ] Create `001_pages.sql` with CREATE TABLE statement
- [ ] Add column definitions with types and constraints
- [ ] Add unique constraint on (namespace, title)
- [ ] Add indexes for common queries
- [ ] Add inline comments

### Validation
- [ ] Validate SQL syntax with SQLite CLI
- [ ] Test schema creation: `sqlite3 test.db < schema/sqlite/001_pages.sql`
- [ ] Test insert operations
- [ ] Test unique constraint violations
- [ ] Test index usage with EXPLAIN QUERY PLAN
- [ ] Delete test database

### Documentation
- [ ] Add header comment with schema version
- [ ] Document each column's purpose
- [ ] Document index usage patterns
- [ ] Note any future migration considerations

## Technical Details

### File Structure
```
schema/
└── sqlite/
    └── 001_pages.sql
```

### Schema Implementation

```sql
-- schema/sqlite/001_pages.sql
-- Pages table: Stores wiki page metadata
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 12+

CREATE TABLE IF NOT EXISTS pages (
    -- Unique identifier for each page
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Namespace (0=Main, 2=User, 4=Project, 6=File, etc.)
    -- Standard MediaWiki namespace numbering
    namespace INTEGER NOT NULL DEFAULT 0,
    
    -- Page title (without namespace prefix)
    -- Example: "Prontera" not "Main:Prontera"
    title TEXT NOT NULL,
    
    -- Whether this page is a redirect to another page
    is_redirect BOOLEAN DEFAULT FALSE,
    
    -- Timestamp when page was first created in our database
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Timestamp when page metadata was last updated
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure titles are unique within each namespace
    UNIQUE(namespace, title),
    
    -- Namespace must be non-negative
    CHECK(namespace >= 0)
);

-- Index for fast lookup by title (case-sensitive)
-- Used by: page discovery, link resolution, search
CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title);

-- Index for filtering by namespace
-- Used by: namespace-specific queries, statistics
CREATE INDEX IF NOT EXISTS idx_pages_namespace ON pages(namespace);

-- Index for finding redirects
-- Used by: redirect resolution, cleanup operations
CREATE INDEX IF NOT EXISTS idx_pages_redirect ON pages(is_redirect) WHERE is_redirect = TRUE;
```

### Query Examples

```sql
-- Lookup page by title and namespace
SELECT page_id, title, is_redirect
FROM pages
WHERE namespace = 0 AND title = 'Prontera';

-- Get all pages in File namespace
SELECT page_id, title
FROM pages
WHERE namespace = 6
ORDER BY title;

-- Count pages by namespace
SELECT namespace, COUNT(*) as page_count
FROM pages
GROUP BY namespace;

-- Find all redirects
SELECT page_id, namespace, title
FROM pages
WHERE is_redirect = TRUE;
```

### Test Script

```bash
#!/bin/bash
# test_pages_schema.sh
# Validates pages schema

set -e

DB="test_pages.db"
SCHEMA="schema/sqlite/001_pages.sql"

# Clean up any existing test database
rm -f "$DB"

# Create schema
echo "Creating schema..."
sqlite3 "$DB" < "$SCHEMA"

# Test inserts
echo "Testing inserts..."
sqlite3 "$DB" <<EOF
INSERT INTO pages (namespace, title, is_redirect) VALUES (0, 'Prontera', FALSE);
INSERT INTO pages (namespace, title, is_redirect) VALUES (0, 'Geffen', FALSE);
INSERT INTO pages (namespace, title, is_redirect) VALUES (6, 'Example.png', FALSE);
INSERT INTO pages (namespace, title, is_redirect) VALUES (0, 'OldName', TRUE);
EOF

# Test unique constraint
echo "Testing unique constraint..."
if sqlite3 "$DB" "INSERT INTO pages (namespace, title) VALUES (0, 'Prontera');" 2>&1 | grep -q UNIQUE; then
    echo "✓ Unique constraint works"
else
    echo "✗ Unique constraint failed"
    exit 1
fi

# Test indexes exist
echo "Checking indexes..."
INDEX_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='pages';")
if [ "$INDEX_COUNT" -ge 3 ]; then
    echo "✓ Indexes created: $INDEX_COUNT"
else
    echo "✗ Expected at least 3 indexes, found $INDEX_COUNT"
    exit 1
fi

# Test query performance
echo "Testing query performance..."
sqlite3 "$DB" "EXPLAIN QUERY PLAN SELECT * FROM pages WHERE title = 'Prontera';"

# Clean up
rm -f "$DB"
echo "✓ All tests passed"
```

### Column Design Rationale

| Column | Type | Rationale |
|--------|------|-----------|
| page_id | INTEGER PK | Auto-incrementing ID, efficient foreign key target |
| namespace | INTEGER | MediaWiki standard, supports negative namespaces |
| title | TEXT | Unicode support for international characters |
| is_redirect | BOOLEAN | Fast filtering, minimal storage |
| created_at | TIMESTAMP | Audit trail, useful for incremental updates |
| updated_at | TIMESTAMP | Track last modification time |

### Index Strategy

**idx_pages_title**: Most common query pattern is lookup by title
**idx_pages_namespace**: Filtering/grouping by namespace is frequent
**idx_pages_redirect**: Partial index for redirect resolution (SQLite 3.8.0+)

### Migration Path

Future schema changes should:
1. Create new file: `002_pages_add_column.sql`
2. Use `ALTER TABLE` statements
3. Update `schema_version` table (Story 05)
4. Test migration on copy of production database

## Dependencies

### Requires
- SQLite 3.35+ (for RETURNING clause support in future stories)
- Directory: `schema/sqlite/` created

### Blocks
- Story 02: Revisions Table Schema (references pages.page_id)
- Story 04: Links Table Schema (references pages.page_id)
- Story 06: Database Initialization (loads this schema)
- Story 07: Page CRUD Operations (operates on this table)

## Testing Requirements

### Schema Validation Tests
- [ ] SQL file executes without errors
- [ ] All columns created with correct types
- [ ] Primary key constraint works
- [ ] Unique constraint enforced on (namespace, title)
- [ ] Check constraint validates namespace >= 0

### Index Tests
- [ ] Verify indexes created: `sqlite3 test.db ".indexes pages"`
- [ ] EXPLAIN QUERY PLAN confirms index usage
- [ ] Query by title uses idx_pages_title
- [ ] Query by namespace uses idx_pages_namespace

### Data Integrity Tests
- [ ] Insert valid page succeeds
- [ ] Insert duplicate (namespace, title) fails
- [ ] Insert negative namespace fails
- [ ] NULL title rejected
- [ ] Boolean values stored correctly

### Performance Tests
- [ ] Insert 2,400 pages < 1 second (bulk)
- [ ] Single insert < 10ms
- [ ] Title lookup < 1ms
- [ ] Namespace filter < 5ms

## Definition of Done

- [ ] SQL file created and committed
- [ ] Schema executes without errors in SQLite
- [ ] All constraints and indexes verified
- [ ] Test script passes all validations
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Code review completed
- [ ] Schema file committed to repository

## Notes for Implementation

### Design Decisions

**Why auto-increment page_id?**
- Simple and efficient for SQLite
- Predictable ordering by insertion
- Easier debugging (sequential IDs)

**Why NOT use MediaWiki's page_id?**
- We don't have access to it from API
- Our IDs are independent of source wiki
- Allows merging multiple wikis in future

**Why separate created_at and updated_at?**
- Track when page entered our database vs. last modified
- Useful for incremental scraping (Story 11)
- Audit trail for debugging

**Why index is_redirect?**
- Partial index only indexes TRUE values
- Minimal overhead (few redirects)
- Fast redirect resolution

### Common Pitfalls

- **Forgetting UNIQUE constraint**: Allows duplicate pages
- **Wrong namespace type**: Must be INTEGER not TEXT
- **Missing indexes**: Queries will be slow on large datasets
- **Not testing constraints**: Silent data corruption

### Future Considerations

- May add `last_scraped_at` timestamp for incremental updates
- May add `content_model` field (default 'wikitext')
- May add `language` field for multi-language wikis
- Consider adding `deleted` flag for soft deletes

## References

- MediaWiki Database Schema: https://www.mediawiki.org/wiki/Manual:Page_table
- SQLite Datatypes: https://www.sqlite.org/datatype3.html
- SQLite Indexes: https://www.sqlite.org/queryplanner.html
- Epic 01 Models: `scraper/models/page.py`
