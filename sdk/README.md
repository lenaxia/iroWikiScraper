# iRO Wiki SDK for Go

A Go SDK for querying the iRO Wiki archive. Supports both SQLite and PostgreSQL backends with a clean, idiomatic Go API.

## Features

- **Dual Backend Support**: Works with SQLite (portable) or PostgreSQL (scalable)
- **Complete Query API**: Search pages, retrieve revisions, access files, and generate statistics
- **Context Support**: All methods accept `context.Context` for cancellation and timeouts
- **Connection Pooling**: Configurable connection management for optimal performance
- **Type-Safe**: Strongly-typed models with full documentation
- **Thread-Safe**: Safe for concurrent use by multiple goroutines

## Installation

```bash
go get github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki
```

## Quick Start

### SQLite Example

```go
package main

import (
    "context"
    "fmt"
    "log"
    
    "github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
    // Open SQLite database
    client, err := irowiki.OpenSQLite("irowiki.db")
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()
    
    ctx := context.Background()
    
    // Search for pages
    results, err := client.Search(ctx, irowiki.SearchOptions{
        Query:     "Poring",
        Namespace: 0,
        Limit:     10,
    })
    if err != nil {
        log.Fatal(err)
    }
    
    for _, result := range results {
        fmt.Printf("- %s (ID: %d)\n", result.Title, result.PageID)
    }
}
```

### PostgreSQL Example

```go
client, err := irowiki.OpenPostgres("postgres://user:pass@localhost/irowiki?sslmode=disable")
if err != nil {
    log.Fatal(err)
}
defer client.Close()

// Use the same API as SQLite
page, err := client.GetPage(ctx, "Main_Page")
if err != nil {
    log.Fatal(err)
}

fmt.Printf("Title: %s\nContent: %s\n", page.Title, page.Content)
```

## API Overview

### Page Operations

```go
// Get page by title
page, err := client.GetPage(ctx, "Prontera")

// Get page by ID
page, err := client.GetPageByID(ctx, 123)

// List pages in a namespace (with pagination)
pages, err := client.ListPages(ctx, 0, 0, 100)
```

### Search Operations

```go
// Simple title search
results, err := client.Search(ctx, irowiki.SearchOptions{
    Query:     "Ragnarok",
    Namespace: 0,
    Offset:    0,
    Limit:     20,
})

// Full-text search (content)
results, err := client.SearchFullText(ctx, "monster drops", irowiki.SearchOptions{
    Limit: 50,
})
```

### Revision History

```go
// Get page history
history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{
    Limit: 50,
})

// Get specific revision
revision, err := client.GetRevision(ctx, 12345)

// Get page as it existed at a specific time
import "time"

timestamp := time.Date(2020, 6, 15, 0, 0, 0, 0, time.UTC)
revision, err := client.GetPageAtTime(ctx, "Main_Page", timestamp)
```

### Timeline Queries

```go
// Get all changes in a time period
start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
end := time.Date(2020, 12, 31, 23, 59, 59, 0, time.UTC)

changes, err := client.GetChangesByPeriod(ctx, start, end)

// Get edits by a specific user
activity, err := client.GetEditorActivity(ctx, "Admin", start, end)
```

### File Operations

```go
// Get file metadata
file, err := client.GetFile(ctx, "Example.png")

// List all files (with pagination)
files, err := client.ListFiles(ctx, 0, 100)
```

### Statistics

```go
// Get overall statistics
stats, err := client.GetStatistics(ctx)
fmt.Printf("Total Pages: %d\n", stats.TotalPages)
fmt.Printf("Total Revisions: %d\n", stats.TotalRevisions)
fmt.Printf("Total Files: %d\n", stats.TotalFiles)

// Get page-specific statistics
pageStats, err := client.GetPageStats(ctx, "Main_Page")
fmt.Printf("Revision Count: %d\n", pageStats.RevisionCount)
fmt.Printf("Editor Count: %d\n", pageStats.EditorCount)
```

## Advanced Usage

### Custom Connection Options

```go
opts := irowiki.ConnectionOptions{
    MaxOpenConns:    10,
    MaxIdleConns:    5,
    ConnMaxLifetime: 5 * time.Minute,
    ConnectTimeout:  10 * time.Second,
    QueryTimeout:    30 * time.Second,
}

client, err := irowiki.OpenSQLiteWithOptions("irowiki.db", opts)
```

### Context Timeouts

```go
// Set query timeout
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

page, err := client.GetPage(ctx, "Prontera")
if err != nil {
    // Handle timeout or other errors
}
```

### Health Checks

```go
// Check database connection
if err := client.Ping(ctx); err != nil {
    log.Printf("Database connection failed: %v", err)
}
```

## Data Models

### Page
- `ID`: Page identifier
- `Namespace`: MediaWiki namespace (0=Main, 6=File, etc.)
- `Title`: Page title
- `IsRedirect`: Whether this is a redirect page
- `LatestRevisionID`: Current revision ID
- `Content`: Latest page content
- `Timestamp`: Last modification time
- `User`: Last editor username
- `Comment`: Latest edit summary

### Revision
- `ID`: Revision identifier
- `PageID`: Associated page ID
- `ParentID`: Previous revision ID
- `Timestamp`: Edit timestamp
- `User`: Editor username
- `UserID`: Editor user ID
- `Comment`: Edit summary
- `Content`: Wikitext content
- `Size`: Content size in bytes
- `SHA1`: Content hash
- `Minor`: Whether this is a minor edit
- `Tags`: Edit tags (e.g., "visual edit")

### File
- `Filename`: File name
- `URL`: Direct download URL
- `DescriptionURL`: File description page URL
- `SHA1`: File content hash
- `Size`: File size in bytes
- `Width`/`Height`: Image dimensions (nil for non-images)
- `MimeType`: File MIME type
- `Timestamp`: Upload time
- `Uploader`: Uploader username

## Error Handling

```go
page, err := client.GetPage(ctx, "NonExistent")
if errors.Is(err, irowiki.ErrNotFound) {
    fmt.Println("Page not found")
} else if errors.Is(err, irowiki.ErrClosed) {
    fmt.Println("Client is closed")
} else if err != nil {
    fmt.Printf("Database error: %v\n", err)
}
```

## Testing

Run tests:
```bash
go test ./...
```

With coverage:
```bash
go test ./... -cover
```

View coverage report:
```bash
go test ./... -coverprofile=coverage.out
go tool cover -html=coverage.out
```

## Performance

- SQLite: Optimized for single-user/read-heavy workloads
  - Default: 5 max connections, 2 idle
  - Best for: Local queries, embedded applications
  
- PostgreSQL: Optimized for multi-user/concurrent access
  - Default: 25 max connections, 5 idle
  - Best for: Web services, analytics, high concurrency

## License

See the main repository for license information.

## Contributing

See the main repository for contribution guidelines.
