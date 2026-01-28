# US-0712: CLI Documentation and Help

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** Pending  
**Priority:** Low  
**Story Points:** 2

## User Story

As a user, I need comprehensive CLI documentation and help text, so that I can understand how to use the scraper effectively without reading source code.

## Acceptance Criteria

1. **Built-in Help**
   - [ ] `python -m scraper --help` shows main help
   - [ ] `python -m scraper full --help` shows full command help
   - [ ] `python -m scraper incremental --help` shows incremental help
   - [ ] Help text includes examples

2. **README Documentation**
   - [ ] Installation instructions
   - [ ] Quick start guide
   - [ ] Command reference (all commands and flags)
   - [ ] Configuration file format
   - [ ] Examples for common use cases
   - [ ] Troubleshooting section

3. **Usage Examples**
   - [ ] Basic full scrape
   - [ ] Full scrape with specific namespaces
   - [ ] Dry run example
   - [ ] Incremental scrape example
   - [ ] Custom configuration example
   - [ ] GitHub Actions integration example

4. **Error Messages**
   - [ ] Clear, actionable error messages
   - [ ] Suggest fixes for common errors
   - [ ] Include relevant context (file paths, values)

5. **FAQ Section**
   - [ ] How long does a full scrape take?
   - [ ] How much disk space is needed?
   - [ ] What if scrape is interrupted?
   - [ ] How to resume a failed scrape?
   - [ ] What rate limit should I use?
   - [ ] How to scrape only specific namespaces?

## Technical Details

### Main Help Output

```
$ python -m scraper --help

usage: scraper [-h] [--config PATH] [--database PATH] 
               [--log-level LEVEL] [--quiet]
               {full,incremental} ...

iRO Wiki Scraper - Archive MediaWiki content

positional arguments:
  {full,incremental}
    full              Perform a full scrape of the wiki
    incremental       Perform an incremental update

optional arguments:
  -h, --help          show this help message and exit
  --config PATH       Path to configuration YAML file
  --database PATH     Path to SQLite database file (default: data/irowiki.db)
  --log-level LEVEL   Set logging level (default: INFO)
  --quiet             Suppress progress output

For more information, visit https://github.com/lenaxia/iroWikiScraper
```

### Full Command Help

```
$ python -m scraper full --help

usage: scraper full [-h] [--namespace NS [NS ...]] 
                    [--rate-limit RATE] [--force] [--dry-run]

Scrape all pages and their complete revision history from the wiki

optional arguments:
  -h, --help            show this help message and exit
  --namespace NS [NS ...]
                        Namespace IDs to scrape (default: 0-15)
  --rate-limit RATE     Maximum requests per second (default: 2.0)
  --force               Force scrape even if data already exists
  --dry-run             Discover pages but don't scrape revisions

Examples:
  # Full scrape with defaults
  python -m scraper full

  # Scrape specific namespaces only
  python -m scraper full --namespace 0 4 6

  # Dry run to estimate time
  python -m scraper full --dry-run
```

### README Structure

```markdown
# iRO Wiki Scraper

Archive and preserve MediaWiki content with full revision history.

## Installation

## Quick Start

## Usage

### Full Scrape
### Incremental Scrape
### Configuration File
### Command Reference

## Examples

### Example 1: Basic Full Scrape
### Example 2: Scrape Specific Namespaces
### Example 3: Incremental Updates
### Example 4: Custom Configuration

## Configuration

### Configuration File Format
### Available Options

## GitHub Actions

### Automated Monthly Scrapes
### Manual Workflow Triggers

## Troubleshooting

### Common Errors
### Performance Tips
### Resume Failed Scrapes

## FAQ

## Development

## License
```

### Error Message Examples

Bad:
```
Error: Database error
```

Good:
```
ERROR: Cannot write to database: data/irowiki.db
Reason: Permission denied

Suggestions:
  - Check file permissions: chmod 644 data/irowiki.db
  - Check directory permissions: chmod 755 data/
  - Ensure you have write access to the data/ directory
```

## Dependencies

- `argparse` help text formatting
- Markdown for README

## Testing Requirements

- [ ] Verify help text is accurate
- [ ] Verify examples in README work
- [ ] Test all documented commands
- [ ] Verify configuration examples are valid
- [ ] Check for broken links in documentation

## Documentation

- [ ] README.md with complete usage guide
- [ ] CLI help text for all commands
- [ ] Example configuration file (config.example.yaml)
- [ ] CONTRIBUTING.md for developers
- [ ] FAQ.md with common questions

## Notes

- Good documentation reduces support burden
- Examples should be copy-pasteable
- Help text should fit in 80-column terminal
- Consider adding man page for Unix systems
- Keep README up-to-date with code changes
