#!/bin/bash
# Check if scrape is complete and create release

SCRAPE_LOG="scrape.log"
DB_PATH="data/irowiki.db"

# Check if scrape is still running
if pgrep -f "python3 -m scraper" > /dev/null; then
    echo "Scrape is still running..."
    
    # Show current progress
    if [[ -f "$DB_PATH" ]]; then
        PAGES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pages" 2>/dev/null || echo "0")
        REVISIONS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM revisions" 2>/dev/null || echo "0")
        CONTENT_MB=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions" 2>/dev/null || echo "0")
        
        echo "Current progress:"
        echo "  Pages: $PAGES"
        echo "  Revisions: $REVISIONS"
        echo "  Content: ${CONTENT_MB} MB"
    fi
    exit 0
fi

# Scrape completed - check the timing log
if [[ -f scrape_timing.log ]]; then
    echo "=== Scrape Complete! ==="
    echo ""
    cat scrape_timing.log
    echo ""
fi

# Ask about creating release
echo "Scrape is complete. Would you like to create a GitHub release? [y/N]"
read -t 30 -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating release..."
    ./scripts/local-scrape-and-release.sh --release
else
    echo "Skipping release creation."
    echo "To create release later, run:"
    echo "  ./scripts/local-scrape-and-release.sh --release"
fi
