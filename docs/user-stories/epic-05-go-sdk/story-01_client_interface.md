# Story 01: Client Interface Design

**Story ID**: epic-05-story-01  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** Go developer  
**I want** a well-designed client interface for accessing wiki archive data  
**So that** I can query the archive with a clean, idiomatic Go API

## Acceptance Criteria

1. **Interface Definition**
   - [x] Define `Client` interface with all query methods
   - [x] Interface follows Go naming conventions
   - [x] All methods return `(result, error)` tuple
   - [x] Context support for cancellation and timeouts

2. **Core Methods**
   - [x] Search methods (title, content, full-text)
   - [x] Page query methods (by ID, by title, list)
   - [x] Revision query methods (history, by ID, at time)
   - [x] Statistics methods
   - [x] File query methods
   - [x] Close() for cleanup

3. **Options Structures**
   - [x] `SearchOptions` with filters and pagination
   - [x] `HistoryOptions` with date range
   - [x] All options use functional options pattern or structs

4. **Error Handling**
   - [x] Custom error types for common scenarios
   - [x] `ErrNotFound` for missing entities
   - [x] `ErrClosed` for operations on closed client
   - [x] Wrapped errors preserve context

## Technical Details

### Interface Definition

```go
package irowiki

import (
    "context"
    "time"
)

// Client provides methods to query wiki archive data
type Client interface {
    // Search
    Search(ctx context.Context, opts SearchOptions) ([]SearchResult, error)
    SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error)
    
    // Pages
    GetPage(ctx context.Context, title string) (*Page, error)
    GetPageByID(ctx context.Context, id int64) (*Page, error)
    ListPages(ctx context.Context, namespace int, offset, limit int) ([]Page, error)
    
    // Revisions
    GetPageHistory(ctx context.Context, title string, opts HistoryOptions) ([]Revision, error)
    GetRevision(ctx context.Context, revisionID int64) (*Revision, error)
    GetPageAtTime(ctx context.Context, title string, timestamp time.Time) (*Revision, error)
    
    // Timeline
    GetChangesByPeriod(ctx context.Context, start, end time.Time) ([]Revision, error)
    GetEditorActivity(ctx context.Context, username string, start, end time.Time) ([]Revision, error)
    
    // Statistics
    GetStatistics(ctx context.Context) (*Statistics, error)
    GetPageStats(ctx context.Context, title string) (*PageStatistics, error)
    
    // Files
    GetFile(ctx context.Context, filename string) (*File, error)
    ListFiles(ctx context.Context, offset, limit int) ([]File, error)
    
    // Lifecycle
    Close() error
}

// SearchOptions configures search queries
type SearchOptions struct {
    Query     string
    Namespace int
    Offset    int
    Limit     int
}

// HistoryOptions configures history queries
type HistoryOptions struct {
    StartDate time.Time
    EndDate   time.Time
    Offset    int
    Limit     int
}
```

### Error Types

```go
package irowiki

import "errors"

var (
    ErrNotFound = errors.New("entity not found")
    ErrClosed   = errors.New("client is closed")
    ErrInvalidInput = errors.New("invalid input")
)
```

## Dependencies

- None (this is the foundation)

## Implementation Notes

- Use `context.Context` for all query methods
- Follow standard library patterns (database/sql, net/http)
- Interface should be backend-agnostic
- Options structs should use pointer fields for optional parameters

## Testing Requirements

- [ ] Unit tests for option validation
- [ ] Mock implementations for testing consumers
- [ ] Example usage in godoc comments
- [ ] Interface compliance tests for implementations

## Definition of Done

- [ ] Interface defined in `sdk/irowiki/client.go`
- [ ] All methods documented with examples
- [ ] Option structs defined with validation
- [ ] Error types defined
- [ ] Unit tests passing
- [ ] Godoc generated and reviewed
- [ ] Code reviewed and approved
