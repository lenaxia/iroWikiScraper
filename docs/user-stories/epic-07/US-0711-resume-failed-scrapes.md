# US-0711: Resume Failed Scrapes

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** Pending  
**Priority:** Low  
**Story Points:** 5

## User Story

As a user, I need the ability to resume a failed or interrupted scrape from where it left off, so that I don't have to restart from the beginning after a network failure or interruption.

## Acceptance Criteria

1. **Checkpoint Tracking**
   - [ ] Save checkpoint file during scrape
   - [ ] Record last completed page/namespace
   - [ ] Include timestamp and scrape parameters
   - [ ] Update checkpoint periodically (e.g., every 10 pages)

2. **Resume Detection**
   - [ ] Detect existing checkpoint on startup
   - [ ] Ask user if they want to resume
   - [ ] `--resume` flag to auto-resume without prompt
   - [ ] `--no-resume` flag to ignore checkpoint

3. **Resume Logic**
   - [ ] Skip namespaces already completed
   - [ ] Skip pages already scraped in current namespace
   - [ ] Verify existing data before skipping
   - [ ] Handle database rollback if interrupted mid-transaction

4. **Checkpoint Cleanup**
   - [ ] Delete checkpoint on successful completion
   - [ ] Keep checkpoint on failure for debugging
   - [ ] `--clean` flag to remove old checkpoints

5. **Idempotency**
   - [ ] Safe to re-run on already-scraped data
   - [ ] Use INSERT OR REPLACE for pages
   - [ ] Use INSERT OR REPLACE for revisions
   - [ ] No duplicate data created

## Technical Details

### Checkpoint File Format

```json
{
  "version": "1.0",
  "scrape_type": "full",
  "started_at": "2025-01-24T10:00:00Z",
  "last_update": "2025-01-24T10:15:32Z",
  "parameters": {
    "namespaces": [0, 4, 6, 10, 14],
    "rate_limit": 2.0
  },
  "progress": {
    "namespaces_completed": [0, 4],
    "current_namespace": 6,
    "pages_completed": 89,
    "last_page_id": 1523
  },
  "statistics": {
    "pages_scraped": 2076,
    "revisions_scraped": 13452,
    "errors": 2
  }
}
```

### Checkpoint Location

```
data/.checkpoint.json
```

### Resume Prompt

```
Found existing scrape checkpoint from 2025-01-24 10:00:00

Progress:
  Namespaces completed: 0, 4
  Current namespace: 6 (89/156 pages)
  Total progress: 2076/2400 pages (86.5%)

Do you want to resume this scrape? [y/N]: 
```

### Resume Implementation

```python
def _check_for_checkpoint(args: Namespace, config: Config) -> Optional[Checkpoint]:
    """Check for existing checkpoint file."""
    checkpoint_file = config.storage.checkpoint_file
    
    if not checkpoint_file.exists():
        return None
    
    try:
        checkpoint = Checkpoint.load(checkpoint_file)
        
        # Verify checkpoint is compatible
        if not checkpoint.is_compatible(args):
            logger.warning("Checkpoint parameters don't match, ignoring")
            return None
        
        return checkpoint
        
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}")
        return None

def _prompt_resume(checkpoint: Checkpoint) -> bool:
    """Prompt user to resume scrape."""
    print(f"\nFound existing scrape checkpoint from {checkpoint.started_at}")
    print(f"\nProgress:")
    print(f"  Namespaces completed: {checkpoint.namespaces_completed}")
    print(f"  Current namespace: {checkpoint.current_namespace}")
    print(f"  Total progress: {checkpoint.pages_scraped}/{checkpoint.total_pages}")
    
    response = input("\nDo you want to resume this scrape? [y/N]: ")
    return response.lower() in ["y", "yes"]
```

### FullScraper Resume Support

```python
class FullScraper:
    def scrape(
        self,
        namespaces: Optional[List[int]] = None,
        checkpoint: Optional[Checkpoint] = None,
        ...
    ) -> ScrapeResult:
        # Filter namespaces if resuming
        if checkpoint:
            namespaces = [
                ns for ns in namespaces
                if ns not in checkpoint.namespaces_completed
            ]
            logger.info(f"Resuming scrape, skipping {len(checkpoint.namespaces_completed)} namespaces")
        
        # ... rest of scrape logic ...
        
        # Save checkpoint periodically
        if self.checkpoint_callback:
            self.checkpoint_callback(current_state)
```

## Dependencies

- `json` module for checkpoint file
- `scraper.config.StorageConfig.checkpoint_file`
- Database INSERT OR REPLACE semantics

## Testing Requirements

- [ ] Test checkpoint file creation and update
- [ ] Test resume from checkpoint
- [ ] Test checkpoint ignored with --no-resume
- [ ] Test auto-resume with --resume flag
- [ ] Test checkpoint cleanup on completion
- [ ] Test idempotent scraping (re-run safe)
- [ ] Test incompatible checkpoint is ignored

## Documentation

- [ ] Document checkpoint file format
- [ ] Document --resume and --no-resume flags
- [ ] Document resume workflow in README
- [ ] Add FAQ about interrupted scrapes

## Notes

- Resume capability critical for large wikis (hours of scraping)
- Checkpoints should be small (just progress, not data)
- Database inserts must be idempotent for safe resume
- Consider checkpoint versioning for future compatibility
- Prompting user prevents accidental resume of old scrapes
