# Epic 03: Incremental Updates

**Epic ID**: epic-03  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 1-2 weeks

## Overview

Implement incremental update capability to efficiently capture only new changes since the last scrape. This enables monthly automated updates without re-scraping the entire wiki, reducing bandwidth and time from days to hours.

## Goals

1. Track last scrape timestamp for incremental runs
2. Query MediaWiki's recentchanges API for delta detection
3. Fetch only new/modified pages since last scrape
4. Fetch only new revisions on existing pages
5. Download only new/modified files
6. Verify integrity after incremental updates
7. Support fallback to full scrape if needed

## Success Criteria

- ✅ Incremental update completes in <4 hours (vs 24-48 hours full scrape)
- ✅ Only fetches changed content (verify via API call counts)
- ✅ Correctly identifies new pages, new revisions, new files
- ✅ No duplicate data in database
- ✅ Can detect and handle deleted pages
- ✅ Maintains data integrity after incremental runs
- ✅ 80%+ test coverage on incremental logic

## User Stories

### Change Detection
- [Story 01: Recent Changes API Client](story-01_recentchanges_api.md)
- [Story 02: Track Last Scrape Timestamp](story-02_track_timestamp.md)
- [Story 03: Detect New Pages](story-03_detect_new_pages.md)
- [Story 04: Detect New Revisions](story-04_detect_new_revisions.md)
- [Story 05: Detect New Files](story-05_detect_new_files.md)

### Differential Scraping
- [Story 06: Incremental Page Scraper](story-06_incremental_pages.md)
- [Story 07: Incremental Revision Scraper](story-07_incremental_revisions.md)
- [Story 08: Incremental File Downloader](story-08_incremental_files.md)

### Verification & Integrity
- [Story 09: Verify No Duplicates](story-09_verify_duplicates.md)
- [Story 10: Integrity Checks](story-10_integrity_checks.md)
- [Story 11: Handle Deleted Content](story-11_handle_deletions.md)

### Workflow
- [Story 12: Full vs Incremental Selection](story-12_scrape_mode_selection.md)
- [Story 13: Incremental Run Statistics](story-13_incremental_stats.md)

## Dependencies

### Requires:
- Epic 01: Core scraper (full scrape implementation)
- Epic 02: Database (scrape_runs table for timestamps)

### Blocks:
- Epic 06: Automation (monthly incremental runs)

## Technical Notes

### MediaWiki Recent Changes API

```python
# Query changes since last scrape
api.get_recent_changes(
    start=last_scrape_time,
    end=now,
    limit=500  # Paginate
)

# Response includes:
# - New pages (type='new')
# - Edits (type='edit')
# - Deletions (type='log', log_type='delete')
# - Moves (type='log', log_type='move')
```

### Change Detection Strategy

**New Pages:**
1. Query recentchanges for type='new'
2. Scrape entire page history
3. Insert into database

**Modified Pages:**
1. Query recentchanges for type='edit'
2. Get highest revision ID in database for page
3. Fetch only revisions newer than stored max
4. Insert new revisions

**New Files:**
1. Compare allimages list with files table
2. Check SHA1 hash for modifications
3. Download only new/changed files

**Deletions:**
1. Query recentchanges for type='log', log_type='delete'
2. Mark page as deleted (don't remove from database)
3. Preserve historical data

### Performance Optimization

**Full Scrape:**
- Duration: 24-48 hours
- API calls: ~5,000
- Bandwidth: ~15-25 GB

**Incremental (Monthly):**
- Duration: 2-4 hours
- API calls: ~100-500
- Bandwidth: ~500 MB - 2 GB
- **Speedup: 10-20x faster**

### Fallback Logic

If incremental update fails or data seems inconsistent:
1. Log warning
2. Optionally run full scrape
3. Compare results for discrepancies

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/api/recentchanges_response.json` - Sample recent changes
- `fixtures/api/recentchanges_new_page.json` - New page change
- `fixtures/api/recentchanges_edit.json` - Edit change
- `fixtures/api/recentchanges_delete.json` - Deletion change
- `fixtures/database/pre_incremental.db` - Database before update
- `fixtures/database/post_incremental.db` - Expected after update

### Mocks Needed
- `tests/mocks/mock_incremental_api.py` - Mock recent changes API
- `tests/mocks/mock_timestamp_tracker.py` - Mock timestamp storage

### Test Utilities
- `tests/utils/incremental_helpers.py` - Setup incremental test scenarios
- `tests/utils/db_diff.py` - Compare database states

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |

## Definition of Done

- [ ] All 13 user stories completed
- [ ] Incremental update successfully runs in <4 hours
- [ ] Only changed content fetched (verified)
- [ ] No duplicate data after incremental runs
- [ ] Handles all change types (new, edit, delete, move)
- [ ] All tests passing (80%+ coverage)
- [ ] Fallback to full scrape works
- [ ] Documentation complete (workflow diagrams, examples)
- [ ] Design document created and approved
- [ ] Code reviewed and merged
