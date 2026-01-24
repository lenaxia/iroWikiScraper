# Story 13: Linting Workflow

**Story ID**: epic-06-story-13  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** automated code linting on every pull request  
**So that** code style is consistent and quality issues are caught early

## Acceptance Criteria

1. **Python Linting**
   - [ ] Black for code formatting
   - [ ] Flake8 for style checking
   - [ ] MyPy for type checking
   - [ ] Pylint for code quality

2. **Go Linting**
   - [ ] gofmt for formatting
   - [ ] golangci-lint for comprehensive linting
   - [ ] go vet for correctness
   - [ ] staticcheck for additional checks

3. **Auto-fix Support**
   - [ ] Suggest fixes in PR comments
   - [ ] Option to auto-commit fixes
   - [ ] Clear instructions for local fixes
   - [ ] Pre-commit hooks documentation

4. **Fast Execution**
   - [ ] Linting completes in <3 minutes
   - [ ] Cache dependencies
   - [ ] Run linters in parallel
   - [ ] Fail fast on critical issues

## Technical Details

### Lint Workflow

```yaml
name: Lint

on:
  pull_request:
  push:
    branches: [ main ]

jobs:
  lint-python:
    name: Lint Python
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install linting tools
        run: |
          pip install black flake8 mypy pylint isort
          pip install -r requirements.txt
      
      - name: Check with Black
        run: |
          black --check --diff scraper/ tests/
      
      - name: Check with isort
        run: |
          isort --check-only --diff scraper/ tests/
      
      - name: Lint with Flake8
        run: |
          flake8 scraper/ tests/ \
            --max-line-length=100 \
            --extend-ignore=E203,W503 \
            --statistics
      
      - name: Type check with MyPy
        run: |
          mypy scraper/ --strict
      
      - name: Lint with Pylint
        run: |
          pylint scraper/ \
            --fail-under=8.0 \
            --output-format=colorized \
            --reports=y

  lint-go:
    name: Lint Go
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          cache: true
      
      - name: Format check
        working-directory: sdk
        run: |
          if [ "$(gofmt -s -l . | wc -l)" -gt 0 ]; then
            echo "Please run gofmt:"
            gofmt -s -d .
            exit 1
          fi
      
      - name: Run go vet
        working-directory: sdk
        run: go vet ./...
      
      - name: Run staticcheck
        uses: dominikh/staticcheck-action@v1
        with:
          version: "latest"
          install-go: false
          working-directory: sdk
      
      - name: Run golangci-lint
        uses: golangci/golangci-lint-action@v4
        with:
          version: latest
          working-directory: sdk
          args: --timeout=5m
```

### Python Linting Configuration

```ini
# .flake8
[flake8]
max-line-length = 100
extend-ignore = E203, W503
exclude =
    .git,
    __pycache__,
    .venv,
    venv,
    build,
    dist
per-file-ignores =
    __init__.py:F401
```

```ini
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py310', 'py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  \.git
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pylint]
max-line-length = 100
disable = [
    "C0111",  # missing-docstring
    "C0103",  # invalid-name
]
```

### Go Linting Configuration

```yaml
# .golangci.yml
linters:
  enable:
    - gofmt
    - govet
    - staticcheck
    - errcheck
    - gosimple
    - ineffassign
    - unused
    - typecheck
    - bodyclose
    - noctx
    - rowserrcheck
    - sqlclosecheck

linters-settings:
  gofmt:
    simplify: true
  
  govet:
    check-shadowing: true
  
  errcheck:
    check-type-assertions: true
    check-blank: true

issues:
  exclude-use-default: false
  max-issues-per-linter: 0
  max-same-issues: 0

run:
  timeout: 5m
  tests: true
```

### Auto-fix PR

```yaml
- name: Auto-fix formatting
  if: failure()
  run: |
    # Auto-format with Black
    black scraper/ tests/
    
    # Auto-format imports with isort
    isort scraper/ tests/
    
    # Check if there are changes
    if [[ -n $(git status --porcelain) ]]; then
      echo "Formatting changes detected"
      git diff
    fi

- name: Create auto-fix commit
  if: github.event_name == 'pull_request'
  uses: stefanzweifel/git-auto-commit-action@v5
  with:
    commit_message: "style: auto-format code"
    file_pattern: "*.py"
```

### Reviewdog Integration

```yaml
- name: Run reviewdog
  uses: reviewdog/action-flake8@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    reporter: github-pr-review
    flake8_args: "--max-line-length=100"
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### Local Linting Script

```bash
#!/bin/bash
# scripts/lint.sh

set -e

echo "=== Running Python linters ==="
black scraper/ tests/
isort scraper/ tests/
flake8 scraper/ tests/
mypy scraper/
pylint scraper/

echo "=== Running Go linters ==="
cd sdk
gofmt -s -w .
go vet ./...
golangci-lint run
staticcheck ./...

echo "✅ All linters passed!"
```

## Dependencies

- **Story 11**: Pull request testing (part of CI pipeline)

## Implementation Notes

- Run formatters before linters
- Black and isort must agree on style
- MyPy strict mode may require gradual adoption
- Pylint can be noisy, tune configuration
- golangci-lint includes many linters
- Consider auto-fixing on push to PR branches
- Pre-commit hooks improve developer experience
- Cache linter dependencies for speed

## Testing Requirements

- [ ] Test with code that passes all linters
- [ ] Test with code that fails each linter
- [ ] Test auto-fix functionality
- [ ] Test with pre-commit hooks locally
- [ ] Verify PR comments appear correctly
- [ ] Test with both Python and Go changes
- [ ] Verify caching speeds up runs
- [ ] Test lint-only changes don't trigger full tests

## Definition of Done

- [ ] Lint workflow created
- [ ] Python linters configured
- [ ] Go linters configured
- [ ] Configuration files created
- [ ] Auto-fix option implemented (optional)
- [ ] Pre-commit hooks documented
- [ ] Local linting script created
- [ ] Tested with real PRs
- [ ] Documentation updated
- [ ] Code reviewed and approved
