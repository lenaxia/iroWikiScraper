# Story 03: Modified Page Detection

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-03  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to identify which existing pages have been modified**,  
So that **I can fetch only new revisions without re-scraping entire page history**.

## Description

Implement logic to query the database for existing pages that have been modified since the last scrape. For each modified page, determine the highest revision ID already stored, so we can fetch only newer revisions from the API.

This optimization dramatically reduces scraping time: instead of fetching 100 revisions for a page, we fetch only the 1-2 new revisions added since last month.

## Background & Context

**Modified Page Workflow:**
1. ChangeDetector identifies modified_page_ids from recent changes
2. ModifiedPageDetector queries database for each page:
   - Get current page metadata (title, namespace)
   - Get highest revision_id stored
   - Get last modification timestamp
3. Return PageUpdateInfo for each page
4. Incremental scraper uses this to fetch only new revisions

**Efficiency Gains:**
- Full scrape: Fetch all 86,500 revisions
- Incremental: Fetch only ~200-500 new revisions per month
- **100x fewer revision API calls**

**Why This Story Matters:**
- Core of incremental efficiency
- Prevents duplicate revision fetching
- Enables precise incremental updates
- Dramatically reduces bandwidth and time

## Acceptance Criteria

### 1. ModifiedPageDetector Class
- [ ] Create `scraper/incremental/modified_page_detector.py`
- [ ] Accepts `Database` instance in constructor
- [ ] Stateless operation (no instance state)
- [ ] Thread-safe for future parallel processing

### 2. Get Page Update Info Method
- [ ] Implement `get_page_update_info(page_id: int) -> PageUpdateInfo`
- [ ] Queries database for page metadata
- [ ] Queries database for highest revision_id
- [ ] Queries database for last revision timestamp
- [ ] Returns structured PageUpdateInfo object
- [ ] Raises PageNotFoundError if page not in database

### 3. Batch Query Method
- [ ] Implement `get_batch_update_info(page_ids: List[int]) -> List[PageUpdateInfo]`
- [ ] Efficiently queries all pages in single database transaction
- [ ] Uses JOIN to fetch page + revision info together
- [ ] Returns list of PageUpdateInfo objects
- [ ] Skips pages not found in database (logs warning)

### 4. PageUpdateInfo Data Model
- [ ] Create `PageUpdateInfo` dataclass in `scraper/incremental/models.py`
- [ ] Fields: `page_id`, `namespace`, `title`, `is_redirect`
- [ ] Fields: `highest_revision_id`, `last_revision_timestamp`
- [ ] Fields: `total_revisions_stored` (count)
- [ ] Property: `needs_update` (always True for modified pages)
- [ ] Method: `get_revision_filter()` returns params for API query

### 5. Database Queries
- [ ] Query page metadata from `pages` table
- [ ] Query MAX(revision_id) from `revisions` table for each page
- [ ] Query MAX(timestamp) from `revisions` table for each page
- [ ] Query COUNT(*) from `revisions` table for each page
- [ ] Use efficient JOINs for batch queries
- [ ] Index usage verified with EXPLAIN QUERY PLAN

### 6. Error Handling
- [ ] Handle page not found in database
- [ ] Handle page with no revisions (data integrity issue)
- [ ] Handle database connection errors
- [ ] Log warnings for unexpected states
- [ ] Raise clear exceptions with context

### 7. Performance Requirements
- [ ] Single page query: <10ms
- [ ] Batch query (100 pages): <100ms
- [ ] Batch query (500 pages): <500ms
- [ ] Use prepared statements for efficiency
- [ ] Minimize database round trips

### 8. Testing Requirements
- [ ] Test infrastructure: Populate test database with pages and revisions
- [ ] Unit test: Get update info for single page
- [ ] Unit test: Get update info for page with multiple revisions
- [ ] Unit test: Get update info for page with single revision
- [ ] Unit test: Handle page not found
- [ ] Unit test: Handle page with no revisions (edge case)
- [ ] Unit test: Batch query with multiple pages
- [ ] Unit test: Batch query with some pages missing
- [ ] Performance test: Batch query 500 pages <500ms
- [ ] Test coverage: 80%+ on modified_page_detector.py

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `tests/fixtures/modified_pages_testdb.py`
- [ ] Populate test database with sample pages
- [ ] Populate test database with sample revisions
- [ ] Create helper to reset test database state
- [ ] Update `tests/conftest.py` with fixtures

### Data Model
- [ ] Update `scraper/incremental/models.py`
- [ ] Create `PageUpdateInfo` dataclass
- [ ] Add helper methods and properties
- [ ] Add comprehensive docstrings
- [ ] Add type hints

### Detector Implementation
- [ ] Create `scraper/incremental/modified_page_detector.py`
- [ ] Implement `ModifiedPageDetector.__init__(db)`
- [ ] Implement `get_page_update_info()` method
- [ ] Implement `get_batch_update_info()` method
- [ ] Implement `_query_page_metadata()` helper
- [ ] Implement `_query_revision_info()` helper
- [ ] Add comprehensive docstrings

### Testing (After Implementation)
- [ ] Write tests in `tests/test_modified_page_detector.py`
- [ ] Test all acceptance criteria
- [ ] Test edge cases
- [ ] Run tests: `pytest tests/test_modified_page_detector.py -v`
- [ ] Verify 80%+ code coverage
- [ ] Performance test batch queries

### Documentation
- [ ] Add module docstring
- [ ] Document database query strategy
- [ ] Add usage examples
- [ ] Document performance characteristics

## Technical Details

### File Structure
```
scraper/
├── incremental/
│   ├── __init__.py
│   ├── models.py                    # Update with PageUpdateInfo
│   └── modified_page_detector.py    # NEW

tests/
├── test_modified_page_detector.py   # NEW
└── fixtures/
    └── modified_pages_testdb.py     # NEW
```

### PageUpdateInfo Data Model

```python
# scraper/incremental/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

@dataclass
class PageUpdateInfo:
    """
    Information about a page's current state for incremental updates.
    
    Used to determine which revisions to fetch from the API.
    
    Attributes:
        page_id: Page ID in database
        namespace: Namespace ID
        title: Page title
        is_redirect: Whether page is currently a redirect
        highest_revision_id: Highest revision ID stored in database
        last_revision_timestamp: Timestamp of most recent revision stored
        total_revisions_stored: Count of revisions in database
    """
    page_id: int
    namespace: int
    title: str
    is_redirect: bool
    highest_revision_id: int
    last_revision_timestamp: datetime
    total_revisions_stored: int
    
    @property
    def needs_update(self) -> bool:
        """Always True for modified pages (why else would we query?)"""
        return True
    
    def get_revision_filter(self) -> Dict[str, Any]:
        """
        Get API parameters to fetch only new revisions.
        
        Returns:
            Dict of parameters for MediaWiki revisions API
            
        Example:
            >>> info = detector.get_page_update_info(123)
            >>> params = info.get_revision_filter()
            >>> # params = {'rvstartid': 100000, 'rvdir': 'newer'}
        """
        return {
            'rvstartid': self.highest_revision_id + 1,  # Start after last known
            'rvdir': 'newer'  # Fetch newer revisions
        }
    
    def __repr__(self) -> str:
        return (f"PageUpdateInfo(page_id={self.page_id}, title={self.title}, "
                f"highest_rev={self.highest_revision_id}, "
                f"total_revs={self.total_revisions_stored})")
```

### ModifiedPageDetector Implementation

```python
# scraper/incremental/modified_page_detector.py
import logging
from typing import List, Optional
from scraper.storage.database import Database
from scraper.api.exceptions import PageNotFoundError
from .models import PageUpdateInfo

logger = logging.getLogger(__name__)

class ModifiedPageDetector:
    """
    Detects which existing pages need revision updates.
    
    Queries the database to determine the current state of modified pages,
    including which revisions are already stored, so we can fetch only
    new revisions from the API.
    
    Example:
        >>> db = Database("irowiki.db")
        >>> detector = ModifiedPageDetector(db)
        >>> info = detector.get_page_update_info(123)
        >>> print(f"Page has {info.total_revisions_stored} revisions")
        >>> print(f"Last revision: {info.highest_revision_id}")
    """
    
    def __init__(self, database: Database):
        """
        Initialize modified page detector.
        
        Args:
            database: Database instance for querying page state
        """
        self.db = database
    
    def get_page_update_info(self, page_id: int) -> PageUpdateInfo:
        """
        Get update information for a single modified page.
        
        Args:
            page_id: Page ID to query
            
        Returns:
            PageUpdateInfo with current page state
            
        Raises:
            PageNotFoundError: If page not found in database
            
        Example:
            >>> info = detector.get_page_update_info(123)
            >>> print(f"Fetch revisions after {info.highest_revision_id}")
        """
        query = """
            SELECT 
                p.page_id,
                p.namespace,
                p.title,
                p.is_redirect,
                COALESCE(MAX(r.revision_id), 0) as highest_revision_id,
                COALESCE(MAX(r.timestamp), p.created_at) as last_revision_timestamp,
                COUNT(r.revision_id) as total_revisions
            FROM pages p
            LEFT JOIN revisions r ON p.page_id = r.page_id
            WHERE p.page_id = ?
            GROUP BY p.page_id
        """
        
        result = self.db.execute(query, (page_id,)).fetchone()
        
        if result is None:
            raise PageNotFoundError(f"Page {page_id} not found in database")
        
        # Unpack result
        (page_id, namespace, title, is_redirect, 
         highest_rev_id, last_timestamp, total_revs) = result
        
        # Warn if page has no revisions (data integrity issue)
        if total_revs == 0:
            logger.warning(f"Page {page_id} ({title}) has no revisions in database")
        
        return PageUpdateInfo(
            page_id=page_id,
            namespace=namespace,
            title=title,
            is_redirect=bool(is_redirect),
            highest_revision_id=highest_rev_id,
            last_revision_timestamp=last_timestamp,
            total_revisions_stored=total_revs
        )
    
    def get_batch_update_info(self, page_ids: List[int]) -> List[PageUpdateInfo]:
        """
        Get update information for multiple pages efficiently.
        
        Uses a single query with JOIN to fetch all page information at once.
        Skips pages not found in database (logs warning).
        
        Args:
            page_ids: List of page IDs to query
            
        Returns:
            List of PageUpdateInfo objects (may be shorter than input if pages missing)
            
        Example:
            >>> page_ids = [100, 101, 102, 103, 104]
            >>> infos = detector.get_batch_update_info(page_ids)
            >>> print(f"Found {len(infos)} pages in database")
        """
        if not page_ids:
            return []
        
        logger.info(f"Querying update info for {len(page_ids)} pages")
        
        # Build query with IN clause
        placeholders = ','.join('?' * len(page_ids))
        query = f"""
            SELECT 
                p.page_id,
                p.namespace,
                p.title,
                p.is_redirect,
                COALESCE(MAX(r.revision_id), 0) as highest_revision_id,
                COALESCE(MAX(r.timestamp), p.created_at) as last_revision_timestamp,
                COUNT(r.revision_id) as total_revisions
            FROM pages p
            LEFT JOIN revisions r ON p.page_id = r.page_id
            WHERE p.page_id IN ({placeholders})
            GROUP BY p.page_id
        """
        
        results = self.db.execute(query, page_ids).fetchall()
        
        # Warn if some pages missing
        found_ids = {row[0] for row in results}
        missing_ids = set(page_ids) - found_ids
        if missing_ids:
            logger.warning(f"{len(missing_ids)} pages not found in database: {missing_ids}")
        
        # Convert rows to PageUpdateInfo objects
        infos = []
        for row in results:
            (page_id, namespace, title, is_redirect,
             highest_rev_id, last_timestamp, total_revs) = row
            
            if total_revs == 0:
                logger.warning(f"Page {page_id} ({title}) has no revisions")
            
            infos.append(PageUpdateInfo(
                page_id=page_id,
                namespace=namespace,
                title=title,
                is_redirect=bool(is_redirect),
                highest_revision_id=highest_rev_id,
                last_revision_timestamp=last_timestamp,
                total_revisions_stored=total_revs
            ))
        
        logger.info(f"Retrieved update info for {len(infos)} pages")
        return infos
```

### Usage Example

```python
from scraper.storage.database import Database
from scraper.incremental.change_detector import ChangeDetector
from scraper.incremental.modified_page_detector import ModifiedPageDetector

# Initialize
db = Database("data/irowiki.db")
detector = ModifiedPageDetector(db)

# Get changes
change_detector = ChangeDetector(db, rc_client)
changes = change_detector.detect_changes()

# Get update info for all modified pages
page_infos = detector.get_batch_update_info(list(changes.modified_page_ids))

print(f"Processing {len(page_infos)} modified pages:")

for info in page_infos:
    print(f"\nPage: {info.title} (ID: {info.page_id})")
    print(f"  Current revisions stored: {info.total_revisions_stored}")
    print(f"  Highest revision ID: {info.highest_revision_id}")
    print(f"  Last update: {info.last_revision_timestamp}")
    
    # Get API parameters for fetching new revisions
    api_params = info.get_revision_filter()
    print(f"  API params: {api_params}")
    
    # Use with revision scraper
    # new_revisions = revision_scraper.fetch_revisions(
    #     page_id=info.page_id,
    #     **api_params
    # )
```

## Dependencies

### Requires
- Epic 02, Story 01: Pages Schema
- Epic 02, Story 02: Revisions Schema
- Epic 02, Story 06: Database Initialization
- Epic 03, Story 02: Change Detection Logic

### Blocks
- Story 05: Incremental Page Scraper
- Story 06: Incremental Revision Scraper

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] ModifiedPageDetector class fully implemented
- [ ] PageUpdateInfo model created
- [ ] Efficient batch query implemented
- [ ] All tests passing: `pytest tests/test_modified_page_detector.py -v`
- [ ] Test coverage ≥80%
- [ ] Performance requirements met (<500ms for 500 pages)
- [ ] Type hints on all methods
- [ ] Comprehensive docstrings
- [ ] No pylint warnings
- [ ] Code formatted with black
- [ ] Integration test with real database
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Understand LEFT JOIN**: Used because pages might have no revisions
2. **COALESCE for defaults**: Handle NULL values from LEFT JOIN
3. **Batch queries are critical**: Avoid N+1 query problem
4. **Index usage matters**: Verify with EXPLAIN QUERY PLAN
5. **Test edge cases**: No revisions, missing pages, etc.

### Common Pitfalls

- **N+1 queries**: Always use batch query, not loop of single queries
- **Missing indexes**: Slow without index on revisions.page_id
- **NULL handling**: LEFT JOIN returns NULLs, use COALESCE
- **Data integrity**: Pages with no revisions shouldn't exist
- **Timezone consistency**: Ensure timestamps match API timezone

### Performance Optimization

- Use indexes: `page_id`, `revision_id`, `timestamp`
- Batch queries minimize database round trips
- Prepared statements cached by database
- Use EXPLAIN QUERY PLAN to verify index usage

## References

- Database Schema: `schema/sqlite.sql`
- Epic 03 README: `docs/user-stories/epic-03-incremental-updates/README.md`
- Story 02: Change Detection Logic
- SQLite EXPLAIN: https://www.sqlite.org/eqp.html
