# Story 08: Incremental Link Scraper

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-08  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to update links only for changed pages**,  
So that **the link graph stays current without re-processing all pages**.

## Description

Implement incremental link extraction that re-extracts internal links only from pages that have been modified or newly created. For each changed page, delete old links and insert new links to maintain an accurate link graph.

## Acceptance Criteria

### 1. IncrementalLinkScraper Class
- [ ] Create `scraper/incremental/link_scraper.py`
- [ ] Accepts `Database`, `LinkExtractor`
- [ ] Processes links for changed pages only
- [ ] Maintains link graph consistency

### 2. Update Links for Page Method
- [ ] Implement `update_links_for_page(page_id: int, content: str)`
- [ ] Deletes existing links for page_id from links table
- [ ] Extracts new links from current content
- [ ] Inserts new link records
- [ ] Uses transaction for atomicity

### 3. Batch Update Method
- [ ] Implement `update_links_batch(page_contents: Dict[int, str])`
- [ ] Efficiently updates links for multiple pages
- [ ] Minimizes database round trips
- [ ] Uses bulk delete and insert operations

### 4. Link Deletion Strategy
- [ ] DELETE FROM links WHERE source_page_id = ?
- [ ] Remove all outgoing links from changed page
- [ ] Preserve incoming links from other pages
- [ ] Use index on source_page_id for efficiency

### 5. Link Extraction
- [ ] Reuse existing LinkExtractor from Epic 01
- [ ] Parse wikitext for [[internal links]]
- [ ] Resolve redirect targets
- [ ] Handle namespace prefixes

### 6. Database Operations
- [ ] DELETE old links in transaction
- [ ] INSERT new links in bulk
- [ ] COMMIT transaction atomically
- [ ] Handle foreign key constraints

### 7. Error Handling
- [ ] Handle malformed wikitext gracefully
- [ ] Log link extraction failures
- [ ] Continue on single page failures
- [ ] Rollback transaction on error

### 8. Testing Requirements
- [ ] Test update links for single page
- [ ] Test batch update for multiple pages
- [ ] Test link deletion
- [ ] Test transaction rollback on error
- [ ] Test coverage: 80%+

## Technical Implementation

```python
class IncrementalLinkScraper:
    def __init__(self, database, link_extractor):
        self.db = database
        self.link_extractor = link_extractor
    
    def update_links_for_page(self, page_id: int, content: str):
        """Update links for a single page."""
        with self.db.transaction():
            # Delete old links
            self.db.execute(
                "DELETE FROM links WHERE source_page_id = ?",
                (page_id,)
            )
            
            # Extract new links
            links = self.link_extractor.extract_links(content)
            
            # Insert new links
            for target_title in links:
                target_id = self._resolve_page_id(target_title)
                if target_id:
                    self.db.execute(
                        "INSERT INTO links (source_page_id, target_page_id, target_title) VALUES (?, ?, ?)",
                        (page_id, target_id, target_title)
                    )
    
    def update_links_batch(self, page_contents: Dict[int, str]):
        """Update links for multiple pages efficiently."""
        # Delete all old links in one query
        page_ids = list(page_contents.keys())
        placeholders = ','.join('?' * len(page_ids))
        self.db.execute(
            f"DELETE FROM links WHERE source_page_id IN ({placeholders})",
            page_ids
        )
        
        # Extract and insert new links
        all_links = []
        for page_id, content in page_contents.items():
            links = self.link_extractor.extract_links(content)
            for target_title in links:
                target_id = self._resolve_page_id(target_title)
                if target_id:
                    all_links.append((page_id, target_id, target_title))
        
        # Bulk insert
        self.db.executemany(
            "INSERT INTO links (source_page_id, target_page_id, target_title) VALUES (?, ?, ?)",
            all_links
        )
```

## Dependencies

### Requires
- Epic 01, Story 09-10: Link Extraction and Storage
- Epic 02, Story 04: Links Schema

### Blocks
- Story 05: Incremental Page Scraper

## Definition of Done

- [ ] IncrementalLinkScraper implemented
- [ ] Batch operations working
- [ ] Transactions ensure consistency
- [ ] All tests passing (80%+ coverage)
- [ ] Code reviewed and merged
