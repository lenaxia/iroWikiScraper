# Story 02: SQLite Backend

**Story ID**: epic-05-story-02  
**Epic**: Epic 05 - Go SDK  
**Priority**: High  
**Estimate**: 6 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** an SQLite backend implementation for the Client interface  
**So that** I can query wiki archives stored in SQLite databases

## Acceptance Criteria

1. **Implementation**
   - [x] Implement `Client` interface for SQLite
   - [x] Use modernc.org/sqlite (pure Go, no CGo)
   - [x] Connection pooling and management
   - [x] Prepared statement caching

2. **Connection Management**
   - [x] `OpenSQLite(path string) (Client, error)` function
   - [x] Read-only mode by default
   - [x] Proper connection cleanup on Close()
   - [x] Connection timeout handling

3. **Query Implementation**
   - [x] All Client interface methods implemented
   - [x] Efficient SQL queries with proper indexes
   - [x] Transaction support where needed
   - [x] Context cancellation support

4. **Error Handling**
   - [x] Translate SQLite errors to custom errors
   - [x] Handle file not found
   - [x] Handle corrupted database
   - [x] Proper error wrapping with context

## Technical Details

### Implementation Structure

```go
package irowiki

import (
    "context"
    "database/sql"
    _ "modernc.org/sqlite"
)

type sqliteClient struct {
    db *sql.DB
    stmts map[string]*sql.Stmt
}

func OpenSQLite(path string) (Client, error) {
    db, err := sql.Open("sqlite", path+"?mode=ro")
    if err != nil {
        return nil, err
    }
    
    // Configure connection pool
    db.SetMaxOpenConns(5)
    db.SetMaxIdleConns(2)
    
    client := &sqliteClient{
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
```

## Dependencies

- Story 01: Client Interface Design

## Testing Requirements

- [ ] Unit tests for connection management
- [ ] Integration tests with test database
- [ ] Benchmark tests for query performance
- [ ] Error scenario tests (missing file, corrupted db)

## Definition of Done

- [ ] SQLite backend implemented in `sdk/irowiki/sqlite.go`
- [ ] All Client methods implemented
- [ ] Connection management working
- [ ] All tests passing
- [ ] Performance targets met (<100ms queries)
- [ ] Code reviewed and approved
