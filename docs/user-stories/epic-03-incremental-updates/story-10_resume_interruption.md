# Story 10: Resume After Interruption

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-10  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to resume incremental scrapes after interruptions**,  
So that **network failures or crashes don't require restarting from the beginning**.

## Description

Extend the checkpoint system from Epic 01 to support incremental scrapes. Track which pages have been processed in the current incremental run so we can skip them if the scrape is interrupted and resumed.

Reuses the existing Checkpoint infrastructure but adds incremental-specific state tracking.

## Acceptance Criteria

### 1. Incremental Checkpoint State
- [ ] Extend Checkpoint class to track incremental scrape state
- [ ] Fields: `completed_new_pages`, `completed_modified_pages`, `completed_deleted_pages`
- [ ] Field: `current_phase` (new_pages, modified_pages, deleted_pages, files)
- [ ] Save checkpoint after every 10 pages

### 2. Resume Detection
- [ ] Check for existing checkpoint file on scrape start
- [ ] Load previous state if checkpoint exists
- [ ] Skip already-completed pages
- [ ] Log resume information

### 3. Page Skip Logic
- [ ] Skip pages in `completed_new_pages` set
- [ ] Skip pages in `completed_modified_pages` set
- [ ] Skip pages in `completed_deleted_pages` set
- [ ] Continue from current_phase

### 4. Checkpoint Cleanup
- [ ] Clear checkpoint after successful complete run
- [ ] Keep checkpoint after failed run (for manual inspection)
- [ ] Optionally archive old checkpoints

### 5. Testing Requirements
- [ ] Test save and load checkpoint
- [ ] Test resume skips completed pages
- [ ] Test phase continuation
- [ ] Test coverage: 80%+

## Technical Implementation

```python
@dataclass
class IncrementalCheckpointState:
    completed_new_pages: Set[int] = field(default_factory=set)
    completed_modified_pages: Set[int] = field(default_factory=set)
    completed_deleted_pages: Set[int] = field(default_factory=set)
    current_phase: str = 'init'  # init, new_pages, modified_pages, deleted_pages, files
    last_updated: datetime = field(default_factory=datetime.now)

class IncrementalCheckpoint(Checkpoint):
    def load_state(self) -> IncrementalCheckpointState:
        if self.checkpoint_file.exists():
            data = json.loads(self.checkpoint_file.read_text())
            return IncrementalCheckpointState(
                completed_new_pages=set(data.get('completed_new_pages', [])),
                completed_modified_pages=set(data.get('completed_modified_pages', [])),
                completed_deleted_pages=set(data.get('completed_deleted_pages', [])),
                current_phase=data.get('current_phase', 'init'),
                last_updated=datetime.fromisoformat(data.get('last_updated'))
            )
        return IncrementalCheckpointState()
    
    def save_state(self, state: IncrementalCheckpointState):
        data = {
            'completed_new_pages': list(state.completed_new_pages),
            'completed_modified_pages': list(state.completed_modified_pages),
            'completed_deleted_pages': list(state.completed_deleted_pages),
            'current_phase': state.current_phase,
            'last_updated': state.last_updated.isoformat()
        }
        self.checkpoint_file.write_text(json.dumps(data, indent=2))
```

## Dependencies

### Requires
- Epic 01, Story 11: Checkpoint and Resume
- Epic 03, Story 05: Incremental Page Scraper

### Blocks
- None (enhances Story 05)

## Definition of Done

- [ ] IncrementalCheckpoint implemented
- [ ] Resume logic working correctly
- [ ] All tests passing (80%+ coverage)
- [ ] Integration test with interruption
- [ ] Code reviewed and merged
