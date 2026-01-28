# Epic 07: CLI and Orchestration Layer

**Status:** In Progress  
**Priority:** Critical  
**Target:** v1.1.0

## Overview

Create a command-line interface and orchestration layer that allows users to actually run the scraper. Currently, the project has all the library components (API client, scrapers, storage) but no way to execute a scrape from the command line.

## Problem Statement

The iRO-Wiki-Scraper project is feature-complete as a library (1005 passing tests, all 6 prior epics completed), but **cannot be run**. There is no CLI entry point, no orchestration layer connecting the components, and GitHub Actions workflows fail because there's no working scraper to execute.

## Goals

1. Create a `FullScraper` orchestrator that coordinates page discovery, revision scraping, and storage
2. Create a CLI with `full` and `incremental` commands
3. Integrate with GitHub Actions workflows for automated scraping
4. Add progress tracking, error handling, and logging
5. Support all scrape configurations (namespaces, rate limits, dry-run, etc.)

## User Stories

### High Priority (Must Have)

- **US-0701**: Full Scraper Orchestrator Class (8 pts) ✅ **COMPLETED**
  - Core orchestration layer that connects all library components
  - Coordinates page discovery, revision scraping, and storage
  - Returns ScrapeResult with statistics

- **US-0702**: CLI Argument Parsing (3 pts) ✅ **COMPLETED**
  - Command-line interface with argparse
  - Global options and subcommands (full, incremental)
  - Clear help text and examples

- **US-0703**: Full Scrape Command (5 pts) ✅ **COMPLETED**
  - `python -m scraper full` command
  - Performs complete baseline scrape
  - Progress display and statistics output

- **US-0704**: Incremental Scrape Command (3 pts) - **IN PROGRESS**
  - `python -m scraper incremental` command
  - Updates existing archive with recent changes
  - Requires prior full scrape baseline

- **US-0708**: GitHub Actions Integration (2 pts) - **PENDING**
  - Update workflows to use new CLI commands
  - Support both full and incremental modes
  - Pass workflow parameters correctly

### Medium Priority (Should Have)

- **US-0705**: Progress Tracking and Logging (3 pts) - **PENDING**
  - Clear progress updates during long scrapes
  - Configurable log levels
  - Summary output at completion

- **US-0706**: Error Handling and Recovery (5 pts) - **PENDING**
  - Robust error handling with retries
  - Continue on partial failures
  - Clear error reporting

- **US-0707**: Configuration Management (2 pts) - **PENDING**
  - Load config from YAML file
  - Override with CLI arguments
  - Proper precedence order

- **US-0709**: Statistics and Reporting (2 pts) - **PENDING**
  - Detailed statistics about scrape results
  - Breakdown by namespace
  - Optional JSON output

### Low Priority (Nice to Have)

- **US-0710**: Dry Run Mode (2 pts) - **PENDING**
  - Discover pages without scraping
  - Estimate time and storage requirements
  - Useful for planning

- **US-0711**: Resume Failed Scrapes (5 pts) - **PENDING**
  - Checkpoint tracking during scrape
  - Resume from last checkpoint after interruption
  - Idempotent operations

- **US-0712**: CLI Documentation and Help (2 pts) - **PENDING**
  - Comprehensive README with examples
  - Built-in help text for all commands
  - FAQ and troubleshooting guide

## Total Story Points

- **Total:** 42 points
- **Completed:** 16 points (38%)
- **In Progress:** 3 points (7%)
- **Pending:** 23 points (55%)

## Success Criteria

The epic is complete when:

1. ✅ Can run `python -m scraper full` and it completes a full scrape
2. ✅ Can run `python -m scraper incremental` and it updates changed pages
3. ✅ Data is stored in SQLite database
4. ⏳ Progress is logged during scraping
5. ⏳ Errors are handled gracefully
6. ⏳ GitHub Actions workflows complete successfully
7. ⏳ Tests cover the new orchestration and CLI code
8. ⏳ Documentation explains how to use the CLI

## Dependencies

### External Dependencies
- `argparse` (Python stdlib)
- `logging` (Python stdlib)
- `pathlib` (Python stdlib)

### Internal Dependencies
- All existing library components:
  - `scraper.api.client.MediaWikiAPIClient`
  - `scraper.scrapers.page_scraper.PageDiscovery`
  - `scraper.scrapers.revision_scraper.RevisionScraper`
  - `scraper.storage.database.Database`
  - `scraper.storage.page_repository.PageRepository`
  - `scraper.storage.revision_repository.RevisionRepository`
  - `scraper.incremental.page_scraper.IncrementalPageScraper`
  - `scraper.config.Config`

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ CLI Layer (NEW)                                              │
├─────────────────────────────────────────────────────────────┤
│ scraper/__main__.py        - Entry point                    │
│ scraper/cli/args.py        - Argument parsing               │
│ scraper/cli/commands.py    - Command implementations        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Orchestration Layer (NEW)                                   │
├─────────────────────────────────────────────────────────────┤
│ scraper/orchestration/full_scraper.py  - Full scrape        │
│ scraper/orchestration/progress.py      - Progress tracking  │
│ scraper/orchestration/recovery.py      - Checkpoints        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Library Components (EXISTING)                               │
├─────────────────────────────────────────────────────────────┤
│ • PageDiscovery        → Find all pages                     │
│ • RevisionScraper      → Get revision history               │
│ • FileScraper          → Download files                     │
│ • PageRepository       → Store pages                        │
│ • RevisionRepository   → Store revisions                    │
│ • FileRepository       → Store files                        │
│ • IncrementalPageScraper → Update changes                   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Minimal Working Implementation ✅ **COMPLETED**
1. ✅ Create FullScraper orchestrator (US-0701)
2. ✅ Create CLI argument parsing (US-0702)
3. ✅ Create full scrape command (US-0703)
4. ⏳ Test locally with small namespace
5. ⏳ Update workflows to use new CLI

### Phase 2: Robustness (IN PROGRESS)
1. ⏳ Add error handling and retry logic (US-0706)
2. ⏳ Add progress tracking with estimates (US-0705)
3. ⏳ Complete incremental command (US-0704)
4. ⏳ Write comprehensive tests
5. ⏳ Update GitHub Actions workflows (US-0708)

### Phase 3: Polish (PLANNED)
1. ⏳ Add statistics and reporting (US-0709)
2. ⏳ Add configuration file support (US-0707)
3. ⏳ Add dry-run mode (US-0710)
4. ⏳ Add resume capability (US-0711)
5. ⏳ Update README with usage examples (US-0712)

## Testing Strategy

### Unit Tests
- `tests/orchestration/test_full_scraper.py` - Test FullScraper
- `tests/cli/test_args.py` - Test argument parsing
- `tests/cli/test_commands.py` - Test command execution
- `tests/orchestration/test_progress.py` - Test progress tracking

### Integration Tests
- End-to-end test with small wiki subset
- Test full scrape populates database correctly
- Test incremental scrape updates correctly
- Test GitHub Actions workflow integration

### Manual Testing
```bash
# Test full scrape
python -m scraper full --namespace 4 --dry-run
python -m scraper full --namespace 4

# Test incremental scrape
python -m scraper incremental

# Test with configuration
python -m scraper --config config.yaml full
```

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API client signature mismatch | High | Medium | Check MediaWikiAPIClient constructor parameters |
| Database path type mismatch | Medium | High | Convert Path to str for Database() |
| Progress callback interface mismatch | Low | Medium | Define clear callback signature |
| Incremental scraper missing methods | High | Low | IncrementalPageScraper already exists and works |

## Known Issues

1. **Type Mismatches in commands.py**:
   - Database() expects str, not Path → Fix: Convert Path to str
   - MediaWikiAPIClient() missing api_path parameter → Fix: Check actual constructor
   - Need to verify IncrementalStats has start_time/end_time attributes

2. **LSP Errors**:
   - Several type errors in scraper/cli/commands.py
   - Need to fix before testing

## Timeline

- **Start Date:** 2025-01-24
- **Target Completion:** 2025-01-25
- **Actual Completion:** TBD

## References

- [Original Project Completion Summary](../../completion-summary.md)
- [GitHub Actions Manual Scrape Workflow](../../.github/workflows/manual-scrape.yml)
- [GitHub Actions Monthly Scrape Workflow](../../.github/workflows/monthly-scrape.yml)
- [All User Stories](../user-stories/epic-07/)
