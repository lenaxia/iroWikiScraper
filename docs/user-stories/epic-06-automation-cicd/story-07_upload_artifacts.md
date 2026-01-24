# Story 07: Upload Release Artifacts

**Story ID**: epic-06-story-07  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to upload packaged archives to the GitHub release  
**So that** users can download the complete wiki archive

## Acceptance Criteria

1. **Upload Assets**
   - [ ] Upload all archive files to release
   - [ ] Upload checksum files
   - [ ] Upload README and metadata
   - [ ] Set correct content types

2. **Upload Validation**
   - [ ] Verify all files uploaded successfully
   - [ ] Check file sizes match local files
   - [ ] Verify checksums after upload
   - [ ] Handle partial upload failures

3. **Performance**
   - [ ] Support concurrent uploads
   - [ ] Show upload progress
   - [ ] Handle large file uploads (>1GB)
   - [ ] Implement timeout handling

4. **Error Recovery**
   - [ ] Retry failed uploads
   - [ ] Resume interrupted uploads if possible
   - [ ] Clean up failed partial uploads
   - [ ] Log detailed error messages

## Technical Details

### Upload with GitHub Release Action

```yaml
- name: Upload release artifacts
  uses: softprops/action-gh-release@v2
  with:
    tag_name: ${{ steps.version.outputs.release_version }}
    files: |
      releases/*.tar.gz
      releases/*.tar.gz.part-*
      releases/*.sha256
      releases/README.md
      releases/RELEASE_INFO.json
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Upload with GitHub CLI

```yaml
- name: Upload artifacts with gh CLI
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    
    echo "Uploading artifacts to release $VERSION..."
    
    cd releases/
    for file in *.tar.gz* *.sha256 README.md RELEASE_INFO.json; do
      if [[ -f "$file" ]]; then
        echo "Uploading: $file"
        gh release upload "$VERSION" "$file" --clobber
      fi
    done
    
    echo "✓ All artifacts uploaded"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Parallel Upload with xargs

```yaml
- name: Upload artifacts in parallel
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    
    cd releases/
    
    # Upload in parallel (4 at a time)
    find . -type f \( -name "*.tar.gz*" -o -name "*.sha256" -o -name "*.md" -o -name "*.json" \) \
      -print0 | \
      xargs -0 -n 1 -P 4 -I {} \
        gh release upload "$VERSION" {} --clobber
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Upload with Retry Logic

```yaml
- name: Upload each artifact with retry
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    RELEASE_DIR="releases"
    MAX_RETRIES=3
    
    upload_with_retry() {
      local file="$1"
      local attempt=1
      
      while [[ $attempt -le $MAX_RETRIES ]]; do
        echo "Uploading $file (attempt $attempt/$MAX_RETRIES)..."
        
        if gh release upload "$VERSION" "$file" --clobber; then
          echo "✓ Uploaded: $file"
          return 0
        else
          echo "⚠ Upload failed: $file"
          attempt=$((attempt + 1))
          
          if [[ $attempt -le $MAX_RETRIES ]]; then
            sleep $((attempt * 5))  # Exponential backoff
          fi
        fi
      done
      
      echo "❌ Failed to upload after $MAX_RETRIES attempts: $file"
      return 1
    }
    
    # Upload each file
    failed_uploads=()
    cd "$RELEASE_DIR"
    
    for file in *.tar.gz* *.sha256 README.md RELEASE_INFO.json; do
      if [[ -f "$file" ]]; then
        if ! upload_with_retry "$file"; then
          failed_uploads+=("$file")
        fi
      fi
    done
    
    # Report results
    if [[ ${#failed_uploads[@]} -gt 0 ]]; then
      echo "❌ Failed uploads:"
      printf '%s\n' "${failed_uploads[@]}"
      exit 1
    else
      echo "✓ All files uploaded successfully"
    fi
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Verify Uploads

```yaml
- name: Verify uploaded artifacts
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    
    echo "Verifying uploaded artifacts..."
    
    # Get list of uploaded assets
    gh release view "$VERSION" --json assets --jq '.assets[].name' > uploaded.txt
    
    # Get list of local files
    cd releases/
    ls -1 *.tar.gz* *.sha256 *.md *.json > ../expected.txt
    cd ..
    
    # Compare
    echo ""
    echo "=== Expected Files ==="
    cat expected.txt
    
    echo ""
    echo "=== Uploaded Files ==="
    cat uploaded.txt
    
    # Check all expected files are uploaded
    missing=()
    while IFS= read -r file; do
      if ! grep -q "^$file$" uploaded.txt; then
        missing+=("$file")
      fi
    done < expected.txt
    
    if [[ ${#missing[@]} -gt 0 ]]; then
      echo ""
      echo "❌ Missing files:"
      printf '%s\n' "${missing[@]}"
      exit 1
    else
      echo ""
      echo "✓ All files uploaded successfully"
    fi
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Progress Tracking

```yaml
- name: Upload with progress tracking
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    
    cd releases/
    
    total_files=$(find . -type f \( -name "*.tar.gz*" -o -name "*.sha256" -o -name "*.md" -o -name "*.json" \) | wc -l)
    current=0
    
    echo "Uploading $total_files files..."
    
    for file in *.tar.gz* *.sha256 *.md *.json; do
      if [[ -f "$file" ]]; then
        current=$((current + 1))
        file_size=$(du -h "$file" | cut -f1)
        
        echo ""
        echo "[$current/$total_files] Uploading: $file ($file_size)"
        
        gh release upload "$VERSION" "$file" --clobber
      fi
    done
    
    echo ""
    echo "✓ Upload complete ($total_files files)"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Dependencies

- **Story 05**: Package release (creates files to upload)
- **Story 06**: Create GitHub release (creates release to upload to)

## Implementation Notes

- GitHub has 2GB limit per asset
- Split large files before upload (handled in Story 05)
- Use `--clobber` to overwrite if re-running
- Parallel uploads speed up process
- Monitor for rate limiting
- Large uploads can take 10+ minutes
- Verify after upload to ensure completeness

## Testing Requirements

- [ ] Test upload of small files
- [ ] Test upload of large files (>1GB)
- [ ] Test upload of split archives
- [ ] Test retry on failure
- [ ] Test parallel uploads
- [ ] Test upload verification
- [ ] Test with network interruption (if possible)
- [ ] Verify all file types uploaded

## Definition of Done

- [ ] Upload mechanism implemented
- [ ] Retry logic implemented
- [ ] Progress tracking implemented
- [ ] Verification step implemented
- [ ] Error handling implemented
- [ ] Parallel upload option implemented
- [ ] Tested with real data
- [ ] Documentation updated
- [ ] Code reviewed and approved
