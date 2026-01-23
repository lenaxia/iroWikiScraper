# Epic 01: Core Scraper Implementation

**Epic ID**: epic-01  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 2-3 weeks

## Overview

Implement the core MediaWiki API scraper for iRO Wiki with complete page and revision history scraping, file downloading, and link extraction. This epic establishes the foundation for all archival functionality.

## Goals

1. Fetch all pages across all namespaces from iRO Wiki
2. Scrape complete revision history for each page
3. Download all media files with verification
4. Extract and store internal link structure
5. Implement respectful rate limiting and retry logic
6. Support checkpoint/resume for interrupted scrapes

## Success Criteria

- ✅ Scraper successfully fetches all ~2,400 pages
- ✅ All ~86,500 revisions captured with full metadata
- ✅ All ~4,000 files downloaded and verified (SHA1)
- ✅ Rate limiting prevents API abuse (1 req/sec default)
- ✅ Scraper can resume after interruption
- ✅ 80%+ test coverage on all scraper components

## User Stories

### API Client & Rate Limiting
- [Story 01: MediaWiki API Client](story-01_mediawiki_api_client.md)
- [Story 02: Rate Limiter with Backoff](story-02_rate_limiter.md)
- [Story 03: API Error Handling](story-03_api_error_handling.md)

### Page & Revision Scraping
- [Story 04: Page Discovery](story-04_page_discovery.md)
- [Story 05: Revision History Scraping](story-05_revision_scraping.md)
- [Story 06: Pagination Handling](story-06_pagination_handling.md)

### File Scraping
- [Story 07: File Discovery](story-07_file_discovery.md)
- [Story 08: File Download with Verification](story-08_file_download.md)

### Link Extraction
- [Story 09: Internal Link Extraction](story-09_link_extraction.md)
- [Story 10: Link Storage](story-10_link_storage.md)

### Infrastructure
- [Story 11: Checkpoint and Resume](story-11_checkpoint_resume.md)
- [Story 12: Progress Tracking and Logging](story-12_progress_tracking.md)
- [Story 13: Configuration Management](story-13_configuration.md)

## Dependencies

### Requires:
- Epic 02: Database schema (for data storage)

### Blocks:
- Epic 03: Incremental updates (depends on full scraper)
- Epic 04: Export and packaging (depends on scraped data)

## Technical Notes

### MediaWiki API Endpoints
- `action=query&list=allpages` - Page discovery
- `action=query&prop=revisions` - Revision history
- `action=query&list=allimages` - File listing
- `action=query&prop=imageinfo` - File metadata

### Rate Limiting Strategy
- Default: 1 request/second
- Configurable via config.yaml
- Exponential backoff on 429 (rate limit) errors
- Respect API's `maxlag` parameter

### Namespaces to Archive
- 0: Main (articles)
- 1: Talk
- 2: User
- 3: User talk
- 4: Project
- 5: Project talk
- 6: File
- 7: File talk
- 8: MediaWiki
- 9: MediaWiki talk
- 10: Template
- 11: Template talk
- 12: Help
- 13: Help talk
- 14: Category
- 15: Category talk

### Error Handling
- Network timeouts: Retry with exponential backoff
- HTTP 404: Log and continue (deleted pages)
- HTTP 429: Wait and retry with longer delay
- HTTP 500+: Retry up to 3 times, then log error

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/api/allpages_response.json` - Sample page list
- `fixtures/api/revisions_response.json` - Sample revision data
- `fixtures/api/allimages_response.json` - Sample file list
- `fixtures/api/imageinfo_response.json` - Sample file metadata
- `fixtures/api/error_responses/*.json` - Error scenarios

### Mocks Needed
- `tests/mocks/mock_api_client.py` - Mock MediaWiki API
- `tests/mocks/mock_rate_limiter.py` - Mock rate limiter
- `tests/mocks/mock_http_session.py` - Mock requests.Session

### Test Utilities
- `tests/utils/api_helpers.py` - API response builders
- `tests/utils/assertions.py` - Custom assertions for scraped data

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |

## Definition of Done

- [ ] All 13 user stories completed
- [ ] All tests passing (80%+ coverage)
- [ ] Full scrape of iRO Wiki successful
- [ ] All files downloaded and verified
- [ ] Can resume after interruption
- [ ] Documentation complete (docstrings, examples)
- [ ] Design document created and approved
- [ ] Code reviewed and merged
