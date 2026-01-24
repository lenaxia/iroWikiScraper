# Story 05: Scrape Metadata Schema

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-05  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **scraper operator**,  
I want **to track scrape runs and page status**,  
So that **I can resume interrupted scrapes, run incremental updates, and track schema versions**.

## Description

Design and implement SQL schemas for three metadata tracking tables:
1. `scrape_runs` - Track each scraping session
2. `scrape_page_status` - Track per-page scrape status
3. `schema_version` - Track database schema migrations

These tables enable resume capability, incremental updates, and schema evolution.

## Background & Context

**Why metadata tracking?**
- Scraping takes hours (2,400 pages × 36 revisions each)
- Network errors require resume capability
- Incremental updates need to know what changed
- Schema evolution requires migration tracking

**Use cases:**
- Resume interrupted scrape from last successful page
- Identify failed pages for retry
- Track when each page was last scraped
- Know which schema version is installed
- Support schema migrations in future

## Acceptance Criteria

### 1. Schema File Creation
- [ ] Create `schema/sqlite/005_scrape_metadata.sql`
- [ ] Contains all three table definitions
- [ ] Includes indexes for performance
- [ ] Includes comments

### 2. Scrape Runs Table
- [ ] Column: `run_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- [ ] Column: `start_time` (TIMESTAMP NOT NULL)
- [ ] Column: `end_time` (TIMESTAMP NULL)
- [ ] Column: `status` (TEXT NOT NULL)
- [ ] Column: `pages_scraped` (INTEGER DEFAULT 0)
- [ ] Column: `revisions_scraped` (INTEGER DEFAULT 0)
- [ ] Column: `files_downloaded` (INTEGER DEFAULT 0)
- [ ] Column: `error_message` (TEXT NULL)
- [ ] Check: `status IN ('running', 'completed', 'failed', 'interrupted')`

### 3. Scrape Page Status Table
- [ ] Column: `page_id` (INTEGER NOT NULL, foreign key)
- [ ] Column: `run_id` (INTEGER NOT NULL, foreign key)
- [ ] Column: `status` (TEXT NOT NULL)
- [ ] Column: `last_revision_id` (INTEGER NULL)
- [ ] Column: `error_message` (TEXT NULL)
- [ ] Column: `scraped_at` (TIMESTAMP NOT NULL)
- [ ] Primary key: `(page_id, run_id)`
- [ ] Check: `status IN ('pending', 'success', 'failed', 'skipped')`

### 4. Schema Version Table
- [ ] Column: `version` (INTEGER PRIMARY KEY)
- [ ] Column: `applied_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- [ ] Column: `description` (TEXT NOT NULL)

### 5. Performance
- [ ] Query recent scrape runs < 5ms
- [ ] Query failed pages < 10ms
- [ ] Insert page status (bulk) < 1s for 2,400 pages

## Technical Details

### Schema Implementation

```sql
-- schema/sqlite/005_scrape_metadata.sql
-- Metadata tables: Track scrape runs, page status, and schema versions
-- Version: 1.0

-- Track each scraping session
CREATE TABLE IF NOT EXISTS scrape_runs (
    -- Unique identifier for this scrape run
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- When scraping started
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- When scraping completed (NULL if still running)
    end_time TIMESTAMP,
    
    -- Status: 'running', 'completed', 'failed', 'interrupted'
    status TEXT NOT NULL DEFAULT 'running',
    
    -- Statistics
    pages_scraped INTEGER DEFAULT 0,
    revisions_scraped INTEGER DEFAULT 0,
    files_downloaded INTEGER DEFAULT 0,
    
    -- Error message if failed
    error_message TEXT,
    
    CHECK(status IN ('running', 'completed', 'failed', 'interrupted')),
    CHECK(pages_scraped >= 0),
    CHECK(revisions_scraped >= 0),
    CHECK(files_downloaded >= 0)
);

-- Track per-page scrape status
CREATE TABLE IF NOT EXISTS scrape_page_status (
    -- Page being scraped
    page_id INTEGER NOT NULL,
    
    -- Which scrape run
    run_id INTEGER NOT NULL,
    
    -- Status: 'pending', 'success', 'failed', 'skipped'
    status TEXT NOT NULL,
    
    -- Last revision ID scraped (NULL if none)
    last_revision_id INTEGER,
    
    -- Error message if failed
    error_message TEXT,
    
    -- When this page was scraped
    scraped_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (page_id, run_id),
    FOREIGN KEY (page_id) REFERENCES pages(page_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE CASCADE,
    
    CHECK(status IN ('pending', 'success', 'failed', 'skipped'))
);

-- Track schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    -- Schema version number (sequential)
    version INTEGER PRIMARY KEY,
    
    -- When this version was applied
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Description of changes
    description TEXT NOT NULL
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial schema: pages, revisions, files, links, scrape metadata');

-- Indexes for scrape_runs
CREATE INDEX IF NOT EXISTS idx_runs_status ON scrape_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_start_time ON scrape_runs(start_time DESC);

-- Indexes for scrape_page_status
CREATE INDEX IF NOT EXISTS idx_page_status_run ON scrape_page_status(run_id);
CREATE INDEX IF NOT EXISTS idx_page_status_status ON scrape_page_status(status);
```

### Query Examples

```sql
-- Get most recent scrape run
SELECT *
FROM scrape_runs
ORDER BY start_time DESC
LIMIT 1;

-- Get failed pages from last run
SELECT sps.page_id, p.title, sps.error_message
FROM scrape_page_status sps
JOIN pages p ON sps.page_id = p.page_id
WHERE sps.run_id = (SELECT MAX(run_id) FROM scrape_runs)
  AND sps.status = 'failed'
ORDER BY p.title;

-- Resume: get pages not yet scraped in current run
SELECT p.page_id, p.title
FROM pages p
LEFT JOIN scrape_page_status sps ON p.page_id = sps.page_id 
  AND sps.run_id = ?
WHERE sps.page_id IS NULL
ORDER BY p.page_id;

-- Statistics for a run
SELECT 
    status,
    COUNT(*) as count
FROM scrape_page_status
WHERE run_id = ?
GROUP BY status;

-- Check current schema version
SELECT MAX(version) as current_version
FROM schema_version;

-- Get schema migration history
SELECT version, applied_at, description
FROM schema_version
ORDER BY version;
```

## Dependencies

### Requires
- Story 01: Pages Table Schema

### Blocks
- Story 06: Database Initialization
- Epic 03: Incremental Updates (uses this for tracking)

## Testing Requirements

- [ ] Create scrape run record
- [ ] Update run status and statistics
- [ ] Record page status for multiple pages
- [ ] Query failed pages efficiently
- [ ] Resume queries work correctly
- [ ] Schema version tracking works

## Definition of Done

- [ ] SQL file created
- [ ] All tables and indexes created
- [ ] Test script passes
- [ ] Code review completed

## Notes

**Resume workflow:**
1. Start scrape → create run record (status='running')
2. For each page → record page_status
3. If interrupted → status='interrupted'
4. Resume → query pages without status in current run
5. Complete → update status='completed'

**Incremental update workflow (Epic 03):**
1. Query last_revision_id per page
2. Fetch only newer revisions from API
3. Update last_revision_id

**Future considerations:**
- Add `scrape_type` (full, incremental, selective)
- Add `config_snapshot` (JSON of scrape parameters)
- Add per-run performance metrics
