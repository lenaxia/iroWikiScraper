# Story 11: Get Page at Timestamp

**Story ID**: epic-05-story-11  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to retrieve a page's content as it existed at a specific point in time  
**So that** I can view historical versions of wiki pages

## Acceptance Criteria

1. **Timestamp Query**
   - [ ] Get page content at exact timestamp
   - [ ] Get closest revision before timestamp
   - [ ] Get closest revision after timestamp
   - [ ] Handle timestamps before first revision

2. **Query Modes**
   - [ ] Exact match mode (fails if no exact match)
   - [ ] Before-or-at mode (finds latest before timestamp)
   - [ ] After-or-at mode (finds earliest after timestamp)
   - [ ] Nearest mode (finds closest revision)

3. **Response Data**
   - [ ] Full revision content and metadata
   - [ ] Indicate if exact match or approximate
   - [ ] Include temporal distance from query time
   - [ ] Previous and next revision references

4. **Performance**
   - [ ] Efficient index-based lookup
   - [ ] Sub-10ms query time
   - [ ] Handle edge cases gracefully
   - [ ] Support batch queries

## Technical Details

### GetPageAtTime Implementation

```go
package irowiki

import (
    "context"
    "fmt"
    "time"
)

// TimestampMode specifies how to match timestamps
type TimestampMode string

const (
    TimestampExact   TimestampMode = "exact"   // Must match exactly
    TimestampBefore  TimestampMode = "before"  // Latest before or at
    TimestampAfter   TimestampMode = "after"   // Earliest after or at
    TimestampNearest TimestampMode = "nearest" // Closest in either direction
)

// TimestampResult wraps a revision with temporal metadata
type TimestampResult struct {
    Revision      *Revision
    IsExactMatch  bool
    TimeDelta     time.Duration // Distance from query timestamp
    PrevRevision  *int64        // ID of previous revision
    NextRevision  *int64        // ID of next revision
}

// GetPageAtTime retrieves a page as it existed at a specific time
func (c *sqliteClient) GetPageAtTime(ctx context.Context, title string, timestamp time.Time) (*Revision, error) {
    return c.GetPageAtTimeWithMode(ctx, title, timestamp, TimestampBefore)
}

// GetPageAtTimeWithMode retrieves a page with specific matching mode
func (c *sqliteClient) GetPageAtTimeWithMode(ctx context.Context, title string, timestamp time.Time, mode TimestampMode) (*Revision, error) {
    // Get page ID
    page, err := c.GetPage(ctx, title)
    if err != nil {
        return nil, err
    }
    
    return c.getPageAtTimeByID(ctx, page.ID, timestamp, mode)
}

// getPageAtTimeByID performs the actual query
func (c *sqliteClient) getPageAtTimeByID(ctx context.Context, pageID int64, timestamp time.Time, mode TimestampMode) (*Revision, error) {
    var query string
    
    switch mode {
    case TimestampExact:
        query = `
            SELECT 
                r.rev_id, r.page_id, r.rev_timestamp,
                r.rev_user_text, r.rev_user_id, r.rev_comment,
                r.rev_minor_edit, r.content_size, r.sha1, r.content
            FROM revisions r
            WHERE r.page_id = ? AND r.rev_timestamp = ?
        `
        
    case TimestampBefore:
        query = `
            SELECT 
                r.rev_id, r.page_id, r.rev_timestamp,
                r.rev_user_text, r.rev_user_id, r.rev_comment,
                r.rev_minor_edit, r.content_size, r.sha1, r.content
            FROM revisions r
            WHERE r.page_id = ? AND r.rev_timestamp <= ?
            ORDER BY r.rev_timestamp DESC
            LIMIT 1
        `
        
    case TimestampAfter:
        query = `
            SELECT 
                r.rev_id, r.page_id, r.rev_timestamp,
                r.rev_user_text, r.rev_user_id, r.rev_comment,
                r.rev_minor_edit, r.content_size, r.sha1, r.content
            FROM revisions r
            WHERE r.page_id = ? AND r.rev_timestamp >= ?
            ORDER BY r.rev_timestamp ASC
            LIMIT 1
        `
        
    case TimestampNearest:
        // Find both before and after, then choose closest
        return c.getNearestRevision(ctx, pageID, timestamp)
        
    default:
        return nil, fmt.Errorf("invalid timestamp mode: %s", mode)
    }
    
    var rev Revision
    var userID sql.NullInt64
    
    err := c.db.QueryRowContext(ctx, query, pageID, timestamp).Scan(
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
    
    if err == sql.ErrNoRows {
        return nil, ErrNotFound
    }
    if err != nil {
        return nil, fmt.Errorf("query failed: %w", err)
    }
    
    if userID.Valid {
        id := userID.Int64
        rev.UserID = &id
    }
    
    return &rev, nil
}

// getNearestRevision finds the closest revision to a timestamp
func (c *sqliteClient) getNearestRevision(ctx context.Context, pageID int64, timestamp time.Time) (*Revision, error) {
    // Get revision before
    before, errBefore := c.getPageAtTimeByID(ctx, pageID, timestamp, TimestampBefore)
    
    // Get revision after
    after, errAfter := c.getPageAtTimeByID(ctx, pageID, timestamp, TimestampAfter)
    
    // Handle cases
    if errBefore != nil && errAfter != nil {
        return nil, ErrNotFound
    }
    if errBefore != nil {
        return after, nil
    }
    if errAfter != nil {
        return before, nil
    }
    
    // Compare distances
    beforeDelta := timestamp.Sub(before.Timestamp)
    afterDelta := after.Timestamp.Sub(timestamp)
    
    if beforeDelta <= afterDelta {
        return before, nil
    }
    return after, nil
}
```

### Enhanced Result with Metadata

```go
// GetPageAtTimeDetailed returns detailed temporal information
func (c *sqliteClient) GetPageAtTimeDetailed(ctx context.Context, title string, timestamp time.Time, mode TimestampMode) (*TimestampResult, error) {
    page, err := c.GetPage(ctx, title)
    if err != nil {
        return nil, err
    }
    
    rev, err := c.getPageAtTimeByID(ctx, page.ID, timestamp, mode)
    if err != nil {
        return nil, err
    }
    
    result := &TimestampResult{
        Revision:     rev,
        IsExactMatch: rev.Timestamp.Equal(timestamp),
        TimeDelta:    timestamp.Sub(rev.Timestamp).Abs(),
    }
    
    // Get previous and next revisions
    prev, _ := c.getAdjacentRevision(ctx, page.ID, rev.Timestamp, "before")
    if prev != nil {
        result.PrevRevision = &prev.ID
    }
    
    next, _ := c.getAdjacentRevision(ctx, page.ID, rev.Timestamp, "after")
    if next != nil {
        result.NextRevision = &next.ID
    }
    
    return result, nil
}

// getAdjacentRevision finds the revision before or after a timestamp
func (c *sqliteClient) getAdjacentRevision(ctx context.Context, pageID int64, timestamp time.Time, direction string) (*Revision, error) {
    var query string
    
    if direction == "before" {
        query = `
            SELECT rev_id, rev_timestamp
            FROM revisions
            WHERE page_id = ? AND rev_timestamp < ?
            ORDER BY rev_timestamp DESC
            LIMIT 1
        `
    } else {
        query = `
            SELECT rev_id, rev_timestamp
            FROM revisions
            WHERE page_id = ? AND rev_timestamp > ?
            ORDER BY rev_timestamp ASC
            LIMIT 1
        `
    }
    
    var rev Revision
    err := c.db.QueryRowContext(ctx, query, pageID, timestamp).Scan(&rev.ID, &rev.Timestamp)
    
    if err == sql.ErrNoRows {
        return nil, nil
    }
    if err != nil {
        return nil, err
    }
    
    return &rev, nil
}
```

### Batch Queries

```go
// TimelineSnapshot represents multiple pages at a single timestamp
type TimelineSnapshot struct {
    Timestamp time.Time
    Pages     map[string]*Revision
}

// GetMultiplePagesAtTime retrieves multiple pages at a timestamp
func (c *sqliteClient) GetMultiplePagesAtTime(ctx context.Context, titles []string, timestamp time.Time) (*TimelineSnapshot, error) {
    snapshot := &TimelineSnapshot{
        Timestamp: timestamp,
        Pages:     make(map[string]*Revision),
    }
    
    for _, title := range titles {
        rev, err := c.GetPageAtTime(ctx, title, timestamp)
        if err == nil {
            snapshot.Pages[title] = rev
        }
    }
    
    return snapshot, nil
}

// GetPageTimeline retrieves a page at multiple timestamps
func (c *sqliteClient) GetPageTimeline(ctx context.Context, title string, timestamps []time.Time) ([]*Revision, error) {
    revisions := make([]*Revision, 0, len(timestamps))
    
    for _, ts := range timestamps {
        rev, err := c.GetPageAtTime(ctx, title, ts)
        if err == nil {
            revisions = append(revisions, rev)
        }
    }
    
    return revisions, nil
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 05: Data Models
- Story 10: Page History Query

## Implementation Notes

- Use index on (page_id, rev_timestamp) for efficient queries
- Consider caching for frequently accessed timestamps
- Handle edge cases: page doesn't exist yet, page deleted
- For exact mode, consider time zone handling
- Batch queries can be optimized with single SQL query
- Consider supporting relative timestamps ("1 year ago")

## Testing Requirements

- [ ] Exact timestamp match tests
- [ ] Before-or-at tests
- [ ] After-or-at tests
- [ ] Nearest match tests
- [ ] Edge case tests (no revisions before/after)
- [ ] Batch query tests
- [ ] Performance tests (<10ms)
- [ ] Time zone handling tests

## Definition of Done

- [ ] GetPageAtTime implemented for both backends
- [ ] All timestamp modes working
- [ ] Detailed result with metadata
- [ ] Batch query support
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code reviewed and approved
