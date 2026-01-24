# Story 06: Page Search

**Story ID**: epic-05-story-06  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 5 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to search for pages by title and content  
**So that** I can find relevant wiki pages quickly

## Acceptance Criteria

1. **Title Search**
   - [ ] Exact title matching
   - [ ] Prefix matching (e.g., "Por" matches "Poring")
   - [ ] Case-insensitive search
   - [ ] Wildcard support (* and ?)

2. **Content Search**
   - [ ] Search in page content
   - [ ] Multiple keyword support
   - [ ] Phrase matching with quotes
   - [ ] Exclude keywords with minus prefix

3. **Filtering**
   - [ ] Filter by namespace
   - [ ] Filter by date range
   - [ ] Filter by page size
   - [ ] Combine multiple filters

4. **Results**
   - [ ] Return relevant pages sorted by match quality
   - [ ] Include match snippets with context
   - [ ] Calculate relevance scores
   - [ ] Support pagination

## Technical Details

### Search Implementation

```go
package irowiki

import (
    "context"
    "fmt"
    "strings"
)

// Search performs a general search across pages
func (c *sqliteClient) Search(ctx context.Context, opts SearchOptions) ([]SearchResult, error) {
    if err := opts.Validate(); err != nil {
        return nil, fmt.Errorf("invalid options: %w", err)
    }
    
    opts.SetDefaults()
    
    query := c.buildSearchQuery(opts)
    args := c.buildSearchArgs(opts)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, fmt.Errorf("search query failed: %w", err)
    }
    defer rows.Close()
    
    var results []SearchResult
    for rows.Next() {
        var result SearchResult
        err := rows.Scan(
            &result.ID,
            &result.Title,
            &result.Namespace,
            &result.Snippet,
            &result.Score,
            &result.MatchType,
        )
        if err != nil {
            return nil, fmt.Errorf("scan failed: %w", err)
        }
        results = append(results, result)
    }
    
    return results, rows.Err()
}

// buildSearchQuery constructs the SQL query based on options
func (c *sqliteClient) buildSearchQuery(opts SearchOptions) string {
    var conditions []string
    
    // Base query
    query := `
        SELECT DISTINCT
            p.page_id,
            p.page_title,
            p.page_namespace,
            snippet(content_fts) as snippet,
            rank as score,
            match_type
        FROM pages p
        JOIN revisions r ON p.page_latest = r.rev_id
    `
    
    // Title search
    if opts.MatchType == "title" || opts.MatchType == "any" {
        conditions = append(conditions, "p.page_title LIKE ?")
    }
    
    // Content search
    if opts.MatchType == "content" || opts.MatchType == "any" {
        query += " LEFT JOIN content_fts ON r.rev_id = content_fts.rowid"
        conditions = append(conditions, "content_fts MATCH ?")
    }
    
    // Namespace filter
    if opts.Namespace != nil {
        conditions = append(conditions, "p.page_namespace = ?")
    }
    
    // Date range
    if opts.StartDate != nil {
        conditions = append(conditions, "r.rev_timestamp >= ?")
    }
    if opts.EndDate != nil {
        conditions = append(conditions, "r.rev_timestamp <= ?")
    }
    
    // Add WHERE clause
    if len(conditions) > 0 {
        query += " WHERE " + strings.Join(conditions, " AND ")
    }
    
    // Sorting
    if opts.SortBy == "relevance" {
        query += " ORDER BY score DESC"
    } else if opts.SortBy == "date" {
        query += " ORDER BY r.rev_timestamp " + strings.ToUpper(opts.SortOrder)
    } else {
        query += " ORDER BY p.page_title " + strings.ToUpper(opts.SortOrder)
    }
    
    // Pagination
    query += fmt.Sprintf(" LIMIT %d OFFSET %d", opts.Limit, opts.Offset)
    
    return query
}

// buildSearchArgs constructs the query arguments
func (c *sqliteClient) buildSearchArgs(opts SearchOptions) []interface{} {
    var args []interface{}
    
    // Add query parameter
    if opts.MatchType == "title" || opts.MatchType == "any" {
        args = append(args, "%"+opts.Query+"%")
    }
    
    if opts.MatchType == "content" || opts.MatchType == "any" {
        args = append(args, opts.Query)
    }
    
    // Add filters
    if opts.Namespace != nil {
        args = append(args, *opts.Namespace)
    }
    
    if opts.StartDate != nil {
        args = append(args, opts.StartDate)
    }
    
    if opts.EndDate != nil {
        args = append(args, opts.EndDate)
    }
    
    return args
}
```

### Title Search Helper

```go
// SearchByTitle searches for pages by title prefix
func (c *sqliteClient) SearchByTitle(ctx context.Context, titlePrefix string, limit int) ([]Page, error) {
    const query = `
        SELECT page_id, page_title, page_namespace, page_latest
        FROM pages
        WHERE page_title LIKE ? || '%'
        ORDER BY page_title
        LIMIT ?
    `
    
    rows, err := c.db.QueryContext(ctx, query, titlePrefix, limit)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var pages []Page
    for rows.Next() {
        var page Page
        if err := rows.Scan(&page.ID, &page.Title, &page.Namespace, &page.LatestRevID); err != nil {
            return nil, err
        }
        pages = append(pages, page)
    }
    
    return pages, rows.Err()
}
```

### Snippet Generation

```go
// generateSnippet creates a context snippet around matches
func generateSnippet(content string, query string, maxLength int) string {
    query = strings.ToLower(query)
    contentLower := strings.ToLower(content)
    
    // Find first match
    idx := strings.Index(contentLower, query)
    if idx == -1 {
        // No match, return beginning
        if len(content) <= maxLength {
            return content
        }
        return content[:maxLength] + "..."
    }
    
    // Calculate snippet bounds
    start := idx - maxLength/2
    if start < 0 {
        start = 0
    }
    
    end := start + maxLength
    if end > len(content) {
        end = len(content)
    }
    
    snippet := content[start:end]
    
    // Add ellipsis
    if start > 0 {
        snippet = "..." + snippet
    }
    if end < len(content) {
        snippet = snippet + "..."
    }
    
    return snippet
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 05: Data Models
- Epic 02: Database Schema (FTS indexes)

## Implementation Notes

- Use SQLite FTS5 for content search
- PostgreSQL can use `ts_vector` and `ts_query`
- Cache compiled search patterns for performance
- Limit snippet length to 200 characters
- Consider highlighting matches in snippets
- Support Unicode characters in search

## Testing Requirements

- [ ] Title search tests (exact, prefix, case-insensitive)
- [ ] Content search tests (keywords, phrases)
- [ ] Filter combination tests
- [ ] Pagination tests
- [ ] Empty result tests
- [ ] Special character handling tests
- [ ] Performance benchmarks (<100ms for most searches)

## Definition of Done

- [ ] Search methods implemented in both backends
- [ ] All search types working (title, content)
- [ ] Filtering and pagination working
- [ ] Snippet generation implemented
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code reviewed and approved
