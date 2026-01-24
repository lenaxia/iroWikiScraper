package irowiki_test

import (
	"context"
	"testing"
	"time"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/internal/testutil"
	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

// TestSQLiteClient_GetStatisticsEnhanced tests comprehensive enhanced archive statistics
func TestSQLiteClient_GetStatisticsEnhanced(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Get enhanced statistics
	stats, err := client.GetStatisticsEnhanced(ctx)
	if err != nil {
		t.Fatalf("GetStatisticsEnhanced failed: %v", err)
	}

	// Verify basic counts
	if stats.TotalPages <= 0 {
		t.Error("expected TotalPages > 0")
	}
	if stats.TotalRevisions <= 0 {
		t.Error("expected TotalRevisions > 0")
	}

	// Verify temporal statistics
	if stats.FirstEdit.IsZero() {
		t.Error("expected FirstEdit to be set")
	}
	if stats.LastEdit.IsZero() {
		t.Error("expected LastEdit to be set")
	}
	if stats.LastEdit.Before(stats.FirstEdit) {
		t.Error("LastEdit should be after FirstEdit")
	}

	// Verify namespace distribution
	if stats.PagesByNamespace == nil {
		t.Error("expected PagesByNamespace to be initialized")
	}
	if len(stats.PagesByNamespace) == 0 {
		t.Error("expected at least one namespace")
	}

	// Verify namespace totals match
	var totalPages int64
	for _, count := range stats.PagesByNamespace {
		totalPages += count
	}
	if totalPages != stats.TotalPages {
		t.Errorf("sum of namespace pages (%d) != TotalPages (%d)",
			totalPages, stats.TotalPages)
	}

	// Verify top editors
	if len(stats.TopEditors) == 0 {
		t.Error("expected at least one top editor")
	}
	for i, editor := range stats.TopEditors {
		if editor.Username == "" {
			t.Errorf("TopEditors[%d] has empty username", i)
		}
		if editor.EditCount <= 0 {
			t.Errorf("TopEditors[%d] has invalid edit count: %d", i, editor.EditCount)
		}
		if editor.FirstEdit.IsZero() {
			t.Errorf("TopEditors[%d] has zero FirstEdit", i)
		}
		if editor.LastEdit.IsZero() {
			t.Errorf("TopEditors[%d] has zero LastEdit", i)
		}
	}

	// Verify most edited pages
	if len(stats.MostEditedPages) == 0 {
		t.Error("expected at least one most edited page")
	}
	for i, page := range stats.MostEditedPages {
		if page.PageTitle == "" {
			t.Errorf("MostEditedPages[%d] has empty title", i)
		}
		if page.RevisionCount <= 0 {
			t.Errorf("MostEditedPages[%d] has invalid revision count: %d", i, page.RevisionCount)
		}
	}

	// Verify edits by month
	if stats.EditsByMonth == nil {
		t.Error("expected EditsByMonth to be initialized")
	}

	// Verify extremes
	if stats.LargestPage != nil {
		if stats.LargestPage.Size <= 0 {
			t.Error("LargestPage should have size > 0")
		}
	}
	if stats.SmallestPage != nil {
		if stats.SmallestPage.Size < 0 {
			t.Error("SmallestPage should have size >= 0")
		}
	}

	t.Logf("Enhanced statistics: %d pages, %d revisions, %d editors",
		stats.TotalPages, stats.TotalRevisions, stats.TotalEditors)
	t.Logf("Top editor: %s with %d edits", stats.TopEditors[0].Username, stats.TopEditors[0].EditCount)
	if stats.LargestPage != nil {
		t.Logf("Largest page: %s (%d bytes)", stats.LargestPage.Title, stats.LargestPage.Size)
	}
}

// TestSQLiteClient_GetPageStatsEnhanced tests detailed enhanced page statistics
func TestSQLiteClient_GetPageStatsEnhanced(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get enhanced stats for existing page
	stats, err := client.GetPageStatsEnhanced(ctx, "Main_Page")
	if err != nil {
		t.Fatalf("GetPageStatsEnhanced failed: %v", err)
	}

	// Verify basic info
	if stats.PageID == 0 {
		t.Error("expected PageID to be set")
	}
	if stats.Title != "Main_Page" {
		t.Errorf("expected Title = 'Main_Page', got %q", stats.Title)
	}

	// Verify revision statistics
	if stats.RevisionCount <= 0 {
		t.Error("expected RevisionCount > 0")
	}
	if stats.FirstEdit.IsZero() {
		t.Error("expected FirstEdit to be set")
	}
	if stats.LastEdit.IsZero() {
		t.Error("expected LastEdit to be set")
	}

	// Verify contributor statistics
	if stats.EditorCount <= 0 {
		t.Error("expected EditorCount > 0")
	}

	// Verify top contributors
	if len(stats.TopContributors) == 0 {
		t.Error("expected at least one top contributor")
	}
	for i, contrib := range stats.TopContributors {
		if contrib.Username == "" {
			t.Errorf("TopContributors[%d] has empty username", i)
		}
		if contrib.EditCount <= 0 {
			t.Errorf("TopContributors[%d] has invalid edit count: %d", i, contrib.EditCount)
		}
		if contrib.Percentage < 0 || contrib.Percentage > 100 {
			t.Errorf("TopContributors[%d] has invalid percentage: %.2f", i, contrib.Percentage)
		}
	}

	// Verify size statistics
	if stats.CurrentSize < 0 {
		t.Error("CurrentSize should be non-negative")
	}
	if stats.MinSize < 0 {
		t.Error("MinSize should be non-negative")
	}
	if stats.MaxSize < stats.MinSize {
		t.Errorf("MaxSize (%d) should be >= MinSize (%d)", stats.MaxSize, stats.MinSize)
	}
	if stats.CurrentSize > stats.MaxSize {
		t.Errorf("CurrentSize (%d) should be <= MaxSize (%d)", stats.CurrentSize, stats.MaxSize)
	}

	// Verify quality metrics
	if stats.MinorEditPercent < 0 || stats.MinorEditPercent > 100 {
		t.Errorf("MinorEditPercent should be 0-100, got %.2f", stats.MinorEditPercent)
	}
	if stats.StabilityScore < 0 || stats.StabilityScore > 100 {
		t.Errorf("StabilityScore should be 0-100, got %.2f", stats.StabilityScore)
	}

	// Verify activity patterns
	if stats.EditFrequency != nil && len(stats.EditFrequency) > 0 {
		// If we have edit frequency data, busiest month should be set
		if stats.BusiestMonth == "" {
			t.Error("expected BusiestMonth to be set when EditFrequency has data")
		}
	}

	t.Logf("Page enhanced stats: %d revisions, %d editors, stability: %.1f",
		stats.RevisionCount, stats.EditorCount, stats.StabilityScore)
	if len(stats.TopContributors) > 0 {
		t.Logf("Top contributor: %s with %d edits (%.1f%%)",
			stats.TopContributors[0].Username,
			stats.TopContributors[0].EditCount,
			stats.TopContributors[0].Percentage)
	}
}

// TestSQLiteClient_GetPageStatsEnhanced_NotFound tests enhanced stats for non-existent page
func TestSQLiteClient_GetPageStatsEnhanced_NotFound(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get enhanced stats for non-existent page
	_, err = client.GetPageStatsEnhanced(ctx, "NonExistentPage123")
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_GetEditorActivityEnhanced tests enhanced editor activity analysis
func TestSQLiteClient_GetEditorActivityEnhanced(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// First, get a list of editors
	stats, err := client.GetStatistics(ctx)
	if err != nil {
		t.Fatalf("GetStatistics failed: %v", err)
	}

	// Use the full date range
	start := stats.FirstEdit.Add(-24 * time.Hour)
	end := stats.LastEdit.Add(24 * time.Hour)

	// Get revisions to find an editor
	revisions, err := client.GetChangesByPeriod(ctx, start, end)
	if err != nil || len(revisions) == 0 {
		t.Skip("No revisions found for testing")
	}

	testUser := revisions[0].User

	// Test: Get enhanced activity for specific editor
	activity, err := client.GetEditorActivityEnhanced(ctx, testUser, start, end)
	if err != nil {
		t.Fatalf("GetEditorActivityEnhanced failed: %v", err)
	}

	// Verify basic stats
	if activity.Username != testUser {
		t.Errorf("expected Username = %q, got %q", testUser, activity.Username)
	}
	if activity.TotalEdits <= 0 {
		t.Error("expected TotalEdits > 0")
	}
	if activity.FirstEdit.IsZero() {
		t.Error("expected FirstEdit to be set")
	}
	if activity.LastEdit.IsZero() {
		t.Error("expected LastEdit to be set")
	}
	if activity.ActiveDays <= 0 {
		t.Error("expected ActiveDays > 0")
	}

	// Verify content stats
	if activity.PagesEdited <= 0 {
		t.Error("expected PagesEdited > 0")
	}
	if activity.MinorEdits < 0 {
		t.Error("MinorEdits should be non-negative")
	}
	if activity.MinorEdits > activity.TotalEdits {
		t.Errorf("MinorEdits (%d) cannot exceed TotalEdits (%d)",
			activity.MinorEdits, activity.TotalEdits)
	}

	// Verify activity patterns
	if activity.EditsByHour == nil {
		t.Error("expected EditsByHour to be initialized")
	}
	if activity.EditsByDay == nil {
		t.Error("expected EditsByDay to be initialized")
	}
	if activity.EditsByMonth == nil {
		t.Error("expected EditsByMonth to be initialized")
	}

	// Verify top pages
	if len(activity.TopPages) == 0 {
		t.Error("expected at least one top page")
	}
	for i, page := range activity.TopPages {
		if page.PageTitle == "" {
			t.Errorf("TopPages[%d] has empty title", i)
		}
		if page.EditCount <= 0 {
			t.Errorf("TopPages[%d] has invalid edit count: %d", i, page.EditCount)
		}
	}

	// Verify hour distribution sums to total edits
	var totalHourEdits int
	for _, count := range activity.EditsByHour {
		totalHourEdits += count
	}
	if totalHourEdits != activity.TotalEdits {
		t.Errorf("sum of hourly edits (%d) != TotalEdits (%d)",
			totalHourEdits, activity.TotalEdits)
	}

	t.Logf("Editor %q activity: %d edits across %d pages over %d days",
		activity.Username, activity.TotalEdits, activity.PagesEdited, activity.ActiveDays)
	if len(activity.TopPages) > 0 {
		t.Logf("Most edited page: %s with %d edits",
			activity.TopPages[0].PageTitle, activity.TopPages[0].EditCount)
	}
	t.Logf("Busiest hour: %02d:00, Busiest day: %s",
		activity.BusiestHour, activity.BusiestDay)
}

// TestSQLiteClient_GetEditorActivityEnhanced_NotFound tests enhanced activity for non-existent editor
func TestSQLiteClient_GetEditorActivityEnhanced_NotFound(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test: Get enhanced activity for non-existent editor
	start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2025, 12, 31, 23, 59, 59, 0, time.UTC)

	_, err = client.GetEditorActivityEnhanced(ctx, "NonExistentEditor123", start, end)
	if err != irowiki.ErrNotFound {
		t.Errorf("expected ErrNotFound, got %v", err)
	}
}

// TestSQLiteClient_StatisticsEnhanced_DateRangeFiltering tests enhanced activity with date filtering
func TestSQLiteClient_StatisticsEnhanced_DateRangeFiltering(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Get overall stats to determine date range
	stats, err := client.GetStatistics(ctx)
	if err != nil {
		t.Fatalf("GetStatistics failed: %v", err)
	}

	// Get revisions to find an editor
	revisions, err := client.GetChangesByPeriod(ctx, stats.FirstEdit, stats.LastEdit)
	if err != nil || len(revisions) == 0 {
		t.Skip("No revisions found for testing")
	}

	testUser := revisions[0].User

	// Test with full range
	activityFull, err := client.GetEditorActivityEnhanced(ctx, testUser, stats.FirstEdit, stats.LastEdit)
	if err != nil {
		t.Fatalf("GetEditorActivityEnhanced (full range) failed: %v", err)
	}

	// Test with restricted range (first half)
	midPoint := stats.FirstEdit.Add(stats.LastEdit.Sub(stats.FirstEdit) / 2)
	activityHalf, err := client.GetEditorActivityEnhanced(ctx, testUser, stats.FirstEdit, midPoint)
	if err != nil {
		t.Fatalf("GetEditorActivityEnhanced (half range) failed: %v", err)
	}

	// The half range should have <= edits than full range
	if activityHalf.TotalEdits > activityFull.TotalEdits {
		t.Errorf("half range edits (%d) > full range edits (%d)",
			activityHalf.TotalEdits, activityFull.TotalEdits)
	}

	t.Logf("Date range filtering: Full range: %d edits, Half range: %d edits",
		activityFull.TotalEdits, activityHalf.TotalEdits)
}
