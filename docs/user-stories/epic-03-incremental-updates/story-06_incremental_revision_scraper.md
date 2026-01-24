# Story 06: Incremental Revision Scraper

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-06  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to fetch only new revisions for modified pages**,  
So that **I avoid re-scraping the entire revision history unnecessarily**.

## Description

Implement an incremental revision scraper that fetches only revisions created since the last scrape for a given page. Uses the highest_revision_id from the database to request only newer revisions from the API.

This is the core efficiency gain of incremental updates: instead of fetching 100 revisions, fetch only the 1-2 new ones.

## Acceptance Criteria

### 1. IncrementalRevisionScraper Class
- [ ] Create `scraper/incremental/revision_scraper.py`
- [ ] Accepts `APIClient`, `Database`
- [ ] Reuses existing revision parsing logic
- [ ] Handles pagination for new revisions

### 2. Fetch New Revisions Method
- [ ] Implement `fetch_new_revisions(page_update_info: PageUpdateInfo) -> List[Revision]`
- [ ] Uses `rvstartid` parameter to fetch only newer revisions
- [ ] Returns list of new Revision objects
- [ ] Handles case where no new revisions exist

### 3. Batch Fetch Method
- [ ] Implement `fetch_new_revisions_batch(infos: List[PageUpdateInfo]) -> Dict[int, List[Revision]]`
- [ ] Efficiently fetches revisions for multiple pages
- [ ] Returns dict mapping page_id to list of new revisions
- [ ] Respects rate limiting

### 4. Revision Deduplication
- [ ] Check revision_id doesn't already exist before inserting
- [ ] Handle edge case of revision already scraped by another process
- [ ] Log warnings for duplicate revisions
- [ ] Skip duplicates silently (idempotent operation)

### 5. Database Integration
- [ ] Insert new revisions using existing database methods
- [ ] Update page.updated_at timestamp
- [ ] Maintain referential integrity
- [ ] Use transactions for atomic updates

### 6. API Query Optimization
- [ ] Use `rvstartid` to fetch revisions after highest known ID
- [ ] Use `rvdir=newer` to get chronological order
- [ ] Limit results per page (rvlimit=500)
- [ ] Follow continuation tokens

### 7. Error Handling
- [ ] Handle page not found (may have been deleted)
- [ ] Handle API errors gracefully
- [ ] Retry transient failures
- [ ] Log failed pages for manual review

### 8. Testing Requirements
- [ ] Test fetch with 1 new revision
- [ ] Test fetch with multiple new revisions
- [ ] Test fetch with no new revisions (edge case)
- [ ] Test deduplication logic
- [ ] Test batch fetching
- [ ] Test coverage: 80%+

## Technical Implementation

```python
class IncrementalRevisionScraper:
    def __init__(self, api_client, database):
        self.api = api_client
        self.db = database
        self.revision_parser = RevisionParser()
    
    def fetch_new_revisions(self, info: PageUpdateInfo) -> List[Revision]:
        """Fetch revisions newer than highest_revision_id."""
        params = {
            'pageids': info.page_id,
            'prop': 'revisions',
            'rvprop': 'ids|timestamp|user|userid|comment|content|sha1|size',
            'rvstartid': info.highest_revision_id + 1,
            'rvdir': 'newer',
            'rvlimit': 500
        }
        
        revisions = []
        while True:
            response = self.api.query(params)
            
            # Parse revisions
            page_data = response['query']['pages'][str(info.page_id)]
            if 'revisions' not in page_data:
                break
            
            for rev_data in page_data['revisions']:
                rev = self.revision_parser.parse(rev_data, info.page_id)
                revisions.append(rev)
            
            # Check for continuation
            if 'continue' not in response:
                break
            params.update(response['continue'])
        
        return revisions
```

## Dependencies

### Requires
- Epic 01, Story 05: Revision Scraping
- Epic 03, Story 03: Modified Page Detection

### Blocks
- Story 05: Incremental Page Scraper

## Definition of Done

- [ ] IncrementalRevisionScraper implemented
- [ ] All tests passing (80%+ coverage)
- [ ] Handles edge cases correctly
- [ ] Efficient API usage verified
- [ ] Code reviewed and merged
