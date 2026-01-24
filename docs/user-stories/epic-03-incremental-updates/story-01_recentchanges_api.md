# Story 01: Recent Changes API Client

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-01  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to integrate with MediaWiki's recentchanges API**,  
So that **I can detect all changes since the last scrape efficiently**.

## Description

Implement a client for MediaWiki's `recentchanges` API endpoint to fetch all page changes within a specified time range. This is the foundation for incremental updates, allowing the scraper to identify which pages have been created, modified, or deleted since the last run.

The recent changes API provides a chronological feed of all wiki activity including new pages, edits, deletions, moves, and other log events. By querying this API with a timestamp range, we can avoid re-scraping unchanged content.

## Background & Context

**MediaWiki recentchanges API:**
- Endpoint: `api.php?action=query&list=recentchanges`
- Returns changes in chronological order
- Supports filtering by namespace, type, and time range
- Pagination via continue tokens (max 500 results per request)
- Change types: new, edit, log (delete, move, protect, etc.)

**iRO Wiki Scale:**
- Typical monthly changes: 100-500 edits
- Full scrape: 24-48 hours, 5,000 API calls
- Incremental scrape: 2-4 hours, 100-500 API calls
- **10-20x speedup for monthly updates**

**Why This Story Matters:**
- Enables efficient incremental updates
- Reduces bandwidth and scraping time
- Foundation for all change detection logic
- Allows monthly automated updates

## Acceptance Criteria

### 1. RecentChangesClient Class
- [ ] Create `scraper/api/recent_changes.py` with `RecentChangesClient` class
- [ ] Client accepts `MediaWikiAPIClient` in constructor
- [ ] Integrates with existing rate limiting infrastructure
- [ ] All methods return typed data structures (no raw dicts)

### 2. Query Recent Changes Method
- [ ] Implement `get_recent_changes(start: datetime, end: datetime)` method
- [ ] Returns List[RecentChange] with all changes in time range
- [ ] Handles pagination automatically (max 500 per request)
- [ ] Supports filtering by namespace (optional parameter)
- [ ] Supports filtering by change type (optional parameter)
- [ ] Orders results chronologically (oldest first)

### 3. RecentChange Data Model
- [ ] Create `RecentChange` dataclass in `scraper/storage/models.py`
- [ ] Fields: `rcid`, `type`, `namespace`, `title`, `pageid`, `revid`, `old_revid`
- [ ] Fields: `timestamp`, `user`, `userid`, `comment`
- [ ] Fields: `oldlen`, `newlen` (content size changes)
- [ ] Type enum: `new`, `edit`, `log`
- [ ] Log action field for log entries (delete, move, etc.)

### 4. Pagination Handling
- [ ] Automatically follows continuation tokens (`rccontinue`)
- [ ] Accumulates all results before returning
- [ ] Logs progress for long queries (>1000 changes)
- [ ] Respects rate limiting between paginated requests

### 5. Time Range Filtering
- [ ] Accepts Python datetime objects
- [ ] Converts to MediaWiki timestamp format (ISO 8601)
- [ ] Validates start < end
- [ ] Handles timezone-aware datetimes (convert to UTC)
- [ ] Defaults to UTC if timezone-naive

### 6. Change Type Filtering
- [ ] Filter by type: `new` (new pages only)
- [ ] Filter by type: `edit` (edits to existing pages)
- [ ] Filter by type: `log` (log events)
- [ ] Support multiple types simultaneously
- [ ] Default: return all types

### 7. Namespace Filtering
- [ ] Accept namespace parameter (int or list of ints)
- [ ] Filter to specific namespaces
- [ ] Default: all namespaces

### 8. Error Handling
- [ ] Handle API errors gracefully
- [ ] Retry transient failures (503, timeout)
- [ ] Raise `APIError` with clear message on persistent failures
- [ ] Validate response structure before parsing
- [ ] Log warnings for unexpected response fields

### 9. Testing Requirements
- [ ] Test infrastructure: Create `fixtures/api/recentchanges_*.json` files
- [ ] Test infrastructure: Mock recent changes API responses
- [ ] Unit test: Parse single recent change entry
- [ ] Unit test: Handle paginated results (>500 changes)
- [ ] Unit test: Filter by time range
- [ ] Unit test: Filter by namespace
- [ ] Unit test: Filter by change type
- [ ] Unit test: Handle empty results
- [ ] Unit test: Handle API errors
- [ ] Unit test: Validate timestamp conversion
- [ ] Integration test: Fetch real recent changes (optional, marked @pytest.mark.integration)
- [ ] Test coverage: 80%+ on recent_changes.py

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `fixtures/api/` directory if not exists
- [ ] Create `fixtures/api/recentchanges_new_page.json` (new page change)
- [ ] Create `fixtures/api/recentchanges_edit.json` (edit change)
- [ ] Create `fixtures/api/recentchanges_delete.json` (deletion log entry)
- [ ] Create `fixtures/api/recentchanges_paginated.json` (with continue token)
- [ ] Update `tests/conftest.py` with recent changes fixtures
- [ ] Verify fixtures load correctly

### Data Models
- [ ] Update `scraper/storage/models.py`
- [ ] Create `RecentChange` dataclass with all fields
- [ ] Create `ChangeType` enum (NEW, EDIT, LOG)
- [ ] Create `LogAction` enum (DELETE, MOVE, PROTECT, etc.)
- [ ] Add type hints and docstrings
- [ ] Add `__repr__` for debugging

### API Client Implementation
- [ ] Create `scraper/api/recent_changes.py`
- [ ] Implement `RecentChangesClient.__init__(api_client)`
- [ ] Implement `get_recent_changes()` method
- [ ] Implement `_parse_change_entry()` helper method
- [ ] Implement `_format_timestamp()` helper method
- [ ] Add comprehensive docstrings

### Testing (After Implementation)
- [ ] Write tests in `tests/test_recent_changes.py`
- [ ] Mock MediaWiki API responses
- [ ] Test all acceptance criteria
- [ ] Run tests: `pytest tests/test_recent_changes.py -v`
- [ ] Verify 80%+ code coverage
- [ ] Fix any failing tests

### Documentation
- [ ] Add module docstring to `recent_changes.py`
- [ ] Add usage examples in docstrings
- [ ] Document all parameters and return types
- [ ] Add type hints to all methods
- [ ] Document time range format requirements

## Technical Details

### File Structure
```
scraper/
├── api/
│   ├── __init__.py
│   ├── client.py              # Existing MediaWikiAPIClient
│   ├── recent_changes.py      # NEW: RecentChangesClient
│   └── exceptions.py
├── storage/
│   └── models.py              # Update with RecentChange dataclass

tests/
├── conftest.py                # Update with recent changes fixtures
├── test_recent_changes.py     # NEW: Recent changes tests
└── mocks/
    └── mock_api_client.py

fixtures/
└── api/
    ├── recentchanges_new_page.json     # NEW
    ├── recentchanges_edit.json         # NEW
    ├── recentchanges_delete.json       # NEW
    └── recentchanges_paginated.json    # NEW
```

### RecentChange Data Model

```python
# scraper/storage/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class ChangeType(Enum):
    """Type of change in recent changes feed."""
    NEW = "new"      # New page created
    EDIT = "edit"    # Existing page edited
    LOG = "log"      # Log event (delete, move, etc.)

class LogAction(Enum):
    """Type of log action for LOG change type."""
    DELETE = "delete"
    MOVE = "move"
    PROTECT = "protect"
    UPLOAD = "upload"
    OTHER = "other"

@dataclass
class RecentChange:
    """
    Represents a single change from MediaWiki recent changes feed.
    
    Attributes:
        rcid: Recent change ID (unique)
        type: Type of change (new, edit, log)
        namespace: Namespace ID of affected page
        title: Page title (with namespace prefix)
        pageid: Page ID (0 for deleted pages)
        revid: New revision ID (0 for non-edit changes)
        old_revid: Previous revision ID (0 for new pages)
        timestamp: When the change occurred
        user: Username who made the change
        userid: User ID (0 for anonymous users)
        comment: Edit comment or log comment
        oldlen: Previous content length in bytes
        newlen: New content length in bytes
        log_action: Log action type (only for LOG changes)
    """
    rcid: int
    type: ChangeType
    namespace: int
    title: str
    pageid: int
    revid: int
    old_revid: int
    timestamp: datetime
    user: str
    userid: int
    comment: str
    oldlen: int
    newlen: int
    log_action: Optional[LogAction] = None
    
    def __repr__(self) -> str:
        return (f"RecentChange(type={self.type.value}, title={self.title}, "
                f"timestamp={self.timestamp}, user={self.user})")
    
    @property
    def is_new_page(self) -> bool:
        """Check if this change created a new page."""
        return self.type == ChangeType.NEW
    
    @property
    def is_edit(self) -> bool:
        """Check if this change edited an existing page."""
        return self.type == ChangeType.EDIT
    
    @property
    def is_deletion(self) -> bool:
        """Check if this change deleted a page."""
        return self.type == ChangeType.LOG and self.log_action == LogAction.DELETE
    
    @property
    def size_change(self) -> int:
        """Calculate size change in bytes (positive = growth, negative = shrinkage)."""
        return self.newlen - self.oldlen
```

### RecentChangesClient Implementation

```python
# scraper/api/recent_changes.py
import logging
from datetime import datetime
from typing import List, Optional, Union
from .client import MediaWikiAPIClient
from .exceptions import APIError
from scraper.storage.models import RecentChange, ChangeType, LogAction

logger = logging.getLogger(__name__)

class RecentChangesClient:
    """
    Client for querying MediaWiki recent changes.
    
    Provides methods to fetch and parse recent changes from the MediaWiki
    recentchanges API, supporting time range filtering, namespace filtering,
    and automatic pagination.
    
    Example:
        >>> api = MediaWikiAPIClient("https://irowiki.org")
        >>> rc_client = RecentChangesClient(api)
        >>> changes = rc_client.get_recent_changes(
        ...     start=datetime(2026, 1, 1),
        ...     end=datetime(2026, 1, 31)
        ... )
        >>> print(f"Found {len(changes)} changes")
        Found 156 changes
    """
    
    def __init__(self, api_client: MediaWikiAPIClient):
        """
        Initialize recent changes client.
        
        Args:
            api_client: MediaWiki API client instance
        """
        self.api = api_client
    
    def get_recent_changes(
        self,
        start: datetime,
        end: datetime,
        namespace: Optional[Union[int, List[int]]] = None,
        change_type: Optional[Union[str, List[str]]] = None
    ) -> List[RecentChange]:
        """
        Fetch all recent changes within a time range.
        
        Automatically handles pagination to retrieve all changes. Results
        are returned in chronological order (oldest first).
        
        Args:
            start: Start of time range (inclusive)
            end: End of time range (inclusive)
            namespace: Filter to specific namespace(s) (optional)
            change_type: Filter to specific change type(s): 'new', 'edit', 'log' (optional)
            
        Returns:
            List of RecentChange objects, ordered chronologically
            
        Raises:
            ValueError: If start >= end
            APIError: If API request fails
            
        Example:
            >>> changes = client.get_recent_changes(
            ...     start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ...     end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            ...     namespace=0,
            ...     change_type='edit'
            ... )
        """
        if start >= end:
            raise ValueError(f"start must be before end: {start} >= {end}")
        
        logger.info(f"Fetching recent changes from {start} to {end}")
        
        # Build query parameters
        params = {
            'list': 'recentchanges',
            'rcstart': self._format_timestamp(start),
            'rcend': self._format_timestamp(end),
            'rcdir': 'newer',  # Oldest first
            'rclimit': 500,     # Max per request
            'rcprop': 'ids|title|timestamp|user|userid|comment|sizes|loginfo'
        }
        
        # Add namespace filter
        if namespace is not None:
            if isinstance(namespace, list):
                params['rcnamespace'] = '|'.join(str(ns) for ns in namespace)
            else:
                params['rcnamespace'] = str(namespace)
        
        # Add type filter
        if change_type is not None:
            if isinstance(change_type, list):
                params['rctype'] = '|'.join(change_type)
            else:
                params['rctype'] = change_type
        
        # Fetch all changes with pagination
        all_changes = []
        continue_token = None
        page_count = 0
        
        while True:
            # Add continue token for pagination
            if continue_token:
                params.update(continue_token)
            
            # Make API request
            response = self.api.query(params)
            
            # Parse changes from response
            if 'recentchanges' not in response.get('query', {}):
                logger.warning("No recentchanges in API response")
                break
            
            changes = response['query']['recentchanges']
            
            # Parse each change entry
            for change_data in changes:
                try:
                    change = self._parse_change_entry(change_data)
                    all_changes.append(change)
                except Exception as e:
                    logger.warning(f"Failed to parse change entry: {e}, data: {change_data}")
            
            page_count += 1
            logger.debug(f"Fetched page {page_count}, got {len(changes)} changes, "
                        f"total {len(all_changes)}")
            
            # Check for more pages
            if 'continue' not in response:
                break
            
            continue_token = response['continue']
        
        logger.info(f"Fetched {len(all_changes)} recent changes in {page_count} pages")
        return all_changes
    
    def _parse_change_entry(self, data: dict) -> RecentChange:
        """
        Parse a single recent change entry from API response.
        
        Args:
            data: Raw change data from API
            
        Returns:
            Parsed RecentChange object
            
        Raises:
            ValueError: If required fields are missing
        """
        # Parse change type
        change_type_str = data.get('type', 'edit')
        try:
            change_type = ChangeType(change_type_str)
        except ValueError:
            logger.warning(f"Unknown change type: {change_type_str}, defaulting to EDIT")
            change_type = ChangeType.EDIT
        
        # Parse log action (for log entries)
        log_action = None
        if change_type == ChangeType.LOG:
            log_action_str = data.get('logaction', 'other')
            try:
                log_action = LogAction(log_action_str)
            except ValueError:
                log_action = LogAction.OTHER
        
        # Parse timestamp
        timestamp_str = data.get('timestamp')
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        return RecentChange(
            rcid=data['rcid'],
            type=change_type,
            namespace=data['ns'],
            title=data['title'],
            pageid=data.get('pageid', 0),
            revid=data.get('revid', 0),
            old_revid=data.get('old_revid', 0),
            timestamp=timestamp,
            user=data.get('user', ''),
            userid=data.get('userid', 0),
            comment=data.get('comment', ''),
            oldlen=data.get('oldlen', 0),
            newlen=data.get('newlen', 0),
            log_action=log_action
        )
    
    def _format_timestamp(self, dt: datetime) -> str:
        """
        Format datetime for MediaWiki API.
        
        Args:
            dt: Datetime to format
            
        Returns:
            ISO 8601 timestamp string in UTC
        """
        # Convert to UTC if timezone-aware
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz=None)  # Convert to UTC
        
        # Format as ISO 8601
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
```

### Test Fixtures

```json
// fixtures/api/recentchanges_new_page.json
{
    "batchcomplete": "",
    "query": {
        "recentchanges": [
            {
                "rcid": 12345,
                "type": "new",
                "ns": 0,
                "title": "New_Page",
                "pageid": 2500,
                "revid": 100000,
                "old_revid": 0,
                "timestamp": "2026-01-15T10:30:00Z",
                "user": "Editor",
                "userid": 42,
                "comment": "Created new page about Poring",
                "oldlen": 0,
                "newlen": 1500
            }
        ]
    }
}
```

```json
// fixtures/api/recentchanges_edit.json
{
    "batchcomplete": "",
    "query": {
        "recentchanges": [
            {
                "rcid": 12346,
                "type": "edit",
                "ns": 0,
                "title": "Prontera",
                "pageid": 100,
                "revid": 100001,
                "old_revid": 99999,
                "timestamp": "2026-01-15T14:20:00Z",
                "user": "Admin",
                "userid": 1,
                "comment": "Updated NPC locations",
                "oldlen": 5000,
                "newlen": 5200
            }
        ]
    }
}
```

```json
// fixtures/api/recentchanges_delete.json
{
    "batchcomplete": "",
    "query": {
        "recentchanges": [
            {
                "rcid": 12347,
                "type": "log",
                "ns": 0,
                "title": "Spam_Page",
                "pageid": 0,
                "revid": 0,
                "old_revid": 0,
                "timestamp": "2026-01-16T09:00:00Z",
                "user": "Admin",
                "userid": 1,
                "comment": "Spam content",
                "logtype": "delete",
                "logaction": "delete",
                "oldlen": 0,
                "newlen": 0
            }
        ]
    }
}
```

### Usage Example

```python
from datetime import datetime, timezone
from scraper.api.client import MediaWikiAPIClient
from scraper.api.recent_changes import RecentChangesClient

# Initialize clients
api = MediaWikiAPIClient("https://irowiki.org")
rc_client = RecentChangesClient(api)

# Get all changes in January 2026
changes = rc_client.get_recent_changes(
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
)

print(f"Total changes: {len(changes)}")

# Analyze changes
new_pages = [c for c in changes if c.is_new_page]
edits = [c for c in changes if c.is_edit]
deletions = [c for c in changes if c.is_deletion]

print(f"New pages: {len(new_pages)}")
print(f"Edits: {len(edits)}")
print(f"Deletions: {len(deletions)}")

# Get only edits in main namespace
main_edits = rc_client.get_recent_changes(
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 1, 31, tzinfo=timezone.utc),
    namespace=0,
    change_type='edit'
)

print(f"Main namespace edits: {len(main_edits)}")
```

## Dependencies

### Requires
- Epic 01, Story 01: MediaWiki API Client
- Epic 01, Story 02: Rate Limiter
- Epic 02, Story 14: Data models (for RecentChange dataclass)

### Blocks
- Story 02: Change Detection Logic
- Story 03: Modified Page Detection
- Story 04: New Page Detection
- All incremental scraping stories

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] RecentChangesClient class implemented with full functionality
- [ ] RecentChange data model created with type hints
- [ ] All tests passing: `pytest tests/test_recent_changes.py -v`
- [ ] Test coverage ≥80% on recent_changes.py
- [ ] Type hints on all methods
- [ ] Comprehensive docstrings with examples
- [ ] No pylint warnings
- [ ] Code formatted with black
- [ ] Imports sorted with isort
- [ ] Manual test: Fetch real recent changes from irowiki.org
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Start with test infrastructure**: Create all fixtures and test utilities BEFORE writing client code
2. **Understand the API**: Read MediaWiki API docs for recentchanges
3. **Handle pagination carefully**: Test with >500 changes to verify continuation works
4. **Timezone handling**: Always work in UTC internally, convert at boundaries
5. **Type safety**: Use dataclasses and enums, not raw dictionaries

### Common Pitfalls

- **Forgetting pagination**: Recent changes can have thousands of entries
- **Timezone confusion**: MediaWiki uses UTC, be explicit about timezones
- **Missing log actions**: Not all change types have revisions
- **Deleted pages**: Have pageid=0, handle gracefully
- **Anonymous users**: Have userid=0, username is IP address

### Testing Strategy

- Mock all API calls with fixtures
- Test pagination with continue tokens
- Test time range filtering edge cases
- Test all change types (new, edit, log)
- Verify timezone conversion correctness
- Integration test with real API (optional, marked)

## References

- MediaWiki API: https://www.mediawiki.org/wiki/API:RecentChanges
- iRO Wiki API: https://irowiki.org/w/api.php?action=help&modules=query%2Brecentchanges
- Python datetime: https://docs.python.org/3/library/datetime.html
- Epic 03 Design: `docs/design/2026-01-XX_incremental_updates.md`
