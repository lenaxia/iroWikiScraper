# Database Schema

This directory contains SQL schema definitions for the iRO Wiki Scraper database.

## Overview

The database schema consists of 5 core tables organized into numbered migration files:

1. **001_pages.sql** - Wiki page metadata (Story 01)
2. **002_revisions.sql** - Complete edit history (Story 02)
3. **003_files.sql** - File metadata (Story 03)
4. **004_links.sql** - Page relationships (Story 04)
5. **005_scrape_metadata.sql** - Scraping operational metadata (Story 05)

## Compatibility Requirements

All schemas are designed to be **portable between SQLite and PostgreSQL**:

### Type Conventions

- **IDs**: `INTEGER` (not SERIAL or AUTOINCREMENT keywords in column definition)
- **Strings**: `TEXT` (not VARCHAR)
- **Dates**: `TIMESTAMP` (not TIMESTAMPTZ)
- **Flags**: `BOOLEAN` (SQLite stores as 0/1, PostgreSQL has native type)
- **JSON data**: Stored as `TEXT` (no JSON or JSONB column types)
- **Arrays**: Not used (stored as JSON-formatted TEXT strings)

### Design Principles

1. **Standard SQL only** - No database-specific functions in schema
2. **Explicit constraints** - All validation in CHECK and FOREIGN KEY constraints
3. **Descriptive names** - Clear, self-documenting table and column names
4. **Comprehensive comments** - Every table, column, index, and constraint documented
5. **Performance-first indexing** - Indexes aligned with expected query patterns

## Database Structure

### Entity Relationships

```
pages (2,400 rows)
  ├── revisions (86,500 rows) - FK: page_id → pages.page_id
  │   └── revisions (self) - FK: parent_id → revisions.revision_id
  ├── links (50,000 rows) - FK: source_page_id → pages.page_id
  └── scrape_page_status - FK: page_id → pages.page_id

files (4,000 rows) - Independent table (no FK to pages)

scrape_runs
  └── scrape_page_status - FK: run_id → scrape_runs.run_id

schema_version - Version tracking table
```

## Table Details

### 001_pages.sql

**Purpose**: Store wiki page metadata

**Key Features**:
- Primary key on `page_id` (INTEGER)
- Unique constraint on `(namespace, title)`
- Check constraint: `namespace >= 0`
- Indexes: title, namespace, is_redirect

**Typical Queries**:
- Lookup page by title and namespace
- List all pages in namespace
- Find redirect pages

**Scale**: ~2,400 pages

---

### 002_revisions.sql

**Purpose**: Store complete edit history for all pages

**Key Features**:
- Primary key on `revision_id` (from MediaWiki API)
- Foreign keys: `page_id → pages`, `parent_id → revisions` (self)
- Stores full content per revision (not diffs)
- Tags stored as JSON-formatted TEXT
- Composite index on `(page_id, timestamp DESC)` for history queries

**Typical Queries**:
- Get revision history for page
- Get latest revision for page
- Get page state at specific time
- Temporal queries across all pages

**Scale**: ~86,500 revisions (~865MB content)

---

### 003_files.sql

**Purpose**: Store metadata for uploaded files (images, documents, etc.)

**Key Features**:
- Primary key on `filename` (natural key)
- `width`/`height` nullable for non-image files
- `sha1` hash for duplicate detection
- Check constraints: size ≥ 0, width > 0 if not NULL, height > 0 if not NULL
- Indexes: sha1, timestamp, mime_type, uploader

**Typical Queries**:
- Get file metadata by filename
- Find duplicate files by SHA1
- List recent uploads
- Filter by MIME type

**Scale**: ~4,000 files (~2MB metadata, files stored separately on disk)

**Note**: This table stores metadata only. Actual file content is stored on the filesystem.

---

### 004_links.sql

**Purpose**: Store page relationships (wikilinks, templates, categories)

**Key Features**:
- Composite unique key on `(source_page_id, target_title, link_type)`
- Foreign key: `source_page_id → pages`
- Check constraint: `link_type IN ('wikilink', 'template', 'category')`
- Stores `target_title` (not `target_page_id`) because target may not exist yet
- Indexes: source, target, type, composite (type, target)

**Link Types**:
- `wikilink`: Standard page-to-page links `[[Target]]`
- `template`: Template inclusions `{{Template}}`
- `category`: Category memberships `[[Category:Name]]`

**Typical Queries**:
- Get all links from page (outbound)
- Get all links to page (backlinks)
- List pages in category
- Find pages using template

**Scale**: ~50,000 links (40K wikilinks, 8K templates, 2K categories)

---

### 005_scrape_metadata.sql

**Purpose**: Track scraping operations and schema versions

**Contains Three Tables**:

1. **scrape_runs** - Track each scraping session
   - Status: running, completed, failed, interrupted
   - Statistics: pages_scraped, revisions_scraped, files_downloaded
   - Enables monitoring and progress tracking

2. **scrape_page_status** - Per-page status within each run
   - Status: pending, success, failed, skipped
   - Stores `last_revision_id` for incremental updates
   - Enables resume capability after interruption

3. **schema_version** - Database schema migration tracking
   - Sequential version numbers
   - Applied timestamps
   - Migration descriptions
   - Initial version (1) automatically inserted

**Typical Queries**:
- Get most recent scrape run
- Find failed pages for retry
- Resume interrupted scrape
- Check current schema version

**Scale**: Grows with each scrape run

## Usage

### Creating a New Database

```bash
# Create SQLite database with all schemas
cd /path/to/project
sqlite3 wiki.db < schema/sqlite/001_pages.sql
sqlite3 wiki.db < schema/sqlite/002_revisions.sql
sqlite3 wiki.db < schema/sqlite/003_files.sql
sqlite3 wiki.db < schema/sqlite/004_links.sql
sqlite3 wiki.db < schema/sqlite/005_scrape_metadata.sql

# Enable foreign key enforcement (important!)
sqlite3 wiki.db "PRAGMA foreign_keys = ON;"
```

### Testing Schemas

```bash
# Run all schema tests
pytest tests/storage/test_schema.py -v

# Test specific schema
pytest tests/storage/test_schema.py::test_pages_table_creation -v
```

### Verifying Installation

```sql
-- Check all tables exist
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;

-- Check current schema version
SELECT version, applied_at, description FROM schema_version;

-- Check indexes for a table
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pages';

-- Verify foreign key enforcement is enabled
PRAGMA foreign_keys;
```

## Schema Evolution

### Migration Strategy

When schema changes are needed:

1. **Create new migration file**: `006_description.sql`
2. **Use ALTER TABLE**: Modify existing structures
3. **Update schema_version**: Insert new version record
4. **Test migration**: Run on copy of production database
5. **Update tests**: Add tests for new schema features
6. **Document changes**: Update this README

### Example Migration

```sql
-- schema/sqlite/006_add_page_language.sql
-- Add language field to pages table

ALTER TABLE pages ADD COLUMN language TEXT DEFAULT 'en';

CREATE INDEX IF NOT EXISTS idx_pages_language ON pages(language);

INSERT INTO schema_version (version, description)
VALUES (2, 'Added language field to pages table');
```

## Performance Considerations

### Index Usage

All indexes are carefully designed for common query patterns:

- **Composite indexes**: Used when filtering and sorting together
- **Partial indexes**: Used when indexing sparse data (e.g., redirects, non-NULL users)
- **Covering indexes**: Future optimization for frequently-accessed columns

### Query Optimization Tips

```sql
-- ✓ GOOD: Uses idx_rev_page_time composite index
SELECT * FROM revisions 
WHERE page_id = 123 
ORDER BY timestamp DESC;

-- ✗ BAD: Cannot use composite index efficiently (wrong column order)
SELECT * FROM revisions 
WHERE timestamp > '2024-01-01' 
ORDER BY page_id;

-- ✓ GOOD: Uses idx_links_type_target composite index
SELECT * FROM links 
WHERE link_type = 'category' AND target_title = 'Cities';

-- Check index usage
EXPLAIN QUERY PLAN SELECT ...;
```

### Scale Expectations

| Table | Rows | Size | Indexes |
|-------|------|------|---------|
| pages | 2,400 | <1MB | 3 |
| revisions | 86,500 | ~865MB | 5 |
| files | 4,000 | ~2MB | 4 |
| links | 50,000 | ~5MB | 4 |
| scrape_runs | ~10 | <1MB | 2 |
| scrape_page_status | ~24,000 | ~2MB | 2 |
| schema_version | ~5 | <1KB | 0 |
| **Total** | **~163,000** | **~875MB** | **20** |

## Future Enhancements

Potential schema additions for future stories:

- **Full-text search**: Add FTS5 virtual table for content search
- **Page history snapshots**: Optimize common time-based queries
- **Category tree**: Materialized path for category hierarchy
- **User table**: Normalize contributor information
- **File downloads**: Track download status and local paths
- **Incremental updates**: Track last_modified per table/page

## References

- **MediaWiki Database Schema**: https://www.mediawiki.org/wiki/Manual:Database_layout
- **SQLite Datatypes**: https://www.sqlite.org/datatype3.html
- **SQLite Foreign Keys**: https://www.sqlite.org/foreignkeys.html
- **SQLite Query Planner**: https://www.sqlite.org/queryplanner.html
- **PostgreSQL Compatibility**: Ensure schemas work on both databases

## Support

For issues or questions about the schema:

1. Check test file: `tests/storage/test_schema.py`
2. Review story files: `docs/user-stories/epic-02-database-storage/story-0[1-5]_*.md`
3. Examine SQL comments: Each schema file has detailed inline documentation
4. Run `EXPLAIN QUERY PLAN` to understand query performance

---

**Schema Version**: 1  
**Last Updated**: 2026-01-23  
**Compatible**: SQLite 3.35+, PostgreSQL 13+  
**Status**: Production Ready
