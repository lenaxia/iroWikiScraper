// Example program demonstrating timeline and diff functionality
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
	// This example requires an actual database file
	// For demonstration, using a test database path
	client, err := irowiki.OpenSQLite("../../testdata/test.db")
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	fmt.Println("=== iRO Wiki SDK - Timeline and History Features ===\n")

	// 1. Get page history
	fmt.Println("1. Getting page history for 'Main_Page'...")
	history, err := client.GetPageHistory(ctx, "Main_Page", irowiki.HistoryOptions{
		Limit: 5,
	})
	if err != nil {
		log.Fatalf("Failed to get history: %v", err)
	}

	fmt.Printf("   Found %d revisions:\n", len(history))
	for i, rev := range history {
		fmt.Printf("   %d. Rev #%d by %s at %s (Size: %d bytes)\n",
			i+1, rev.ID, rev.User, rev.Timestamp.Format("2006-01-02 15:04:05"), rev.Size)
		if rev.Comment != "" {
			fmt.Printf("      Comment: %s\n", rev.Comment)
		}
	}
	fmt.Println()

	// 2. Get page at specific time
	if len(history) > 1 {
		fmt.Println("2. Getting page content at a specific point in time...")
		// Get content at time of second-to-last revision
		targetTime := history[1].Timestamp
		rev, err := client.GetPageAtTime(ctx, "Main_Page", targetTime)
		if err != nil {
			log.Printf("   Failed: %v\n", err)
		} else {
			fmt.Printf("   At %s, page was at revision #%d\n", targetTime.Format("2006-01-02 15:04:05"), rev.ID)
			fmt.Printf("   Content size: %d bytes\n", rev.Size)
			if len(rev.Content) > 100 {
				fmt.Printf("   Content preview: %s...\n", rev.Content[:100])
			}
		}
		fmt.Println()
	}

	// 3. Get changes in a time period
	fmt.Println("3. Getting all changes in the last 30 days...")
	thirtyDaysAgo := time.Now().AddDate(0, 0, -30)
	changes, err := client.GetChangesByPeriod(ctx, thirtyDaysAgo, time.Now())
	if err != nil {
		log.Printf("   Failed: %v\n", err)
	} else {
		fmt.Printf("   Found %d changes in the last 30 days\n", len(changes))
		if len(changes) > 0 {
			fmt.Println("   Most recent changes:")
			for i := 0; i < len(changes) && i < 3; i++ {
				fmt.Printf("   - Rev #%d at %s by %s\n",
					changes[i].ID,
					changes[i].Timestamp.Format("2006-01-02 15:04:05"),
					changes[i].User)
			}
		}
	}
	fmt.Println()

	// 4. Get editor activity
	if len(history) > 0 && history[0].User != "" {
		fmt.Printf("4. Getting activity for editor '%s'...\n", history[0].User)
		start := time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)
		activity, err := client.GetEditorActivity(ctx, history[0].User, start, time.Now())
		if err != nil {
			log.Printf("   Failed: %v\n", err)
		} else {
			fmt.Printf("   %s has made %d edits\n", history[0].User, len(activity))
		}
		fmt.Println()
	}

	// 5. Get diff between revisions
	if len(history) >= 2 {
		fmt.Println("5. Computing diff between two revisions...")
		diff, err := client.GetRevisionDiff(ctx, history[1].ID, history[0].ID)
		if err != nil {
			log.Printf("   Failed: %v\n", err)
		} else {
			fmt.Printf("   Diff from rev #%d to rev #%d:\n", diff.FromRevision, diff.ToRevision)
			fmt.Printf("   Lines added: %d\n", diff.Stats.LinesAdded)
			fmt.Printf("   Lines removed: %d\n", diff.Stats.LinesRemoved)
			fmt.Printf("   Characters added: %d\n", diff.Stats.CharsAdded)
			fmt.Printf("   Characters removed: %d\n", diff.Stats.CharsRemoved)
			fmt.Printf("   Change percentage: %.1f%%\n", diff.Stats.ChangePercent)

			if diff.Unified != "" {
				fmt.Println("\n   Unified diff (first 500 chars):")
				if len(diff.Unified) > 500 {
					fmt.Printf("   %s...\n", diff.Unified[:500])
				} else {
					fmt.Printf("   %s\n", diff.Unified)
				}
			}
		}
		fmt.Println()
	}

	// 6. Get consecutive diff (from parent)
	if len(history) > 0 {
		fmt.Println("6. Computing consecutive diff (from parent revision)...")
		diff, err := client.GetConsecutiveDiff(ctx, history[0].ID)
		if err != nil {
			log.Printf("   Failed: %v\n", err)
		} else {
			if diff.FromRevision == 0 {
				fmt.Printf("   Revision #%d is the first revision (diff from empty)\n", diff.ToRevision)
			} else {
				fmt.Printf("   Revision #%d changed from revision #%d\n", diff.ToRevision, diff.FromRevision)
			}
			fmt.Printf("   Lines added: %d, removed: %d\n", diff.Stats.LinesAdded, diff.Stats.LinesRemoved)
		}
	}

	fmt.Println("\n=== Example completed successfully! ===")
}
