# Story 05: Revision History Scraping

**Epic**: Epic 01 - Core Scraper  
**Story ID**: epic-01-story-05  
**Priority**: High  
**Effort**: 3-4 days

## User Story
As a scraper developer, I want to fetch complete revision history for each page, so that all historical edits are preserved.

## Description
Implement revision history scraping using MediaWiki's revisions API. Fetch ALL revisions for a page with full metadata (timestamp, user, comment, content).

## Acceptance Criteria
- [ ] Method fetch_revisions(page_id) returns all revisions
- [ ] Handles pagination (rvlimit=500, rvcontinue)
- [ ] Returns Revision objects with: revid, timestamp, user, comment, content, sha1
- [ ] Stores complete wikitext content
- [ ] Handles missing users (deleted accounts)

## Key Implementation
```python
@dataclass
class Revision:
    revision_id: int
    page_id: int
    parent_id: Optional[int]
    timestamp: datetime
    user: str
    user_id: Optional[int]
    comment: str
    content: str
    sha1: str
    size: int

def fetch_revisions(page_id: int) -> List[Revision]:
    revisions = []
    continue_token = None
    
    while True:
        params = {
            'prop': 'revisions',
            'pageids': page_id,
            'rvprop': 'ids|timestamp|user|userid|comment|content|sha1|size',
            'rvlimit': 500,
            'rvdir': 'newer'  # oldest first
        }
        if continue_token:
            params.update(continue_token)
        
        response = self.api.query(params)
        # ... parse and create Revision objects
```

## Testing
- Test single revision page
- Test multi-revision page (>500)
- Test deleted user handling
- Test pagination

Dependencies: Story 04 (Page Discovery)
