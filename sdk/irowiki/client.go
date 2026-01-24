// Package irowiki provides a Go SDK for querying iRO Wiki archive data.
//
// The SDK supports both SQLite and PostgreSQL backends, offering a clean,
// idiomatic Go API for accessing wiki pages, revisions, files, and statistics.
//
// Example usage with SQLite:
//
//	client, err := irowiki.OpenSQLite("irowiki.db")
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Close()
//
//	// Search for pages
//	results, err := client.Search(ctx, irowiki.SearchOptions{
//	    Query:     "Poring",
//	    Namespace: 0,
//	    Limit:     10,
//	})
//
//	// Get page history
//	history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{
//	    Limit: 50,
//	})
//
// Example usage with PostgreSQL:
//
//	client, err := irowiki.OpenPostgres("postgres://user:pass@localhost/irowiki")
//	if err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Close()
package irowiki

import (
	"context"
	"time"
)

// Client provides methods to query wiki archive data.
// All query methods accept a context for cancellation and timeout control.
// The client is safe for concurrent use by multiple goroutines.
type Client interface {
	// Search performs a search across pages.
	// Returns pages matching the search criteria with pagination support.
	Search(ctx context.Context, opts SearchOptions) ([]SearchResult, error)

	// SearchFullText performs full-text search across page content.
	// Uses the database's full-text search capabilities for relevance ranking.
	SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error)

	// GetPage retrieves the latest version of a page by title.
	// Returns ErrNotFound if the page doesn't exist.
	GetPage(ctx context.Context, title string) (*Page, error)

	// GetPageByID retrieves the latest version of a page by ID.
	// Returns ErrNotFound if the page doesn't exist.
	GetPageByID(ctx context.Context, id int64) (*Page, error)

	// ListPages returns a paginated list of pages in the specified namespace.
	// Use offset and limit for pagination. Set limit to 0 for default (100).
	ListPages(ctx context.Context, namespace int, offset, limit int) ([]Page, error)

	// GetPageHistory retrieves the revision history for a page.
	// Returns revisions in reverse chronological order (newest first).
	GetPageHistory(ctx context.Context, title string, opts HistoryOptions) ([]Revision, error)

	// GetRevision retrieves a specific revision by ID.
	// Returns ErrNotFound if the revision doesn't exist.
	GetRevision(ctx context.Context, revisionID int64) (*Revision, error)

	// GetPageAtTime retrieves the page content as it existed at a specific timestamp.
	// Returns the most recent revision at or before the specified time.
	// Returns ErrNotFound if the page didn't exist at that time.
	GetPageAtTime(ctx context.Context, title string, timestamp time.Time) (*Revision, error)

	// GetChangesByPeriod retrieves all revisions within a time range.
	// Useful for analyzing editing activity over a period.
	GetChangesByPeriod(ctx context.Context, start, end time.Time) ([]Revision, error)

	// GetEditorActivity retrieves all revisions by a specific user within a time range.
	// Use for contributor analysis and statistics.
	GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error)

	// GetStatistics returns overall wiki statistics.
	// Includes counts of pages, revisions, files, and storage metrics.
	GetStatistics(ctx context.Context) (*Statistics, error)

	// GetStatisticsEnhanced returns comprehensive enhanced wiki statistics.
	// Includes top editors, most edited pages, size distributions, and temporal patterns.
	GetStatisticsEnhanced(ctx context.Context) (*StatisticsEnhanced, error)

	// GetPageStats returns statistics for a specific page.
	// Includes revision count, contributor count, and edit frequency.
	GetPageStats(ctx context.Context, title string) (*PageStatistics, error)

	// GetPageStatsEnhanced returns enhanced statistics for a specific page.
	// Includes contributor details, size trends, quality metrics, and activity patterns.
	GetPageStatsEnhanced(ctx context.Context, title string) (*PageStatisticsEnhanced, error)

	// GetEditorActivityEnhanced retrieves enhanced activity analysis for an editor.
	// Includes content statistics, activity patterns, and top pages edited.
	GetEditorActivityEnhanced(ctx context.Context, username string, start, end time.Time) (*EditorActivity, error)

	// GetRevisionDiff computes the diff between two revisions.
	// Returns a unified diff showing additions and removals.
	// Returns ErrNotFound if either revision doesn't exist.
	// Returns ErrInvalidInput if revisions are from different pages.
	GetRevisionDiff(ctx context.Context, fromRevID, toRevID int64) (*DiffResult, error)

	// GetConsecutiveDiff computes the diff from a revision to its parent.
	// Useful for seeing what changed in a specific edit.
	// Returns ErrNotFound if the revision doesn't exist or has no parent.
	GetConsecutiveDiff(ctx context.Context, revID int64) (*DiffResult, error)

	// GetFile retrieves file metadata by filename.
	// Returns ErrNotFound if the file doesn't exist.
	GetFile(ctx context.Context, filename string) (*File, error)

	// ListFiles returns a paginated list of all files.
	// Use offset and limit for pagination. Set limit to 0 for default (100).
	ListFiles(ctx context.Context, offset, limit int) ([]File, error)

	// Ping checks if the database connection is alive.
	// Use for health checks and connection validation.
	Ping(ctx context.Context) error

	// Close cleanly shuts down the client and releases resources.
	// After calling Close, the client should not be used.
	Close() error
}

// SearchOptions configures search queries with advanced filtering.
type SearchOptions struct {
	// Query is the search term. For full-text search, supports wildcards.
	Query string

	// Namespace filters results to a specific namespace.
	// Use -1 to search across all namespaces (default: -1).
	Namespace int

	// Namespaces filters results to multiple specific namespaces.
	// Takes precedence over Namespace if set.
	Namespaces []int

	// ExcludeNamespaces excludes specific namespaces from results.
	ExcludeNamespaces []int

	// CreatedAfter filters pages created on or after this time.
	CreatedAfter *time.Time

	// CreatedBefore filters pages created on or before this time.
	CreatedBefore *time.Time

	// ModifiedAfter filters pages modified on or after this time.
	ModifiedAfter *time.Time

	// ModifiedBefore filters pages modified on or before this time.
	ModifiedBefore *time.Time

	// MinSize filters pages with content size >= this value (bytes).
	MinSize *int

	// MaxSize filters pages with content size <= this value (bytes).
	MaxSize *int

	// IncludeRedirects includes redirect pages in results (default: true).
	IncludeRedirects bool

	// OnlyRedirects returns only redirect pages.
	OnlyRedirects bool

	// ExcludeRedirects excludes redirect pages from results.
	ExcludeRedirects bool

	// SortBy specifies the sort field: "relevance", "title", "date", "size".
	// Default: "relevance" for searches, "title" for listings.
	SortBy string

	// SortOrder specifies sort direction: "asc" or "desc".
	// Default: "desc" for relevance/date, "asc" for title.
	SortOrder string

	// MinScore filters results with relevance score >= this value.
	// Only applies to full-text searches.
	MinScore float64

	// Offset is the number of results to skip (for pagination).
	Offset int

	// Limit is the maximum number of results to return.
	// Set to 0 for default limit (20).
	Limit int

	// IncludeTotalCount computes the total result count (may be expensive).
	IncludeTotalCount bool
}

// HistoryOptions configures history queries.
type HistoryOptions struct {
	// StartDate filters revisions on or after this date (optional).
	StartDate time.Time

	// EndDate filters revisions on or before this date (optional).
	EndDate time.Time

	// Offset is the number of results to skip (for pagination).
	Offset int

	// Limit is the maximum number of results to return.
	// Set to 0 for default limit (100).
	Limit int
}
