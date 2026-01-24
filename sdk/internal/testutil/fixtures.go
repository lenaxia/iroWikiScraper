// Package testutil provides testing utilities and fixtures for the irowiki SDK.
package testutil

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

// TestDB represents a test database instance
type TestDB struct {
	DB   *sql.DB
	Path string
}

// SetupTestDB creates an in-memory SQLite database with schema and test data
func SetupTestDB(t *testing.T) *TestDB {
	t.Helper()

	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open test database: %v", err)
	}

	// Create schema
	if err := createSchema(db); err != nil {
		db.Close()
		t.Fatalf("failed to create schema: %v", err)
	}

	// Insert test data
	if err := insertTestData(db); err != nil {
		db.Close()
		t.Fatalf("failed to insert test data: %v", err)
	}

	return &TestDB{
		DB:   db,
		Path: ":memory:",
	}
}

// SetupTestDBFile creates a file-based SQLite database for integration tests
func SetupTestDBFile(t *testing.T) *TestDB {
	t.Helper()

	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("failed to open test database: %v", err)
	}

	// Create schema
	if err := createSchema(db); err != nil {
		db.Close()
		t.Fatalf("failed to create schema: %v", err)
	}

	// Insert test data
	if err := insertTestData(db); err != nil {
		db.Close()
		t.Fatalf("failed to insert test data: %v", err)
	}

	return &TestDB{
		DB:   db,
		Path: dbPath,
	}
}

// Close closes the test database
func (tdb *TestDB) Close() error {
	if tdb.DB != nil {
		return tdb.DB.Close()
	}
	return nil
}

// CleanupFile removes the database file if it exists
func (tdb *TestDB) CleanupFile() error {
	if tdb.Path != ":memory:" && tdb.Path != "" {
		return os.Remove(tdb.Path)
	}
	return nil
}

// createSchema creates the database schema
func createSchema(db *sql.DB) error {
	schemas := []string{
		// pages table
		`CREATE TABLE IF NOT EXISTS pages (
			page_id INTEGER PRIMARY KEY,
			namespace INTEGER NOT NULL DEFAULT 0,
			title TEXT NOT NULL,
			is_redirect BOOLEAN NOT NULL DEFAULT 0,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(namespace, title),
			CHECK(namespace >= 0)
		)`,
		`CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title)`,
		`CREATE INDEX IF NOT EXISTS idx_pages_namespace ON pages(namespace)`,
		`CREATE INDEX IF NOT EXISTS idx_pages_redirect ON pages(is_redirect) WHERE is_redirect = TRUE`,

		// revisions table
		`CREATE TABLE IF NOT EXISTS revisions (
			revision_id INTEGER PRIMARY KEY,
			page_id INTEGER NOT NULL,
			parent_id INTEGER,
			timestamp TIMESTAMP NOT NULL,
			user TEXT,
			user_id INTEGER,
			comment TEXT,
			content TEXT NOT NULL,
			size INTEGER NOT NULL,
			sha1 TEXT NOT NULL,
			minor BOOLEAN DEFAULT 0,
			tags TEXT,
			FOREIGN KEY (page_id) REFERENCES pages(page_id) ON DELETE CASCADE,
			FOREIGN KEY (parent_id) REFERENCES revisions(revision_id) ON DELETE SET NULL,
			CHECK(size >= 0)
		)`,
		`CREATE INDEX IF NOT EXISTS idx_rev_page_time ON revisions(page_id, timestamp DESC)`,
		`CREATE INDEX IF NOT EXISTS idx_rev_timestamp ON revisions(timestamp)`,
		`CREATE INDEX IF NOT EXISTS idx_rev_parent ON revisions(parent_id) WHERE parent_id IS NOT NULL`,
		`CREATE INDEX IF NOT EXISTS idx_rev_sha1 ON revisions(sha1)`,
		`CREATE INDEX IF NOT EXISTS idx_rev_user ON revisions(user_id) WHERE user_id IS NOT NULL`,

		// files table
		`CREATE TABLE IF NOT EXISTS files (
			filename TEXT PRIMARY KEY,
			url TEXT NOT NULL,
			descriptionurl TEXT NOT NULL,
			sha1 TEXT NOT NULL,
			size INTEGER NOT NULL,
			width INTEGER,
			height INTEGER,
			mime_type TEXT NOT NULL,
			timestamp TIMESTAMP NOT NULL,
			uploader TEXT,
			CHECK(size >= 0),
			CHECK(width IS NULL OR width > 0),
			CHECK(height IS NULL OR height > 0)
		)`,
		`CREATE INDEX IF NOT EXISTS idx_files_sha1 ON files(sha1)`,
		`CREATE INDEX IF NOT EXISTS idx_files_timestamp ON files(timestamp)`,
		`CREATE INDEX IF NOT EXISTS idx_files_mime ON files(mime_type)`,
		`CREATE INDEX IF NOT EXISTS idx_files_uploader ON files(uploader) WHERE uploader IS NOT NULL`,

		// FTS5 virtual table for full-text search
		`CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
			page_id UNINDEXED,
			title,
			content,
			tokenize='porter unicode61'
		)`,
	}

	for _, schema := range schemas {
		if _, err := db.Exec(schema); err != nil {
			return fmt.Errorf("failed to execute schema: %w", err)
		}
	}

	return nil
}

// insertTestData inserts test data into the database
func insertTestData(db *sql.DB) error {
	ctx := context.Background()

	// Insert test pages
	pages := []struct {
		id        int64
		namespace int
		title     string
		redirect  bool
	}{
		{1, 0, "Main_Page", false},
		{2, 0, "Prontera", false},
		{3, 0, "Poring", false},
		{4, 6, "Example.png", false},
		{5, 0, "Redirect_Test", true},
	}

	for _, p := range pages {
		_, err := db.ExecContext(ctx,
			`INSERT INTO pages (page_id, namespace, title, is_redirect) VALUES (?, ?, ?, ?)`,
			p.id, p.namespace, p.title, p.redirect,
		)
		if err != nil {
			return fmt.Errorf("failed to insert page: %w", err)
		}
	}

	// Insert test revisions
	baseTime := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	revisions := []struct {
		id      int64
		pageID  int64
		parent  *int64
		time    time.Time
		user    string
		userID  int
		comment string
		content string
		size    int
		sha1    string
		minor   bool
	}{
		{100, 1, nil, baseTime, "Admin", 1, "Initial creation", "Welcome to the wiki!", 21, "abc123", false},
		{101, 1, int64Ptr(100), baseTime.Add(24 * time.Hour), "Editor", 2, "Updated content", "Welcome to the iRO wiki!", 25, "def456", false},
		{102, 2, nil, baseTime.Add(48 * time.Hour), "Admin", 1, "Created Prontera page", "Prontera is the capital city.", 30, "ghi789", false},
		{103, 2, int64Ptr(102), baseTime.Add(72 * time.Hour), "Editor", 2, "Minor typo fix", "Prontera is the capital city", 29, "jkl012", true},
		{104, 3, nil, baseTime.Add(96 * time.Hour), "Contributor", 3, "Created Poring page", "Poring is a pink slime monster.", 32, "mno345", false},
		{105, 4, nil, baseTime.Add(120 * time.Hour), "Admin", 1, "Uploaded image", "Image file", 10, "pqr678", false},
		{106, 5, nil, baseTime.Add(144 * time.Hour), "Admin", 1, "Created redirect", "REDIRECT Main_Page", 20, "stu901", false},
	}

	for _, r := range revisions {
		_, err := db.ExecContext(ctx,
			`INSERT INTO revisions (revision_id, page_id, parent_id, timestamp, user, user_id, comment, content, size, sha1, minor) 
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			r.id, r.pageID, r.parent, r.time, r.user, r.userID, r.comment, r.content, r.size, r.sha1, r.minor,
		)
		if err != nil {
			return fmt.Errorf("failed to insert revision: %w", err)
		}
	}

	// Insert test files
	files := []struct {
		filename       string
		url            string
		descriptionurl string
		sha1           string
		size           int
		width          *int
		height         *int
		mimeType       string
		timestamp      time.Time
		uploader       string
	}{
		{
			"Example.png",
			"https://irowiki.org/w/images/e/ex/Example.png",
			"https://irowiki.org/wiki/File:Example.png",
			"abc123def456",
			12345,
			intPtr(800),
			intPtr(600),
			"image/png",
			baseTime,
			"Admin",
		},
		{
			"Document.pdf",
			"https://irowiki.org/w/images/d/do/Document.pdf",
			"https://irowiki.org/wiki/File:Document.pdf",
			"xyz789uvw012",
			54321,
			nil,
			nil,
			"application/pdf",
			baseTime.Add(24 * time.Hour),
			"Editor",
		},
	}

	for _, f := range files {
		_, err := db.ExecContext(ctx,
			`INSERT INTO files (filename, url, descriptionurl, sha1, size, width, height, mime_type, timestamp, uploader)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			f.filename, f.url, f.descriptionurl, f.sha1, f.size, f.width, f.height, f.mimeType, f.timestamp, f.uploader,
		)
		if err != nil {
			return fmt.Errorf("failed to insert file: %w", err)
		}
	}

	// Populate FTS table with test data
	ftsEntries := []struct {
		pageID  int64
		title   string
		content string
	}{
		{1, "Main_Page", "Welcome to the iRO wiki!"},
		{2, "Prontera", "Prontera is the capital city"},
		{3, "Poring", "Poring is a pink slime monster."},
		{4, "Example.png", "Image file"},
		{5, "Redirect_Test", "REDIRECT Main_Page"},
	}

	for _, entry := range ftsEntries {
		_, err := db.ExecContext(ctx,
			`INSERT INTO pages_fts (page_id, title, content) VALUES (?, ?, ?)`,
			entry.pageID, entry.title, entry.content,
		)
		if err != nil {
			return fmt.Errorf("failed to insert FTS entry: %w", err)
		}
	}

	return nil
}

// Helper functions
func int64Ptr(i int64) *int64 {
	return &i
}

func intPtr(i int) *int {
	return &i
}
