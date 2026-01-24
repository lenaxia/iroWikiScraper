# Story 10: Handle Large Artifacts

**Story ID**: epic-06-story-10  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to handle large database artifacts efficiently  
**So that** uploads don't fail and storage costs stay reasonable

## Acceptance Criteria

1. **Size Detection**
   - [ ] Detect artifact size before upload
   - [ ] Warn if approaching size limits
   - [ ] Log artifact sizes for monitoring
   - [ ] Fail early if size exceeds limits

2. **Compression Strategy**
   - [ ] Compress artifacts >500MB
   - [ ] Test multiple compression algorithms
   - [ ] Choose optimal compression level
   - [ ] Document compression ratios

3. **Splitting Large Files**
   - [ ] Split artifacts >2GB for releases
   - [ ] Create numbered parts
   - [ ] Include reassembly instructions
   - [ ] Verify split/join operations

4. **Alternative Storage**
   - [ ] Use GitHub Releases for large artifacts
   - [ ] Consider external storage (S3) for very large files
   - [ ] Document storage options
   - [ ] Implement fallback mechanisms

## Technical Details

### Size Detection

```yaml
- name: Check database size
  id: check-size
  run: |
    DB_SIZE=$(stat -f%z data/irowiki.db 2>/dev/null || stat -c%s data/irowiki.db)
    DB_SIZE_MB=$((DB_SIZE / 1048576))
    
    echo "Database size: $(numfmt --to=iec-i --suffix=B $DB_SIZE) ($DB_SIZE_MB MB)"
    echo "size_bytes=$DB_SIZE" >> $GITHUB_OUTPUT
    echo "size_mb=$DB_SIZE_MB" >> $GITHUB_OUTPUT
    
    # GitHub Actions artifact size limits
    # Soft limit: 2GB recommended
    # Hard limit: 5GB (but may have issues)
    if [[ $DB_SIZE_MB -gt 2048 ]]; then
      echo "⚠ Database exceeds 2GB, will use compression/splitting"
      echo "needs_compression=true" >> $GITHUB_OUTPUT
    elif [[ $DB_SIZE_MB -gt 500 ]]; then
      echo "⚠ Database is large, will compress"
      echo "needs_compression=true" >> $GITHUB_OUTPUT
    else
      echo "✓ Database size is acceptable"
      echo "needs_compression=false" >> $GITHUB_OUTPUT
    fi
```

### Compression Comparison

```yaml
- name: Test compression algorithms
  if: steps.check-size.outputs.needs_compression == 'true'
  run: |
    echo "Testing compression algorithms..."
    
    # Original size
    ORIGINAL_SIZE=$(stat -f%z data/irowiki.db 2>/dev/null || stat -c%s data/irowiki.db)
    echo "Original: $(numfmt --to=iec-i --suffix=B $ORIGINAL_SIZE)"
    
    # Test gzip (fast, good compression)
    time gzip -c -6 data/irowiki.db > data/irowiki.db.gz
    GZIP_SIZE=$(stat -f%z data/irowiki.db.gz 2>/dev/null || stat -c%s data/irowiki.db.gz)
    GZIP_RATIO=$((ORIGINAL_SIZE * 100 / GZIP_SIZE))
    echo "Gzip: $(numfmt --to=iec-i --suffix=B $GZIP_SIZE) ($GZIP_RATIO% ratio)"
    
    # Test zstd (faster, similar compression)
    time zstd -6 -q data/irowiki.db -o data/irowiki.db.zst
    ZSTD_SIZE=$(stat -f%z data/irowiki.db.zst 2>/dev/null || stat -c%s data/irowiki.db.zst)
    ZSTD_RATIO=$((ORIGINAL_SIZE * 100 / ZSTD_SIZE))
    echo "Zstd: $(numfmt --to=iec-i --suffix=B $ZSTD_SIZE) ($ZSTD_RATIO% ratio)"
    
    # Test xz (slow, best compression)
    time xz -c -6 data/irowiki.db > data/irowiki.db.xz
    XZ_SIZE=$(stat -f%z data/irowiki.db.xz 2>/dev/null || stat -c%s data/irowiki.db.xz)
    XZ_RATIO=$((ORIGINAL_SIZE * 100 / XZ_SIZE))
    echo "XZ: $(numfmt --to=iec-i --suffix=B $XZ_SIZE) ($XZ_RATIO% ratio)"
    
    # Choose best based on size/speed tradeoff
    # For CI/CD, prefer zstd (fast) over xz (slow)
    echo "Using zstd for optimal speed/compression balance"
    mv data/irowiki.db.zst data/irowiki-compressed.db.zst
    echo "compressed_path=data/irowiki-compressed.db.zst" >> $GITHUB_OUTPUT
```

### Optimal Compression

```yaml
- name: Compress database
  if: steps.check-size.outputs.needs_compression == 'true'
  run: |
    echo "Compressing database with zstd..."
    
    # Zstd level 6 is good balance (1=fast, 19=best)
    zstd -6 --rm data/irowiki.db -o data/irowiki.db.zst
    
    ORIGINAL_SIZE=${{ steps.check-size.outputs.size_bytes }}
    COMPRESSED_SIZE=$(stat -f%z data/irowiki.db.zst 2>/dev/null || stat -c%s data/irowiki.db.zst)
    SAVINGS=$((ORIGINAL_SIZE - COMPRESSED_SIZE))
    PERCENT=$((SAVINGS * 100 / ORIGINAL_SIZE))
    
    echo "Original: $(numfmt --to=iec-i --suffix=B $ORIGINAL_SIZE)"
    echo "Compressed: $(numfmt --to=iec-i --suffix=B $COMPRESSED_SIZE)"
    echo "Savings: $(numfmt --to=iec-i --suffix=B $SAVINGS) ($PERCENT%)"

- name: Upload compressed artifact
  uses: actions/upload-artifact@v4
  if: steps.check-size.outputs.needs_compression == 'true'
  with:
    name: irowiki-database
    path: data/irowiki.db.zst
    retention-days: 90
    compression-level: 0  # Already compressed, don't double-compress

- name: Create decompression instructions
  if: steps.check-size.outputs.needs_compression == 'true'
  run: |
    cat > DECOMPRESSION.md <<'EOF'
# Decompression Instructions

This artifact has been compressed with zstd to save space.

## Install zstd

**Ubuntu/Debian:**
```bash
sudo apt-get install zstd
```

**macOS:**
```bash
brew install zstd
```

**Windows:**
```powershell
choco install zstandard
```

## Decompress

```bash
zstd -d irowiki.db.zst
```

This will create `irowiki.db` in the current directory.
EOF
    
    cat DECOMPRESSION.md
```

### Split Large Files

```yaml
- name: Split large artifact
  if: steps.check-size.outputs.size_mb > 1900  # Leave buffer under 2GB
  run: |
    echo "Splitting large database..."
    
    # Split into 1GB chunks
    split -b 1G data/irowiki.db data/irowiki.db.part-
    
    # Create reassembly script
    cat > data/reassemble.sh <<'EOF'
#!/bin/bash
cat irowiki.db.part-* > irowiki.db
echo "Database reassembled: irowiki.db"
EOF
    chmod +x data/reassemble.sh
    
    # List parts
    echo "Parts created:"
    ls -lh data/irowiki.db.part-*

- name: Upload split artifacts
  if: steps.check-size.outputs.size_mb > 1900
  uses: actions/upload-artifact@v4
  with:
    name: irowiki-database-parts
    path: |
      data/irowiki.db.part-*
      data/reassemble.sh
    retention-days: 90
```

### Alternative: External Storage

```yaml
- name: Upload to S3 (if very large)
  if: steps.check-size.outputs.size_mb > 3000  # >3GB
  run: |
    echo "Database too large for GitHub artifacts, uploading to S3..."
    
    # Upload to S3
    aws s3 cp data/irowiki.db \
      s3://irowiki-archives/$(date +%Y-%m)/irowiki.db \
      --storage-class INTELLIGENT_TIERING
    
    # Create pointer file
    cat > data/ARTIFACT_LOCATION.txt <<EOF
    This artifact is too large for GitHub Actions.
    Download from: s3://irowiki-archives/$(date +%Y-%m)/irowiki.db
    
    Or use: aws s3 cp s3://irowiki-archives/$(date +%Y-%m)/irowiki.db .
    EOF
    
    # Upload pointer as artifact
    gh actions-cache set irowiki-database data/ARTIFACT_LOCATION.txt
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### Download Compressed Artifact

```yaml
# In next workflow run
- name: Download and decompress artifact
  run: |
    # Download
    gh run download --name irowiki-database --dir data/
    
    # Check if compressed
    if [[ -f "data/irowiki.db.zst" ]]; then
      echo "Decompressing artifact..."
      zstd -d data/irowiki.db.zst -o data/irowiki.db
      rm data/irowiki.db.zst
    fi
    
    # Check if split
    if [[ -f "data/reassemble.sh" ]]; then
      echo "Reassembling split artifact..."
      cd data/
      bash reassemble.sh
      rm irowiki.db.part-* reassemble.sh
    fi
    
    echo "✓ Database ready: data/irowiki.db"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Dependencies

- **Story 08**: Store database artifact (base implementation)

## Implementation Notes

- GitHub Actions artifacts up to 5GB (but 2GB recommended)
- Compression can save 30-50% for SQLite databases
- zstd is faster than gzip with similar compression
- Split files if approaching 2GB to be safe
- Consider external storage (S3, Azure Blob) for >5GB
- Document decompression/reassembly for users
- Test compression ratios with real data

## Testing Requirements

- [ ] Test with small database (<500MB)
- [ ] Test with medium database (500MB-2GB)
- [ ] Test with large database (2-5GB)
- [ ] Test compression algorithms
- [ ] Test split/reassemble operations
- [ ] Test decompression in next workflow run
- [ ] Verify compressed artifacts work correctly
- [ ] Measure compression times

## Definition of Done

- [ ] Size detection implemented
- [ ] Compression strategy implemented
- [ ] Splitting logic implemented (if needed)
- [ ] Decompression instructions created
- [ ] Download and decompress logic implemented
- [ ] Tested with various database sizes
- [ ] Documentation updated
- [ ] Code reviewed and approved
