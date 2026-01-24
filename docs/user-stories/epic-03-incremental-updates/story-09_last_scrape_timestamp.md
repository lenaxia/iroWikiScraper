# Story 09: Last Scrape Timestamp Tracking

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-09  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to track when the last successful scrape completed**,  
So that **I know the starting point for incremental updates**.

## Description

Implement methods to store and retrieve the last successful scrape timestamp from the `scrape_runs` table. This timestamp is critical for incremental updates—it determines which changes to fetch from the recent changes API.

## Acceptance Criteria

### 1. Get Last Scrape Timestamp Method
- [ ] Implement `get_last_scrape_timestamp() -> Optional[datetime]`
- [ ] Queries `scrape_runs` table for most recent completed run
- [ ] Returns `end_time` of last successful scrape
- [ ] Returns `None` if no completed scrapes exist

### 2. Set Last Scrape Timestamp Method
- [ ] Implement `set_last_scrape_timestamp(timestamp: datetime)`
- [ ] Updates current scrape_run record's end_time
- [ ] Marks run as 'completed'
- [ ] Atomic operation

### 3. Scrape Run Creation
- [ ] Implement `create_scrape_run(run_type: str) -> int`
- [ ] Inserts new row in scrape_runs table
- [ ] Returns run_id for later updates
- [ ] Sets status to 'running'
- [ ] Records start_time automatically

### 4. Scrape Run Completion
- [ ] Implement `complete_scrape_run(run_id: int, stats: dict)`
- [ ] Updates scrape_run with statistics
- [ ] Sets end_time to current timestamp
- [ ] Sets status to 'completed'
- [ ] Stores pages_scraped, revisions_scraped, etc.

### 5. Scrape Run Failure Handling
- [ ] Implement `fail_scrape_run(run_id: int, error: str)`
- [ ] Sets status to 'failed'
- [ ] Records error message
- [ ] Sets end_time
- [ ] Does NOT update last_scrape_timestamp (failed runs don't count)

### 6. Query Optimization
- [ ] Index on `status` column for filtering
- [ ] Index on `end_time` for ordering
- [ ] Query uses ORDER BY end_time DESC LIMIT 1
- [ ] Query performance: <5ms

### 7. Testing Requirements
- [ ] Test get timestamp with no runs
- [ ] Test get timestamp with completed runs
- [ ] Test get timestamp ignores failed runs
- [ ] Test create/complete/fail scrape run
- [ ] Test coverage: 85%+

## Technical Implementation

```python
class ScrapeRunTracker:
    def __init__(self, database):
        self.db = database
    
    def get_last_scrape_timestamp(self) -> Optional[datetime]:
        """Get timestamp of last successful scrape."""
        query = """
            SELECT end_time
            FROM scrape_runs
            WHERE status = 'completed'
            ORDER BY end_time DESC
            LIMIT 1
        """
        result = self.db.execute(query).fetchone()
        return result[0] if result else None
    
    def create_scrape_run(self, run_type: str) -> int:
        """Create new scrape run record."""
        query = """
            INSERT INTO scrape_runs (run_type, status, start_time)
            VALUES (?, 'running', CURRENT_TIMESTAMP)
        """
        cursor = self.db.execute(query, (run_type,))
        return cursor.lastrowid
    
    def complete_scrape_run(self, run_id: int, stats: dict):
        """Mark scrape run as completed."""
        query = """
            UPDATE scrape_runs
            SET status = 'completed',
                end_time = CURRENT_TIMESTAMP,
                pages_scraped = ?,
                revisions_scraped = ?,
                files_downloaded = ?
            WHERE run_id = ?
        """
        self.db.execute(query, (
            stats.get('pages', 0),
            stats.get('revisions', 0),
            stats.get('files', 0),
            run_id
        ))
    
    def fail_scrape_run(self, run_id: int, error: str):
        """Mark scrape run as failed."""
        query = """
            UPDATE scrape_runs
            SET status = 'failed',
                end_time = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE run_id = ?
        """
        self.db.execute(query, (error, run_id))
```

## Dependencies

### Requires
- Epic 02, Story 05: Scrape Metadata Schema

### Blocks
- Story 02: Change Detection Logic
- Story 05: Incremental Page Scraper

## Definition of Done

- [ ] ScrapeRunTracker class implemented
- [ ] All methods working correctly
- [ ] All tests passing (85%+ coverage)
- [ ] Query performance verified
- [ ] Code reviewed and merged
