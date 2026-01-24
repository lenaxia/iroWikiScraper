# Story 07: Incremental File Scraper

**Epic**: Epic 03 - Incremental Updates  
**Story ID**: epic-03-story-07  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 2-3 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **to download only new or modified files**,  
So that **I don't re-download unchanged media files unnecessarily**.

## Description

Implement incremental file downloading that detects new file uploads and file modifications (new versions) using SHA1 checksums. Downloads only files that don't exist locally or have changed checksums.

Files are typically large (images, documents), so avoiding unnecessary downloads significantly reduces bandwidth and time.

## Acceptance Criteria

### 1. IncrementalFileScraper Class
- [ ] Create `scraper/incremental/file_scraper.py`
- [ ] Accepts `APIClient`, `Database`, `FileDownloader`
- [ ] Detects new and modified files
- [ ] Downloads only changed files

### 2. Detect File Changes Method
- [ ] Implement `detect_file_changes() -> FileChangeSet`
- [ ] Queries MediaWiki allimages list
- [ ] Compares with database files table
- [ ] Identifies: new files, modified files (SHA1 mismatch), deleted files
- [ ] Returns FileChangeSet with categorized file changes

### 3. FileChangeSet Data Model
- [ ] Fields: `new_files: List[FileInfo]`
- [ ] Fields: `modified_files: List[FileInfo]` (SHA1 changed)
- [ ] Fields: `deleted_files: List[str]` (file titles)
- [ ] Property: `total_changes`

### 4. SHA1 Comparison
- [ ] Fetch SHA1 checksums from allimages API
- [ ] Compare with database sha1 column
- [ ] Identify files with different SHA1 (new version uploaded)
- [ ] Mark for re-download

### 5. Incremental Download Method
- [ ] Implement `download_new_files(file_change_set: FileChangeSet)`
- [ ] Downloads new files
- [ ] Re-downloads modified files (overwrite)
- [ ] Marks deleted files in database
- [ ] Uses existing FileDownloader for actual download

### 6. Database Updates
- [ ] Insert new file records
- [ ] Update modified file records (sha1, size, timestamp)
- [ ] Mark deleted files (is_deleted flag)
- [ ] Atomic transactions

### 7. Performance Optimization
- [ ] Batch SHA1 queries
- [ ] Skip download if file exists locally with correct SHA1
- [ ] Parallel downloads (optional, configurable)
- [ ] Resume interrupted downloads

### 8. Testing Requirements
- [ ] Test detect new files
- [ ] Test detect modified files (SHA1 change)
- [ ] Test detect deleted files
- [ ] Test download only changed files
- [ ] Test coverage: 80%+

## Technical Implementation

```python
@dataclass
class FileInfo:
    title: str
    sha1: str
    size: int
    url: str
    timestamp: datetime

@dataclass
class FileChangeSet:
    new_files: List[FileInfo] = field(default_factory=list)
    modified_files: List[FileInfo] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    
    @property
    def total_changes(self) -> int:
        return len(self.new_files) + len(self.modified_files) + len(self.deleted_files)

class IncrementalFileScraper:
    def detect_file_changes(self) -> FileChangeSet:
        # Fetch all files from API
        api_files = self._fetch_all_files_from_api()
        
        # Fetch all files from database
        db_files = self._fetch_all_files_from_db()
        
        changes = FileChangeSet()
        
        for file_info in api_files:
            if file_info.title not in db_files:
                changes.new_files.append(file_info)
            elif db_files[file_info.title].sha1 != file_info.sha1:
                changes.modified_files.append(file_info)
        
        # Detect deleted files
        api_titles = {f.title for f in api_files}
        for db_title in db_files:
            if db_title not in api_titles:
                changes.deleted_files.append(db_title)
        
        return changes
```

## Dependencies

### Requires
- Epic 01, Story 07-08: File Discovery and Download
- Epic 02, Story 03: Files Schema

### Blocks
- Story 05: Incremental Page Scraper

## Definition of Done

- [ ] IncrementalFileScraper implemented
- [ ] SHA1 comparison working
- [ ] Downloads only changed files
- [ ] All tests passing (80%+ coverage)
- [ ] Code reviewed and merged
