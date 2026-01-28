# US-0709: Statistics and Reporting

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** Pending  
**Priority:** Low  
**Story Points:** 2

## User Story

As a user, I need detailed statistics about the scrape results, so that I can understand what was archived and track changes over time.

## Acceptance Criteria

1. **Full Scrape Statistics**
   - [ ] Total pages discovered
   - [ ] Total revisions scraped
   - [ ] Breakdown by namespace
   - [ ] Duration (seconds)
   - [ ] Average revisions per page
   - [ ] Failed pages count

2. **Incremental Scrape Statistics**
   - [ ] New pages count
   - [ ] Modified pages count
   - [ ] Deleted pages count
   - [ ] Moved pages count
   - [ ] New revisions count
   - [ ] Files downloaded count
   - [ ] Duration (seconds)

3. **Output Format**
   - [ ] Clear visual separators (=== lines)
   - [ ] Aligned columns
   - [ ] Human-readable numbers
   - [ ] Summary section at end

4. **Error Reporting**
   - [ ] Show failed page count
   - [ ] Show sample of failed page IDs
   - [ ] Show sample of error messages
   - [ ] Indicate if errors truncated

5. **Optional JSON Output**
   - [ ] `--format json` flag for machine-readable output
   - [ ] Include all statistics
   - [ ] Include error details
   - [ ] Valid JSON structure

## Technical Details

### Statistics Output (Full Scrape)

```
============================================================
FULL SCRAPE COMPLETE
============================================================
Pages scraped:     2,400
Revisions scraped: 15,832
Average revs/page: 6.6
Duration:          245.3s (4m 5s)
Rate:              9.8 pages/sec

Breakdown by namespace:
  0 (Main):        1,842 pages    12,431 revisions
  4 (Project):       234 pages     1,205 revisions
  6 (File):          156 pages       892 revisions
  10 (Template):     102 pages       814 revisions
  14 (Category):      66 pages       490 revisions

Failed pages:      3 (0.1%)
  IDs: 142, 589, 1023

Errors (first 3 of 3):
  - Page 142: Connection timeout after 3 retries
  - Page 589: Invalid revision data structure
  - Page 1023: API rate limit exceeded
============================================================
```

### Statistics Output (Incremental Scrape)

```
============================================================
INCREMENTAL SCRAPE COMPLETE
============================================================
Changes detected:
  New pages:         12
  Modified pages:    47
  Deleted pages:     3
  Moved pages:       2

Data updated:
  Revisions added:   89
  Files downloaded:  5

Total affected:    64 pages
Duration:          18.7s
Rate:              3.4 pages/sec
============================================================
```

### JSON Output Format

```json
{
  "scrape_type": "full",
  "success": true,
  "timestamp": "2025-01-24T10:04:05Z",
  "duration_seconds": 245.3,
  "statistics": {
    "pages_count": 2400,
    "revisions_count": 15832,
    "average_revisions_per_page": 6.6,
    "rate_pages_per_second": 9.8,
    "namespaces": {
      "0": {"pages": 1842, "revisions": 12431},
      "4": {"pages": 234, "revisions": 1205},
      ...
    }
  },
  "errors": {
    "count": 3,
    "failed_pages": [142, 589, 1023],
    "messages": [
      "Page 142: Connection timeout",
      ...
    ]
  }
}
```

## Dependencies

- `ScrapeResult` from FullScraper (US-0701)
- `IncrementalStats` from IncrementalPageScraper
- `json` module for JSON output

## Testing Requirements

- [ ] Test full scrape statistics formatting
- [ ] Test incremental scrape statistics formatting
- [ ] Test JSON output is valid JSON
- [ ] Test statistics calculated correctly
- [ ] Test error messages are truncated appropriately
- [ ] Test namespace breakdown calculation

## Documentation

- [ ] Document statistics output in README
- [ ] Document JSON format in README
- [ ] Add examples to README

## Notes

- Statistics help users understand scrape completeness
- JSON output useful for monitoring/alerting systems
- Consider adding stats command to query existing database
