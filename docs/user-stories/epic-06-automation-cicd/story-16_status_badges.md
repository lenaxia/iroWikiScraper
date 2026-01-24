# Story 16: Workflow Status Badges

**Story ID**: epic-06-story-16  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Low  
**Estimate**: 1 hour  
**Status**: Not Started

## User Story

**As a** repository visitor  
**I want** to see workflow status badges in the README  
**So that** I can quickly assess the project's health and build status

## Acceptance Criteria

1. **Build Status Badge**
   - [ ] Badge shows latest workflow status
   - [ ] Updates automatically
   - [ ] Links to workflow runs
   - [ ] Shows passing/failing state

2. **Coverage Badge**
   - [ ] Badge shows test coverage percentage
   - [ ] Color-coded by coverage level
   - [ ] Links to coverage report
   - [ ] Updates on every run

3. **Release Badge**
   - [ ] Badge shows latest release version
   - [ ] Links to latest release
   - [ ] Shows release date
   - [ ] Auto-updates on new release

4. **Additional Badges**
   - [ ] License badge
   - [ ] Language badges (Python, Go)
   - [ ] GitHub stars/forks
   - [ ] Last commit date

## Technical Details

### Workflow Status Badges

```markdown
# README.md

# iRO Wiki Scraper

![Monthly Scrape](https://github.com/OWNER/REPO/actions/workflows/monthly-scrape.yml/badge.svg)
![Tests](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)
![Lint](https://github.com/OWNER/REPO/actions/workflows/lint.yml/badge.svg)

<!-- Or with links -->
[![Monthly Scrape](https://github.com/OWNER/REPO/actions/workflows/monthly-scrape.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/monthly-scrape.yml)
[![Tests](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/test.yml)
```

### Coverage Badges

```markdown
<!-- Codecov -->
[![codecov](https://codecov.io/gh/OWNER/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/OWNER/REPO)

<!-- Or shields.io -->
![Coverage](https://img.shields.io/codecov/c/github/OWNER/REPO?logo=codecov)
```

### Release Badges

```markdown
[![GitHub release](https://img.shields.io/github/v/release/OWNER/REPO)](https://github.com/OWNER/REPO/releases/latest)
[![GitHub Release Date](https://img.shields.io/github/release-date/OWNER/REPO)](https://github.com/OWNER/REPO/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/OWNER/REPO/total)](https://github.com/OWNER/REPO/releases)
```

### Language and Quality Badges

```markdown
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![Go](https://img.shields.io/badge/go-1.21%20%7C%201.22-blue?logo=go)](https://golang.org/)
[![License](https://img.shields.io/github/license/OWNER/REPO)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
```

### Repository Stats Badges

```markdown
[![GitHub stars](https://img.shields.io/github/stars/OWNER/REPO?style=social)](https://github.com/OWNER/REPO/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/OWNER/REPO?style=social)](https://github.com/OWNER/REPO/network/members)
[![GitHub issues](https://img.shields.io/github/issues/OWNER/REPO)](https://github.com/OWNER/REPO/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/OWNER/REPO)](https://github.com/OWNER/REPO/commits/main)
```

### Complete Badge Section

```markdown
# iRO Wiki Scraper

[![Monthly Scrape](https://github.com/OWNER/REPO/actions/workflows/monthly-scrape.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/monthly-scrape.yml)
[![Tests](https://github.com/OWNER/REPO/actions/workflows/test.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/OWNER/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/OWNER/REPO)
[![GitHub release](https://img.shields.io/github/v/release/OWNER/REPO)](https://github.com/OWNER/REPO/releases/latest)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![Go 1.21+](https://img.shields.io/badge/go-1.21%20%7C%201.22-blue?logo=go)](https://golang.org/)
[![License: MIT](https://img.shields.io/github/license/OWNER/REPO)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> Automated monthly archival of the iRO Wiki with full history preservation.

## Features

...
```

### Custom Status Badge

```yaml
# If you need a custom badge, you can create one in the workflow
- name: Create status badge
  if: always()
  run: |
    if [[ "${{ job.status }}" == "success" ]]; then
      COLOR="brightgreen"
      STATUS="passing"
    else
      COLOR="red"
      STATUS="failing"
    fi
    
    curl "https://img.shields.io/badge/scrape-$STATUS-$COLOR" \
      -o badge.svg
    
    # Upload to GitHub Pages or artifact
    echo "Badge: https://img.shields.io/badge/scrape-$STATUS-$COLOR"
```

### Dynamic Badges with Shields.io

```markdown
<!-- Custom endpoint badge -->
![Last Scrape](https://img.shields.io/badge/dynamic/json?url=https://api.github.com/repos/OWNER/REPO/releases/latest&label=last%20scrape&query=$.created_at&color=blue)

<!-- Repository size -->
![Repo Size](https://img.shields.io/github/repo-size/OWNER/REPO)

<!-- Archive size from release -->
![Archive Size](https://img.shields.io/github/downloads/OWNER/REPO/latest/total)
```

## Dependencies

- **Story 06**: Create GitHub release (for release badges)
- **Story 12**: Code coverage reporting (for coverage badges)

## Implementation Notes

- GitHub Actions badges update automatically
- Use shields.io for custom badges
- Keep badges at top of README
- Link badges to relevant pages
- Don't overdo it (5-8 badges is enough)
- Arrange badges logically (status, then quality, then meta)
- Use `style=flat-square` for cleaner look
- Test badge URLs before committing

## Testing Requirements

- [ ] Verify all badge URLs work
- [ ] Test badge links lead to correct pages
- [ ] Verify badges update after workflow runs
- [ ] Test with different workflow statuses
- [ ] Check badges on mobile/different browsers
- [ ] Verify coverage badge updates
- [ ] Test release badge shows latest version
- [ ] Check badge formatting in README

## Definition of Done

- [ ] Badge URLs added to README
- [ ] All badges working
- [ ] Badges properly linked
- [ ] README formatting looks good
- [ ] Tested with real workflow runs
- [ ] Documentation updated if needed
- [ ] Code reviewed and approved
