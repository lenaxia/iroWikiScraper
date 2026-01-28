# US-0702: CLI Argument Parsing

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** ✅ Complete  
**Priority:** High  
**Story Points:** 3  
**Completed:** 2026-01-24

## User Story

As a user, I need a well-designed command-line interface with clear arguments and help text, so that I can easily run scrapes with appropriate options.

## Acceptance Criteria

1. **File Structure**
   - [x] Create `scraper/cli/args.py`
   - [x] Create `create_parser()` function that returns configured ArgumentParser

2. **Global Arguments**
   - [x] `--config PATH` - Path to YAML configuration file (optional)
   - [x] `--database PATH` - Path to SQLite database file (optional)
   - [x] `--log-level LEVEL` - Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - [x] `--quiet` - Suppress progress output (errors still shown)

3. **Subcommands**
   - [x] `full` - Full scrape command
   - [x] `incremental` - Incremental scrape command
   - [x] Subcommands are required (user must choose one)

4. **Full Scrape Arguments**
   - [x] `--namespace NS [NS ...]` - Namespace IDs to scrape (optional, default: all)
   - [x] `--rate-limit RATE` - Maximum requests per second (default: 2.0)
   - [x] `--force` - Force scrape even if data exists
   - [x] `--dry-run` - Discover pages but don't scrape revisions

5. **Incremental Scrape Arguments**
   - [x] `--since TIMESTAMP` - Only scrape changes since timestamp (optional)
   - [x] `--namespace NS [NS ...]` - Limit to specific namespaces (optional)
   - [x] `--rate-limit RATE` - Maximum requests per second (default: 2.0)

6. **Help Text**
   - [x] Clear program description
   - [x] Clear subcommand descriptions
   - [x] Helpful argument descriptions with defaults shown
   - [x] Example usage in epilog or help text

## Technical Details

### Parser Structure

```python
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="iRO Wiki Scraper - Archive MediaWiki content",
        epilog="For more information, visit https://github.com/lenaxia/iroWikiScraper",
    )
    
    # Global options
    parser.add_argument("--config", type=Path, help="...")
    parser.add_argument("--database", type=Path, help="...")
    parser.add_argument("--log-level", choices=[...], help="...")
    parser.add_argument("--quiet", action="store_true", help="...")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Full scrape
    full_parser = subparsers.add_parser("full", help="...")
    full_parser.add_argument("--namespace", type=int, nargs="+", help="...")
    full_parser.add_argument("--rate-limit", type=float, default=2.0, help="...")
    full_parser.add_argument("--force", action="store_true", help="...")
    full_parser.add_argument("--dry-run", action="store_true", help="...")
    
    # Incremental scrape
    incr_parser = subparsers.add_parser("incremental", help="...")
    incr_parser.add_argument("--since", type=str, help="...")
    incr_parser.add_argument("--namespace", type=int, nargs="+", help="...")
    incr_parser.add_argument("--rate-limit", type=float, default=2.0, help="...")
    
    return parser
```

### Usage Examples

```bash
# Full scrape with defaults
python -m scraper full

# Full scrape specific namespaces
python -m scraper full --namespace 0 4 6

# Full scrape with custom rate limit
python -m scraper full --rate-limit 1.0

# Dry run to see what would be scraped
python -m scraper full --dry-run

# Incremental update
python -m scraper incremental

# Incremental since specific time
python -m scraper incremental --since 2025-01-01T00:00:00Z

# With custom config and database
python -m scraper --config config.yaml --database wiki.db full
```

## Dependencies

- `argparse` (Python standard library)
- `pathlib.Path` for path arguments

## Testing Requirements

- [x] Test parser creation succeeds
- [x] Test parsing valid full scrape arguments
- [x] Test parsing valid incremental scrape arguments
- [x] Test default values are applied
- [x] Test invalid arguments are rejected
- [x] Test help text is generated correctly
- [x] Test required subcommand enforcement
- [x] Test terminal handling (no interference with scrolling/history)
- [x] Test Ctrl+C handling and exit codes

## Documentation

- [x] Docstrings for create_parser()
- [x] Comment explaining each argument group
- [x] Help text for each argument includes defaults

## Implementation Summary

**Files Created/Modified:**
- `scraper/cli/args.py` - Argument parser with all required options
- `scraper/__main__.py` - Updated main entry point with signal handling
- `tests/test_cli_args.py` - 46 tests for argument parsing
- `tests/test_cli_terminal.py` - 18 tests for terminal handling

**Test Coverage:** 64/64 tests passing (100%)

**Terminal Handling Verified:**
- ✅ No progress bars (uses simple print statements)
- ✅ No terminal mode changes (arrow keys work normally)
- ✅ Scroll wheel works (standard output)
- ✅ Ctrl+C handling (exits with code 130)
- ✅ Terminal state restored on exit

**Validation:** See `US-0702-VALIDATION.md` for detailed validation report

## Notes

- Use `argparse` for consistency with Python ecosystem ✅
- Keep argument names consistent with config file structure ✅
- Provide sensible defaults for all optional arguments ✅
- Help text should be clear for non-technical users ✅
- **CRITICAL:** Terminal handling preserves normal functionality ✅
