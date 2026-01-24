# Story 05: Data Models

**Story ID**: epic-05-story-05  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** well-defined data models for wiki entities  
**So that** I can work with strongly-typed data structures that match the database schema

## Acceptance Criteria

1. **Core Models**
   - [ ] Page model with all fields
   - [ ] Revision model with content and metadata
   - [ ] File model for uploaded files
   - [ ] User model for editor information

2. **Search Models**
   - [ ] SearchResult with relevance scoring
   - [ ] SearchOptions with all filter fields
   - [ ] Pagination metadata

3. **Statistics Models**
   - [ ] Statistics aggregate data
   - [ ] PageStatistics for individual pages
   - [ ] EditorStatistics for user activity

4. **Helper Methods**
   - [ ] JSON marshaling support
   - [ ] String formatting for display
   - [ ] Validation methods
   - [ ] Type conversion utilities

## Technical Details

### Core Data Models

```go
package irowiki

import (
    "time"
    "encoding/json"
)

// Page represents a wiki page
type Page struct {
    ID           int64     `json:"id"`
    Title        string    `json:"title"`
    Namespace    int       `json:"namespace"`
    LatestRevID  int64     `json:"latest_rev_id"`
    Created      time.Time `json:"created"`
    Modified     time.Time `json:"modified"`
    RevisionCount int      `json:"revision_count"`
    IsRedirect   bool      `json:"is_redirect"`
    RedirectTo   *string   `json:"redirect_to,omitempty"`
}

// Revision represents a page revision
type Revision struct {
    ID           int64     `json:"id"`
    PageID       int64     `json:"page_id"`
    PageTitle    string    `json:"page_title"`
    Timestamp    time.Time `json:"timestamp"`
    Username     string    `json:"username"`
    UserID       *int64    `json:"user_id,omitempty"`
    Comment      string    `json:"comment"`
    Content      string    `json:"content"`
    ContentSize  int       `json:"content_size"`
    IsMinor      bool      `json:"is_minor"`
    SHA1         string    `json:"sha1"`
}

// File represents an uploaded file
type File struct {
    Name        string    `json:"name"`
    URL         string    `json:"url"`
    Size        int64     `json:"size"`
    MimeType    string    `json:"mime_type"`
    Width       *int      `json:"width,omitempty"`
    Height      *int      `json:"height,omitempty"`
    Timestamp   time.Time `json:"timestamp"`
    Uploader    string    `json:"uploader"`
    Description string    `json:"description"`
}

// User represents a wiki editor
type User struct {
    ID           int64     `json:"id"`
    Name         string    `json:"name"`
    EditCount    int       `json:"edit_count"`
    FirstEdit    time.Time `json:"first_edit"`
    LastEdit     time.Time `json:"last_edit"`
    IsBot        bool      `json:"is_bot"`
    IsAdmin      bool      `json:"is_admin"`
}
```

### Search Models

```go
// SearchResult represents a search result with relevance
type SearchResult struct {
    Page
    Snippet   string  `json:"snippet"`
    Score     float64 `json:"score"`
    MatchType string  `json:"match_type"` // "title", "content", "fulltext"
}

// SearchOptions configures search queries
type SearchOptions struct {
    Query       string
    Namespace   *int
    MatchType   string    // "title", "content", "fulltext", "any"
    MinScore    float64
    StartDate   *time.Time
    EndDate     *time.Time
    Offset      int
    Limit       int
    SortBy      string    // "relevance", "date", "title"
    SortOrder   string    // "asc", "desc"
}

// PagedResult contains results with pagination metadata
type PagedResult struct {
    Results    []SearchResult `json:"results"`
    Total      int            `json:"total"`
    Offset     int            `json:"offset"`
    Limit      int            `json:"limit"`
    HasMore    bool           `json:"has_more"`
}
```

### Statistics Models

```go
// Statistics contains aggregate archive statistics
type Statistics struct {
    TotalPages      int       `json:"total_pages"`
    TotalRevisions  int       `json:"total_revisions"`
    TotalFiles      int       `json:"total_files"`
    TotalEditors    int       `json:"total_editors"`
    FirstEdit       time.Time `json:"first_edit"`
    LastEdit        time.Time `json:"last_edit"`
    ActiveEditors   int       `json:"active_editors"`   // Last 30 days
    DatabaseSize    int64     `json:"database_size"`
    ContentSize     int64     `json:"content_size"`
}

// PageStatistics contains statistics for a specific page
type PageStatistics struct {
    PageID          int64     `json:"page_id"`
    PageTitle       string    `json:"page_title"`
    RevisionCount   int       `json:"revision_count"`
    EditorCount     int       `json:"editor_count"`
    FirstEdit       time.Time `json:"first_edit"`
    LastEdit        time.Time `json:"last_edit"`
    AverageRevSize  int       `json:"average_rev_size"`
    TotalEdits      int       `json:"total_edits"`
    MinorEdits      int       `json:"minor_edits"`
    TopEditors      []EditorStat `json:"top_editors"`
}

// EditorStat represents editor activity stats
type EditorStat struct {
    Username      string    `json:"username"`
    EditCount     int       `json:"edit_count"`
    FirstEdit     time.Time `json:"first_edit"`
    LastEdit      time.Time `json:"last_edit"`
    MinorEdits    int       `json:"minor_edits"`
    BytesAdded    int       `json:"bytes_added"`
    BytesRemoved  int       `json:"bytes_removed"`
}
```

### Helper Methods

```go
// String returns a human-readable representation
func (p *Page) String() string {
    return fmt.Sprintf("Page{ID: %d, Title: %q, Revisions: %d}",
        p.ID, p.Title, p.RevisionCount)
}

// Validate checks if the model is valid
func (opts *SearchOptions) Validate() error {
    if opts.Limit < 0 {
        return fmt.Errorf("limit must be non-negative")
    }
    if opts.Offset < 0 {
        return fmt.Errorf("offset must be non-negative")
    }
    if opts.Limit > 1000 {
        return fmt.Errorf("limit must not exceed 1000")
    }
    return nil
}

// SetDefaults applies default values to SearchOptions
func (opts *SearchOptions) SetDefaults() {
    if opts.Limit == 0 {
        opts.Limit = 20
    }
    if opts.SortBy == "" {
        opts.SortBy = "relevance"
    }
    if opts.SortOrder == "" {
        opts.SortOrder = "desc"
    }
}
```

## Dependencies

- Story 01: Client Interface Design
- Epic 02: Database Schema (field definitions)

## Implementation Notes

- Use pointer fields for optional values
- All timestamps should be UTC
- Provide JSON tags for API serialization
- Consider adding `omitempty` for optional fields
- Add validation methods for user input
- Support scanning from database rows
- Consider using `sql.NullString` for nullable fields

## Testing Requirements

- [ ] Model creation and field access tests
- [ ] JSON marshaling/unmarshaling tests
- [ ] Validation method tests
- [ ] String formatting tests
- [ ] Database scanning tests
- [ ] Edge case tests (nil values, empty strings)

## Definition of Done

- [ ] All models defined in `sdk/irowiki/models.go`
- [ ] JSON serialization working
- [ ] Validation methods implemented
- [ ] Helper methods added
- [ ] All tests passing
- [ ] Godoc examples provided
- [ ] Code reviewed and approved
