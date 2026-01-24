-- schema/sqlite/005_scrape_metadata.sql
-- Metadata tables: Track scrape runs, page status, and schema versions
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 13+
--
-- Design Notes:
-- - Three tables for operational metadata
-- - scrape_runs: Track each scraping session (full or incremental)
-- - scrape_page_status: Per-page status within each run (for resume capability)
-- - schema_version: Track database schema migrations
-- - Enables resume after interruption and incremental updates

-- ============================================================================
-- Table: scrape_runs
-- Track each scraping session with statistics and status
-- ============================================================================

CREATE TABLE IF NOT EXISTS scrape_runs (
    -- Unique identifier for this scrape run
    -- INTEGER PRIMARY KEY provides auto-increment
    -- Sequential IDs make it easy to identify runs chronologically
    run_id INTEGER PRIMARY KEY,
    
    -- When scraping started (UTC)
    -- Automatically set to current time when run created
    -- Used for identifying recent runs and calculating duration
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- When scraping completed (UTC)
    -- NULL while scrape is still running
    -- Set when run reaches terminal state (completed/failed/interrupted)
    end_time TIMESTAMP,
    
    -- Current status of scrape run
    -- 'running': Scrape in progress
    -- 'completed': Successfully finished
    -- 'failed': Terminated due to error
    -- 'interrupted': Stopped by user or system (can resume)
    -- Default 'running' when run created
    status TEXT NOT NULL DEFAULT 'running',
    
    -- Number of pages successfully scraped in this run
    -- Incremented as each page completes
    -- Used for progress tracking and statistics
    pages_scraped INTEGER DEFAULT 0,
    
    -- Number of revisions successfully scraped in this run
    -- Sum across all pages
    -- Used for statistics and estimating completion time
    revisions_scraped INTEGER DEFAULT 0,
    
    -- Number of files successfully downloaded in this run
    -- Tracks file download progress separately from pages
    -- Used for storage planning and statistics
    files_downloaded INTEGER DEFAULT 0,
    
    -- Error message if run failed
    -- NULL for successful runs
    -- Contains exception message or error description
    -- Used for debugging and error reporting
    error_message TEXT,
    
    -- Validation constraints
    -- Status must be one of four allowed values
    CHECK(status IN ('running', 'completed', 'failed', 'interrupted')),
    -- Statistics cannot be negative
    CHECK(pages_scraped >= 0),
    CHECK(revisions_scraped >= 0),
    CHECK(files_downloaded >= 0)
);

-- ============================================================================
-- Table: scrape_page_status  
-- Track per-page status within each scrape run (enables resume)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scrape_page_status (
    -- Page being scraped
    -- Foreign key to pages table
    -- Identifies which page this status record is for
    page_id INTEGER NOT NULL,
    
    -- Which scrape run this status belongs to
    -- Foreign key to scrape_runs table
    -- Allows multiple status records per page (one per run)
    run_id INTEGER NOT NULL,
    
    -- Status of this page in this run
    -- 'pending': Not yet scraped (initial state)
    -- 'success': Successfully scraped all revisions
    -- 'failed': Error occurred during scraping
    -- 'skipped': Intentionally skipped (e.g., already up-to-date)
    status TEXT NOT NULL,
    
    -- Last revision ID successfully scraped for this page
    -- NULL if no revisions scraped yet
    -- Used for incremental updates (fetch only newer revisions)
    -- Also useful for resume (know where to continue)
    last_revision_id INTEGER,
    
    -- Error message if page scraping failed
    -- NULL for successful pages
    -- Contains exception message or API error
    -- Used for debugging and retry logic
    error_message TEXT,
    
    -- When this page was scraped (UTC)
    -- Automatically set to current time
    -- Used for incremental update decisions
    scraped_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite primary key
    -- One status record per (page, run) combination
    -- Allows querying status across different runs
    PRIMARY KEY (page_id, run_id),
    
    -- Foreign key constraints
    -- CASCADE: if page deleted, remove all its status records
    -- CASCADE: if run deleted, remove all page statuses for that run
    FOREIGN KEY (page_id) 
        REFERENCES pages(page_id) 
        ON DELETE CASCADE,
    FOREIGN KEY (run_id) 
        REFERENCES scrape_runs(run_id) 
        ON DELETE CASCADE,
    
    -- Validate status is one of four allowed values
    CHECK(status IN ('pending', 'success', 'failed', 'skipped'))
);

-- ============================================================================
-- Table: schema_version
-- Track database schema migrations for version management
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    -- Schema version number (sequential)
    -- Primary key ensures unique version numbers
    -- Starts at 1 for initial schema
    -- Incremented with each migration
    version INTEGER PRIMARY KEY,
    
    -- When this schema version was applied (UTC)
    -- Automatically set to current time
    -- Used for audit trail and troubleshooting
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Description of changes in this version
    -- Human-readable summary of what changed
    -- Example: "Added full-text search index on revisions.content"
    -- Used for documentation and migration planning
    description TEXT NOT NULL
);

-- Insert initial schema version record
-- Version 1: Initial schema with all base tables
-- OR IGNORE prevents duplicate insertion if already exists
-- This establishes baseline for future migrations
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial schema: pages, revisions, files, links, scrape_metadata');

-- ============================================================================
-- Indexes for scrape_runs
-- ============================================================================

-- Index for filtering runs by status
-- Used by: get_active_runs(), get_failed_runs()
-- Covers queries: SELECT * FROM scrape_runs WHERE status = ?
CREATE INDEX IF NOT EXISTS idx_runs_status 
ON scrape_runs(status);

-- Index for temporal queries (most recent runs first)
-- Used by: get_recent_runs(), latest_run()
-- Covers queries: SELECT * FROM scrape_runs ORDER BY start_time DESC
CREATE INDEX IF NOT EXISTS idx_runs_start_time 
ON scrape_runs(start_time DESC);

-- ============================================================================
-- Indexes for scrape_page_status
-- ============================================================================

-- Index for querying all pages in a specific run
-- Used by: get_run_progress(), list_failed_pages()
-- Covers queries: SELECT * FROM scrape_page_status WHERE run_id = ?
CREATE INDEX IF NOT EXISTS idx_page_status_run 
ON scrape_page_status(run_id);

-- Index for filtering pages by status
-- Used by: get_pending_pages(), get_failed_pages(), resume_scrape()
-- Covers queries: SELECT * FROM scrape_page_status WHERE status = ?
CREATE INDEX IF NOT EXISTS idx_page_status_status 
ON scrape_page_status(status);
