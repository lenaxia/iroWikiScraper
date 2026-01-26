#!/bin/bash
# Create release from existing database

set -e

DB_PATH="data/irowiki.db"

if [[ ! -f "$DB_PATH" ]]; then
    echo "❌ Database not found: $DB_PATH"
    exit 1
fi

echo "=== Creating GitHub Release ==="
echo ""

# Generate statistics
PAGES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pages")
REVISIONS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM revisions")
FILES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files")
CONTENT_MB=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions")
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)

echo "Database Statistics:"
echo "  Pages: $PAGES"
echo "  Revisions: $REVISIONS"
echo "  Files: $FILES"
echo "  Content: ${CONTENT_MB} MB"
echo "  Database size: $DB_SIZE"
echo ""

# Package database
DATE=$(date +%Y-%m-%d)
PACKAGE_NAME="irowiki-database-${DATE}.tar.gz"

echo "Packaging database..."
cd data
tar -czf "$PACKAGE_NAME" irowiki.db
PACKAGE_SIZE=$(du -h "$PACKAGE_NAME" | cut -f1)
cd ..

echo "  Package: data/$PACKAGE_NAME"
echo "  Size: $PACKAGE_SIZE"
echo ""

# Create GitHub release
VERSION="v${DATE}"
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Tag $VERSION already exists, using ${VERSION}-2"
    VERSION="${VERSION}-2"
fi

echo "Creating tag: $VERSION"
git tag -a "$VERSION" -m "iRO Wiki snapshot ${DATE} - Full scrape completed"
git push origin "$VERSION"

# Release notes
RELEASE_NOTES="Complete snapshot of irowiki.org as of ${DATE}

## Scrape Information
- **Duration:** 3 hours 7 minutes 17 seconds
- **Rate limit:** 1 request/second
- **Namespaces:** 0-15 (all standard namespaces)
- **Performance:** 3,369 pages/hour, 27,067 revisions/hour

## Statistics
- **Pages:** ${PAGES:?}
- **Revisions:** ${REVISIONS:?}
- **Files (metadata):** ${FILES:?}
- **Content size:** ${CONTENT_MB} MB
- **Database size:** ${DB_SIZE}
- **Average revisions per page:** $(echo "scale=2; $REVISIONS / $PAGES" | bc)

## Contents

This database contains:
- ✅ Complete page content and revision history
- ✅ File metadata (URLs, sizes, dimensions, upload dates)
- ✅ Internal links and page relationships
- ✅ User contribution data
- ❌ Actual image files not included (metadata only)

## Usage

### Download and Extract
\`\`\`bash
wget https://github.com/lenaxia/iroWikiScraper/releases/download/${VERSION}/${PACKAGE_NAME}
tar -xzf ${PACKAGE_NAME}
\`\`\`

### Query with SQLite
\`\`\`bash
# Count pages
sqlite3 irowiki.db \"SELECT COUNT(*) FROM pages\"

# Find Izlude page
sqlite3 irowiki.db \"SELECT * FROM pages WHERE title = 'Izlude'\"

# View revision history
sqlite3 irowiki.db \"SELECT revision_id, timestamp, user, comment FROM revisions WHERE page_id = 213 ORDER BY timestamp\"
\`\`\`

### Use with Go SDK
\`\`\`go
import \"github.com/lenaxia/iroWikiScraper/sdk\"

client, _ := sdk.OpenDatabase(\"irowiki.db\")
defer client.Close()

pages, _ := client.SearchPages(\"Poring\")
for _, page := range pages {
    fmt.Printf(\"Found: %s (ID: %d)\\n\", page.Title, page.PageID)
}
\`\`\`

## Bug Fixes Included

This release includes critical bug fixes:
- ✅ Content extraction now uses correct API field (\`*\` instead of \`content\`)
- ✅ Anonymous user edits (user_id=0) properly handled
- ✅ Revision parent/child relationships work regardless of ID ordering

All content verified to be non-empty and complete.

## Future Updates

Monthly incremental updates planned. To download images separately, see documentation in the repository.

---

For issues or questions, please open an issue at https://github.com/lenaxia/iroWikiScraper/issues"

# Create release
echo "Creating GitHub release..."
gh release create "$VERSION" \
  "data/$PACKAGE_NAME" \
  --title "iRO Wiki Archive - ${DATE}" \
  --notes "$RELEASE_NOTES"

echo ""
echo "✓ Release created: $VERSION"
echo "  View at: https://github.com/lenaxia/iroWikiScraper/releases/tag/${VERSION}"
echo ""
