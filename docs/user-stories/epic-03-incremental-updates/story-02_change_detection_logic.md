# Story 02: Change Detection Logic

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-02  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **logic to detect what changed since the last scrape**,  
So that **I know which pages need to be updated in the database**.

## Description

Implement the core change detection logic that compares the last scrape timestamp against recent changes to determine exactly which pages have been created, modified, or deleted. This is the brain of the incremental update system, coordinating between the recent changes API and the database.

The change detector queries the `scrape_runs` table for the last successful scrape, fetches all changes since then, and categorizes them into actionable change sets (new pages, modified pages, deleted pages, moved pages).

## Background & Context

**Change Detection Strategy:**
- Query `scrape_runs` table for last successful scrape timestamp
- Fetch all recent changes since that timestamp
- Categorize changes by type and page
- Deduplicate (same page may have multiple edits)
- Return structured change sets for downstream processing

**Incremental Update Flow:**
```
1. Get last_scrape_timestamp from database
2. Query recent changes API (last_scrape to now)
3. Parse and categorize changes:
   - New pages → full scrape needed
   - Modified pages → fetch new revisions only
   - Deleted pages → mark as deleted
   - Moved pages → update title, fetch if needed
4. Return ChangeSet with categorized page IDs
```

**Why This Story Matters:**
- Orchestrates incremental update workflow
- Ensures no changes are missed
- Prevents duplicate processing
- Foundation for efficient scraping

## Acceptance Criteria

### 1. ChangeDetector Class
- [ ] Create `scraper/incremental/change_detector.py` with `ChangeDetector` class
- [ ] Accepts `Database` and `RecentChangesClient` in constructor
- [ ] Stateless operation (no instance state between calls)
- [ ] Thread-safe for future parallel processing

### 2. Detect Changes Method
- [ ] Implement `detect_changes() -> ChangeSet` method
- [ ] Queries database for last successful scrape timestamp
- [ ] Handles first run (no previous scrape) → returns full scrape indicator
- [ ] Fetches all recent changes since last scrape
- [ ] Returns structured `ChangeSet` object

### 3. ChangeSet Data Model
- [ ] Create `ChangeSet` dataclass in `scraper/incremental/models.py`
- [ ] Field: `new_page_ids: Set[int]` - pages created since last scrape
- [ ] Field: `modified_page_ids: Set[int]` - pages edited since last scrape
- [ ] Field: `deleted_page_ids: Set[int]` - pages deleted since last scrape
- [ ] Field: `moved_pages: List[MovedPage]` - pages moved/renamed
- [ ] Field: `last_scrape_time: datetime` - timestamp used for detection
- [ ] Field: `detection_time: datetime` - when detection ran
- [ ] Property: `total_changes: int` - count of all changes
- [ ] Property: `requires_full_scrape: bool` - true if no last scrape

### 4. MovedPage Data Model
- [ ] Create `MovedPage` dataclass
- [ ] Fields: `page_id`, `old_title`, `new_title`, `namespace`, `timestamp`
- [ ] Used to track page moves/renames

### 5. Change Categorization
- [ ] Parse `ChangeType.NEW` → add to `new_page_ids`
- [ ] Parse `ChangeType.EDIT` → add to `modified_page_ids`
- [ ] Parse `LogAction.DELETE` → add to `deleted_page_ids`
- [ ] Parse `LogAction.MOVE` → add to `moved_pages`
- [ ] Deduplicate page IDs (page with multiple edits counted once)
- [ ] Handle edge case: page created then deleted (net zero change)

### 6. Last Scrape Timestamp Retrieval
- [ ] Query `scrape_runs` table ordered by `end_time DESC`
- [ ] Filter for `status = 'completed'` only
- [ ] Return `end_time` of most recent completed run
- [ ] Return `None` if no completed runs exist
- [ ] Log timestamp being used for change detection

### 7. First Run Handling
- [ ] If no previous scrape found, set `requires_full_scrape = True`
- [ ] Return empty change sets
- [ ] Log that first run detected
- [ ] Don't query recent changes API (unnecessary)

### 8. Edge Case Handling
- [ ] Same page edited multiple times → appears once in modified_page_ids
- [ ] Page created and edited → in new_page_ids, not modified_page_ids
- [ ] Page created then deleted → in deleted_page_ids only (skip scraping)
- [ ] Page moved → update title in database, check if content changed
- [ ] Handle pages with revid=0 (deleted revisions, log events)

### 9. Logging and Statistics
- [ ] Log last scrape timestamp used
- [ ] Log number of recent changes fetched
- [ ] Log breakdown by change type (new: X, edit: Y, delete: Z)
- [ ] Log total unique pages affected
- [ ] Log detection duration

### 10. Testing Requirements
- [ ] Test infrastructure: Create mock database with scrape_runs
- [ ] Test infrastructure: Create mock RecentChangesClient
- [ ] Unit test: First run returns requires_full_scrape=True
- [ ] Unit test: Detects new pages correctly
- [ ] Unit test: Detects modified pages correctly
- [ ] Unit test: Detects deleted pages correctly
- [ ] Unit test: Detects moved pages correctly
- [ ] Unit test: Deduplicates multiple edits to same page
- [ ] Unit test: Handles page created then deleted
- [ ] Unit test: Handles page created then edited
- [ ] Integration test: Full workflow from database to changeset
- [ ] Test coverage: 85%+ on change_detector.py

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `tests/fixtures/scrape_runs_data.json` with sample runs
- [ ] Create `tests/mocks/mock_database.py` for scrape_runs queries
- [ ] Create `tests/mocks/mock_recent_changes_client.py`
- [ ] Update `tests/conftest.py` with change detection fixtures
- [ ] Verify fixtures and mocks work correctly

### Data Models
- [ ] Create `scraper/incremental/__init__.py`
- [ ] Create `scraper/incremental/models.py`
- [ ] Define `ChangeSet` dataclass with all fields
- [ ] Define `MovedPage` dataclass
- [ ] Add helper methods (`total_changes`, etc.)
- [ ] Add comprehensive docstrings

### Change Detector Implementation
- [ ] Create `scraper/incremental/change_detector.py`
- [ ] Implement `ChangeDetector.__init__(db, rc_client)`
- [ ] Implement `detect_changes()` method
- [ ] Implement `_get_last_scrape_timestamp()` helper
- [ ] Implement `_categorize_changes()` helper
- [ ] Implement `_deduplicate_page_ids()` helper
- [ ] Implement `_handle_edge_cases()` helper
- [ ] Add comprehensive docstrings and type hints

### Testing (After Implementation)
- [ ] Write tests in `tests/test_change_detector.py`
- [ ] Test all acceptance criteria
- [ ] Test edge cases thoroughly
- [ ] Run tests: `pytest tests/test_change_detector.py -v`
- [ ] Verify 85%+ code coverage
- [ ] Fix any failing tests

### Documentation
- [ ] Add module docstring explaining change detection strategy
- [ ] Document all methods with examples
- [ ] Add inline comments for complex logic
- [ ] Document edge case handling

## Technical Details

### File Structure
```
scraper/
├── incremental/
│   ├── __init__.py
│   ├── models.py              # NEW: ChangeSet, MovedPage
│   └── change_detector.py     # NEW: ChangeDetector class
└── storage/
    └── database.py            # Existing (query scrape_runs)

tests/
├── conftest.py                # Update with fixtures
├── test_change_detector.py    # NEW: Change detector tests
├── mocks/
│   ├── mock_database.py
│   └── mock_recent_changes_client.py
└── fixtures/
    └── scrape_runs_data.json  # NEW
```

### ChangeSet Data Model

```python
# scraper/incremental/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Set, List, Optional

@dataclass
class MovedPage:
    """
    Represents a page that was moved/renamed.
    
    Attributes:
        page_id: Page ID
        old_title: Previous page title
        new_title: New page title
        namespace: Namespace ID
        timestamp: When the move occurred
    """
    page_id: int
    old_title: str
    new_title: str
    namespace: int
    timestamp: datetime

@dataclass
class ChangeSet:
    """
    Result of change detection, categorizing all changes since last scrape.
    
    Attributes:
        new_page_ids: Pages created since last scrape (need full scrape)
        modified_page_ids: Pages edited since last scrape (need revision update)
        deleted_page_ids: Pages deleted since last scrape (mark as deleted)
        moved_pages: Pages that were renamed/moved
        last_scrape_time: Timestamp used for change detection
        detection_time: When change detection was performed
        requires_full_scrape: True if this is the first scrape
    """
    new_page_ids: Set[int] = field(default_factory=set)
    modified_page_ids: Set[int] = field(default_factory=set)
    deleted_page_ids: Set[int] = field(default_factory=set)
    moved_pages: List[MovedPage] = field(default_factory=list)
    last_scrape_time: Optional[datetime] = None
    detection_time: datetime = field(default_factory=datetime.now)
    requires_full_scrape: bool = False
    
    @property
    def total_changes(self) -> int:
        """Total number of unique pages affected by changes."""
        return (len(self.new_page_ids) + 
                len(self.modified_page_ids) + 
                len(self.deleted_page_ids) + 
                len(self.moved_pages))
    
    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return self.total_changes > 0 or self.requires_full_scrape
    
    def __repr__(self) -> str:
        return (f"ChangeSet(new={len(self.new_page_ids)}, "
                f"modified={len(self.modified_page_ids)}, "
                f"deleted={len(self.deleted_page_ids)}, "
                f"moved={len(self.moved_pages)}, "
                f"full_scrape={self.requires_full_scrape})")
```

### ChangeDetector Implementation

```python
# scraper/incremental/change_detector.py
import logging
from datetime import datetime
from typing import Optional, List
from scraper.storage.database import Database
from scraper.api.recent_changes import RecentChangesClient
from scraper.storage.models import RecentChange, ChangeType, LogAction
from .models import ChangeSet, MovedPage

logger = logging.getLogger(__name__)

class ChangeDetector:
    """
    Detects changes between scrape runs for incremental updates.
    
    Coordinates between the database (last scrape time) and recent changes
    API to determine which pages need to be updated.
    
    Example:
        >>> db = Database("irowiki.db")
        >>> rc_client = RecentChangesClient(api)
        >>> detector = ChangeDetector(db, rc_client)
        >>> changes = detector.detect_changes()
        >>> print(f"New: {len(changes.new_page_ids)}, "
        ...       f"Modified: {len(changes.modified_page_ids)}")
    """
    
    def __init__(self, database: Database, rc_client: RecentChangesClient):
        """
        Initialize change detector.
        
        Args:
            database: Database instance for querying scrape history
            rc_client: Recent changes client for fetching changes
        """
        self.db = database
        self.rc_client = rc_client
    
    def detect_changes(self) -> ChangeSet:
        """
        Detect all changes since last scrape.
        
        Returns:
            ChangeSet with categorized changes
            
        Raises:
            APIError: If recent changes API call fails
        """
        logger.info("Starting change detection")
        
        # Get last successful scrape timestamp
        last_scrape = self._get_last_scrape_timestamp()
        
        if last_scrape is None:
            logger.info("No previous scrape found, full scrape required")
            return ChangeSet(
                requires_full_scrape=True,
                detection_time=datetime.now()
            )
        
        logger.info(f"Last scrape: {last_scrape}")
        
        # Fetch recent changes since last scrape
        now = datetime.now()
        recent_changes = self.rc_client.get_recent_changes(
            start=last_scrape,
            end=now
        )
        
        logger.info(f"Fetched {len(recent_changes)} recent changes")
        
        # Categorize changes
        changeset = self._categorize_changes(recent_changes, last_scrape)
        
        logger.info(f"Change detection complete: {changeset}")
        return changeset
    
    def _get_last_scrape_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of last successful scrape.
        
        Returns:
            Timestamp of last completed scrape, or None if no previous scrape
        """
        # Query most recent completed scrape run
        query = """
            SELECT end_time
            FROM scrape_runs
            WHERE status = 'completed'
            ORDER BY end_time DESC
            LIMIT 1
        """
        
        result = self.db.execute(query).fetchone()
        
        if result is None:
            return None
        
        return result[0]
    
    def _categorize_changes(
        self,
        changes: List[RecentChange],
        last_scrape: datetime
    ) -> ChangeSet:
        """
        Categorize recent changes into change sets.
        
        Args:
            changes: List of recent changes from API
            last_scrape: Timestamp of last scrape
            
        Returns:
            ChangeSet with categorized changes
        """
        new_pages = set()
        modified_pages = set()
        deleted_pages = set()
        moved_pages = []
        
        # Track pages created then deleted (net zero)
        created_page_ids = set()
        
        for change in changes:
            page_id = change.pageid
            
            # Skip invalid page IDs
            if page_id == 0 and change.type != ChangeType.LOG:
                logger.warning(f"Skipping change with page_id=0: {change}")
                continue
            
            # Categorize by change type
            if change.is_new_page:
                new_pages.add(page_id)
                created_page_ids.add(page_id)
                
            elif change.is_edit:
                # Only add to modified if not a new page
                if page_id not in created_page_ids:
                    modified_pages.add(page_id)
                    
            elif change.is_deletion:
                deleted_pages.add(page_id)
                # If page was created then deleted, remove from new_pages
                if page_id in new_pages:
                    new_pages.remove(page_id)
                    
            elif change.type == ChangeType.LOG and change.log_action == LogAction.MOVE:
                # Parse move: need old and new titles
                # Note: MediaWiki API provides move details in log params
                moved_page = MovedPage(
                    page_id=page_id,
                    old_title=change.comment,  # Simplified; real impl parses log params
                    new_title=change.title,
                    namespace=change.namespace,
                    timestamp=change.timestamp
                )
                moved_pages.append(moved_page)
        
        # Remove deleted pages from modified set
        modified_pages -= deleted_pages
        
        return ChangeSet(
            new_page_ids=new_pages,
            modified_page_ids=modified_pages,
            deleted_page_ids=deleted_pages,
            moved_pages=moved_pages,
            last_scrape_time=last_scrape,
            detection_time=datetime.now(),
            requires_full_scrape=False
        )
```

### Usage Example

```python
from scraper.storage.database import Database
from scraper.api.client import MediaWikiAPIClient
from scraper.api.recent_changes import RecentChangesClient
from scraper.incremental.change_detector import ChangeDetector

# Initialize components
db = Database("data/irowiki.db")
api = MediaWikiAPIClient("https://irowiki.org")
rc_client = RecentChangesClient(api)

# Detect changes
detector = ChangeDetector(db, rc_client)
changes = detector.detect_changes()

# Check if full scrape needed
if changes.requires_full_scrape:
    print("First run - performing full scrape")
    # ... run full scraper
else:
    print(f"Incremental update detected {changes.total_changes} changes:")
    print(f"  New pages: {len(changes.new_page_ids)}")
    print(f"  Modified pages: {len(changes.modified_page_ids)}")
    print(f"  Deleted pages: {len(changes.deleted_page_ids)}")
    print(f"  Moved pages: {len(changes.moved_pages)}")
    
    # Process new pages
    for page_id in changes.new_page_ids:
        print(f"Scraping new page {page_id}")
        # ... scrape full page history
    
    # Process modified pages
    for page_id in changes.modified_page_ids:
        print(f"Updating page {page_id}")
        # ... scrape new revisions only
    
    # Process deleted pages
    for page_id in changes.deleted_page_ids:
        print(f"Marking page {page_id} as deleted")
        # ... update is_deleted flag
```

## Dependencies

### Requires
- Epic 03, Story 01: Recent Changes API Client
- Epic 02, Story 05: Scrape Metadata Schema (scrape_runs table)
- Epic 02, Story 06: Database Initialization

### Blocks
- Story 03: Modified Page Detection
- Story 04: New Page Detection
- Story 05: Incremental Page Scraper
- All downstream incremental stories

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] ChangeDetector class fully implemented
- [ ] ChangeSet and MovedPage models created
- [ ] All tests passing: `pytest tests/test_change_detector.py -v`
- [ ] Test coverage ≥85%
- [ ] Type hints on all methods
- [ ] Comprehensive docstrings
- [ ] Edge cases handled and tested
- [ ] No pylint warnings
- [ ] Code formatted with black
- [ ] Imports sorted with isort
- [ ] Integration test with real database
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Understand the flow**: Last scrape time → Recent changes → Categorization
2. **Handle edge cases**: Pages created then deleted, multiple edits, etc.
3. **Test thoroughly**: Edge cases are where bugs hide
4. **Use sets for deduplication**: Efficient and automatic
5. **Log everything**: Helps debug incremental issues

### Common Pitfalls

- **Forgetting deduplication**: Page edited 10 times should appear once
- **Not handling created→deleted**: Net zero change, skip scraping
- **Ignoring moved pages**: Title changed but content may not have
- **Wrong last scrape query**: Must filter by status='completed'
- **Timezone issues**: Ensure database and API use same timezone

### Testing Strategy

- Mock database to return specific scrape_runs data
- Mock RecentChangesClient to return controlled changes
- Test each change type independently
- Test combinations (created+edited, created+deleted)
- Test first run scenario
- Integration test with real database schema

## References

- Epic 03 README: `docs/user-stories/epic-03-incremental-updates/README.md`
- Story 01: Recent Changes API
- Database Schema: `schema/sqlite.sql`
- MediaWiki Recent Changes: https://www.mediawiki.org/wiki/API:RecentChanges
