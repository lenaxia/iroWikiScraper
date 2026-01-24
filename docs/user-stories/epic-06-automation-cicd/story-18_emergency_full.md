# Story 18: Emergency Full Scrape

**Story ID**: epic-06-story-18  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** project maintainer  
**I want** a dedicated emergency full scrape workflow  
**So that** I can quickly capture the entire wiki before it changes or goes offline

## Acceptance Criteria

1. **Separate Workflow**
   - [ ] Dedicated "Emergency Full Scrape" workflow
   - [ ] Clear name and purpose
   - [ ] Requires confirmation reason
   - [ ] High visibility in Actions list

2. **Priority Execution**
   - [ ] Can run concurrently with other workflows
   - [ ] Longer timeout (7 days)
   - [ ] Ignores rate limits (aggressive mode)
   - [ ] Immediate notification on completion

3. **Complete Capture**
   - [ ] Always runs full scrape
   - [ ] Ignores existing database
   - [ ] Downloads all files
   - [ ] Verifies completeness

4. **Emergency Features**
   - [ ] Fast-track mode (aggressive scraping)
   - [ ] Automatic retry on failure
   - [ ] Progress checkpoints
   - [ ] Immediate release creation

## Technical Details

### Emergency Workflow

```yaml
name: Emergency Full Scrape

on:
  workflow_dispatch:
    inputs:
      reason:
        description: 'Emergency reason (required)'
        required: true
        type: string
      
      aggressive:
        description: 'Use aggressive scraping (faster, may trigger rate limits)'
        required: false
        default: false
        type: boolean
      
      notify_on_progress:
        description: 'Send progress notifications every hour'
        required: false
        default: true
        type: boolean

jobs:
  emergency-scrape:
    name: Emergency Full Wiki Scrape
    runs-on: ubuntu-latest
    timeout-minutes: 10080  # 7 days
    
    steps:
      - name: Alert emergency scrape started
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK_URGENT }}
          status: "in_progress"
          title: "🚨 EMERGENCY FULL SCRAPE STARTED"
          description: |
            **Reason:** ${{ github.event.inputs.reason }}
            **Triggered by:** @${{ github.actor }}
            **Mode:** ${{ github.event.inputs.aggressive == 'true' && 'Aggressive' || 'Normal' }}
          color: 0xff9900
          username: "Emergency Scraper"
      
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .
      
      - name: Create emergency configuration
        run: |
          cat > emergency-config.yaml <<EOF
          base_url: https://irowiki.org
          
          database:
            path: data/emergency-irowiki.db
          
          rate_limit:
            requests_per_second: ${{ github.event.inputs.aggressive == 'true' && '10' || '2' }}
            burst: ${{ github.event.inputs.aggressive == 'true' && '20' || '5' }}
            respect_retry_after: true
          
          scrape:
            full: true
            force: true
            download_files: true
            verify_completeness: true
          
          checkpoints:
            enabled: true
            interval: 1000
          
          retry:
            max_attempts: 10
            backoff_factor: 3
          EOF
      
      - name: Run emergency scrape
        id: scrape
        run: |
          mkdir -p data/ downloads/ logs/
          
          python -m scraper scrape \
            --config emergency-config.yaml \
            --force-full \
            --log-level DEBUG \
            2>&1 | tee logs/emergency-scrape.log
        continue-on-error: true
      
      - name: Monitor progress (background)
        if: github.event.inputs.notify_on_progress == 'true'
        run: |
          # Start background progress monitor
          while kill -0 ${{ steps.scrape.pid }} 2>/dev/null; do
            sleep 3600  # Every hour
            
            # Get current progress
            PAGES=$(sqlite3 data/emergency-irowiki.db "SELECT COUNT(*) FROM pages" 2>/dev/null || echo "0")
            REVISIONS=$(sqlite3 data/emergency-irowiki.db "SELECT COUNT(*) FROM revisions" 2>/dev/null || echo "0")
            
            # Send progress update
            curl -X POST "${{ secrets.DISCORD_WEBHOOK_URGENT }}" \
              -H "Content-Type: application/json" \
              -d "{\"content\": \"⏳ Emergency scrape in progress: $PAGES pages, $REVISIONS revisions\"}"
          done &
      
      - name: Verify completeness
        run: |
          python -m scraper verify \
            --database data/emergency-irowiki.db \
            --strict
      
      - name: Package emergency release
        run: |
          VERSION="emergency-$(date +%Y%m%d-%H%M%S)"
          
          tar -czf "irowiki-emergency-$VERSION.tar.gz" \
            -C data emergency-irowiki.db
          
          sha256sum "irowiki-emergency-$VERSION.tar.gz" > "irowiki-emergency-$VERSION.tar.gz.sha256"
      
      - name: Create emergency release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: emergency-${{ github.run_number }}
          name: "Emergency Backup - ${{ github.event.inputs.reason }}"
          body: |
            ## 🚨 Emergency Full Scrape
            
            **Reason:** ${{ github.event.inputs.reason }}
            **Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
            **Triggered by:** @${{ github.actor }}
            
            This is an emergency full scrape of the iRO Wiki.
            
            See workflow run for details: [${{ github.run_id }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})
          files: |
            irowiki-emergency-*.tar.gz*
          prerelease: true
      
      - name: Upload emergency database artifact
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: emergency-database
          path: data/emergency-irowiki.db
          retention-days: 30
      
      - name: Upload logs
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: emergency-logs
          path: logs/
          retention-days: 30
      
      - name: Notify completion
        if: always()
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK_URGENT }}
          status: ${{ job.status }}
          title: ${{ job.status == 'success' && '✅ EMERGENCY SCRAPE COMPLETED' || '❌ EMERGENCY SCRAPE FAILED' }}
          description: |
            **Reason:** ${{ github.event.inputs.reason }}
            **Status:** ${{ job.status }}
            **Duration:** ${{ job.duration }}
            
            ${{ job.status == 'success' && format('[Download Release]({0}/{1}/releases/tag/emergency-{2})', github.server_url, github.repository, github.run_number) || 'Check logs for details' }}
          color: ${{ job.status == 'success' && '0x00ff00' || '0xff0000' }}
```

### Emergency CLI Command

```bash
#!/bin/bash
# scripts/emergency-scrape.sh

set -e

REASON="${1:-Emergency scrape}"
AGGRESSIVE="${2:-false}"

echo "🚨 Starting emergency full scrape"
echo "Reason: $REASON"

# Trigger via GitHub CLI
gh workflow run emergency-scrape.yml \
  -f reason="$REASON" \
  -f aggressive="$AGGRESSIVE" \
  -f notify_on_progress=true

echo "Emergency scrape triggered"
echo "Monitor progress: gh run watch"
```

### Emergency Scrape Documentation

```markdown
## Emergency Full Scrape

Use this when you need to capture the entire wiki urgently.

### When to Use

- Wiki announced shutdown/migration
- Major content deletion detected
- Server instability/downtime expected
- Legal/copyright takedown imminent
- Testing disaster recovery

### How to Trigger

**Via GitHub UI:**
1. Go to [Actions](../../actions/workflows/emergency-scrape.yml)
2. Click "Run workflow"
3. Enter emergency reason (required)
4. Choose aggressive mode if urgent
5. Click "Run workflow"

**Via CLI:**
```bash
gh workflow run emergency-scrape.yml \
  -f reason="Wiki shutting down tomorrow" \
  -f aggressive=true
```

### Aggressive Mode

When enabled:
- 5x faster scraping (10 req/sec vs 2 req/sec)
- Higher burst limit
- May trigger rate limiting
- Use only when necessary

**Warning:** Aggressive mode may result in temporary IP bans.

### Recovery

Emergency database is stored as:
1. GitHub Release (prerelease, tagged `emergency-*`)
2. Workflow artifact (30 days retention)
3. Can be used to restore normal database

### Post-Emergency

After emergency scrape completes:
1. Verify data completeness
2. Document what happened
3. Update normal schedule if needed
4. Consider running normal scrape to verify
```

## Dependencies

- **Story 01**: Scheduled workflow trigger (base workflow)
- **Story 17**: Manual workflow trigger (extends manual triggers)

## Implementation Notes

- Emergency workflow has higher timeout (7 days vs 3 days)
- Uses separate database file to avoid conflicts
- Creates prerelease (not latest)
- More aggressive rate limiting acceptable
- Sends notifications to urgent channel
- Progress monitoring for long-running scrapes
- Automatic retry with exponential backoff
- Checkpointing for resume capability

## Testing Requirements

- [ ] Test emergency workflow trigger
- [ ] Test with normal mode
- [ ] Test with aggressive mode
- [ ] Test progress notifications
- [ ] Test completion notifications
- [ ] Verify release creation
- [ ] Test with simulated failure
- [ ] Verify artifacts uploaded

## Definition of Done

- [ ] Emergency workflow created
- [ ] Aggressive scraping mode implemented
- [ ] Progress monitoring implemented
- [ ] Emergency release creation implemented
- [ ] Notifications configured
- [ ] CLI helper script created
- [ ] Documentation written
- [ ] Tested end-to-end
- [ ] Code reviewed and approved
