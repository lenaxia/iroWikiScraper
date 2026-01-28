# US-0705: Progress Tracking and Logging

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** Complete  
**Priority:** Medium  
**Story Points:** 3

## User Story

As a user, I need clear progress updates during long-running scrapes, so that I can understand what's happening and estimate time remaining.

## Acceptance Criteria

1. **Progress Display**
   - [x] Show current stage (discover, scrape, etc.)
   - [x] Show current/total counts
   - [x] Show percentage complete
   - [x] Update in place (same line) for cleaner output
   - [x] Suppressed when `--quiet` flag is used

2. **Logging Levels**
   - [x] DEBUG: Detailed component-level logging
   - [x] INFO: Progress updates, major milestones (default)
   - [x] WARNING: Recoverable errors, retries
   - [x] ERROR: Failed operations, critical issues
   - [x] CRITICAL: Fatal errors requiring termination

3. **Stage Tracking**
   - [x] "discover" - Page discovery phase
   - [x] "scrape" - Revision scraping phase
   - [x] Clear start/end markers for each phase

4. **Progress Updates**
   - [x] Update every N items (configurable)
   - [x] Always show first and last update
   - [x] Show percentage with 1 decimal place
   - [x] Include timing information where helpful

5. **Summary Output**
   - [x] Print summary at completion
   - [x] Include total counts
   - [x] Include duration
   - [x] Include error count (if any)

## Technical Details

### Progress Callback

```python
def _print_progress(stage: str, current: int, total: int) -> None:
    """Print progress update.
    
    Args:
        stage: Stage name (discover, scrape, etc.)
        current: Current item number
        total: Total items
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"[{stage}] {current}/{total} ({percentage:.1f}%)", flush=True)
```

### Logging Configuration

```python
def _setup_logging(log_level: str) -> None:
    """Configure logging for CLI."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
```

### Example Output (Verbose)

```
2025-01-24 10:00:00 - scraper.cli - INFO - Starting full scrape
2025-01-24 10:00:00 - scraper.orchestration - INFO - Discovering pages in namespace 0
[discover] 1/5 (20.0%)
[discover] 2/5 (40.0%)
[discover] 3/5 (60.0%)
[discover] 4/5 (80.0%)
[discover] 5/5 (100.0%)
2025-01-24 10:00:15 - scraper.orchestration - INFO - Discovered 2400 pages
[scrape] 100/2400 (4.2%)
[scrape] 200/2400 (8.3%)
...
[scrape] 2400/2400 (100.0%)
2025-01-24 10:04:05 - scraper.orchestration - INFO - Scraped 15832 revisions
```

### Example Output (Quiet)

```
Starting full scrape...
Namespaces: [0, 4, 6, 10, 14]

============================================================
FULL SCRAPE COMPLETE
============================================================
Pages scraped:     2400
Revisions scraped: 15832
Duration:          245.3s
============================================================
```

## Dependencies

- `logging` module (Python standard library)
- Progress callback in FullScraper (US-0701)

## Testing Requirements

- [x] Test progress callback is called at correct intervals
- [x] Test --quiet suppresses progress output
- [x] Test log levels filter messages correctly
- [x] Test progress percentages calculated correctly
- [x] Test summary output is formatted correctly

## Documentation

- [x] Docstring for _print_progress()
- [x] Docstring for _setup_logging()
- [ ] README section on progress output
- [ ] README section on log levels

## Notes

- Progress updates help users understand long operations aren't frozen
- --quiet mode useful for cron jobs or CI/CD pipelines
- Log levels allow debugging without overwhelming normal users
- Consider terminal width for progress display
