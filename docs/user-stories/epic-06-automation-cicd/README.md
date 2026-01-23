# Epic 06: Automation & CI/CD

**Epic ID**: epic-06  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 week

## Overview

Implement GitHub Actions workflows for automated monthly scraping, release packaging, and publication. Set up CI/CD for testing, building, and deploying the scraper and SDK with artifact management and release automation.

## Goals

1. Create monthly scheduled scrape workflow
2. Automate release packaging and publication
3. Set up continuous testing on pull requests
4. Implement artifact storage for incremental runs
5. Configure secrets and environment variables
6. Set up notifications for failures
7. Publish Docker images (optional)

## Success Criteria

- ✅ Monthly scrapes run automatically on schedule
- ✅ Releases published to GitHub Releases automatically
- ✅ All tests run on every pull request
- ✅ Artifacts stored for next incremental run
- ✅ Notifications sent on workflow failures
- ✅ Manual trigger works for ad-hoc scrapes
- ✅ Complete workflow documentation

## User Stories

### Monthly Scrape Workflow
- [Story 01: Scheduled Workflow Trigger](story-01_scheduled_trigger.md)
- [Story 02: Download Previous Archive](story-02_download_previous.md)
- [Story 03: Run Incremental Scrape](story-03_run_scrape.md)
- [Story 04: Generate Statistics](story-04_generate_stats.md)
- [Story 05: Package Release](story-05_package_release.md)
- [Story 06: Create GitHub Release](story-06_create_release.md)
- [Story 07: Upload Release Artifacts](story-07_upload_artifacts.md)

### Artifact Management
- [Story 08: Store Database Artifact](story-08_store_artifact.md)
- [Story 09: Artifact Retention Policy](story-09_retention_policy.md)
- [Story 10: Handle Large Artifacts](story-10_large_artifacts.md)

### Testing & Quality
- [Story 11: Pull Request Testing](story-11_pr_testing.md)
- [Story 12: Code Coverage Reporting](story-12_coverage_reporting.md)
- [Story 13: Linting Workflow](story-13_linting.md)

### Notifications & Monitoring
- [Story 14: Failure Notifications](story-14_notifications.md)
- [Story 15: Success Notifications](story-15_success_notify.md)
- [Story 16: Workflow Status Badges](story-16_status_badges.md)

### Manual Operations
- [Story 17: Manual Workflow Trigger](story-17_manual_trigger.md)
- [Story 18: Emergency Full Scrape](story-18_emergency_full.md)

### Optional Enhancements
- [Story 19: Docker Image Build](story-19_docker_build.md)
- [Story 20: Publish to GHCR](story-20_ghcr_publish.md)

## Dependencies

### Requires:
- Epic 01: Core scraper (scraper to run)
- Epic 03: Incremental updates (for monthly updates)
- Epic 04: Export & packaging (for release creation)

### Blocks:
- None (final epic in automation chain)

## Technical Notes

### Monthly Workflow Structure

```yaml
name: Monthly Wiki Archive

on:
  schedule:
    - cron: '0 2 1 * *'  # 2 AM on 1st of each month
  workflow_dispatch:  # Manual trigger

jobs:
  scrape-and-release:
    runs-on: ubuntu-latest
    timeout-minutes: 4320  # 3 days max
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .
      
      - name: Download previous archive
        uses: actions/download-artifact@v4
        with:
          name: irowiki-database
          path: data/
        continue-on-error: true
      
      - name: Run scraper
        run: |
          python -m scraper scrape --config config.yaml --incremental
      
      - name: Generate statistics
        run: |
          python -m scraper stats --output release-notes.md
      
      - name: Package release
        run: |
          bash scripts/package-release.sh
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ github.run_number }}-$(date +%Y%m)
          name: iRO Wiki Archive - $(date +%Y-%m)
          body_path: release-notes.md
          files: |
            releases/*.tar.gz
            releases/*.tar.gz.sha256
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Upload database artifact
        uses: actions/upload-artifact@v4
        with:
          name: irowiki-database
          path: data/irowiki.db
          retention-days: 90
```

### PR Testing Workflow

```yaml
name: Test

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  test-python:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install -e .
      
      - name: Run tests
        run: pytest tests/ -v --cov=scraper --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Lint
        run: |
          black --check scraper/ tests/
          flake8 scraper/ tests/
          mypy scraper/
  
  test-go:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Run tests
        run: |
          cd sdk
          go test ./... -v -race -coverprofile=coverage.out
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./sdk/coverage.out
```

### Secrets Configuration

Required secrets in GitHub repository settings:
- `GITHUB_TOKEN` (automatic, for releases)
- `CODECOV_TOKEN` (optional, for code coverage)
- `DISCORD_WEBHOOK` (optional, for notifications)

### Artifact Storage Strategy

**Database Artifact:**
- Stored after each scrape
- Used by next incremental run
- 90-day retention (covers 3 months)
- ~500 MB - 2 GB size

**Release Artifacts:**
- Stored indefinitely in GitHub Releases
- Split if >2GB (GitHub limit)
- Include checksums for verification

### Notification Strategy

**Failure Notifications:**
- Email to repository owner
- Optional: Discord webhook
- Include error logs
- Retry instructions

**Success Notifications:**
- Optional: Discord announcement
- Include release link
- Include statistics

### Manual Trigger Use Cases

1. **Ad-hoc scrape**: User requests immediate update
2. **Testing**: Validate workflow changes
3. **Recovery**: Re-run after failure
4. **Emergency**: Capture content before deletion

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/ci/sample_config.yaml` - Test workflow config
- `fixtures/ci/mock_github_env.sh` - Mock GitHub environment

### Test Utilities
- `tests/utils/ci_helpers.py` - Simulate CI environment
- `scripts/test-workflow-local.sh` - Test workflow locally

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |
| Story 14 | Not Started | - | - |
| Story 15 | Not Started | - | - |
| Story 16 | Not Started | - | - |
| Story 17 | Not Started | - | - |
| Story 18 | Not Started | - | - |
| Story 19 | Not Started | - | - |
| Story 20 | Not Started | - | - |

## Definition of Done

- [ ] All 20 user stories completed
- [ ] Monthly workflow runs successfully
- [ ] Release automatically published
- [ ] PR tests run on every pull request
- [ ] Artifacts stored and retrieved correctly
- [ ] Notifications working
- [ ] Manual trigger functional
- [ ] All workflows documented
- [ ] Status badges added to README
- [ ] Design document created and approved
- [ ] Workflows tested and verified
