package irowiki

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	_ "github.com/lib/pq"
)

// postgresClient implements the Client interface for PostgreSQL databases.
type postgresClient struct {
	db     *sql.DB
	opts   ConnectionOptions
	closed bool
	mu     sync.RWMutex
}

// OpenPostgres opens a PostgreSQL database with the specified DSN and default options.
//
// DSN format examples:
//   - "postgres://user:password@localhost/dbname"
//   - "host=localhost port=5432 user=wiki password=secret dbname=irowiki sslmode=disable"
//
// Example:
//
//	client, err := irowiki.OpenPostgres("postgres://user:pass@localhost/irowiki")
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Close()
func OpenPostgres(dsn string) (Client, error) {
	return OpenPostgresWithOptions(dsn, DefaultPostgresOptions())
}

// OpenPostgresWithOptions opens a PostgreSQL database with custom connection options.
func OpenPostgresWithOptions(dsn string, opts ConnectionOptions) (Client, error) {
	opts.applyDefaults(false)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("%w: failed to open database: %v", ErrConnectionFailed, err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(opts.MaxOpenConns)
	db.SetMaxIdleConns(opts.MaxIdleConns)
	db.SetConnMaxLifetime(opts.ConnMaxLifetime)
	db.SetConnMaxIdleTime(opts.ConnMaxIdleTime)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), opts.ConnectTimeout)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("%w: failed to ping database: %v", ErrConnectionFailed, err)
	}

	client := &postgresClient{
		db:     db,
		opts:   opts,
		closed: false,
	}

	return client, nil
}

// ensureNotClosed checks if the client is closed and returns an error if it is.
func (c *postgresClient) ensureNotClosed() error {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if c.closed {
		return ErrClosed
	}
	return nil
}

// The PostgreSQL client implements the same interface as SQLite, but uses PostgreSQL-specific syntax.
// Key differences:
// - Uses $1, $2 placeholders instead of ?
// - Native timestamp support (no string parsing needed)
// - Better full-text search with ts_vector (future enhancement)

// GetPage retrieves the latest version of a page by title.
func (c *postgresClient) GetPage(ctx context.Context, title string) (*Page, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT p.page_id, p.namespace, p.title, p.is_redirect,
		       r.revision_id, r.timestamp, r.user, r.comment, r.content
		FROM pages p
		LEFT JOIN revisions r ON p.page_id = r.page_id
		WHERE p.title = $1
		ORDER BY r.timestamp DESC
		LIMIT 1
	`

	var page Page
	var revID sql.NullInt64
	var timestamp sql.NullTime
	var user, comment, content sql.NullString

	err := c.db.QueryRowContext(ctx, query, title).Scan(
		&page.ID, &page.Namespace, &page.Title, &page.IsRedirect,
		&revID, &timestamp, &user, &comment, &content,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Populate revision fields if they exist
	if revID.Valid {
		page.LatestRevisionID = revID.Int64
	}
	if timestamp.Valid {
		page.Timestamp = timestamp.Time
	}
	if user.Valid {
		page.User = user.String
	}
	if comment.Valid {
		page.Comment = comment.String
	}
	if content.Valid {
		page.Content = content.String
	}

	return &page, nil
}

// GetPageByID retrieves the latest version of a page by ID.
func (c *postgresClient) GetPageByID(ctx context.Context, id int64) (*Page, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT p.page_id, p.namespace, p.title, p.is_redirect,
		       r.revision_id, r.timestamp, r.user, r.comment, r.content
		FROM pages p
		LEFT JOIN revisions r ON p.page_id = r.page_id
		WHERE p.page_id = $1
		ORDER BY r.timestamp DESC
		LIMIT 1
	`

	var page Page
	var revID sql.NullInt64
	var timestamp sql.NullTime
	var user, comment, content sql.NullString

	err := c.db.QueryRowContext(ctx, query, id).Scan(
		&page.ID, &page.Namespace, &page.Title, &page.IsRedirect,
		&revID, &timestamp, &user, &comment, &content,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Populate revision fields if they exist
	if revID.Valid {
		page.LatestRevisionID = revID.Int64
	}
	if timestamp.Valid {
		page.Timestamp = timestamp.Time
	}
	if user.Valid {
		page.User = user.String
	}
	if comment.Valid {
		page.Comment = comment.String
	}
	if content.Valid {
		page.Content = content.String
	}

	return &page, nil
}

// ListPages returns a paginated list of pages in the specified namespace.
func (c *postgresClient) ListPages(ctx context.Context, namespace int, offset, limit int) ([]Page, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	if limit == 0 {
		limit = 100
	}

	const query = `
		SELECT p.page_id, p.namespace, p.title, p.is_redirect,
		       r.revision_id, r.timestamp, r.user, r.comment, r.content
		FROM pages p
		LEFT JOIN LATERAL (
			SELECT revision_id, timestamp, user, comment, content
			FROM revisions
			WHERE page_id = p.page_id
			ORDER BY timestamp DESC
			LIMIT 1
		) r ON true
		WHERE p.namespace = $1
		ORDER BY p.page_id
		LIMIT $2 OFFSET $3
	`

	rows, err := c.db.QueryContext(ctx, query, namespace, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var pages []Page
	for rows.Next() {
		var page Page
		var revID sql.NullInt64
		var timestamp sql.NullTime
		var user, comment, content sql.NullString

		err := rows.Scan(
			&page.ID, &page.Namespace, &page.Title, &page.IsRedirect,
			&revID, &timestamp, &user, &comment, &content,
		)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		// Populate revision fields if they exist
		if revID.Valid {
			page.LatestRevisionID = revID.Int64
		}
		if timestamp.Valid {
			page.Timestamp = timestamp.Time
		}
		if user.Valid {
			page.User = user.String
		}
		if comment.Valid {
			page.Comment = comment.String
		}
		if content.Valid {
			page.Content = content.String
		}

		pages = append(pages, page)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return pages, nil
}

// Search performs a simple search across page titles.
func (c *postgresClient) Search(ctx context.Context, opts SearchOptions) ([]SearchResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	if opts.Limit == 0 {
		opts.Limit = 100
	}

	query := `
		SELECT p.page_id, p.namespace, p.title, r.timestamp
		FROM pages p
		LEFT JOIN LATERAL (
			SELECT timestamp
			FROM revisions
			WHERE page_id = p.page_id
			ORDER BY timestamp DESC
			LIMIT 1
		) r ON true
		WHERE p.title LIKE $1
	`

	args := []interface{}{"%" + opts.Query + "%"}
	paramCount := 1

	if opts.Namespace >= 0 {
		paramCount++
		query += fmt.Sprintf(" AND p.namespace = $%d", paramCount)
		args = append(args, opts.Namespace)
	}

	paramCount++
	query += fmt.Sprintf(" ORDER BY p.page_id LIMIT $%d OFFSET $%d", paramCount, paramCount+1)
	args = append(args, opts.Limit, opts.Offset)

	rows, err := c.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var result SearchResult
		var timestamp sql.NullTime

		err := rows.Scan(&result.PageID, &result.Namespace, &result.Title, &timestamp)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		if timestamp.Valid {
			result.Timestamp = timestamp.Time
		}

		results = append(results, result)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return results, nil
}

// SearchFullText performs full-text search across page content.
func (c *postgresClient) SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error) {
	// For now, use simple search as full-text search requires ts_vector setup
	return c.Search(ctx, opts)
}

// GetPageHistory retrieves the revision history for a page.
func (c *postgresClient) GetPageHistory(ctx context.Context, title string, opts HistoryOptions) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// First, get the page ID
	var pageID int64
	err := c.db.QueryRowContext(ctx, "SELECT page_id FROM pages WHERE title = $1", title).Scan(&pageID)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	if opts.Limit == 0 {
		opts.Limit = 100
	}

	query := `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE page_id = $1
	`
	args := []interface{}{pageID}
	paramCount := 1

	if !opts.StartDate.IsZero() {
		paramCount++
		query += fmt.Sprintf(" AND timestamp >= $%d", paramCount)
		args = append(args, opts.StartDate)
	}
	if !opts.EndDate.IsZero() {
		paramCount++
		query += fmt.Sprintf(" AND timestamp <= $%d", paramCount)
		args = append(args, opts.EndDate)
	}

	paramCount++
	query += fmt.Sprintf(" ORDER BY timestamp DESC LIMIT $%d OFFSET $%d", paramCount, paramCount+1)
	args = append(args, opts.Limit, opts.Offset)

	rows, err := c.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	return c.scanRevisions(rows)
}

// GetRevision retrieves a specific revision by ID.
func (c *postgresClient) GetRevision(ctx context.Context, revisionID int64) (*Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE revision_id = $1
	`

	var rev Revision
	var parentID sql.NullInt64
	var user sql.NullString
	var userID sql.NullInt64
	var comment sql.NullString
	var tagsJSON sql.NullString

	err := c.db.QueryRowContext(ctx, query, revisionID).Scan(
		&rev.ID, &rev.PageID, &parentID, &rev.Timestamp, &user, &userID,
		&comment, &rev.Content, &rev.Size, &rev.SHA1, &rev.Minor, &tagsJSON,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Handle nullable fields
	if parentID.Valid {
		pid := parentID.Int64
		rev.ParentID = &pid
	}
	if user.Valid {
		rev.User = user.String
	}
	if userID.Valid {
		uid := int(userID.Int64)
		rev.UserID = &uid
	}
	if comment.Valid {
		rev.Comment = comment.String
	}
	if tagsJSON.Valid && tagsJSON.String != "" {
		json.Unmarshal([]byte(tagsJSON.String), &rev.Tags)
	}

	return &rev, nil
}

// GetPageAtTime retrieves the page content as it existed at a specific timestamp.
func (c *postgresClient) GetPageAtTime(ctx context.Context, title string, timestamp time.Time) (*Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// First, get the page ID
	var pageID int64
	err := c.db.QueryRowContext(ctx, "SELECT page_id FROM pages WHERE title = $1", title).Scan(&pageID)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE page_id = $1 AND timestamp <= $2
		ORDER BY timestamp DESC
		LIMIT 1
	`

	var rev Revision
	var parentID sql.NullInt64
	var user sql.NullString
	var userID sql.NullInt64
	var comment sql.NullString
	var tagsJSON sql.NullString

	err = c.db.QueryRowContext(ctx, query, pageID, timestamp).Scan(
		&rev.ID, &rev.PageID, &parentID, &rev.Timestamp, &user, &userID,
		&comment, &rev.Content, &rev.Size, &rev.SHA1, &rev.Minor, &tagsJSON,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Handle nullable fields
	if parentID.Valid {
		pid := parentID.Int64
		rev.ParentID = &pid
	}
	if user.Valid {
		rev.User = user.String
	}
	if userID.Valid {
		uid := int(userID.Int64)
		rev.UserID = &uid
	}
	if comment.Valid {
		rev.Comment = comment.String
	}
	if tagsJSON.Valid && tagsJSON.String != "" {
		json.Unmarshal([]byte(tagsJSON.String), &rev.Tags)
	}

	return &rev, nil
}

// GetChangesByPeriod retrieves all revisions within a time range.
func (c *postgresClient) GetChangesByPeriod(ctx context.Context, start, end time.Time) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE timestamp BETWEEN $1 AND $2
		ORDER BY timestamp DESC
	`

	rows, err := c.db.QueryContext(ctx, query, start, end)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	return c.scanRevisions(rows)
}

// GetEditorActivity retrieves all revisions by a specific user within a time range.
func (c *postgresClient) GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE user = $1 AND timestamp BETWEEN $2 AND $3
		ORDER BY timestamp DESC
	`

	rows, err := c.db.QueryContext(ctx, query, username, start, end)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	return c.scanRevisions(rows)
}

// scanRevisions is a helper function to scan multiple revisions from rows.
func (c *postgresClient) scanRevisions(rows *sql.Rows) ([]Revision, error) {
	var revisions []Revision

	for rows.Next() {
		var rev Revision
		var parentID sql.NullInt64
		var user sql.NullString
		var userID sql.NullInt64
		var comment sql.NullString
		var tagsJSON sql.NullString

		err := rows.Scan(
			&rev.ID, &rev.PageID, &parentID, &rev.Timestamp, &user, &userID,
			&comment, &rev.Content, &rev.Size, &rev.SHA1, &rev.Minor, &tagsJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		// Handle nullable fields
		if parentID.Valid {
			pid := parentID.Int64
			rev.ParentID = &pid
		}
		if user.Valid {
			rev.User = user.String
		}
		if userID.Valid {
			uid := int(userID.Int64)
			rev.UserID = &uid
		}
		if comment.Valid {
			rev.Comment = comment.String
		}
		if tagsJSON.Valid && tagsJSON.String != "" {
			json.Unmarshal([]byte(tagsJSON.String), &rev.Tags)
		}

		revisions = append(revisions, rev)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return revisions, nil
}

// GetStatistics returns overall wiki statistics.
func (c *postgresClient) GetStatistics(ctx context.Context) (*Statistics, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	stats := &Statistics{
		PagesByNamespace: make(map[int]int64),
	}

	// Get total pages
	err := c.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM pages").Scan(&stats.TotalPages)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Get total revisions
	err = c.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM revisions").Scan(&stats.TotalRevisions)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Get total files
	err = c.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM files").Scan(&stats.TotalFiles)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Get pages by namespace
	rows, err := c.db.QueryContext(ctx, "SELECT namespace, COUNT(*) FROM pages GROUP BY namespace")
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	for rows.Next() {
		var namespace int
		var count int64
		if err := rows.Scan(&namespace, &count); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}
		stats.PagesByNamespace[namespace] = count
	}

	// Get unique editors
	err = c.db.QueryRowContext(ctx, "SELECT COUNT(DISTINCT user_id) FROM revisions WHERE user_id IS NOT NULL").Scan(&stats.TotalEditors)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Get first and last edit times
	var firstEdit, lastEdit sql.NullTime
	err = c.db.QueryRowContext(ctx, "SELECT MIN(timestamp), MAX(timestamp) FROM revisions").Scan(&firstEdit, &lastEdit)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	if firstEdit.Valid {
		stats.FirstEdit = firstEdit.Time
	}
	if lastEdit.Valid {
		stats.LastEdit = lastEdit.Time
	}

	return stats, nil
}

// GetPageStats returns statistics for a specific page.
func (c *postgresClient) GetPageStats(ctx context.Context, title string) (*PageStatistics, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Get page ID
	var pageID int64
	var pageTitle string
	err := c.db.QueryRowContext(ctx, "SELECT page_id, title FROM pages WHERE title = $1", title).Scan(&pageID, &pageTitle)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	stats := &PageStatistics{
		PageID: pageID,
		Title:  pageTitle,
	}

	// Get revision count and other stats
	const query = `
		SELECT 
			COUNT(*) as revision_count,
			COUNT(DISTINCT user_id) as editor_count,
			MIN(timestamp) as first_edit,
			MAX(timestamp) as last_edit,
			AVG(size) as avg_size,
			SUM(CASE WHEN minor = true THEN 1 ELSE 0 END) as minor_edits
		FROM revisions
		WHERE page_id = $1
	`

	var firstEdit, lastEdit sql.NullTime
	var avgSize sql.NullFloat64
	err = c.db.QueryRowContext(ctx, query, pageID).Scan(
		&stats.RevisionCount, &stats.EditorCount, &firstEdit, &lastEdit, &avgSize, &stats.MinorEdits,
	)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	if firstEdit.Valid {
		stats.FirstEdit = firstEdit.Time
	}
	if lastEdit.Valid {
		stats.LastEdit = lastEdit.Time
	}
	if avgSize.Valid {
		stats.AverageEditSize = avgSize.Float64
	}
	stats.TotalEdits = stats.RevisionCount

	return stats, nil
}

// GetFile retrieves file metadata by filename.
func (c *postgresClient) GetFile(ctx context.Context, filename string) (*File, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader
		FROM files
		WHERE filename = $1
	`

	var file File
	var width, height sql.NullInt64
	var uploader sql.NullString

	err := c.db.QueryRowContext(ctx, query, filename).Scan(
		&file.Filename, &file.URL, &file.DescriptionURL, &file.SHA1, &file.Size,
		&width, &height, &file.MimeType, &file.Timestamp, &uploader,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	if width.Valid {
		w := int(width.Int64)
		file.Width = &w
	}
	if height.Valid {
		h := int(height.Int64)
		file.Height = &h
	}
	if uploader.Valid {
		file.Uploader = uploader.String
	}

	return &file, nil
}

// ListFiles returns a paginated list of all files.
func (c *postgresClient) ListFiles(ctx context.Context, offset, limit int) ([]File, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	if limit == 0 {
		limit = 100
	}

	const query = `
		SELECT filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader
		FROM files
		ORDER BY filename
		LIMIT $1 OFFSET $2
	`

	rows, err := c.db.QueryContext(ctx, query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var files []File
	for rows.Next() {
		var file File
		var width, height sql.NullInt64
		var uploader sql.NullString

		err := rows.Scan(
			&file.Filename, &file.URL, &file.DescriptionURL, &file.SHA1, &file.Size,
			&width, &height, &file.MimeType, &file.Timestamp, &uploader,
		)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		if width.Valid {
			w := int(width.Int64)
			file.Width = &w
		}
		if height.Valid {
			h := int(height.Int64)
			file.Height = &h
		}
		if uploader.Valid {
			file.Uploader = uploader.String
		}

		files = append(files, file)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return files, nil
}

// Ping checks if the database connection is alive.
func (c *postgresClient) Ping(ctx context.Context) error {
	if err := c.ensureNotClosed(); err != nil {
		return err
	}

	return c.db.PingContext(ctx)
}

// GetRevisionDiff computes the diff between two revisions.
// Uses the same implementation as SQLite since the diff logic is database-agnostic.
func (c *postgresClient) GetRevisionDiff(ctx context.Context, fromRevID, toRevID int64) (*DiffResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Fetch both revisions
	fromRev, err := c.GetRevision(ctx, fromRevID)
	if err != nil {
		return nil, fmt.Errorf("failed to get from revision: %w", err)
	}

	toRev, err := c.GetRevision(ctx, toRevID)
	if err != nil {
		return nil, fmt.Errorf("failed to get to revision: %w", err)
	}

	// Ensure they're for the same page
	if fromRev.PageID != toRev.PageID {
		return nil, fmt.Errorf("%w: revisions are for different pages", ErrInvalidInput)
	}

	return computeDiff(fromRev, toRev), nil
}

// GetConsecutiveDiff computes the diff from a revision to its parent.
func (c *postgresClient) GetConsecutiveDiff(ctx context.Context, revID int64) (*DiffResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Get the revision
	toRev, err := c.GetRevision(ctx, revID)
	if err != nil {
		return nil, err
	}

	// Check if it has a parent
	if toRev.ParentID == nil {
		// This is the first revision - diff from empty
		return computeDiffFromEmpty(toRev), nil
	}

	// Get parent revision (using PostgreSQL placeholder $1)
	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE revision_id = $1
	`

	var fromRev Revision
	var parentID sql.NullInt64
	var user sql.NullString
	var userID sql.NullInt64
	var comment sql.NullString
	var tagsJSON sql.NullString

	err = c.db.QueryRowContext(ctx, query, *toRev.ParentID).Scan(
		&fromRev.ID, &fromRev.PageID, &parentID, &fromRev.Timestamp, &user, &userID,
		&comment, &fromRev.Content, &fromRev.Size, &fromRev.SHA1, &fromRev.Minor, &tagsJSON,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Handle nullable fields
	if parentID.Valid {
		pid := parentID.Int64
		fromRev.ParentID = &pid
	}
	if user.Valid {
		fromRev.User = user.String
	}
	if userID.Valid {
		uid := int(userID.Int64)
		fromRev.UserID = &uid
	}
	if comment.Valid {
		fromRev.Comment = comment.String
	}
	if tagsJSON.Valid && tagsJSON.String != "" {
		json.Unmarshal([]byte(tagsJSON.String), &fromRev.Tags)
	}

	return computeDiff(&fromRev, toRev), nil
}

// GetStatisticsEnhanced retrieves comprehensive enhanced wiki statistics for PostgreSQL.
// Note: This is a stub implementation. Full PostgreSQL-specific implementation coming in future release.
func (c *postgresClient) GetStatisticsEnhanced(ctx context.Context) (*StatisticsEnhanced, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	return nil, fmt.Errorf("GetStatisticsEnhanced not yet implemented for PostgreSQL backend")
}

// GetPageStatsEnhanced retrieves enhanced statistics for a specific page for PostgreSQL.
// Note: This is a stub implementation. Full PostgreSQL-specific implementation coming in future release.
func (c *postgresClient) GetPageStatsEnhanced(ctx context.Context, title string) (*PageStatisticsEnhanced, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	return nil, fmt.Errorf("GetPageStatsEnhanced not yet implemented for PostgreSQL backend")
}

// GetEditorActivityEnhanced retrieves enhanced activity for an editor for PostgreSQL.
// Note: This is a stub implementation. Full PostgreSQL-specific implementation coming in future release.
func (c *postgresClient) GetEditorActivityEnhanced(ctx context.Context, username string, start, end time.Time) (*EditorActivity, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	return nil, fmt.Errorf("GetEditorActivityEnhanced not yet implemented for PostgreSQL backend")
}

// Close cleanly shuts down the client and releases resources.
func (c *postgresClient) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return ErrClosed
	}

	c.closed = true

	if err := c.db.Close(); err != nil {
		return fmt.Errorf("%w: failed to close database: %v", ErrDatabaseError, err)
	}

	return nil
}
