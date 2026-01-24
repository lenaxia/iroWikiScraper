# Story 11: Scrape Run Metadata

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-11  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1-2 days  
**Assignee**: TBD

## User Story

As a **system operator**,  
I want **detailed metadata about each scrape run**,  
So that **I can track performance trends and diagnose issues**.

## Description

Enhance scrape_runs table to store comprehensive metadata about each incremental update, including statistics, duration, API call counts, and any errors encountered. This provides audit trail and performance monitoring.

## Acceptance Criteria

### 1. Enhanced scrape_runs Schema
- [ ] Add column: `pages_new` (INT)
- [ ] Add column: `pages_modified` (INT)
- [ ] Add column: `pages_deleted` (INT)
- [ ] Add column: `revisions_added` (INT)
- [ ] Add column: `files_downloaded` (INT)
- [ ] Add column: `api_calls` (INT)
- [ ] Add column: `duration_seconds` (REAL)
- [ ] Add column: `error_message` (TEXT)

### 2. Statistics Collection
- [ ] Count pages processed by type
- [ ] Count revisions added
- [ ] Count files downloaded
- [ ] Count API calls made
- [ ] Calculate duration

### 3. Metadata Storage
- [ ] Store statistics at scrape run completion
- [ ] Store error message on failure
- [ ] Store start_time and end_time
- [ ] Calculate and store duration

### 4. Query Methods
- [ ] Implement `get_scrape_run_history(limit=10)`
- [ ] Implement `get_scrape_run_statistics(run_id)`
- [ ] Implement `get_recent_errors()`

### 5. Visualization Data
- [ ] Method to get statistics for plotting
- [ ] Trend data: pages per run, duration per run
- [ ] Success rate over time

### 6. Testing Requirements
- [ ] Test metadata storage
- [ ] Test query methods
- [ ] Test statistics calculation
- [ ] Test coverage: 80%+

## Technical Implementation

```python
class ScrapeRunMetadata:
    def store_run_metadata(self, run_id: int, stats: IncrementalStats):
        """Store comprehensive scrape run metadata."""
        query = """
            UPDATE scrape_runs
            SET pages_new = ?,
                pages_modified = ?,
                pages_deleted = ?,
                revisions_added = ?,
                files_downloaded = ?,
                api_calls = ?,
                duration_seconds = ?,
                status = 'completed',
                end_time = CURRENT_TIMESTAMP
            WHERE run_id = ?
        """
        self.db.execute(query, (
            stats.pages_new,
            stats.pages_modified,
            stats.pages_deleted,
            stats.revisions_added,
            stats.files_downloaded,
            stats.api_calls,
            stats.duration.total_seconds(),
            run_id
        ))
    
    def get_scrape_run_history(self, limit: int = 10):
        """Get recent scrape run history."""
        query = """
            SELECT run_id, run_type, status,
                   start_time, end_time, duration_seconds,
                   pages_new, pages_modified, pages_deleted,
                   revisions_added, files_downloaded, api_calls
            FROM scrape_runs
            ORDER BY start_time DESC
            LIMIT ?
        """
        return self.db.execute(query, (limit,)).fetchall()
```

## Dependencies

### Requires
- Epic 02, Story 05: Scrape Metadata Schema
- Epic 03, Story 09: Last Scrape Timestamp Tracking

### Blocks
- Epic 06: Automation (uses statistics)

## Definition of Done

- [ ] Enhanced schema implemented
- [ ] Metadata storage working
- [ ] Query methods implemented
- [ ] All tests passing (80%+ coverage)
- [ ] Code reviewed and merged
