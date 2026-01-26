# Full Scrape Timing Documentation

## Scrape Started
- **Date:** 2026-01-25
- **Start Time:** 23:19:28 UTC
- **Configuration:**
  - Namespaces: 0-15 (all standard namespaces)
  - Rate limit: 1 request/second
  - Resume: Fresh start (no checkpoint)
  - Force: Yes (overwrite existing data)

## Expected Timeline

Based on discovery phase:
- **Total pages discovered:** ~7,000-8,000 pages
- **Estimated revisions:** 50,000-150,000 (depends on edit history)
- **Rate:** ~1,800-3,600 pages/hour (at 1 req/sec)
- **Estimated duration:** 3-12 hours

### Discovery Phase (First ~1 minute)
- Namespace 0 (Main): 4,047 pages ✓
- Namespace 1 (Talk): 346 pages ✓
- Namespace 2 (User): 800 pages ✓
- Namespace 3 (User talk): 639 pages ✓
- Namespace 4-15: In progress...

### Revision Scraping Phase
- This is the time-consuming part
- Each page requires 1+ API requests
- Pages with many revisions need multiple requests (pagination)
- At 1 req/sec: ~1-2 hours per 1,000 pages minimum

## Monitoring Commands

```bash
# Watch progress
tail -f scrape.log

# Check database stats every minute
watch -n 60 'sqlite3 data/irowiki.db "SELECT COUNT(*) as pages, (SELECT COUNT(*) FROM revisions) as revs, (SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions) as mb FROM pages"'

# Check timing log
tail scrape_timing.log

# Check if scrape is still running
ps aux | grep "python3 -m scraper"
```

## Progress Checkpoints

Will update this as the scrape progresses:

### Checkpoint 1: Discovery Complete
- Time: TBD
- Pages discovered: TBD

### Checkpoint 2: 25% Complete
- Time: TBD
- Pages scraped: TBD
- Revisions scraped: TBD

### Checkpoint 3: 50% Complete
- Time: TBD
- Pages scraped: TBD
- Revisions scraped: TBD

### Checkpoint 4: 75% Complete
- Time: TBD
- Pages scraped: TBD
- Revisions scraped: TBD

### Final: Scrape Complete ✅
- **End time:** 2026-01-26 02:26:45 UTC
- **Total duration:** 3 hours 7 minutes 17 seconds (11,237 seconds)
- **Total pages:** 10,516
- **Total revisions:** 84,486
- **Total content:** 960.45 MB
- **Database size:** 1.1 GB (compressed: 159 MB)
- **Performance:** 3,369 pages/hour, 27,067 revisions/hour
- **Average:** 8.03 revisions per page

## Post-Scrape Tasks

- [x] Verify data integrity
- [x] Create release package
- [x] Upload to GitHub releases
- [x] Update documentation with timing
- [ ] Add to README as reference for future scrapes

**Release URL:** https://github.com/lenaxia/iroWikiScraper/releases/tag/v2026-01-26

## Notes

- Scrape is running in background (PID tracked in scrape_timing.log)
- Checkpoint system enabled - can resume if interrupted
- All output logged to scrape.log
- Timing summary in scrape_timing.log
