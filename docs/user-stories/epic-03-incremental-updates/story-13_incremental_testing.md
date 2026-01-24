# Story 13: Incremental Update Testing

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-13  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 3-4 days  
**Assignee**: TBD

## User Story

As a **QA engineer**,  
I want **comprehensive end-to-end tests for incremental updates**,  
So that **I can verify the incremental scraper works correctly in real-world scenarios**.

## Description

Create comprehensive integration tests that simulate realistic incremental update scenarios: initial full scrape, adding new pages, modifying existing pages, deleting pages, and running incremental scrapes. Validates the entire incremental workflow from start to finish.

## Acceptance Criteria

### 1. Test Infrastructure
- [ ] Create test database with realistic data (100 pages, 500 revisions)
- [ ] Mock MediaWiki API responses for incremental queries
- [ ] Fixtures for various change scenarios
- [ ] Test database reset utilities

### 2. Full→Incremental Workflow Test
- [ ] Test: Full scrape creates baseline
- [ ] Test: First incremental detects requires_full_scrape=False
- [ ] Test: Second incremental processes only changes
- [ ] Test: Third incremental with no changes

### 3. New Page Test
- [ ] Mock: Add 10 new pages to wiki
- [ ] Run: Incremental scrape
- [ ] Verify: All 10 pages inserted with full revision history
- [ ] Verify: Links extracted and stored
- [ ] Verify: Statistics accurate

### 4. Modified Page Test
- [ ] Mock: Add 5 new revisions to existing pages
- [ ] Run: Incremental scrape
- [ ] Verify: Only new revisions inserted
- [ ] Verify: Old revisions unchanged
- [ ] Verify: Page.updated_at updated
- [ ] Verify: Links updated

### 5. Deleted Page Test
- [ ] Mock: Delete 3 pages from wiki
- [ ] Run: Incremental scrape
- [ ] Verify: Pages marked as deleted (is_deleted=True)
- [ ] Verify: Historical data preserved
- [ ] Verify: No API calls for deleted pages

### 6. Moved Page Test
- [ ] Mock: Move/rename 2 pages
- [ ] Run: Incremental scrape
- [ ] Verify: Page titles updated
- [ ] Verify: New revisions fetched if content changed

### 7. Mixed Changes Test
- [ ] Mock: Complex scenario (10 new, 20 modified, 3 deleted, 2 moved)
- [ ] Run: Incremental scrape
- [ ] Verify: All changes processed correctly
- [ ] Verify: Statistics match expected

### 8. Performance Test
- [ ] Test: Incremental scrape with 100 modified pages completes in <30 minutes
- [ ] Test: Memory usage stays under 500MB
- [ ] Test: API calls count is reasonable (<200 for 100 changes)

### 9. Error Recovery Test
- [ ] Mock: API errors during scrape
- [ ] Verify: Scraper continues with other pages
- [ ] Verify: Failed pages logged
- [ ] Verify: scrape_run marked as 'partial'

### 10. Resume Test
- [ ] Simulate: Interruption after 50% complete
- [ ] Run: Resume scrape
- [ ] Verify: Skips completed pages
- [ ] Verify: Completes remaining pages
- [ ] Verify: Final result correct

### 11. Idempotency Test
- [ ] Run: Same incremental scrape twice
- [ ] Verify: No duplicate data
- [ ] Verify: No errors
- [ ] Verify: Database state identical

### 12. Integration Test Suite
- [ ] Test: Full workflow end-to-end
- [ ] Benchmark: Execution time
- [ ] Verify: No database corruption
- [ ] Generate: Coverage report (80%+ for incremental module)

## Test Scenarios

### Scenario 1: Initial Setup + First Incremental
```python
def test_full_to_incremental_workflow():
    # Step 1: Full scrape
    scraper.scrape_full()
    assert db.count_pages() == 100
    assert db.count_revisions() == 500
    
    # Step 2: Add changes to mock API
    mock_api.add_new_pages(10)
    mock_api.add_revisions_to_pages([1, 2, 3], count=2)
    
    # Step 3: Run incremental
    stats = scraper.scrape_incremental()
    
    # Verify
    assert stats.pages_new == 10
    assert stats.pages_modified == 3
    assert stats.revisions_added == 6  # 2 revisions × 3 pages
    assert db.count_pages() == 110
    assert db.count_revisions() == 506
```

### Scenario 2: Large-Scale Changes
```python
def test_large_scale_incremental():
    # Baseline
    scraper.scrape_full()
    
    # Add realistic monthly changes
    mock_api.add_new_pages(50)  # ~50 new pages per month
    mock_api.modify_pages(100)  # ~100 edits per month
    mock_api.delete_pages(5)     # ~5 deletions per month
    
    # Run incremental
    start_time = time.time()
    stats = scraper.scrape_incremental()
    duration = time.time() - start_time
    
    # Performance assertions
    assert duration < 1800  # < 30 minutes
    assert stats.api_calls < 200
    
    # Correctness assertions
    assert stats.pages_new == 50
    assert stats.pages_modified == 100
    assert stats.pages_deleted == 5
```

### Scenario 3: Error Handling
```python
def test_incremental_with_errors():
    scraper.scrape_full()
    
    # Inject API errors for specific pages
    mock_api.inject_error(page_id=10, error_code=500)
    mock_api.inject_error(page_id=20, error_code=timeout)
    
    mock_api.modify_pages([5, 10, 15, 20, 25])
    
    # Run incremental (should continue despite errors)
    stats = scraper.scrape_incremental()
    
    # Verify partial success
    assert stats.pages_modified >= 3  # At least non-error pages
    assert len(scraper.failed_pages) == 2  # Two pages failed
    
    # Verify scrape_run marked appropriately
    run = db.get_latest_scrape_run()
    assert run.status == 'partial'  # Not fully successful
```

## Test Data

### Mock API Data Generation
```python
class MockIncrementalAPI:
    def __init__(self):
        self.pages = {...}  # Initial state
        self.changes = []
    
    def add_new_pages(self, count: int):
        for i in range(count):
            page_id = self.next_page_id()
            self.pages[page_id] = self._generate_page()
            self.changes.append(RecentChange(
                type='new',
                pageid=page_id,
                ...
            ))
    
    def modify_pages(self, page_ids: List[int]):
        for page_id in page_ids:
            new_revision = self._generate_revision(page_id)
            self.pages[page_id].revisions.append(new_revision)
            self.changes.append(RecentChange(
                type='edit',
                pageid=page_id,
                ...
            ))
```

## Performance Benchmarks

| Scenario | Expected Duration | Expected API Calls | Expected Memory |
|----------|-------------------|-------------------|-----------------|
| 10 new pages | <2 min | ~15 | <100 MB |
| 50 modified pages | <10 min | ~60 | <200 MB |
| 100 mixed changes | <30 min | <200 | <500 MB |
| 500 modifications | <2 hours | ~600 | <1 GB |

## Dependencies

### Requires
- All Epic 03 stories (testing complete functionality)
- Test infrastructure from Epic 01 and 02

### Blocks
- Epic 06: Automation (confidence in incremental scraping required)

## Definition of Done

- [ ] All 12 test scenarios implemented
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Integration test coverage ≥85%
- [ ] Test execution time <5 minutes for full suite
- [ ] Continuous integration setup
- [ ] Test documentation complete
- [ ] Code reviewed and merged

## Notes for Implementation

### Testing Strategy
1. **Unit tests**: Individual components (Stories 01-04)
2. **Integration tests**: Combined workflows (Stories 05-08)
3. **End-to-end tests**: This story (full incremental workflow)
4. **Performance tests**: Benchmarking and optimization

### Mock Data Realism
- Use realistic edit patterns (most pages have 1-5 edits/month)
- Include edge cases (heavily edited pages, stub pages)
- Model actual iRO Wiki statistics

### CI/CD Integration
- Run incremental tests on every PR
- Performance regression testing
- Nightly full integration test
- Monthly test with live API (optional)

## References

- All Epic 03 stories
- Epic 01 testing infrastructure
- MediaWiki API test documentation
- pytest best practices
