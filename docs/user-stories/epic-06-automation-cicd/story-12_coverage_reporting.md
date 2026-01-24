# Story 12: Code Coverage Reporting

**Story ID**: epic-06-story-12  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** code coverage reports generated and tracked over time  
**So that** I can ensure adequate test coverage and identify untested code

## Acceptance Criteria

1. **Coverage Generation**
   - [ ] Generate coverage reports for Python code
   - [ ] Generate coverage reports for Go code
   - [ ] Coverage calculated per module
   - [ ] Branch coverage included

2. **Coverage Upload**
   - [ ] Upload coverage to Codecov or similar service
   - [ ] Coverage trends tracked over time
   - [ ] PR comments show coverage changes
   - [ ] Coverage badges generated

3. **Coverage Thresholds**
   - [ ] Minimum 80% coverage enforced
   - [ ] PR fails if coverage decreases significantly
   - [ ] Exclude generated/vendored code
   - [ ] Track coverage per package

4. **Reporting**
   - [ ] Coverage report in PR comments
   - [ ] HTML coverage report as artifact
   - [ ] Coverage badge in README
   - [ ] Coverage trends visualization

## Technical Details

### Python Coverage Configuration

```ini
# .coveragerc
[run]
source = scraper
omit =
    */tests/*
    */venv/*
    */__pycache__/*
    */site-packages/*
    */migrations/*
branch = True

[report]
precision = 2
show_missing = True
skip_covered = False
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov

[xml]
output = coverage.xml
```

### Coverage Workflow Step

```yaml
- name: Run tests with coverage
  run: |
    pytest tests/ \
      --cov=scraper \
      --cov-report=xml \
      --cov-report=term \
      --cov-report=html \
      --cov-branch \
      --cov-fail-under=80

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.xml
    flags: unittests
    name: codecov-umbrella
    fail_ci_if_error: true
    verbose: true

- name: Upload HTML coverage report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: htmlcov/
    retention-days: 30
```

### Go Coverage

```yaml
- name: Run Go tests with coverage
  working-directory: sdk
  run: |
    go test ./... \
      -race \
      -coverprofile=coverage.out \
      -covermode=atomic \
      -coverpkg=./...

- name: Generate coverage report
  working-directory: sdk
  run: |
    go tool cover -html=coverage.out -o coverage.html
    go tool cover -func=coverage.out

- name: Upload Go coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./sdk/coverage.out
    flags: go
    name: go-coverage
```

### Coverage Comment on PR

```yaml
- name: Coverage comment
  uses: py-cov-action/python-coverage-comment-action@v3
  with:
    GITHUB_TOKEN: ${{ github.token }}
    MINIMUM_GREEN: 90
    MINIMUM_ORANGE: 80
```

### Codecov Configuration

```yaml
# codecov.yml
coverage:
  status:
    project:
      default:
        target: 80%
        threshold: 2%  # Allow 2% decrease
    patch:
      default:
        target: 80%
  
  ignore:
    - "tests/**"
    - "**/__pycache__/**"
    - "**/venv/**"
    - "setup.py"

comment:
  layout: "reach,diff,flags,tree"
  behavior: default
  require_changes: false
  require_base: false
  require_head: true

github_checks:
  annotations: true
```

### Coverage Badge

```markdown
# README.md
[![codecov](https://codecov.io/gh/OWNER/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/OWNER/REPO)
```

### Coverage Trend Report

```yaml
- name: Generate coverage trend
  run: |
    # Get previous coverage
    PREV_COVERAGE=$(curl -s "https://codecov.io/api/gh/${{ github.repository }}/branch/main" | jq -r '.commit.totals.c')
    
    # Get current coverage
    CURR_COVERAGE=$(python -c "import xml.etree.ElementTree as ET; tree = ET.parse('coverage.xml'); print(tree.getroot().attrib['line-rate'])")
    
    # Calculate change
    CHANGE=$(echo "$CURR_COVERAGE - $PREV_COVERAGE" | bc)
    
    echo "Previous coverage: ${PREV_COVERAGE}%"
    echo "Current coverage: ${CURR_COVERAGE}%"
    echo "Change: ${CHANGE}%"
    
    if (( $(echo "$CHANGE < -2.0" | bc -l) )); then
      echo "⚠️ Coverage decreased by more than 2%"
      exit 1
    fi
```

### Detailed Coverage Report

```yaml
- name: Generate detailed coverage report
  run: |
    # Generate per-module coverage
    coverage report --format=markdown > coverage-report.md
    
    # Add to PR comment
    cat coverage-report.md
    
    # Generate missing lines report
    coverage report --show-missing > coverage-missing.txt
```

## Dependencies

- **Story 11**: Pull request testing (runs coverage)

## Implementation Notes

- Use Codecov for free open-source projects
- Consider alternatives: Coveralls, Code Climate
- Coverage should not significantly slow tests
- Exclude test files from coverage
- Set realistic coverage targets (80-90%)
- Track trends, not just absolute numbers
- HTML reports useful for local debugging
- Branch coverage more comprehensive than line coverage

## Testing Requirements

- [ ] Test coverage generation locally
- [ ] Test Codecov upload works
- [ ] Test PR coverage comments appear
- [ ] Verify coverage thresholds enforced
- [ ] Test with decreasing coverage
- [ ] Test HTML report generation
- [ ] Verify badge updates
- [ ] Test with both Python and Go

## Definition of Done

- [ ] Coverage configuration files created
- [ ] Codecov integration configured
- [ ] Coverage thresholds set
- [ ] PR comment integration working
- [ ] Coverage badge added to README
- [ ] HTML reports uploaded as artifacts
- [ ] Tested with real PRs
- [ ] Documentation updated
- [ ] Code reviewed and approved
