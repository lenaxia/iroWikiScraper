package irowiki_test

import (
	"context"
	"testing"
	"time"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/internal/testutil"
	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

// TestSQLiteClient_GetPage tests retrieving a page by title
func TestSQLiteClient_GetPage(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get existing page
	page, err := client.GetPage(ctx, "Main_Page")
	if err != nil {
		t.Fatalf("GetPage failed: %v", err)
	}

	if page.ID != 1 {
		t.Errorf("expected page ID 1, got %d", page.ID)
	}
	if page.Title != "Main_Page" {
		t.Errorf("expected title 'Main_Page', got %q", page.Title)
	}
	if page.Namespace != 0 {
		t.Errorf("expected namespace 0, got %d", page.Namespace)
	}
	if page.Content == "" {
		t.Error("expected non-empty content")
	}

	// Test: Get non-existent page
	_, err = client.GetPage(ctx, "NonExistent")
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_GetPageByID tests retrieving a page by ID
func TestSQLiteClient_GetPageByID(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get existing page
	page, err := client.GetPageByID(ctx, 1)
	if err != nil {
		t.Fatalf("GetPageByID failed: %v", err)
	}

	if page.ID != 1 {
		t.Errorf("expected page ID 1, got %d", page.ID)
	}
	if page.Title != "Main_Page" {
		t.Errorf("expected title 'Main_Page', got %q", page.Title)
	}

	// Test: Get non-existent page
	_, err = client.GetPageByID(ctx, 999)
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_ListPages tests listing pages with pagination
func TestSQLiteClient_ListPages(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: List all pages in namespace 0
	pages, err := client.ListPages(ctx, 0, 0, 10)
	if err != nil {
		t.Fatalf("ListPages failed: %v", err)
	}

	if len(pages) != 4 { // Main_Page, Prontera, Poring, Redirect_Test
		t.Errorf("expected 4 pages, got %d", len(pages))
	}

	// Test: Pagination
	pages, err = client.ListPages(ctx, 0, 2, 2)
	if err != nil {
		t.Fatalf("ListPages with pagination failed: %v", err)
	}

	if len(pages) != 2 {
		t.Errorf("expected 2 pages, got %d", len(pages))
	}
}

// TestSQLiteClient_GetPageHistory tests retrieving page revision history
func TestSQLiteClient_GetPageHistory(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get history for page with multiple revisions
	opts := irowiki.HistoryOptions{
		Limit: 10,
	}
	history, err := client.GetPageHistory(ctx, "Main_Page", opts)
	if err != nil {
		t.Fatalf("GetPageHistory failed: %v", err)
	}

	if len(history) != 2 {
		t.Errorf("expected 2 revisions, got %d", len(history))
	}

	// Verify they are in reverse chronological order (newest first)
	if len(history) >= 2 && history[0].Timestamp.Before(history[1].Timestamp) {
		t.Error("expected revisions in reverse chronological order")
	}

	// Test: Get history for non-existent page
	_, err = client.GetPageHistory(ctx, "NonExistent", opts)
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_GetRevision tests retrieving a specific revision
func TestSQLiteClient_GetRevision(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get existing revision
	rev, err := client.GetRevision(ctx, 100)
	if err != nil {
		t.Fatalf("GetRevision failed: %v", err)
	}

	if rev.ID != 100 {
		t.Errorf("expected revision ID 100, got %d", rev.ID)
	}
	if rev.User != "Admin" {
		t.Errorf("expected user 'Admin', got %q", rev.User)
	}

	// Test: Get non-existent revision
	_, err = client.GetRevision(ctx, 999)
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_GetPageAtTime tests getting page content at a specific time
func TestSQLiteClient_GetPageAtTime(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get page as it existed after first revision
	timestamp := time.Date(2020, 1, 1, 12, 0, 0, 0, time.UTC)
	rev, err := client.GetPageAtTime(ctx, "Main_Page", timestamp)
	if err != nil {
		t.Fatalf("GetPageAtTime failed: %v", err)
	}

	if rev.ID != 100 {
		t.Errorf("expected revision ID 100, got %d", rev.ID)
	}

	// Test: Get page after second revision
	timestamp = time.Date(2020, 1, 2, 12, 0, 0, 0, time.UTC)
	rev, err = client.GetPageAtTime(ctx, "Main_Page", timestamp)
	if err != nil {
		t.Fatalf("GetPageAtTime failed: %v", err)
	}

	if rev.ID != 101 {
		t.Errorf("expected revision ID 101, got %d", rev.ID)
	}

	// Test: Get page before it existed
	timestamp = time.Date(2019, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err = client.GetPageAtTime(ctx, "Main_Page", timestamp)
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_GetChangesByPeriod tests retrieving revisions in a time range
func TestSQLiteClient_GetChangesByPeriod(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get all changes in January 2020
	start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2020, 1, 31, 23, 59, 59, 0, time.UTC)

	changes, err := client.GetChangesByPeriod(ctx, start, end)
	if err != nil {
		t.Fatalf("GetChangesByPeriod failed: %v", err)
	}

	if len(changes) != 7 { // All test revisions are in January 2020 (revisions 100-106)
		t.Errorf("expected 7 changes, got %d", len(changes))
	}
}

// TestSQLiteClient_GetEditorActivity tests retrieving revisions by a specific user
func TestSQLiteClient_GetEditorActivity(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2020, 12, 31, 23, 59, 59, 0, time.UTC)

	// Test: Get activity for Admin
	activity, err := client.GetEditorActivity(ctx, "Admin", start, end)
	if err != nil {
		t.Fatalf("GetEditorActivity failed: %v", err)
	}

	if len(activity) != 4 { // Admin made 4 edits (revisions 100, 102, 105, 106)
		t.Errorf("expected 4 revisions by Admin, got %d", len(activity))
	}

	// Verify all are by Admin
	for _, rev := range activity {
		if rev.User != "Admin" {
			t.Errorf("expected user 'Admin', got %q", rev.User)
		}
	}
}

// TestSQLiteClient_GetFile tests retrieving file metadata
func TestSQLiteClient_GetFile(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get existing file
	file, err := client.GetFile(ctx, "Example.png")
	if err != nil {
		t.Fatalf("GetFile failed: %v", err)
	}

	if file.Filename != "Example.png" {
		t.Errorf("expected filename 'Example.png', got %q", file.Filename)
	}
	if file.MimeType != "image/png" {
		t.Errorf("expected mime type 'image/png', got %q", file.MimeType)
	}
	if file.Width == nil || *file.Width != 800 {
		t.Error("expected width 800")
	}

	// Test: Get non-existent file
	_, err = client.GetFile(ctx, "NonExistent.png")
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_ListFiles tests listing files with pagination
func TestSQLiteClient_ListFiles(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: List all files
	files, err := client.ListFiles(ctx, 0, 10)
	if err != nil {
		t.Fatalf("ListFiles failed: %v", err)
	}

	if len(files) != 2 {
		t.Errorf("expected 2 files, got %d", len(files))
	}
}

// TestSQLiteClient_GetStatistics tests retrieving overall statistics
func TestSQLiteClient_GetStatistics(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	stats, err := client.GetStatistics(ctx)
	if err != nil {
		t.Fatalf("GetStatistics failed: %v", err)
	}

	if stats.TotalPages != 5 {
		t.Errorf("expected 5 pages, got %d", stats.TotalPages)
	}
	if stats.TotalRevisions != 7 {
		t.Errorf("expected 7 revisions, got %d", stats.TotalRevisions)
	}
	if stats.TotalFiles != 2 {
		t.Errorf("expected 2 files, got %d", stats.TotalFiles)
	}
}

// TestSQLiteClient_GetPageStats tests retrieving page-specific statistics
func TestSQLiteClient_GetPageStats(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	stats, err := client.GetPageStats(ctx, "Main_Page")
	if err != nil {
		t.Fatalf("GetPageStats failed: %v", err)
	}

	if stats.PageID != 1 {
		t.Errorf("expected page ID 1, got %d", stats.PageID)
	}
	if stats.Title != "Main_Page" {
		t.Errorf("expected title 'Main_Page', got %q", stats.Title)
	}
	if stats.RevisionCount != 2 {
		t.Errorf("expected 2 revisions, got %d", stats.RevisionCount)
	}
	if stats.EditorCount != 2 {
		t.Errorf("expected 2 editors, got %d", stats.EditorCount)
	}
}

// TestSQLiteClient_Ping tests connection health check
func TestSQLiteClient_Ping(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Ping active connection
	if err := client.Ping(ctx); err != nil {
		t.Errorf("Ping failed: %v", err)
	}
}

// TestSQLiteClient_Close tests client cleanup
func TestSQLiteClient_Close(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}

	// Close the client
	if err := client.Close(); err != nil {
		t.Errorf("Close failed: %v", err)
	}

	// Test: Operations after close should fail
	ctx := context.Background()
	_, err = client.GetPage(ctx, "Main_Page")
	if err != irowiki.ErrClosed {
		t.Errorf("expected ErrClosed, got %v", err)
	}
}

// TestSQLiteClient_ContextCancellation tests context cancellation support
func TestSQLiteClient_ContextCancellation(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	// Create a context that's already cancelled
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	// Operations should fail with context error
	_, err = client.GetPage(ctx, "Main_Page")
	if err == nil {
		t.Error("expected error with cancelled context")
	}
}
