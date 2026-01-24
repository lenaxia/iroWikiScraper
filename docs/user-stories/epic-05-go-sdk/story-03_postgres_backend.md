# Story 03: PostgreSQL Backend

**Story ID**: epic-05-story-03  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 6 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** a PostgreSQL backend implementation for the Client interface  
**So that** I can query wiki archives stored in PostgreSQL databases with better scalability

## Acceptance Criteria

1. **Implementation**
   - [ ] Implement `Client` interface for PostgreSQL
   - [ ] Use lib/pq driver for database access
   - [ ] Connection pooling and management
   - [ ] Prepared statement caching

2. **Connection Management**
   - [ ] `OpenPostgres(dsn string) (Client, error)` function
   - [ ] Support connection string with all parameters
   - [ ] Proper connection cleanup on Close()
   - [ ] Connection timeout and retry handling

3. **Query Implementation**
   - [ ] All Client interface methods implemented
   - [ ] PostgreSQL-optimized queries with indexes
   - [ ] Transaction support where needed
   - [ ] Context cancellation support

4. **Error Handling**
   - [ ] Translate PostgreSQL errors to custom errors
   - [ ] Handle connection failures gracefully
   - [ ] Handle query timeouts
   - [ ] Proper error wrapping with context

## Technical Details

### Implementation Structure

```go
package irowiki

import (
    "context"
    "database/sql"
    "time"
    _ "github.com/lib/pq"
)

type postgresClient struct {
    db *sql.DB
    stmts map[string]*sql.Stmt
}

func OpenPostgres(dsn string) (Client, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, err
    }
    
    // Configure connection pool
    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(5)
    db.SetConnMaxLifetime(5 * time.Minute)
    
    // Test connection
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    
    if err := db.PingContext(ctx); err != nil {
        db.Close()
        return nil, fmt.Errorf("failed to connect: %w", err)
    }
    
    client := &postgresClient{
        db: db,
        stmts: make(map[string]*sql.Stmt),
    }
    
    // Prepare common statements
    if err := client.prepareStatements(); err != nil {
        db.Close()
        return nil, err
    }
    
    return client, nil
}

func (c *postgresClient) GetPage(ctx context.Context, title string) (*Page, error) {
    const query = `
        SELECT p.page_id, p.page_title, p.page_namespace, 
               r.rev_id, r.rev_timestamp, r.content
        FROM pages p
        JOIN revisions r ON p.page_latest = r.rev_id
        WHERE p.page_title = $1
    `
    
    var page Page
    err := c.db.QueryRowContext(ctx, query, title).Scan(
        &page.ID, &page.Title, &page.Namespace,
        &page.LatestRevID, &page.Timestamp, &page.Content,
    )
    
    if err == sql.ErrNoRows {
        return nil, ErrNotFound
    }
    
    return &page, err
}
```

### Connection String Format

```go
// Example DSN formats supported
const (
    // Key-value format
    dsn1 = "host=localhost port=5432 user=wiki password=secret dbname=irowiki sslmode=disable"
    
    // URL format
    dsn2 = "postgres://wiki:secret@localhost:5432/irowiki?sslmode=disable"
)
```

## Dependencies

- Story 01: Client Interface Design
- Epic 02: Database Schema (PostgreSQL schema)

## Implementation Notes

- PostgreSQL supports better full-text search than SQLite
- Use `$1`, `$2` style placeholders (not `?`)
- Take advantage of PostgreSQL-specific features:
  - `EXPLAIN ANALYZE` for query optimization
  - `ts_vector` for full-text search
  - Better JSON support for metadata
- Connection pooling is more important for PostgreSQL
- Support SSL connections for production use

## Testing Requirements

- [ ] Unit tests for connection management
- [ ] Integration tests with test database
- [ ] Benchmark tests comparing to SQLite
- [ ] Error scenario tests (connection loss, timeouts)
- [ ] SSL connection tests
- [ ] Connection pool stress tests

## Definition of Done

- [ ] PostgreSQL backend implemented in `sdk/irowiki/postgres.go`
- [ ] All Client methods implemented
- [ ] Connection management working with pooling
- [ ] All tests passing
- [ ] Performance targets met (<100ms queries)
- [ ] SSL support verified
- [ ] Code reviewed and approved
