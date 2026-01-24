-- schema/sqlite/001_pages.sql
-- Pages table: Stores wiki page metadata
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 13+
--
-- Design Notes:
-- - page_id uses INTEGER PRIMARY KEY (auto-increment in SQLite, serial in PostgreSQL)
-- - namespace follows MediaWiki standard (0=Main, 2=User, 4=Project, 6=File, etc.)
-- - title is stored without namespace prefix (e.g., "Prontera" not "Main:Prontera")
-- - is_redirect tracks redirect pages for link resolution
-- - created_at/updated_at track database timestamps (not wiki timestamps)

CREATE TABLE IF NOT EXISTS pages (
    -- Unique identifier for each page
    -- INTEGER PRIMARY KEY provides auto-increment in SQLite
    -- Compatible with PostgreSQL SERIAL type
    page_id INTEGER PRIMARY KEY,
    
    -- Namespace following MediaWiki numbering
    -- 0=Main, 2=User, 4=Project, 6=File, 8=MediaWiki, 10=Template, 12=Help, 14=Category
    -- Must be non-negative (negative namespaces reserved for special pages)
    namespace INTEGER NOT NULL DEFAULT 0,
    
    -- Page title without namespace prefix
    -- Example: "Prontera" not "Main:Prontera"
    -- TEXT type supports Unicode for international characters
    title TEXT NOT NULL,
    
    -- Whether this page redirects to another page
    -- Used for redirect resolution and cleanup operations
    -- BOOLEAN stored as 0/1 in SQLite, native boolean in PostgreSQL
    is_redirect BOOLEAN NOT NULL DEFAULT 0,
    
    -- Timestamp when page record was created in our database
    -- TIMESTAMP type compatible with both SQLite and PostgreSQL
    -- Tracks when we first discovered this page
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Timestamp when page metadata was last updated
    -- Used for incremental scraping and change tracking
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure titles are unique within each namespace
    -- Prevents duplicate page entries
    UNIQUE(namespace, title),
    
    -- Namespace must be non-negative
    -- Negative namespaces are for special MediaWiki pages
    CHECK(namespace >= 0)
);

-- Index for fast lookup by title (case-sensitive)
-- Used by: page discovery, link resolution, search operations
-- Covers queries: SELECT * FROM pages WHERE title = ?
CREATE INDEX IF NOT EXISTS idx_pages_title 
ON pages(title);

-- Index for filtering and grouping by namespace
-- Used by: namespace-specific queries, statistics, filtering
-- Covers queries: SELECT * FROM pages WHERE namespace = ?
CREATE INDEX IF NOT EXISTS idx_pages_namespace 
ON pages(namespace);

-- Partial index for finding redirect pages
-- Only indexes rows where is_redirect = TRUE (saves space)
-- Used by: redirect resolution, cleanup operations
-- SQLite 3.8.0+ feature, not portable to older versions
CREATE INDEX IF NOT EXISTS idx_pages_redirect 
ON pages(is_redirect) 
WHERE is_redirect = TRUE;
