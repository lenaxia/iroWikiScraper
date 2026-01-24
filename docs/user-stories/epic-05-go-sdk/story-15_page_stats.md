# Story 15: Page Statistics

**Story ID**: epic-05-story-15  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 5 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to retrieve detailed statistics for individual wiki pages  
**So that** I can analyze page activity, contributors, and evolution over time

## Acceptance Criteria

1. **Revision Statistics**
   - [ ] Total revision count
   - [ ] Date of first and last edit
   - [ ] Average time between edits
   - [ ] Revision frequency over time

2. **Contributor Statistics**
   - [ ] Number of unique contributors
   - [ ] Top contributors by edit count
   - [ ] Contribution distribution
   - [ ] Anonymous vs registered editor ratio

3. **Content Statistics**
   - [ ] Current page size
   - [ ] Size growth over time
   - [ ] Largest/smallest revision sizes
   - [ ] Net change in content size

4. **Quality Metrics**
   - [ ] Minor edit percentage
   - [ ] Average edit comment length
   - [ ] Revert detection
   - [ ] Edit stability score

## Technical Details

### PageStatistics Structure

```go
package irowiki

import "time"

// PageStatistics contains comprehensive statistics for a page
type PageStatistics struct {
    // Basic info
    PageID        int64     `json:"page_id"`
    PageTitle     string    `json:"page_title"`
    PageNamespace int       `json:"page_namespace"`
    
    // Revision stats
    RevisionCount     int           `json:"revision_count"`
    FirstEdit         time.Time     `json:"first_edit"`
    LastEdit          time.Time     `json:"last_edit"`
    AvgTimeBetween    time.Duration `json:"avg_time_between_edits"`
    EditFrequency     map[string]int `json:"edit_frequency"` // Month -> count
    
    // Contributor stats
    EditorCount       int              `json:"editor_count"`
    AnonEditors       int              `json:"anon_editors"`
    RegisteredEditors int              `json:"registered_editors"`
    TopContributors   []ContributorStat `json:"top_contributors"`
    
    // Size stats
    CurrentSize       int              `json:"current_size"`
    OriginalSize      int              `json:"original_size"`
    MaxSize           int              `json:"max_size"`
    MinSize           int              `json:"min_size"`
    AvgSize           int              `json:"avg_size"`
    SizeGrowth        []SizePoint      `json:"size_growth"`
    
    // Quality metrics
    MinorEditPercent  float64          `json:"minor_edit_percent"`
    AvgCommentLength  float64          `json:"avg_comment_length"`
    RevertCount       int              `json:"revert_count"`
    StabilityScore    float64          `json:"stability_score"`
    
    // Activity patterns
    BusiestMonth      string           `json:"busiest_month,omitempty"`
    BusiestYear       string           `json:"busiest_year,omitempty"`
    LongestGap        time.Duration    `json:"longest_gap"`
}

// ContributorStat represents a contributor's statistics
type ContributorStat struct {
    Username       string    `json:"username"`
    EditCount      int       `json:"edit_count"`
    FirstEdit      time.Time `json:"first_edit"`
    LastEdit       time.Time `json:"last_edit"`
    BytesAdded     int       `json:"bytes_added"`
    BytesRemoved   int       `json:"bytes_removed"`
    MinorEdits     int       `json:"minor_edits"`
    Percentage     float64   `json:"percentage"`
}

// SizePoint represents page size at a point in time
type SizePoint struct {
    Timestamp time.Time `json:"timestamp"`
    Size      int       `json:"size"`
    Delta     int       `json:"delta"`
}

// PageStatsOptions configures page statistics queries
type PageStatsOptions struct {
    IncludeSizeGrowth  bool
    IncludeTopEditors  bool
    IncludeFrequency   bool
    TopN               int
    GrowthSampleSize   int // Number of points in size growth
}
```

### GetPageStats Implementation

```go
// GetPageStats retrieves statistics for a specific page
func (c *sqliteClient) GetPageStats(ctx context.Context, title string) (*PageStatistics, error) {
    opts := PageStatsOptions{
        IncludeSizeGrowth: true,
        IncludeTopEditors: true,
        IncludeFrequency:  true,
        TopN:              5,
        GrowthSampleSize:  50,
    }
    
    return c.GetPageStatsWithOptions(ctx, title, opts)
}

// GetPageStatsWithOptions retrieves page statistics with custom options
func (c *sqliteClient) GetPageStatsWithOptions(ctx context.Context, title string, opts PageStatsOptions) (*PageStatistics, error) {
    // Get page
    page, err := c.GetPage(ctx, title)
    if err != nil {
        return nil, err
    }
    
    stats := &PageStatistics{
        PageID:        page.ID,
        PageTitle:     page.Title,
        PageNamespace: page.Namespace,
    }
    
    // Get basic revision statistics
    if err := c.getRevisionStats(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get revision stats: %w", err)
    }
    
    // Get contributor statistics
    if err := c.getContributorStats(ctx, stats, opts.TopN); err != nil {
        return nil, fmt.Errorf("failed to get contributor stats: %w", err)
    }
    
    // Get size statistics
    if err := c.getSizeStatsForPage(ctx, stats, opts.IncludeSizeGrowth, opts.GrowthSampleSize); err != nil {
        return nil, fmt.Errorf("failed to get size stats: %w", err)
    }
    
    // Get quality metrics
    if err := c.getQualityMetrics(ctx, stats); err != nil {
        return nil, fmt.Errorf("failed to get quality metrics: %w", err)
    }
    
    // Get activity patterns
    if opts.IncludeFrequency {
        if err := c.getActivityPatterns(ctx, stats); err != nil {
            return nil, fmt.Errorf("failed to get activity patterns: %w", err)
        }
    }
    
    return stats, nil
}

// getRevisionStats retrieves basic revision statistics
func (c *sqliteClient) getRevisionStats(ctx context.Context, stats *PageStatistics) error {
    const query = `
        SELECT 
            COUNT(*) as revision_count,
            MIN(rev_timestamp) as first_edit,
            MAX(rev_timestamp) as last_edit
        FROM revisions
        WHERE page_id = ?
    `
    
    err := c.db.QueryRowContext(ctx, query, stats.PageID).Scan(
        &stats.RevisionCount,
        &stats.FirstEdit,
        &stats.LastEdit,
    )
    
    if err != nil {
        return err
    }
    
    // Calculate average time between edits
    if stats.RevisionCount > 1 {
        totalTime := stats.LastEdit.Sub(stats.FirstEdit)
        stats.AvgTimeBetween = totalTime / time.Duration(stats.RevisionCount-1)
    }
    
    return nil
}

// getContributorStats retrieves contributor statistics
func (c *sqliteClient) getContributorStats(ctx context.Context, stats *PageStatistics, topN int) error {
    // Count editors
    const countQuery = `
        SELECT 
            COUNT(DISTINCT rev_user_text) as total_editors,
            SUM(CASE WHEN rev_user_id IS NULL THEN 1 ELSE 0 END) as anon_count,
            SUM(CASE WHEN rev_user_id IS NOT NULL THEN 1 ELSE 0 END) as reg_count
        FROM revisions
        WHERE page_id = ?
    `
    
    var anonCount, regCount int
    err := c.db.QueryRowContext(ctx, countQuery, stats.PageID).Scan(
        &stats.EditorCount,
        &anonCount,
        &regCount,
    )
    if err != nil {
        return err
    }
    
    // Calculate distinct anon vs registered
    const distinctQuery = `
        SELECT 
            COUNT(DISTINCT CASE WHEN rev_user_id IS NULL THEN rev_user_text END) as anon_editors,
            COUNT(DISTINCT CASE WHEN rev_user_id IS NOT NULL THEN rev_user_text END) as reg_editors
        FROM revisions
        WHERE page_id = ?
    `
    
    err = c.db.QueryRowContext(ctx, distinctQuery, stats.PageID).Scan(
        &stats.AnonEditors,
        &stats.RegisteredEditors,
    )
    if err != nil {
        return err
    }
    
    // Get top contributors
    query := fmt.Sprintf(`
        SELECT 
            r.rev_user_text as username,
            COUNT(*) as edit_count,
            MIN(r.rev_timestamp) as first_edit,
            MAX(r.rev_timestamp) as last_edit,
            SUM(CASE WHEN r.rev_minor_edit = 1 THEN 1 ELSE 0 END) as minor_edits,
            SUM(CASE WHEN r2.content_size IS NULL THEN r.content_size
                     WHEN r.content_size > r2.content_size THEN r.content_size - r2.content_size
                     ELSE 0 END) as bytes_added,
            SUM(CASE WHEN r2.content_size IS NULL THEN 0
                     WHEN r.content_size < r2.content_size THEN r2.content_size - r.content_size
                     ELSE 0 END) as bytes_removed
        FROM revisions r
        LEFT JOIN revisions r2 ON r.page_id = r2.page_id 
            AND r2.rev_timestamp < r.rev_timestamp
            AND r2.rev_timestamp = (
                SELECT MAX(rev_timestamp) 
                FROM revisions 
                WHERE page_id = r.page_id AND rev_timestamp < r.rev_timestamp
            )
        WHERE r.page_id = ?
        GROUP BY r.rev_user_text
        ORDER BY edit_count DESC
        LIMIT %d
    `, topN)
    
    rows, err := c.db.QueryContext(ctx, query, stats.PageID)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.TopContributors = make([]ContributorStat, 0, topN)
    for rows.Next() {
        var contrib ContributorStat
        err := rows.Scan(
            &contrib.Username,
            &contrib.EditCount,
            &contrib.FirstEdit,
            &contrib.LastEdit,
            &contrib.MinorEdits,
            &contrib.BytesAdded,
            &contrib.BytesRemoved,
        )
        if err != nil {
            return err
        }
        
        // Calculate percentage
        contrib.Percentage = float64(contrib.EditCount) / float64(stats.RevisionCount) * 100
        stats.TopContributors = append(stats.TopContributors, contrib)
    }
    
    return rows.Err()
}

// getSizeStatsForPage retrieves size statistics
func (c *sqliteClient) getSizeStatsForPage(ctx context.Context, stats *PageStatistics, includeGrowth bool, sampleSize int) error {
    const query = `
        SELECT 
            MIN(content_size) as min_size,
            MAX(content_size) as max_size,
            AVG(content_size) as avg_size
        FROM revisions
        WHERE page_id = ?
    `
    
    var avgSize float64
    err := c.db.QueryRowContext(ctx, query, stats.PageID).Scan(
        &stats.MinSize,
        &stats.MaxSize,
        &avgSize,
    )
    if err != nil {
        return err
    }
    
    stats.AvgSize = int(avgSize)
    
    // Get current and original size
    const sizeQuery = `
        SELECT 
            (SELECT content_size FROM revisions WHERE page_id = ? ORDER BY rev_timestamp ASC LIMIT 1) as original,
            (SELECT content_size FROM revisions WHERE page_id = ? ORDER BY rev_timestamp DESC LIMIT 1) as current
    `
    
    err = c.db.QueryRowContext(ctx, sizeQuery, stats.PageID, stats.PageID).Scan(
        &stats.OriginalSize,
        &stats.CurrentSize,
    )
    if err != nil {
        return err
    }
    
    // Get size growth over time
    if includeGrowth {
        query := fmt.Sprintf(`
            SELECT 
                r.rev_timestamp,
                r.content_size,
                COALESCE(r.content_size - prev.content_size, r.content_size) as delta
            FROM revisions r
            LEFT JOIN revisions prev ON r.page_id = prev.page_id
                AND prev.rev_timestamp < r.rev_timestamp
                AND prev.rev_timestamp = (
                    SELECT MAX(rev_timestamp)
                    FROM revisions
                    WHERE page_id = r.page_id AND rev_timestamp < r.rev_timestamp
                )
            WHERE r.page_id = ?
            ORDER BY r.rev_timestamp
            LIMIT %d
        `, sampleSize)
        
        rows, err := c.db.QueryContext(ctx, query, stats.PageID)
        if err != nil {
            return err
        }
        defer rows.Close()
        
        stats.SizeGrowth = make([]SizePoint, 0, sampleSize)
        for rows.Next() {
            var point SizePoint
            err := rows.Scan(&point.Timestamp, &point.Size, &point.Delta)
            if err != nil {
                return err
            }
            stats.SizeGrowth = append(stats.SizeGrowth, point)
        }
        
        if err := rows.Err(); err != nil {
            return err
        }
    }
    
    return nil
}

// getQualityMetrics calculates quality metrics
func (c *sqliteClient) getQualityMetrics(ctx context.Context, stats *PageStatistics) error {
    const query = `
        SELECT 
            AVG(CASE WHEN rev_minor_edit = 1 THEN 1.0 ELSE 0.0 END) * 100 as minor_percent,
            AVG(LENGTH(rev_comment)) as avg_comment_len
        FROM revisions
        WHERE page_id = ?
    `
    
    err := c.db.QueryRowContext(ctx, query, stats.PageID).Scan(
        &stats.MinorEditPercent,
        &stats.AvgCommentLength,
    )
    if err != nil {
        return err
    }
    
    // Detect reverts (simple: look for identical SHA1 hashes)
    const revertQuery = `
        SELECT COUNT(*)
        FROM revisions r1
        JOIN revisions r2 ON r1.page_id = r2.page_id 
            AND r1.sha1 = r2.sha1 
            AND r1.rev_id < r2.rev_id
        WHERE r1.page_id = ?
    `
    
    c.db.QueryRowContext(ctx, revertQuery, stats.PageID).Scan(&stats.RevertCount)
    
    // Calculate stability score (0-100, higher is more stable)
    // Based on: low edit frequency, fewer reverts, more minor edits
    stats.StabilityScore = calculateStabilityScore(
        stats.AvgTimeBetween,
        stats.RevertCount,
        stats.RevisionCount,
        stats.MinorEditPercent,
    )
    
    return nil
}

// getActivityPatterns identifies activity patterns
func (c *sqliteClient) getActivityPatterns(ctx context.Context, stats *PageStatistics) error {
    // Edit frequency by month
    const freqQuery = `
        SELECT 
            strftime('%Y-%m', rev_timestamp) as month,
            COUNT(*) as count
        FROM revisions
        WHERE page_id = ?
        GROUP BY month
        ORDER BY month
    `
    
    rows, err := c.db.QueryContext(ctx, freqQuery, stats.PageID)
    if err != nil {
        return err
    }
    defer rows.Close()
    
    stats.EditFrequency = make(map[string]int)
    maxCount := 0
    var busiestMonth string
    
    for rows.Next() {
        var month string
        var count int
        if err := rows.Scan(&month, &count); err != nil {
            return err
        }
        stats.EditFrequency[month] = count
        
        if count > maxCount {
            maxCount = count
            busiestMonth = month
        }
    }
    
    stats.BusiestMonth = busiestMonth
    
    // Find longest gap between edits
    const gapQuery = `
        SELECT MAX(
            julianday(rev_timestamp) - julianday(
                LAG(rev_timestamp) OVER (ORDER BY rev_timestamp)
            )
        ) as max_gap_days
        FROM revisions
        WHERE page_id = ?
    `
    
    var gapDays float64
    if err := c.db.QueryRowContext(ctx, gapQuery, stats.PageID).Scan(&gapDays); err == nil {
        stats.LongestGap = time.Duration(gapDays * 24 * float64(time.Hour))
    }
    
    return rows.Err()
}

// calculateStabilityScore computes a stability score for the page
func calculateStabilityScore(avgTimeBetween time.Duration, reverts, totalRevs int, minorPercent float64) float64 {
    // Base score
    score := 50.0
    
    // Longer time between edits = more stable
    hoursB etween := avgTimeBetween.Hours()
    if hoursBetween > 720 { // > 30 days
        score += 20
    } else if hoursBetween > 168 { // > 7 days
        score += 10
    }
    
    // Fewer reverts = more stable
    revertPercent := float64(reverts) / float64(totalRevs) * 100
    if revertPercent < 5 {
        score += 20
    } else if revertPercent < 10 {
        score += 10
    } else {
        score -= 10
    }
    
    // More minor edits = more stable (polishing vs major changes)
    if minorPercent > 30 {
        score += 10
    }
    
    // Clamp to 0-100
    if score < 0 {
        score = 0
    }
    if score > 100 {
        score = 100
    }
    
    return score
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 03: PostgreSQL Backend
- Story 05: Data Models
- Story 10: Page History Query
- Story 14: Archive Statistics

## Implementation Notes

- Page statistics can be expensive for pages with many revisions
- Consider caching frequently accessed page stats
- Size growth sampling helps with performance for long histories
- Revert detection is simplified (could be enhanced with content comparison)
- Stability score is heuristic-based (can be tuned)
- Activity patterns help identify interesting trends

## Testing Requirements

- [ ] Basic stats tests (counts, dates)
- [ ] Contributor stats tests
- [ ] Size calculation tests
- [ ] Quality metrics tests
- [ ] Activity pattern tests
- [ ] Stability score tests
- [ ] Edge cases (single revision, no minor edits)
- [ ] Performance tests with high-revision pages
- [ ] Comparison between SQLite and PostgreSQL results

## Definition of Done

- [ ] GetPageStats implemented for both backends
- [ ] All statistics components working
- [ ] Quality metrics calculated correctly
- [ ] Activity patterns identified
- [ ] All tests passing
- [ ] Performance acceptable (<500ms per page)
- [ ] Documentation complete
- [ ] Code reviewed and approved
