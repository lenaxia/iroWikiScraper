package irowiki

import "time"

// Page represents a wiki page with its latest content.
type Page struct {
	// ID is the unique page identifier.
	ID int64

	// Namespace is the MediaWiki namespace (0=Main, 2=User, 6=File, etc.).
	Namespace int

	// Title is the page title without namespace prefix.
	Title string

	// IsRedirect indicates if this page is a redirect.
	IsRedirect bool

	// LatestRevisionID is the revision ID of the current version.
	LatestRevisionID int64

	// Content is the wikitext content of the latest revision.
	Content string

	// Timestamp is when the latest revision was created.
	Timestamp time.Time

	// User is the username of the last editor.
	User string

	// Comment is the edit summary of the latest revision.
	Comment string
}

// Revision represents a single edit/revision of a page.
type Revision struct {
	// ID is the unique revision identifier.
	ID int64

	// PageID is the ID of the page this revision belongs to.
	PageID int64

	// ParentID is the ID of the previous revision (nil for first revision).
	ParentID *int64

	// Timestamp is when this edit was made.
	Timestamp time.Time

	// User is the username of the editor.
	User string

	// UserID is the numeric user ID (nil for anonymous edits).
	UserID *int

	// Comment is the edit summary provided by the editor.
	Comment string

	// Content is the wikitext content at this revision.
	Content string

	// Size is the content size in bytes.
	Size int

	// SHA1 is the content hash for duplicate detection.
	SHA1 string

	// Minor indicates if this was marked as a minor edit.
	Minor bool

	// Tags are edit tags (e.g., "visual edit", "mobile edit").
	Tags []string
}

// File represents an uploaded file (image, document, etc.).
type File struct {
	// Filename is the unique file name (e.g., "Example.png").
	Filename string

	// URL is the direct URL to download the file.
	URL string

	// DescriptionURL is the URL to the file description page.
	DescriptionURL string

	// SHA1 is the file content hash.
	SHA1 string

	// Size is the file size in bytes.
	Size int

	// Width is the image width in pixels (nil for non-images).
	Width *int

	// Height is the image height in pixels (nil for non-images).
	Height *int

	// MimeType is the file MIME type (e.g., "image/png").
	MimeType string

	// Timestamp is when the file was uploaded.
	Timestamp time.Time

	// Uploader is the username of the uploader.
	Uploader string
}

// SearchResult represents a search result with relevance information.
type SearchResult struct {
	// PageID is the unique page identifier.
	PageID int64

	// Namespace is the MediaWiki namespace.
	Namespace int

	// Title is the page title.
	Title string

	// Snippet is a text snippet showing the match context (for full-text search).
	Snippet string

	// Timestamp is when the page was last modified.
	Timestamp time.Time

	// Relevance is the search relevance score (for full-text search, higher is better).
	// For FTS searches, this is typically the BM25 score.
	Relevance float64

	// MatchType indicates where the match occurred ("title", "content", "fulltext").
	MatchType string
}

// PagedResult wraps search results with pagination metadata.
type PagedResult struct {
	// Results contains the search results for the current page.
	Results []SearchResult

	// Total is the total number of results across all pages (optional, may be 0 if not computed).
	Total int

	// Offset is the starting position of these results.
	Offset int

	// Limit is the maximum number of results per page.
	Limit int

	// HasMore indicates if there are more results beyond this page.
	HasMore bool
}

// PageInfo provides detailed pagination information.
type PageInfo struct {
	// CurrentPage is the current page number (1-indexed).
	CurrentPage int

	// TotalPages is the total number of pages (0 if Total is unknown).
	TotalPages int

	// PageSize is the number of results per page.
	PageSize int

	// Total is the total number of results.
	Total int

	// HasNext indicates if there is a next page.
	HasNext bool

	// HasPrev indicates if there is a previous page.
	HasPrev bool
}

// GetPageInfo calculates pagination information from PagedResult.
func (pr *PagedResult) GetPageInfo() PageInfo {
	currentPage := 1
	if pr.Limit > 0 {
		currentPage = pr.Offset/pr.Limit + 1
	}

	totalPages := 0
	if pr.Total > 0 && pr.Limit > 0 {
		totalPages = (pr.Total + pr.Limit - 1) / pr.Limit
	}

	return PageInfo{
		CurrentPage: currentPage,
		TotalPages:  totalPages,
		PageSize:    pr.Limit,
		Total:       pr.Total,
		HasNext:     pr.HasMore,
		HasPrev:     pr.Offset > 0,
	}
}

// NextOffset returns the offset for the next page.
func (pr *PagedResult) NextOffset() int {
	if !pr.HasMore {
		return pr.Offset
	}
	return pr.Offset + pr.Limit
}

// PrevOffset returns the offset for the previous page.
func (pr *PagedResult) PrevOffset() int {
	if pr.Offset == 0 {
		return 0
	}
	prev := pr.Offset - pr.Limit
	if prev < 0 {
		return 0
	}
	return prev
}

// Statistics represents overall wiki statistics.
type Statistics struct {
	// TotalPages is the total number of pages.
	TotalPages int64

	// TotalRevisions is the total number of revisions across all pages.
	TotalRevisions int64

	// TotalFiles is the total number of uploaded files.
	TotalFiles int64

	// PagesByNamespace is a map of namespace to page count.
	PagesByNamespace map[int]int64

	// TotalEditors is the number of unique editors.
	TotalEditors int64

	// FirstEdit is the timestamp of the oldest revision.
	FirstEdit time.Time

	// LastEdit is the timestamp of the newest revision.
	LastEdit time.Time
}

// PageStatistics represents statistics for a specific page.
type PageStatistics struct {
	// PageID is the unique page identifier.
	PageID int64

	// Title is the page title.
	Title string

	// RevisionCount is the total number of revisions.
	RevisionCount int64

	// EditorCount is the number of unique editors.
	EditorCount int64

	// FirstEdit is the timestamp of the first revision.
	FirstEdit time.Time

	// LastEdit is the timestamp of the latest revision.
	LastEdit time.Time

	// AverageEditSize is the average size of revisions in bytes.
	AverageEditSize float64

	// TotalEdits is the total number of edits (including minor edits).
	TotalEdits int64

	// MinorEdits is the number of minor edits.
	MinorEdits int64
}

// DiffResult contains the comparison between two revisions.
type DiffResult struct {
	// FromRevision is the ID of the older revision.
	FromRevision int64

	// ToRevision is the ID of the newer revision.
	ToRevision int64

	// FromTimestamp is when the older revision was created.
	FromTimestamp time.Time

	// ToTimestamp is when the newer revision was created.
	ToTimestamp time.Time

	// Unified is the unified diff format output.
	Unified string

	// Stats contains statistical information about the changes.
	Stats DiffStats
}

// DiffStats contains statistical information about changes between revisions.
type DiffStats struct {
	// LinesAdded is the number of lines added.
	LinesAdded int

	// LinesRemoved is the number of lines removed.
	LinesRemoved int

	// LinesChanged is the number of lines changed (removed + added pairs).
	LinesChanged int

	// CharsAdded is the number of characters added.
	CharsAdded int

	// CharsRemoved is the number of characters removed.
	CharsRemoved int

	// ChangePercent is the percentage of content changed (0-100).
	ChangePercent float64
}

// StatisticsEnhanced contains enhanced comprehensive archive statistics.
type StatisticsEnhanced struct {
	// Basic counts
	TotalPages     int64 `json:"total_pages"`
	TotalRevisions int64 `json:"total_revisions"`
	TotalFiles     int64 `json:"total_files"`
	TotalEditors   int64 `json:"total_editors"`

	// Temporal
	FirstEdit     time.Time `json:"first_edit"`
	LastEdit      time.Time `json:"last_edit"`
	ActiveEditors int64     `json:"active_editors"` // Last 30 days

	// Size
	TotalContentSize int64 `json:"total_content_size"`
	AveragePageSize  int   `json:"average_page_size"`
	MedianPageSize   int   `json:"median_page_size"`

	// Distribution
	PagesByNamespace map[int]int64    `json:"namespace_distribution"`
	EditsByMonth     map[string]int64 `json:"edits_by_month"`
	TopEditors       []EditorStat     `json:"top_editors"`
	MostEditedPages  []PageStat       `json:"most_edited_pages"`

	// Extremes
	LargestPage  *PageInfoStat `json:"largest_page,omitempty"`
	SmallestPage *PageInfoStat `json:"smallest_page,omitempty"`
}

// PageInfoStat contains basic page information for statistics.
type PageInfoStat struct {
	ID        int64  `json:"id"`
	Title     string `json:"title"`
	Namespace int    `json:"namespace"`
	Size      int    `json:"size"`
}

// PageStat contains page statistics.
type PageStat struct {
	PageID        int64  `json:"page_id"`
	PageTitle     string `json:"page_title"`
	RevisionCount int    `json:"revision_count"`
	EditorCount   int    `json:"editor_count"`
}

// EditorStat contains editor statistics.
type EditorStat struct {
	Username    string    `json:"username"`
	EditCount   int       `json:"edit_count"`
	FirstEdit   time.Time `json:"first_edit"`
	LastEdit    time.Time `json:"last_edit"`
	MinorEdits  int       `json:"minor_edits"`
	PagesEdited int       `json:"pages_edited"`
}

// PageStatisticsEnhanced contains enhanced comprehensive statistics for a page.
type PageStatisticsEnhanced struct {
	// Basic info
	PageID        int64  `json:"page_id"`
	Title         string `json:"page_title"`
	PageNamespace int    `json:"page_namespace"`

	// Revision stats
	RevisionCount  int64          `json:"revision_count"`
	FirstEdit      time.Time      `json:"first_edit"`
	LastEdit       time.Time      `json:"last_edit"`
	AvgTimeBetween time.Duration  `json:"avg_time_between_edits"`
	EditFrequency  map[string]int `json:"edit_frequency"` // Month -> count

	// Contributor stats
	EditorCount       int               `json:"editor_count"`
	AnonEditors       int               `json:"anon_editors"`
	RegisteredEditors int               `json:"registered_editors"`
	TopContributors   []ContributorStat `json:"top_contributors"`

	// Size stats
	CurrentSize  int `json:"current_size"`
	OriginalSize int `json:"original_size"`
	MaxSize      int `json:"max_size"`
	MinSize      int `json:"min_size"`
	AvgSize      int `json:"avg_size"`

	// Quality metrics
	MinorEditPercent float64 `json:"minor_edit_percent"`
	AvgCommentLength float64 `json:"avg_comment_length"`
	RevertCount      int     `json:"revert_count"`
	StabilityScore   float64 `json:"stability_score"`

	// Activity patterns
	BusiestMonth string        `json:"busiest_month,omitempty"`
	LongestGap   time.Duration `json:"longest_gap"`
}

// ContributorStat represents a contributor's statistics.
type ContributorStat struct {
	Username   string    `json:"username"`
	EditCount  int       `json:"edit_count"`
	FirstEdit  time.Time `json:"first_edit"`
	LastEdit   time.Time `json:"last_edit"`
	MinorEdits int       `json:"minor_edits"`
	Percentage float64   `json:"percentage"`
}

// EditorActivity contains comprehensive editor statistics.
type EditorActivity struct {
	Username    string `json:"username"`
	UserID      *int64 `json:"user_id,omitempty"`
	IsAnonymous bool   `json:"is_anonymous"`

	// Basic stats
	TotalEdits int       `json:"total_edits"`
	FirstEdit  time.Time `json:"first_edit"`
	LastEdit   time.Time `json:"last_edit"`
	ActiveDays int       `json:"active_days"`

	// Content stats
	PagesEdited int `json:"pages_edited"`
	MinorEdits  int `json:"minor_edits"`

	// Activity patterns
	EditsByHour  map[int]int    `json:"edits_by_hour"`
	EditsByDay   map[string]int `json:"edits_by_day"`
	EditsByMonth map[string]int `json:"edits_by_month"`
	BusiestHour  int            `json:"busiest_hour"`
	BusiestDay   string         `json:"busiest_day"`

	// Top pages
	TopPages []PageEditStat `json:"top_pages"`
}

// PageEditStat represents editing statistics for a page.
type PageEditStat struct {
	PageID    int64     `json:"page_id"`
	PageTitle string    `json:"page_title"`
	EditCount int       `json:"edit_count"`
	FirstEdit time.Time `json:"first_edit"`
	LastEdit  time.Time `json:"last_edit"`
}
