# Story 08: Store Database Artifact

**Story ID**: epic-06-story-08  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to store the database as a GitHub Actions artifact after each scrape  
**So that** the next incremental run can download and use it

## Acceptance Criteria

1. **Artifact Upload**
   - [ ] Upload database file as GitHub Actions artifact
   - [ ] Use descriptive artifact name
   - [ ] Configure appropriate retention period
   - [ ] Compress artifact if beneficial

2. **Artifact Metadata**
   - [ ] Include version/timestamp in artifact
   - [ ] Store metadata about scrape run
   - [ ] Tag artifact with workflow run ID
   - [ ] Include database size information

3. **Storage Optimization**
   - [ ] Only store necessary files
   - [ ] Compress database before upload if larger
   - [ ] Check artifact size limits
   - [ ] Clean up temporary files

4. **Reliability**
   - [ ] Upload even if release creation fails
   - [ ] Verify upload completed successfully
   - [ ] Handle upload failures gracefully
   - [ ] Log artifact URL for reference

## Technical Details

### Upload Database Artifact

```yaml
- name: Upload database artifact
  uses: actions/upload-artifact@v4
  if: always()  # Upload even if later steps fail
  with:
    name: irowiki-database
    path: data/irowiki.db
    retention-days: 90  # Keep for 3 months
    compression-level: 6  # Good balance of speed/size
    if-no-files-found: error

- name: Log artifact information
  if: always()
  run: |
    echo "=== Database Artifact Information ==="
    echo "File: data/irowiki.db"
    echo "Size: $(du -h data/irowiki.db | cut -f1)"
    echo "Artifact name: irowiki-database"
    echo "Retention: 90 days"
    echo "Workflow run: ${{ github.run_id }}"
```

### Upload with Metadata

```yaml
- name: Create artifact metadata
  run: |
    # Create metadata file
    cat > data/artifact-metadata.json <<EOF
    {
      "workflow_run_id": "${{ github.run_id }}",
      "workflow_run_number": ${{ github.run_number }},
      "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "version": "${{ steps.version.outputs.release_version }}",
      "scrape_type": "${{ github.event.inputs.scrape_type || 'incremental' }}",
      "database_size_bytes": $(stat -f%z data/irowiki.db 2>/dev/null || stat -c%s data/irowiki.db),
      "trigger": "${{ github.event_name }}"
    }
    EOF
    
    cat data/artifact-metadata.json

- name: Upload database artifact with metadata
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: irowiki-database
    path: |
      data/irowiki.db
      data/artifact-metadata.json
    retention-days: 90
```

### Conditional Compression

```yaml
- name: Compress database if large
  run: |
    DB_SIZE=$(stat -f%z data/irowiki.db 2>/dev/null || stat -c%s data/irowiki.db)
    
    # If larger than 500MB, compress it
    if [[ $DB_SIZE -gt 524288000 ]]; then
      echo "Database is large ($(numfmt --to=iec-i --suffix=B $DB_SIZE)), compressing..."
      
      gzip -k data/irowiki.db  # Keep original
      
      COMPRESSED_SIZE=$(stat -f%z data/irowiki.db.gz 2>/dev/null || stat -c%s data/irowiki.db.gz)
      SAVINGS=$((DB_SIZE - COMPRESSED_SIZE))
      PERCENT=$((SAVINGS * 100 / DB_SIZE))
      
      echo "Compressed size: $(numfmt --to=iec-i --suffix=B $COMPRESSED_SIZE)"
      echo "Savings: $(numfmt --to=iec-i --suffix=B $SAVINGS) ($PERCENT%)"
      
      # Use compressed version for artifact
      rm data/irowiki.db
      mv data/irowiki.db.gz data/irowiki-artifact.db.gz
      echo "ARTIFACT_PATH=data/irowiki-artifact.db.gz" >> $GITHUB_ENV
    else
      echo "Database size is reasonable, no compression needed"
      echo "ARTIFACT_PATH=data/irowiki.db" >> $GITHUB_ENV
    fi

- name: Upload database artifact
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: irowiki-database
    path: ${{ env.ARTIFACT_PATH }}
    retention-days: 90
```

### Multiple Artifacts for Safety

```yaml
- name: Upload database artifacts
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: irowiki-database-${{ github.run_number }}
    path: data/irowiki.db
    retention-days: 90

- name: Upload latest database artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: irowiki-database-latest
    path: data/irowiki.db
    retention-days: 90
    overwrite: true  # Replace previous "latest"
```

### Verify Artifact Upload

```yaml
- name: Verify artifact upload
  if: always()
  run: |
    # Wait a moment for upload to complete
    sleep 5
    
    # List artifacts for this workflow run
    gh run view ${{ github.run_id }} --json artifacts --jq '.artifacts[] | {name, sizeInBytes, expiredAt}'
    
    # Check if our artifact exists
    if gh run view ${{ github.run_id }} --json artifacts --jq '.artifacts[].name' | grep -q 'irowiki-database'; then
      echo "✓ Database artifact uploaded successfully"
    else
      echo "❌ Database artifact not found"
      exit 1
    fi
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Cleanup Old Artifacts

```yaml
- name: Cleanup old artifacts
  if: success()
  continue-on-error: true
  run: |
    echo "Cleaning up artifacts older than 90 days..."
    
    # Get all artifacts for the repository
    gh api repos/${{ github.repository }}/actions/artifacts \
      --paginate \
      --jq '.artifacts[] | select(.name == "irowiki-database") | select(.expired == false) | .id' | \
      while read artifact_id; do
        # Get artifact details
        artifact_info=$(gh api repos/${{ github.repository }}/actions/artifacts/$artifact_id)
        created_at=$(echo "$artifact_info" | jq -r '.created_at')
        
        # Calculate age in days
        created_timestamp=$(date -d "$created_at" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$created_at" +%s)
        current_timestamp=$(date +%s)
        age_days=$(( (current_timestamp - created_timestamp) / 86400 ))
        
        if [[ $age_days -gt 90 ]]; then
          echo "Deleting artifact $artifact_id (age: $age_days days)"
          gh api -X DELETE repos/${{ github.repository }}/actions/artifacts/$artifact_id || true
        fi
      done
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Dependencies

- **Story 03**: Run incremental scrape (creates database to store)

## Implementation Notes

- GitHub Actions artifacts have 90-day max retention
- Artifacts are compressed automatically by GitHub Actions
- Artifact name must be unique or use overwrite
- artifacts older than retention are deleted automatically
- Free tier: 500MB storage, paid tiers have more
- Consider storing in release if >90 day retention needed
- Artifacts are only accessible within the repository

## Testing Requirements

- [ ] Test artifact upload after successful scrape
- [ ] Test artifact upload after failed scrape
- [ ] Test with small database (<100MB)
- [ ] Test with large database (>1GB)
- [ ] Test metadata file creation
- [ ] Verify artifact appears in Actions UI
- [ ] Test artifact retention period
- [ ] Test artifact download in next run

## Definition of Done

- [ ] Artifact upload step implemented
- [ ] Metadata generation implemented
- [ ] Compression logic implemented (if needed)
- [ ] Verification step implemented
- [ ] Cleanup logic implemented (optional)
- [ ] Tested with real database
- [ ] Documentation updated
- [ ] Code reviewed and approved
