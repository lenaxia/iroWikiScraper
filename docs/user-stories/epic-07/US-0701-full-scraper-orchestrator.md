# US-0701: Full Scraper Orchestrator Class

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** In Progress  
**Priority:** High  
**Story Points:** 8

## User Story

As a developer, I need a FullScraper orchestrator class that coordinates all components for a complete baseline scrape, so that I can perform a full wiki scrape with a single function call.

## Acceptance Criteria

1. **Class Structure**
   - [ ] Create `scraper/orchestration/full_scraper.py`
   - [ ] Define `FullScraper` class with clear initialization
   - [ ] Define `ScrapeResult` dataclass for return values
   - [ ] Class accepts `Config`, `MediaWikiAPIClient`, and `Database` instances

2. **Core Functionality**
   - [ ] `scrape()` method orchestrates complete scrape workflow
   - [ ] Uses `PageDiscovery` to find all pages in specified namespaces
   - [ ] Uses `RevisionScraper` to fetch complete revision history
   - [ ] Uses `PageRepository` and `RevisionRepository` to store data
   - [ ] Handles default namespaces (0-15) if none specified

3. **Progress Tracking**
   - [ ] Optional progress callback parameter: `Callable[[str, int, int], None]`
   - [ ] Callback receives: stage name, current count, total count
   - [ ] Called during discovery phase (per namespace)
   - [ ] Called during scrape phase (per page batch)

4. **Error Handling**
   - [ ] Catches exceptions per namespace (continues with others)
   - [ ] Catches exceptions per page (continues with others)
   - [ ] Records errors in `ScrapeResult.errors` list
   - [ ] Records failed page IDs in `ScrapeResult.failed_pages` list
   - [ ] Returns success status in `ScrapeResult.success` property

5. **Result Reporting**
   - [ ] `ScrapeResult` includes pages_count
   - [ ] `ScrapeResult` includes revisions_count
   - [ ] `ScrapeResult` includes namespaces_scraped
   - [ ] `ScrapeResult` includes start_time and end_time
   - [ ] `ScrapeResult` includes duration property (in seconds)
   - [ ] `ScrapeResult` includes errors list
   - [ ] `ScrapeResult` includes failed_pages list

6. **Performance**
   - [ ] Uses batch insert for pages (per namespace)
   - [ ] Uses batch insert for revisions (per page)
   - [ ] Logs progress at regular intervals
   - [ ] Respects rate limiting from config

## Technical Details

### Class Signature

```python
class FullScraper:
    def __init__(
        self,
        config: Config,
        api_client: MediaWikiAPIClient,
        database: Database,
    ):
        ...
    
    def scrape(
        self,
        namespaces: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ScrapeResult:
        ...
```

### ScrapeResult Dataclass

```python
@dataclass
class ScrapeResult:
    pages_count: int = 0
    revisions_count: int = 0
    namespaces_scraped: List[int] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    failed_pages: List[int] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        ...
    
    @property
    def success(self) -> bool:
        ...
```

### Workflow Steps

1. **Initialize** - Create PageDiscovery, RevisionScraper, repositories
2. **Discover** - For each namespace, discover all pages and store immediately
3. **Scrape** - For each page, fetch revisions and store in batches
4. **Report** - Return ScrapeResult with statistics and errors

## Dependencies

- `scraper.api.client.MediaWikiAPIClient`
- `scraper.config.Config`
- `scraper.scrapers.page_scraper.PageDiscovery`
- `scraper.scrapers.revision_scraper.RevisionScraper`
- `scraper.storage.database.Database`
- `scraper.storage.page_repository.PageRepository`
- `scraper.storage.revision_repository.RevisionRepository`

## Testing Requirements

- [ ] Unit tests for FullScraper initialization
- [ ] Unit tests for scrape() with mock API and database
- [ ] Test progress callback is called correctly
- [ ] Test error handling (namespace failure, page failure)
- [ ] Test ScrapeResult calculation (duration, success)
- [ ] Integration test with small wiki subset

## Documentation

- [ ] Docstrings for FullScraper class
- [ ] Docstrings for scrape() method
- [ ] Docstrings for ScrapeResult dataclass
- [ ] Example usage in module docstring

## Notes

- This is the core orchestration layer that connects all library components
- Must be robust to partial failures (continue on errors)
- Progress callback allows CLI to show real-time updates
- Batch operations critical for performance with large wikis
