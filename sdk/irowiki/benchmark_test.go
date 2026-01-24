package irowiki_test

import (
	"context"
	"testing"
	"time"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/internal/testutil"
	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

// BenchmarkGetPageHistory measures history query performance
func BenchmarkGetPageHistory(b *testing.B) {
	tdb := testutil.SetupTestDBFile(&testing.T{})
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		b.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()
	opts := irowiki.HistoryOptions{Limit: 50}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.GetPageHistory(ctx, "Main_Page", opts)
		if err != nil {
			b.Fatalf("GetPageHistory failed: %v", err)
		}
	}
}

// BenchmarkGetPageAtTime measures point-in-time query performance
func BenchmarkGetPageAtTime(b *testing.B) {
	tdb := testutil.SetupTestDBFile(&testing.T{})
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		b.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()
	timestamp := time.Now()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.GetPageAtTime(ctx, "Main_Page", timestamp)
		if err != nil {
			b.Fatalf("GetPageAtTime failed: %v", err)
		}
	}
}

// BenchmarkGetChangesByPeriod measures timeline query performance
func BenchmarkGetChangesByPeriod(b *testing.B) {
	tdb := testutil.SetupTestDBFile(&testing.T{})
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		b.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()
	start := time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Now()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.GetChangesByPeriod(ctx, start, end)
		if err != nil {
			b.Fatalf("GetChangesByPeriod failed: %v", err)
		}
	}
}

// BenchmarkGetRevisionDiff measures diff computation performance
func BenchmarkGetRevisionDiff(b *testing.B) {
	tdb := testutil.SetupTestDBFile(&testing.T{})
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		b.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Get two revisions to diff
	history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 2})
	if err != nil || len(history) < 2 {
		b.Skip("need at least 2 revisions for this benchmark")
	}

	fromID := history[1].ID
	toID := history[0].ID

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.GetRevisionDiff(ctx, fromID, toID)
		if err != nil {
			b.Fatalf("GetRevisionDiff failed: %v", err)
		}
	}
}

// BenchmarkGetConsecutiveDiff measures consecutive diff performance
func BenchmarkGetConsecutiveDiff(b *testing.B) {
	tdb := testutil.SetupTestDBFile(&testing.T{})
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		b.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Get a revision with a parent
	history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{})
	if err != nil || len(history) == 0 {
		b.Skip("need at least 1 revision for this benchmark")
	}

	var revID int64
	for _, rev := range history {
		if rev.ParentID != nil {
			revID = rev.ID
			break
		}
	}
	if revID == 0 {
		b.Skip("need a revision with parent for this benchmark")
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.GetConsecutiveDiff(ctx, revID)
		if err != nil {
			b.Fatalf("GetConsecutiveDiff failed: %v", err)
		}
	}
}
