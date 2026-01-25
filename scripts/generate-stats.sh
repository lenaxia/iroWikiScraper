#!/bin/bash
# Generate statistics and release notes from the database
# Output formatted as Markdown for GitHub releases

set -e

DATABASE="${1:-data/irowiki.db}"

if [[ ! -f "$DATABASE" ]]; then
    echo "Error: Database not found at $DATABASE"
    exit 1
fi

# Generate release notes header
cat <<EOF
# iRO Wiki Archive - $(date +%Y-%m)

Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## Summary

This release contains a complete archive of irowiki.org, including all pages, revisions, and metadata.

EOF

# Query database for statistics
echo "## Statistics"
echo ""

# Use sqlite3 to query stats
sqlite3 "$DATABASE" <<SQL
.mode markdown

-- Overall statistics
SELECT '### Overall' as '';
SELECT '' as '';

SELECT 'Metric' as Metric, 'Count' as Count;
SELECT '---' as Metric, '---' as Count;

SELECT 'Total pages' as Metric, COUNT(*) as Count FROM pages;
SELECT 'Total revisions' as Metric, COUNT(*) as Count FROM revisions;
SELECT 'Total users' as Metric, COUNT(DISTINCT user) as Count FROM revisions WHERE user IS NOT NULL;
SELECT 'Total files' as Metric, COUNT(*) as Count FROM files;

-- Recent activity (last 30 days)
SELECT '' as '';
SELECT '### Recent Activity (Last 30 Days)' as '';
SELECT '' as '';

SELECT 'Metric' as Metric, 'Count' as Count;
SELECT '---' as Metric, '---' as Count;

SELECT 'New pages' as Metric, 
       COUNT(*) as Count 
FROM pages 
WHERE created_at >= datetime('now', '-30 days');

SELECT 'Updated pages' as Metric,
       COUNT(DISTINCT page_id) as Count
FROM revisions 
WHERE timestamp >= datetime('now', '-30 days');

SELECT 'New revisions' as Metric,
       COUNT(*) as Count
FROM revisions 
WHERE timestamp >= datetime('now', '-30 days');

SELECT 'Active users' as Metric,
       COUNT(DISTINCT user) as Count
FROM revisions 
WHERE timestamp >= datetime('now', '-30 days') 
  AND user IS NOT NULL;

-- Namespace breakdown
SELECT '' as '';
SELECT '### Pages by Namespace' as '';
SELECT '' as '';

SELECT 'Namespace' as Namespace, 'Pages' as Pages;
SELECT '---' as Namespace, '---' as Pages;

SELECT 
    CASE namespace
        WHEN 0 THEN 'Main'
        WHEN 1 THEN 'Talk'
        WHEN 2 THEN 'User'
        WHEN 3 THEN 'User talk'
        WHEN 4 THEN 'Project'
        WHEN 5 THEN 'Project talk'
        WHEN 6 THEN 'File'
        WHEN 7 THEN 'File talk'
        WHEN 8 THEN 'MediaWiki'
        WHEN 9 THEN 'MediaWiki talk'
        WHEN 10 THEN 'Template'
        WHEN 11 THEN 'Template talk'
        WHEN 12 THEN 'Help'
        WHEN 13 THEN 'Help talk'
        WHEN 14 THEN 'Category'
        WHEN 15 THEN 'Category talk'
        ELSE 'Other (' || namespace || ')'
    END as Namespace,
    COUNT(*) as Pages
FROM pages
GROUP BY namespace
ORDER BY namespace;

-- Top contributors (last 30 days)
SELECT '' as '';
SELECT '### Top Contributors (Last 30 Days)' as '';
SELECT '' as '';

SELECT 'User' as User, 'Edits' as Edits;
SELECT '---' as User, '---' as Edits;

SELECT 
    COALESCE(user, 'Anonymous') as User,
    COUNT(*) as Edits
FROM revisions
WHERE timestamp >= datetime('now', '-30 days')
GROUP BY user
ORDER BY COUNT(*) DESC
LIMIT 10;

-- Database size info
SELECT '' as '';
SELECT '### Database Information' as '';
SELECT '' as '';

SELECT 'Property' as Property, 'Value' as Value;
SELECT '---' as Property, '---' as Value;

.quit
SQL

# Get database file size
DB_SIZE=$(stat -c%s "$DATABASE" 2>/dev/null || stat -f%z "$DATABASE" 2>/dev/null || echo "0")
DB_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$DB_SIZE" 2>/dev/null || echo "$DB_SIZE bytes")

echo "SELECT 'Database size' as Property, '$DB_SIZE_HUMAN' as Value;" | sqlite3 "$DATABASE" -markdown

# Get last scrape run info if available
if sqlite3 "$DATABASE" "SELECT name FROM sqlite_master WHERE type='table' AND name='scrape_runs';" | grep -q "scrape_runs"; then
    sqlite3 "$DATABASE" -markdown <<SQL
SELECT 'Last scrape' as Property, 
       datetime(MAX(start_time), 'localtime') as Value
FROM scrape_runs;

SELECT 'Scrape status' as Property,
       status as Value
FROM scrape_runs
ORDER BY start_time DESC
LIMIT 1;
SQL
fi

# Add download instructions
cat <<EOF

## Download Instructions

### Database Only (~$DB_SIZE_HUMAN)

\`\`\`bash
# Download database archive
wget https://github.com/\$REPO/releases/download/\$VERSION/irowiki-database-\$VERSION.tar.gz

# Verify checksum
wget https://github.com/\$REPO/releases/download/\$VERSION/irowiki-database-\$VERSION.tar.gz.sha256
sha256sum -c irowiki-database-\$VERSION.tar.gz.sha256

# Extract
tar -xzf irowiki-database-\$VERSION.tar.gz
\`\`\`

### Full Archive (includes downloaded files)

\`\`\`bash
# Download full archive (may be split into parts)
wget https://github.com/\$REPO/releases/download/\$VERSION/irowiki-full-\$VERSION.tar.gz*

# Extract (combines parts automatically if split)
cat irowiki-full-\$VERSION.tar.gz* | tar -xz
\`\`\`

## Usage Examples

### SQLite Command Line

\`\`\`bash
# Search for pages
sqlite3 irowiki-*/irowiki.db "SELECT title FROM pages WHERE title LIKE '%Poring%' LIMIT 10;"

# Get page history
sqlite3 irowiki-*/irowiki.db "SELECT timestamp, comment FROM revisions WHERE page_id = 1 ORDER BY timestamp DESC;"

# Export to CSV
sqlite3 irowiki-*/irowiki.db -csv -header "SELECT * FROM pages;" > pages.csv
\`\`\`

### Python

\`\`\`python
import sqlite3

conn = sqlite3.connect('irowiki-*/irowiki.db')
cursor = conn.cursor()

# Search pages
cursor.execute("SELECT title FROM pages WHERE title LIKE ? LIMIT 10", ('%Poring%',))
for row in cursor.fetchall():
    print(row[0])

conn.close()
\`\`\`

### Go SDK

\`\`\`go
import "github.com/YOUR_USERNAME/iRO-Wiki-Scraper/sdk/irowiki"

client, _ := irowiki.NewSQLiteClient("irowiki-*/irowiki.db")
defer client.Close()

// Search for pages
results, _ := client.Search(context.Background(), irowiki.SearchOptions{
    Query: "Poring",
    Limit: 10,
})

for _, result := range results {
    fmt.Printf("%s (ID: %d)\\n", result.Title, result.PageID)
}
\`\`\`

## Schema

The database follows this schema:

- **pages**: Page metadata (ID, title, namespace, creation date)
- **revisions**: Complete revision history with content
- **files**: Downloaded media files with checksums
- **links**: Internal wiki link structure
- **scrape_runs**: Metadata about archival runs

Full schema documentation: https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/tree/main/schema

## Support

- **Issues**: https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/issues
- **Discussions**: https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/discussions

## License

- **Wiki Content**: GNU Free Documentation License 1.3 (GFDL)
- **Scraper Code**: MIT License

---

*This archive was generated automatically by the iRO Wiki Scraper.*
EOF
