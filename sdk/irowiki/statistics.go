package irowiki

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// GetStatisticsEnhanced retrieves comprehensive archive statistics with additional details.
// This is an enhanced version that provides more detailed statistics than GetStatistics().
func (c *sqliteClient) GetStatisticsEnhanced(ctx context.Context) (*StatisticsEnhanced, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	stats := &StatisticsEnhanced{
		PagesByNamespace: make(map[int]int64),
		EditsByMonth:     make(map[string]int64),
	}

	// Get basic counts
	err := c.getBasicCounts(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get basic counts: %w", err)
	}

	// Get temporal statistics
	err = c.getTemporalStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get temporal stats: %w", err)
	}

	// Get size statistics
	err = c.getSizeStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get size stats: %w", err)
	}

	// Get namespace distribution
	err = c.getNamespaceStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get namespace stats: %w", err)
	}

	// Get top editors
	err = c.getTopEditors(ctx, stats, 10)
	if err != nil {
		return nil, fmt.Errorf("failed to get top editors: %w", err)
	}

	// Get most edited pages
	err = c.getMostEditedPages(ctx, stats, 10)
	if err != nil {
		return nil, fmt.Errorf("failed to get most edited pages: %w", err)
	}

	// Get edit distribution by month
	err = c.getEditsByMonth(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get edits by month: %w", err)
	}

	return stats, nil
}

// getBasicCounts retrieves basic count statistics.
func (c *sqliteClient) getBasicCounts(ctx context.Context, stats *StatisticsEnhanced) error {
	const query = `
		SELECT 
			(SELECT COUNT(*) FROM pages) as total_pages,
			(SELECT COUNT(*) FROM revisions) as total_revisions,
			(SELECT COUNT(*) FROM files) as total_files,
			(SELECT COUNT(DISTINCT user) FROM revisions WHERE user IS NOT NULL) as total_editors
	`

	return c.db.QueryRowContext(ctx, query).Scan(
		&stats.TotalPages,
		&stats.TotalRevisions,
		&stats.TotalFiles,
		&stats.TotalEditors,
	)
}

// getTemporalStats retrieves temporal statistics.
func (c *sqliteClient) getTemporalStats(ctx context.Context, stats *StatisticsEnhanced) error {
	const query = `
		SELECT 
			datetime(MIN(timestamp)) as first_edit,
			datetime(MAX(timestamp)) as last_edit
		FROM revisions
		WHERE timestamp IS NOT NULL
	`

	var firstEdit, lastEdit sql.NullString
	err := c.db.QueryRowContext(ctx, query).Scan(&firstEdit, &lastEdit)
	if err != nil {
		return err
	}

	if firstEdit.Valid && firstEdit.String != "" {
		if t, err := time.Parse("2006-01-02 15:04:05", firstEdit.String); err == nil {
			stats.FirstEdit = t
		} else if t, err := time.Parse(time.RFC3339, firstEdit.String); err == nil {
			stats.FirstEdit = t
		}
	}

	if lastEdit.Valid && lastEdit.String != "" {
		if t, err := time.Parse("2006-01-02 15:04:05", lastEdit.String); err == nil {
			stats.LastEdit = t
		} else if t, err := time.Parse(time.RFC3339, lastEdit.String); err == nil {
			stats.LastEdit = t
		}
	}

	// Calculate active editors (last 30 days from last edit)
	if !stats.LastEdit.IsZero() {
		cutoff := stats.LastEdit.Add(-30 * 24 * time.Hour)
		const activeQuery = `
			SELECT COUNT(DISTINCT user)
			FROM revisions
			WHERE datetime(timestamp) >= datetime(?) AND user IS NOT NULL
		`
		c.db.QueryRowContext(ctx, activeQuery, cutoff).Scan(&stats.ActiveEditors)
	}

	return nil
}

// getSizeStats retrieves size statistics.
func (c *sqliteClient) getSizeStats(ctx context.Context, stats *StatisticsEnhanced) error {
	const query = `
		SELECT 
			COALESCE(SUM(r.size), 0) as total_size,
			COALESCE(AVG(r.size), 0) as avg_size
		FROM revisions r
		INNER JOIN (
			SELECT page_id, MAX(timestamp) as max_time
			FROM revisions
			GROUP BY page_id
		) latest ON r.page_id = latest.page_id AND r.timestamp = latest.max_time
	`

	var avgSize float64
	err := c.db.QueryRowContext(ctx, query).Scan(&stats.TotalContentSize, &avgSize)
	if err != nil {
		return err
	}

	stats.AveragePageSize = int(avgSize)

	// Get median page size
	const medianQuery = `
		SELECT size
		FROM (
			SELECT r.size, ROW_NUMBER() OVER (ORDER BY r.size) as rn,
				   COUNT(*) OVER () as total
			FROM revisions r
			INNER JOIN (
				SELECT page_id, MAX(timestamp) as max_time
				FROM revisions
				GROUP BY page_id
			) latest ON r.page_id = latest.page_id AND r.timestamp = latest.max_time
		) 
		WHERE rn = (total + 1) / 2
	`

	c.db.QueryRowContext(ctx, medianQuery).Scan(&stats.MedianPageSize)

	// Get largest and smallest pages
	err = c.getExtremesPages(ctx, stats)
	if err != nil {
		return err
	}

	return nil
}

// getExtremesPages retrieves largest and smallest pages.
func (c *sqliteClient) getExtremesPages(ctx context.Context, stats *StatisticsEnhanced) error {
	// Largest page
	const largestQuery = `
		SELECT p.page_id, p.title, p.namespace, r.size
		FROM pages p
		INNER JOIN revisions r ON r.page_id = p.page_id
		INNER JOIN (
			SELECT page_id, MAX(timestamp) as max_time
			FROM revisions
			GROUP BY page_id
		) latest ON r.page_id = latest.page_id AND r.timestamp = latest.max_time
		ORDER BY r.size DESC
		LIMIT 1
	`

	var largest PageInfoStat
	err := c.db.QueryRowContext(ctx, largestQuery).Scan(
		&largest.ID,
		&largest.Title,
		&largest.Namespace,
		&largest.Size,
	)
	if err == nil {
		stats.LargestPage = &largest
	}

	// Smallest page (exclude empty pages)
	const smallestQuery = `
		SELECT p.page_id, p.title, p.namespace, r.size
		FROM pages p
		INNER JOIN revisions r ON r.page_id = p.page_id
		INNER JOIN (
			SELECT page_id, MAX(timestamp) as max_time
			FROM revisions
			GROUP BY page_id
		) latest ON r.page_id = latest.page_id AND r.timestamp = latest.max_time
		WHERE r.size > 0
		ORDER BY r.size ASC
		LIMIT 1
	`

	var smallest PageInfoStat
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

// getNamespaceStats retrieves namespace distribution.
func (c *sqliteClient) getNamespaceStats(ctx context.Context, stats *StatisticsEnhanced) error {
	const query = `
		SELECT namespace, COUNT(*) as count
		FROM pages
		GROUP BY namespace
		ORDER BY namespace
	`

	rows, err := c.db.QueryContext(ctx, query)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var ns int
		var count int64
		if err := rows.Scan(&ns, &count); err != nil {
			return err
		}
		stats.PagesByNamespace[ns] = count
	}

	return rows.Err()
}

// getTopEditors retrieves top N editors by edit count.
func (c *sqliteClient) getTopEditors(ctx context.Context, stats *StatisticsEnhanced, n int) error {
	query := fmt.Sprintf(`
		SELECT 
			user,
			COUNT(*) as edit_count,
			datetime(MIN(timestamp)) as first_edit,
			datetime(MAX(timestamp)) as last_edit,
			SUM(CASE WHEN minor = 1 THEN 1 ELSE 0 END) as minor_edits,
			COUNT(DISTINCT page_id) as pages_edited
		FROM revisions
		WHERE user IS NOT NULL
		GROUP BY user
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
		var firstEdit, lastEdit sql.NullString

		err := rows.Scan(
			&editor.Username,
			&editor.EditCount,
			&firstEdit,
			&lastEdit,
			&editor.MinorEdits,
			&editor.PagesEdited,
		)
		if err != nil {
			return err
		}

		if firstEdit.Valid && firstEdit.String != "" {
			if t, err := time.Parse("2006-01-02 15:04:05", firstEdit.String); err == nil {
				editor.FirstEdit = t
			} else if t, err := time.Parse(time.RFC3339, firstEdit.String); err == nil {
				editor.FirstEdit = t
			}
		}

		if lastEdit.Valid && lastEdit.String != "" {
			if t, err := time.Parse("2006-01-02 15:04:05", lastEdit.String); err == nil {
				editor.LastEdit = t
			} else if t, err := time.Parse(time.RFC3339, lastEdit.String); err == nil {
				editor.LastEdit = t
			}
		}

		stats.TopEditors = append(stats.TopEditors, editor)
	}

	return rows.Err()
}

// getMostEditedPages retrieves top N most edited pages.
func (c *sqliteClient) getMostEditedPages(ctx context.Context, stats *StatisticsEnhanced, n int) error {
	query := fmt.Sprintf(`
		SELECT 
			p.page_id,
			p.title,
			COUNT(*) as revision_count,
			COUNT(DISTINCT r.user) as editor_count
		FROM pages p
		INNER JOIN revisions r ON p.page_id = r.page_id
		WHERE r.user IS NOT NULL
		GROUP BY p.page_id, p.title
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

// getEditsByMonth retrieves edit distribution by month.
func (c *sqliteClient) getEditsByMonth(ctx context.Context, stats *StatisticsEnhanced) error {
	const query = `
		SELECT 
			strftime('%Y-%m', timestamp) as month,
			COUNT(*) as edit_count
		FROM revisions
		WHERE timestamp IS NOT NULL
		GROUP BY month
		ORDER BY month
	`

	rows, err := c.db.QueryContext(ctx, query)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var month sql.NullString
		var count int64
		if err := rows.Scan(&month, &count); err != nil {
			return err
		}
		if month.Valid && month.String != "" {
			stats.EditsByMonth[month.String] = count
		}
	}

	return rows.Err()
}

// GetPageStatsEnhanced retrieves enhanced statistics for a specific page.
func (c *sqliteClient) GetPageStatsEnhanced(ctx context.Context, title string) (*PageStatisticsEnhanced, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Get page ID
	var pageID int64
	var pageTitle string
	var namespace int
	err := c.db.QueryRowContext(ctx, "SELECT page_id, title, namespace FROM pages WHERE title = ?", title).Scan(&pageID, &pageTitle, &namespace)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	stats := &PageStatisticsEnhanced{
		PageID:        pageID,
		Title:         pageTitle,
		PageNamespace: namespace,
	}

	// Get basic revision statistics
	err = c.getPageRevisionStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get revision stats: %w", err)
	}

	// Get contributor statistics
	err = c.getPageContributorStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get contributor stats: %w", err)
	}

	// Get size statistics
	err = c.getPageSizeStats(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get size stats: %w", err)
	}

	// Get quality metrics
	err = c.getPageQualityMetrics(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get quality metrics: %w", err)
	}

	// Get activity patterns
	err = c.getPageActivityPatterns(ctx, stats)
	if err != nil {
		return nil, fmt.Errorf("failed to get activity patterns: %w", err)
	}

	return stats, nil
}

// getPageRevisionStats retrieves basic revision statistics for a page.
func (c *sqliteClient) getPageRevisionStats(ctx context.Context, stats *PageStatisticsEnhanced) error {
	const query = `
		SELECT 
			COUNT(*) as revision_count,
			datetime(MIN(timestamp)) as first_edit,
			datetime(MAX(timestamp)) as last_edit
		FROM revisions
		WHERE page_id = ?
	`

	var firstEdit, lastEdit sql.NullString
	err := c.db.QueryRowContext(ctx, query, stats.PageID).Scan(
		&stats.RevisionCount,
		&firstEdit,
		&lastEdit,
	)
	if err != nil {
		return err
	}

	if firstEdit.Valid && firstEdit.String != "" {
		if t, err := time.Parse("2006-01-02 15:04:05", firstEdit.String); err == nil {
			stats.FirstEdit = t
		} else if t, err := time.Parse(time.RFC3339, firstEdit.String); err == nil {
			stats.FirstEdit = t
		}
	}

	if lastEdit.Valid && lastEdit.String != "" {
		if t, err := time.Parse("2006-01-02 15:04:05", lastEdit.String); err == nil {
			stats.LastEdit = t
		} else if t, err := time.Parse(time.RFC3339, lastEdit.String); err == nil {
			stats.LastEdit = t
		}
	}

	// Calculate average time between edits
	if stats.RevisionCount > 1 && !stats.FirstEdit.IsZero() && !stats.LastEdit.IsZero() {
		totalTime := stats.LastEdit.Sub(stats.FirstEdit)
		stats.AvgTimeBetween = totalTime / time.Duration(stats.RevisionCount-1)
	}

	return nil
}

// getPageContributorStats retrieves contributor statistics for a page.
func (c *sqliteClient) getPageContributorStats(ctx context.Context, stats *PageStatisticsEnhanced) error {
	// Count editors
	const countQuery = `
		SELECT 
			COUNT(DISTINCT user) as total_editors,
			COUNT(DISTINCT CASE WHEN user_id IS NULL THEN user END) as anon_editors,
			COUNT(DISTINCT CASE WHEN user_id IS NOT NULL THEN user END) as reg_editors
		FROM revisions
		WHERE page_id = ? AND user IS NOT NULL
	`

	err := c.db.QueryRowContext(ctx, countQuery, stats.PageID).Scan(
		&stats.EditorCount,
		&stats.AnonEditors,
		&stats.RegisteredEditors,
	)
	if err != nil {
		return err
	}

	// Get top contributors
	const topContribQuery = `
		SELECT 
			user,
			COUNT(*) as edit_count,
			MIN(timestamp) as first_edit,
			MAX(timestamp) as last_edit,
			SUM(CASE WHEN minor = 1 THEN 1 ELSE 0 END) as minor_edits
		FROM revisions
		WHERE page_id = ? AND user IS NOT NULL
		GROUP BY user
		ORDER BY edit_count DESC
		LIMIT 5
	`

	rows, err := c.db.QueryContext(ctx, topContribQuery, stats.PageID)
	if err != nil {
		return err
	}
	defer rows.Close()

	stats.TopContributors = make([]ContributorStat, 0, 5)
	for rows.Next() {
		var contrib ContributorStat
		var firstEditStr, lastEditStr sql.NullString

		err := rows.Scan(
			&contrib.Username,
			&contrib.EditCount,
			&firstEditStr,
			&lastEditStr,
			&contrib.MinorEdits,
		)
		if err != nil {
			return err
		}

		if firstEditStr.Valid {
			if t, err := time.Parse("2006-01-02 15:04:05", firstEditStr.String); err == nil {
				contrib.FirstEdit = t
			} else if t, err := time.Parse(time.RFC3339, firstEditStr.String); err == nil {
				contrib.FirstEdit = t
			}
		}

		if lastEditStr.Valid {
			if t, err := time.Parse("2006-01-02 15:04:05", lastEditStr.String); err == nil {
				contrib.LastEdit = t
			} else if t, err := time.Parse(time.RFC3339, lastEditStr.String); err == nil {
				contrib.LastEdit = t
			}
		}

		contrib.Percentage = float64(contrib.EditCount) / float64(stats.RevisionCount) * 100
		stats.TopContributors = append(stats.TopContributors, contrib)
	}

	return rows.Err()
}

// getPageSizeStats retrieves size statistics for a page.
func (c *sqliteClient) getPageSizeStats(ctx context.Context, stats *PageStatisticsEnhanced) error {
	const query = `
		SELECT 
			MIN(size) as min_size,
			MAX(size) as max_size,
			AVG(size) as avg_size
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
			(SELECT size FROM revisions WHERE page_id = ? ORDER BY timestamp ASC LIMIT 1) as original,
			(SELECT size FROM revisions WHERE page_id = ? ORDER BY timestamp DESC LIMIT 1) as current
	`

	err = c.db.QueryRowContext(ctx, sizeQuery, stats.PageID, stats.PageID).Scan(
		&stats.OriginalSize,
		&stats.CurrentSize,
	)

	return err
}

// getPageQualityMetrics calculates quality metrics for a page.
func (c *sqliteClient) getPageQualityMetrics(ctx context.Context, stats *PageStatisticsEnhanced) error {
	const query = `
		SELECT 
			AVG(CASE WHEN minor = 1 THEN 1.0 ELSE 0.0 END) * 100 as minor_percent,
			AVG(LENGTH(comment)) as avg_comment_len
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
		INNER JOIN revisions r2 ON r1.page_id = r2.page_id 
			AND r1.sha1 = r2.sha1 
			AND r1.revision_id < r2.revision_id
		WHERE r1.page_id = ?
	`

	c.db.QueryRowContext(ctx, revertQuery, stats.PageID).Scan(&stats.RevertCount)

	// Calculate stability score
	stats.StabilityScore = calculateStabilityScore(
		stats.AvgTimeBetween,
		stats.RevertCount,
		int(stats.RevisionCount),
		stats.MinorEditPercent,
	)

	return nil
}

// calculateStabilityScore computes a stability score for the page.
func calculateStabilityScore(avgTimeBetween time.Duration, reverts int, totalRevs int, minorPercent float64) float64 {
	if totalRevs == 0 {
		return 0
	}

	// Base score
	score := 50.0

	// Longer time between edits = more stable
	hoursBetween := avgTimeBetween.Hours()
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

// getPageActivityPatterns identifies activity patterns for a page.
func (c *sqliteClient) getPageActivityPatterns(ctx context.Context, stats *PageStatisticsEnhanced) error {
	// Edit frequency by month
	const freqQuery = `
		SELECT 
			strftime('%Y-%m', timestamp) as month,
			COUNT(*) as count
		FROM revisions
		WHERE page_id = ? AND timestamp IS NOT NULL
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
		var month sql.NullString
		var count int
		if err := rows.Scan(&month, &count); err != nil {
			return err
		}
		if month.Valid && month.String != "" {
			stats.EditFrequency[month.String] = count

			if count > maxCount {
				maxCount = count
				busiestMonth = month.String
			}
		}
	}

	stats.BusiestMonth = busiestMonth

	// Find longest gap between edits
	const gapQuery = `
		WITH gaps AS (
			SELECT 
				timestamp,
				LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
			FROM revisions
			WHERE page_id = ?
		)
		SELECT MAX(julianday(timestamp) - julianday(prev_timestamp)) as max_gap_days
		FROM gaps
		WHERE prev_timestamp IS NOT NULL
	`

	var gapDays sql.NullFloat64
	if err := c.db.QueryRowContext(ctx, gapQuery, stats.PageID).Scan(&gapDays); err == nil && gapDays.Valid {
		stats.LongestGap = time.Duration(gapDays.Float64 * 24 * float64(time.Hour))
	}

	return rows.Err()
}

// GetEditorActivityEnhanced retrieves enhanced activity for an editor.
func (c *sqliteClient) GetEditorActivityEnhanced(ctx context.Context, username string, start, end time.Time) (*EditorActivity, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	activity := &EditorActivity{
		Username: username,
	}

	// Get basic statistics
	err := c.getEditorBasicStats(ctx, activity, start, end)
	if err != nil {
		return nil, fmt.Errorf("failed to get basic stats: %w", err)
	}

	// Get content statistics
	err = c.getEditorContentStats(ctx, activity, start, end)
	if err != nil {
		return nil, fmt.Errorf("failed to get content stats: %w", err)
	}

	// Get activity patterns
	err = c.getEditorActivityPatterns(ctx, activity, start, end)
	if err != nil {
		return nil, fmt.Errorf("failed to get activity patterns: %w", err)
	}

	// Get top pages
	err = c.getEditorTopPages(ctx, activity, start, end, 10)
	if err != nil {
		return nil, fmt.Errorf("failed to get top pages: %w", err)
	}

	return activity, nil
}

// getEditorBasicStats retrieves basic editor statistics.
func (c *sqliteClient) getEditorBasicStats(ctx context.Context, activity *EditorActivity, start, end time.Time) error {
	query := `
		SELECT 
			COUNT(*) as total_edits,
			MIN(timestamp) as first_edit,
			MAX(timestamp) as last_edit,
			COUNT(DISTINCT DATE(timestamp)) as active_days,
			user_id
		FROM revisions
		WHERE user = ?
	`

	args := []interface{}{activity.Username}

	if !start.IsZero() {
		query += " AND timestamp >= ?"
		args = append(args, start)
	}
	if !end.IsZero() {
		query += " AND timestamp <= ?"
		args = append(args, end)
	}

	query += " GROUP BY user_id"

	var userID sql.NullInt64
	var firstEditStr, lastEditStr sql.NullString

	err := c.db.QueryRowContext(ctx, query, args...).Scan(
		&activity.TotalEdits,
		&firstEditStr,
		&lastEditStr,
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

	if firstEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", firstEditStr.String); err == nil {
			activity.FirstEdit = t
		} else if t, err := time.Parse(time.RFC3339, firstEditStr.String); err == nil {
			activity.FirstEdit = t
		}
	}

	if lastEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", lastEditStr.String); err == nil {
			activity.LastEdit = t
		} else if t, err := time.Parse(time.RFC3339, lastEditStr.String); err == nil {
			activity.LastEdit = t
		}
	}

	return nil
}

// getEditorContentStats retrieves content contribution statistics.
func (c *sqliteClient) getEditorContentStats(ctx context.Context, activity *EditorActivity, start, end time.Time) error {
	query := `
		SELECT 
			COUNT(DISTINCT page_id) as pages_edited,
			SUM(CASE WHEN minor = 1 THEN 1 ELSE 0 END) as minor_edits
		FROM revisions
		WHERE user = ?
	`

	args := []interface{}{activity.Username}

	if !start.IsZero() {
		query += " AND timestamp >= ?"
		args = append(args, start)
	}
	if !end.IsZero() {
		query += " AND timestamp <= ?"
		args = append(args, end)
	}

	err := c.db.QueryRowContext(ctx, query, args...).Scan(
		&activity.PagesEdited,
		&activity.MinorEdits,
	)

	return err
}

// getEditorActivityPatterns retrieves activity patterns.
func (c *sqliteClient) getEditorActivityPatterns(ctx context.Context, activity *EditorActivity, start, end time.Time) error {
	query := `
		SELECT 
			CAST(strftime('%H', timestamp) AS INTEGER) as hour,
			strftime('%w', timestamp) as day_of_week,
			strftime('%Y-%m', timestamp) as month
		FROM revisions
		WHERE user = ? AND timestamp IS NOT NULL
	`

	args := []interface{}{activity.Username}

	if !start.IsZero() {
		query += " AND timestamp >= ?"
		args = append(args, start)
	}
	if !end.IsZero() {
		query += " AND timestamp <= ?"
		args = append(args, end)
	}

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
		var hour sql.NullInt64
		var dayOfWeek, month sql.NullString

		if err := rows.Scan(&hour, &dayOfWeek, &month); err != nil {
			return err
		}

		if hour.Valid {
			h := int(hour.Int64)
			activity.EditsByHour[h]++
			if activity.EditsByHour[h] > maxHourCount {
				maxHourCount = activity.EditsByHour[h]
				activity.BusiestHour = h
			}
		}

		if dayOfWeek.Valid && dayOfWeek.String != "" {
			// Convert day number (0-6) to name
			if len(dayOfWeek.String) == 1 && dayOfWeek.String[0] >= '0' && dayOfWeek.String[0] <= '6' {
				dayIdx := int(dayOfWeek.String[0] - '0')
				dayName := dayNames[dayIdx]
				activity.EditsByDay[dayName]++
				if activity.EditsByDay[dayName] > maxDayCount {
					maxDayCount = activity.EditsByDay[dayName]
					activity.BusiestDay = dayName
				}
			}
		}

		if month.Valid && month.String != "" {
			activity.EditsByMonth[month.String]++
		}
	}

	return rows.Err()
}

// getEditorTopPages retrieves top pages edited by the editor.
func (c *sqliteClient) getEditorTopPages(ctx context.Context, activity *EditorActivity, start, end time.Time, n int) error {
	query := fmt.Sprintf(`
		SELECT 
			r.page_id,
			p.title,
			COUNT(*) as edit_count,
			MIN(r.timestamp) as first_edit,
			MAX(r.timestamp) as last_edit
		FROM revisions r
		INNER JOIN pages p ON r.page_id = p.page_id
		WHERE r.user = ?
	`)

	args := []interface{}{activity.Username}

	if !start.IsZero() {
		query += " AND r.timestamp >= ?"
		args = append(args, start)
	}
	if !end.IsZero() {
		query += " AND r.timestamp <= ?"
		args = append(args, end)
	}

	query += fmt.Sprintf(`
		GROUP BY r.page_id, p.title
		ORDER BY edit_count DESC
		LIMIT %d
	`, n)

	rows, err := c.db.QueryContext(ctx, query, args...)
	if err != nil {
		return err
	}
	defer rows.Close()

	activity.TopPages = make([]PageEditStat, 0, n)
	for rows.Next() {
		var pageStat PageEditStat
		var firstEditStr, lastEditStr sql.NullString

		err := rows.Scan(
			&pageStat.PageID,
			&pageStat.PageTitle,
			&pageStat.EditCount,
			&firstEditStr,
			&lastEditStr,
		)
		if err != nil {
			return err
		}

		if firstEditStr.Valid {
			if t, err := time.Parse("2006-01-02 15:04:05", firstEditStr.String); err == nil {
				pageStat.FirstEdit = t
			} else if t, err := time.Parse(time.RFC3339, firstEditStr.String); err == nil {
				pageStat.FirstEdit = t
			}
		}

		if lastEditStr.Valid {
			if t, err := time.Parse("2006-01-02 15:04:05", lastEditStr.String); err == nil {
				pageStat.LastEdit = t
			} else if t, err := time.Parse(time.RFC3339, lastEditStr.String); err == nil {
				pageStat.LastEdit = t
			}
		}

		activity.TopPages = append(activity.TopPages, pageStat)
	}

	return rows.Err()
}
