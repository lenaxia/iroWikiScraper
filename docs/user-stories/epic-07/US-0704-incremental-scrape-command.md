# US-0704: Incremental Scrape Command

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** ✅ Complete  
**Priority:** High  
**Story Points:** 3  
**Validation Report:** [US-0704-validation-report.md](US-0704-validation-report.md)

## User Story

As a user, I need an `incremental` command that updates my existing archive with recent changes, so that I can keep my archive up-to-date without re-scraping everything.

## Acceptance Criteria

1. **Command Implementation**
   - [x] Create `incremental_scrape_command(args: Namespace) -> int` in `scraper/cli/commands.py`
   - [x] Returns 0 on success, non-zero on failure
   - [x] Accepts parsed arguments from argparse

2. **Prerequisites Check**
   - [x] Verify database file exists
   - [x] Verify database has pages (not empty)
   - [x] Exit with clear error if baseline doesn't exist
   - [x] Suggest running `full` command first

3. **Configuration Loading**
   - [x] Load config from file if `--config` specified
   - [x] Use default config if no file specified
   - [x] Override config with CLI arguments
   - [x] Validate configuration

4. **Scraper Execution**
   - [x] Create MediaWikiAPIClient with config
   - [x] Create download directory for files
   - [x] Create IncrementalPageScraper with components
   - [x] Execute incremental scrape
   - [x] Handle FirstRunRequiresFullScrapeError specifically

5. **Result Reporting**
   - [x] Print formatted summary with separators
   - [x] Show pages new count
   - [x] Show pages modified count
   - [x] Show pages deleted count
   - [x] Show pages moved count
   - [x] Show revisions added count
   - [x] Show files downloaded count
   - [x] Show total pages affected
   - [x] Show duration

6. **Error Handling**
   - [x] Catch FirstRunRequiresFullScrapeError, exit with clear message
   - [x] Catch KeyboardInterrupt gracefully, exit 130
   - [x] Catch configuration errors, log and exit 1
   - [x] Catch API errors, log and exit 1
   - [x] Catch database errors, log and exit 1

7. **Exit Codes**
   - [x] 0 = Success
   - [x] 1 = Failure (database missing, API error, etc.)
   - [x] 130 = Interrupted by user

## Technical Details

### Command Structure

```python
def incremental_scrape_command(args: Namespace) -> int:
    try:
        # Setup logging
        _setup_logging(args.log_level)
        
        # Load configuration
        config = _load_config(args)
        
        # Check database exists
        if not config.storage.database_file.exists():
            logger.error("Database not found. Run 'scraper full' first.")
            return 1
        
        # Create components
        database = _create_database(config)
        api_client = MediaWikiAPIClient(...)
        download_dir = config.storage.data_dir / "files"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        scraper = IncrementalPageScraper(api_client, database, download_dir)
        
        # Print header
        print("Starting incremental scrape...")
        
        # Run scrape
        stats = scraper.scrape_incremental()
        
        # Print results
        print_summary(stats)
        
        return 0
        
    except FirstRunRequiresFullScrapeError as e:
        logger.error(str(e))
        print(f"\nERROR: {e}")
        print("Run 'scraper full' first to create baseline.")
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Incremental scrape failed: {e}", exc_info=True)
        return 1
```

### Output Format

```
Starting incremental scrape...

============================================================
INCREMENTAL SCRAPE COMPLETE
============================================================
Pages new:         12
Pages modified:    47
Pages deleted:     3
Pages moved:       2
Revisions added:   89
Files downloaded:  5
Total affected:    64
Duration:          18.7s
============================================================
```

### Error Output (No Baseline)

```
ERROR: Database not found: data/irowiki.db. Run 'scraper full' first to create baseline.
```

### Error Output (Empty Database)

```
ERROR: No previous scrape found. Run full scrape first.
Run 'scraper full' first to create baseline.
```

## Dependencies

- `scraper.config.Config`
- `scraper.api.client.MediaWikiAPIClient`
- `scraper.storage.database.Database`
- `scraper.incremental.page_scraper.IncrementalPageScraper`
- `scraper.incremental.page_scraper.FirstRunRequiresFullScrapeError`

## Testing Requirements

- [x] Unit tests for command with mock components (15 tests)
- [x] Test successful incremental returns 0
- [x] Test missing database returns 1 with clear error
- [x] Test FirstRunRequiresFullScrapeError is caught and reported
- [x] Test KeyboardInterrupt returns 130
- [x] Test --since parameter is passed correctly
- [x] Test --namespace filter is applied
- [x] Integration test with existing baseline database

## Documentation

- [x] Docstring for incremental_scrape_command()
- [x] Comments explaining each major section
- [x] Help text in argparser (US-0702)
- [x] Note in README about requiring baseline first

## Notes

- Incremental scraping requires an existing baseline from `full` command
- Must provide clear error messages when prerequisites not met
- Should be fast for small numbers of changes
- File downloads handled automatically for changed pages
