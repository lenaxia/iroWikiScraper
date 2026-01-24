-- schema/sqlite/004_links.sql
-- Links table: Stores page relationships (wikilinks, templates, categories)
-- Version: 1.0
-- Compatible: SQLite 3.35+, PostgreSQL 13+
--
-- Design Notes:
-- - Stores directed edges in wiki page graph
-- - target_title (not target_page_id) because target may not exist yet
-- - Four link types: page ([[Page]]), template ({{Template}}), file ([[File:Name]]), category ([[Category:Name]])
-- - Unique constraint prevents duplicate links
-- - Expected ~50,000 links total (40K page links, 8K templates, 1K files, 1K categories)

CREATE TABLE IF NOT EXISTS links (
    -- Source page containing the link
    -- Foreign key to pages table
    -- The page that has the link, template inclusion, or category membership
    source_page_id INTEGER NOT NULL,
    
    -- Target title that is linked to
    -- Stored as title (not page_id) because target may not exist yet
    -- Format depends on namespace:
    --   - "PageTitle" for main namespace page links
    --   - "Template:Name" for template inclusions
    --   - "File:Name.png" for file references
    --   - "Category:Name" for category memberships
    -- TEXT type supports Unicode titles
    target_title TEXT NOT NULL,
    
    -- Type of link relationship
    -- 'page': [[Target]] - standard hyperlink between pages
    -- 'template': {{Template}} - template inclusion/transclusion
    -- 'file': [[File:Name.png]] - file/image reference
    -- 'category': [[Category:Name]] - category membership
    -- Constrained to these four values only
    link_type TEXT NOT NULL,
    
    -- Prevent duplicate links
    -- Same source can link to same target only once per type
    -- But can have both page link AND template to same target
    UNIQUE(source_page_id, target_title, link_type),
    
    -- Validate link type is one of the four allowed values
    -- Prevents invalid link types from being inserted
    CHECK(link_type IN ('page', 'template', 'file', 'category'))
);

-- Index for "what does this page link to" queries
-- Used by: get_outbound_links(), get_templates_used(), get_categories()
-- Covers queries: SELECT * FROM links WHERE source_page_id = ?
-- Most common query pattern for displaying page dependencies
CREATE INDEX IF NOT EXISTS idx_links_source 
ON links(source_page_id);

-- Index for "what links here" (backlinks) queries
-- Used by: get_backlinks(), find_references(), orphaned_pages()
-- Covers queries: SELECT * FROM links WHERE target_title = ?
-- Critical for dependency analysis and navigation
CREATE INDEX IF NOT EXISTS idx_links_target 
ON links(target_title);

-- Index for filtering by link type
-- Used by: get_all_templates(), get_all_categories(), statistics()
-- Covers queries: SELECT * FROM links WHERE link_type = ?
-- Enables efficient "show all template inclusions" queries
CREATE INDEX IF NOT EXISTS idx_links_type 
ON links(link_type);

-- Composite index for category/template membership queries
-- Optimizes "what pages use this template?" and "what pages are in this category?"
-- Used by: get_template_usage(), get_category_members()
-- Covers queries: SELECT * FROM links WHERE link_type = ? AND target_title = ?
-- More efficient than using separate indexes when filtering by both
CREATE INDEX IF NOT EXISTS idx_links_type_target 
ON links(link_type, target_title);
