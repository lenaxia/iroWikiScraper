# US-0703: Full Scrape Command

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** In Progress  
**Priority:** High  
**Story Points:** 5

## User Story

As a user, I need a `full` command that performs a complete baseline scrape of the wiki, so that I can create an initial archive with all pages and revision history.

## Acceptance Criteria

1. **Command Implementation**
   - [ ] Create `full_scrape_command(args: Namespace) -> int` in `scraper/cli/commands.py`
   - [ ] Returns 0 on success, non-zero on failure
   - [ ] Accepts parsed arguments from argparse

2. **Configuration Loading**
   - [ ] Load config from file if `--config` specified
   - [ ] Use default config if no file specified
   - [ ] Override config with CLI arguments (rate-limit, database)
   - [ ] Validate configuration before proceeding

3. **Logging Setup**
   - [ ] Configure logging based on `--log-level`
   - [ ] Set appropriate format for CLI output
   - [ ] Log to console with timestamps

4. **Database Initialization**
   - [ ] Create database parent directory if needed
   - [ ] Initialize database schema
   - [ ] Check for existing data if `--force` not specified
   - [ ] Prompt user or exit if data exists without --force

5. **Scraper Execution**
   - [ ] Create MediaWikiAPIClient with config
   - [ ] Create FullScraper with components
   - [ ] Determine namespaces (from args or defaults)
   - [ ] Execute scrape with progress callback (if not --quiet)
   - [ ] Handle dry-run mode (discovery only, no storage)

6. **Progress Display**
   - [ ] Print "Starting full scrape..." header
   - [ ] Print namespace list being scraped
   - [ ] Show progress during discovery phase
   - [ ] Show progress during scrape phase
   - [ ] Print final statistics summary

7. **Result Reporting**
   - [ ] Print formatted summary with separators
   - [ ] Show pages scraped count
   - [ ] Show revisions scraped count
   - [ ] Show duration
   - [ ] Show namespaces list
   - [ ] Show failed pages (if any)
   - [ ] Show error messages (if any)

8. **Error Handling**
   - [ ] Catch KeyboardInterrupt (Ctrl+C) gracefully, exit 130
   - [ ] Catch configuration errors, log and exit 1
   - [ ] Catch API errors, log and exit 1
   - [ ] Catch database errors, log and exit 1
   - [ ] Allow partial success (some pages failed but others succeeded)

9. **Exit Codes**
   - [ ] 0 = Complete success
   - [ ] 1 = Failure or >10% of pages failed
   - [ ] 130 = Interrupted by user (Ctrl+C)

## Technical Details

### Command Structure

```python
def full_scrape_command(args: Namespace) -> int:
    try:
        # Setup logging
        _setup_logging(args.log_level)
        
        # Load configuration
        config = _load_config(args)
        
        # Check for existing data (if not --force)
        if not args.force:
            # Check database and warn/exit if data exists
            ...
        
        # Dry run check
        if args.dry_run:
            # Only discover, don't scrape
            ...
        
        # Create components
        database = _create_database(config)
        api_client = MediaWikiAPIClient(...)
        scraper = FullScraper(config, api_client, database)
        
        # Print header
        print("Starting full scrape...")
        
        # Run scrape
        result = scraper.scrape(
            namespaces=args.namespace,
            progress_callback=None if args.quiet else _print_progress
        )
        
        # Print results
        print_summary(result)
        
        # Return exit code
        return 0 if result.success else 1
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Full scrape failed: {e}", exc_info=True)
        return 1
```

### Output Format

```
Starting full scrape...
Namespaces: [0, 4, 6, 10, 14]

[discover] 1/5 (20.0%)
[discover] 2/5 (40.0%)
...
[scrape] 100/2400 (4.2%)
[scrape] 200/2400 (8.3%)
...

============================================================
FULL SCRAPE COMPLETE
============================================================
Pages scraped:     2400
Revisions scraped: 15832
Duration:          245.3s
Namespaces:        [0, 4, 6, 10, 14]
Failed pages:      3
  IDs: [142, 589, 1023]
============================================================
```

### Dry Run Output

```
DRY RUN MODE: Will discover pages but not scrape revisions

Starting full scrape...
Namespaces: all common namespaces (0-15)

[discover] 1/16 (6.2%)
[discover] 2/16 (12.5%)
...

DRY RUN COMPLETE
Would scrape 2400 pages

Breakdown by namespace:
  Namespace 0: 1842 pages
  Namespace 4: 234 pages
  Namespace 6: 156 pages
  ...
```

## Dependencies

- `scraper.config.Config`
- `scraper.api.client.MediaWikiAPIClient`
- `scraper.storage.database.Database`
- `scraper.orchestration.full_scraper.FullScraper`
- `scraper.scrapers.page_scraper.PageDiscovery` (for dry-run)

## Testing Requirements

- [ ] Unit tests for command with mock components
- [ ] Test successful scrape returns 0
- [ ] Test failed scrape returns 1
- [ ] Test KeyboardInterrupt returns 130
- [ ] Test --force flag bypasses existing data check
- [ ] Test --dry-run only discovers pages
- [ ] Test --quiet suppresses progress output
- [ ] Test progress callback is invoked (when not quiet)
- [ ] Integration test with small wiki subset

## Documentation

- [ ] Docstring for full_scrape_command()
- [ ] Comments explaining each major section
- [ ] Help text in argparser (US-0702)

## Notes

- This is the primary command users will run to initialize their archive
- Must be robust to network issues and partial failures
- Progress display helps users understand long-running operations
- Dry-run mode useful for estimating time/space before full scrape
