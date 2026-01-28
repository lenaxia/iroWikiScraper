# US-0706: Error Handling and Recovery

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** ✅ Complete  
**Priority:** Medium  
**Story Points:** 5  
**Completed:** 2026-01-24

## User Story

As a user, I need robust error handling that allows scraping to continue despite failures, so that temporary issues don't abort an entire multi-hour scrape.

## Acceptance Criteria

1. **Error Categories**
   - [x] Network errors (timeouts, connection failures)
   - [x] API errors (rate limiting, invalid responses)
   - [x] Database errors (locks, constraint violations)
   - [x] Data validation errors (malformed content)

2. **Namespace-Level Errors**
   - [x] Catch exceptions during namespace discovery
   - [x] Log error with namespace details
   - [x] Continue with remaining namespaces
   - [x] Record failure in ScrapeResult

3. **Page-Level Errors**
   - [x] Catch exceptions during page scraping
   - [x] Log error with page details
   - [x] Continue with remaining pages
   - [x] Record failed page ID in ScrapeResult

4. **Retry Logic**
   - [x] Retry transient errors (network, rate limit)
   - [x] Use exponential backoff for retries
   - [x] Configurable max retries (default: 3)
   - [x] Don't retry permanent errors (404, validation)

5. **Error Reporting**
   - [x] Collect all errors in ScrapeResult
   - [x] Include error type and context
   - [x] Show summary at end of scrape
   - [x] Limit displayed errors (e.g., first 5)

6. **Partial Success**
   - [x] Allow scrape to complete if >90% succeed
   - [x] Return exit code 0 for high success rate
   - [x] Return exit code 1 for low success rate
   - [x] Log warning for partial failures

7. **User Interruption**
   - [x] Handle Ctrl+C (SIGINT) gracefully
   - [x] Log partial progress before exit
   - [x] Return exit code 130 (standard for SIGINT)
   - [x] Don't leave database in inconsistent state

## Technical Details

### Error Handling in FullScraper

```python
def _scrape_revisions(self, pages: List[Page], ...) -> int:
    total_revisions = 0
    
    for page in pages:
        try:
            revisions = self.revision_scraper.fetch_revisions(page.page_id)
            self.revision_repo.insert_revisions_batch(revisions)
            total_revisions += len(revisions)
            
        except TransientError as e:
            # Retry with backoff
            if retry_with_backoff(page.page_id, max_retries=3):
                continue
            else:
                # Give up and record failure
                result.errors.append(f"Page {page.page_id}: {e}")
                result.failed_pages.append(page.page_id)
                
        except PermanentError as e:
            # Don't retry, just record
            logger.error(f"Page {page.page_id} failed: {e}")
            result.errors.append(f"Page {page.page_id}: {e}")
            result.failed_pages.append(page.page_id)
            continue
    
    return total_revisions
```

### Retry with Exponential Backoff

```python
def retry_with_backoff(
    operation: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> bool:
    """Retry operation with exponential backoff.
    
    Returns:
        True if operation succeeded, False if all retries exhausted
    """
    for attempt in range(max_retries):
        try:
            operation()
            return True
        except TransientError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}")
                time.sleep(delay)
            else:
                logger.error(f"All retries exhausted: {e}")
                return False
```

### Error Classification

```python
# Transient errors (retry)
- requests.exceptions.Timeout
- requests.exceptions.ConnectionError
- APIRateLimitError (429)
- sqlite3.OperationalError (database locked)

# Permanent errors (don't retry)
- APIResponseError (invalid data structure)
- ValueError (data validation)
- 404 Not Found
```

### Exit Code Logic

```python
if result.success:
    return 0
else:
    failure_rate = len(result.failed_pages) / result.pages_count
    if failure_rate > 0.1:  # More than 10% failed
        return 1
    else:
        return 0  # Partial success is acceptable
```

## Dependencies

- `scraper.api.exceptions` (API error types)
- `time` module for backoff delays
- `logging` for error reporting

## Testing Requirements

- [x] Test namespace failure continues with other namespaces
- [x] Test page failure continues with other pages
- [x] Test retry logic with transient errors
- [x] Test no retry for permanent errors
- [x] Test exponential backoff timing
- [x] Test KeyboardInterrupt handling
- [x] Test error collection in ScrapeResult
- [x] Test exit code logic for different failure rates

## Documentation

- [x] Document error handling strategy in code
- [x] Document retry logic in README
- [x] Document exit codes in README
- [x] Document transient vs permanent errors

## Notes

- Scraping 2400+ pages can take hours - must handle transient failures
- Database transactions should be per-batch to avoid loss
- User should be able to Ctrl+C without corrupting database
- Error summary helps user understand what went wrong

---

## Implementation Summary

**Completed:** 2026-01-24  
**Test Results:** ✅ 87/87 tests passing

### Files Created
1. `scraper/orchestration/retry.py` - Retry logic with exponential backoff
2. `tests/test_error_handling.py` - 19 comprehensive tests

### Files Modified
1. `scraper/orchestration/full_scraper.py` - Integrated retry logic
2. `tests/orchestration/test_full_scraper.py` - Updated test expectations
3. `tests/orchestration/test_full_scraper_integration.py` - Updated test expectations

### Key Features
- Error classification (transient vs permanent)
- Retry with exponential backoff (1s, 2s, 4s)
- Namespace-level error recovery
- Page-level error recovery
- Partial success handling (>90% success = exit 0)
- Graceful user interruption (Ctrl+C = exit 130)
- Comprehensive error reporting with context

### Validation
See `US-0706-validation-report.md` for detailed validation results.
