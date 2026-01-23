# Epic 02: Database & Storage

**Epic ID**: epic-02  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 1-2 weeks

## Overview

Design and implement the database schema and storage layer for complete wiki archival. Schema must be compatible with both SQLite (portable) and PostgreSQL (scalable), with support for full-text search and efficient queries.

## Goals

1. Design schema compatible with SQLite and PostgreSQL
2. Store pages with complete metadata
3. Store all revisions with full content and metadata
4. Store file metadata and organize downloaded files
5. Store internal link relationships
6. Support full-text search (SQLite FTS5)
7. Track scrape runs for incremental updates

## Success Criteria

- ✅ Schema works identically on SQLite and PostgreSQL
- ✅ Can store ~2,400 pages with metadata
- ✅ Can store ~86,500 revisions with full content
- ✅ Efficient queries (indexed fields, <100ms for common operations)
- ✅ Full-text search functional on page titles and content
- ✅ Referential integrity maintained (foreign keys)
- ✅ 80%+ test coverage on database operations

## User Stories

### Schema Design
- [Story 01: Pages Table Schema](story-01_pages_schema.md)
- [Story 02: Revisions Table Schema](story-02_revisions_schema.md)
- [Story 03: Files Table Schema](story-03_files_schema.md)
- [Story 04: Links Table Schema](story-04_links_schema.md)
- [Story 05: Scrape Metadata Schema](story-05_scrape_metadata_schema.md)

### Database Operations
- [Story 06: Database Initialization](story-06_db_initialization.md)
- [Story 07: Page CRUD Operations](story-07_page_operations.md)
- [Story 08: Revision CRUD Operations](story-08_revision_operations.md)
- [Story 09: File CRUD Operations](story-09_file_operations.md)
- [Story 10: Link Operations](story-10_link_operations.md)

### Query & Search
- [Story 11: Full-Text Search (FTS5)](story-11_fulltext_search.md)
- [Story 12: Timeline Queries](story-12_timeline_queries.md)
- [Story 13: Statistics Queries](story-13_statistics_queries.md)

### Data Models
- [Story 14: Python Data Models](story-14_data_models.md)
- [Story 15: Model Validation](story-15_model_validation.md)

## Dependencies

### Requires:
- None (foundational epic)

### Blocks:
- Epic 01: Core scraper (needs database for storage)
- Epic 03: Incremental updates (needs scrape metadata tables)
- Epic 05: Go SDK (needs schema for querying)

## Technical Notes

### SQLite/PostgreSQL Compatibility

**Use Compatible Types:**
- `INTEGER` - Works on both (not SERIAL or AUTOINCREMENT)
- `TEXT` - Works on both (not VARCHAR)
- `TIMESTAMP` - Works on both (not TIMESTAMPTZ)
- `BOOLEAN` - Works on both (SQLite stores as 0/1)

**Avoid:**
- ❌ `SERIAL` (PostgreSQL) / `AUTOINCREMENT` (SQLite)
- ❌ `VARCHAR(n)` - Use `TEXT` instead
- ❌ `JSONB` - Store JSON as TEXT, parse in app
- ❌ `ARRAY` types - Use separate tables for collections

### Database Schema Overview

```sql
-- Core tables
CREATE TABLE pages (...)
CREATE TABLE revisions (...)
CREATE TABLE files (...)
CREATE TABLE links (...)
CREATE TABLE namespaces (...)

-- Metadata tables
CREATE TABLE scrape_runs (...)
CREATE TABLE archive_info (...)

-- Indices for performance
CREATE INDEX idx_rev_page_time ON revisions(page_id, timestamp DESC);
CREATE INDEX idx_rev_timestamp ON revisions(timestamp);
CREATE INDEX idx_pages_title ON pages(title);

-- Full-text search (SQLite FTS5)
CREATE VIRTUAL TABLE pages_fts USING fts5(
    page_id UNINDEXED,
    title,
    content
);
```

### Storage Organization

```
data/
├── irowiki.db              # SQLite database
├── irowiki-classic.db      # Classic wiki (separate)
└── files/                  # Downloaded files
    ├── File/
    │   ├── A/              # Files starting with A
    │   ├── B/
    │   └── ...
    └── ...
```

### Data Volumes

- Pages: ~2,400 × ~500 bytes = ~1.2 MB
- Revisions: ~86,500 × ~5 KB avg = ~430 MB
- File metadata: ~4,000 × ~200 bytes = ~800 KB
- Links: ~50,000 × ~100 bytes = ~5 MB
- **Total database**: ~450 MB - 2 GB (with indices and FTS)
- **Files**: ~10-20 GB

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/database/sample_pages.json` - Test page data
- `fixtures/database/sample_revisions.json` - Test revision data
- `fixtures/database/sample_files.json` - Test file metadata
- `schema/test_schema.sql` - Test database schema

### Mocks Needed
- `tests/mocks/mock_database.py` - In-memory test database

### Test Utilities
- `tests/utils/db_helpers.py` - Database setup/teardown
- `tests/utils/db_assertions.py` - Database state assertions
- `tests/utils/schema_validator.py` - Validate schema compatibility

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |
| Story 14 | Not Started | - | - |
| Story 15 | Not Started | - | - |

## Definition of Done

- [ ] All 15 user stories completed
- [ ] Schema tested on both SQLite and PostgreSQL
- [ ] All CRUD operations working
- [ ] Full-text search functional
- [ ] Performance benchmarks met (<100ms for queries)
- [ ] All tests passing (80%+ coverage)
- [ ] Data models have type validation
- [ ] Documentation complete (schema diagrams, examples)
- [ ] Design document created and approved
- [ ] Code reviewed and merged
