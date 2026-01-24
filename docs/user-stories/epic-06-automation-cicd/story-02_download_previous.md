# Story 02: Download Previous Archive

**Story ID**: epic-06-story-02  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to download the database from the previous scrape run  
**So that** I can perform incremental updates instead of full scrapes

## Acceptance Criteria

1. **Artifact Download**
   - [ ] Download previous database artifact from GitHub Actions
   - [ ] Use `actions/download-artifact@v4` action
   - [ ] Download to correct path (`data/irowiki.db`)
   - [ ] Handle missing artifact gracefully (first run)

2. **Error Handling**
   - [ ] `continue-on-error: true` for missing artifacts
   - [ ] Log clear message when artifact not found
   - [ ] Log success message when artifact downloaded
   - [ ] Workflow continues regardless of download status

3. **Fallback Behavior**
   - [ ] If artifact not found, log warning and proceed
   - [ ] Scraper detects missing database and runs full scrape
   - [ ] First monthly run handles missing artifact correctly
   - [ ] No manual intervention required for first run

4. **Artifact Validation**
   - [ ] Check downloaded file exists after download
   - [ ] Verify file is not empty (size > 0)
   - [ ] Log artifact metadata (size, age)
   - [ ] Warn if artifact is very old (>90 days)

## Technical Details

### Download Artifact Step

```yaml
- name: Download previous database artifact
  id: download-artifact
  uses: actions/download-artifact@v4
  with:
    name: irowiki-database
    path: data/
  continue-on-error: true

- name: Check artifact download status
  run: |
    if [[ -f "data/irowiki.db" ]]; then
      echo "✓ Previous database found"
      ls -lh data/irowiki.db
      
      # Check file size
      FILE_SIZE=$(stat -f%z "data/irowiki.db" 2>/dev/null || stat -c%s "data/irowiki.db")
      echo "Database size: $(numfmt --to=iec-i --suffix=B $FILE_SIZE)"
      
      # Check if SQLite database is valid
      if sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages;" 2>/dev/null; then
        echo "✓ Database is valid SQLite file"
      else
        echo "⚠ Database file exists but may be corrupted"
        mv data/irowiki.db data/irowiki.db.backup
        echo "Moved to backup, will run full scrape"
      fi
    else
      echo "⚠ No previous database found - will run full scrape"
      echo "This is expected for the first run"
    fi

- name: Create data directory if needed
  run: |
    mkdir -p data/
    mkdir -p downloads/
```

### Alternative: Download from GitHub Release

If artifacts are too large or expired, download from latest release:

```yaml
- name: Download database from latest release
  if: steps.download-artifact.outcome == 'failure'
  run: |
    echo "Artifact not found, checking latest release..."
    
    # Get latest release
    LATEST_RELEASE=$(gh release list --limit 1 --json tagName --jq '.[0].tagName')
    
    if [[ -n "$LATEST_RELEASE" ]]; then
      echo "Found release: $LATEST_RELEASE"
      
      # Download database from release
      gh release download "$LATEST_RELEASE" \
        --pattern "irowiki-database.tar.gz" \
        --dir data/ || true
      
      if [[ -f "data/irowiki-database.tar.gz" ]]; then
        echo "Extracting database..."
        tar -xzf data/irowiki-database.tar.gz -C data/
        echo "✓ Database restored from release"
      else
        echo "⚠ No database in release, will run full scrape"
      fi
    else
      echo "⚠ No releases found, will run full scrape"
    fi
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Artifact Metadata Logging

```yaml
- name: Log artifact metadata
  if: hashFiles('data/irowiki.db') != ''
  run: |
    echo "=== Database Artifact Information ==="
    echo "File: data/irowiki.db"
    echo "Size: $(du -h data/irowiki.db | cut -f1)"
    echo "Modified: $(stat -c %y data/irowiki.db 2>/dev/null || stat -f %Sm data/irowiki.db)"
    
    # Count records
    echo ""
    echo "=== Database Contents ==="
    sqlite3 data/irowiki.db <<SQL
.mode column
.headers on
SELECT 
  'Pages' as entity, 
  COUNT(*) as count 
FROM pages
UNION ALL
SELECT 
  'Revisions', 
  COUNT(*) 
FROM revisions
UNION ALL
SELECT 
  'Files', 
  COUNT(*) 
FROM files;
SQL
    
    # Get last scrape info
    echo ""
    echo "=== Last Scrape Run ==="
    sqlite3 data/irowiki.db <<SQL
SELECT 
  run_id,
  start_time,
  end_time,
  status,
  pages_created,
  pages_updated,
  revisions_added
FROM scrape_runs
ORDER BY start_time DESC
LIMIT 1;
SQL
```

## Dependencies

- **Story 01**: Scheduled workflow trigger (must run first)
- **Epic 03**: Incremental update system (database schema)
- **Story 08**: Store database artifact (creates artifacts to download)

## Implementation Notes

- First run will always fail to download artifact (expected)
- `continue-on-error: true` prevents workflow failure
- Artifact retention is 90 days by default
- After 90 days, artifact expires and full scrape runs
- Alternative: Store database in release for longer retention
- GitHub Actions artifacts are repo-scoped (not public)

## Testing Requirements

- [ ] Test with no previous artifact (first run)
- [ ] Test with valid previous artifact
- [ ] Test with corrupted artifact file
- [ ] Test with expired artifact (>90 days)
- [ ] Test artifact download from release fallback
- [ ] Verify database validation works
- [ ] Test data directory creation
- [ ] Check log output is clear and helpful

## Definition of Done

- [ ] Artifact download step added to workflow
- [ ] Error handling implemented
- [ ] Fallback to release download implemented
- [ ] Artifact validation implemented
- [ ] Database integrity check implemented
- [ ] Metadata logging implemented
- [ ] Tested with and without previous artifact
- [ ] Documentation updated
- [ ] Code reviewed and approved
