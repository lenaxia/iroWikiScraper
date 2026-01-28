# Epic 07: CLI & Scraper Orchestration

**Epic ID**: epic-07  
**Priority**: Critical (Blocking Production Use)  
**Status**: In Progress  
**Estimated Effort**: 1-2 days

## Overview

Implement command-line interface and orchestration layer to connect all existing scraper components. Currently, the project has complete scraping, storage, and export functionality implemented as a library, but no way to actually run a scrape from the command line. This epic provides the "glue code" that makes the system usable in production.

## Problem Statement

The iRO Wiki Scraper project is **100% feature-complete as a library** with:
- ✅ Complete scraping logic (PageDiscovery, RevisionScraper, FileScraper)
- ✅ Full database storage (PageRepository, RevisionRepository, FileRepository)
- ✅ Incremental updates (IncrementalPageScraper with change detection)
- ✅ Export & packaging (XML generation, release packaging)
- ✅ 1005 passing tests covering all functionality
- ✅ CI/CD workflows configured

**What's Missing:**
- ❌ **CLI entry point** - No `__main__.py` or command-line interface
- ❌ **Full scrape orchestrator** - No coordinator that connects components for initial baseline scrape
- ❌ **Integration glue code** - No high-level interface that CLI → Scraper → Repository → Database
- ❌ **Workflow integration** - GitHub Actions workflows can't actually run scrapes

## Goals

1. Create command-line interface (`scraper/__main__.py`) supporting scrape operations
2. Implement full scrape orchestrator that coordinates baseline data collection
3. Connect all components: API → Scrapers → Repositories → Database storage
4. Enable GitHub Actions workflows to successfully execute scrapes
5. Support both full (baseline) and incremental scrape modes
6. Provide proper progress tracking, logging, and error handling

## Success Criteria

- ✅ `python -m scraper scrape` successfully runs a full scrape
- ✅ Data is actually stored to database (pages, revisions, files)
- ✅ Progress is tracked and logged during execution
- ✅ Incremental scrapes work after baseline established
- ✅ GitHub Actions workflows can trigger and complete scrapes
- ✅ Statistics can be generated from scraped data
- ✅ CLI supports configuration via arguments and YAML file
- ✅ Graceful error handling and resume capability

## User Stories

### CLI Foundation
- [Story 01: Command-Line Interface Structure](story-01_cli_structure.md)
- [Story 02: Argument Parsing and Validation](story-02_argument_parsing.md)
- [Story 03: Configuration Loading](story-03_configuration_loading.md)

### Full Scrape Orchestration
- [Story 04: Full Scrape Orchestrator](story-04_full_scrape_orchestrator.md)
- [Story 05: Page and Revision Pipeline](story-05_page_revision_pipeline.md)
- [Story 06: File Download Integration](story-06_file_download_integration.md)
- [Story 07: Link Extraction and Storage](story-07_link_extraction_storage.md)

### Progress and Logging
- [Story 08: Progress Tracking Integration](story-08_progress_tracking.md)
- [Story 09: Structured Logging](story-09_structured_logging.md)
- [Story 10: Error Handling and Recovery](story-10_error_handling.md)

### Incremental Integration
- [Story 11: Incremental Scrape Integration](story-11_incremental_integration.md)
- [Story 12: Scrape Mode Detection](story-12_scrape_mode_detection.md)

### Workflow Integration
- [Story 13: GitHub Actions Compatibility](story-13_github_actions_compatibility.md)
- [Story 14: Statistics Generation Fix](story-14_statistics_generation.md)

## Dependencies

### Requires:
- Epic 01: Core Scraper ✅ **Complete**
- Epic 02: Database Storage ✅ **Complete**
- Epic 03: Incremental Updates ✅ **Complete**

### Blocks:
- **Production deployment** - Cannot run scrapes without CLI
- **Automated workflows** - GitHub Actions currently fail
- **User adoption** - No way for users to actually use the system

## Technical Architecture

### Current State (Library-Only)

```
┌─────────────────────────────────────────┐
│  Existing Components (No Integration)   │
├─────────────────────────────────────────┤
│                                          │
│  API Clients:                            │
│    • MediaWikiAPIClient                  │
│    • RecentChangesClient                 │
│                                          │
│  Scrapers:                               │
│    • PageDiscovery                       │
│    • RevisionScraper                     │
│    • FileScraper                         │
│    • LinkExtractor                       │
│                                          │
│  Incremental:                            │
│    • IncrementalPageScraper              │
│    • ChangeDetector                      │
│                                          │
│  Storage:                                │
│    • PageRepository                      │
│    • RevisionRepository                  │
│    • FileRepository                      │
│    • LinkRepository                      │
│                                          │
│  ❌ NO CLI ENTRY POINT                   │
│  ❌ NO ORCHESTRATION LAYER               │
└─────────────────────────────────────────┘
```

### Target State (Production-Ready)

```
┌───────────────────────────────────────────────┐
│                 CLI Layer                      │
│  ┌─────────────────────────────────────────┐  │
│  │  scraper/__main__.py                    │  │
│  │    • Argument parsing                   │  │
│  │    • Configuration loading              │  │
│  │    • Command routing                    │  │
│  └─────────────────────────────────────────┘  │
└────────────────┬──────────────────────────────┘
                 │
┌────────────────▼──────────────────────────────┐
│          Orchestration Layer                   │
│  ┌─────────────────────────────────────────┐  │
│  │  FullScrapeOrchestrator                 │  │
│  │    • Coordinates all components         │  │
│  │    • Manages transaction boundaries     │  │
│  │    • Tracks progress                    │  │
│  │    • Handles errors                     │  │
│  └─────────────────────────────────────────┘  │
│                                                │
│  ┌─────────────────────────────────────────┐  │
│  │  IncrementalPageScraper (existing)      │  │
│  │    • Already has orchestration built-in │  │
│  └─────────────────────────────────────────┘  │
└────────────────┬──────────────────────────────┘
                 │
┌────────────────▼──────────────────────────────┐
│          Component Layer (Existing)            │
│    API → Scrapers → Repositories → Database   │
└───────────────────────────────────────────────┘
```

### Data Flow

```
1. User runs: python -m scraper scrape --database wiki.db
                          ↓
2. CLI parses args, loads config, creates database
                          ↓
3. Orchestrator initialized with API client + DB
                          ↓
4. Orchestrator calls PageDiscovery.discover_all_pages()
                          ↓
5. For each page:
   a. RevisionScraper.fetch_revisions(page_id)
   b. PageRepository.insert_page(page)
   c. RevisionRepository.insert_revisions_batch(revisions)
   d. FileScraper.download_files(page_files)
   e. LinkExtractor.extract_links(content)
   f. LinkRepository.store_links(links)
                          ↓
6. Progress tracked and logged throughout
                          ↓
7. Success/failure status returned to CLI
```

## Component Design

### 1. CLI Entry Point (`scraper/__main__.py`)

```python
"""Command-line interface for iRO Wiki Scraper."""

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    
    # Scrape command
    scrape_parser = subparsers.add_parser('scrape')
    scrape_parser.add_argument('--database', required=True)
    scrape_parser.add_argument('--config')
    scrape_parser.add_argument('--full', action='store_true')
    scrape_parser.add_argument('--incremental', action='store_true')
    
    args = parser.parse_args()
    return args.func(args)
```

### 2. Full Scrape Orchestrator

```python
"""Orchestrates a complete baseline scrape."""

class FullScrapeOrchestrator:
    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        database: Database,
        download_dir: Path,
    ):
        self.api = api_client
        self.db = database
        self.download_dir = download_dir
        
        # Initialize components
        self.page_discovery = PageDiscovery(api_client)
        self.revision_scraper = RevisionScraper(api_client)
        self.file_scraper = FileDownloader(api_client, download_dir)
        self.link_extractor = LinkExtractor()
        
        # Initialize repositories
        self.page_repo = PageRepository(database)
        self.revision_repo = RevisionRepository(database)
        self.file_repo = FileRepository(database)
        self.link_repo = LinkRepository(database)
    
    def scrape_all(
        self,
        namespaces: Optional[List[int]] = None
    ) -> ScrapeStats:
        """
        Perform complete baseline scrape.
        
        Returns:
            ScrapeStats with pages, revisions, files counts
        """
        logger.info("Starting full scrape")
        
        # 1. Discover all pages
        pages = self.page_discovery.discover_all_pages(namespaces)
        logger.info(f"Discovered {len(pages)} pages")
        
        stats = ScrapeStats()
        
        # 2. Process each page
        for page in tqdm(pages, desc="Scraping pages"):
            try:
                # Store page
                self.page_repo.insert_page(page)
                stats.pages_scraped += 1
                
                # Get and store revisions
                revisions = self.revision_scraper.fetch_revisions(page.page_id)
                self.revision_repo.insert_revisions_batch(revisions)
                stats.revisions_scraped += len(revisions)
                
                # Extract and store links
                for revision in revisions:
                    links = self.link_extractor.extract(revision.content)
                    self.link_repo.store_links(page.page_id, links)
                
                # Download files if file page
                if page.namespace == 6:  # File namespace
                    file_info = self.file_scraper.download(page.title)
                    if file_info:
                        self.file_repo.insert_file(file_info)
                        stats.files_downloaded += 1
                        
            except Exception as e:
                logger.error(f"Error scraping page {page.page_id}: {e}")
                stats.errors += 1
                continue
        
        logger.info(f"Scrape complete: {stats}")
        return stats
```

### 3. Mode Detection and Routing

```python
def cmd_scrape(args):
    """Execute scrape command."""
    
    # Initialize database
    db = Database(args.database)
    
    # Check if this is first run
    is_first_run = not db.has_data()
    
    if args.incremental and is_first_run:
        logger.error("Cannot run incremental scrape on empty database")
        logger.info("Run with --full first to establish baseline")
        return 1
    
    # Determine scrape mode
    if args.full or is_first_run:
        logger.info("Running FULL scrape")
        orchestrator = FullScrapeOrchestrator(api, db, download_dir)
        stats = orchestrator.scrape_all()
    else:
        logger.info("Running INCREMENTAL scrape")
        scraper = IncrementalPageScraper(api, db, download_dir)
        stats = scraper.scrape_incremental()
    
    logger.info(f"Scrape completed: {stats}")
    return 0
```

## Implementation Plan

### Phase 1: CLI Foundation (4 hours)
1. Create `scraper/__main__.py` with argparse setup
2. Implement configuration loading (YAML + arguments)
3. Add database initialization
4. Basic command routing

### Phase 2: Full Scrape Orchestrator (6 hours)
1. Create `FullScrapeOrchestrator` class
2. Integrate PageDiscovery → Repository pipeline
3. Integrate RevisionScraper → Repository pipeline
4. Add link extraction integration
5. Add file download integration
6. Implement progress tracking

### Phase 3: Integration and Testing (4 hours)
1. Connect CLI to orchestrator
2. Add incremental mode routing
3. Test full scrape end-to-end
4. Test incremental after baseline
5. Fix GitHub Actions workflow integration
6. Update statistics script

### Phase 4: Polish (2 hours)
1. Add error handling and recovery
2. Improve logging output
3. Add dry-run mode
4. Update documentation
5. Add usage examples

**Total Estimated Time: 16 hours (2 days)**

## Testing Strategy

### Unit Tests
- [ ] Test CLI argument parsing
- [ ] Test configuration loading
- [ ] Test orchestrator initialization
- [ ] Test mode detection logic

### Integration Tests
- [ ] Test full scrape on small dataset (10 pages)
- [ ] Test incremental scrape after baseline
- [ ] Test resume after interruption
- [ ] Test error recovery

### End-to-End Tests
- [ ] Test CLI → Orchestrator → Database flow
- [ ] Verify data actually stored to database
- [ ] Test GitHub Actions workflow execution
- [ ] Verify statistics generation works

## Known Limitations

1. **File download is I/O intensive** - May need threading/async for performance
2. **Large wikis require pagination** - Already implemented in PageDiscovery
3. **Memory usage with many pages** - May need batching for very large wikis
4. **No parallelization yet** - Single-threaded execution (can optimize later)

## Progress Tracking

| Story | Status | Estimate | Completed |
|-------|--------|----------|-----------|
| Story 01 | In Progress | 1h | - |
| Story 02 | Not Started | 1h | - |
| Story 03 | Not Started | 1h | - |
| Story 04 | Not Started | 2h | - |
| Story 05 | Not Started | 2h | - |
| Story 06 | Not Started | 1h | - |
| Story 07 | Not Started | 1h | - |
| Story 08 | Not Started | 1h | - |
| Story 09 | Not Started | 1h | - |
| Story 10 | Not Started | 2h | - |
| Story 11 | Not Started | 1h | - |
| Story 12 | Not Started | 1h | - |
| Story 13 | Not Started | 1h | - |
| Story 14 | Not Started | 1h | - |

**Total: 16 hours**

## Definition of Done

- [ ] All 14 user stories completed
- [ ] CLI successfully runs full scrape
- [ ] Data is stored to database (verified with queries)
- [ ] Incremental scrapes work after baseline
- [ ] GitHub Actions workflows pass
- [ ] Statistics script generates correct output
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Code reviewed and merged

## References

- Epic 01: Core Scraper (all components exist)
- Epic 02: Database Storage (repositories ready)
- Epic 03: Incremental Updates (IncrementalPageScraper ready)
- PROJECT_COMPLETE.md (confirms 100% library functionality)
