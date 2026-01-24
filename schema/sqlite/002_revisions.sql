-- schema/sqlite/002_revisions.sql
-- Revisions table: Stores complete edit history for all pages
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 13+
--
-- Design Notes:
-- - revision_id comes from MediaWiki API (not auto-generated)
-- - Stores full content per revision (not diffs) for simplicity
-- - parent_id creates revision chain for history traversal
-- - tags stored as JSON-formatted TEXT (no native JSON/ARRAY types)
-- - Average content size: ~10KB, max ~1MB per revision
-- - Expected ~86,500 revisions, ~865MB total content

CREATE TABLE IF NOT EXISTS revisions (
    -- MediaWiki revision ID (globally unique across wiki)
    -- INTEGER PRIMARY KEY but NOT auto-increment (comes from API)
    -- Must preserve original revision IDs for incremental updates
    revision_id INTEGER PRIMARY KEY,
    
    -- Foreign key to pages table
    -- CASCADE: if page deleted, all its revisions are deleted
    -- Cannot have orphaned revisions without a page
    page_id INTEGER NOT NULL,
    
    -- Parent revision ID forming revision chain
    -- NULL for first revision of a page (no parent)
    -- Self-referencing foreign key for history traversal
    parent_id INTEGER,
    
    -- When this edit was made (UTC timestamp from MediaWiki)
    -- Used for temporal queries and timeline reconstruction
    -- TIMESTAMP type compatible with SQLite and PostgreSQL
    timestamp TIMESTAMP NOT NULL,
    
    -- Username of editor
    -- NULL for deleted/suppressed users or anonymous edits
    -- TEXT type supports Unicode usernames
    user TEXT,
    
    -- MediaWiki user ID
    -- NULL for anonymous edits (IP addresses have no user_id)
    -- Used for contributor statistics and filtering
    user_id INTEGER,
    
    -- Edit summary/comment provided by editor
    -- NULL if no comment was provided
    -- Can contain wikitext markup
    comment TEXT,
    
    -- Full wikitext content at this revision
    -- Average ~10KB, maximum ~1MB per revision
    -- NOT stored as diff (simpler, faster reconstruction)
    -- TEXT type has no size limit in SQLite (up to 1GB)
    content TEXT NOT NULL,
    
    -- Content size in bytes
    -- Used for statistics and storage tracking
    -- Must be non-negative
    size INTEGER NOT NULL,
    
    -- SHA1 hash of content (40-character hex string)
    -- Used for duplicate content detection
    -- Enables finding identical revisions across pages
    sha1 TEXT NOT NULL,
    
    -- Whether edit was marked as minor by editor
    -- BOOLEAN stored as 0/1 in SQLite
    -- Used for filtering significant edits
    minor BOOLEAN DEFAULT 0,
    
    -- Edit tags as JSON array string
    -- Example: '["visual edit", "mobile edit"]'
    -- NULL if no tags applied
    -- Stored as TEXT (no native JSON/ARRAY in portable SQL)
    tags TEXT,
    
    -- Foreign key constraints
    -- CASCADE on page delete: remove all revisions of deleted page
    -- SET NULL on parent delete: preserve revision even if parent deleted
    FOREIGN KEY (page_id) 
        REFERENCES pages(page_id) 
        ON DELETE CASCADE,
    FOREIGN KEY (parent_id) 
        REFERENCES revisions(revision_id) 
        ON DELETE SET NULL,
    
    -- Validation constraints
    -- Size cannot be negative
    CHECK(size >= 0)
);

-- Composite index for per-page history queries (MOST COMMON)
-- Ordered by timestamp DESC for "latest first" retrieval
-- Used by: get_revisions_by_page(), get_latest_revision()
-- Covers queries: SELECT * FROM revisions WHERE page_id = ? ORDER BY timestamp DESC
CREATE INDEX IF NOT EXISTS idx_rev_page_time 
ON revisions(page_id, timestamp DESC);

-- Index for temporal queries across all pages
-- Used by: get_revisions_in_range(), timeline queries, statistics
-- Covers queries: SELECT * FROM revisions WHERE timestamp BETWEEN ? AND ?
CREATE INDEX IF NOT EXISTS idx_rev_timestamp 
ON revisions(timestamp);

-- Partial index for traversing revision chains
-- Only indexes non-NULL parent_id values (saves space)
-- Used by: parent-child relationship queries, history reconstruction
-- Covers queries: SELECT * FROM revisions WHERE parent_id = ?
CREATE INDEX IF NOT EXISTS idx_rev_parent 
ON revisions(parent_id) 
WHERE parent_id IS NOT NULL;

-- Index for duplicate content detection
-- Used by: finding identical revisions, deduplication analysis
-- Covers queries: SELECT * FROM revisions WHERE sha1 = ?
CREATE INDEX IF NOT EXISTS idx_rev_sha1 
ON revisions(sha1);

-- Partial index for user contribution queries
-- Only indexes non-NULL user_id values
-- Used by: contributor statistics, user activity tracking
-- Covers queries: SELECT * FROM revisions WHERE user_id = ?
CREATE INDEX IF NOT EXISTS idx_rev_user
ON revisions(user_id) 
WHERE user_id IS NOT NULL;
