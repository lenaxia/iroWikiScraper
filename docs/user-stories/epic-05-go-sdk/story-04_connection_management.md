# Story 04: Connection Management

**Story ID**: epic-05-story-04  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** robust connection management and lifecycle handling  
**So that** I can efficiently manage database resources and avoid connection leaks

## Acceptance Criteria

1. **Connection Pooling**
   - [ ] Configurable pool size for both backends
   - [ ] Automatic connection recycling
   - [ ] Idle connection cleanup
   - [ ] Connection lifetime limits

2. **Health Checks**
   - [ ] `Ping()` method to test connection health
   - [ ] Automatic reconnection on transient failures
   - [ ] Connection state validation before queries
   - [ ] Graceful degradation on connection issues

3. **Resource Cleanup**
   - [ ] Proper cleanup in `Close()` method
   - [ ] Statement cache cleanup
   - [ ] Connection drain on shutdown
   - [ ] No resource leaks in error paths

4. **Configuration**
   - [ ] Connection options struct
   - [ ] Timeout configuration
   - [ ] Retry policy configuration
   - [ ] Debug logging support

## Technical Details

### Connection Options

```go
package irowiki

import "time"

// ConnectionOptions configures database connections
type ConnectionOptions struct {
    // Pool settings
    MaxOpenConns    int
    MaxIdleConns    int
    ConnMaxLifetime time.Duration
    ConnMaxIdleTime time.Duration
    
    // Timeouts
    ConnectTimeout time.Duration
    QueryTimeout   time.Duration
    
    // Retry policy
    MaxRetries     int
    RetryDelay     time.Duration
    
    // Logging
    Debug          bool
    Logger         Logger
}

// DefaultSQLiteOptions returns sensible defaults for SQLite
func DefaultSQLiteOptions() ConnectionOptions {
    return ConnectionOptions{
        MaxOpenConns:    5,
        MaxIdleConns:    2,
        ConnMaxLifetime: 0, // SQLite doesn't need connection recycling
        ConnMaxIdleTime: 5 * time.Minute,
        ConnectTimeout:  5 * time.Second,
        QueryTimeout:    30 * time.Second,
        MaxRetries:      3,
        RetryDelay:      100 * time.Millisecond,
    }
}

// DefaultPostgresOptions returns sensible defaults for PostgreSQL
func DefaultPostgresOptions() ConnectionOptions {
    return ConnectionOptions{
        MaxOpenConns:    25,
        MaxIdleConns:    5,
        ConnMaxLifetime: 5 * time.Minute,
        ConnMaxIdleTime: 1 * time.Minute,
        ConnectTimeout:  10 * time.Second,
        QueryTimeout:    30 * time.Second,
        MaxRetries:      3,
        RetryDelay:      500 * time.Millisecond,
    }
}
```

### Enhanced Open Functions

```go
// OpenSQLiteWithOptions opens a SQLite database with custom options
func OpenSQLiteWithOptions(path string, opts ConnectionOptions) (Client, error) {
    db, err := sql.Open("sqlite", path+"?mode=ro")
    if err != nil {
        return nil, fmt.Errorf("failed to open database: %w", err)
    }
    
    // Apply connection pool settings
    db.SetMaxOpenConns(opts.MaxOpenConns)
    db.SetMaxIdleConns(opts.MaxIdleConns)
    db.SetConnMaxLifetime(opts.ConnMaxLifetime)
    db.SetConnMaxIdleTime(opts.ConnMaxIdleTime)
    
    // Test connection
    ctx, cancel := context.WithTimeout(context.Background(), opts.ConnectTimeout)
    defer cancel()
    
    if err := db.PingContext(ctx); err != nil {
        db.Close()
        return nil, fmt.Errorf("failed to ping database: %w", err)
    }
    
    client := &sqliteClient{
        db:      db,
        opts:    opts,
        stmts:   make(map[string]*sql.Stmt),
        closed:  false,
    }
    
    if err := client.prepareStatements(); err != nil {
        db.Close()
        return nil, err
    }
    
    return client, nil
}
```

### Health Check Implementation

```go
// Ping checks if the database connection is alive
func (c *sqliteClient) Ping(ctx context.Context) error {
    if c.closed {
        return ErrClosed
    }
    
    return c.db.PingContext(ctx)
}

// ensureConnected verifies connection before query
func (c *sqliteClient) ensureConnected(ctx context.Context) error {
    if c.closed {
        return ErrClosed
    }
    
    // Quick health check
    if err := c.db.PingContext(ctx); err != nil {
        return fmt.Errorf("connection lost: %w", err)
    }
    
    return nil
}
```

### Graceful Shutdown

```go
// Close cleanly shuts down the client
func (c *sqliteClient) Close() error {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    if c.closed {
        return ErrClosed
    }
    
    c.closed = true
    
    // Close all prepared statements
    for name, stmt := range c.stmts {
        if err := stmt.Close(); err != nil {
            c.log("failed to close statement %s: %v", name, err)
        }
    }
    
    // Close database connection
    if err := c.db.Close(); err != nil {
        return fmt.Errorf("failed to close database: %w", err)
    }
    
    return nil
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 03: PostgreSQL Backend

## Implementation Notes

- Use `sync.Mutex` to protect closed state
- Consider using `sync.Once` for initialization
- Log connection pool stats for debugging
- Implement connection warmup for critical applications
- Support read-only vs read-write connections

## Testing Requirements

- [ ] Connection pool behavior tests
- [ ] Connection timeout tests
- [ ] Reconnection logic tests
- [ ] Resource leak tests (using `-race` flag)
- [ ] Concurrent access tests
- [ ] Graceful shutdown tests
- [ ] Connection state validation tests

## Definition of Done

- [ ] Connection options implemented
- [ ] Health check methods added
- [ ] Graceful shutdown working
- [ ] No resource leaks detected
- [ ] All tests passing
- [ ] Concurrent access verified
- [ ] Documentation complete
- [ ] Code reviewed and approved
