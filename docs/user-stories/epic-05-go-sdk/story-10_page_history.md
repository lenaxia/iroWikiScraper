# Story 10: Page History Query

**Story ID**: epic-05-story-10  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to retrieve the complete revision history of a wiki page  
**So that** I can track how a page has evolved over time

## Acceptance Criteria

1. **Basic History Retrieval**
   - [ ] Get all revisions for a page by title
   - [ ] Get all revisions for a page by ID
   - [ ] Results ordered by timestamp (newest or oldest first)
   - [ ] Include revision metadata (user, comment, size)

2. **Filtering Options**
   - [ ] Filter by date range
   - [ ] Filter by specific editors
   - [ ] Filter by revision size changes
   - [ ] Include/exclude minor edits

3. **Performance**
   - [ ] Efficient query with proper indexes
   - [ ] Pagination for pages with many revisions
   - [ ] Option to exclude content for metadata-only queries
   - [ ] Handle pages with thousands of revisions

4. **Additional Features**
   - [ ] Get revision count for a page
   - [ ] Get list of contributors
   - [ ] Get edit frequency statistics
   - [ ] Support for deleted revisions (if available)

## Technical Details

### History Query Implementation

```go
package irowiki

import (
    "context"
    "time"
)

// HistoryOptions configures history queries
type HistoryOptions struct {
    // Date range
    StartDate *time.Time
    EndDate   *time.Time
    
    // Filtering
    Editor        string
    ExcludeMinor  bool
    OnlyMinor     bool
    MinSizeChange *int
    MaxSizeChange *int
    
    // Content
    IncludeContent bool
    
    // Pagination
    Offset int
    Limit  int
    
    // Sorting
    Oldest bool // If true, oldest first; otherwise newest first
}

// GetPageHistory retrieves revision history for a page
func (c *sqliteClient) GetPageHistory(ctx context.Context, title string, opts HistoryOptions) ([]Revision, error) {
    // First, get the page ID
    page, err := c.GetPage(ctx, title)
    if err != nil {
        return nil, err
    }
    
    return c.GetPageHistoryByID(ctx, page.ID, opts)
}

// GetPageHistoryByID retrieves revision history by page ID
func (c *sqliteClient) GetPageHistoryByID(ctx context.Context, pageID int64, opts HistoryOptions) ([]Revision, error) {
    query := c.buildHistoryQuery(opts)
    args := c.buildHistoryArgs(pageID, opts)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, fmt.Errorf("history query failed: %w", err)
    }
    defer rows.Close()
    
    var revisions []Revision
    for rows.Next() {
        revision, err := c.scanRevision(rows, opts.IncludeContent)
        if err != nil {
            return nil, err
        }
        revisions = append(revisions, *revision)
    }
    
    return revisions, rows.Err()
}

// buildHistoryQuery constructs the SQL query
func (c *sqliteClient) buildHistoryQuery(opts HistoryOptions) string {
    // Select columns
    columns := `
        r.rev_id,
        r.page_id,
        r.rev_timestamp,
        r.rev_user_text,
        r.rev_user_id,
        r.rev_comment,
        r.rev_minor_edit,
        r.content_size,
        r.sha1
    `
    
    if opts.IncludeContent {
        columns += ", r.content"
    }
    
    query := "SELECT " + columns + " FROM revisions r WHERE r.page_id = ?"
    
    // Date filters
    if opts.StartDate != nil {
        query += " AND r.rev_timestamp >= ?"
    }
    if opts.EndDate != nil {
        query += " AND r.rev_timestamp <= ?"
    }
    
    // Editor filter
    if opts.Editor != "" {
        query += " AND r.rev_user_text = ?"
    }
    
    // Minor edit filter
    if opts.ExcludeMinor {
        query += " AND r.rev_minor_edit = 0"
    } else if opts.OnlyMinor {
        query += " AND r.rev_minor_edit = 1"
    }
    
    // Size change filters (requires self-join)
    if opts.MinSizeChange != nil || opts.MaxSizeChange != nil {
        query = c.addSizeChangeFilter(query, opts)
    }
    
    // Sorting
    if opts.Oldest {
        query += " ORDER BY r.rev_timestamp ASC"
    } else {
        query += " ORDER BY r.rev_timestamp DESC"
    }
    
    // Pagination
    if opts.Limit > 0 {
        query += fmt.Sprintf(" LIMIT %d", opts.Limit)
    }
    if opts.Offset > 0 {
        query += fmt.Sprintf(" OFFSET %d", opts.Offset)
    }
    
    return query
}

// buildHistoryArgs constructs query arguments
func (c *sqliteClient) buildHistoryArgs(pageID int64, opts HistoryOptions) []interface{} {
    args := []interface{}{pageID}
    
    if opts.StartDate != nil {
        args = append(args, opts.StartDate)
    }
    if opts.EndDate != nil {
        args = append(args, opts.EndDate)
    }
    if opts.Editor != "" {
        args = append(args, opts.Editor)
    }
    
    return args
}

// scanRevision scans a revision from a row
func (c *sqliteClient) scanRevision(rows *sql.Rows, includeContent bool) (*Revision, error) {
    var rev Revision
    var userID sql.NullInt64
    
    if includeContent {
        err := rows.Scan(
            &rev.ID,
            &rev.PageID,
            &rev.Timestamp,
            &rev.Username,
            &userID,
            &rev.Comment,
            &rev.IsMinor,
            &rev.ContentSize,
            &rev.SHA1,
            &rev.Content,
        )
        if err != nil {
            return nil, err
        }
    } else {
        err := rows.Scan(
            &rev.ID,
            &rev.PageID,
            &rev.Timestamp,
            &rev.Username,
            &userID,
            &rev.Comment,
            &rev.IsMinor,
            &rev.ContentSize,
            &rev.SHA1,
        )
        if err != nil {
            return nil, err
        }
    }
    
    if userID.Valid {
        id := userID.Int64
        rev.UserID = &id
    }
    
    return &rev, nil
}
```

### Additional History Queries

```go
// GetRevisionCount returns the number of revisions for a page
func (c *sqliteClient) GetRevisionCount(ctx context.Context, pageID int64) (int, error) {
    const query = `
        SELECT COUNT(*) FROM revisions WHERE page_id = ?
    `
    
    var count int
    err := c.db.QueryRowContext(ctx, query, pageID).Scan(&count)
    return count, err
}

// GetContributors returns a list of users who edited a page
func (c *sqliteClient) GetContributors(ctx context.Context, pageID int64) ([]User, error) {
    const query = `
        SELECT 
            r.rev_user_id,
            r.rev_user_text,
            COUNT(*) as edit_count,
            MIN(r.rev_timestamp) as first_edit,
            MAX(r.rev_timestamp) as last_edit
        FROM revisions r
        WHERE r.page_id = ?
        GROUP BY r.rev_user_text
        ORDER BY edit_count DESC
    `
    
    rows, err := c.db.QueryContext(ctx, query, pageID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var contributors []User
    for rows.Next() {
        var user User
        var userID sql.NullInt64
        
        err := rows.Scan(
            &userID,
            &user.Name,
            &user.EditCount,
            &user.FirstEdit,
            &user.LastEdit,
        )
        if err != nil {
            return nil, err
        }
        
        if userID.Valid {
            user.ID = userID.Int64
        }
        
        contributors = append(contributors, user)
    }
    
    return contributors, rows.Err()
}

// GetEditFrequency returns edit statistics over time
func (c *sqliteClient) GetEditFrequency(ctx context.Context, pageID int64) (map[string]int, error) {
    const query = `
        SELECT 
            strftime('%Y-%m', r.rev_timestamp) as month,
            COUNT(*) as edit_count
        FROM revisions r
        WHERE r.page_id = ?
        GROUP BY month
        ORDER BY month
    `
    
    rows, err := c.db.QueryContext(ctx, query, pageID)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    frequency := make(map[string]int)
    for rows.Next() {
        var month string
        var count int
        
        if err := rows.Scan(&month, &count); err != nil {
            return nil, err
        }
        
        frequency[month] = count
    }
    
    return frequency, rows.Err()
}

// GetRevisionByID retrieves a specific revision
func (c *sqliteClient) GetRevision(ctx context.Context, revisionID int64) (*Revision, error) {
    const query = `
        SELECT 
            r.rev_id,
            r.page_id,
            r.rev_timestamp,
            r.rev_user_text,
            r.rev_user_id,
            r.rev_comment,
            r.rev_minor_edit,
            r.content_size,
            r.sha1,
            r.content,
            p.page_title
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        WHERE r.rev_id = ?
    `
    
    var rev Revision
    var userID sql.NullInt64
    
    err := c.db.QueryRowContext(ctx, query, revisionID).Scan(
        &rev.ID,
        &rev.PageID,
        &rev.Timestamp,
        &rev.Username,
        &userID,
        &rev.Comment,
        &rev.IsMinor,
        &rev.ContentSize,
        &rev.SHA1,
        &rev.Content,
        &rev.PageTitle,
    )
    
    if err == sql.ErrNoRows {
        return nil, ErrNotFound
    }
    if err != nil {
        return nil, err
    }
    
    if userID.Valid {
        id := userID.Int64
        rev.UserID = &id
    }
    
    return &rev, nil
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 05: Data Models
- Epic 02: Database Schema (revisions table)

## Implementation Notes

- Consider excluding content by default for performance
- Use proper indexes on (page_id, rev_timestamp)
- Handle pages with thousands of revisions efficiently
- Support streaming results for very long histories
- Cache contributor lists for frequently accessed pages
- Consider rate limiting for bulk history queries

## Testing Requirements

- [ ] Basic history retrieval tests
- [ ] Date range filtering tests
- [ ] Editor filtering tests
- [ ] Minor edit filtering tests
- [ ] Pagination tests
- [ ] Revision count tests
- [ ] Contributor list tests
- [ ] Performance tests with large histories (1000+ revisions)

## Definition of Done

- [ ] History query methods implemented
- [ ] All filtering options working
- [ ] Pagination support added
- [ ] Additional query methods implemented
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code reviewed and approved
