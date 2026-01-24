# Story 03: Run Incremental Scrape

**Story ID**: epic-06-story-03  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to execute the scraper with proper configuration and environment  
**So that** the wiki is scraped incrementally and changes are captured

## Acceptance Criteria

1. **Python Environment Setup**
   - [ ] Python 3.11 installed using `actions/setup-python@v5`
   - [ ] Dependencies installed from `requirements.txt`
   - [ ] Scraper package installed in development mode
   - [ ] Environment setup completes in <5 minutes

2. **Scraper Execution**
   - [ ] Scraper runs with incremental mode flag
   - [ ] Configuration loaded from `config.yaml`
   - [ ] Progress logs visible in workflow output
   - [ ] Exit code checked for success/failure

3. **Progress Monitoring**
   - [ ] Scraper output streamed to workflow logs
   - [ ] Progress indicators visible (pages, revisions, files)
   - [ ] Estimated time remaining displayed
   - [ ] Rate limiting logs visible

4. **Error Handling**
   - [ ] Workflow fails if scraper exits with error
   - [ ] Error messages captured in logs
   - [ ] Partial progress saved before failure
   - [ ] Clear error messages for common issues

## Technical Details

### Python Setup

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'  # Cache pip dependencies for faster installs

- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install -e .

- name: Verify installation
  run: |
    python --version
    python -m scraper --version
    python -c "import scraper; print(f'Scraper version: {scraper.__version__}')"
```

### Configuration Setup

```yaml
- name: Create configuration file
  run: |
    cat > config.yaml <<EOF
    # CI/CD Configuration
    base_url: https://irowiki.org
    
    # Database
    database:
      path: data/irowiki.db
      type: sqlite
    
    # Rate limiting
    rate_limit:
      requests_per_second: 2
      burst: 5
      respect_retry_after: true
    
    # Incremental settings
    incremental:
      enabled: true
      lookback_hours: 720  # 30 days
      force_full: false
    
    # Logging
    logging:
      level: INFO
      format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      file: logs/scrape.log
    
    # Timeouts
    timeouts:
      connect: 30
      read: 60
      total: 300
    
    # Retry
    retry:
      max_attempts: 5
      backoff_factor: 2
    EOF
    
    echo "Configuration file created:"
    cat config.yaml
```

### Scraper Execution

```yaml
- name: Run incremental scrape
  id: scrape
  run: |
    # Create necessary directories
    mkdir -p data/ downloads/ logs/
    
    # Determine scrape type
    SCRAPE_TYPE="${{ github.event.inputs.scrape_type || 'incremental' }}"
    echo "Running $SCRAPE_TYPE scrape..."
    
    # Build scraper command
    SCRAPER_CMD="python -m scraper scrape"
    SCRAPER_CMD="$SCRAPER_CMD --config config.yaml"
    SCRAPER_CMD="$SCRAPER_CMD --database data/irowiki.db"
    SCRAPER_CMD="$SCRAPER_CMD --log-level INFO"
    
    if [[ "$SCRAPE_TYPE" == "incremental" ]]; then
      SCRAPER_CMD="$SCRAPER_CMD --incremental"
    else
      SCRAPER_CMD="$SCRAPER_CMD --force-full"
    fi
    
    # Run scraper with output streaming
    echo "Executing: $SCRAPER_CMD"
    $SCRAPER_CMD 2>&1 | tee logs/scrape.log
    
    # Check exit code
    SCRAPE_EXIT_CODE=${PIPESTATUS[0]}
    echo "Scraper exit code: $SCRAPE_EXIT_CODE"
    
    if [[ $SCRAPE_EXIT_CODE -ne 0 ]]; then
      echo "::error::Scraper failed with exit code $SCRAPE_EXIT_CODE"
      exit $SCRAPE_EXIT_CODE
    fi
    
    echo "✓ Scrape completed successfully"
  env:
    PYTHONUNBUFFERED: "1"  # Force unbuffered output for real-time logs

- name: Upload scrape logs
  if: always()  # Upload logs even on failure
  uses: actions/upload-artifact@v4
  with:
    name: scrape-logs-${{ github.run_number }}
    path: logs/
    retention-days: 30
```

### Enhanced Progress Logging

```yaml
- name: Monitor scrape progress
  if: always()
  run: |
    # This runs in background to show periodic progress
    # (In practice, the scraper itself should log progress)
    
    echo "=== Scrape Progress Summary ==="
    
    if [[ -f "data/irowiki.db" ]]; then
      sqlite3 data/irowiki.db <<SQL
.mode column
.headers on

-- Current run statistics
SELECT 
  'Current Run' as source,
  pages_created,
  pages_updated,
  revisions_added,
  files_downloaded
FROM scrape_runs
ORDER BY start_time DESC
LIMIT 1;

-- Overall totals
SELECT
  'Total' as source,
  COUNT(*) as pages_created,
  0 as pages_updated,
  (SELECT COUNT(*) FROM revisions) as revisions_added,
  (SELECT COUNT(*) FROM files) as files_downloaded
FROM pages;
SQL
    else
      echo "Database not available for progress check"
    fi
```

### Error Handling and Diagnostics

```yaml
- name: Diagnose scraper failure
  if: failure() && steps.scrape.outcome == 'failure'
  run: |
    echo "=== Scraper Failure Diagnostics ==="
    
    # Show last 100 lines of log
    echo ""
    echo "Last 100 lines of scrape log:"
    tail -n 100 logs/scrape.log
    
    # Check for common errors
    echo ""
    echo "Checking for common issues..."
    
    if grep -q "Rate limit exceeded" logs/scrape.log; then
      echo "❌ Rate limit exceeded - increase backoff time"
    fi
    
    if grep -q "Connection timeout" logs/scrape.log; then
      echo "❌ Connection timeout - check network or increase timeout"
    fi
    
    if grep -q "Database locked" logs/scrape.log; then
      echo "❌ Database locked - possible concurrent access issue"
    fi
    
    if grep -q "Out of memory" logs/scrape.log; then
      echo "❌ Out of memory - scraper using too much RAM"
    fi
    
    # Check disk space
    echo ""
    echo "Disk space:"
    df -h
    
    # Check database integrity if exists
    if [[ -f "data/irowiki.db" ]]; then
      echo ""
      echo "Database integrity check:"
      sqlite3 data/irowiki.db "PRAGMA integrity_check;" || echo "Database corrupted"
    fi
```

## Dependencies

- **Story 01**: Scheduled workflow trigger
- **Story 02**: Download previous archive
- **Epic 01**: Core scraper implementation
- **Epic 03**: Incremental update system

## Implementation Notes

- Use `PYTHONUNBUFFERED=1` for real-time log output
- Cache pip dependencies to speed up future runs
- Stream output using `tee` to both console and log file
- Check scraper exit code explicitly
- Upload logs even on failure for debugging
- Consider adding progress webhook for long-running scrapes

## Testing Requirements

- [ ] Test with existing database (incremental mode)
- [ ] Test without database (full scrape)
- [ ] Test with corrupted database (should detect and fail)
- [ ] Test with invalid configuration
- [ ] Test scraper error handling (simulate API failure)
- [ ] Test timeout enforcement
- [ ] Verify logs are uploaded on failure
- [ ] Test manual trigger with different scrape types

## Definition of Done

- [ ] Python environment setup implemented
- [ ] Scraper execution step implemented
- [ ] Configuration file generation implemented
- [ ] Progress monitoring implemented
- [ ] Error handling and diagnostics implemented
- [ ] Log upload on failure implemented
- [ ] Tested with both incremental and full scrape
- [ ] Documentation updated
- [ ] Code reviewed and approved
