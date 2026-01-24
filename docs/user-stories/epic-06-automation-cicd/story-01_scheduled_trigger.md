# Story 01: Scheduled Workflow Trigger

**Story ID**: epic-06-story-01  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** project maintainer  
**I want** the wiki scraper to run automatically on the 1st of each month  
**So that** the archive stays up-to-date without manual intervention

## Acceptance Criteria

1. **Scheduled Trigger**
   - [ ] Workflow triggers on cron schedule (1st of month at 2 AM UTC)
   - [ ] Schedule configured in workflow YAML
   - [ ] Workflow runs consistently without manual intervention
   - [ ] Timezone set to UTC for predictable execution

2. **Workflow Configuration**
   - [ ] Workflow named clearly ("Monthly Wiki Archive")
   - [ ] Timeout set to 72 hours (3 days) for long-running scrapes
   - [ ] Runs on `ubuntu-latest` runner
   - [ ] Workflow file in `.github/workflows/` directory

3. **Manual Override**
   - [ ] `workflow_dispatch` enabled for manual triggers
   - [ ] Manual trigger accessible from GitHub Actions UI
   - [ ] Manual runs use same configuration as scheduled runs
   - [ ] Logs clearly show trigger source

4. **Error Handling**
   - [ ] Workflow fails gracefully on timeout
   - [ ] Error logs preserved for debugging
   - [ ] Workflow status visible in Actions tab
   - [ ] Failed runs don't block next scheduled run

## Technical Details

### Workflow YAML

```yaml
name: Monthly Wiki Archive

on:
  schedule:
    # Run at 2 AM UTC on the 1st of every month
    - cron: '0 2 1 * *'
  
  workflow_dispatch:
    # Allow manual trigger from GitHub Actions UI
    inputs:
      scrape_type:
        description: 'Type of scrape to run'
        required: false
        default: 'incremental'
        type: choice
        options:
          - incremental
          - full

jobs:
  scrape-and-release:
    name: Scrape Wiki and Create Release
    runs-on: ubuntu-latest
    timeout-minutes: 4320  # 3 days max (72 hours)
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Log trigger information
        run: |
          echo "Workflow triggered by: ${{ github.event_name }}"
          echo "Trigger time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "Manual trigger - Scrape type: ${{ github.event.inputs.scrape_type }}"
          else
            echo "Scheduled trigger"
          fi
```

### Cron Schedule Explanation

The cron expression `'0 2 1 * *'` breaks down as:
- `0` - Minute (0th minute)
- `2` - Hour (2 AM)
- `1` - Day of month (1st)
- `*` - Month (every month)
- `*` - Day of week (any day)

This means: "At 02:00 UTC on day 1 of every month"

### Timezone Considerations

GitHub Actions always uses UTC for cron schedules. This is important to remember:
- `2 AM UTC` = `6 PM PST` (previous day)
- `2 AM UTC` = `7 PM PDT` (previous day)
- `2 AM UTC` = `10 AM JST` (same day)

Early morning UTC avoids conflicts with peak usage hours.

### Timeout Calculation

```yaml
timeout-minutes: 4320  # 3 days
```

Why 3 days?
- Full scrape can take 24-48 hours
- Includes buffer for retries and rate limiting
- Prevents runaway processes
- GitHub Actions has 72-hour max timeout

## Dependencies

- None (this is the foundation of the CI/CD system)

## Implementation Notes

- Create workflow file: `.github/workflows/monthly-scrape.yml`
- Test manual trigger first before relying on schedule
- Monitor first scheduled run to verify timing
- Consider GitHub Actions usage limits (2000 minutes/month free tier)
- Scheduled workflows may be delayed during high GitHub load

## Testing Requirements

- [ ] Manual trigger test from GitHub Actions UI
- [ ] Verify workflow appears in Actions list
- [ ] Test both scheduled and manual trigger paths
- [ ] Verify timeout enforcement (can simulate with sleep command)
- [ ] Check workflow logs are accessible
- [ ] Confirm workflow runs on schedule (may require waiting for next month)

## Definition of Done

- [ ] Workflow file created at `.github/workflows/monthly-scrape.yml`
- [ ] Cron schedule configured correctly
- [ ] Manual trigger tested and working
- [ ] Timeout configured to 3 days
- [ ] Workflow name and description clear
- [ ] Trigger logging implemented
- [ ] Documentation added to README
- [ ] Code reviewed and approved
