-- schema/sqlite/003_files.sql
-- Files table: Stores metadata for uploaded files (images, documents, etc.)
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 13+
--
-- Design Notes:
-- - filename is natural primary key (unique in MediaWiki)
-- - Stores metadata only, actual file content stored on disk
-- - width/height are NULL for non-image files (PDFs, documents)
-- - sha1 enables duplicate detection and integrity verification
-- - Expected ~4,000 files, ~2MB metadata, ~100MB-1GB actual files on disk

CREATE TABLE IF NOT EXISTS files (
    -- Unique filename (e.g., "Example.png", "Document.pdf")
    -- Primary key ensures uniqueness and efficient lookup
    -- TEXT type supports Unicode and special characters
    -- MediaWiki filenames are unique across entire wiki
    filename TEXT PRIMARY KEY,
    
    -- Full URL to file on wiki server
    -- Example: https://irowiki.org/w/images/a/ab/Example.png
    -- Used for downloading actual file content
    -- TEXT type has no length limit
    url TEXT NOT NULL,
    
    -- URL to file description page on wiki
    -- Example: https://irowiki.org/wiki/File:Example.png
    -- Links to page with file history and metadata
    descriptionurl TEXT NOT NULL,
    
    -- SHA1 hash of file content (40-character hex string)
    -- Used for duplicate detection and integrity verification
    -- Enables finding identical files with different names
    -- TEXT type for hex string representation
    sha1 TEXT NOT NULL,
    
    -- File size in bytes
    -- Used for storage tracking and statistics
    -- Must be non-negative
    size INTEGER NOT NULL,
    
    -- Image width in pixels
    -- NULL for non-image files (PDFs, text files, etc.)
    -- INTEGER type, must be positive if not NULL
    width INTEGER,
    
    -- Image height in pixels  
    -- NULL for non-image files (PDFs, text files, etc.)
    -- INTEGER type, must be positive if not NULL
    height INTEGER,
    
    -- MIME type (e.g., "image/png", "image/jpeg", "application/pdf")
    -- Used for filtering by file type and determining handling
    -- TEXT type for MIME type string
    mime_type TEXT NOT NULL,
    
    -- Upload timestamp (UTC from MediaWiki)
    -- When file was originally uploaded to wiki
    -- TIMESTAMP type compatible with SQLite and PostgreSQL
    timestamp TIMESTAMP NOT NULL,
    
    -- Username of uploader
    -- NULL if user account was deleted
    -- Used for contributor statistics
    uploader TEXT,
    
    -- Validation constraints
    -- Size cannot be negative
    CHECK(size >= 0),
    -- Width must be positive if specified (NULL allowed)
    CHECK(width IS NULL OR width > 0),
    -- Height must be positive if specified (NULL allowed)
    CHECK(height IS NULL OR height > 0)
);

-- Index for duplicate detection by content hash
-- Used by: find_duplicates(), integrity_check()
-- Covers queries: SELECT * FROM files WHERE sha1 = ?
-- Enables finding multiple files with identical content
CREATE INDEX IF NOT EXISTS idx_files_sha1 
ON files(sha1);

-- Index for temporal queries (recent uploads, date ranges)
-- Used by: list_recent_files(), upload_statistics()
-- Covers queries: SELECT * FROM files WHERE timestamp > ? ORDER BY timestamp DESC
CREATE INDEX IF NOT EXISTS idx_files_timestamp 
ON files(timestamp);

-- Index for filtering by file type
-- Used by: list_images(), get_pdfs(), statistics_by_type()
-- Covers queries: SELECT * FROM files WHERE mime_type = ?
-- Enables efficient "show all PNGs" or "show all PDFs" queries
CREATE INDEX IF NOT EXISTS idx_files_mime 
ON files(mime_type);

-- Partial index for uploader statistics
-- Only indexes non-NULL uploader values (saves space)
-- Used by: contributor_file_counts(), user_uploads()
-- Covers queries: SELECT * FROM files WHERE uploader = ?
CREATE INDEX IF NOT EXISTS idx_files_uploader
ON files(uploader) 
WHERE uploader IS NOT NULL;
