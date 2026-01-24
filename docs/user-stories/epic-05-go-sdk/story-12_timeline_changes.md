# Story 12: Timeline Changes Query

**Story ID**: epic-05-story-12  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to query all changes that occurred during a specific time period  
**So that** I can track wiki activity and generate timelines of modifications

## Acceptance Criteria

1. **Period Queries**
   - [ ] Get all changes between two timestamps
   - [ ] Support various time granularities (hour, day, week, month)
   - [ ] Include all affected pages and editors
   - [ ] Order by timestamp (ascending or descending)

2. **Filtering**
   - [ ] Filter by namespace
   - [ ] Filter by editor
   - [ ] Filter by change type (new page, edit, minor edit)
   - [ ] Filter by size of change (delta)

3. **Aggregation**
   - [ ] Group by time periods
   - [ ] Group by page
   - [ ] Group by editor
   - [ ] Summary statistics per group

4. **Performance**
   - [ ] Efficient queries with date indexes
   - [ ] Handle large time periods
   - [ ] Support streaming results
   - [ ] Pagination for large result sets

## Technical Details

### Timeline Query Implementation

```go
package irowiki

import (
    "context"
    "time"
)

// TimelineOptions configures timeline queries
type TimelineOptions struct {
    // Time range
    StartTime time.Time
    EndTime   time.Time
    
    // Filtering
    Namespaces    []int
    Editors       []string
    ExcludeMinor  bool
    MinSizeDelta  *int
    MaxSizeDelta  *int
    
    // Grouping
    GroupBy       string // "hour", "day", "week", "month", "page", "editor"
    
    // Include flags
    IncludeContent bool
    IncludeStats   bool
    
    // Pagination
    Offset int
    Limit  int
    
    // Sorting
    SortOrder string // "asc" or "desc"
}

// TimelineChange represents a single change in the timeline
type TimelineChange struct {
    Revision      *Revision
    PageTitle     string
    ChangeType    string // "new", "edit", "minor"
    SizeDelta     int
    PrevRevID     *int64
}

// TimelineGroup represents aggregated changes
type TimelineGroup struct {
    Period        string    // ISO 8601 period or identifier
    StartTime     time.Time
    EndTime       time.Time
    Changes       []TimelineChange
    ChangeCount   int
    PagesAffected int
    Editors       []string
    TotalAdded    int
    TotalRemoved  int
}

// GetChangesByPeriod retrieves all changes in a time period
func (c *sqliteClient) GetChangesByPeriod(ctx context.Context, start, end time.Time) ([]Revision, error) {
    opts := TimelineOptions{
        StartTime: start,
        EndTime:   end,
        SortOrder: "asc",
    }
    
    changes, err := c.GetTimeline(ctx, opts)
    if err != nil {
        return nil, err
    }
    
    revisions := make([]Revision, len(changes))
    for i, change := range changes {
        revisions[i] = *change.Revision
    }
    
    return revisions, nil
}

// GetTimeline retrieves detailed timeline with filtering
func (c *sqliteClient) GetTimeline(ctx context.Context, opts TimelineOptions) ([]TimelineChange, error) {
    query := c.buildTimelineQuery(opts)
    args := c.buildTimelineArgs(opts)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, fmt.Errorf("timeline query failed: %w", err)
    }
    defer rows.Close()
    
    var changes []TimelineChange
    for rows.Next() {
        change, err := c.scanTimelineChange(rows, opts.IncludeContent)
        if err != nil {
            return nil, err
        }
        changes = append(changes, *change)
    }
    
    return changes, rows.Err()
}

// buildTimelineQuery constructs the SQL query
func (c *sqliteClient) buildTimelineQuery(opts TimelineOptions) string {
    columns := `
        r.rev_id,
        r.page_id,
        r.rev_timestamp,
        r.rev_user_text,
        r.rev_user_id,
        r.rev_comment,
        r.rev_minor_edit,
        r.content_size,
        r.sha1,
        p.page_title,
        p.page_namespace,
        COALESCE(r.content_size - prev.content_size, r.content_size) as size_delta,
        prev.rev_id as prev_rev_id
    `
    
    if opts.IncludeContent {
        columns += ", r.content"
    }
    
    query := `
        SELECT ` + columns + `
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        LEFT JOIN revisions prev ON r.page_id = prev.page_id 
            AND prev.rev_timestamp < r.rev_timestamp
        WHERE r.rev_timestamp BETWEEN ? AND ?
    `
    
    // Add filters
    if len(opts.Namespaces) > 0 {
        placeholders := strings.Repeat("?,", len(opts.Namespaces))
        placeholders = placeholders[:len(placeholders)-1]
        query += " AND p.page_namespace IN (" + placeholders + ")"
    }
    
    if len(opts.Editors) > 0 {
        placeholders := strings.Repeat("?,", len(opts.Editors))
        placeholders = placeholders[:len(placeholders)-1]
        query += " AND r.rev_user_text IN (" + placeholders + ")"
    }
    
    if opts.ExcludeMinor {
        query += " AND r.rev_minor_edit = 0"
    }
    
    if opts.MinSizeDelta != nil {
        query += " AND ABS(COALESCE(r.content_size - prev.content_size, r.content_size)) >= ?"
    }
    
    // Sorting
    if opts.SortOrder == "desc" {
        query += " ORDER BY r.rev_timestamp DESC"
    } else {
        query += " ORDER BY r.rev_timestamp ASC"
    }
    
    // Pagination
    if opts.Limit > 0 {
        query += fmt.Sprintf(" LIMIT %d OFFSET %d", opts.Limit, opts.Offset)
    }
    
    return query
}

// buildTimelineArgs constructs query arguments
func (c *sqliteClient) buildTimelineArgs(opts TimelineOptions) []interface{} {
    args := []interface{}{opts.StartTime, opts.EndTime}
    
    for _, ns := range opts.Namespaces {
        args = append(args, ns)
    }
    
    for _, editor := range opts.Editors {
        args = append(args, editor)
    }
    
    if opts.MinSizeDelta != nil {
        args = append(args, *opts.MinSizeDelta)
    }
    
    return args
}

// scanTimelineChange scans a change from a row
func (c *sqliteClient) scanTimelineChange(rows *sql.Rows, includeContent bool) (*TimelineChange, error) {
    var change TimelineChange
    change.Revision = &Revision{}
    
    var userID sql.NullInt64
    var prevRevID sql.NullInt64
    var namespace int
    
    if includeContent {
        err := rows.Scan(
            &change.Revision.ID,
            &change.Revision.PageID,
            &change.Revision.Timestamp,
            &change.Revision.Username,
            &userID,
            &change.Revision.Comment,
            &change.Revision.IsMinor,
            &change.Revision.ContentSize,
            &change.Revision.SHA1,
            &change.PageTitle,
            &namespace,
            &change.SizeDelta,
            &prevRevID,
            &change.Revision.Content,
        )
        if err != nil {
            return nil, err
        }
    } else {
        err := rows.Scan(
            &change.Revision.ID,
            &change.Revision.PageID,
            &change.Revision.Timestamp,
            &change.Revision.Username,
            &userID,
            &change.Revision.Comment,
            &change.Revision.IsMinor,
            &change.Revision.ContentSize,
            &change.Revision.SHA1,
            &change.PageTitle,
            &namespace,
            &change.SizeDelta,
            &prevRevID,
        )
        if err != nil {
            return nil, err
        }
    }
    
    if userID.Valid {
        id := userID.Int64
        change.Revision.UserID = &id
    }
    
    if prevRevID.Valid {
        id := prevRevID.Int64
        change.PrevRevID = &id
        change.ChangeType = "edit"
        if change.Revision.IsMinor {
            change.ChangeType = "minor"
        }
    } else {
        change.ChangeType = "new"
    }
    
    return &change, nil
}
```

### Grouped Timeline Queries

```go
// GetTimelineGrouped retrieves changes grouped by time period
func (c *sqliteClient) GetTimelineGrouped(ctx context.Context, opts TimelineOptions) ([]TimelineGroup, error) {
    if opts.GroupBy == "" {
        opts.GroupBy = "day"
    }
    
    query := c.buildGroupedTimelineQuery(opts)
    args := c.buildTimelineArgs(opts)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return nil, fmt.Errorf("grouped timeline query failed: %w", err)
    }
    defer rows.Close()
    
    var groups []TimelineGroup
    for rows.Next() {
        var group TimelineGroup
        err := rows.Scan(
            &group.Period,
            &group.StartTime,
            &group.ChangeCount,
            &group.PagesAffected,
            &group.TotalAdded,
            &group.TotalRemoved,
        )
        if err != nil {
            return nil, err
        }
        
        groups = append(groups, group)
    }
    
    return groups, rows.Err()
}

// buildGroupedTimelineQuery constructs aggregated query
func (c *sqliteClient) buildGroupedTimelineQuery(opts TimelineOptions) string {
    // Determine grouping format
    var groupFormat string
    switch opts.GroupBy {
    case "hour":
        groupFormat = "%Y-%m-%d %H"
    case "day":
        groupFormat = "%Y-%m-%d"
    case "week":
        groupFormat = "%Y-W%W"
    case "month":
        groupFormat = "%Y-%m"
    default:
        groupFormat = "%Y-%m-%d"
    }
    
    query := `
        SELECT 
            strftime('` + groupFormat + `', r.rev_timestamp) as period,
            MIN(r.rev_timestamp) as period_start,
            COUNT(*) as change_count,
            COUNT(DISTINCT r.page_id) as pages_affected,
            SUM(CASE WHEN r.content_size > COALESCE(prev.content_size, 0) 
                THEN r.content_size - COALESCE(prev.content_size, 0) ELSE 0 END) as total_added,
            SUM(CASE WHEN r.content_size < COALESCE(prev.content_size, 0) 
                THEN COALESCE(prev.content_size, 0) - r.content_size ELSE 0 END) as total_removed
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        LEFT JOIN revisions prev ON r.page_id = prev.page_id 
            AND prev.rev_timestamp < r.rev_timestamp
        WHERE r.rev_timestamp BETWEEN ? AND ?
    `
    
    // Add namespace filter
    if len(opts.Namespaces) > 0 {
        placeholders := strings.Repeat("?,", len(opts.Namespaces))
        placeholders = placeholders[:len(placeholders)-1]
        query += " AND p.page_namespace IN (" + placeholders + ")"
    }
    
    query += " GROUP BY period ORDER BY period"
    
    return query
}

// GetEditorActivity retrieves activity for a specific editor
func (c *sqliteClient) GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error) {
    query := `
        SELECT 
            r.rev_id, r.page_id, r.rev_timestamp,
            r.rev_user_text, r.rev_user_id, r.rev_comment,
            r.rev_minor_edit, r.content_size, r.sha1,
            p.page_title
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        WHERE r.rev_user_text = ?
          AND r.rev_timestamp BETWEEN ? AND ?
        ORDER BY r.rev_timestamp ASC
    `
    
    rows, err := c.db.QueryContext(ctx, query, username, start, end)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var revisions []Revision
    for rows.Next() {
        var rev Revision
        var userID sql.NullInt64
        
        err := rows.Scan(
            &rev.ID, &rev.PageID, &rev.Timestamp,
            &rev.Username, &userID, &rev.Comment,
            &rev.IsMinor, &rev.ContentSize, &rev.SHA1,
            &rev.PageTitle,
        )
        if err != nil {
            return nil, err
        }
        
        if userID.Valid {
            id := userID.Int64
            rev.UserID = &id
        }
        
        revisions = append(revisions, rev)
    }
    
    return revisions, rows.Err()
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 05: Data Models
- Story 10: Page History Query

## Implementation Notes

- Use index on rev_timestamp for efficient period queries
- Consider pre-computing deltas for performance
- Handle time zones consistently (use UTC)
- Large time periods may need streaming or chunking
- Consider caching for popular time periods
- Support various date formats in grouping

## Testing Requirements

- [ ] Period query tests (various ranges)
- [ ] Filtering tests (namespace, editor, size delta)
- [ ] Grouping tests (hour, day, week, month)
- [ ] Edge case tests (empty periods, single change)
- [ ] Performance tests with large periods
- [ ] Time zone handling tests
- [ ] Pagination tests

## Definition of Done

- [ ] Timeline query methods implemented
- [ ] Filtering options working
- [ ] Grouping support added
- [ ] Editor activity query working
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code reviewed and approved
