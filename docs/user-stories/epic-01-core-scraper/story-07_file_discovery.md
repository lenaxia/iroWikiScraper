# Story 07: File Discovery

**Epic**: Epic 01 - Core Scraper  
**Story ID**: epic-01-story-07  
**Priority**: High  
**Effort**: 2 days

## User Story
As a scraper developer, I want to discover all uploaded files, so that media content is included in the archive.

## Description
Use MediaWiki's allimages API to discover all files. Store metadata for later download.

## Acceptance Criteria
- [ ] Method discover_files() returns all file metadata
- [ ] File model: filename, url, sha1, size, mime_type, timestamp, uploader
- [ ] Handles pagination
- [ ] ~4,000 files discovered

## Implementation
```python
@dataclass
class FileMetadata:
    filename: str
    url: str
    descriptionurl: str
    sha1: str
    size: int
    width: Optional[int]
    height: Optional[int]
    mime_type: str
    timestamp: datetime
    uploader: str

def discover_files() -> List[FileMetadata]:
    params = {
        'list': 'allimages',
        'ailimit': 500,
        'aiprop': 'url|size|sha1|mime|timestamp|user|dimensions'
    }
    # Use PaginatedQuery
```

Dependencies: Story 06 (Pagination)
