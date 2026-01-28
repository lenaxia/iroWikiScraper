# Pre-commit Setup

This repository uses [pre-commit](https://pre-commit.com/) to automatically run code quality checks before each commit.

## Installation

1. Install pre-commit and dev dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Install the git hook scripts:
```bash
pre-commit install
```

## Usage

Once installed, pre-commit will run automatically on `git commit`. The hooks will:
- Format code with `black`
- Sort imports with `isort`
- Check code style with `flake8`
- Remove unused imports with `autoflake`
- Check for common issues (trailing whitespace, merge conflicts, etc.)

### Manual Execution

Run on all files manually:
```bash
pre-commit run --all-files
```

Run on specific files:
```bash
pre-commit run --files scraper/storage/page_repository.py
```

### Skipping Hooks

If you need to commit without running hooks (not recommended):
```bash
git commit --no-verify
```

## Configured Hooks

- **black**: Python code formatter (88 char line length)
- **isort**: Import statement sorter (black-compatible profile)
- **flake8**: Python linter (uses `.flake8` config)
- **autoflake**: Removes unused imports and variables
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with newline
- **check-yaml**: Validates YAML syntax
- **check-merge-conflict**: Detects merge conflict markers
- **prettier**: Formats YAML and Markdown files

## Troubleshooting

### Hook fails locally but passes in CI
- Ensure you're using Python 3.11+ (same as CI)
- Run `pre-commit run --all-files` to see detailed errors

### Update hooks to latest versions
```bash
pre-commit autoupdate
```

### Clear hook cache
```bash
pre-commit clean
```
