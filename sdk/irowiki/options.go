package irowiki

import "time"

// ConnectionOptions configures database connections.
type ConnectionOptions struct {
	// MaxOpenConns is the maximum number of open connections to the database.
	// Default varies by backend (5 for SQLite, 25 for PostgreSQL).
	MaxOpenConns int

	// MaxIdleConns is the maximum number of idle connections to maintain.
	// Default varies by backend (2 for SQLite, 5 for PostgreSQL).
	MaxIdleConns int

	// ConnMaxLifetime is the maximum time a connection can be reused.
	// Set to 0 to disable connection recycling.
	// Default: 0 for SQLite, 5 minutes for PostgreSQL.
	ConnMaxLifetime time.Duration

	// ConnMaxIdleTime is the maximum time a connection can remain idle.
	// Connections idle longer than this will be closed.
	// Default: 5 minutes for SQLite, 1 minute for PostgreSQL.
	ConnMaxIdleTime time.Duration

	// ConnectTimeout is the maximum time to wait for connection establishment.
	// Default: 5 seconds for SQLite, 10 seconds for PostgreSQL.
	ConnectTimeout time.Duration

	// QueryTimeout is the default timeout for queries (can be overridden per-query with context).
	// Default: 30 seconds for both backends.
	QueryTimeout time.Duration

	// MaxRetries is the number of times to retry transient failures.
	// Default: 3 for both backends.
	MaxRetries int

	// RetryDelay is the initial delay between retries (exponential backoff is applied).
	// Default: 100ms for SQLite, 500ms for PostgreSQL.
	RetryDelay time.Duration

	// Debug enables detailed connection and query logging.
	// Default: false.
	Debug bool
}

// DefaultSQLiteOptions returns sensible defaults for SQLite connections.
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
		Debug:           false,
	}
}

// DefaultPostgresOptions returns sensible defaults for PostgreSQL connections.
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
		Debug:           false,
	}
}

// applyDefaults fills in missing options with defaults.
func (opts *ConnectionOptions) applyDefaults(isSQLite bool) {
	var defaults ConnectionOptions
	if isSQLite {
		defaults = DefaultSQLiteOptions()
	} else {
		defaults = DefaultPostgresOptions()
	}

	if opts.MaxOpenConns == 0 {
		opts.MaxOpenConns = defaults.MaxOpenConns
	}
	if opts.MaxIdleConns == 0 {
		opts.MaxIdleConns = defaults.MaxIdleConns
	}
	if opts.ConnMaxLifetime == 0 {
		opts.ConnMaxLifetime = defaults.ConnMaxLifetime
	}
	if opts.ConnMaxIdleTime == 0 {
		opts.ConnMaxIdleTime = defaults.ConnMaxIdleTime
	}
	if opts.ConnectTimeout == 0 {
		opts.ConnectTimeout = defaults.ConnectTimeout
	}
	if opts.QueryTimeout == 0 {
		opts.QueryTimeout = defaults.QueryTimeout
	}
	if opts.MaxRetries == 0 {
		opts.MaxRetries = defaults.MaxRetries
	}
	if opts.RetryDelay == 0 {
		opts.RetryDelay = defaults.RetryDelay
	}
}
