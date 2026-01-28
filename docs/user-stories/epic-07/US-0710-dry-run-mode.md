# US-0710: Dry Run Mode

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** Pending  
**Priority:** Low  
**Story Points:** 2

## User Story

As a user, I need a dry-run mode that shows what would be scraped without actually doing it, so that I can estimate time and storage requirements before starting a full scrape.

## Acceptance Criteria

1. **Dry Run Flag**
   - [ ] `--dry-run` flag available for `full` command
   - [ ] Not available for `incremental` command
   - [ ] Clearly indicates dry-run mode in output

2. **Discovery Only**
   - [ ] Discovers all pages via PageDiscovery
   - [ ] Does NOT scrape revisions
   - [ ] Does NOT store any data to database
   - [ ] Does NOT make revision API calls

3. **Statistics Display**
   - [ ] Show total pages that would be scraped
   - [ ] Show breakdown by namespace
   - [ ] Show estimated API calls (pages + revisions estimate)
   - [ ] Show estimated duration (based on rate limit)

4. **Output Clarity**
   - [ ] Print "DRY RUN MODE" header
   - [ ] Use "Would scrape..." language
   - [ ] Print "DRY RUN COMPLETE" footer
   - [ ] No database file created

## Technical Details

### Dry Run Implementation

```python
if args.dry_run:
    print("DRY RUN MODE: Will discover pages but not scrape revisions")
    
    # Only discover pages
    discovery = PageDiscovery(api_client)
    pages = discovery.discover_all_pages(namespaces)
    
    print(f"\nDRY RUN COMPLETE")
    print(f"Would scrape {len(pages)} pages")
    
    # Show breakdown by namespace
    from collections import Counter
    ns_counts = Counter(p.namespace for p in pages)
    print("\nBreakdown by namespace:")
    for ns in sorted(ns_counts.keys()):
        print(f"  Namespace {ns}: {ns_counts[ns]} pages")
    
    # Estimate API calls and duration
    estimated_calls = len(pages)  # Discovery + revision calls per page
    estimated_duration = estimated_calls / config.scraper.rate_limit
    
    print(f"\nEstimated API calls: {estimated_calls:,}")
    print(f"Estimated duration: {estimated_duration:.0f}s ({estimated_duration/60:.1f}m)")
    
    return 0
```

### Dry Run Output Example

```
DRY RUN MODE: Will discover pages but not scrape revisions

Starting full scrape...
Namespaces: [0, 4, 6, 10, 14]

[discover] 1/5 (20.0%)
[discover] 2/5 (40.0%)
[discover] 3/5 (60.0%)
[discover] 4/5 (80.0%)
[discover] 5/5 (100.0%)

DRY RUN COMPLETE
Would scrape 2,400 pages

Breakdown by namespace:
  Namespace 0: 1,842 pages
  Namespace 4: 234 pages
  Namespace 6: 156 pages
  Namespace 10: 102 pages
  Namespace 14: 66 pages

Estimated API calls: 2,400
Estimated duration: 1200s (20.0m) at 2.0 req/sec

NOTE: Actual duration will be longer due to revision scraping
      and may vary based on page complexity.
```

### Usage Examples

```bash
# Dry run for all namespaces
python -m scraper full --dry-run

# Dry run for specific namespaces
python -m scraper full --namespace 0 4 --dry-run

# Dry run with custom rate limit (for estimation)
python -m scraper full --dry-run --rate-limit 1.0
```

## Dependencies

- `scraper.scrapers.page_scraper.PageDiscovery`
- `collections.Counter` for namespace breakdown

## Testing Requirements

- [ ] Test dry-run discovers pages
- [ ] Test dry-run does NOT call revision API
- [ ] Test dry-run does NOT create database
- [ ] Test dry-run shows correct statistics
- [ ] Test dry-run estimates are reasonable
- [ ] Test dry-run works with namespace filter

## Documentation

- [ ] Document --dry-run flag in README
- [ ] Document dry-run output format
- [ ] Add dry-run examples to README
- [ ] Note limitations of estimates

## Notes

- Dry run helps users plan scrapes and storage
- Discovery API calls are fast (500 pages per call)
- Revision scraping is much slower (need to call per page)
- Estimates are approximate - actual time varies
- Consider showing sample page titles in output
