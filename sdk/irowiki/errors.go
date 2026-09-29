package irowiki

import "errors"

var (
	// ErrNotFound is returned when a requested entity (page, revision, file) is not found.
	ErrNotFound = errors.New("entity not found")

	// ErrClosed is returned when an operation is attempted on a closed client.
	ErrClosed = errors.New("client is closed")

	// ErrInvalidInput is returned when input parameters are invalid.
	ErrInvalidInput = errors.New("invalid input")

	// ErrDatabaseError is returned for database-related errors.
	ErrDatabaseError = errors.New("database error")

	// ErrNotMaterialized is returned when the archive carries no materialized
	// markdown (pages_md). Run the materialize command on the database.
	ErrNotMaterialized = errors.New("markdown not materialized for this archive")

	// ErrConnectionFailed is returned when database connection fails.
	ErrConnectionFailed = errors.New("connection failed")
)
