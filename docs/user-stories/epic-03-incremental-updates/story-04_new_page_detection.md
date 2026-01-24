# Story 04: New Page Detection

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-04  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 1-2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to identify pages created since the last scrape**,  
So that **I can perform full scrapes of these new pages including complete revision history**.

## Description

Implement logic to identify new pages that don't exist in the database yet. Unlike modified pages (which need only new revisions), new pages require a full scrape from creation to current state.

This is simpler than modified page detection since there's no database state to query—we just need to verify the page doesn't exist and prepare it for full scraping.

## Background & Context

**New Page Workflow:**
1. ChangeDetector identifies `new_page_ids` from recent changes
2. NewPageDetector verifies pages don't exist in database
3. For each new page, prepare full scrape (all revisions)
4. Incremental scraper performs full page scrape
5. Insert complete page + revision history into database

**Key Difference from Modified Pages:**
- **Modified pages**: Fetch only new revisions (efficient)
- **New pages**: Fetch entire history (necessary, but typically short)
- Most new pages have only 1-5 revisions at creation

**Why This Story Matters:**
- Ensures new content is captured
- Distinguishes new vs modified pages
- Simpler logic than modified page detection
- Critical for complete archival

## Acceptance Criteria

### 1. NewPageDetector Class
- [ ] Create `scraper/incremental/new_page_detector.py`
- [ ] Accepts `Database` instance in constructor
- [ ] Stateless operation
- [ ] Thread-safe

### 2. Verify New Page Method
- [ ] Implement `verify_new_page(page_id: int) -> bool`
- [ ] Returns `True` if page not in database
- [ ] Returns `False` if page already exists
- [ ] Fast query (index on page_id)

### 3. Batch Verification Method
- [ ] Implement `verify_new_pages(page_ids: List[int]) -> Set[int]`
- [ ] Returns set of page IDs that don't exist in database
- [ ] Single efficient query using NOT IN or LEFT JOIN
- [ ] Handles empty input gracefully

### 4. Filter Existing Pages Method
- [ ] Implement `filter_new_pages(page_ids: List[int]) -> Set[int]`
- [ ] Alias for `verify_new_pages` with clearer name
- [ ] Returns only genuinely new page IDs

### 5. Get New Page Info Method
- [ ] Implement `get_new_page_info(page_id: int, title: str, namespace: int) -> NewPageInfo`
- [ ] Returns `NewPageInfo` dataclass with basic metadata
- [ ] Does NOT query database (page doesn't exist yet)
- [ ] Uses metadata from recent changes

### 6. NewPageInfo Data Model
- [ ] Create `NewPageInfo` dataclass in `scraper/incremental/models.py`
- [ ] Fields: `page_id`, `namespace`, `title`
- [ ] Field: `detected_at` (when we discovered this new page)
- [ ] Property: `needs_full_scrape` (always True)
- [ ] Method: `to_scrape_params()` returns API parameters

### 7. Database Queries
- [ ] Simple EXISTS query: `SELECT 1 FROM pages WHERE page_id = ? LIMIT 1`
- [ ] Batch query: `SELECT page_id FROM pages WHERE page_id IN (...)`
- [ ] Use index on page_id (should exist from primary key)
- [ ] Query performance: <1ms per page, <50ms for 500 pages

### 8. Edge Case Handling
- [ ] Handle page that was "new" but already scraped by another process
- [ ] Handle race conditions (page appears between detection and scrape)
- [ ] Log when "new" page already exists (warning, not error)
- [ ] Handle empty page_ids list

### 9. Testing Requirements
- [ ] Test infrastructure: Test database with known pages
- [ ] Unit test: Verify genuinely new page returns True
- [ ] Unit test: Verify existing page returns False
- [ ] Unit test: Batch verification with mix of new/existing pages
- [ ] Unit test: Batch verification with all new pages
- [ ] Unit test: Batch verification with all existing pages
- [ ] Unit test: Handle empty input list
- [ ] Performance test: Batch query 500 pages <50ms
- [ ] Test coverage: 80%+ on new_page_detector.py

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `tests/fixtures/new_pages_testdb.py`
- [ ] Populate test database with known pages
- [ ] Create helper to check page existence
- [ ] Update `tests/conftest.py` with fixtures

### Data Model
- [ ] Update `scraper/incremental/models.py`
- [ ] Create `NewPageInfo` dataclass
- [ ] Add helper methods
- [ ] Add comprehensive docstrings

### Detector Implementation
- [ ] Create `scraper/incremental/new_page_detector.py`
- [ ] Implement `NewPageDetector.__init__(db)`
- [ ] Implement `verify_new_page()` method
- [ ] Implement `verify_new_pages()` batch method
- [ ] Implement `filter_new_pages()` alias method
- [ ] Implement `get_new_page_info()` method
- [ ] Add comprehensive docstrings

### Testing (After Implementation)
- [ ] Write tests in `tests/test_new_page_detector.py`
- [ ] Test all acceptance criteria
- [ ] Test edge cases
- [ ] Run tests: `pytest tests/test_new_page_detector.py -v`
- [ ] Verify 80%+ code coverage
- [ ] Performance test batch queries

### Documentation
- [ ] Add module docstring
- [ ] Document query strategy
- [ ] Add usage examples
- [ ] Document integration with ChangeDetector

## Technical Details

### File Structure
```
scraper/
├── incremental/
│   ├── __init__.py
│   ├── models.py                 # Update with NewPageInfo
│   └── new_page_detector.py      # NEW

tests/
├── test_new_page_detector.py     # NEW
└── fixtures/
    └── new_pages_testdb.py       # NEW
```

### NewPageInfo Data Model

```python
# scraper/incremental/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

@dataclass
class NewPageInfo:
    """
    Information about a newly created page for incremental scraping.
    
    Unlike PageUpdateInfo (for modified pages), this has minimal metadata
    since the page doesn't exist in our database yet.
    
    Attributes:
        page_id: Page ID from MediaWiki
        namespace: Namespace ID
        title: Page title
        detected_at: When we discovered this new page
    """
    page_id: int
    namespace: int
    title: str
    detected_at: datetime
    
    @property
    def needs_full_scrape(self) -> bool:
        """New pages always need full scrape of all revisions."""
        return True
    
    def to_scrape_params(self) -> Dict[str, Any]:
        """
        Get API parameters for scraping this new page.
        
        Returns:
            Dict of parameters for MediaWiki API
            
        Example:
            >>> info = NewPageInfo(123, 0, "New_Page", datetime.now())
            >>> params = info.to_scrape_params()
            >>> # params = {'pageids': 123, 'rvdir': 'newer'}
        """
        return {
            'pageids': self.page_id,
            'rvdir': 'newer',  # Oldest revisions first
            'rvlimit': 500,    # Get all revisions (new pages typically have few)
        }
    
    def __repr__(self) -> str:
        return f"NewPageInfo(page_id={self.page_id}, title={self.title}, namespace={self.namespace})"
```

### NewPageDetector Implementation

```python
# scraper/incremental/new_page_detector.py
import logging
from datetime import datetime
from typing import List, Set
from scraper.storage.database import Database
from .models import NewPageInfo

logger = logging.getLogger(__name__)

class NewPageDetector:
    """
    Detects which pages are genuinely new (not in database).
    
    Used during incremental updates to distinguish new pages (need full scrape)
    from modified pages (need only new revisions).
    
    Example:
        >>> db = Database("irowiki.db")
        >>> detector = NewPageDetector(db)
        >>> is_new = detector.verify_new_page(12345)
        >>> if is_new:
        ...     print("Need to scrape full page history")
    """
    
    def __init__(self, database: Database):
        """
        Initialize new page detector.
        
        Args:
            database: Database instance for checking page existence
        """
        self.db = database
    
    def verify_new_page(self, page_id: int) -> bool:
        """
        Check if a page is genuinely new (not in database).
        
        Args:
            page_id: Page ID to check
            
        Returns:
            True if page not in database, False if it exists
            
        Example:
            >>> is_new = detector.verify_new_page(12345)
            >>> if is_new:
            ...     print("This is a new page")
        """
        query = "SELECT 1 FROM pages WHERE page_id = ? LIMIT 1"
        result = self.db.execute(query, (page_id,)).fetchone()
        
        exists = result is not None
        
        if exists:
            logger.debug(f"Page {page_id} already exists in database")
        else:
            logger.debug(f"Page {page_id} is new (not in database)")
        
        return not exists
    
    def verify_new_pages(self, page_ids: List[int]) -> Set[int]:
        """
        Check which pages are genuinely new (batch operation).
        
        Efficiently checks multiple pages in a single query.
        
        Args:
            page_ids: List of page IDs to check
            
        Returns:
            Set of page IDs that don't exist in database
            
        Example:
            >>> candidate_ids = [100, 101, 102, 103]
            >>> new_ids = detector.verify_new_pages(candidate_ids)
            >>> print(f"{len(new_ids)} pages are genuinely new")
        """
        if not page_ids:
            logger.debug("No page IDs to verify")
            return set()
        
        logger.info(f"Verifying {len(page_ids)} pages for newness")
        
        # Query existing pages
        placeholders = ','.join('?' * len(page_ids))
        query = f"SELECT page_id FROM pages WHERE page_id IN ({placeholders})"
        
        results = self.db.execute(query, page_ids).fetchall()
        existing_ids = {row[0] for row in results}
        
        # Calculate new pages (in input but not in database)
        candidate_ids = set(page_ids)
        new_ids = candidate_ids - existing_ids
        
        logger.info(f"Found {len(new_ids)} new pages, {len(existing_ids)} already exist")
        
        if existing_ids:
            logger.warning(f"Pages marked as 'new' but already in database: {existing_ids}")
        
        return new_ids
    
    def filter_new_pages(self, page_ids: List[int]) -> Set[int]:
        """
        Filter list to only genuinely new pages.
        
        Alias for verify_new_pages with clearer intent.
        
        Args:
            page_ids: List of candidate page IDs
            
        Returns:
            Set of page IDs not in database
        """
        return self.verify_new_pages(page_ids)
    
    def get_new_page_info(
        self,
        page_id: int,
        title: str,
        namespace: int
    ) -> NewPageInfo:
        """
        Create NewPageInfo for a new page.
        
        Does not query database (page doesn't exist yet). Uses metadata
        from recent changes or other source.
        
        Args:
            page_id: Page ID from recent changes
            title: Page title from recent changes
            namespace: Namespace ID from recent changes
            
        Returns:
            NewPageInfo object ready for scraping
            
        Example:
            >>> # From recent change entry
            >>> change = recent_changes[0]
            >>> info = detector.get_new_page_info(
            ...     page_id=change.pageid,
            ...     title=change.title,
            ...     namespace=change.namespace
            ... )
            >>> print(info.to_scrape_params())
        """
        return NewPageInfo(
            page_id=page_id,
            namespace=namespace,
            title=title,
            detected_at=datetime.now()
        )
```

### Usage Example

```python
from scraper.storage.database import Database
from scraper.api.client import MediaWikiAPIClient
from scraper.api.recent_changes import RecentChangesClient
from scraper.incremental.change_detector import ChangeDetector
from scraper.incremental.new_page_detector import NewPageDetector

# Initialize
db = Database("data/irowiki.db")
api = MediaWikiAPIClient("https://irowiki.org")
rc_client = RecentChangesClient(api)

# Detect changes
change_detector = ChangeDetector(db, rc_client)
changes = change_detector.detect_changes()

print(f"Candidate new pages: {len(changes.new_page_ids)}")

# Verify which are genuinely new
new_page_detector = NewPageDetector(db)
genuinely_new = new_page_detector.filter_new_pages(list(changes.new_page_ids))

print(f"Genuinely new pages: {len(genuinely_new)}")

# Get info for each new page from recent changes
for change in recent_changes:
    if change.pageid in genuinely_new:
        info = new_page_detector.get_new_page_info(
            page_id=change.pageid,
            title=change.title,
            namespace=change.namespace
        )
        
        print(f"\nNew page: {info.title}")
        print(f"  Page ID: {info.page_id}")
        print(f"  Namespace: {info.namespace}")
        print(f"  Needs full scrape: {info.needs_full_scrape}")
        
        # Use with page scraper
        scrape_params = info.to_scrape_params()
        # page_scraper.scrape_page(**scrape_params)
```

### Integration Example

```python
# Complete incremental workflow
def incremental_scrape():
    """Complete incremental scrape workflow."""
    # Detect changes
    changes = change_detector.detect_changes()
    
    if changes.requires_full_scrape:
        print("First run - performing full scrape")
        return full_scrape()
    
    # Process new pages
    new_detector = NewPageDetector(db)
    new_ids = new_detector.filter_new_pages(list(changes.new_page_ids))
    
    print(f"Scraping {len(new_ids)} new pages (full history)")
    for page_id in new_ids:
        # Full scrape for new pages
        page_scraper.scrape_page_full(page_id)
    
    # Process modified pages
    modified_detector = ModifiedPageDetector(db)
    modified_infos = modified_detector.get_batch_update_info(
        list(changes.modified_page_ids)
    )
    
    print(f"Updating {len(modified_infos)} modified pages (new revisions only)")
    for info in modified_infos:
        # Incremental scrape for modified pages
        revision_scraper.scrape_new_revisions(info)
    
    print("Incremental scrape complete!")
```

## Dependencies

### Requires
- Epic 02, Story 01: Pages Schema
- Epic 02, Story 06: Database Initialization
- Epic 03, Story 02: Change Detection Logic

### Blocks
- Story 05: Incremental Page Scraper
- Story 06: Incremental Revision Scraper

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] NewPageDetector class fully implemented
- [ ] NewPageInfo model created
- [ ] Efficient batch verification implemented
- [ ] All tests passing: `pytest tests/test_new_page_detector.py -v`
- [ ] Test coverage ≥80%
- [ ] Performance requirements met (<50ms for 500 pages)
- [ ] Type hints on all methods
- [ ] Comprehensive docstrings
- [ ] No pylint warnings
- [ ] Code formatted with black
- [ ] Integration example documented
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Simpler than modified page detection**: Just check existence
2. **Batch queries are faster**: Use NOT IN or LEFT JOIN WHERE NULL
3. **Index on page_id**: Should exist from primary key constraint
4. **Log when "new" pages exist**: Indicates race condition or bug
5. **NewPageInfo is lightweight**: No database state needed

### Common Pitfalls

- **N+1 queries**: Always use batch verification
- **Not logging warnings**: Important to track "new" pages that exist
- **Race conditions**: Another process may scrape page first
- **Assuming all "new" pages are new**: Always verify
- **Not handling empty lists**: Edge case but important

### Performance Considerations

- Single page query: <1ms (index lookup)
- Batch query: <50ms for 500 pages
- Use IN clause or LEFT JOIN WHERE NULL
- Index on page_id from PRIMARY KEY constraint

### Testing Strategy

- Test with genuinely new pages
- Test with pages that already exist
- Test with mix of new and existing
- Test empty input
- Test performance with large batches

## References

- Database Schema: `schema/sqlite.sql`
- Epic 03 README: `docs/user-stories/epic-03-incremental-updates/README.md`
- Story 02: Change Detection Logic
- Story 03: Modified Page Detection
