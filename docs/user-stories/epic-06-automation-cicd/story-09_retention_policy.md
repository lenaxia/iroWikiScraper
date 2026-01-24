# Story 09: Artifact Retention Policy

**Story ID**: epic-06-story-09  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 1 hour  
**Status**: Not Started

## User Story

**As a** project maintainer  
**I want** to configure appropriate retention policies for artifacts  
**So that** storage costs are minimized while maintaining necessary history

## Acceptance Criteria

1. **Retention Configuration**
   - [ ] Database artifacts retained for 90 days
   - [ ] Log artifacts retained for 30 days
   - [ ] Temporary artifacts retained for 7 days
   - [ ] Critical artifacts preserved indefinitely in releases

2. **Policy Documentation**
   - [ ] Document retention policy in README
   - [ ] Explain why each retention period chosen
   - [ ] Document storage cost implications
   - [ ] Provide cleanup instructions

3. **Automatic Cleanup**
   - [ ] Artifacts auto-delete after retention period
   - [ ] Old workflow runs cleaned up
   - [ ] Monitor storage usage
   - [ ] Alert if approaching limits

4. **Manual Override**
   - [ ] Ability to delete artifacts manually
   - [ ] Ability to preserve specific artifacts
   - [ ] Ability to download before expiry
   - [ ] Script to bulk delete old artifacts

## Technical Details

### Retention Policy Configuration

```yaml
# Database artifacts - needed for next incremental run
- name: Upload database artifact
  uses: actions/upload-artifact@v4
  with:
    name: irowiki-database
    path: data/irowiki.db
    retention-days: 90  # 3 months covers ~3 monthly runs

# Scrape logs - useful for debugging recent runs
- name: Upload scrape logs
  uses: actions/upload-artifact@v4
  with:
    name: scrape-logs-${{ github.run_number }}
    path: logs/
    retention-days: 30  # 1 month for debugging

# Temporary build artifacts - short-term only
- name: Upload temporary artifacts
  uses: actions/upload-artifact@v4
  with:
    name: temp-${{ github.run_number }}
    path: temp/
    retention-days: 7  # 1 week
```

### Storage Usage Monitoring

```yaml
- name: Check artifact storage usage
  run: |
    echo "=== Artifact Storage Usage ==="
    
    # Get all artifacts
    total_size=0
    artifact_count=0
    
    gh api repos/${{ github.repository }}/actions/artifacts \
      --paginate \
      --jq '.artifacts[] | {name, size_in_bytes, expired}' | \
      while IFS= read -r artifact; do
        artifact_count=$((artifact_count + 1))
        size=$(echo "$artifact" | jq -r '.size_in_bytes')
        total_size=$((total_size + size))
      done
    
    echo "Total artifacts: $artifact_count"
    echo "Total size: $(numfmt --to=iec-i --suffix=B $total_size)"
    
    # GitHub free tier: 500MB
    # Warn if over 400MB
    if [[ $total_size -gt 419430400 ]]; then
      echo "⚠ Warning: Approaching storage limit (500MB)"
      echo "Consider cleaning up old artifacts"
    fi
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Manual Cleanup Script

```bash
#!/bin/bash
# scripts/cleanup-artifacts.sh

set -e

REPO="${1:-$GITHUB_REPOSITORY}"
DAYS_TO_KEEP="${2:-90}"

echo "Cleaning up artifacts older than $DAYS_TO_KEEP days in $REPO"

# Calculate cutoff date
CUTOFF_DATE=$(date -d "$DAYS_TO_KEEP days ago" +%Y-%m-%d 2>/dev/null || date -v-${DAYS_TO_KEEP}d +%Y-%m-%d)
echo "Cutoff date: $CUTOFF_DATE"

# List and delete old artifacts
gh api repos/$REPO/actions/artifacts --paginate | \
  jq -r ".artifacts[] | select(.created_at < \"$CUTOFF_DATE\") | .id" | \
  while read artifact_id; do
    echo "Deleting artifact: $artifact_id"
    gh api -X DELETE repos/$REPO/actions/artifacts/$artifact_id
  done

echo "✓ Cleanup complete"
```

### Cleanup Workflow

```yaml
name: Cleanup Old Artifacts

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  cleanup:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Delete old artifacts
        uses: c-hive/gha-remove-artifacts@v1
        with:
          age: '90 days'
          skip-recent: 3  # Keep last 3 regardless of age
      
      - name: Report storage usage
        run: |
          total=$(gh api repos/${{ github.repository }}/actions/artifacts --jq '[.artifacts[].size_in_bytes] | add')
          echo "Current storage: $(numfmt --to=iec-i --suffix=B $total)"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Retention Policy Documentation

```markdown
## Artifact Retention Policy

### Database Artifacts
- **Retention**: 90 days
- **Reason**: Supports 3 monthly incremental scrapes with buffer
- **Size**: ~500MB-2GB per artifact
- **Backup**: Latest database also stored in GitHub Releases (indefinite)

### Scrape Logs
- **Retention**: 30 days
- **Reason**: Sufficient for debugging recent runs
- **Size**: ~10-50MB per artifact
- **Backup**: Critical errors logged in workflow output (90 days)

### Temporary Artifacts
- **Retention**: 7 days
- **Reason**: Only needed for active debugging
- **Size**: Varies
- **Backup**: None needed

### Storage Limits
- **GitHub Free**: 500MB total artifact storage
- **GitHub Pro**: 2GB total artifact storage
- **GitHub Team**: 2GB total artifact storage
- **Current Usage**: Check in Actions tab

### Manual Cleanup
```bash
# Clean up artifacts older than 90 days
./scripts/cleanup-artifacts.sh

# Clean up all artifacts except latest
gh api repos/OWNER/REPO/actions/artifacts | \
  jq -r '.artifacts[1:] | .[].id' | \
  xargs -I {} gh api -X DELETE repos/OWNER/REPO/actions/artifacts/{}
```
```

### Preserve Critical Artifacts

```yaml
- name: Store critical artifacts in release
  if: success()
  run: |
    VERSION="${{ steps.version.outputs.release_version }}"
    
    # Database already in release, but let's also save metadata
    gh release upload "$VERSION" \
      data/artifact-metadata.json \
      --clobber
    
    echo "Critical artifacts preserved in release $VERSION"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Artifact Lifecycle

```
Day 0: Scrape runs, database artifact uploaded (90-day retention)
Day 1-30: Scrape logs available for debugging
Day 7: Temporary artifacts deleted
Day 30: Scrape logs deleted
Day 90: Database artifact deleted (unless preserved in release)
Day 90+: Database still available in GitHub Release (indefinite)
```

## Dependencies

- **Story 08**: Store database artifact (implements upload)

## Implementation Notes

- GitHub Actions retention max is 90 days
- Retention periods are configurable per artifact
- Artifacts auto-delete after retention expires
- Repository admins can delete artifacts manually
- Storage counts against GitHub plan limits
- Consider using releases for long-term storage
- Workflow logs retained 90 days (not configurable)

## Testing Requirements

- [ ] Test artifacts expire after retention period
- [ ] Test storage usage monitoring
- [ ] Test manual cleanup script
- [ ] Verify retention periods are correct
- [ ] Test preservation in releases
- [ ] Check documentation is clear
- [ ] Verify cleanup workflow runs correctly

## Definition of Done

- [ ] Retention periods configured for all artifacts
- [ ] Storage monitoring implemented
- [ ] Cleanup script created
- [ ] Cleanup workflow created (optional)
- [ ] Documentation written
- [ ] Policy documented in README
- [ ] Tested in real environment
- [ ] Code reviewed and approved
