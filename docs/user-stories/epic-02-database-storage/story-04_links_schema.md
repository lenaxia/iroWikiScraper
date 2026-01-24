# Story 04: Links Table Schema

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-04  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 0.5 days  
**Assignee**: TBD

## User Story

As a **database developer**,  
I want **a SQL schema for link relationships**,  
So that **I can efficiently query page connections, templates, and categories with deduplication**.

## Description

Design and implement the SQL schema for the `links` table, which stores relationships between pages (wikilinks, template inclusions, category memberships). The schema must support ~50,000 links with efficient queries by source page, target title, and link type.

This table enables graph queries like "what links here", "what templates does this page use", and "what pages are in this category".

## Background & Context

**What is the links table?**
- Stores directed edges in wiki page graph
- Three types: wikilinks, templates, categories
- Source page → target title (not target page_id, as target may not exist)
- Used for link analysis, dependency tracking, navigation

**iRO Wiki Scale:**
- ~50,000 total link relationships
- Wikilinks: ~40,000 (page → page)
- Templates: ~8,000 (page → template)
- Categories: ~2,000 (page → category)
- Many pages have 10-30 links each

**Why This Story Matters:**
- Enable "what links here" queries
- Track template dependencies
- Support category browsing
- Foundation for graph analysis

## Acceptance Criteria

### 1. Schema File Creation
- [ ] Create `schema/sqlite/004_links.sql`
- [ ] File contains complete table definition
- [ ] Includes all indexes
- [ ] Includes comments

### 2. Table Structure
- [ ] Column: `source_page_id` (INTEGER NOT NULL, foreign key)
- [ ] Column: `target_title` (TEXT NOT NULL)
- [ ] Column: `link_type` (TEXT NOT NULL)
- [ ] Composite unique constraint on (source_page_id, target_title, link_type)

### 3. Constraints
- [ ] Foreign key: `source_page_id` → `pages(page_id)` with CASCADE
- [ ] NOT NULL on all columns
- [ ] Check constraint: `link_type IN ('wikilink', 'template', 'category')`
- [ ] Unique constraint prevents duplicate links

### 4. Indexes
- [ ] Index: `idx_links_source` on `source_page_id` for "what does this page link to"
- [ ] Index: `idx_links_target` on `target_title` for "what links here"
- [ ] Index: `idx_links_type` on `link_type` for filtering by type
- [ ] Composite index: `idx_links_type_target` on `(link_type, target_title)` for category/template queries

### 5. Performance
- [ ] Supports 50,000 links
- [ ] Query by source < 5ms
- [ ] Query by target < 10ms
- [ ] Bulk inserts (10,000 links) < 2 seconds

## Technical Details

### Schema Implementation

```sql
-- schema/sqlite/004_links.sql
-- Links table: Stores page relationships (wikilinks, templates, categories)
-- Version: 1.0

CREATE TABLE IF NOT EXISTS links (
    -- Source page (the page containing the link)
    source_page_id INTEGER NOT NULL,
    
    -- Target title (may not exist as page yet)
    -- Stored as title, not page_id, because target may not exist
    -- Format: "Title" for main namespace, "Template:Name" for templates
    target_title TEXT NOT NULL,
    
    -- Type of link relationship
    -- 'wikilink': [[Target]]
    -- 'template': {{Template}}
    -- 'category': [[Category:Name]]
    link_type TEXT NOT NULL,
    
    -- Ensure no duplicate links
    UNIQUE(source_page_id, target_title, link_type),
    
    -- Foreign key to source page
    FOREIGN KEY (source_page_id) REFERENCES pages(page_id) ON DELETE CASCADE,
    
    -- Validate link type
    CHECK(link_type IN ('wikilink', 'template', 'category'))
);

-- Index for "what does this page link to" queries
CREATE INDEX IF NOT EXISTS idx_links_source 
ON links(source_page_id);

-- Index for "what links here" (backlinks) queries
CREATE INDEX IF NOT EXISTS idx_links_target 
ON links(target_title);

-- Index for filtering by link type
CREATE INDEX IF NOT EXISTS idx_links_type 
ON links(link_type);

-- Composite index for category/template membership queries
-- "What pages use this template?" or "What pages are in this category?"
CREATE INDEX IF NOT EXISTS idx_links_type_target 
ON links(link_type, target_title);
```

### Query Examples

```sql
-- Get all links from a page
SELECT target_title, link_type
FROM links
WHERE source_page_id = 123
ORDER BY link_type, target_title;

-- Get backlinks (what links here)
SELECT l.source_page_id, p.title
FROM links l
JOIN pages p ON l.source_page_id = p.page_id
WHERE l.target_title = 'Prontera' AND l.link_type = 'wikilink'
ORDER BY p.title;

-- Get all pages in a category
SELECT l.source_page_id, p.title
FROM links l
JOIN pages p ON l.source_page_id = p.page_id
WHERE l.target_title = 'Category:Cities' AND l.link_type = 'category'
ORDER BY p.title;

-- Get all pages using a template
SELECT l.source_page_id, p.title
FROM links l
JOIN pages p ON l.source_page_id = p.page_id
WHERE l.target_title = 'Template:Infobox' AND l.link_type = 'template'
ORDER BY p.title;

-- Count links by type
SELECT link_type, COUNT(*) as count
FROM links
GROUP BY link_type;

-- Find orphaned pages (no incoming links)
SELECT p.page_id, p.title
FROM pages p
WHERE p.page_id NOT IN (
    SELECT DISTINCT l.source_page_id
    FROM links l
    WHERE l.target_title = p.title
);
```

## Dependencies

### Requires
- Story 01: Pages Table Schema (foreign key dependency)

### Blocks
- Story 06: Database Initialization
- Story 10: Link Database Operations
- Epic 03: Incremental Updates (link tracking)

## Testing Requirements

- [ ] Foreign key enforced
- [ ] Unique constraint prevents duplicates
- [ ] Check constraint validates link_type
- [ ] All 4 indexes created
- [ ] Insert 10,000 links < 2 seconds
- [ ] Query by source < 5ms
- [ ] Query by target < 10ms

## Definition of Done

- [ ] SQL file created
- [ ] Schema executes without errors
- [ ] All constraints and indexes verified
- [ ] Test script passes
- [ ] Performance benchmarks met
- [ ] Code review completed

## Notes

**Why target_title not target_page_id?**
- Target page may not exist yet (red links)
- Links created before target page scraped
- Matches MediaWiki behavior

**Why composite unique constraint?**
- Same page can link to target multiple times (different types)
- Prevents duplicate wikilinks
- Deduplication built into schema

**Future considerations:**
- May add `anchor_text` for link labels
- May add `position` for link order
- May normalize target titles (case, underscores)
