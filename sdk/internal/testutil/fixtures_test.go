package testutil

import (
	"context"
	"testing"
)

// TestSetupTestDB verifies that the test database setup works correctly
func TestSetupTestDB(t *testing.T) {
	tdb := SetupTestDB(t)
	defer tdb.Close()

	ctx := context.Background()

	// Verify pages table exists and has data
	var count int
	err := tdb.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM pages").Scan(&count)
	if err != nil {
		t.Fatalf("failed to query pages: %v", err)
	}
	if count != 5 {
		t.Errorf("expected 5 pages, got %d", count)
	}

	// Verify revisions table exists and has data
	err = tdb.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM revisions").Scan(&count)
	if err != nil {
		t.Fatalf("failed to query revisions: %v", err)
	}
	if count != 7 {
		t.Errorf("expected 7 revisions, got %d", count)
	}

	// Verify files table exists and has data
	err = tdb.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM files").Scan(&count)
	if err != nil {
		t.Fatalf("failed to query files: %v", err)
	}
	if count != 2 {
		t.Errorf("expected 2 files, got %d", count)
	}
}
