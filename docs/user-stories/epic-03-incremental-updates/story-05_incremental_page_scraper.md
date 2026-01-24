# Story 05: Incremental Page Scraper

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-05  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 3-4 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to scrape only changed pages during incremental updates**,  
So that **I can efficiently update the database without re-fetching unchanged content**.

## Description

Implement the incremental page scraper that coordinates new page detection and modified page detection to scrape only what's changed. This is the orchestrator that uses ChangeSet data to perform targeted scraping operations.

For new pages, perform full scrapes. For modified pages, fetch only new revisions. For deleted pages, mark as deleted without fetching.

## Background & Context

**Incremental Page Scraping Flow:**
1. Get ChangeSet from ChangeDetector
2. For new pages: Full scrape (all revisions)
3. For modified pages: Incremental scrape (new revisions only)
4. For deleted pages: Mark as deleted
5. For moved pages: Update title, check for new revisions
6. Update scrape_runs metadata

**Why This Story Matters:**
- Core of incremental efficiency
- Orchestrates all detection logic
- Dramatically reduces scraping time
- Foundation for automation

## Acceptance Criteria

### 1. IncrementalPageScraper Class
- [ ] Create `scraper/incremental/page_scraper.py`
- [ ] Accepts `Database`, `APIClient`, scraper components
- [ ] Orchestrates incremental scraping workflow
- [ ] Creates scrape_run record before starting

### 2. Main Scrape Method
- [ ] Implement `scrape_incremental() -> IncrementalStats`
- [ ] Gets ChangeSet from ChangeDetector
- [ ] Falls back to full scrape if first run
- [ ] Processes new pages (full scrape)
- [ ] Processes modified pages (incremental revisions)
- [ ] Processes deleted pages (mark as deleted)
- [ ] Processes moved pages (update title)
- [ ] Returns statistics

### 3. New Page Processing
- [ ] Verify pages are genuinely new
- [ ] Scrape complete page history using existing PageScraper
- [ ] Insert page + all revisions
- [ ] Insert links for page
- [ ] Log progress

### 4. Modified Page Processing
- [ ] Get PageUpdateInfo for each modified page
- [ ] Fetch revisions newer than highest_revision_id
- [ ] Insert new revisions only
- [ ] Update page metadata (updated_at)
- [ ] Re-extract and update links
- [ ] Log progress

### 5. Deleted Page Handling
- [ ] Mark page as deleted (add is_deleted flag)
- [ ] Preserve all historical data
- [ ] Don't fetch from API
- [ ] Log deletions

### 6. Moved Page Handling
- [ ] Update page title in database
- [ ] Check if content changed
- [ ] Fetch new revisions if content changed
- [ ] Log moves

### 7. Progress Tracking
- [ ] Log start of incremental scrape
- [ ] Log progress for each page type
- [ ] Show progress bars (optional, use tqdm)
- [ ] Log statistics at end

### 8. Error Handling
- [ ] Handle API errors gracefully
- [ ] Continue on single page failures
- [ ] Log failed pages for retry
- [ ] Mark scrape_run as 'partial' if errors
- [ ] Save checkpoint frequently

### 9. Scrape Run Metadata
- [ ] Create scrape_run at start
- [ ] Update statistics during scrape
- [ ] Mark as 'completed' at end
- [ ] Mark as 'failed' if critical error
- [ ] Store start_time, end_time, statistics

### 10. IncrementalStats Data Model
- [ ] Create dataclass with: pages_new, pages_modified, pages_deleted
- [ ] Fields: revisions_added, duration, api_calls
- [ ] Property: total_pages_affected
- [ ] Method: to_dict() for logging

### 11. Testing Requirements
- [ ] Test infrastructure: Full test database with pages/revisions
- [ ] Unit test: Process new pages
- [ ] Unit test: Process modified pages
- [ ] Unit test: Process deleted pages
- [ ] Unit test: Process moved pages
- [ ] Integration test: Full incremental workflow
- [ ] Test coverage: 80%+

## Technical Details

### IncrementalStats Model

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class IncrementalStats:
    """Statistics from an incremental scrape run."""
    pages_new: int = 0
    pages_modified: int = 0
    pages_deleted: int = 0
    pages_moved: int = 0
    revisions_added: int = 0
    start_time: datetime = None
    end_time: datetime = None
    api_calls: int = 0
    
    @property
    def total_pages_affected(self) -> int:
        return self.pages_new + self.pages_modified + self.pages_deleted + self.pages_moved
    
    @property
    def duration(self) -> timedelta:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return timedelta(0)
    
    def to_dict(self) -> dict:
        return {
            'pages_new': self.pages_new,
            'pages_modified': self.pages_modified,
            'pages_deleted': self.pages_deleted,
            'pages_moved': self.pages_moved,
            'revisions_added': self.revisions_added,
            'duration_seconds': self.duration.total_seconds(),
            'api_calls': self.api_calls
        }
```

### Implementation Skeleton

```python
class IncrementalPageScraper:
    def __init__(self, db, api_client, page_scraper, revision_scraper):
        self.db = db
        self.api = api_client
        self.page_scraper = page_scraper
        self.revision_scraper = revision_scraper
        self.change_detector = ChangeDetector(db, RecentChangesClient(api_client))
        self.new_detector = NewPageDetector(db)
        self.modified_detector = ModifiedPageDetector(db)
    
    def scrape_incremental(self) -> IncrementalStats:
        stats = IncrementalStats(start_time=datetime.now())
        
        # Detect changes
        changes = self.change_detector.detect_changes()
        if changes.requires_full_scrape:
            raise FullScrapeRequiredError()
        
        # Create scrape_run
        run_id = self.db.create_scrape_run('incremental', 'running')
        
        try:
            # Process new pages
            stats.pages_new = self._process_new_pages(changes.new_page_ids)
            
            # Process modified pages
            stats.pages_modified, stats.revisions_added = self._process_modified_pages(
                changes.modified_page_ids
            )
            
            # Process deletions
            stats.pages_deleted = self._process_deleted_pages(changes.deleted_page_ids)
            
            # Mark run complete
            stats.end_time = datetime.now()
            self.db.update_scrape_run(run_id, 'completed', stats.to_dict())
            
        except Exception as e:
            self.db.update_scrape_run(run_id, 'failed')
            raise
        
        return stats
```

## Dependencies

### Requires
- Epic 01: All scraper stories (PageScraper, RevisionScraper)
- Epic 03, Story 01-04: All detection stories
- Epic 02: Database operations

### Blocks
- Story 11: Scrape Run Metadata
- Story 13: Incremental Update Testing
- Epic 06: Automation

## Definition of Done

- [ ] All acceptance criteria met
- [ ] IncrementalPageScraper class implemented
- [ ] All page types processed correctly
- [ ] Statistics tracked and returned
- [ ] All tests passing (80%+ coverage)
- [ ] Integration test with full workflow
- [ ] Error handling tested
- [ ] Code reviewed
- [ ] Merged to main branch

## References

- Epic 03 README
- Stories 01-04 (detection logic)
- Epic 01 (core scrapers)
