# Story 12: Integrity Verification

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-12  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **data curator**,  
I want **to verify no data was missed during incremental updates**,  
So that **the archive remains complete and accurate**.

## Description

Implement integrity verification checks to ensure incremental updates captured all changes correctly. Detects gaps in revision IDs, missing pages, inconsistent timestamps, and other data integrity issues.

## Acceptance Criteria

### 1. IntegrityVerifier Class
- [ ] Create `scraper/incremental/integrity_verifier.py`
- [ ] Performs various integrity checks
- [ ] Returns detailed verification report

### 2. Revision Gap Detection
- [ ] Check for gaps in revision_id sequences per page
- [ ] Identify missing revisions
- [ ] Report pages with gaps

### 3. Timestamp Consistency Check
- [ ] Verify revision timestamps are sequential
- [ ] Check page.updated_at matches latest revision
- [ ] Detect timestamp anomalies

### 4. Page Completeness Check
- [ ] Compare page count with MediaWiki statistics
- [ ] Identify pages in API but not in database
- [ ] Report missing pages

### 5. Link Consistency Check
- [ ] Verify links point to existing pages
- [ ] Detect broken links
- [ ] Check bidirectional link consistency

### 6. File Integrity Check
- [ ] Verify all files in database exist on disk
- [ ] Check SHA1 checksums match
- [ ] Detect corrupted files

### 7. Verification Report
- [ ] Create `VerificationReport` dataclass
- [ ] Fields: revision_gaps, missing_pages, broken_links, corrupted_files
- [ ] Property: `has_issues` (True if any problems found)
- [ ] Method: `to_dict()` for serialization

### 8. Testing Requirements
- [ ] Test detect revision gaps
- [ ] Test detect missing pages
- [ ] Test detect broken links
- [ ] Test detect corrupted files
- [ ] Test coverage: 80%+

## Technical Implementation

```python
@dataclass
class VerificationReport:
    revision_gaps: List[Tuple[int, int, int]] = field(default_factory=list)  # (page_id, gap_start, gap_end)
    missing_pages: List[int] = field(default_factory=list)
    broken_links: List[Tuple[int, str]] = field(default_factory=list)  # (source_page_id, target_title)
    corrupted_files: List[str] = field(default_factory=list)  # file titles
    timestamp_anomalies: List[int] = field(default_factory=list)  # page_ids
    
    @property
    def has_issues(self) -> bool:
        return bool(
            self.revision_gaps or
            self.missing_pages or
            self.broken_links or
            self.corrupted_files or
            self.timestamp_anomalies
        )
    
    @property
    def total_issues(self) -> int:
        return (
            len(self.revision_gaps) +
            len(self.missing_pages) +
            len(self.broken_links) +
            len(self.corrupted_files) +
            len(self.timestamp_anomalies)
        )

class IntegrityVerifier:
    def verify_all(self) -> VerificationReport:
        """Run all integrity checks."""
        report = VerificationReport()
        
        report.revision_gaps = self.check_revision_gaps()
        report.missing_pages = self.check_missing_pages()
        report.broken_links = self.check_broken_links()
        report.corrupted_files = self.check_file_integrity()
        report.timestamp_anomalies = self.check_timestamp_consistency()
        
        return report
    
    def check_revision_gaps(self) -> List[Tuple[int, int, int]]:
        """Detect gaps in revision ID sequences."""
        query = """
            SELECT page_id, revision_id,
                   LAG(revision_id) OVER (PARTITION BY page_id ORDER BY revision_id) as prev_revision_id
            FROM revisions
        """
        results = self.db.execute(query).fetchall()
        
        gaps = []
        for page_id, revision_id, prev_id in results:
            if prev_id is not None and revision_id - prev_id > 1:
                gaps.append((page_id, prev_id, revision_id))
        
        return gaps
```

## Dependencies

### Requires
- All Epic 03 stories (verification runs after scraping)
- Epic 02: Database schemas

### Blocks
- None (optional verification step)

## Definition of Done

- [ ] IntegrityVerifier class implemented
- [ ] All verification checks working
- [ ] Comprehensive report generated
- [ ] All tests passing (80%+ coverage)
- [ ] Code reviewed and merged
