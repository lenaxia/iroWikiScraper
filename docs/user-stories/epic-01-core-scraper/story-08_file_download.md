# Story 08: File Download with Verification

**Epic**: Epic 01 - Core Scraper  
**Story ID**: epic-01-story-08  
**Priority**: High  
**Effort**: 3 days

## User Story
As a scraper developer, I want to download files with SHA1 verification, so that file integrity is guaranteed.

## Description
Download files from URLs, verify checksums, organize in directory structure, handle failures gracefully.

## Acceptance Criteria
- [ ] Download file from URL to local path
- [ ] Verify SHA1 checksum after download
- [ ] Organize: files/File/A/filename.ext (by first letter)
- [ ] Resume partial downloads
- [ ] Handle missing/deleted files
- [ ] Retry on transient failures

## Implementation
```python
class FileDownloader:
    def __init__(self, api_client, files_dir: Path):
        self.api = api_client
        self.files_dir = files_dir
    
    def download_file(self, file_meta: FileMetadata) -> Path:
        # Create directory structure
        first_letter = file_meta.filename[0].upper()
        file_dir = self.files_dir / "File" / first_letter
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = file_dir / file_meta.filename
        
        # Check if already downloaded and verified
        if file_path.exists():
            if self._verify_checksum(file_path, file_meta.sha1):
                logger.debug(f"File already exists: {file_meta.filename}")
                return file_path
        
        # Download
        response = requests.get(file_meta.url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify
        if not self._verify_checksum(file_path, file_meta.sha1):
            file_path.unlink()
            raise DownloadError(f"Checksum mismatch: {file_meta.filename}")
        
        return file_path
    
    def _verify_checksum(self, file_path: Path, expected_sha1: str) -> bool:
        sha1 = hashlib.sha1()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        return sha1.hexdigest() == expected_sha1
```

Dependencies: Story 07 (File Discovery)
