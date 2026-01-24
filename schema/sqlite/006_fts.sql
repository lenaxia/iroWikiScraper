-- schema/sqlite/006_fts.sql
-- Full-text search using FTS5
-- Version: 1.0

-- Create FTS5 virtual table
-- UNINDEXED means the field is stored but not searchable (used for joins)
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    page_id UNINDEXED,  -- Don't index page_id (we'll join on it)
    title,               -- Page title (searchable)
    content,             -- Page content (searchable)
    tokenize='porter unicode61'  -- Porter stemming + Unicode support
);

-- Trigger to sync new revisions to FTS
-- When a new revision is inserted, update the FTS index
CREATE TRIGGER IF NOT EXISTS revisions_fts_insert
AFTER INSERT ON revisions
BEGIN
    -- Delete old FTS entry for this page (if exists)
    DELETE FROM pages_fts WHERE page_id = NEW.page_id;
    
    -- Insert new FTS entry with latest content
    INSERT INTO pages_fts (page_id, title, content)
    SELECT p.page_id, p.title, NEW.content
    FROM pages p
    WHERE p.page_id = NEW.page_id;
END;

-- Trigger to sync revision updates to FTS
-- When a revision is updated, update the FTS index
CREATE TRIGGER IF NOT EXISTS revisions_fts_update
AFTER UPDATE ON revisions
BEGIN
    -- Delete old FTS entry for this page
    DELETE FROM pages_fts WHERE page_id = NEW.page_id;
    
    -- Insert new FTS entry with latest content
    INSERT INTO pages_fts (page_id, title, content)
    SELECT p.page_id, p.title, NEW.content
    FROM pages p
    WHERE p.page_id = NEW.page_id;
END;

-- Trigger to sync page title updates to FTS
-- When a page title is updated, update it in FTS
CREATE TRIGGER IF NOT EXISTS pages_fts_update
AFTER UPDATE OF title ON pages
BEGIN
    -- Update title in FTS (keep existing content)
    -- We need to get the latest content from revisions
    DELETE FROM pages_fts WHERE page_id = NEW.page_id;
    
    INSERT INTO pages_fts (page_id, title, content)
    SELECT NEW.page_id, NEW.title, r.content
    FROM revisions r
    WHERE r.page_id = NEW.page_id
    ORDER BY r.timestamp DESC
    LIMIT 1;
END;

-- Trigger to remove deleted pages from FTS
CREATE TRIGGER IF NOT EXISTS pages_fts_delete
AFTER DELETE ON pages
BEGIN
    DELETE FROM pages_fts WHERE page_id = OLD.page_id;
END;

-- Initial population: populate FTS with latest revision for each page
-- This is idempotent (will be skipped if already populated)
INSERT OR IGNORE INTO pages_fts (page_id, title, content)
SELECT 
    p.page_id,
    p.title,
    (
        SELECT r.content
        FROM revisions r
        WHERE r.page_id = p.page_id
        ORDER BY r.timestamp DESC
        LIMIT 1
    ) as content
FROM pages p
WHERE EXISTS (
    SELECT 1 FROM revisions r WHERE r.page_id = p.page_id
);
