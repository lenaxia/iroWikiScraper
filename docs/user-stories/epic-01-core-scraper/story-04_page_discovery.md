# Story 04: Page Discovery

**Epic**: Epic 01 - Core Scraper Implementation  
**Story ID**: epic-01-story-04  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to discover all pages across all namespaces in the wiki**,  
So that **I can fetch complete content for archival**.

## Description

Implement functionality to discover all pages in iRO Wiki using the MediaWiki `allpages` API. This includes iterating through all namespaces, handling pagination, tracking progress, and storing page metadata.

## Background

**MediaWiki Namespaces:**
- 0: Main (articles like "Poring", "Main_Page")
- 1: Talk (discussion pages)
- 2: User (user pages)
- 3: User talk
- 4: Project (wiki admin pages)
- 6: File (image/file pages)
- 10: Template (reusable templates)
- 14: Category
- And more...

**allpages API:**
```
GET /w/api.php?action=query&list=allpages&aplimit=500&apnamespace=0
```

Returns pages in chunks with continuation tokens.

## Acceptance Criteria

### 1. Page Discovery Implementation
- [ ] Create `scraper/scrapers/page_scraper.py` with `PageDiscovery` class
- [ ] Method `discover_all_pages()` returns list of all pages
- [ ] Method `discover_namespace(ns_id)` returns pages in namespace
- [ ] Handles pagination automatically via continue tokens
- [ ] Returns Page objects with: page_id, title, namespace

### 2. Pagination Handling
- [ ] Fetch up to 500 pages per request (API max)
- [ ] Use continue tokens for next batch
- [ ] Stop when no more continue token
- [ ] Track pages discovered vs total

### 3. Progress Tracking
- [ ] Log progress every N pages (configurable)
- [ ] Report estimated time remaining
- [ ] Track pages per namespace

### 4. Data Models
- [ ] Create `scraper/storage/models.py`
- [ ] Define `Page` dataclass with validation
- [ ] Fields: page_id, namespace, title, is_redirect

### 5. Testing
- [ ] Test infrastructure: Create allpages response fixtures
- [ ] Test: Discover pages in single namespace
- [ ] Test: Handle pagination correctly
- [ ] Test: All namespaces discovered
- [ ] Test: Progress logging works

## Tasks

### Test Infrastructure (FIRST)
- [ ] Create `fixtures/api/allpages_single.json`
- [ ] Create `fixtures/api/allpages_paginated.json`
- [ ] Create `fixtures/api/allpages_continue.json`

### Implementation
- [ ] Create `scraper/storage/models.py` with Page dataclass
- [ ] Create `scraper/scrapers/page_scraper.py`
- [ ] Implement PageDiscovery class
- [ ] Implement discover_namespace()
- [ ] Implement discover_all_pages()
- [ ] Add progress logging

### Testing
- [ ] Write tests in `tests/test_page_discovery.py`
- [ ] Test pagination
- [ ] Test all namespaces
- [ ] Run tests

## Technical Details

```python
# scraper/storage/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Page:
    page_id: int
    namespace: int
    title: str
    is_redirect: bool = False
    
    def __post_init__(self):
        if self.page_id <= 0:
            raise ValueError("page_id must be positive")
        if self.namespace < 0:
            raise ValueError("namespace must be non-negative")
        if not self.title:
            raise ValueError("title cannot be empty")

# scraper/scrapers/page_scraper.py
class PageDiscovery:
    def __init__(self, api_client: MediaWikiAPIClient):
        self.api = api_client
    
    def discover_namespace(self, namespace: int) -> List[Page]:
        """Discover all pages in namespace."""
        pages = []
        continue_token = None
        
        while True:
            params = {
                'list': 'allpages',
                'aplimit': 500,
                'apnamespace': namespace
            }
            
            if continue_token:
                params.update(continue_token)
            
            response = self.api.query(params)
            
            # Extract pages
            for page_data in response['query']['allpages']:
                pages.append(Page(
                    page_id=page_data['pageid'],
                    namespace=page_data['ns'],
                    title=page_data['title'],
                    is_redirect='redirect' in page_data
                ))
            
            # Check for continuation
            if 'continue' not in response:
                break
            
            continue_token = response['continue']
            logger.info(f"Namespace {namespace}: {len(pages)} pages discovered")
        
        return pages
    
    def discover_all_pages(self) -> List[Page]:
        """Discover all pages across all namespaces."""
        all_pages = []
        namespaces = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        
        for ns in namespaces:
            logger.info(f"Discovering namespace {ns}")
            pages = self.discover_namespace(ns)
            all_pages.extend(pages)
            logger.info(f"Namespace {ns}: {len(pages)} pages")
        
        logger.info(f"Total pages discovered: {len(all_pages)}")
        return all_pages
```

## Dependencies

- Requires: Story 01 (API Client), Story 02 (Rate Limiter), Story 03 (Error Handling)
- Blocks: Story 05 (Revision Scraping)

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tests passing (≥80% coverage)
- [ ] Can discover all ~2,400 pages
- [ ] Pagination works correctly
- [ ] Progress logging clear
- [ ] Code reviewed and merged
