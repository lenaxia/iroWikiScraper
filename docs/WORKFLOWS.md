# GitHub Actions Workflows Documentation

This document describes all GitHub Actions workflows implemented for automated CI/CD.

## Overview

The project uses GitHub Actions for:
- **Automated monthly scraping** - Scrapes the wiki on the 1st of each month
- **Continuous testing** - Runs tests on all PRs and commits to main
- **Code quality** - Enforces linting and formatting standards
- **Release automation** - Packages and publishes releases automatically
- **Notifications** - Sends alerts on release publication

## Workflows

### 1. Monthly Scrape (`monthly-scrape.yml`)

**Purpose**: Automatically scrape the wiki and create releases on a monthly schedule.

**Triggers**:
- Schedule: 1st of each month at 2 AM UTC (cron: `0 2 1 * *`)
- Manual: workflow_dispatch with configurable parameters

**Parameters** (manual trigger):
- `scrape_type`: incremental (default) or full
- `force`: Force full scrape even if database exists
- `create_release`: Create GitHub release (default: true)
- `announce`: Send Discord/Slack notification (default: false for manual)
- `reason`: Optional reason for triggering

**Workflow Steps**:
1. Check out repository
2. Set up Python 3.11 environment
3. Download previous database artifact (if exists)
4. Run incremental or full scrape
5. Generate statistics and release notes
6. Package releases (database, full archive, XML)
7. Create GitHub release with version tag
8. Upload database artifact for next run
9. Send notifications (if configured)

**Artifacts**:
- Database: `irowiki-database` (90-day retention)
- Logs: `scrape-logs-{run_number}` (30-day retention)

**Secrets Used**:
- `GITHUB_TOKEN` (automatic) - For creating releases
- `DISCORD_WEBHOOK_URL` (optional) - For Discord notifications
- `SLACK_WEBHOOK_URL` (optional) - For Slack notifications

**Timeout**: 4320 minutes (3 days)

---

### 2. Tests (`test.yml`)

**Purpose**: Run comprehensive tests on all code changes.

**Triggers**:
- Pull requests to main
- Pushes to main

**Test Matrix**:
- **Python**: 3.10, 3.11, 3.12 on Ubuntu
- **Go**: 1.21, 1.22 on Ubuntu

**Test Jobs**:
1. **Python Tests**
   - Unit and integration tests with pytest
   - Code coverage reporting (Codecov)
   - Parallel execution with pytest-xdist
   - Coverage threshold enforcement

2. **Go Tests**
   - Unit tests with race detector
   - Code coverage reporting (Codecov)
   - Test all SDK packages

3. **Python Linting**
   - Black (formatting)
   - isort (import sorting)
   - Flake8 (style guide)
   - MyPy (type checking, non-blocking)

4. **Go Linting**
   - go fmt (formatting)
   - go vet (code analysis)
   - golangci-lint (comprehensive linting)
   - staticcheck (static analysis, non-blocking)

5. **Test Summary**
   - Aggregates results from all test jobs
   - Fails if any critical test fails

**Secrets Used**:
- `CODECOV_TOKEN` (optional) - For coverage reporting

**Typical Duration**: 5-10 minutes

---

### 3. Manual Scrape (`manual-scrape.yml`)

**Purpose**: On-demand scraping for testing or emergency updates.

**Triggers**:
- Manual: workflow_dispatch only

**Parameters**:
- `scrape_type`: incremental or full
- `force`: Force full scrape
- `create_release`: Create GitHub release (default: false)
- `notify`: Send notifications (default: false)
- `reason`: Reason for manual trigger (required for logging)

**Differences from Monthly Scrape**:
- Default release creation is disabled
- Default notifications are disabled
- Releases marked as pre-release
- More suitable for testing

**Use Cases**:
- Testing workflow changes
- Emergency wiki backup
- Immediate update capture
- Recovery from failed scheduled run

---

### 4. Release Notifications (`notify-release.yml`)

**Purpose**: Send notifications when releases are published.

**Triggers**:
- release: published event

**Notification Channels**:
- **Discord**: Rich embed with statistics and download link
- **Slack**: Formatted message with action button

**Extracted Information**:
- Release version and name
- Prerelease status
- Statistics (total pages, revisions, new/updated counts)
- Download URL

**Secrets Used**:
- `DISCORD_WEBHOOK_URL` (optional)
- `SLACK_WEBHOOK_URL` (optional)

---

### 5. Lint (`lint.yml`)

**Purpose**: Dedicated linting workflow for code quality enforcement.

**Triggers**:
- Pull requests to main
- Pushes to main

**Linting Jobs**:
1. **Python Linting**
   - Black (code formatting)
   - isort (import sorting)
   - Flake8 (PEP 8 compliance)
   - MyPy (type checking)
   - Pylint (code analysis)

2. **Go Linting**
   - go fmt (code formatting)
   - go vet (suspicious constructs)
   - golangci-lint (comprehensive checks)
   - staticcheck (bug finding)

3. **YAML Validation**
   - Validate all YAML files
   - actionlint for GitHub Actions syntax

4. **Markdown Linting**
   - markdownlint-cli2 for documentation

**Typical Duration**: 2-3 minutes

---

## Secrets Configuration

### Required Secrets

Navigate to: `Settings > Secrets and variables > Actions`

| Secret | Required | Purpose | How to Get |
|--------|----------|---------|------------|
| `GITHUB_TOKEN` | Yes (automatic) | Create releases, manage artifacts | Provided automatically by GitHub |
| `CODECOV_TOKEN` | Optional | Upload coverage reports | https://codecov.io |
| `DISCORD_WEBHOOK_URL` | Optional | Send Discord notifications | Discord Server Settings > Integrations > Webhooks |
| `SLACK_WEBHOOK_URL` | Optional | Send Slack notifications | Slack App Directory > Incoming Webhooks |

### Setting Up Discord Webhook

1. Go to your Discord server
2. Server Settings > Integrations > Webhooks
3. Click "New Webhook"
4. Name it "iRO Wiki Scraper"
5. Select target channel
6. Copy webhook URL
7. Add to GitHub repository secrets as `DISCORD_WEBHOOK_URL`

### Setting Up Slack Webhook

1. Go to https://api.slack.com/apps
2. Create new app
3. Add "Incoming Webhooks" feature
4. Activate webhooks
5. Add webhook to workspace
6. Copy webhook URL
7. Add to GitHub repository secrets as `SLACK_WEBHOOK_URL`

---

## Artifact Management

### Database Artifact

- **Name**: `irowiki-database`
- **Contents**: `data/irowiki.db`
- **Retention**: 90 days (3 months)
- **Size**: ~500MB - 2GB (compressed)
- **Purpose**: Used by next incremental run
- **Compression**: Maximum (level 9)

### Log Artifacts

- **Name**: `scrape-logs-{run_number}` or `manual-scrape-logs-{run_number}`
- **Contents**: All log files from scrape run
- **Retention**: 30 days
- **Purpose**: Debugging and auditing

### Release Artifacts

- **Storage**: GitHub Releases (permanent)
- **Contents**:
  - `irowiki-database-{version}.tar.gz` - Database only
  - `irowiki-full-{version}.tar.gz` - Database + downloads
  - `*.sha256` - Checksums for verification
- **Split**: Automatically split if >1.9GB

---

## Manual Workflow Triggering

### Via GitHub UI

1. Navigate to repository on GitHub
2. Click "Actions" tab
3. Select workflow from left sidebar
4. Click "Run workflow" button (right side)
5. Fill in parameters
6. Click "Run workflow" to start

### Via GitHub CLI

```bash
# Install GitHub CLI
brew install gh  # macOS
# or
sudo apt install gh  # Ubuntu

# Authenticate
gh auth login

# Trigger monthly scrape
gh workflow run monthly-scrape.yml

# Trigger manual scrape with parameters
gh workflow run manual-scrape.yml \
  -f scrape_type=incremental \
  -f create_release=false \
  -f notify=false \
  -f reason="Testing new feature"
```

### Via REST API

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/OWNER/REPO/actions/workflows/manual-scrape.yml/dispatches \
  -d '{
    "ref":"main",
    "inputs":{
      "scrape_type":"incremental",
      "create_release":"false",
      "notify":"false",
      "reason":"API trigger test"
    }
  }'
```

---

## Status Badges

Add these to README.md:

```markdown
![Monthly Scrape](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/actions/workflows/monthly-scrape.yml/badge.svg)
![Tests](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/actions/workflows/test.yml/badge.svg)
![Lint](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/actions/workflows/lint.yml/badge.svg)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/iRO-Wiki-Scraper/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/iRO-Wiki-Scraper)
```

---

## Monitoring & Debugging

### View Workflow Runs

1. Go to Actions tab
2. Select workflow from left sidebar
3. Click on specific run to view details
4. Click on job to see step-by-step logs
5. Download artifacts from run summary

### Common Issues

#### Workflow Not Triggering on Schedule

**Symptoms**: Monthly scrape doesn't run on the 1st
**Causes**:
- Repository has no recent activity (GitHub may delay inactive repos)
- Schedule syntax error
- Workflow file has YAML errors

**Solutions**:
1. Check workflow YAML syntax
2. Trigger manually to confirm it works
3. Check GitHub status page for scheduled workflow delays
4. Ensure repository had at least one commit in the last 60 days

#### Database Artifact Not Found

**Symptoms**: "Download previous database artifact" step fails
**Causes**:
- First run (no previous artifact exists)
- Artifact expired (>90 days old)
- Previous run failed before uploading

**Solutions**:
- Expected on first run (continue-on-error: true)
- Will perform full scrape automatically
- Check previous run logs

#### Release Creation Fails

**Symptoms**: "Create GitHub Release" step fails
**Causes**:
- Tag already exists
- No write permissions
- Package files missing

**Solutions**:
1. Check if release tag already exists
2. Verify GITHUB_TOKEN has correct permissions
3. Check previous packaging step succeeded
4. Manually delete conflicting tag if needed

#### Tests Failing

**Symptoms**: PR cannot be merged due to test failures
**Solutions**:
1. View test logs in Actions tab
2. Run tests locally: `pytest tests/ -v`
3. Check for:
   - Import errors
   - Missing dependencies
   - Type errors
   - Linting issues
4. Fix issues and push changes

---

## Local Testing

Test workflows locally before pushing:

```bash
# Run local workflow test script
bash scripts/test-workflow-local.sh

# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/monthly-scrape.yml'))"

# Install actionlint for GitHub Actions validation
go install github.com/rhysd/actionlint/cmd/actionlint@latest
actionlint .github/workflows/*.yml

# Test scripts individually
bash scripts/package-release.sh test-v1.0
bash scripts/generate-stats.sh data/irowiki.db
```

---

## Maintenance

### Updating Dependencies

Dependencies are automatically updated by Dependabot:
- GitHub Actions: Weekly on Mondays
- Python packages: Weekly on Mondays
- Go modules: Weekly on Mondays

Review and merge Dependabot PRs regularly.

### Modifying Workflows

1. Edit workflow files in `.github/workflows/`
2. Test locally with `scripts/test-workflow-local.sh`
3. Validate YAML syntax
4. Create PR with changes
5. Test workflow in PR environment
6. Merge after successful tests

### Adding New Workflows

1. Create new YAML file in `.github/workflows/`
2. Follow existing patterns
3. Document in this file
4. Add status badge to README
5. Test thoroughly before relying on it

---

## Support

For issues with workflows:
1. Check workflow run logs
2. Review this documentation
3. Search existing GitHub Issues
4. Create new issue with:
   - Workflow name and run ID
   - Error messages
   - Expected vs actual behavior
   - Steps to reproduce

---

**Last Updated**: 2026-01-24
