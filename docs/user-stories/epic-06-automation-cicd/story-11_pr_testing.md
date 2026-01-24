# Story 11: Pull Request Testing

**Story ID**: epic-06-story-11  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** all tests to run automatically on pull requests  
**So that** code quality is maintained and bugs are caught early

## Acceptance Criteria

1. **Test Workflow**
   - [ ] Workflow triggers on all pull requests
   - [ ] Tests run for both Python and Go code
   - [ ] All test suites execute successfully
   - [ ] Workflow blocks merge if tests fail

2. **Test Coverage**
   - [ ] Unit tests run for all modules
   - [ ] Integration tests run where applicable
   - [ ] Coverage reports generated
   - [ ] Minimum coverage threshold enforced

3. **Multiple Environments**
   - [ ] Test on multiple Python versions (3.10, 3.11, 3.12)
   - [ ] Test on multiple OS (Ubuntu, macOS, Windows)
   - [ ] Test with different database backends
   - [ ] Matrix builds configured

4. **Fast Feedback**
   - [ ] Tests complete in <10 minutes
   - [ ] Parallel test execution
   - [ ] Cache dependencies for speed
   - [ ] Clear error messages on failure

## Technical Details

### Test Workflow

```yaml
name: Tests

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  test-python:
    name: Python Tests
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.10', '3.11', '3.12']
      fail-fast: false  # Continue even if one fails
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install -e .
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --tb=short
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v --tb=short
      
      - name: Run tests with coverage
        run: |
          pytest tests/ \
            -v \
            --cov=scraper \
            --cov-report=xml \
            --cov-report=term \
            --cov-report=html
      
      - name: Upload coverage reports
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          flags: python-${{ matrix.python-version }}
          name: python-${{ matrix.python-version }}-${{ matrix.os }}
        env:
          CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
      
      - name: Upload coverage HTML
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-html-${{ matrix.os }}-${{ matrix.python-version }}
          path: htmlcov/

  test-go:
    name: Go Tests
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        go-version: ['1.21', '1.22']
      fail-fast: false
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Go ${{ matrix.go-version }}
        uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}
          cache: true
          cache-dependency-path: sdk/go.sum
      
      - name: Download dependencies
        working-directory: sdk
        run: go mod download
      
      - name: Run tests
        working-directory: sdk
        run: |
          go test ./... -v -race -coverprofile=coverage.out -covermode=atomic
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./sdk/coverage.out
          flags: go-${{ matrix.go-version }}
          name: go-${{ matrix.go-version }}-${{ matrix.os }}
        env:
          CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}

  lint:
    name: Linting
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install black flake8 mypy pylint
          pip install -r requirements.txt
      
      - name: Run Black
        run: black --check scraper/ tests/
      
      - name: Run Flake8
        run: flake8 scraper/ tests/ --max-line-length=100
      
      - name: Run MyPy
        run: mypy scraper/
      
      - name: Run Pylint
        run: pylint scraper/ --fail-under=8.0

  test-summary:
    name: Test Summary
    runs-on: ubuntu-latest
    needs: [test-python, test-go, lint]
    if: always()
    
    steps:
      - name: Check test results
        run: |
          if [[ "${{ needs.test-python.result }}" != "success" ]]; then
            echo "❌ Python tests failed"
            exit 1
          fi
          
          if [[ "${{ needs.test-go.result }}" != "success" ]]; then
            echo "❌ Go tests failed"
            exit 1
          fi
          
          if [[ "${{ needs.lint.result }}" != "success" ]]; then
            echo "❌ Linting failed"
            exit 1
          fi
          
          echo "✅ All tests passed!"
```

### Branch Protection Rules

```yaml
# Configure in GitHub repo settings
branch_protection:
  main:
    required_status_checks:
      strict: true
      checks:
        - "Python Tests (ubuntu-latest, 3.11)"
        - "Go Tests (ubuntu-latest, 1.22)"
        - "Linting"
    required_pull_request_reviews:
      required_approving_review_count: 1
    enforce_admins: false
    allow_force_pushes: false
    allow_deletions: false
```

### Fast Test Configuration

```yaml
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    -n auto  # Parallel execution with pytest-xdist
    --maxfail=3  # Stop after 3 failures
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

### Parallel Test Execution

```yaml
- name: Run tests in parallel
  run: |
    # Install pytest-xdist for parallel execution
    pip install pytest-xdist
    
    # Run with auto CPU detection
    pytest tests/ -n auto --dist loadscope
```

### Test with Different Databases

```yaml
test-databases:
  name: Test Database Backends
  runs-on: ubuntu-latest
  strategy:
    matrix:
      database: [sqlite, postgres]
  
  services:
    postgres:
      image: postgres:15
      env:
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: test_irowiki
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
      ports:
        - 5432:5432
  
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
    
    - name: Run tests with ${{ matrix.database }}
      env:
        TEST_DATABASE: ${{ matrix.database }}
        DATABASE_URL: ${{ matrix.database == 'postgres' && 'postgresql://postgres:postgres@localhost:5432/test_irowiki' || '' }}
      run: |
        pytest tests/ -v -m "not slow"
```

## Dependencies

- None (this is a foundational quality check)

## Implementation Notes

- Use matrix builds for multiple environments
- Cache dependencies to speed up workflow
- Use `pytest-xdist` for parallel test execution
- Set up branch protection to require passing tests
- Consider using `pytest-timeout` to prevent hanging tests
- Upload coverage to Codecov or similar service
- Keep tests fast (<10 minutes total)
- Use `fail-fast: false` to see all failures

## Testing Requirements

- [ ] Test workflow triggers on PR creation
- [ ] Test workflow triggers on PR update
- [ ] Test workflow blocks merge on failure
- [ ] Test all matrix combinations work
- [ ] Verify coverage reports upload correctly
- [ ] Test parallel execution works
- [ ] Verify caching speeds up subsequent runs
- [ ] Test with intentionally failing test

## Definition of Done

- [ ] Test workflow created
- [ ] Matrix builds configured
- [ ] Coverage reporting implemented
- [ ] Linting integrated
- [ ] Branch protection configured
- [ ] Parallel execution enabled
- [ ] Cache configured
- [ ] Tested with real PR
- [ ] Documentation updated
- [ ] Code reviewed and approved
