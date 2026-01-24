package irowiki_test

import (
	"context"
	"testing"
	"time"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/internal/testutil"
	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

// TestSearchOptions_Validate tests SearchOptions validation
func TestSearchOptions_Validate(t *testing.T) {
	tests := []struct {
		name    string
		opts    irowiki.SearchOptions
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid options",
			opts: irowiki.SearchOptions{
				Query:     "test",
				Namespace: 0,
				Limit:     20,
				Offset:    0,
			},
			wantErr: false,
		},
		{
			name: "negative limit",
			opts: irowiki.SearchOptions{
				Limit: -1,
			},
			wantErr: true,
			errMsg:  "limit must be non-negative",
		},
		{
			name: "limit exceeds maximum",
			opts: irowiki.SearchOptions{
				Limit: 2000,
			},
			wantErr: true,
			errMsg:  "limit must not exceed 1000",
		},
		{
			name: "negative offset",
			opts: irowiki.SearchOptions{
				Offset: -1,
			},
			wantErr: true,
			errMsg:  "offset must be non-negative",
		},
		{
			name: "invalid date range - created",
			opts: irowiki.SearchOptions{
				CreatedAfter:  &time.Time{},
				CreatedBefore: &time.Time{},
			},
			wantErr: false, // Zero times are equal
		},
		{
			name: "invalid date range - modified",
			opts: func() irowiki.SearchOptions {
				after := time.Now()
				before := after.Add(-24 * time.Hour)
				return irowiki.SearchOptions{
					ModifiedAfter:  &after,
					ModifiedBefore: &before,
				}
			}(),
			wantErr: true,
			errMsg:  "modified_after must be before or equal to modified_before",
		},
		{
			name: "invalid size range",
			opts: func() irowiki.SearchOptions {
				min := 100
				max := 50
				return irowiki.SearchOptions{
					MinSize: &min,
					MaxSize: &max,
				}
			}(),
			wantErr: true,
			errMsg:  "min_size must be less than or equal to max_size",
		},
		{
			name: "conflicting redirect filters",
			opts: irowiki.SearchOptions{
				OnlyRedirects:    true,
				ExcludeRedirects: true,
			},
			wantErr: true,
			errMsg:  "only one of OnlyRedirects or ExcludeRedirects can be true",
		},
		{
			name: "invalid sort by",
			opts: irowiki.SearchOptions{
				SortBy: "invalid",
			},
			wantErr: true,
			errMsg:  "invalid sort_by",
		},
		{
			name: "invalid sort order",
			opts: irowiki.SearchOptions{
				SortOrder: "invalid",
			},
			wantErr: true,
			errMsg:  "invalid sort_order",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.opts.Validate()
			if tt.wantErr {
				if err == nil {
					t.Errorf("expected error containing %q, got nil", tt.errMsg)
				} else if tt.errMsg != "" && !contains(err.Error(), tt.errMsg) {
					t.Errorf("expected error containing %q, got %q", tt.errMsg, err.Error())
				}
			} else {
				if err != nil {
					t.Errorf("expected no error, got %v", err)
				}
			}
		})
	}
}

// TestSearchOptions_SetDefaults tests default value application
func TestSearchOptions_SetDefaults(t *testing.T) {
	tests := []struct {
		name     string
		opts     irowiki.SearchOptions
		expected irowiki.SearchOptions
	}{
		{
			name: "apply all defaults",
			opts: irowiki.SearchOptions{},
			expected: irowiki.SearchOptions{
				Limit:            20,
				SortBy:           "title",
				SortOrder:        "asc",
				Namespace:        0,
				IncludeRedirects: true,
			},
		},
		{
			name: "search with query defaults to relevance sort",
			opts: irowiki.SearchOptions{
				Query: "test",
			},
			expected: irowiki.SearchOptions{
				Query:            "test",
				Limit:            20,
				SortBy:           "relevance",
				SortOrder:        "desc",
				Namespace:        0,
				IncludeRedirects: true,
			},
		},
		{
			name: "preserve custom values",
			opts: irowiki.SearchOptions{
				Limit:     50,
				SortBy:    "date",
				SortOrder: "asc",
			},
			expected: irowiki.SearchOptions{
				Limit:            50,
				SortBy:           "date",
				SortOrder:        "asc",
				Namespace:        0,
				IncludeRedirects: true,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.opts.SetDefaults()

			if tt.opts.Limit != tt.expected.Limit {
				t.Errorf("Limit: expected %d, got %d", tt.expected.Limit, tt.opts.Limit)
			}
			if tt.opts.SortBy != tt.expected.SortBy {
				t.Errorf("SortBy: expected %q, got %q", tt.expected.SortBy, tt.opts.SortBy)
			}
			if tt.opts.SortOrder != tt.expected.SortOrder {
				t.Errorf("SortOrder: expected %q, got %q", tt.expected.SortOrder, tt.opts.SortOrder)
			}
			if tt.opts.Namespace != tt.expected.Namespace {
				t.Errorf("Namespace: expected %d, got %d", tt.expected.Namespace, tt.opts.Namespace)
			}
			if tt.opts.IncludeRedirects != tt.expected.IncludeRedirects {
				t.Errorf("IncludeRedirects: expected %v, got %v", tt.expected.IncludeRedirects, tt.opts.IncludeRedirects)
			}
		})
	}
}

// TestPagedResult_GetPageInfo tests pagination info calculation
func TestPagedResult_GetPageInfo(t *testing.T) {
	tests := []struct {
		name     string
		result   irowiki.PagedResult
		expected irowiki.PageInfo
	}{
		{
			name: "first page with more results",
			result: irowiki.PagedResult{
				Total:   100,
				Offset:  0,
				Limit:   20,
				HasMore: true,
			},
			expected: irowiki.PageInfo{
				CurrentPage: 1,
				TotalPages:  5,
				PageSize:    20,
				Total:       100,
				HasNext:     true,
				HasPrev:     false,
			},
		},
		{
			name: "middle page",
			result: irowiki.PagedResult{
				Total:   100,
				Offset:  40,
				Limit:   20,
				HasMore: true,
			},
			expected: irowiki.PageInfo{
				CurrentPage: 3,
				TotalPages:  5,
				PageSize:    20,
				Total:       100,
				HasNext:     true,
				HasPrev:     true,
			},
		},
		{
			name: "last page",
			result: irowiki.PagedResult{
				Total:   100,
				Offset:  80,
				Limit:   20,
				HasMore: false,
			},
			expected: irowiki.PageInfo{
				CurrentPage: 5,
				TotalPages:  5,
				PageSize:    20,
				Total:       100,
				HasNext:     false,
				HasPrev:     true,
			},
		},
		{
			name: "unknown total",
			result: irowiki.PagedResult{
				Total:   0,
				Offset:  20,
				Limit:   20,
				HasMore: true,
			},
			expected: irowiki.PageInfo{
				CurrentPage: 2,
				TotalPages:  0,
				PageSize:    20,
				Total:       0,
				HasNext:     true,
				HasPrev:     true,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			info := tt.result.GetPageInfo()

			if info.CurrentPage != tt.expected.CurrentPage {
				t.Errorf("CurrentPage: expected %d, got %d", tt.expected.CurrentPage, info.CurrentPage)
			}
			if info.TotalPages != tt.expected.TotalPages {
				t.Errorf("TotalPages: expected %d, got %d", tt.expected.TotalPages, info.TotalPages)
			}
			if info.HasNext != tt.expected.HasNext {
				t.Errorf("HasNext: expected %v, got %v", tt.expected.HasNext, info.HasNext)
			}
			if info.HasPrev != tt.expected.HasPrev {
				t.Errorf("HasPrev: expected %v, got %v", tt.expected.HasPrev, info.HasPrev)
			}
		})
	}
}

// TestSearch_TitleSearch tests title-based searching
func TestSearch_TitleSearch(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	tests := []struct {
		name          string
		opts          irowiki.SearchOptions
		wantCount     int
		wantTitles    []string
		wantNamespace int
	}{
		{
			name: "search for 'Main'",
			opts: irowiki.SearchOptions{
				Query: "Main",
			},
			wantCount:  1,
			wantTitles: []string{"Main_Page"},
		},
		{
			name: "search for 'Por' prefix",
			opts: irowiki.SearchOptions{
				Query: "Por",
			},
			wantCount:  1,
			wantTitles: []string{"Poring"},
		},
		{
			name: "case-insensitive search",
			opts: irowiki.SearchOptions{
				Query: "poring",
			},
			wantCount:  1,
			wantTitles: []string{"Poring"},
		},
		{
			name: "search in namespace 0",
			opts: irowiki.SearchOptions{
				Query:     "P",
				Namespace: 0,
			},
			wantCount:  3,
			wantTitles: []string{"Main_Page", "Poring", "Prontera"},
		},
		{
			name: "search in namespace 6",
			opts: irowiki.SearchOptions{
				Query:     "Example",
				Namespace: 6,
			},
			wantCount:  1,
			wantTitles: []string{"Example.png"},
		},
		{
			name: "empty results",
			opts: irowiki.SearchOptions{
				Query: "NonExistent",
			},
			wantCount: 0,
		},
		{
			name: "pagination - first page",
			opts: irowiki.SearchOptions{
				Query:  "P",
				Limit:  1,
				Offset: 0,
			},
			wantCount: 1,
		},
		{
			name: "pagination - second page",
			opts: irowiki.SearchOptions{
				Query:  "P",
				Limit:  1,
				Offset: 1,
			},
			wantCount: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := client.Search(ctx, tt.opts)
			if err != nil {
				t.Fatalf("Search failed: %v", err)
			}

			if len(results) != tt.wantCount {
				t.Errorf("expected %d results, got %d", tt.wantCount, len(results))
			}

			if tt.wantTitles != nil {
				titles := make([]string, len(results))
				for i, r := range results {
					titles[i] = r.Title
				}
				if !equalSlices(titles, tt.wantTitles) {
					t.Errorf("expected titles %v, got %v", tt.wantTitles, titles)
				}
			}
		})
	}
}

// TestSearchFullText tests full-text search functionality
func TestSearchFullText(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	tests := []struct {
		name       string
		query      string
		opts       irowiki.SearchOptions
		wantCount  int
		wantTitles []string
		checkScore bool
	}{
		{
			name:       "search for 'wiki'",
			query:      "wiki",
			opts:       irowiki.SearchOptions{},
			wantCount:  1,
			wantTitles: []string{"Main_Page"},
			checkScore: true,
		},
		{
			name:       "search for 'Poring'",
			query:      "Poring",
			opts:       irowiki.SearchOptions{},
			wantCount:  1,
			wantTitles: []string{"Poring"},
			checkScore: true,
		},
		{
			name:       "search for 'city'",
			query:      "city",
			opts:       irowiki.SearchOptions{},
			wantCount:  1,
			wantTitles: []string{"Prontera"},
			checkScore: true,
		},
		{
			name:      "search with min score filter",
			query:     "monster",
			opts:      irowiki.SearchOptions{MinScore: -10.0}, // BM25 scores are usually negative
			wantCount: 1,
		},
		{
			name:      "no results",
			query:     "nonexistent",
			opts:      irowiki.SearchOptions{},
			wantCount: 0,
		},
		{
			name:      "empty query returns error",
			query:     "",
			opts:      irowiki.SearchOptions{},
			wantCount: -1, // Expect error
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := client.SearchFullText(ctx, tt.query, tt.opts)

			if tt.wantCount == -1 {
				if err == nil {
					t.Error("expected error for empty query, got nil")
				}
				return
			}

			if err != nil {
				t.Fatalf("SearchFullText failed: %v", err)
			}

			if len(results) != tt.wantCount {
				t.Errorf("expected %d results, got %d", tt.wantCount, len(results))
			}

			if tt.wantTitles != nil {
				titles := make([]string, len(results))
				for i, r := range results {
					titles[i] = r.Title
				}
				if !equalSlices(titles, tt.wantTitles) {
					t.Errorf("expected titles %v, got %v", tt.wantTitles, titles)
				}
			}

			if tt.checkScore && len(results) > 0 {
				for _, r := range results {
					if r.Relevance == 0 {
						t.Error("expected non-zero relevance score")
					}
					if r.MatchType != "fulltext" {
						t.Errorf("expected MatchType 'fulltext', got %q", r.MatchType)
					}
					if r.Snippet == "" {
						t.Error("expected non-empty snippet")
					}
				}
			}
		})
	}
}

// TestSearch_AdvancedFilters tests advanced filtering options
func TestSearch_AdvancedFilters(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	baseTime := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)

	tests := []struct {
		name      string
		opts      irowiki.SearchOptions
		wantCount int
		wantErr   bool
	}{
		{
			name: "filter by date range",
			opts: irowiki.SearchOptions{
				ModifiedAfter:  ptrTime(baseTime),
				ModifiedBefore: ptrTime(baseTime.Add(48 * time.Hour)),
			},
			wantCount: 1, // Main_Page (latest rev at baseTime+24h) - Prontera's latest rev is at baseTime+72h (outside range)
		},
		{
			name: "filter by size range",
			opts: func() irowiki.SearchOptions {
				min := 20
				max := 30
				return irowiki.SearchOptions{
					MinSize: &min,
					MaxSize: &max,
				}
			}(),
			wantCount: 3, // Pages with content size 20-30 bytes: Main_Page (25), Prontera (29), Redirect_Test (20)
		},
		{
			name: "exclude redirects",
			opts: irowiki.SearchOptions{
				ExcludeRedirects: true,
				Namespace:        -1, // Search all namespaces
			},
			wantCount: 4, // All pages except Redirect_Test
		},
		{
			name: "only redirects",
			opts: irowiki.SearchOptions{
				OnlyRedirects: true,
			},
			wantCount: 1, // Only Redirect_Test
		},
		{
			name: "multiple namespaces",
			opts: irowiki.SearchOptions{
				Namespaces: []int{0, 6},
			},
			wantCount: 5, // All test pages
		},
		{
			name: "exclude namespace",
			opts: irowiki.SearchOptions{
				ExcludeNamespaces: []int{6},
			},
			wantCount: 4, // All except Example.png
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := client.Search(ctx, tt.opts)

			if tt.wantErr {
				if err == nil {
					t.Error("expected error, got nil")
				}
				return
			}

			if err != nil {
				t.Fatalf("Search failed: %v", err)
			}

			if len(results) != tt.wantCount {
				t.Errorf("expected %d results, got %d", tt.wantCount, len(results))
			}
		})
	}
}

// TestSearch_Sorting tests result sorting
func TestSearch_Sorting(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	tests := []struct {
		name          string
		opts          irowiki.SearchOptions
		wantFirst     string
		wantLast      string
		checkOrdering bool
	}{
		{
			name: "sort by title asc",
			opts: irowiki.SearchOptions{
				SortBy:    "title",
				SortOrder: "asc",
			},
			wantFirst:     "Main_Page",
			checkOrdering: true,
		},
		{
			name: "sort by title desc",
			opts: irowiki.SearchOptions{
				SortBy:    "title",
				SortOrder: "desc",
			},
			wantFirst:     "Redirect_Test", // Highest alphabetically in namespace 0
			checkOrdering: true,
		},
		{
			name: "sort by date desc (newest first)",
			opts: irowiki.SearchOptions{
				SortBy:    "date",
				SortOrder: "desc",
				Namespace: -1, // All namespaces
			},
			wantFirst: "Redirect_Test", // Most recent revision (baseTime + 144h)
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := client.Search(ctx, tt.opts)
			if err != nil {
				t.Fatalf("Search failed: %v", err)
			}

			if len(results) == 0 {
				t.Fatal("expected results, got empty")
			}

			if tt.wantFirst != "" && results[0].Title != tt.wantFirst {
				t.Errorf("expected first result %q, got %q", tt.wantFirst, results[0].Title)
			}

			if tt.wantLast != "" && results[len(results)-1].Title != tt.wantLast {
				t.Errorf("expected last result %q, got %q", tt.wantLast, results[len(results)-1].Title)
			}

			if tt.checkOrdering && len(results) > 1 {
				// Verify ordering is consistent with sort direction
				if tt.opts.SortBy == "title" {
					for i := 0; i < len(results)-1; i++ {
						if tt.opts.SortOrder == "asc" {
							if results[i].Title > results[i+1].Title {
								t.Errorf("results not sorted ascending: %q > %q", results[i].Title, results[i+1].Title)
							}
						} else {
							if results[i].Title < results[i+1].Title {
								t.Errorf("results not sorted descending: %q < %q", results[i].Title, results[i+1].Title)
							}
						}
					}
				}
			}
		})
	}
}

// Helper functions
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) > 0 && anyIndexOf(s, substr) >= 0)
}

func anyIndexOf(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return i
		}
	}
	return -1
}

func equalSlices(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func ptrTime(t time.Time) *time.Time {
	return &t
}
