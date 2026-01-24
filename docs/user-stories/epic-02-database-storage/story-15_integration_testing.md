# Story 15: Integration Testing

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-15  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **QA engineer**,  
I want **end-to-end database integration tests**,  
So that **I can validate complete workflows and ensure all components work together correctly**.

## Description

Implement comprehensive integration tests that validate complete database workflows: scraping → storage → queries → export. These tests use realistic data volumes and verify that all Epic 02 components work together seamlessly.

## Background & Context

**What are integration tests?**
- Test multiple components together
- Validate complete workflows end-to-end
- Use realistic data volumes
- Catch integration bugs that unit tests miss

**Why This Story Matters:**
- Validates Epic 02 is complete and functional
- Ensures components integrate correctly
- Provides confidence for production use
- Documents expected behavior

## Acceptance Criteria

### 1. Integration Test Suite
- [ ] Create `tests/storage/test_integration.py`
- [ ] Test: Complete scrape workflow (discover → store → query)
- [ ] Test: Incremental update simulation
- [ ] Test: Full-text search on real data
- [ ] Test: Timeline queries with realistic data
- [ ] Test: Export workflow (query → format → save)
- [ ] Test: Performance with realistic volumes

### 2. Realistic Data Tests
- [ ] Test with 2,400 pages
- [ ] Test with 86,500 revisions
- [ ] Test with 4,000 files
- [ ] Test with 50,000 links
- [ ] Verify performance benchmarks

### 3. Workflow Tests
- [ ] **Workflow 1**: Scrape → Store → Query
  - Discover pages
  - Scrape revisions
  - Store in database
  - Query and verify
- [ ] **Workflow 2**: Incremental Update
  - Initial scrape
  - Simulate new edits
  - Update database
  - Verify only new data added
- [ ] **Workflow 3**: Search & Export
  - Full-text search
  - Timeline queries
  - Export results
  - Verify accuracy

### 4. Cross-Component Tests
- [ ] Test: Page + Revisions integration
- [ ] Test: Pages + Links integration
- [ ] Test: FTS5 + Revisions sync
- [ ] Test: Foreign key constraints enforced
- [ ] Test: Triggers work correctly

### 5. Performance Benchmarks
- [ ] Initialize database: < 10 seconds
- [ ] Insert 2,400 pages: < 1 second
- [ ] Insert 86,500 revisions: < 60 seconds
- [ ] Full-text search: < 50ms
- [ ] Timeline query: < 50ms
- [ ] Export 100 pages: < 5 seconds

### 6. Database Integrity
- [ ] Test: Foreign keys prevent orphaned data
- [ ] Test: Unique constraints enforced
- [ ] Test: Triggers maintain FTS5 sync
- [ ] Test: Cascade delete works
- [ ] Test: No data corruption

### 7. Edge Cases
- [ ] Test: Empty database
- [ ] Test: Single page
- [ ] Test: Very large revision (1MB+)
- [ ] Test: Page with 1000+ revisions
- [ ] Test: Database > 1GB

## Tasks

### Test Infrastructure
- [ ] Create `tests/storage/test_integration.py`
- [ ] Create helper functions for generating test data
- [ ] Create fixtures for realistic data volumes
- [ ] Setup teardown for cleanup

### Workflow Tests
- [ ] Implement complete scrape workflow test
- [ ] Implement incremental update test
- [ ] Implement search & export test
- [ ] Verify all workflows succeed

### Performance Tests
- [ ] Implement performance benchmarks
- [ ] Measure actual timings
- [ ] Compare against acceptance criteria
- [ ] Document results

### Cross-Component Tests
- [ ] Test repository interactions
- [ ] Test foreign key enforcement
- [ ] Test trigger functionality
- [ ] Test index usage

### Run Full Test Suite
- [ ] Run all Epic 02 tests
- [ ] Run all Epic 01 tests (ensure no regressions)
- [ ] Verify 80%+ coverage across Epic 02
- [ ] Fix any failures

## Technical Details

### Test Structure

```python
# tests/storage/test_integration.py
"""
Integration tests for database storage.

These tests validate complete workflows with realistic data volumes.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from scraper.storage.database import Database
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository
from scraper.storage.file_repository import FileRepository
from scraper.storage.link_storage import LinkStorage
from scraper.storage.search import search, rebuild_index
from scraper.storage.queries import (
    get_page_at_time,
    list_pages_at_time,
    get_changes_in_range
)
from scraper.models.page import Page
from scraper.models.revision import Revision


class TestDatabaseIntegration:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def integration_db(self):
        """Provide database with full schema."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db = Database(db_path)
        db.initialize_schema()
        
        yield db
        
        # Cleanup
        db.close()
        Path(db_path).unlink(missing_ok=True)
    
    def test_complete_scrape_workflow(self, integration_db):
        """
        Test complete workflow: discover → store → query.
        
        Simulates scraping process:
        1. Discover pages
        2. Scrape revisions
        3. Store in database
        4. Query and verify
        """
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Step 1: Discover and store pages
        pages = [
            Page(page_id=None, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(100)
        ]
        page_repo.insert_pages_batch(pages)
        
        # Verify pages stored
        count = page_repo.count_pages()
        assert count == 100
        
        # Step 2: Scrape and store revisions (10 per page)
        revisions = []
        for page_id in range(1, 101):
            for rev_num in range(10):
                revisions.append(Revision(
                    revision_id=page_id * 1000 + rev_num,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime.now() - timedelta(days=10-rev_num),
                    user=f"User{rev_num}",
                    user_id=rev_num,
                    comment=f"Edit {rev_num}",
                    content=f"Content for page {page_id} rev {rev_num}",
                    size=50,
                    sha1=f"sha{page_id}{rev_num}",
                    minor=False,
                    tags=None
                ))
        
        rev_repo.insert_revisions_batch(revisions)
        
        # Verify revisions stored
        count = rev_repo.count_revisions()
        assert count == 1000  # 100 pages × 10 revisions
        
        # Step 3: Query and verify
        # Get latest revision for page 1
        latest = rev_repo.get_latest_revision(1)
        assert latest is not None
        assert latest.page_id == 1
        
        # Get page history
        history = rev_repo.get_revisions_by_page(1)
        assert len(history) == 10
    
    def test_incremental_update_workflow(self, integration_db):
        """
        Test incremental update workflow.
        
        Simulates:
        1. Initial scrape
        2. Time passes, new edits made
        3. Incremental update (fetch only new revisions)
        4. Verify only new data added
        """
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Initial scrape: 10 pages with 5 revisions each
        pages = [
            Page(page_id=None, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(10)
        ]
        page_repo.insert_pages_batch(pages)
        
        initial_revisions = []
        for page_id in range(1, 11):
            for rev_num in range(5):
                initial_revisions.append(Revision(
                    revision_id=page_id * 100 + rev_num,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime(2024, 1, 1) + timedelta(days=rev_num),
                    user=f"User{rev_num}",
                    user_id=rev_num,
                    comment=f"Initial edit {rev_num}",
                    content=f"Initial content {rev_num}",
                    size=20,
                    sha1=f"initial{page_id}{rev_num}",
                    minor=False,
                    tags=None
                ))
        
        rev_repo.insert_revisions_batch(initial_revisions)
        initial_count = rev_repo.count_revisions()
        assert initial_count == 50
        
        # Simulate new edits (3 new revisions on page 1)
        new_revisions = []
        for rev_num in range(5, 8):
            new_revisions.append(Revision(
                revision_id=100 + rev_num,
                page_id=1,
                parent_id=100 + rev_num - 1,
                timestamp=datetime(2024, 1, 10) + timedelta(days=rev_num),
                user=f"User{rev_num}",
                user_id=rev_num,
                comment=f"New edit {rev_num}",
                content=f"New content {rev_num}",
                size=20,
                sha1=f"new{rev_num}",
                minor=False,
                tags=None
            ))
        
        rev_repo.insert_revisions_batch(new_revisions)
        
        # Verify only new revisions added
        final_count = rev_repo.count_revisions()
        assert final_count == 53  # 50 + 3
        
        # Verify page 1 now has 8 revisions
        page1_history = rev_repo.get_revisions_by_page(1)
        assert len(page1_history) == 8
    
    def test_search_workflow(self, integration_db):
        """Test full-text search workflow."""
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Create pages with searchable content
        pages = [
            Page(page_id=None, namespace=0, title="Prontera", is_redirect=False),
            Page(page_id=None, namespace=0, title="Geffen", is_redirect=False),
            Page(page_id=None, namespace=0, title="Payon", is_redirect=False),
        ]
        page_repo.insert_pages_batch(pages)
        
        # Add content
        revisions = [
            Revision(
                revision_id=1, page_id=1, parent_id=None,
                timestamp=datetime.now(), user="User1", user_id=1,
                comment="", 
                content="Prontera is the capital city of Rune-Midgarts Kingdom",
                size=55, sha1="abc1", minor=False, tags=None
            ),
            Revision(
                revision_id=2, page_id=2, parent_id=None,
                timestamp=datetime.now(), user="User2", user_id=2,
                comment="",
                content="Geffen is the magical city of wizards",
                size=40, sha1="abc2", minor=False, tags=None
            ),
            Revision(
                revision_id=3, page_id=3, parent_id=None,
                timestamp=datetime.now(), user="User3", user_id=3,
                comment="",
                content="Payon is a village in the mountains",
                size=36, sha1="abc3", minor=False, tags=None
            ),
        ]
        rev_repo.insert_revisions_batch(revisions)
        
        # Rebuild FTS index
        rebuild_index(conn)
        
        # Search for "capital"
        results = search(conn, "capital")
        assert len(results) >= 1
        assert results[0].title == "Prontera"
        
        # Search for "city"
        results = search(conn, "city")
        assert len(results) >= 2
    
    def test_timeline_queries(self, integration_db):
        """Test temporal query workflow."""
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Create page
        pages = [Page(page_id=None, namespace=0, title="TestPage", is_redirect=False)]
        page_repo.insert_pages_batch(pages)
        
        # Create revisions at different times
        revisions = [
            Revision(
                revision_id=i,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, i+1),
                user=f"User{i}",
                user_id=i,
                comment="",
                content=f"Version {i}",
                size=10,
                sha1=f"sha{i}",
                minor=False,
                tags=None
            )
            for i in range(1, 11)
        ]
        rev_repo.insert_revisions_batch(revisions)
        
        # Test get page at time
        rev_at_time = get_page_at_time(conn, 1, datetime(2024, 1, 5))
        assert rev_at_time is not None
        assert rev_at_time.content == "Version 4"
        
        # Test get changes in range
        changes = get_changes_in_range(
            conn,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5)
        )
        assert len(changes) == 5
    
    def test_performance_benchmarks(self, integration_db, benchmark):
        """Test performance with realistic data volumes."""
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Benchmark: Insert 1000 pages
        pages = [
            Page(page_id=None, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(1000)
        ]
        
        start = datetime.now()
        page_repo.insert_pages_batch(pages)
        duration = (datetime.now() - start).total_seconds()
        
        assert duration < 1.0, f"Page insert took {duration}s, expected < 1s"
        
        # Benchmark: Insert 10,000 revisions
        revisions = []
        for page_id in range(1, 1001):
            for rev_num in range(10):
                revisions.append(Revision(
                    revision_id=page_id * 100 + rev_num,
                    page_id=page_id,
                    parent_id=None,
                    timestamp=datetime.now(),
                    user="TestUser",
                    user_id=1,
                    comment="",
                    content="Test content" * 10,
                    size=100,
                    sha1=f"sha{page_id}{rev_num}",
                    minor=False,
                    tags=None
                ))
        
        start = datetime.now()
        rev_repo.insert_revisions_batch(revisions)
        duration = (datetime.now() - start).total_seconds()
        
        assert duration < 10.0, f"Revision insert took {duration}s, expected < 10s"
        
        # Benchmark: Query latest revision
        start = datetime.now()
        latest = rev_repo.get_latest_revision(1)
        duration = (datetime.now() - start).total_seconds()
        
        assert duration < 0.01, f"Latest revision query took {duration}s, expected < 0.01s"
    
    def test_foreign_key_enforcement(self, integration_db):
        """Test that foreign key constraints are enforced."""
        conn = integration_db.get_connection()
        
        # Try to insert revision for non-existent page
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            conn.execute("""
                INSERT INTO revisions 
                (revision_id, page_id, timestamp, content, size, sha1)
                VALUES (1, 999, '2024-01-01', 'test', 4, 'abc')
            """)
            conn.commit()
    
    def test_cascade_delete(self, integration_db):
        """Test that cascade delete removes related records."""
        conn = integration_db.get_connection()
        page_repo = PageRepository(conn)
        rev_repo = RevisionRepository(conn)
        
        # Create page with revisions
        pages = [Page(page_id=None, namespace=0, title="TestPage", is_redirect=False)]
        page_repo.insert_pages_batch(pages)
        
        revisions = [
            Revision(
                revision_id=i,
                page_id=1,
                parent_id=None,
                timestamp=datetime.now(),
                user="User1",
                user_id=1,
                comment="",
                content=f"Rev {i}",
                size=5,
                sha1=f"sha{i}",
                minor=False,
                tags=None
            )
            for i in range(1, 6)
        ]
        rev_repo.insert_revisions_batch(revisions)
        
        # Verify revisions exist
        count = rev_repo.count_revisions(page_id=1)
        assert count == 5
        
        # Delete page
        page_repo.delete_page(1)
        
        # Verify revisions deleted
        count = rev_repo.count_revisions(page_id=1)
        assert count == 0
```

## Dependencies

### Requires
- ALL previous Epic 02 stories (01-14)
- Epic 01: Complete (existing tests)

### Blocks
- Epic 02 completion
- Epic 03: Incremental Updates

## Testing Requirements

- [ ] All integration tests pass
- [ ] All Epic 01 tests still pass (no regressions)
- [ ] Performance benchmarks met
- [ ] Coverage across Epic 02: 80%+
- [ ] Memory usage acceptable (< 500MB)

## Definition of Done

- [ ] Integration test suite complete
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Coverage ≥80% for Epic 02
- [ ] All Epic 01 tests still pass
- [ ] Documentation updated
- [ ] Code review completed
- [ ] **Epic 02 COMPLETE**

## Notes

**Why integration tests matter:**
- Unit tests verify individual components
- Integration tests verify they work together
- Catch bugs that only appear in real usage
- Document expected workflows

**Test data generation:**
- Create helpers for realistic data
- Use factories for model instances
- Parameterize for different scales
- Cleanup after tests

**Performance testing:**
- Measure actual timings
- Compare against acceptance criteria
- Profile if performance issues found
- Document results for baseline
