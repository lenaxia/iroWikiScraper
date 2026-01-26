#!/bin/bash
# Local scrape and release script for iRO Wiki Scraper
# Run this locally since GitHub Actions is blocked by irowiki.org

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== iRO Wiki Scraper - Local Scrape & Release ==="
echo ""

# Parse arguments
SCRAPE_TYPE="full"
NAMESPACES="0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15"
RATE_LIMIT="1"
CREATE_RELEASE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --incremental)
            SCRAPE_TYPE="incremental"
            shift
            ;;
        --namespaces)
            NAMESPACES="$2"
            shift 2
            ;;
        --rate-limit)
            RATE_LIMIT="$2"
            shift 2
            ;;
        --release)
            CREATE_RELEASE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --incremental         Run incremental scrape instead of full"
            echo "  --namespaces \"0 4 6\"  Specify namespaces (default: all 0-15)"
            echo "  --rate-limit N        Requests per second (default: 1)"
            echo "  --release             Create GitHub release after scraping"
            echo "  --help                Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Full scrape of all namespaces"
            echo "  $0"
            echo ""
            echo "  # Full scrape with faster rate"
            echo "  $0 --rate-limit 2"
            echo ""
            echo "  # Scrape specific namespaces and create release"
            echo "  $0 --namespaces \"0 4 6\" --release"
            echo ""
            echo "  # Incremental update"
            echo "  $0 --incremental --release"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

echo "Configuration:"
echo "  Scrape type: $SCRAPE_TYPE"
if [[ "$SCRAPE_TYPE" == "full" ]]; then
    echo "  Namespaces: $NAMESPACES"
fi
echo "  Rate limit: $RATE_LIMIT req/sec"
echo "  Create release: $CREATE_RELEASE"
echo ""

# Ensure data directory exists
mkdir -p data

# Run the scrape
echo "=== Starting Scrape ==="
if [[ "$SCRAPE_TYPE" == "full" ]]; then
    python3 -m scraper full \
        --namespace $NAMESPACES \
        --rate-limit "$RATE_LIMIT" \
        --resume
else
    python3 -m scraper incremental \
        --rate-limit "$RATE_LIMIT"
fi

SCRAPE_EXIT_CODE=$?
if [[ $SCRAPE_EXIT_CODE -ne 0 ]]; then
    echo "❌ Scrape failed with exit code $SCRAPE_EXIT_CODE"
    exit $SCRAPE_EXIT_CODE
fi

echo ""
echo "✓ Scrape completed successfully"
echo ""

# Generate statistics
echo "=== Database Statistics ==="
if [[ -f data/irowiki.db ]]; then
    PAGES=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages")
    REVISIONS=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM revisions")
    FILES=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM files")
    DB_SIZE=$(du -h data/irowiki.db | cut -f1)
    CONTENT_MB=$(sqlite3 data/irowiki.db "SELECT ROUND(SUM(LENGTH(content)) / 1024.0 / 1024.0, 2) FROM revisions")
    
    echo "  Pages: $PAGES"
    echo "  Revisions: $REVISIONS"
    echo "  Files: $FILES"
    echo "  Database size: $DB_SIZE"
    echo "  Content size: ${CONTENT_MB} MB"
else
    echo "  ⚠️  Database file not found"
fi
echo ""

# Package the database
echo "=== Packaging Database ==="
DATE=$(date +%Y-%m-%d)
PACKAGE_NAME="irowiki-database-${DATE}.tar.gz"
cd data
tar -czf "$PACKAGE_NAME" irowiki.db
PACKAGE_SIZE=$(du -h "$PACKAGE_NAME" | cut -f1)
cd ..

echo "  Created: data/$PACKAGE_NAME"
echo "  Size: $PACKAGE_SIZE"
echo ""

# Create release if requested
if [[ "$CREATE_RELEASE" == "true" ]]; then
    echo "=== Creating GitHub Release ==="
    
    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        echo "❌ GitHub CLI (gh) not found. Install it or run without --release"
        echo "   Download from: https://cli.github.com/"
        exit 1
    fi
    
    # Create version tag
    VERSION="v${DATE}"
    if git rev-parse "$VERSION" >/dev/null 2>&1; then
        echo "  Tag $VERSION already exists, adding -2 suffix"
        VERSION="${VERSION}-2"
    fi
    
    echo "  Creating tag: $VERSION"
    git tag -a "$VERSION" -m "iRO Wiki snapshot ${DATE}"
    git push origin "$VERSION"
    
    # Generate release notes
    RELEASE_NOTES="Complete snapshot of irowiki.org as of ${DATE}

## Statistics
- **Pages:** ${PAGES}
- **Revisions:** ${REVISIONS}
- **Files:** ${FILES}
- **Database size:** ${DB_SIZE}
- **Content size:** ${CONTENT_MB} MB

## Usage

### Download and Extract
\`\`\`bash
wget https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/download/${VERSION}/${PACKAGE_NAME}
tar -xzf ${PACKAGE_NAME}
\`\`\`

### Query with SQLite
\`\`\`bash
# Get page count
sqlite3 irowiki.db \"SELECT COUNT(*) FROM pages\"

# Find a page
sqlite3 irowiki.db \"SELECT * FROM pages WHERE title LIKE '%Poring%'\"
\`\`\`

### Use with Go SDK
\`\`\`go
import \"github.com/lenaxia/iroWikiScraper/sdk\"

client, _ := sdk.OpenDatabase(\"irowiki.db\")
defer client.Close()

pages, _ := client.SearchPages(\"Poring\")
\`\`\`

## Notes
This database contains the complete revision history and content of all pages from irowiki.org."
    
    # Create the release
    echo "  Creating release..."
    gh release create "$VERSION" \
        "data/$PACKAGE_NAME" \
        --title "iRO Wiki Archive - ${DATE}" \
        --notes "$RELEASE_NOTES"
    
    echo ""
    echo "✓ Release created: $VERSION"
    echo "  View at: https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases/tag/${VERSION}"
else
    echo "ℹ️  Skipping release creation (use --release to create one)"
    echo "   Package is ready at: data/$PACKAGE_NAME"
fi

echo ""
echo "=== Complete ==="
echo ""
echo "Next steps:"
if [[ "$CREATE_RELEASE" == "false" ]]; then
    echo "  1. Test the database: sqlite3 data/irowiki.db"
    echo "  2. Create release: $0 --release"
fi
echo "  • Share the release URL with users"
echo "  • Schedule monthly incremental updates"
echo ""
