# Story 14: Archive Statistics

**Story ID**: epic-05-story-14  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to retrieve comprehensive statistics about the entire wiki archive  
**So that** I can understand the scope and characteristics of the archived content

## Acceptance Criteria

1. **Basic Statistics**
   - [ ] Total number of pages
   - [ ] Total number of revisions
   - [ ] Total number of files
   - [ ] Total number of unique editors

2. **Temporal Statistics**
   - [ ] First edit timestamp
   - [ ] Last edit timestamp
   - [ ] Archive date range
   - [ ] Active editors in last 30 days

3. **Size Statistics**
   - [ ] Total content size in bytes
   - [ ] Database file size
   - [ ] Average page size
   - [ ] Largest/smallest pages

4. **Distribution Statistics**
   - [ ] Pages by namespace
   - [ ] Edits by month/year
   - [ ] Top editors by edit count
   - [ ] Most edited pages

## Technical Details

### Statistics Structure

```go
package irowiki

import "time"

// Statistics contains aggregate archive statistics
type Statistics struct {
    // Counts
    TotalPages      int `json:"total_pages"`
    TotalRevisions  int `json:"total_revisions"`
    TotalFiles      int `json:"total_files"`
    TotalEditors    int `json:"total_editors"`
    
    // Temporal
    FirstEdit       time.Time `json:"first_edit"`
    LastEdit        time.Time `json:"last_edit"`
    ArchiveDuration string    `json:"archive_duration"` // Human-readable
    ActiveEditors   int       `json:"active_editors"`   // Last 30 days
    
    // Size
    TotalContentSize int64   `json:"total_content_size"`
    DatabaseSize     int64   `json:"database_size"`
    AveragePageSize  int     `json:"average_page_size"`
    MedianPageSize   int     `json:"median_page_size"`
    
    // Distribution
    NamespaceDistribution map[int]int      `json:"namespace_distribution"`
    EditsByMonth          map[string]int   `json:"edits_by_month"`
    TopEditors            []EditorStat     `json:"top_editors"`
    MostEditedPages       []PageStat       `json:"most_edited_pages"`
    
    // Extremes
    LargestPage  *PageInfo `json:"largest_page,omitempty"`
    SmallestPage *PageInfo `json:"smallest_page,omitempty"`
}

// PageInfo contains basic page information
type PageInfo struct {
    ID        int64  `json:"id"`
    Title     string `json:"title"`
    Namespace int    `json:"namespace"`
    Size      int    `json:"size"`
}

// PageStat contains page statistics
type PageStat struct {
    PageID        int64  `json:"page_id"`
    PageTitle     string `json:"page_title"`
    RevisionCount int    `json:"revision_count"`
    EditorCount   int    `json:"editor_count"`
}

// StatisticsOptions configures statistics queries
type StatisticsOptions struct {
    IncludeDistribution bool
    IncludeTopEditors   bool
    IncludeMostEdited   bool
    TopN                int // Number of top items to include
}
```

### GetStatistics Implementation

```go
// GetStatistics retrieves comprehensive archive statistics
func (c *sqliteClient) GetStatistics(ctx context.Context) (*Statistics, error) {
    opts := StatisticsOptions{
        IncludeDistribution: true,
        IncludeTopEditors:   true,
        IncludeMostEdited:   true,
        TopN:                10,
    }
    
    return c.GetStatisticsWithOptions(ctx, opts)
}

// GetStatisticsWithOptions retrieves statistics with custom options
func (c *sqliteClient) GetStatisticsWithOptions(ctx context.Context, opts StatisticsOptions) (*Statistics, error) {
    stats := &Statistics{}
    
    // Get basic counts
    if err := c.getBasicCounts(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get basic counts: %w", err)
    }
    
    // Get temporal statistics
    if err := c.getTemporalStats(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get temporal stats: %w", err)
    }
    
    // Get size statistics
    if err := c.getSizeStats(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get size stats: %w", err)
    }
    
    // Optional: distribution statistics
    if opts.IncludeDistribution {
        if err := c.getDistributionStats(ctx, stats); err != nil {
            return nil, fmt.Errorf("failed to get distribution stats: %w", err)
        }
    }
    
    // Optional: top editors
    if opts.IncludeTopEditors {
        if err := c.getTopEditors(ctx, stats, opts.TopN); err != nil {
            return nil, fmt.Errorf("failed to get top editors: %w", err)
        }
    }
    
    // Optional: most edited pages
    if opts.IncludeMostEdited {
        if err := c.getMostEditedPages(ctx, stats, opts.TopN); err != nil {
            return nil, fmt.Errorf("failed to get most edited pages: %w", err)
        }
    }
    
    // Get extremes
    if err := c.getExtremePages(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get extreme pages: %w", err)
    }
    
    return stats, nil
}

// getBasicCounts retrieves basic count statistics
func (c *sqliteClient) getBasicCounts(ctx context.Context, stats *Statistics) error {
    const query = `
        SELECT 
            (SELECT COUNT(*) FROM pages) as total_pages,
            (SELECT COUNT(*) FROM revisions) as total_revisions,
            (SELECT COUNT(*) FROM files) as total_files,
            (SELECT COUNT(DISTINCT rev_user_text) FROM revisions) as total_editors
    `
    
    return c.db.QueryRowContext(ctx, query).Scan(
        &stats.TotalPages,
        &stats.TotalRevisions,
        &stats.TotalFiles,
        &stats.TotalEditors,
    )
}

// getTemporalStats retrieves temporal statistics
func (c *sqliteClient) getTemporalStats(ctx context.Context, stats *Statistics) error {
    const query = `
        SELECT 
            MIN(rev_timestamp) as first_edit,
            MAX(rev_timestamp) as last_edit
        FROM revisions
    `
    
    err := c.db.QueryRowContext(ctx, query).Scan(&stats.FirstEdit, &stats.LastEdit)
    if err != nil {
        return err
    }
    
    // Calculate duration
    duration := stats.LastEdit.Sub(stats.FirstEdit)
    years := int(duration.Hours() / 24 / 365)
    days := int(duration.Hours() / 24)
    
    if years > 0 {
        stats.ArchiveDuration = fmt.Sprintf("%d years, %d days", years, days%365)
    } else {
        stats.ArchiveDuration = fmt.Sprintf("%d days", days)
    }
    
    // Active editors (last 30 days)
    const activeQuery = `
        SELECT COUNT(DISTINCT rev_user_text)
        FROM revisions
        WHERE rev_timestamp >= datetime('now', '-30 days')
    `
    
    return c.db.QueryRowContext(ctx, activeQuery).Scan(&stats.ActiveEditors)
}

// getSizeStats retrieves size statistics
func (c *sqliteClient) getSizeStats(ctx context.Context, stats *Statistics) error {
    const query = `
        SELECT 
            COALESCE(SUM(content_size), 0) as total_size,
            COALESCE(AVG(content_size), 0) as avg_size
        FROM revisions r
        JOIN pages p ON r.rev_id = p.page_latest
    `
    
    var avgSize float64
    err := c.db.QueryRowContext(ctx, query).Scan(&stats.TotalContentSize, &avgSize)
    if err != nil {
        return err
    }
    
    stats.AveragePageSize = int(avgSize)
    
    // Get database file size
    if dbPath, ok := c.getDBPath(); ok {
        if info, err := os.Stat(dbPath); err == nil {
            stats.DatabaseSize = info.Size()
        }
    }
    
    // Get median page size
    const medianQuery = `
        SELECT content_size
        FROM revisions r
        JOIN pages p ON r.rev_id = p.page_latest
        ORDER BY content_size
        LIMIT 1 OFFSET (
            SELECT COUNT(*) / 2 FROM pages
        )
    `
    
    c.db.QueryRowContext(ctx, medianQuery).Scan(&stats.MedianPageSize)
    
    return nil
}

// getDistributionStats retrieves distribution statistics
func (c *sqliteClient) getDistributionStats(ctx context.Context, stats *Statistics) error {
    // Namespace distribution
    const nsQuery = `
        SELECT page_namespace, COUNT(*)
        FROM pages
        GROUP BY page_namespace
        ORDER BY page_namespace
    `
    
    rows, err := c.db.QueryContext(ctx, nsQuery)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.NamespaceDistribution = make(map[int]int)
    for rows.Next() {
        var ns, count int
        if err := rows.Scan(&ns, &count); err != nil {
            return err
        }
        stats.NamespaceDistribution[ns] = count
    }
    
    // Edits by month
    const monthQuery = `
        SELECT 
            strftime('%Y-%m', rev_timestamp) as month,
            COUNT(*) as edit_count
        FROM revisions
        GROUP BY month
        ORDER BY month
    `
    
    rows, err = c.db.QueryContext(ctx, monthQuery)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.EditsByMonth = make(map[string]int)
    for rows.Next() {
        var month string
        var count int
        if err := rows.Scan(&month, &count); err != nil {
            return err
        }
        stats.EditsByMonth[month] = count
    }
    
    return rows.Err()
}

// getTopEditors retrieves top N editors by edit count
func (c *sqliteClient) getTopEditors(ctx context.Context, stats *Statistics, n int) error {
    query := fmt.Sprintf(`
        SELECT 
            rev_user_text as username,
            COUNT(*) as edit_count,
            MIN(rev_timestamp) as first_edit,
            MAX(rev_timestamp) as last_edit,
            SUM(CASE WHEN rev_minor_edit = 1 THEN 1 ELSE 0 END) as minor_edits
        FROM revisions
        GROUP BY rev_user_text
        ORDER BY edit_count DESC
        LIMIT %d
    `, n)
    
    rows, err := c.db.QueryContext(ctx, query)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.TopEditors = make([]EditorStat, 0, n)
    for rows.Next() {
        var editor EditorStat
        err := rows.Scan(
            &editor.Username,
            &editor.EditCount,
            &editor.FirstEdit,
            &editor.LastEdit,
            &editor.MinorEdits,
        )
        if err != nil {
            return err
        }
        stats.TopEditors = append(stats.TopEditors, editor)
    }
    
    return rows.Err()
}

// getMostEditedPages retrieves top N most edited pages
func (c *sqliteClient) getMostEditedPages(ctx context.Context, stats *Statistics, n int) error {
    query := fmt.Sprintf(`
        SELECT 
            p.page_id,
            p.page_title,
            COUNT(*) as revision_count,
            COUNT(DISTINCT r.rev_user_text) as editor_count
        FROM pages p
        JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.page_id
        ORDER BY revision_count DESC
        LIMIT %d
    `, n)
    
    rows, err := c.db.QueryContext(ctx, query)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.MostEditedPages = make([]PageStat, 0, n)
    for rows.Next() {
        var pageStat PageStat
        err := rows.Scan(
            &pageStat.PageID,
            &pageStat.PageTitle,
            &pageStat.RevisionCount,
            &pageStat.EditorCount,
        )
        if err != nil {
            return err
        }
        stats.MostEditedPages = append(stats.MostEditedPages, pageStat)
    }
    
    return rows.Err()
}

// getExtremePages retrieves largest and smallest pages
func (c *sqliteClient) getExtremePages(ctx context.Context, stats *Statistics) error {
    // Largest page
    const largestQuery = `
        SELECT p.page_id, p.page_title, p.page_namespace, r.content_size
        FROM pages p
        JOIN revisions r ON p.page_latest = r.rev_id
        ORDER BY r.content_size DESC
        LIMIT 1
    `
    
    var largest PageInfo
    err := c.db.QueryRowContext(ctx, largestQuery).Scan(
        &largest.ID,
        &largest.Title,
        &largest.Namespace,
        &largest.Size,
    )
    if err == nil {
        stats.LargestPage = &largest
    }
    
    // Smallest page
    const smallestQuery = `
        SELECT p.page_id, p.page_title, p.page_namespace, r.content_size
        FROM pages p
        JOIN revisions r ON p.page_latest = r.rev_id
        WHERE r.content_size > 0
        ORDER BY r.content_size ASC
        LIMIT 1
    `
    
    var smallest PageInfo
    err = c.db.QueryRowContext(ctx, smallestQuery).Scan(
        &smallest.ID,
        &smallest.Title,
        &smallest.Namespace,
        &smallest.Size,
    )
    if err == nil {
        stats.SmallestPage = &smallest
    }
    
    return nil
}
```

### Helper Methods

```go
// FormatSize returns a human-readable size string
func FormatSize(bytes int64) string {
    const unit = 1024
    if bytes < unit {
        return fmt.Sprintf("%d B", bytes)
    }
    
    div, exp := int64(unit), 0
    for n := bytes / unit; n >= unit; n /= unit {
        div *= unit
        exp++
    }
    
    units := []string{"KB", "MB", "GB", "TB"}
    return fmt.Sprintf("%.1f %s", float64(bytes)/float64(div), units[exp])
}

// Summary returns a human-readable summary
func (s *Statistics) Summary() string {
    return fmt.Sprintf(
        "Archive contains %d pages, %d revisions, %d files by %d editors over %s",
        s.TotalPages,
        s.TotalRevisions,
        s.TotalFiles,
        s.TotalEditors,
        s.ArchiveDuration,
    )
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 03: PostgreSQL Backend
- Story 05: Data Models
- Epic 02: Database Schema

## Implementation Notes

- Consider caching statistics (they're expensive to compute)
- Some statistics can be pre-computed during database creation
- For large archives, consider approximations for median
- Database size query is filesystem-specific
- PostgreSQL queries will differ slightly (use standard SQL)
- Consider providing progress callbacks for long queries

## Testing Requirements

- [ ] Basic count tests
- [ ] Temporal statistics tests
- [ ] Size calculation tests
- [ ] Distribution statistics tests
- [ ] Top editors tests
- [ ] Most edited pages tests
- [ ] Extreme pages tests
- [ ] Performance tests with large datasets
- [ ] Empty database edge case tests

## Definition of Done

- [ ] GetStatistics implemented for both backends
- [ ] All statistics components working
- [ ] Options for customizing statistics
- [ ] Helper methods for formatting
- [ ] All tests passing
- [ ] Performance acceptable (<1s for full stats)
- [ ] Documentation complete
- [ ] Code reviewed and approved
