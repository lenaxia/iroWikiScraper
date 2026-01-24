# Story 09: Pagination Support

**Story ID**: epic-05-story-09  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** robust pagination support for query results  
**So that** I can efficiently navigate through large result sets

## Acceptance Criteria

1. **Offset-Based Pagination**
   - [ ] Support offset and limit parameters
   - [ ] Return total count of results
   - [ ] Indicate if more results exist
   - [ ] Handle edge cases (offset beyond results)

2. **Cursor-Based Pagination**
   - [ ] Support cursor tokens for stable pagination
   - [ ] Handle sort order changes gracefully
   - [ ] Efficient queries without offset overhead
   - [ ] Opaque cursor encoding

3. **Result Metadata**
   - [ ] Include pagination info in results
   - [ ] Total count (optional, for performance)
   - [ ] Current page information
   - [ ] Next/previous page helpers

4. **Performance**
   - [ ] Efficient queries with proper indexes
   - [ ] Avoid COUNT(*) overhead when possible
   - [ ] Streaming results for large datasets
   - [ ] Consistent performance across pages

## Technical Details

### PagedResult Structure

```go
package irowiki

import "encoding/base64"

// PagedResult wraps results with pagination metadata
type PagedResult struct {
    Results    []SearchResult `json:"results"`
    Total      int            `json:"total,omitempty"`
    Offset     int            `json:"offset"`
    Limit      int            `json:"limit"`
    HasMore    bool           `json:"has_more"`
    NextCursor string         `json:"next_cursor,omitempty"`
    PrevCursor string         `json:"prev_cursor,omitempty"`
}

// PageInfo provides pagination metadata
type PageInfo struct {
    CurrentPage int  `json:"current_page"`
    TotalPages  int  `json:"total_pages"`
    PageSize    int  `json:"page_size"`
    Total       int  `json:"total"`
    HasNext     bool `json:"has_next"`
    HasPrev     bool `json:"has_prev"`
}

// PaginationOptions configures pagination behavior
type PaginationOptions struct {
    // Offset-based
    Offset int
    Limit  int
    
    // Cursor-based
    Cursor string
    
    // Metadata
    IncludeTotalCount bool
}
```

### Offset-Based Pagination

```go
// SearchPaged performs a search with pagination
func (c *sqliteClient) SearchPaged(ctx context.Context, opts SearchOptions) (*PagedResult, error) {
    if err := opts.Validate(); err != nil {
        return nil, err
    }
    
    opts.SetDefaults()
    
    // Get results with limit+1 to check for more
    opts.Limit++
    results, err := c.Search(ctx, opts)
    if err != nil {
        return nil, err
    }
    opts.Limit--
    
    // Check if more results exist
    hasMore := len(results) > opts.Limit
    if hasMore {
        results = results[:opts.Limit]
    }
    
    paged := &PagedResult{
        Results: results,
        Offset:  opts.Offset,
        Limit:   opts.Limit,
        HasMore: hasMore,
    }
    
    // Optionally get total count (expensive)
    if opts.IncludeTotalCount {
        total, err := c.countResults(ctx, opts)
        if err == nil {
            paged.Total = total
        }
    }
    
    return paged, nil
}

// countResults gets total count for pagination
func (c *sqliteClient) countResults(ctx context.Context, opts SearchOptions) (int, error) {
    query := c.buildCountQuery(opts)
    args := c.buildSearchArgs(opts)
    
    var count int
    err := c.db.QueryRowContext(ctx, query, args...).Scan(&count)
    return count, err
}
```

### Cursor-Based Pagination

```go
// Cursor encodes pagination state
type Cursor struct {
    LastID    int64
    LastValue string // For sorting
    Direction string // "next" or "prev"
}

// Encode converts cursor to string
func (c *Cursor) Encode() string {
    data := fmt.Sprintf("%d:%s:%s", c.LastID, c.LastValue, c.Direction)
    return base64.URLEncoding.EncodeToString([]byte(data))
}

// DecodeCursor parses a cursor string
func DecodeCursor(s string) (*Cursor, error) {
    if s == "" {
        return nil, nil
    }
    
    data, err := base64.URLEncoding.DecodeString(s)
    if err != nil {
        return nil, fmt.Errorf("invalid cursor: %w", err)
    }
    
    parts := strings.Split(string(data), ":")
    if len(parts) != 3 {
        return nil, fmt.Errorf("malformed cursor")
    }
    
    id, err := strconv.ParseInt(parts[0], 10, 64)
    if err != nil {
        return nil, fmt.Errorf("invalid cursor ID: %w", err)
    }
    
    return &Cursor{
        LastID:    id,
        LastValue: parts[1],
        Direction: parts[2],
    }, nil
}

// SearchWithCursor performs cursor-based pagination
func (c *sqliteClient) SearchWithCursor(ctx context.Context, opts SearchOptions) (*PagedResult, error) {
    cursor, err := DecodeCursor(opts.Cursor)
    if err != nil {
        return nil, err
    }
    
    query := c.buildCursorQuery(opts, cursor)
    args := c.buildCursorArgs(opts, cursor)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var results []SearchResult
    var lastResult *SearchResult
    
    for rows.Next() {
        var result SearchResult
        if err := rows.Scan(&result.ID, &result.Title, &result.Score); err != nil {
            return nil, err
        }
        results = append(results, result)
        lastResult = &result
    }
    
    paged := &PagedResult{
        Results: results,
        Limit:   opts.Limit,
        HasMore: len(results) == opts.Limit,
    }
    
    // Generate next cursor
    if lastResult != nil && paged.HasMore {
        nextCursor := &Cursor{
            LastID:    lastResult.ID,
            LastValue: lastResult.Title,
            Direction: "next",
        }
        paged.NextCursor = nextCursor.Encode()
    }
    
    return paged, nil
}

// buildCursorQuery constructs query with cursor
func (c *sqliteClient) buildCursorQuery(opts SearchOptions, cursor *Cursor) string {
    query := c.buildSearchQuery(opts)
    
    if cursor != nil {
        // Add cursor condition
        if cursor.Direction == "next" {
            query += " AND (p.page_title > ? OR (p.page_title = ? AND p.page_id > ?))"
        } else {
            query += " AND (p.page_title < ? OR (p.page_title = ? AND p.page_id < ?))"
        }
    }
    
    return query
}
```

### Helper Methods

```go
// GetPageInfo calculates page information
func (pr *PagedResult) GetPageInfo() PageInfo {
    currentPage := pr.Offset/pr.Limit + 1
    totalPages := 0
    if pr.Total > 0 {
        totalPages = (pr.Total + pr.Limit - 1) / pr.Limit
    }
    
    return PageInfo{
        CurrentPage: currentPage,
        TotalPages:  totalPages,
        PageSize:    pr.Limit,
        Total:       pr.Total,
        HasNext:     pr.HasMore,
        HasPrev:     pr.Offset > 0,
    }
}

// NextOffset returns the offset for the next page
func (pr *PagedResult) NextOffset() int {
    if !pr.HasMore {
        return pr.Offset
    }
    return pr.Offset + pr.Limit
}

// PrevOffset returns the offset for the previous page
func (pr *PagedResult) PrevOffset() int {
    if pr.Offset == 0 {
        return 0
    }
    prev := pr.Offset - pr.Limit
    if prev < 0 {
        return 0
    }
    return prev
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 05: Data Models
- Story 06: Page Search

## Implementation Notes

- Offset-based pagination is simpler but less efficient for large offsets
- Cursor-based pagination is more complex but handles large datasets better
- Consider making total count optional (expensive on large tables)
- Use keyset pagination for stable, efficient pagination
- Cursors should be opaque to prevent manipulation
- Handle edge cases: empty results, out-of-bounds offset

## Testing Requirements

- [ ] Offset pagination tests (basic, edge cases)
- [ ] Cursor pagination tests (forward, backward)
- [ ] Total count calculation tests
- [ ] Cursor encoding/decoding tests
- [ ] Performance tests with large datasets
- [ ] Edge case tests (empty results, single page)
- [ ] Concurrent pagination tests

## Definition of Done

- [ ] Offset-based pagination implemented
- [ ] Cursor-based pagination implemented
- [ ] PagedResult structure complete
- [ ] Helper methods working
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code reviewed and approved
