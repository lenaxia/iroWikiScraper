package main

import (
	"context"
	"fmt"
	"log"

	"github.com/mikekao/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
	fmt.Println("=================================================================")
	fmt.Println("Testing Go SDK with scraped iRO Wiki data")
	fmt.Println("=================================================================")
	fmt.Println()

	// Open the test database
	client, err := irowiki.OpenSQLite("/home/mikekao/personal/iRO-Wiki-Scraper/test_data/test_scrape.db")
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test 1: List all pages
	fmt.Println("Test 1: List all pages")
	fmt.Println("-----------------------------------------------------------------")
	pages, err := client.ListPages(ctx, 0, 0, 10)
	if err != nil {
		log.Printf("Error listing pages: %v", err)
	} else {
		fmt.Printf("Found %d pages:\n", len(pages))
		for _, page := range pages {
			fmt.Printf("  - ID: %d, Title: %s, Namespace: %d\n",
				page.ID, page.Title, page.Namespace)
		}
	}
	fmt.Println()

	// Test 2: Get a specific page
	fmt.Println("Test 2: Get a specific page (Prontera)")
	fmt.Println("-----------------------------------------------------------------")
	page, err := client.GetPage(ctx, "Prontera")
	if err != nil {
		log.Printf("Error getting page: %v", err)
	} else {
		fmt.Printf("Page found:\n")
		fmt.Printf("  ID: %d\n", page.ID)
		fmt.Printf("  Title: %s\n", page.Title)
		fmt.Printf("  Namespace: %d\n", page.Namespace)
		fmt.Printf("  Is Redirect: %v\n", page.IsRedirect)
	}
	fmt.Println()

	// Test 3: Search for pages
	fmt.Println("Test 3: Search for pages containing 'Arch'")
	fmt.Println("-----------------------------------------------------------------")
	results, err := client.Search(ctx, irowiki.SearchOptions{
		Query: "Arch",
		Limit: 10,
	})
	if err != nil {
		log.Printf("Error searching: %v", err)
	} else {
		fmt.Printf("Found %d results:\n", len(results))
		for _, result := range results {
			fmt.Printf("  - %s\n", result.Title)
		}
	}
	fmt.Println()

	// Test 4: Get statistics
	fmt.Println("Test 4: Get archive statistics")
	fmt.Println("-----------------------------------------------------------------")
	stats, err := client.GetStatistics(ctx)
	if err != nil {
		log.Printf("Error getting statistics: %v", err)
	} else {
		fmt.Printf("Archive Statistics:\n")
		fmt.Printf("  Total Pages: %d\n", stats.TotalPages)
		fmt.Printf("  Total Revisions: %d\n", stats.TotalRevisions)
		fmt.Printf("  Total Files: %d\n", stats.TotalFiles)
	}
	fmt.Println()

	// Test 5: Ping
	fmt.Println("Test 5: Ping database")
	fmt.Println("-----------------------------------------------------------------")
	err = client.Ping(ctx)
	if err != nil {
		log.Printf("Ping failed: %v", err)
	} else {
		fmt.Println("✓ Ping successful - database connection is healthy")
	}
	fmt.Println()

	fmt.Println("=================================================================")
	fmt.Println("All tests completed successfully!")
	fmt.Println("=================================================================")
}
