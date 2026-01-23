# Story 11: Checkpoint and Resume

**Epic**: Epic 01  
**Story ID**: epic-01-story-11  
**Priority**: High  
**Effort**: 2-3 days

## User Story
As a scraper developer, I want checkpoint/resume capability, so that scraping can recover from interruptions.

## Acceptance Criteria
- [ ] Save checkpoint after every N pages (default 10)
- [ ] Checkpoint stores: completed_page_ids, current_phase, timestamp
- [ ] On startup, load checkpoint if exists
- [ ] Skip already completed pages
- [ ] Clear checkpoint on successful completion

## Implementation
```python
class Checkpoint:
    def __init__(self, checkpoint_file: str):
        self.file = Path(checkpoint_file)
        self.state = self._load()
    
    def _load(self):
        if self.file.exists():
            with open(self.file) as f:
                return json.load(f)
        return {"completed_pages": [], "current_phase": "init"}
    
    def save(self, state):
        with open(self.file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def mark_complete(self, page_id):
        self.state["completed_pages"].append(page_id)
        if len(self.state["completed_pages"]) % 10 == 0:
            self.save(self.state)
```
