# Epic 05: Go SDK

**Epic ID**: epic-05  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2 weeks

## Overview

Build a Go SDK for querying archived wiki data with support for both SQLite and PostgreSQL backends. Provide idiomatic Go API for search, timeline queries, page history, and statistics with a CLI tool for interactive exploration.

## Goals

1. Implement dual backend support (SQLite and PostgreSQL)
2. Provide search functionality (title, content, full-text)
3. Enable timeline queries (content at specific dates)
4. Support page history retrieval
5. Implement statistics and analytics queries
6. Create CLI tool for interactive queries
7. Provide usage examples and documentation

## Success Criteria

- ✅ SDK works with both SQLite and PostgreSQL
- ✅ Query performance <100ms for common operations
- ✅ Full-text search returns relevant results
- ✅ Timeline queries return accurate historical content
- ✅ CLI tool provides user-friendly interface
- ✅ API follows Go idioms and best practices
- ✅ 80%+ test coverage on SDK code

## User Stories

### Core Client
- [Story 01: Client Interface Design](story-01_client_interface.md)
- [Story 02: SQLite Backend](story-02_sqlite_backend.md)
- [Story 03: PostgreSQL Backend](story-03_postgres_backend.md)
- [Story 04: Connection Management](story-04_connection_management.md)
- [Story 05: Data Models](story-05_data_models.md)

### Search & Query
- [Story 06: Page Search](story-06_page_search.md)
- [Story 07: Full-Text Search](story-07_fulltext_search.md)
- [Story 08: Advanced Filters](story-08_advanced_filters.md)
- [Story 09: Pagination Support](story-09_pagination.md)

### History & Timeline
- [Story 10: Page History Query](story-10_page_history.md)
- [Story 11: Get Page at Timestamp](story-11_page_at_time.md)
- [Story 12: Timeline Changes Query](story-12_timeline_changes.md)
- [Story 13: Revision Diff](story-13_revision_diff.md)

### Statistics & Analytics
- [Story 14: Archive Statistics](story-14_archive_stats.md)
- [Story 15: Page Statistics](story-15_page_stats.md)
- [Story 16: Editor Activity](story-16_editor_activity.md)

### CLI Tool
- [Story 17: CLI Framework Setup](story-17_cli_framework.md)
- [Story 18: Search Command](story-18_cli_search.md)
- [Story 19: History Command](story-19_cli_history.md)
- [Story 20: Stats Command](story-20_cli_stats.md)

### Documentation & Examples
- [Story 21: API Documentation](story-21_api_docs.md)
- [Story 22: Usage Examples](story-22_examples.md)
- [Story 23: CLI Help System](story-23_cli_help.md)

## Dependencies

### Requires:
- Epic 02: Database (schema to query against)
- Epic 04: Export (test data to query)

### Blocks:
- None (SDK is consumer of archive data)

## Technical Notes

### Client Interface Design

```go
package irowiki

type Client interface {
    // Search
    Search(opts SearchOptions) ([]SearchResult, error)
    SearchFullText(query string, opts SearchOptions) ([]SearchResult, error)
    
    // Pages
    GetPage(title string) (*Page, error)
    GetPageByID(id int64) (*Page, error)
    ListPages(namespace int, offset, limit int) ([]Page, error)
    
    // Revisions
    GetPageHistory(title string, opts HistoryOptions) ([]Revision, error)
    GetRevision(revisionID int64) (*Revision, error)
    GetPageAtTime(title string, timestamp time.Time) (*Revision, error)
    
    // Timeline
    GetChangesByPeriod(start, end time.Time) ([]Revision, error)
    GetEditorActivity(username string, start, end time.Time) ([]Revision, error)
    
    // Statistics
    GetStatistics() (*Statistics, error)
    GetPageStats(title string) (*PageStatistics, error)
    
    // Files
    GetFile(filename string) (*File, error)
    ListFiles(offset, limit int) ([]File, error)
    
    Close() error
}
```

### Example Usage

```go
package main

import (
    "fmt"
    "time"
    
    "github.com/user/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
    // Open archive
    client, err := irowiki.OpenSQLite("irowiki.db")
    if err != nil {
        panic(err)
    }
    defer client.Close()
    
    // Search pages
    results, _ := client.Search(irowiki.SearchOptions{
        Query: "Poring",
        Namespace: 0,
        Limit: 10,
    })
    
    for _, result := range results {
        fmt.Printf("%s (ID: %d)\n", result.Title, result.PageID)
    }
    
    // Get page history
    history, _ := client.GetPageHistory("Main_Page", irowiki.HistoryOptions{
        StartDate: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC),
        EndDate: time.Now(),
    })
    
    fmt.Printf("Revisions: %d\n", len(history))
}
```

### CLI Tool Commands

```bash
# Search
irowiki-cli search "Ragnarok"
irowiki-cli search --namespace=0 --limit=20 "Poring"

# Page history
irowiki-cli history "Main_Page"
irowiki-cli history --since=2020-01-01 "Main_Page"

# Get page at time
irowiki-cli snapshot "Main_Page" --date=2020-06-15

# Statistics
irowiki-cli stats
irowiki-cli stats --page="Main_Page"
irowiki-cli stats --editor="Admin" --since=2020-01-01

# List pages
irowiki-cli list --namespace=0 --limit=50

# Export page
irowiki-cli export "Main_Page" --format=markdown
```

### Performance Targets

- Simple queries (<10 results): <10ms
- Complex queries (filters, joins): <100ms
- Full-text search: <200ms
- Large history retrieval (>100 revisions): <500ms
- Statistics calculations: <1s

### Dependencies

```go
// go.mod
module github.com/user/iRO-Wiki-Scraper

go 1.21

require (
    modernc.org/sqlite v1.28.0      // Pure Go SQLite
    github.com/lib/pq v1.10.9        // PostgreSQL driver
    github.com/spf13/cobra v1.8.0    // CLI framework
    github.com/stretchr/testify v1.8.4 // Testing
)
```

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/sdk/test.db` - Small test database (SQLite)
- `fixtures/sdk/test_data.sql` - PostgreSQL test data
- `fixtures/sdk/expected_results/*.json` - Expected query results

### Test Utilities
- `sdk/internal/testutil/db_setup.go` - Test database setup
- `sdk/internal/testutil/assertions.go` - Custom assertions
- `sdk/internal/testutil/fixtures.go` - Load test fixtures

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |
| Story 14 | Not Started | - | - |
| Story 15 | Not Started | - | - |
| Story 16 | Not Started | - | - |
| Story 17 | Not Started | - | - |
| Story 18 | Not Started | - | - |
| Story 19 | Not Started | - | - |
| Story 20 | Not Started | - | - |
| Story 21 | Not Started | - | - |
| Story 22 | Not Started | - | - |
| Story 23 | Not Started | - | - |

## Definition of Done

- [ ] All 23 user stories completed
- [ ] Works with both SQLite and PostgreSQL
- [ ] Performance targets met
- [ ] All tests passing (80%+ coverage)
- [ ] CLI tool fully functional
- [ ] API documentation complete (godoc)
- [ ] Usage examples provided
- [ ] Design document created and approved
- [ ] Code reviewed and merged
- [ ] Published to pkg.go.dev
