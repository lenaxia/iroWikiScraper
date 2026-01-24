package irowiki_test

import (
	"context"
	"strings"
	"testing"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/internal/testutil"
	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

// TestSQLiteClient_GetRevisionDiff tests computing diff between two revisions
func TestSQLiteClient_GetRevisionDiff(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	t.Run("diff between two revisions of same page", func(t *testing.T) {
		// Get at least two revisions
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 2})
		if err != nil || len(history) < 2 {
			t.Skip("need at least 2 revisions for this test")
		}

		// Compute diff from older to newer
		fromRev := history[1] // Older (further back in time)
		toRev := history[0]   // Newer (more recent)

		diff, err := client.GetRevisionDiff(ctx, fromRev.ID, toRev.ID)
		if err != nil {
			t.Fatalf("GetRevisionDiff failed: %v", err)
		}

		// Verify result structure
		if diff.FromRevision != fromRev.ID {
			t.Errorf("expected from revision %d, got %d", fromRev.ID, diff.FromRevision)
		}
		if diff.ToRevision != toRev.ID {
			t.Errorf("expected to revision %d, got %d", toRev.ID, diff.ToRevision)
		}

		// Unified diff should contain something
		if diff.Unified == "" && fromRev.Content != toRev.Content {
			t.Error("expected non-empty unified diff for different content")
		}

		// Stats should be computed
		if fromRev.Content != toRev.Content {
			if diff.Stats.LinesAdded == 0 && diff.Stats.LinesRemoved == 0 {
				t.Error("expected some lines added or removed for different content")
			}
		}
	})

	t.Run("diff of identical revisions shows no changes", func(t *testing.T) {
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 1})
		if err != nil || len(history) == 0 {
			t.Skip("need at least 1 revision for this test")
		}

		rev := history[0]

		// Diff a revision with itself
		diff, err := client.GetRevisionDiff(ctx, rev.ID, rev.ID)
		if err != nil {
			t.Fatalf("GetRevisionDiff failed: %v", err)
		}

		// Should show no changes
		if diff.Stats.LinesAdded != 0 || diff.Stats.LinesRemoved != 0 {
			t.Error("expected no changes when diffing identical revisions")
		}
	})

	t.Run("diff between revisions of different pages fails", func(t *testing.T) {
		// Get revisions from two different pages
		history1, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 1})
		if err != nil || len(history1) == 0 {
			t.Skip("need revision from Main_Page")
		}

		// Try to find another page
		pages, err := client.ListPages(ctx, 0, 0, 10)
		if err != nil || len(pages) < 2 {
			t.Skip("need at least 2 pages for this test")
		}

		var otherPage string
		for _, p := range pages {
			if p.Title != "Main_Page" {
				otherPage = p.Title
				break
			}
		}
		if otherPage == "" {
			t.Skip("need another page besides Main_Page")
		}

		history2, err := client.GetPageHistory(ctx, otherPage, irowiki.HistoryOptions{Limit: 1})
		if err != nil || len(history2) == 0 {
			t.Skip("need revision from second page")
		}

		// Try to diff revisions from different pages
		_, err = client.GetRevisionDiff(ctx, history1[0].ID, history2[0].ID)
		if err == nil || !strings.Contains(err.Error(), "different pages") {
			t.Errorf("expected error about different pages, got %v", err)
		}
	})

	t.Run("non-existent revision returns not found", func(t *testing.T) {
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 1})
		if err != nil || len(history) == 0 {
			t.Skip("need at least 1 revision for this test")
		}

		_, err = client.GetRevisionDiff(ctx, 999999, history[0].ID)
		if err == nil {
			t.Error("expected error for non-existent from revision")
		}

		_, err = client.GetRevisionDiff(ctx, history[0].ID, 999999)
		if err == nil {
			t.Error("expected error for non-existent to revision")
		}
	})

	t.Run("unified diff format is valid", func(t *testing.T) {
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 2})
		if err != nil || len(history) < 2 {
			t.Skip("need at least 2 revisions for this test")
		}

		diff, err := client.GetRevisionDiff(ctx, history[1].ID, history[0].ID)
		if err != nil {
			t.Fatalf("GetRevisionDiff failed: %v", err)
		}

		if diff.Unified == "" && history[0].Content != history[1].Content {
			t.Skip("no diff output for different content")
		}

		// Check for unified diff format markers
		if history[0].Content != history[1].Content {
			if !strings.Contains(diff.Unified, "@@") {
				t.Error("unified diff should contain @@ markers")
			}
		}
	})
}

// TestSQLiteClient_GetConsecutiveDiff tests computing diff from parent revision
func TestSQLiteClient_GetConsecutiveDiff(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	t.Run("diff from parent revision", func(t *testing.T) {
		// Get a revision with a parent
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{})
		if err != nil || len(history) < 2 {
			t.Skip("need at least 2 revisions for this test")
		}

		// Find a revision with a parent
		var revWithParent *irowiki.Revision
		for i := range history {
			if history[i].ParentID != nil {
				revWithParent = &history[i]
				break
			}
		}

		if revWithParent == nil {
			t.Skip("no revision with parent found")
		}

		diff, err := client.GetConsecutiveDiff(ctx, revWithParent.ID)
		if err != nil {
			t.Fatalf("GetConsecutiveDiff failed: %v", err)
		}

		// Verify it computed a diff
		if diff.ToRevision != revWithParent.ID {
			t.Errorf("expected to revision %d, got %d", revWithParent.ID, diff.ToRevision)
		}
		if diff.FromRevision == 0 {
			t.Error("expected non-zero from revision")
		}
	})

	t.Run("first revision diffs from empty", func(t *testing.T) {
		// Get all revisions to find the first one
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{})
		if err != nil || len(history) == 0 {
			t.Skip("need at least 1 revision for this test")
		}

		// The last in the list is the oldest (first revision)
		firstRev := history[len(history)-1]

		// Only test if it's truly the first (no parent)
		if firstRev.ParentID != nil {
			t.Skip("couldn't find first revision")
		}

		diff, err := client.GetConsecutiveDiff(ctx, firstRev.ID)
		if err != nil {
			t.Fatalf("GetConsecutiveDiff failed: %v", err)
		}

		// Should diff from empty (fromRevision = 0)
		if diff.FromRevision != 0 {
			t.Errorf("expected from revision 0 for first revision, got %d", diff.FromRevision)
		}

		// All content should be added
		if diff.Stats.LinesAdded == 0 {
			t.Error("expected lines added for first revision")
		}
		if diff.Stats.LinesRemoved != 0 {
			t.Error("expected no lines removed for first revision")
		}
	})

	t.Run("non-existent revision returns not found", func(t *testing.T) {
		_, err := client.GetConsecutiveDiff(ctx, 999999)
		if err != irowiki.ErrNotFound {
			t.Errorf("expected ErrNotFound, got %v", err)
		}
	})
}

// TestDiffStats tests that diff statistics are correctly computed
func TestDiffStats(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	t.Run("stats are non-negative", func(t *testing.T) {
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 2})
		if err != nil || len(history) < 2 {
			t.Skip("need at least 2 revisions for this test")
		}

		diff, err := client.GetRevisionDiff(ctx, history[1].ID, history[0].ID)
		if err != nil {
			t.Fatalf("GetRevisionDiff failed: %v", err)
		}

		if diff.Stats.LinesAdded < 0 {
			t.Error("lines added should not be negative")
		}
		if diff.Stats.LinesRemoved < 0 {
			t.Error("lines removed should not be negative")
		}
		if diff.Stats.CharsAdded < 0 {
			t.Error("chars added should not be negative")
		}
		if diff.Stats.CharsRemoved < 0 {
			t.Error("chars removed should not be negative")
		}
		if diff.Stats.ChangePercent < 0 || diff.Stats.ChangePercent > 100 {
			t.Errorf("change percent should be 0-100, got %f", diff.Stats.ChangePercent)
		}
	})

	t.Run("identical content has zero stats", func(t *testing.T) {
		history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{Limit: 1})
		if err != nil || len(history) == 0 {
			t.Skip("need at least 1 revision for this test")
		}

		diff, err := client.GetRevisionDiff(ctx, history[0].ID, history[0].ID)
		if err != nil {
			t.Fatalf("GetRevisionDiff failed: %v", err)
		}

		if diff.Stats.LinesAdded != 0 {
			t.Errorf("expected 0 lines added, got %d", diff.Stats.LinesAdded)
		}
		if diff.Stats.LinesRemoved != 0 {
			t.Errorf("expected 0 lines removed, got %d", diff.Stats.LinesRemoved)
		}
		if diff.Stats.ChangePercent != 0 {
			t.Errorf("expected 0%% change, got %f%%", diff.Stats.ChangePercent)
		}
	})
}
