# Story 05: Package Release

**Story ID**: epic-06-story-05  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to package the scraped data into distributable archives  
**So that** users can download complete archives from GitHub Releases

## Acceptance Criteria

1. **Package Creation**
   - [ ] Create compressed database archive (`.tar.gz`)
   - [ ] Create full archive with all files
   - [ ] Split archives if >2GB (GitHub limit)
   - [ ] Generate checksums for all archives

2. **Archive Contents**
   - [ ] Include database file (`irowiki.db`)
   - [ ] Include README with usage instructions
   - [ ] Include schema documentation
   - [ ] Include version/metadata file

3. **Compression**
   - [ ] Use gzip compression for good balance
   - [ ] Optimize compression level (6-9)
   - [ ] Verify compressed archives are valid
   - [ ] Log compression ratio

4. **Validation**
   - [ ] Verify archive integrity after creation
   - [ ] Test extraction works
   - [ ] Generate SHA256 checksums
   - [ ] Create checksum files (`.sha256`)

## Technical Details

### Packaging Script

```bash
#!/bin/bash
# scripts/package-release.sh

set -e

VERSION="${1:-v$(date +%Y-%m).${GITHUB_RUN_NUMBER:-0}}"
OUTPUT_DIR="releases"
DATA_DIR="data"
DOWNLOADS_DIR="downloads"

echo "Packaging release: $VERSION"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Package database
echo "Packaging database..."
tar -czf "$OUTPUT_DIR/irowiki-database-$VERSION.tar.gz" \
    -C "$DATA_DIR" \
    irowiki.db \
    --transform "s|^|irowiki-$VERSION/|"

# Package full archive with downloads
if [[ -d "$DOWNLOADS_DIR" && $(du -sb "$DOWNLOADS_DIR" | cut -f1) -gt 0 ]]; then
    echo "Packaging full archive..."
    
    FULL_SIZE=$(du -sb "$DOWNLOADS_DIR" | cut -f1)
    MAX_SIZE=$((2 * 1024 * 1024 * 1024))  # 2GB in bytes
    
    if [[ $FULL_SIZE -gt $MAX_SIZE ]]; then
        echo "Full archive exceeds 2GB, splitting..."
        tar -czf - -C . "$DATA_DIR" "$DOWNLOADS_DIR" | \
            split -b 1900M - "$OUTPUT_DIR/irowiki-full-$VERSION.tar.gz.part-"
    else
        tar -czf "$OUTPUT_DIR/irowiki-full-$VERSION.tar.gz" \
            -C . "$DATA_DIR" "$DOWNLOADS_DIR"
    fi
fi

# Generate checksums
echo "Generating checksums..."
cd "$OUTPUT_DIR"
for file in *.tar.gz*; do
    sha256sum "$file" > "$file.sha256"
    echo "✓ $(cat "$file.sha256")"
done
cd ..

# Create metadata file
cat > "$OUTPUT_DIR/RELEASE_INFO.json" <<EOF
{
  "version": "$VERSION",
  "release_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database_size": $(stat -f%z "$DATA_DIR/irowiki.db" 2>/dev/null || stat -c%s "$DATA_DIR/irowiki.db"),
  "files": $(ls -1 "$OUTPUT_DIR"/*.tar.gz* | wc -l)
}
EOF

# Display summary
echo ""
echo "=== Release Package Summary ==="
ls -lh "$OUTPUT_DIR"

echo ""
echo "✓ Release packaged successfully"
```

### Workflow Integration

```yaml
- name: Package release
  run: |
    bash scripts/package-release.sh "${{ steps.version.outputs.release_version }}"

- name: Verify packages
  run: |
    echo "Verifying release packages..."
    
    cd releases/
    
    # Verify checksums
    for checksum_file in *.sha256; do
        echo "Verifying: $checksum_file"
        sha256sum -c "$checksum_file"
    done
    
    # Test extraction
    echo ""
    echo "Testing extraction..."
    mkdir -p test-extract
    tar -tzf irowiki-database-*.tar.gz | head -n 10
    tar -xzf irowiki-database-*.tar.gz -C test-extract
    
    # Verify database
    echo ""
    echo "Verifying extracted database..."
    DB_FILE=$(find test-extract -name "irowiki.db")
    if [[ -f "$DB_FILE" ]]; then
        sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM pages;" > /dev/null
        echo "✓ Database is valid"
    else
        echo "❌ Database not found in archive"
        exit 1
    fi
    
    rm -rf test-extract

- name: Create release README
  run: |
    cat > releases/README.md <<'EOF'
# iRO Wiki Archive - ${{ steps.version.outputs.release_date }}

Version: ${{ steps.version.outputs.release_version }}

## Files

- `irowiki-database-*.tar.gz` - SQLite database only (~500MB-2GB)
- `irowiki-full-*.tar.gz` - Full archive with all downloaded files (~5-20GB)
- `*.sha256` - SHA256 checksums for verification

## Installation

### Database Only

```bash
# Download
wget https://github.com/${{ github.repository }}/releases/download/${{ steps.version.outputs.release_version }}/irowiki-database-${{ steps.version.outputs.release_version }}.tar.gz

# Verify checksum
sha256sum -c irowiki-database-${{ steps.version.outputs.release_version }}.tar.gz.sha256

# Extract
tar -xzf irowiki-database-${{ steps.version.outputs.release_version }}.tar.gz
```

### Full Archive

```bash
# Download all parts if split
wget https://github.com/${{ github.repository }}/releases/download/${{ steps.version.outputs.release_version }}/irowiki-full-*.tar.gz*

# Combine and extract if split
cat irowiki-full-*.tar.gz.part-* | tar -xz

# Or extract directly if not split
tar -xzf irowiki-full-*.tar.gz
```

## Usage

### With Go SDK

```go
import "github.com/${{ github.repository }}/sdk/irowiki"

client, err := irowiki.NewSQLiteClient("irowiki-${{ steps.version.outputs.release_version }}/irowiki.db")
if err != nil {
    log.Fatal(err)
}
defer client.Close()

page, err := client.GetPage(context.Background(), "Main_Page")
// ...
```

### Direct SQL

```bash
sqlite3 irowiki-*/irowiki.db "SELECT title FROM pages LIMIT 10;"
```

## Schema

See `SCHEMA.md` in the repository for database schema documentation.
EOF
```

## Dependencies

- **Story 03**: Run incremental scrape (creates data to package)
- **Story 04**: Generate statistics (for release notes)
- **Epic 04**: Export & packaging system

## Implementation Notes

- GitHub has 2GB limit per release asset
- Split large archives into <2GB parts
- Use gzip level 6-9 for good compression
- Include README in every release
- Test extraction before uploading
- Keep checksums for integrity verification

## Testing Requirements

- [ ] Test packaging database only
- [ ] Test packaging full archive
- [ ] Test with archive >2GB (splitting)
- [ ] Test checksum generation
- [ ] Test archive extraction
- [ ] Test corrupted archive detection
- [ ] Verify all files included
- [ ] Test with non-ASCII filenames

## Definition of Done

- [ ] Packaging script created
- [ ] Archive splitting implemented
- [ ] Checksum generation implemented
- [ ] Verification step implemented
- [ ] README template created
- [ ] Workflow integration complete
- [ ] Tested with real data
- [ ] Documentation updated
- [ ] Code reviewed and approved
