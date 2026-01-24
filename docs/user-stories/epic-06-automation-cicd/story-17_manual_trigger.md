# Story 17: Manual Workflow Trigger

**Story ID**: epic-06-story-17  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 1 hour  
**Status**: Not Started

## User Story

**As a** project maintainer  
**I want** to manually trigger scrape workflows when needed  
**So that** I can run ad-hoc updates or test the workflow

## Acceptance Criteria

1. **Manual Trigger Button**
   - [ ] "Run workflow" button in GitHub Actions UI
   - [ ] Accessible from Actions tab
   - [ ] Clear workflow name and description
   - [ ] Confirmation before running

2. **Configurable Options**
   - [ ] Choose scrape type (incremental/full)
   - [ ] Optional parameters (force, notify, etc.)
   - [ ] Branch selection
   - [ ] Input validation

3. **Use Cases**
   - [ ] Test workflow changes
   - [ ] Emergency scrape before wiki changes
   - [ ] Recover from failed automated run
   - [ ] Create special release

4. **Logging**
   - [ ] Log who triggered manually
   - [ ] Log manual trigger reason/notes
   - [ ] Distinguish from scheduled runs
   - [ ] Track manual trigger frequency

## Technical Details

### Workflow Dispatch Configuration

```yaml
name: Monthly Wiki Archive

on:
  schedule:
    - cron: '0 2 1 * *'
  
  workflow_dispatch:
    inputs:
      scrape_type:
        description: 'Type of scrape to run'
        required: true
        default: 'incremental'
        type: choice
        options:
          - incremental
          - full
      
      force:
        description: 'Force full scrape even if database exists'
        required: false
        default: false
        type: boolean
      
      announce:
        description: 'Announce release on Discord/Slack'
        required: false
        default: false
        type: boolean
      
      reason:
        description: 'Reason for manual trigger (optional)'
        required: false
        type: string

jobs:
  scrape-and-release:
    runs-on: ubuntu-latest
    
    steps:
      - name: Log trigger information
        run: |
          echo "=== Workflow Trigger Information ==="
          echo "Event: ${{ github.event_name }}"
          echo "Triggered by: ${{ github.actor }}"
          echo "Branch: ${{ github.ref_name }}"
          
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo ""
            echo "=== Manual Trigger Parameters ==="
            echo "Scrape type: ${{ github.event.inputs.scrape_type }}"
            echo "Force: ${{ github.event.inputs.force }}"
            echo "Announce: ${{ github.event.inputs.announce }}"
            echo "Reason: ${{ github.event.inputs.reason || 'Not provided' }}"
          else
            echo "Scheduled run (automatic)"
          fi
```

### Use Input Parameters

```yaml
- name: Determine scrape parameters
  id: scrape-params
  run: |
    if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
      # Manual trigger - use inputs
      SCRAPE_TYPE="${{ github.event.inputs.scrape_type }}"
      FORCE="${{ github.event.inputs.force }}"
      ANNOUNCE="${{ github.event.inputs.announce }}"
    else
      # Scheduled run - use defaults
      SCRAPE_TYPE="incremental"
      FORCE="false"
      ANNOUNCE="true"
    fi
    
    echo "scrape_type=$SCRAPE_TYPE" >> $GITHUB_OUTPUT
    echo "force=$FORCE" >> $GITHUB_OUTPUT
    echo "announce=$ANNOUNCE" >> $GITHUB_OUTPUT

- name: Run scraper
  run: |
    CMD="python -m scraper scrape --config config.yaml"
    
    if [[ "${{ steps.scrape-params.outputs.scrape_type }}" == "full" ]]; then
      CMD="$CMD --force-full"
    else
      CMD="$CMD --incremental"
    fi
    
    if [[ "${{ steps.scrape-params.outputs.force }}" == "true" ]]; then
      CMD="$CMD --force"
    fi
    
    echo "Running: $CMD"
    $CMD
```

### Record Manual Trigger in Database

```yaml
- name: Record trigger metadata
  run: |
    sqlite3 data/irowiki.db <<SQL
    CREATE TABLE IF NOT EXISTS workflow_triggers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      trigger_time TEXT NOT NULL,
      trigger_type TEXT NOT NULL,
      triggered_by TEXT,
      scrape_type TEXT,
      reason TEXT,
      run_id INTEGER
    );
    
    INSERT INTO workflow_triggers (
      trigger_time,
      trigger_type,
      triggered_by,
      scrape_type,
      reason,
      run_id
    ) VALUES (
      datetime('now'),
      '${{ github.event_name }}',
      '${{ github.actor }}',
      '${{ steps.scrape-params.outputs.scrape_type }}',
      '${{ github.event.inputs.reason }}',
      ${{ github.run_number }}
    );
    SQL
```

### Manual Trigger Documentation

```markdown
## Manual Workflow Trigger

### How to Trigger

1. Go to [Actions tab](../../actions)
2. Select "Monthly Wiki Archive" workflow
3. Click "Run workflow" button
4. Fill in parameters:
   - **Scrape type**: `incremental` or `full`
   - **Force**: Check to force full scrape
   - **Announce**: Check to announce release
   - **Reason**: Optional description
5. Click "Run workflow"

### When to Use Manual Trigger

**Incremental Scrape:**
- Test workflow changes
- Capture recent updates immediately
- Create interim release

**Full Scrape:**
- After major wiki changes
- Recover from database corruption
- Rebuild from scratch
- Before wiki shutdown/migration

### Parameters

- **Scrape Type**:
  - `incremental`: Only fetch changes since last run (faster)
  - `full`: Scrape entire wiki from scratch (slower)

- **Force**:
  - Check this to ignore existing database and start fresh
  - Useful if database is corrupted

- **Announce**:
  - Check to post release announcement to Discord/Slack
  - Unchecked for test runs

- **Reason**:
  - Optional note explaining why manual trigger was needed
  - Stored in workflow logs and database

### Examples

**Quick update:**
```
Scrape type: incremental
Force: No
Announce: No
Reason: Testing new parser
```

**Emergency backup:**
```
Scrape type: full
Force: Yes
Announce: Yes
Reason: Wiki announced shutdown next week
```
```

### Multiple Workflow Triggers

```yaml
# Separate workflow for emergency full scrape
name: Emergency Full Scrape

on:
  workflow_dispatch:
    inputs:
      reason:
        description: 'Reason for emergency scrape'
        required: true
        type: string

jobs:
  emergency-scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 4320
    
    steps:
      - name: Notify start
        run: |
          echo "🚨 Emergency full scrape initiated"
          echo "Reason: ${{ github.event.inputs.reason }}"
          echo "Triggered by: ${{ github.actor }}"
      
      # ... scrape steps
```

## Dependencies

- **Story 01**: Scheduled workflow trigger (base workflow)

## Implementation Notes

- `workflow_dispatch` is built into GitHub Actions
- Inputs are optional but provide better UX
- Input types: string, boolean, choice, environment
- Inputs available via `github.event.inputs.*`
- Manual triggers don't count against schedule limits
- Can be triggered via GitHub CLI: `gh workflow run`
- API access available for automation
- Test manual trigger before relying on schedule

## Testing Requirements

- [ ] Test manual trigger from UI
- [ ] Test with different input combinations
- [ ] Test incremental scrape option
- [ ] Test full scrape option
- [ ] Test force flag
- [ ] Test announce flag
- [ ] Test with/without reason
- [ ] Verify inputs logged correctly

## Definition of Done

- [ ] `workflow_dispatch` configured with inputs
- [ ] Input parameters implemented
- [ ] Parameter handling logic implemented
- [ ] Trigger metadata logging implemented
- [ ] Documentation written
- [ ] Tested manual trigger
- [ ] All input combinations tested
- [ ] Code reviewed and approved
