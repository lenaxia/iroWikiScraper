#!/bin/bash
# Package release artifacts for distribution
# Creates database-only and full archives with checksums

set -e

VERSION="${1:-v$(date +%Y-%m).${GITHUB_RUN_NUMBER:-0}}"
OUTPUT_DIR="releases"
DATA_DIR="data"
DOWNLOADS_DIR="downloads"
EXPORT_DIR="exports"

echo "=== iRO Wiki Scraper Release Packager ==="
echo "Version: $VERSION"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Package database only
echo "Packaging database archive..."
if [[ -f "$DATA_DIR/irowiki.db" ]]; then
    DB_SIZE=$(stat -c%s "$DATA_DIR/irowiki.db" 2>/dev/null || stat -f%z "$DATA_DIR/irowiki.db" 2>/dev/null || echo "0")
    DB_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$DB_SIZE" 2>/dev/null || echo "$DB_SIZE bytes")
    
    echo "  Database size: $DB_SIZE_HUMAN"
    
    tar -czf "$OUTPUT_DIR/irowiki-database-$VERSION.tar.gz" \
        -C "$DATA_DIR" \
        irowiki.db \
        --transform "s|^|irowiki-$VERSION/|"
    
    echo "  ✓ Database archive created"
else
    echo "  ⚠️  Database not found at $DATA_DIR/irowiki.db"
fi

# Package full archive with downloads if they exist
if [[ -d "$DOWNLOADS_DIR" && $(du -sb "$DOWNLOADS_DIR" 2>/dev/null | cut -f1 || echo "0") -gt 0 ]]; then
    echo ""
    echo "Packaging full archive (database + downloads)..."
    
    FULL_SIZE=$(du -sb "$DOWNLOADS_DIR" "$DATA_DIR" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
    FULL_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$FULL_SIZE" 2>/dev/null || echo "$FULL_SIZE bytes")
    MAX_SIZE=$((1900 * 1024 * 1024))  # 1.9GB in bytes (GitHub limit is 2GB)
    
    echo "  Total size: $FULL_SIZE_HUMAN"
    
    if [[ $FULL_SIZE -gt $MAX_SIZE ]]; then
        echo "  Archive exceeds 1.9GB, splitting into parts..."
        tar -czf - \
            -C . \
            --transform "s|^|irowiki-full-$VERSION/|" \
            "$DATA_DIR/irowiki.db" \
            "$DOWNLOADS_DIR" | \
            split -b 1900M -d - "$OUTPUT_DIR/irowiki-full-$VERSION.tar.gz.part-"
        
        PART_COUNT=$(ls -1 "$OUTPUT_DIR"/irowiki-full-*.part-* 2>/dev/null | wc -l)
        echo "  ✓ Full archive split into $PART_COUNT parts"
    else
        tar -czf "$OUTPUT_DIR/irowiki-full-$VERSION.tar.gz" \
            -C . \
            --transform "s|^|irowiki-full-$VERSION/|" \
            "$DATA_DIR/irowiki.db" \
            "$DOWNLOADS_DIR"
        
        echo "  ✓ Full archive created"
    fi
else
    echo ""
    echo "⚠️  No downloads directory found, skipping full archive"
fi

# Package MediaWiki XML export if available
if [[ -d "$EXPORT_DIR" && $(ls -A "$EXPORT_DIR"/*.xml 2>/dev/null | wc -l) -gt 0 ]]; then
    echo ""
    echo "Packaging MediaWiki XML export..."
    
    tar -czf "$OUTPUT_DIR/irowiki-xml-$VERSION.tar.gz" \
        -C "$EXPORT_DIR" \
        --transform "s|^|irowiki-xml-$VERSION/|" \
        .
    
    echo "  ✓ XML export archive created"
fi

# Generate checksums
echo ""
echo "Generating checksums..."
cd "$OUTPUT_DIR"

for file in *.tar.gz*; do
    if [[ -f "$file" ]]; then
        sha256sum "$file" > "$file.sha256"
        CHECKSUM=$(cat "$file.sha256")
        echo "  ✓ $CHECKSUM"
    fi
done

cd ..

# Create metadata file
echo ""
echo "Creating release metadata..."
cat > "$OUTPUT_DIR/RELEASE_INFO.json" <<EOF
{
  "version": "$VERSION",
  "release_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database_size": $(stat -c%s "$DATA_DIR/irowiki.db" 2>/dev/null || stat -f%z "$DATA_DIR/irowiki.db" 2>/dev/null || echo "0"),
  "files": $(ls -1 "$OUTPUT_DIR"/*.tar.gz* 2>/dev/null | wc -l),
  "generator": "iRO Wiki Scraper",
  "source": "https://irowiki.org"
}
EOF

echo "  ✓ Metadata file created"

# Create release README
echo ""
echo "Creating release README..."
cat > "$OUTPUT_DIR/README.md" <<EOF
# iRO Wiki Archive - $VERSION

Release Date: $(date +%Y-%m-%d)

## Files

This release contains the following archives:

EOF

# List all archives
for file in "$OUTPUT_DIR"/*.tar.gz*; do
    if [[ -f "$file" && "$file" != *".sha256" ]]; then
        BASENAME=$(basename "$file")
        SIZE=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
        SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$SIZE" 2>/dev/null || echo "$SIZE bytes")
        
        echo "- \`$BASENAME\` ($SIZE_HUMAN)" >> "$OUTPUT_DIR/README.md"
    fi
done

cat >> "$OUTPUT_DIR/README.md" <<EOF

## Installation

### Database Only

\`\`\`bash
# Download
wget https://github.com/\$REPO/releases/download/$VERSION/irowiki-database-$VERSION.tar.gz

# Verify checksum
sha256sum -c irowiki-database-$VERSION.tar.gz.sha256

# Extract
tar -xzf irowiki-database-$VERSION.tar.gz
\`\`\`

### Full Archive

\`\`\`bash
# Download all parts if split
wget https://github.com/\$REPO/releases/download/$VERSION/irowiki-full-*.tar.gz*

# Combine and extract if split
cat irowiki-full-*.tar.gz.part-* | tar -xz

# Or extract directly if not split
tar -xzf irowiki-full-$VERSION.tar.gz
\`\`\`

## Usage

### Query with SQLite

\`\`\`bash
sqlite3 irowiki-$VERSION/irowiki.db "SELECT title FROM pages LIMIT 10;"
\`\`\`

### Use with Go SDK

\`\`\`go
import "github.com/YOUR_USERNAME/iRO-Wiki-Scraper/sdk/irowiki"

client, err := irowiki.NewSQLiteClient("irowiki-$VERSION/irowiki.db")
if err != nil {
    log.Fatal(err)
}
defer client.Close()

page, err := client.GetPage(context.Background(), "Main_Page")
// ...
\`\`\`

## Schema

See the repository's \`schema/\` directory for database schema documentation.

## License

This archive contains wiki content licensed under GNU Free Documentation License 1.3.
The scraper code is licensed under MIT License.

## Support

For issues or questions, visit: https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper
EOF

echo "  ✓ Release README created"

# Display summary
echo ""
echo "=== Release Package Summary ==="
echo ""
ls -lh "$OUTPUT_DIR" | grep -v "^total" | awk '{printf "  %-10s %s\n", $5, $9}'

# Calculate total size
TOTAL_SIZE=$(du -shc "$OUTPUT_DIR"/*.tar.gz* 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "0")
echo ""
echo "Total archive size: $TOTAL_SIZE"

echo ""
echo "✅ Release packaged successfully!"
echo ""
echo "Next steps:"
echo "1. Verify archives: cd releases/ && sha256sum -c *.sha256"
echo "2. Test extraction: tar -tzf releases/irowiki-database-$VERSION.tar.gz | head"
echo "3. Create GitHub release with tag: $VERSION"
