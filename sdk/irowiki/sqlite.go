package irowiki

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	_ "modernc.org/sqlite"
)

// sqliteClient implements the Client interface for SQLite databases.
type sqliteClient struct {
	db     *sql.DB
	opts   ConnectionOptions
	closed bool
	mu     sync.RWMutex
}

// OpenSQLite opens a SQLite database at the specified path with default options.
// The database is opened in read-only mode by default.
//
// Example:
//
//	client, err := irowiki.OpenSQLite("irowiki.db")
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Close()
func OpenSQLite(path string) (Client, error) {
	return OpenSQLiteWithOptions(path, DefaultSQLiteOptions())
}

// OpenSQLiteWithOptions opens a SQLite database with custom connection options.
func OpenSQLiteWithOptions(path string, opts ConnectionOptions) (Client, error) {
	opts.applyDefaults(true)

	// Open database with appropriate mode
	dsn := path
	if path != ":memory:" {
		dsn = path + "?mode=ro"
	}

	db, err := sql.Open("sqlite", dsn)
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

	client := &sqliteClient{
		db:     db,
		opts:   opts,
		closed: false,
	}

	return client, nil
}

// ensureNotClosed checks if the client is closed and returns an error if it is.
func (c *sqliteClient) ensureNotClosed() error {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if c.closed {
		return ErrClosed
	}
	return nil
}

// GetPage retrieves the latest version of a page by title.
func (c *sqliteClient) GetPage(ctx context.Context, title string) (*Page, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT p.page_id, p.namespace, p.title, p.is_redirect,
		       r.revision_id, r.timestamp, r.user, r.comment, r.content
		FROM pages p
		LEFT JOIN revisions r ON p.page_id = r.page_id
		WHERE p.title = ?
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
func (c *sqliteClient) GetPageByID(ctx context.Context, id int64) (*Page, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT p.page_id, p.namespace, p.title, p.is_redirect,
		       r.revision_id, r.timestamp, r.user, r.comment, r.content
		FROM pages p
		LEFT JOIN revisions r ON p.page_id = r.page_id
		WHERE p.page_id = ?
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
func (c *sqliteClient) ListPages(ctx context.Context, namespace int, offset, limit int) ([]Page, error) {
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
		LEFT JOIN (
			SELECT page_id, revision_id, timestamp, user, comment, content,
			       ROW_NUMBER() OVER (PARTITION BY page_id ORDER BY timestamp DESC) as rn
			FROM revisions
		) r ON p.page_id = r.page_id AND r.rn = 1
		WHERE p.namespace = ?
		ORDER BY p.page_id
		LIMIT ? OFFSET ?
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

// Search performs a search across page titles with advanced filtering and sorting.
func (c *sqliteClient) Search(ctx context.Context, opts SearchOptions) ([]SearchResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Validate and apply defaults
	if err := opts.Validate(); err != nil {
		return nil, fmt.Errorf("invalid search options: %w", err)
	}
	opts.SetDefaults()

	// Build query with filters
	query, args := c.buildSearchQuery(opts)

	rows, err := c.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var result SearchResult
		var timestamp sql.NullTime
		var snippet sql.NullString

		err := rows.Scan(&result.PageID, &result.Namespace, &result.Title, &timestamp, &snippet, &result.Relevance)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		if timestamp.Valid {
			result.Timestamp = timestamp.Time
		}
		if snippet.Valid {
			result.Snippet = snippet.String
		}
		result.MatchType = "title"

		results = append(results, result)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return results, nil
}

// buildSearchQuery constructs the SQL query for title search with filters.
func (c *sqliteClient) buildSearchQuery(opts SearchOptions) (string, []interface{}) {
	var args []interface{}

	// Pre-allocate for relevance calculation args
	exactMatch := ""
	caseInsMatch := ""
	if opts.Query != "" {
		exactMatch = opts.Query
		caseInsMatch = opts.Query
	}

	query := `
		SELECT
			p.page_id,
			p.namespace,
			p.title,
			(SELECT r2.timestamp FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1) as timestamp,
			(SELECT SUBSTR(r2.content, 1, 100) FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1) as snippet,
			CASE 
				WHEN p.title LIKE ? THEN 10.0
				WHEN LOWER(p.title) LIKE LOWER(?) THEN 5.0
				ELSE 1.0
			END as relevance
		FROM pages p
		WHERE 1=1
	`

	// Arguments for relevance calculation (always needed)
	args = append(args, exactMatch, caseInsMatch)

	// Add query filter if provided (case-insensitive)
	if opts.Query != "" {
		query += " AND LOWER(p.title) LIKE LOWER(?)"
		args = append(args, "%"+opts.Query+"%")
	}

	// Add filters
	filterQuery, filterArgs := c.buildFilters(opts)
	query += filterQuery
	args = append(args, filterArgs...)

	// Add sorting
	query += c.buildSortClause(opts)

	// Add pagination
	query += " LIMIT ? OFFSET ?"
	args = append(args, opts.Limit, opts.Offset)

	return query, args
}

// buildFilters constructs WHERE clause conditions from SearchOptions.
func (c *sqliteClient) buildFilters(opts SearchOptions) (string, []interface{}) {
	var conditions []string
	var args []interface{}

	// Namespace filters
	if len(opts.Namespaces) > 0 {
		placeholders := make([]string, len(opts.Namespaces))
		for i, ns := range opts.Namespaces {
			placeholders[i] = "?"
			args = append(args, ns)
		}
		conditions = append(conditions, fmt.Sprintf("p.namespace IN (%s)", join(placeholders, ",")))
	} else if opts.Namespace >= 0 {
		conditions = append(conditions, "p.namespace = ?")
		args = append(args, opts.Namespace)
	}

	if len(opts.ExcludeNamespaces) > 0 {
		placeholders := make([]string, len(opts.ExcludeNamespaces))
		for i, ns := range opts.ExcludeNamespaces {
			placeholders[i] = "?"
			args = append(args, ns)
		}
		conditions = append(conditions, fmt.Sprintf("p.namespace NOT IN (%s)", join(placeholders, ",")))
	}

	// Date range filters (based on latest revision timestamp)
	if opts.CreatedAfter != nil {
		conditions = append(conditions, "(SELECT MIN(r2.timestamp) FROM revisions r2 WHERE r2.page_id = p.page_id) >= ?")
		args = append(args, *opts.CreatedAfter)
	}
	if opts.CreatedBefore != nil {
		conditions = append(conditions, "(SELECT MIN(r2.timestamp) FROM revisions r2 WHERE r2.page_id = p.page_id) <= ?")
		args = append(args, *opts.CreatedBefore)
	}
	if opts.ModifiedAfter != nil {
		conditions = append(conditions, "(SELECT MAX(r2.timestamp) FROM revisions r2 WHERE r2.page_id = p.page_id) >= ?")
		args = append(args, *opts.ModifiedAfter)
	}
	if opts.ModifiedBefore != nil {
		conditions = append(conditions, "(SELECT MAX(r2.timestamp) FROM revisions r2 WHERE r2.page_id = p.page_id) <= ?")
		args = append(args, *opts.ModifiedBefore)
	}

	// Size filters (use subquery to get latest revision size)
	if opts.MinSize != nil {
		conditions = append(conditions, "(SELECT r2.size FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1) >= ?")
		args = append(args, *opts.MinSize)
	}
	if opts.MaxSize != nil {
		conditions = append(conditions, "(SELECT r2.size FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1) <= ?")
		args = append(args, *opts.MaxSize)
	}

	// Redirect filters
	if opts.OnlyRedirects {
		conditions = append(conditions, "p.is_redirect = 1")
	} else if opts.ExcludeRedirects {
		conditions = append(conditions, "p.is_redirect = 0")
	}

	if len(conditions) == 0 {
		return "", nil
	}

	return " AND " + join(conditions, " AND "), args
}

// buildSortClause constructs ORDER BY clause from SearchOptions.
func (c *sqliteClient) buildSortClause(opts SearchOptions) string {
	orderBy := " ORDER BY "

	switch opts.SortBy {
	case "relevance":
		orderBy += "relevance"
	case "date":
		// Use subquery for latest revision timestamp
		orderBy += "(SELECT r2.timestamp FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1)"
	case "size":
		// Use subquery for latest revision size
		orderBy += "(SELECT r2.size FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1)"
	case "title":
		fallthrough
	default:
		orderBy += "p.title"
	}

	if opts.SortOrder == "asc" {
		orderBy += " ASC"
	} else {
		orderBy += " DESC"
	}

	return orderBy
}

// SearchFullText performs full-text search using FTS5 across page content.
func (c *sqliteClient) SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	if query == "" {
		return nil, fmt.Errorf("query cannot be empty")
	}

	// Validate and apply defaults
	if err := opts.Validate(); err != nil {
		return nil, fmt.Errorf("invalid search options: %w", err)
	}
	opts.SetDefaults()

	// Build FTS query
	sqlQuery, args := c.buildFullTextQuery(query, opts)

	rows, err := c.db.QueryContext(ctx, sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var result SearchResult
		var timestamp sql.NullTime

		err := rows.Scan(&result.PageID, &result.Namespace, &result.Title, &timestamp, &result.Snippet, &result.Relevance)
		if err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}

		if timestamp.Valid {
			result.Timestamp = timestamp.Time
		}
		result.MatchType = "fulltext"

		results = append(results, result)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	return results, nil
}

// buildFullTextQuery constructs the FTS5 SQL query.
func (c *sqliteClient) buildFullTextQuery(query string, opts SearchOptions) (string, []interface{}) {
	sqlQuery := `
		SELECT 
			p.page_id,
			p.namespace,
			p.title,
			(SELECT r2.timestamp FROM revisions r2 WHERE r2.page_id = p.page_id ORDER BY r2.timestamp DESC LIMIT 1) as timestamp,
			snippet(pages_fts, -1, '<mark>', '</mark>', '...', 20) as snippet,
			bm25(pages_fts, 10.0, 1.0) as relevance
		FROM pages_fts
		JOIN pages p ON pages_fts.page_id = p.page_id
		WHERE pages_fts MATCH ?
	`

	var args []interface{}
	args = append(args, query)

	// Add filters (namespace, date range, etc.)
	filterQuery, filterArgs := c.buildFilters(opts)
	sqlQuery += filterQuery
	args = append(args, filterArgs...)

	// Add score threshold filter
	if opts.MinScore != 0 {
		sqlQuery += " AND bm25(pages_fts, 10.0, 1.0) >= ?"
		args = append(args, opts.MinScore)
	}

	// Sort by relevance (BM25 score)
	sqlQuery += " ORDER BY relevance DESC"

	// Add pagination
	sqlQuery += " LIMIT ? OFFSET ?"
	args = append(args, opts.Limit, opts.Offset)

	return sqlQuery, args
}

// Helper function to join strings
func join(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}

// GetPageHistory retrieves the revision history for a page.
func (c *sqliteClient) GetPageHistory(ctx context.Context, title string, opts HistoryOptions) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// First, get the page ID
	var pageID int64
	err := c.db.QueryRowContext(ctx, "SELECT page_id FROM pages WHERE title = ?", title).Scan(&pageID)
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
		WHERE page_id = ?
	`
	args := []interface{}{pageID}

	if !opts.StartDate.IsZero() {
		query += " AND timestamp >= ?"
		args = append(args, opts.StartDate)
	}
	if !opts.EndDate.IsZero() {
		query += " AND timestamp <= ?"
		args = append(args, opts.EndDate)
	}

	query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
	args = append(args, opts.Limit, opts.Offset)

	rows, err := c.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	return c.scanRevisions(rows)
}

// GetRevision retrieves a specific revision by ID.
func (c *sqliteClient) GetRevision(ctx context.Context, revisionID int64) (*Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE revision_id = ?
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
func (c *sqliteClient) GetPageAtTime(ctx context.Context, title string, timestamp time.Time) (*Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// First, get the page ID
	var pageID int64
	err := c.db.QueryRowContext(ctx, "SELECT page_id FROM pages WHERE title = ?", title).Scan(&pageID)
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
		WHERE page_id = ? AND timestamp <= ?
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
func (c *sqliteClient) GetChangesByPeriod(ctx context.Context, start, end time.Time) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE timestamp BETWEEN ? AND ?
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
func (c *sqliteClient) GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE user = ? AND timestamp BETWEEN ? AND ?
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
func (c *sqliteClient) scanRevisions(rows *sql.Rows) ([]Revision, error) {
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
func (c *sqliteClient) GetStatistics(ctx context.Context) (*Statistics, error) {
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
	var firstEditStr, lastEditStr sql.NullString
	err = c.db.QueryRowContext(ctx, "SELECT MIN(timestamp), MAX(timestamp) FROM revisions").Scan(&firstEditStr, &lastEditStr)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	if firstEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", firstEditStr.String); err == nil {
			stats.FirstEdit = t
		} else if t, err := time.Parse(time.RFC3339, firstEditStr.String); err == nil {
			stats.FirstEdit = t
		}
	}
	if lastEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", lastEditStr.String); err == nil {
			stats.LastEdit = t
		} else if t, err := time.Parse(time.RFC3339, lastEditStr.String); err == nil {
			stats.LastEdit = t
		}
	}

	return stats, nil
}

// GetPageStats returns statistics for a specific page.
func (c *sqliteClient) GetPageStats(ctx context.Context, title string) (*PageStatistics, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Get page ID
	var pageID int64
	var pageTitle string
	err := c.db.QueryRowContext(ctx, "SELECT page_id, title FROM pages WHERE title = ?", title).Scan(&pageID, &pageTitle)
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
			SUM(CASE WHEN minor = 1 THEN 1 ELSE 0 END) as minor_edits
		FROM revisions
		WHERE page_id = ?
	`

	var firstEditStr, lastEditStr sql.NullString
	var avgSize sql.NullFloat64
	err = c.db.QueryRowContext(ctx, query, pageID).Scan(
		&stats.RevisionCount, &stats.EditorCount, &firstEditStr, &lastEditStr, &avgSize, &stats.MinorEdits,
	)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	if firstEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", firstEditStr.String); err == nil {
			stats.FirstEdit = t
		} else if t, err := time.Parse(time.RFC3339, firstEditStr.String); err == nil {
			stats.FirstEdit = t
		}
	}
	if lastEditStr.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", lastEditStr.String); err == nil {
			stats.LastEdit = t
		} else if t, err := time.Parse(time.RFC3339, lastEditStr.String); err == nil {
			stats.LastEdit = t
		}
	}
	if avgSize.Valid {
		stats.AverageEditSize = avgSize.Float64
	}
	stats.TotalEdits = stats.RevisionCount

	return stats, nil
}

// GetFile retrieves file metadata by filename.
func (c *sqliteClient) GetFile(ctx context.Context, filename string) (*File, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	const query = `
		SELECT filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader
		FROM files
		WHERE filename = ?
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
func (c *sqliteClient) ListFiles(ctx context.Context, offset, limit int) ([]File, error) {
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
		LIMIT ? OFFSET ?
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
func (c *sqliteClient) Ping(ctx context.Context) error {
	if err := c.ensureNotClosed(); err != nil {
		return err
	}

	return c.db.PingContext(ctx)
}

// Close cleanly shuts down the client and releases resources.
func (c *sqliteClient) Close() error {
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
