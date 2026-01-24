# Story 16: Editor Activity

**Story ID**: epic-05-story-16  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to analyze individual editor activity and contributions  
**So that** I can understand user engagement and identify key contributors

## Acceptance Criteria

1. **Activity Queries**
   - [ ] Get all edits by a specific user
   - [ ] Get edits within a date range
   - [ ] Filter by namespace and page
   - [ ] Support pagination for prolific editors

2. **Contribution Statistics**
   - [ ] Total edit count
   - [ ] First and last edit dates
   - [ ] Pages edited count
   - [ ] Content contribution (bytes added/removed)

3. **Activity Patterns**
   - [ ] Edits by day of week
   - [ ] Edits by hour of day
   - [ ] Edits by month/year
   - [ ] Activity intensity over time

4. **Comparison Features**
   - [ ] Compare multiple editors
   - [ ] Rank editors by various metrics
   - [ ] Identify editing clusters
   - [ ] Collaboration detection (co-editing same pages)

## Technical Details

### Editor Activity Structures

```go
package irowiki

import "time"

// EditorActivity contains comprehensive editor statistics
type EditorActivity struct {
    Username          string    `json:"username"`
    UserID            *int64    `json:"user_id,omitempty"`
    IsAnonymous       bool      `json:"is_anonymous"`
    
    // Basic stats
    TotalEdits        int       `json:"total_edits"`
    FirstEdit         time.Time `json:"first_edit"`
    LastEdit          time.Time `json:"last_edit"`
    ActiveDays        int       `json:"active_days"`
    
    // Content stats
    PagesEdited       int       `json:"pages_edited"`
    PagesCreated      int       `json:"pages_created"`
    MinorEdits        int       `json:"minor_edits"`
    BytesAdded        int64     `json:"bytes_added"`
    BytesRemoved      int64     `json:"bytes_removed"`
    NetContribution   int64     `json:"net_contribution"`
    
    // Activity patterns
    EditsByHour       map[int]int    `json:"edits_by_hour"`
    EditsByDay        map[string]int `json:"edits_by_day"`
    EditsByMonth      map[string]int `json:"edits_by_month"`
    BusiestHour       int            `json:"busiest_hour"`
    BusiestDay        string         `json:"busiest_day"`
    
    // Top pages
    TopPages          []PageEditStat `json:"top_pages"`
    
    // Collaboration
    Collaborators     []string       `json:"collaborators,omitempty"`
}

// PageEditStat represents editing statistics for a page
type PageEditStat struct {
    PageID        int64     `json:"page_id"`
    PageTitle     string    `json:"page_title"`
    EditCount     int       `json:"edit_count"`
    FirstEdit     time.Time `json:"first_edit"`
    LastEdit      time.Time `json:"last_edit"`
    BytesAdded    int       `json:"bytes_added"`
    BytesRemoved  int       `json:"bytes_removed"`
}

// EditorComparison compares multiple editors
type EditorComparison struct {
    Editors           []string                `json:"editors"`
    ComparisonMetrics map[string]EditorMetric `json:"metrics"`
    CommonPages       []string                `json:"common_pages"`
    Timeline          []TimelinePoint         `json:"timeline"`
}

// EditorMetric contains a metric value for each editor
type EditorMetric struct {
    Name   string             `json:"name"`
    Values map[string]float64 `json:"values"` // username -> value
}

// TimelinePoint represents activity at a point in time
type TimelinePoint struct {
    Date   time.Time         `json:"date"`
    Counts map[string]int    `json:"counts"` // username -> edit count
}

// EditorActivityOptions configures activity queries
type EditorActivityOptions struct {
    StartDate         *time.Time
    EndDate           *time.Time
    Namespace         *int
    PageTitle         string
    IncludePatterns   bool
    IncludeTopPages   bool
    IncludeCollaborators bool
    TopN              int
}
```

### GetEditorActivity Implementation

```go
// GetEditorActivity retrieves comprehensive activity for an editor
func (c *sqliteClient) GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error) {
    opts := EditorActivityOptions{
        StartDate:         &start,
        EndDate:           &end,
        IncludePatterns:   true,
        IncludeTopPages:   true,
        IncludeCollaborators: true,
        TopN:              10,
    }
    
    activity, err := c.GetEditorActivityDetailed(ctx, username, opts)
    if err != nil {
        return nil, err
    }
    
    // Convert to simple revision list for backward compatibility
    return c.getEditorRevisions(ctx, username, start, end)
}

// GetEditorActivityDetailed retrieves detailed editor activity
func (c *sqliteClient) GetEditorActivityDetailed(ctx context.Context, username string, opts EditorActivityOptions) (*EditorActivity, error) {
    activity := &EditorActivity{
        Username: username,
    }
    
    // Get basic statistics
    if err := c.getEditorBasicStats(ctx, activity, opts); err != nil {
        return nil, fmt.Errorf("failed to get basic stats: %w", err)
    }
    
    // Get content statistics
    if err := c.getEditorContentStats(ctx, activity, opts); err != nil {
        return nil, fmt.Errorf("failed to get content stats: %w", err)
    }
    
    // Get activity patterns
    if opts.IncludePatterns {
        if err := c.getEditorActivityPatterns(ctx, activity, opts); err != nil {
            return nil, fmt.Errorf("failed to get activity patterns: %w", err)
        }
    }
    
    // Get top pages
    if opts.IncludeTopPages {
        if err := c.getEditorTopPages(ctx, activity, opts); err != nil {
            return nil, fmt.Errorf("failed to get top pages: %w", err)
        }
    }
    
    // Get collaborators
    if opts.IncludeCollaborators {
        if err := c.getEditorCollaborators(ctx, activity, opts); err != nil {
            return nil, fmt.Errorf("failed to get collaborators: %w", err)
        }
    }
    
    return activity, nil
}

// getEditorBasicStats retrieves basic editor statistics
func (c *sqliteClient) getEditorBasicStats(ctx context.Context, activity *EditorActivity, opts EditorActivityOptions) error {
    query := `
        SELECT 
            COUNT(*) as total_edits,
            MIN(rev_timestamp) as first_edit,
            MAX(rev_timestamp) as last_edit,
            COUNT(DISTINCT DATE(rev_timestamp)) as active_days,
            rev_user_id
        FROM revisions
        WHERE rev_user_text = ?
    `
    
    args := []interface{}{activity.Username}
    
    // Add date filters
    if opts.StartDate != nil {
        query += " AND rev_timestamp >= ?"
        args = append(args, *opts.StartDate)
    }
    if opts.EndDate != nil {
        query += " AND rev_timestamp <= ?"
        args = append(args, *opts.EndDate)
    }
    
    query += " GROUP BY rev_user_id"
    
    var userID sql.NullInt64
    err := c.db.QueryRowContext(ctx, query, args...).Scan(
        &activity.TotalEdits,
        &activity.FirstEdit,
        &activity.LastEdit,
        &activity.ActiveDays,
        &userID,
    )
    
    if err == sql.ErrNoRows {
        return ErrNotFound
    }
    if err != nil {
        return err
    }
    
    if userID.Valid {
        id := userID.Int64
        activity.UserID = &id
        activity.IsAnonymous = false
    } else {
        activity.IsAnonymous = true
    }
    
    return nil
}

// getEditorContentStats retrieves content contribution statistics
func (c *sqliteClient) getEditorContentStats(ctx context.Context, activity *EditorActivity, opts EditorActivityOptions) error {
    query := `
        SELECT 
            COUNT(DISTINCT r.page_id) as pages_edited,
            SUM(CASE WHEN r.rev_minor_edit = 1 THEN 1 ELSE 0 END) as minor_edits,
            SUM(CASE WHEN prev.rev_id IS NULL THEN 1 ELSE 0 END) as pages_created,
            SUM(CASE WHEN r.content_size > COALESCE(prev.content_size, 0) 
                THEN r.content_size - COALESCE(prev.content_size, 0) ELSE 0 END) as bytes_added,
            SUM(CASE WHEN r.content_size < COALESCE(prev.content_size, 0) 
                THEN COALESCE(prev.content_size, 0) - r.content_size ELSE 0 END) as bytes_removed
        FROM revisions r
        LEFT JOIN revisions prev ON r.page_id = prev.page_id
            AND prev.rev_timestamp < r.rev_timestamp
            AND prev.rev_timestamp = (
                SELECT MAX(rev_timestamp)
                FROM revisions
                WHERE page_id = r.page_id AND rev_timestamp < r.rev_timestamp
            )
        WHERE r.rev_user_text = ?
    `
    
    args := []interface{}{activity.Username}
    
    if opts.StartDate != nil {
        query += " AND r.rev_timestamp >= ?"
        args = append(args, *opts.StartDate)
    }
    if opts.EndDate != nil {
        query += " AND r.rev_timestamp <= ?"
        args = append(args, *opts.EndDate)
    }
    if opts.Namespace != nil {
        query += " AND EXISTS (SELECT 1 FROM pages p WHERE p.page_id = r.page_id AND p.page_namespace = ?)"
        args = append(args, *opts.Namespace)
    }
    
    err := c.db.QueryRowContext(ctx, query, args...).Scan(
        &activity.PagesEdited,
        &activity.MinorEdits,
        &activity.PagesCreated,
        &activity.BytesAdded,
        &activity.BytesRemoved,
    )
    
    if err != nil {
        return err
    }
    
    activity.NetContribution = activity.BytesAdded - activity.BytesRemoved
    
    return nil
}

// getEditorActivityPatterns retrieves activity patterns
func (c *sqliteClient) getEditorActivityPatterns(ctx context.Context, activity *EditorActivity, opts EditorActivityOptions) error {
    query := `
        SELECT 
            CAST(strftime('%H', rev_timestamp) AS INTEGER) as hour,
            strftime('%w', rev_timestamp) as day_of_week,
            strftime('%Y-%m', rev_timestamp) as month,
            COUNT(*) as count
        FROM revisions
        WHERE rev_user_text = ?
    `
    
    args := []interface{}{activity.Username}
    
    if opts.StartDate != nil {
        query += " AND rev_timestamp >= ?"
        args = append(args, *opts.StartDate)
    }
    if opts.EndDate != nil {
        query += " AND rev_timestamp <= ?"
        args = append(args, *opts.EndDate)
    }
    
    query += " GROUP BY hour, day_of_week, month"
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    activity.EditsByHour = make(map[int]int)
    activity.EditsByDay = make(map[string]int)
    activity.EditsByMonth = make(map[string]int)
    
    dayNames := []string{"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}
    maxHourCount := 0
    maxDayCount := 0
    
    for rows.Next() {
        var hour int
        var dayOfWeek, month string
        var count int
        
        if err := rows.Scan(&hour, &dayOfWeek, &month, &count); err != nil {
            return err
        }
        
        activity.EditsByHour[hour] += count
        if activity.EditsByHour[hour] > maxHourCount {
            maxHourCount = activity.EditsByHour[hour]
            activity.BusiestHour = hour
        }
        
        dayIdx, _ := strconv.Atoi(dayOfWeek)
        dayName := dayNames[dayIdx]
        activity.EditsByDay[dayName] += count
        if activity.EditsByDay[dayName] > maxDayCount {
            maxDayCount = activity.EditsByDay[dayName]
            activity.BusiestDay = dayName
        }
        
        activity.EditsByMonth[month] += count
    }
    
    return rows.Err()
}

// getEditorTopPages retrieves top pages edited by the editor
func (c *sqliteClient) getEditorTopPages(ctx context.Context, activity *EditorActivity, opts EditorActivityOptions) error {
    query := fmt.Sprintf(`
        SELECT 
            r.page_id,
            p.page_title,
            COUNT(*) as edit_count,
            MIN(r.rev_timestamp) as first_edit,
            MAX(r.rev_timestamp) as last_edit,
            SUM(CASE WHEN r.content_size > COALESCE(prev.content_size, 0) 
                THEN r.content_size - COALESCE(prev.content_size, 0) ELSE 0 END) as bytes_added,
            SUM(CASE WHEN r.content_size < COALESCE(prev.content_size, 0) 
                THEN COALESCE(prev.content_size, 0) - r.content_size ELSE 0 END) as bytes_removed
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        LEFT JOIN revisions prev ON r.page_id = prev.page_id
            AND prev.rev_timestamp < r.rev_timestamp
            AND prev.rev_timestamp = (
                SELECT MAX(rev_timestamp)
                FROM revisions
                WHERE page_id = r.page_id AND rev_timestamp < r.rev_timestamp
            )
        WHERE r.rev_user_text = ?
    `)
    
    args := []interface{}{activity.Username}
    
    if opts.StartDate != nil {
        query += " AND r.rev_timestamp >= ?"
        args = append(args, *opts.StartDate)
    }
    if opts.EndDate != nil {
        query += " AND r.rev_timestamp <= ?"
        args = append(args, *opts.EndDate)
    }
    if opts.Namespace != nil {
        query += " AND p.page_namespace = ?"
        args = append(args, *opts.Namespace)
    }
    
    query += fmt.Sprintf(`
        GROUP BY r.page_id
        ORDER BY edit_count DESC
        LIMIT %d
    `, opts.TopN)
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    activity.TopPages = make([]PageEditStat, 0, opts.TopN)
    for rows.Next() {
        var pageStat PageEditStat
        err := rows.Scan(
            &pageStat.PageID,
            &pageStat.PageTitle,
            &pageStat.EditCount,
            &pageStat.FirstEdit,
            &pageStat.LastEdit,
            &pageStat.BytesAdded,
            &pageStat.BytesRemoved,
        )
        if err != nil {
            return err
        }
        activity.TopPages = append(activity.TopPages, pageStat)
    }
    
    return rows.Err()
}

// getEditorCollaborators finds other editors who worked on the same pages
func (c *sqliteClient) getEditorCollaborators(ctx context.Context, activity *EditorActivity, opts EditorActivityOptions) error {
    query := `
        SELECT DISTINCT r2.rev_user_text
        FROM revisions r1
        JOIN revisions r2 ON r1.page_id = r2.page_id
        WHERE r1.rev_user_text = ?
          AND r2.rev_user_text != ?
          AND r2.rev_user_text IS NOT NULL
        GROUP BY r2.rev_user_text
        ORDER BY COUNT(*) DESC
        LIMIT 10
    `
    
    rows, err := c.db.QueryContext(ctx, query, activity.Username, activity.Username)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    activity.Collaborators = make([]string, 0)
    for rows.Next() {
        var collaborator string
        if err := rows.Scan(&collaborator); err != nil {
            return err
        }
        activity.Collaborators = append(activity.Collaborators, collaborator)
    }
    
    return rows.Err()
}

// CompareEditors compares activity of multiple editors
func (c *sqliteClient) CompareEditors(ctx context.Context, usernames []string, start, end time.Time) (*EditorComparison, error) {
    comparison := &EditorComparison{
        Editors:           usernames,
        ComparisonMetrics: make(map[string]EditorMetric),
    }
    
    // Get metrics for each editor
    metrics := []string{"total_edits", "pages_edited", "bytes_added", "bytes_removed"}
    
    for _, metric := range metrics {
        values := make(map[string]float64)
        
        for _, username := range usernames {
            activity, err := c.GetEditorActivityDetailed(ctx, username, EditorActivityOptions{
                StartDate: &start,
                EndDate:   &end,
            })
            
            if err != nil {
                continue
            }
            
            switch metric {
            case "total_edits":
                values[username] = float64(activity.TotalEdits)
            case "pages_edited":
                values[username] = float64(activity.PagesEdited)
            case "bytes_added":
                values[username] = float64(activity.BytesAdded)
            case "bytes_removed":
                values[username] = float64(activity.BytesRemoved)
            }
        }
        
        comparison.ComparisonMetrics[metric] = EditorMetric{
            Name:   metric,
            Values: values,
        }
    }
    
    // Find common pages
    if err := c.findCommonPages(ctx, comparison, usernames); err != nil {
        return nil, err
    }
    
    return comparison, nil
}

// findCommonPages finds pages edited by all specified editors
func (c *sqliteClient) findCommonPages(ctx context.Context, comparison *EditorComparison, usernames []string) error {
    if len(usernames) == 0 {
        return nil
    }
    
    // Build query to find pages edited by all users
    query := `
        SELECT DISTINCT p.page_title
        FROM pages p
        WHERE 1=1
    `
    
    for range usernames {
        query += ` AND EXISTS (
            SELECT 1 FROM revisions r 
            WHERE r.page_id = p.page_id AND r.rev_user_text = ?
        )`
    }
    
    query += " LIMIT 20"
    
    args := make([]interface{}, len(usernames))
    for i, username := range usernames {
        args[i] = username
    }
    
    rows, err := c.db.QueryContext(ctx, query, args...)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    comparison.CommonPages = make([]string, 0)
    for rows.Next() {
        var title string
        if err := rows.Scan(&title); err != nil {
            return err
        }
        comparison.CommonPages = append(comparison.CommonPages, title)
    }
    
    return rows.Err()
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 03: PostgreSQL Backend
- Story 05: Data Models
- Story 10: Page History Query
- Story 12: Timeline Changes Query

## Implementation Notes

- Editor activity queries can be expensive for prolific editors
- Consider implementing result caching for frequently queried editors
- Activity patterns are useful for identifying bot vs human editors
- Collaboration detection helps identify working relationships
- Time zone handling is important for hour-of-day analysis
- Anonymous editors identified by lack of user ID

## Testing Requirements

- [ ] Basic activity query tests
- [ ] Date range filtering tests
- [ ] Content statistics tests
- [ ] Activity pattern tests (hour, day, month)
- [ ] Top pages tests
- [ ] Collaborator detection tests
- [ ] Editor comparison tests
- [ ] Edge cases (single edit, anonymous user)
- [ ] Performance tests with prolific editors
- [ ] Pagination tests

## Definition of Done

- [ ] GetEditorActivity implemented for both backends
- [ ] All statistics components working
- [ ] Activity patterns calculated correctly
- [ ] Editor comparison working
- [ ] Collaboration detection implemented
- [ ] All tests passing
- [ ] Performance acceptable (<500ms per editor)
- [ ] Documentation complete
- [ ] Code reviewed and approved
