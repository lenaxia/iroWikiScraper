# Story 12: Progress Tracking and Logging

**Epic**: Epic 01  
**Story ID**: epic-01-story-12  
**Priority**: Medium  
**Effort**: 2 days

## User Story
As a user, I want to see scraping progress, so that I know status and estimated completion time.

## Acceptance Criteria
- [ ] Progress bar with tqdm
- [ ] Log every N pages (configurable)
- [ ] Calculate and display ETA
- [ ] Track: pages done, revisions fetched, files downloaded
- [ ] Final summary statistics

## Implementation
```python
from tqdm import tqdm

class ProgressTracker:
    def __init__(self, total_pages: int):
        self.pbar = tqdm(total=total_pages, desc="Pages", unit="page")
        self.stats = {
            "pages": 0,
            "revisions": 0,
            "files": 0,
            "errors": 0
        }
    
    def update_page(self, revision_count: int):
        self.stats["pages"] += 1
        self.stats["revisions"] += revision_count
        self.pbar.update(1)
    
    def summary(self):
        return f"Pages: {self.stats['pages']}, Revisions: {self.stats['revisions']}"
```
