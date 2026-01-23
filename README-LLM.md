# iRO-Wiki-Scraper - LLM Implementation Guide

**Version:** 1.0  
**Last Updated:** 2026-01-23  
**Project Status:** Initial Setup

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Critical Guidelines & Hard Rules](#critical-guidelines--hard-rules)
3. [Repository Structure](#repository-structure)
4. [Architecture Overview](#architecture-overview)
5. [Technology Stack](#technology-stack)
6. [Development Workflow](#development-workflow)
7. [Common Commands](#common-commands)
8. [Documentation Standards](#documentation-standards)
9. [Release & Packaging](#release--packaging)

---

## Project Overview

**iRO-Wiki-Scraper** is a complete archival system for irowiki.org (and Classic Wiki) with historical preservation, searchable database, and re-hosting capability.

### Core Purpose

- Archive complete wiki content with ALL historical revisions
- Preserve edit metadata (timestamps, authors, comments)
- Download all media files (images, documents)
- Extract and preserve internal link structure
- Enable temporal queries (content at specific dates, edit patterns)
- Generate MediaWiki XML exports for re-hosting
- Support incremental updates for ongoing archival

### Project Goals

1. **Complete Preservation**: Every page revision, every edit, every file
2. **Searchable Database**: Query by timeframe, author, content, page
3. **Full Metadata**: Edit history, authors, timestamps, comments
4. **Re-hostable**: MediaWiki XML export + files for easy restoration
5. **Incremental Updates**: Monthly scrapes capture only new changes
6. **Versioned Releases**: Automated monthly archives via GitHub Actions

### Primary Source Documents

- [`docs/design/`](docs/design/) - Technical specifications and architecture
- [`docs/worklog/`](docs/worklog/) - Daily progress and decisions
- [`docs/user-stories/`](docs/user-stories/) - Feature requirements by epic
- Schema: `schema/sqlite.sql` and `schema/postgres.sql`

### Data Sources

- **Main Wiki**: https://irowiki.org/w/api.php
- **Classic Wiki**: https://irowiki.org/classic (separate archival)
- **API**: MediaWiki 1.44.0 (no authentication required for reads)

---

## Critical Guidelines & Hard Rules

**⚠️ CRITICAL DEVELOPMENT ORDER:**
1. **Test Infrastructure FIRST** - Fixtures, mocks, conftest.py
2. **Tests SECOND** - Write tests using the infrastructure  
3. **Implementation LAST** - Write code to make tests pass

This order is non-negotiable. See section 9 for details.

### 0. Communication Tone - MANDATORY

**Always be neutral, factual, objective.**

- Do NOT be sensational, overly agreeable, or a sycophant
- Don't be a cheerleader, be a critical collaborator
- Never agree with something just because the user stated it
- Always validate statements with evidence
- Provide honest and objective feedback
- If you agree, do so based on evidence or sound reasoning

### 1. Type Safety First - MANDATORY

**Use strongly-typed structs for all data models. No generic maps for structured data.**

```python
# ❌ FORBIDDEN
data = {
    "page_id": 123,
    "title": "Main_Page",
    "revisions": []
}

# ✅ REQUIRED
@dataclass
class Page:
    page_id: int
    namespace: int
    title: str
    is_redirect: bool
    revisions: List[Revision]

page = Page(
    page_id=123,
    namespace=0,
    title="Main_Page",
    is_redirect=False,
    revisions=[]
)
```

**Rules:**
1. Use `@dataclass` for Python data structures
2. Type hints on all function signatures
3. Validate inputs at API boundaries
4. Never ignore type errors from mypy/pyright
5. Use `Optional[T]` for nullable fields

### 2. Complete Implementation - NO STUBS

**NO TODOs, NO placeholders, NO partial implementations.**

```python
# ❌ FORBIDDEN
def scrape_revisions(self, page_id: int) -> List[Revision]:
    # TODO: implement pagination
    return []

# ✅ REQUIRED
def scrape_revisions(self, page_id: int) -> List[Revision]:
    revisions = []
    continue_token = None
    
    while True:
        batch = self._fetch_revision_batch(page_id, continue_token)
        revisions.extend(batch.revisions)
        
        if not batch.has_more:
            break
        continue_token = batch.continue_token
    
    return revisions
```

If you can't implement something completely, **ask the user** before proceeding.

### 3. Error Handling - MANDATORY

**Explicit error handling. Log errors with context. Retry transient failures.**

```python
# ✅ CORRECT
def fetch_page(self, title: str) -> Page:
    if not title:
        raise ValueError("title cannot be empty")
    
    for attempt in range(self.max_retries):
        try:
            response = self.session.get(
                self.api_url,
                params={"action": "query", "titles": title},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_page(data)
            
        except requests.Timeout as e:
            logger.warning(f"Timeout fetching page {title}, attempt {attempt+1}/{self.max_retries}")
            if attempt == self.max_retries - 1:
                raise APIError(f"Failed to fetch page after {self.max_retries} attempts") from e
            time.sleep(self.retry_delay)
            
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                raise PageNotFoundError(f"Page not found: {title}") from e
            raise APIError(f"HTTP error fetching page: {e}") from e

# ❌ WRONG
def fetch_page(self, title: str) -> Page:
    response = self.session.get(self.api_url, params={"titles": title})
    return response.json()  # No validation, no error handling
```

**Error Patterns:**
- Custom exception types for domain errors
- Wrap third-party exceptions with context
- Retry transient failures (timeouts, rate limits)
- Log errors with full context
- Never silently swallow exceptions

### 4. Respectful Scraping - MANDATORY

**Rate limit all requests. Use appropriate User-Agent. Handle backoff.**

```python
class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0.0
    
    def wait(self):
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()

# Use in API client
self.rate_limiter.wait()
response = self.session.get(url, headers={
    'User-Agent': 'iROWikiArchiver/1.0 (github.com/user/iRO-Wiki-Scraper; contact@example.com)'
})
```

**Rules:**
1. Default rate: 1 request/second (configurable)
2. Respect API's maxlag parameter
3. Exponential backoff on rate limit errors (HTTP 429)
4. Descriptive User-Agent with project info
5. Request timeout: 30 seconds default

### 5. Database Schema Compatibility - MANDATORY

**Schema must work identically on SQLite and PostgreSQL.**

```sql
-- ✅ CORRECT (compatible)
CREATE TABLE pages (
    page_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pages_title ON pages(title);

-- ❌ WRONG (PostgreSQL specific)
CREATE TABLE pages (
    page_id SERIAL PRIMARY KEY,           -- SQLite doesn't have SERIAL
    title TEXT NOT NULL,
    data JSONB                             -- SQLite doesn't have JSONB
);

-- ❌ WRONG (SQLite specific)
CREATE TABLE pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- PostgreSQL uses SERIAL
    title TEXT NOT NULL
);
```

**Compatibility Rules:**
1. Use `INTEGER PRIMARY KEY` (not SERIAL/AUTOINCREMENT)
2. Use `TEXT` for strings (not VARCHAR)
3. Use `TIMESTAMP` for dates (not TIMESTAMPTZ)
4. Use `BOOLEAN` for flags (SQLite stores as 0/1)
5. No JSON columns (store as TEXT, parse in application)
6. Test schema on both databases

### 6. Incremental Updates - MANDATORY

**Track last scrape timestamp. Query only changed content.**

```python
def scrape_incremental(self) -> ScrapeStats:
    # Get last scrape timestamp from database
    last_scrape = self.db.get_last_scrape_time()
    
    if not last_scrape:
        logger.info("No previous scrape found, running full scrape")
        return self.scrape_full()
    
    logger.info(f"Running incremental scrape since {last_scrape}")
    
    # Query API for recent changes
    changes = self.api.get_recent_changes(since=last_scrape)
    
    stats = ScrapeStats()
    for change in changes:
        if change.type == 'new':
            # New page - scrape entire history
            self.scrape_page_full(change.page_id)
            stats.pages_added += 1
        elif change.type == 'edit':
            # Existing page - scrape only new revisions
            self.scrape_page_revisions(change.page_id, since=last_scrape)
            stats.pages_updated += 1
    
    # Update last scrape timestamp
    self.db.set_last_scrape_time(datetime.now())
    
    return stats
```

**Rules:**
1. Store scrape timestamps in `scrape_runs` table
2. Use MediaWiki `recentchanges` API for delta detection
3. Compare revision IDs to avoid duplicates
4. Full scrape if no previous timestamp exists
5. Verify integrity after incremental updates

### 7. Checkpoint & Resume - MANDATORY

**Save progress frequently. Support resuming failed scrapes.**

```python
class Checkpoint:
    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.state = self._load()
    
    def _load(self) -> dict:
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file) as f:
                return json.load(f)
        return {"completed_pages": [], "current_phase": "init"}
    
    def save(self, state: dict):
        with open(self.checkpoint_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def mark_page_complete(self, page_id: int):
        self.state["completed_pages"].append(page_id)
        self.save(self.state)
    
    def is_page_complete(self, page_id: int) -> bool:
        return page_id in self.state["completed_pages"]

# Use in scraper
if self.checkpoint.is_page_complete(page.page_id):
    logger.debug(f"Skipping already completed page: {page.title}")
    continue

self.scrape_page(page)
self.checkpoint.mark_page_complete(page.page_id)
```

**Rules:**
1. Checkpoint after every N pages (configurable, default 10)
2. Store checkpoint state in JSON file
3. Check checkpoint before processing each item
4. Clear checkpoint after successful complete run
5. Log progress with ETA estimates

### 8. Structured Logging - MANDATORY

**Use structured logging with context. Enable debug mode for troubleshooting.**

```python
import logging
import structlog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log'),
        logging.StreamHandler()
    ]
)

logger = structlog.get_logger()

# Use structured logging
logger.info("scrape_started", 
    run_type="incremental",
    last_scrape="2026-01-01T00:00:00Z")

logger.debug("fetching_page",
    page_id=123,
    title="Main_Page",
    namespace=0)

logger.error("scrape_failed",
    page_id=456,
    error=str(e),
    retry_count=3)
```

**Rules:**
1. Use INFO for high-level progress
2. Use DEBUG for detailed operations
3. Use WARNING for recoverable issues
4. Use ERROR for failures
5. Include context (page_id, title, etc.)
6. Rotate log files daily

### 9. Testing Requirements - MANDATORY

**Build test infrastructure FIRST, then write tests BEFORE code. ALWAYS.**

#### Test Infrastructure First (Before Any Tests)

**CRITICAL: Set up test infrastructure before writing any tests or implementation code.**

```python
# 1. Create test fixtures FIRST
# fixtures/sample_page_response.json
{
    "query": {
        "pages": {
            "1": {
                "pageid": 1,
                "title": "Main_Page",
                "revisions": [
                    {"revid": 100, "timestamp": "2020-01-01T00:00:00Z", "user": "Admin"},
                    {"revid": 101, "timestamp": "2020-01-02T00:00:00Z", "user": "Editor"}
                ]
            }
        }
    }
}

# 2. Create mocks and test doubles
# tests/mocks/mock_api_client.py
class MockAPIClient:
    """Mock MediaWiki API client for testing."""
    
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir
        self.call_count = 0
    
    def get_page(self, title: str) -> dict:
        self.call_count += 1
        fixture_file = self.fixtures_dir / f"{title.lower()}.json"
        if not fixture_file.exists():
            raise PageNotFoundError(f"Page not found: {title}")
        return json.loads(fixture_file.read_text())

# 3. Create pytest fixtures and conftest.py
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def mock_api_client(fixtures_dir):
    """Return configured mock API client."""
    return MockAPIClient(fixtures_dir)

@pytest.fixture
def test_db():
    """Return in-memory test database."""
    db = Database(":memory:")
    db.initialize_schema()
    return db
```

#### Test-Driven Development (TDD) Workflow

**ORDER: Test Infrastructure → Tests → Implementation**

```python
# STEP 1: Build test infrastructure (fixtures, mocks, conftest.py)
# (See above)

# STEP 2: Write tests FIRST (using the infrastructure)
def test_scrape_page_success(mock_api_client):
    """Test successful page scraping with revisions."""
    scraper = PageScraper(mock_api_client)
    result = scraper.scrape_page("Main_Page")
    
    assert result.page_id == 1
    assert result.title == "Main_Page"
    assert len(result.revisions) == 2
    assert mock_api_client.call_count == 1

def test_scrape_page_not_found(mock_api_client):
    """Test handling of non-existent page."""
    scraper = PageScraper(mock_api_client)
    
    with pytest.raises(PageNotFoundError):
        scraper.scrape_page("NonexistentPage")

def test_database_integrity(test_db):
    """Test that scraped data is stored correctly."""
    page = Page(page_id=1, namespace=0, title="Test_Page", is_redirect=False)
    test_db.insert_page(page)
    
    retrieved = test_db.get_page(1)
    
    assert retrieved.page_id == 1
    assert retrieved.title == "Test_Page"

# STEP 3: Implement code to make tests pass
# scraper/scrapers/page_scraper.py
class PageScraper:
    def __init__(self, api_client):
        self.api_client = api_client
    
    def scrape_page(self, title: str) -> Page:
        # Implementation that makes tests pass
        pass
```

#### Test Infrastructure Components

**Required before writing any tests:**

1. **Test Fixtures** (`fixtures/`)
   - Sample API responses (JSON files)
   - Test database files
   - Sample wiki content
   - Expected output data

2. **Mocks and Test Doubles** (`tests/mocks/`)
   - Mock API clients
   - Mock rate limiters
   - Mock database connections
   - Fake external services

3. **Pytest Configuration** (`tests/conftest.py`)
   - Reusable fixtures
   - Test database setup/teardown
   - Mock configuration
   - Shared test utilities

4. **Test Utilities** (`tests/utils/`)
   - Assertion helpers
   - Test data generators
   - Comparison functions
   - Validation utilities

**Test Coverage Requirements:**
- Unit tests for API client, database, scraper logic
- Integration tests with test fixtures
- Mock all external API calls
- Test error handling paths
- Validate database constraints
- Test incremental update logic
- 80%+ code coverage minimum

### 10. Technical Debt - ZERO TOLERANCE

- Do NOT create temporary workarounds
- Always implement the complete solution
- Remove deprecated code immediately
- Fix bugs properly, don't patch symptoms
- Refactor as you go
- No magic numbers or hardcoded values

### 11. Uncertainty Protocol

**If uncertain about proper behavior: ASK THE USER**

Do not guess, assume, or implement workarounds.

---

## Repository Structure

```
iRO-Wiki-Scraper/
├── README.md                    # User-facing project README
├── README-LLM.md               # This file - LLM implementation guide
├── requirements.txt            # Python dependencies
├── setup.py                    # Python package setup
├── pyproject.toml              # Python project config
├── .gitignore                  # Git ignore patterns
│
├── .github/
│   └── workflows/
│       ├── scrape-monthly.yml      # Monthly scheduled scraper
│       ├── scrape-manual.yml       # Manual trigger
│       └── test.yml                # Run tests on PR
│
├── scraper/                    # Python scraper (main tool)
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point (python -m scraper)
│   ├── cli.py                  # Click CLI interface
│   ├── config.py               # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py           # MediaWiki API wrapper
│   │   ├── rate_limiter.py     # Request throttling
│   │   └── exceptions.py       # API exceptions
│   │
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── page_scraper.py     # Page & revision fetching
│   │   ├── file_scraper.py     # Image/file downloading
│   │   ├── link_analyzer.py    # Internal link extraction
│   │   └── namespace_handler.py # Namespace-specific logic
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite/Postgres operations
│   │   ├── models.py           # Data models (dataclasses)
│   │   └── xml_exporter.py     # MediaWiki XML export
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Structured logging setup
│       ├── checkpoint.py       # Resume capability
│       └── stats.py            # Statistics tracking
│
├── sdk/                        # Go SDK for querying
│   ├── go.mod
│   ├── go.sum
│   ├── README.md
│   │
│   ├── irowiki/
│   │   ├── client.go           # Main client interface
│   │   ├── sqlite.go           # SQLite backend
│   │   ├── postgres.go         # PostgreSQL backend
│   │   ├── models.go           # Data structures
│   │   ├── search.go           # Search operations
│   │   ├── timeline.go         # Timeline queries
│   │   └── errors.go           # Error types
│   │
│   ├── cmd/
│   │   └── irowiki-cli/
│   │       └── main.go         # CLI tool for querying
│   │
│   ├── examples/
│   │   ├── basic_search.go
│   │   ├── timeline_query.go
│   │   └── revision_history.go
│   │
│   └── internal/               # Private Go implementation
│       ├── query/              # Query builders
│       └── parser/             # Response parsing
│
├── schema/
│   ├── sqlite.sql              # SQLite schema
│   ├── postgres.sql            # PostgreSQL schema
│   └── migrations/             # Schema migrations (if needed)
│       └── 001_initial.sql
│
├── docs/
│   ├── README.md               # Documentation index
│   ├── ARCHITECTURE.md         # System design overview
│   ├── API.md                  # SDK API documentation
│   ├── USAGE.md                # User guide
│   │
│   ├── design/                 # Design documents
│   │   ├── README.md           # Design folder guide
│   │   └── YYYY-MM-DD_NN_*.md  # Design docs (dated)
│   │
│   ├── worklog/                # Daily work logs
│   │   ├── README.md           # Worklog folder guide
│   │   └── YYYY-MM-DD_NN_*.md  # Work logs (dated)
│   │
│   └── user-stories/           # User stories by epic
│       ├── README.md           # User stories guide
│       ├── epic-01-scraper/
│       │   ├── README.md       # Epic overview
│       │   └── story-*.md      # Story files
│       ├── epic-02-database/
│       └── epic-03-sdk/
│
├── tests/                      # Python tests
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_api_client.py
│   ├── test_page_scraper.py
│   ├── test_file_scraper.py
│   ├── test_database.py
│   └── test_integration.py
│
├── fixtures/                   # Test data
│   ├── sample_page.json
│   ├── sample_revisions.json
│   └── test_wiki.db
│
├── scripts/
│   ├── package-release.sh      # Create tar.gz release
│   ├── verify-archive.py       # Integrity checks
│   └── db-stats.py             # Database statistics
│
└── config/
    ├── config.example.yaml     # Configuration template
    └── logging.yaml            # Logging configuration
```

---

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                GitHub Actions (Monthly)                  │
│  • Triggers scraper on schedule                         │
│  • Packages release (DB + files + XML)                  │
│  • Publishes to GitHub Releases                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Executes
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Python Scraper (scraper/)                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  API Client  │  │ Page Scraper │  │ File Scraper │ │
│  │              │  │              │  │              │ │
│  │ - Rate limit │  │ - Revisions  │  │ - Downloads  │ │
│  │ - Retry      │  │ - Links      │  │ - Checksums  │ │
│  │ - Backoff    │  │ - Metadata   │  │ - Storage    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │          │
│         └─────────────────┼─────────────────┘          │
│                           │                            │
│                           ▼                            │
│                  ┌──────────────┐                      │
│                  │   Database   │                      │
│                  │              │                      │
│                  │ - Pages      │                      │
│                  │ - Revisions  │                      │
│                  │ - Files      │                      │
│                  │ - Links      │                      │
│                  └──────┬───────┘                      │
└─────────────────────────┼──────────────────────────────┘
                          │
                          │ Stores
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Storage Layer                            │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐                │
│  │   SQLite DB    │  │  Files (10GB+) │                │
│  │                │  │                │                │
│  │ - Portable     │  │ - Original     │                │
│  │ - Fast queries │  │ - Checksums    │                │
│  │ - FTS5 search  │  │ - Organized    │                │
│  └────────────────┘  └────────────────┘                │
│                                                          │
│  ┌──────────────────────────────────┐                  │
│  │     MediaWiki XML Export         │                  │
│  │  (for re-hosting on MediaWiki)   │                  │
│  └──────────────────────────────────┘                  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ Packaged
                     ▼
┌─────────────────────────────────────────────────────────┐
│            Release Artifacts (.tar.gz)                   │
│                                                          │
│  • irowiki-YYYY-MM.db          (SQLite database)        │
│  • files/                      (All media)              │
│  • irowiki-export.xml          (MediaWiki XML)          │
│  • MANIFEST.json               (Metadata)               │
│  • checksums.sha256            (Integrity)              │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Queried by
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Go SDK (sdk/irowiki)                        │
│                                                          │
│  • Search pages by keyword, timeframe, author           │
│  • Get page content at specific timestamp               │
│  • Query revision history                               │
│  • Analyze edit patterns                                │
│  • Extract statistics                                   │
│                                                          │
│  Supports: SQLite (default) or PostgreSQL               │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
MediaWiki API → API Client → Rate Limiter → Scraper → Database
                                  ↓
                            Checkpoint (resume)
                                  ↓
                         Progress Logging (stats)
```

### Key Components

**1. API Client**
- Wraps MediaWiki API
- Handles pagination (continue tokens)
- Rate limiting (1 req/sec default)
- Retry logic with exponential backoff
- Error handling and logging

**2. Page Scraper**
- Fetches pages by namespace
- Retrieves complete revision history
- Extracts internal links
- Handles incremental updates
- Checkpoints progress

**3. File Scraper**
- Downloads all uploaded files
- Verifies checksums (SHA1)
- Organizes by namespace/letter
- Tracks download status
- Resumes interrupted downloads

**4. Database Layer**
- SQLite for portability
- PostgreSQL compatible schema
- Indexed for fast queries
- FTS5 full-text search
- Stores complete history

**5. XML Exporter**
- Generates MediaWiki XML format
- Compatible with importDump.php
- Enables re-hosting on MediaWiki
- Preserves all metadata

**6. Go SDK**
- Idiomatic Go API
- Dual backend (SQLite/Postgres)
- Rich query interface
- Timeline queries
- Statistics and analytics

---

## Technology Stack

### Python Scraper

```
Python 3.11+
├── requests          # HTTP client
├── pyyaml            # Config files
├── click             # CLI interface
├── tqdm              # Progress bars
├── structlog         # Structured logging
├── sqlalchemy        # Database ORM (optional)
└── pytest            # Testing
```

### Go SDK

```
Go 1.21+
├── database/sql      # Database interface
├── modernc.org/sqlite # Pure Go SQLite
├── github.com/lib/pq  # PostgreSQL driver
└── encoding/json     # JSON serialization
```

### Database

- **SQLite 3.35+** (primary, portable)
- **PostgreSQL 13+** (optional, for large deployments)

### Infrastructure

- **GitHub Actions** - Automated scraping & releases
- **GitHub Releases** - Artifact hosting (split archives if >2GB)
- **Optional**: External hosting for large files (archive.org, backblaze)

---

## Development Workflow

### 1. Before Starting Work

```bash
# Pull latest changes
git pull origin main

# Review design docs
cat docs/design/YYYY-MM-DD_*.md

# Check user stories
cat docs/user-stories/epic-*/README.md

# Review recent worklogs
tail -n 50 docs/worklog/YYYY-MM-DD_*.md

# Set up Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Run existing tests
pytest tests/ -v
```

### 2. Implement Feature (Test Infrastructure → Tests → Code)

**CRITICAL: Follow this exact order for every feature implementation.**

```bash
# STEP 1: Build test infrastructure FIRST
# Create fixtures for the feature
vim fixtures/sample_page_response.json
vim fixtures/sample_revisions.json

# Create mocks if needed
vim tests/mocks/mock_api_client.py

# Update conftest.py with new fixtures
vim tests/conftest.py

# Verify test infrastructure is working
pytest tests/test_conftest.py -v

# STEP 2: Write tests SECOND (using the infrastructure)
vim tests/test_page_scraper.py

# Run test (should fail - no implementation yet)
pytest tests/test_page_scraper.py::test_scrape_page_with_revisions -v

# STEP 3: Implement feature LAST (to make tests pass)
vim scraper/scrapers/page_scraper.py

# Run test (should pass now)
pytest tests/test_page_scraper.py::test_scrape_page_with_revisions -v

# Run all tests
pytest tests/ -v

# Check coverage
pytest tests/ --cov=scraper --cov-report=html
```

**Order Violations:**
- ❌ Writing implementation before tests
- ❌ Writing tests before test infrastructure
- ❌ Using unittest.mock.Mock without proper fixtures
- ✅ Infrastructure → Tests → Implementation (ALWAYS)

### 3. Before Committing

```bash
# Format code
black scraper/ tests/
isort scraper/ tests/

# Type checking
mypy scraper/

# Lint
pylint scraper/
flake8 scraper/

# Run all tests
pytest tests/ -v --cov=scraper

# Check for issues
bandit -r scraper/  # Security linting
```

### 4. Create Worklog and Commit

**IMPORTANT: Create a worklog entry after completing any major implementation work or at the end of an agent run, before moving to another story or epic.**

```bash
# Create worklog documenting what was done
vim docs/worklog/YYYY-MM-DD_NN_brief_description.md

# Add worklog to commit
git add docs/worklog/YYYY-MM-DD_NN_*.md

# Commit changes
git add .
git commit -m "feat: implement incremental page scraping"
git push origin feature/incremental-scrape
```

**Worklog Trigger Points:**
- ✅ After completing implementation of a user story
- ✅ At the end of any agent run (session complete)
- ✅ Before moving to a different story or epic
- ✅ After making significant architectural decisions
- ✅ When encountering blockers that halt progress
- ❌ Not needed for minor bug fixes or trivial changes

---

## Common Commands

### Python Scraper

```bash
# Install in development mode
pip install -e .

# Run scraper (full)
python -m scraper scrape --config config/config.yaml --full

# Run scraper (incremental)
python -m scraper scrape --config config/config.yaml --incremental

# Generate statistics
python -m scraper stats --database data/irowiki.db

# Export to MediaWiki XML
python -m scraper export --database data/irowiki.db --output exports/

# Package release
bash scripts/package-release.sh

# Verify archive integrity
python scripts/verify-archive.py releases/irowiki-2026-01.tar.gz
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_page_scraper.py::test_incremental_scrape -v

# Run with coverage
pytest tests/ --cov=scraper --cov-report=html

# Run integration tests only
pytest tests/test_integration.py -v

# Run with debugging
pytest tests/ -v -s  # Show print statements

# Run in parallel
pytest tests/ -n auto
```

### Database

```bash
# Create schema
sqlite3 data/irowiki.db < schema/sqlite.sql

# Query database
sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages;"

# Export database statistics
python scripts/db-stats.py data/irowiki.db

# Vacuum database (optimize)
sqlite3 data/irowiki.db "VACUUM;"

# Integrity check
sqlite3 data/irowiki.db "PRAGMA integrity_check;"
```

### Go SDK

```bash
# Build SDK
cd sdk
go build ./...

# Run tests
go test ./... -v

# Run CLI tool
go run cmd/irowiki-cli/main.go search "Poring"

# Install CLI globally
go install ./cmd/irowiki-cli

# Run examples
go run examples/basic_search.go
```

---

## Documentation Standards

### Document Organization

All documentation follows strict naming conventions:

**Design Documents** (`docs/design/`)
- Naming: `YYYY-MM-DD_NN_descriptive_name.md`
- NN is document number for that day (01, 02, 03...)
- Resets to 01 each day
- Contains: Architecture, specifications, decisions
- Created: Before implementing major features

**Worklog Entries** (`docs/worklog/`)
- Naming: `YYYY-MM-DD_NN_brief_description.md`
- NN is entry number for that day (01, 02, 03...)
- Resets to 01 each day
- Contains: Progress updates, decisions made, blockers encountered, next steps
- **MANDATORY**: Created at end of any agent run, after completing major implementation work, or before moving to another story/epic
- Not needed for minor bug fixes or trivial changes

**User Stories** (`docs/user-stories/`)
- Organized by epic: `epic-NN-name/`
- Story files: `story-NN_description.md`
- Each epic has README.md with overview
- Stories include acceptance criteria and status

### Python Docstrings

```python
def scrape_page_revisions(self, page_id: int, since: Optional[datetime] = None) -> List[Revision]:
    """
    Scrape all revisions for a given page.
    
    Fetches revision history from the MediaWiki API, handling pagination
    automatically. Optionally filters revisions to only those after a
    specific timestamp for incremental updates.
    
    Args:
        page_id: The numeric page ID
        since: Optional timestamp to fetch only recent revisions
        
    Returns:
        List of Revision objects, ordered newest to oldest
        
    Raises:
        PageNotFoundError: If page_id doesn't exist
        APIError: If the API request fails
        
    Example:
        >>> scraper = PageScraper(api_client)
        >>> revisions = scraper.scrape_page_revisions(
        ...     page_id=123,
        ...     since=datetime(2020, 1, 1)
        ... )
        >>> print(len(revisions))
        15
    """
    # Implementation
```

**Rules:**
- One-line summary
- Detailed description
- Document all parameters
- Document return value
- Document exceptions
- Include usage example

### Go Godoc

```go
// SearchOptions configures page search parameters.
type SearchOptions struct {
    // Query is the search term (supports wildcards)
    Query string
    
    // Namespace filters to specific namespace (0 = Main)
    Namespace int
    
    // StartDate filters revisions after this date (optional)
    StartDate *time.Time
    
    // EndDate filters revisions before this date (optional)
    EndDate *time.Time
    
    // Limit is the maximum results to return (default 100)
    Limit int
}

// Search performs a full-text search across all pages.
//
// The search supports wildcards (* and ?) and searches both page titles
// and content. Results are ranked by relevance using SQLite FTS5.
//
// Example:
//     results, err := client.Search(irowiki.SearchOptions{
//         Query: "ragnarok*",
//         Namespace: 0,
//         Limit: 10,
//     })
func (c *Client) Search(opts SearchOptions) ([]SearchResult, error) {
    // Implementation
}
```

---

## Release & Packaging

### Release Contents

```
irowiki-archive-2026-01.tar.gz
├── irowiki.db              # SQLite database (2-5 GB)
├── files/                  # All media files (5-20 GB)
│   ├── File/
│   │   ├── A/
│   │   ├── B/
│   │   └── ...
│   └── ...
├── irowiki-export.xml      # MediaWiki XML dump
├── MANIFEST.json           # Archive metadata
├── README.txt              # Usage instructions
└── checksums.sha256        # SHA256 checksums
```

### MANIFEST.json

```json
{
  "version": "2026.01",
  "scrape_date": "2026-01-01T00:00:00Z",
  "wiki_url": "https://irowiki.org",
  "statistics": {
    "total_pages": 2400,
    "total_revisions": 86500,
    "total_files": 4000,
    "database_size_mb": 3200,
    "files_size_mb": 12800
  },
  "schema_version": "1.0",
  "sqlite_version": "3.35.0",
  "includes_classic_wiki": true
}
```

### GitHub Actions Release

Monthly workflow:
1. Trigger on 1st of month at 2 AM UTC
2. Download previous database (for incremental)
3. Run scraper (incremental mode)
4. Generate statistics
5. Package release (tar.gz with checksums)
6. Create GitHub Release with artifacts
7. Upload database artifact for next month

### Release Naming

- Tag: `v2026.01` (year.month)
- Release: "iRO Wiki Archive - January 2026"
- File: `irowiki-archive-2026-01.tar.gz`

---

## Example Usage (Python)

```python
from scraper import WikiScraper
from scraper.config import Config

# Load configuration
config = Config.from_yaml("config/config.yaml")

# Initialize scraper
scraper = WikiScraper(config)

# Full scrape
scraper.scrape_full()

# Incremental scrape
scraper.scrape_incremental()

# Export to XML
scraper.export_mediawiki_xml("exports/irowiki-export.xml")

# Generate statistics
stats = scraper.get_statistics()
print(f"Pages: {stats.total_pages}")
print(f"Revisions: {stats.total_revisions}")
```

## Example Usage (Go SDK)

```go
package main

import (
    "fmt"
    "time"
    
    "github.com/user/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
    // Open archive
    client, err := irowiki.OpenSQLite("irowiki.db")
    if err != nil {
        panic(err)
    }
    defer client.Close()
    
    // Search pages
    results, _ := client.Search(irowiki.SearchOptions{
        Query: "Poring",
        Limit: 10,
    })
    
    for _, result := range results {
        fmt.Printf("%s (ID: %d)\n", result.Title, result.PageID)
    }
    
    // Get page history
    history, _ := client.GetPageHistory("Main_Page", irowiki.HistoryOptions{
        StartDate: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC),
        EndDate: time.Now(),
    })
    
    fmt.Printf("Revisions: %d\n", len(history))
    
    // Get page at specific time
    content, _ := client.GetPageAtTime("Main_Page",
        time.Date(2020, 6, 15, 0, 0, 0, 0, time.UTC))
    
    fmt.Println(content.Content)
}
```

---

## Success Criteria

### Phase 1: Foundation (Week 1)
- ✅ Git repository initialized
- ✅ Project structure created
- ✅ Database schema defined (SQLite + Postgres)
- ✅ API client with rate limiting
- ✅ Configuration system
- ✅ Basic tests passing

### Phase 2: Core Scraper (Week 2)
- ✅ Page discovery (all namespaces)
- ✅ Revision scraping (complete history)
- ✅ File downloading
- ✅ Link extraction
- ✅ Checkpoint/resume
- ✅ Progress tracking

### Phase 3: Incremental Updates (Week 3)
- ✅ Timestamp tracking
- ✅ Recent changes API integration
- ✅ Delta detection
- ✅ Optimized updates
- ✅ Integrity verification

### Phase 4: Export & Packaging (Week 3)
- ✅ MediaWiki XML export
- ✅ Release packaging script
- ✅ Integrity verification
- ✅ Compression optimization

### Phase 5: Go SDK (Week 4)
- ✅ SQLite backend
- ✅ PostgreSQL backend
- ✅ Search functionality
- ✅ Timeline queries
- ✅ CLI tool
- ✅ Documentation

### Phase 6: Automation (Week 5)
- ✅ GitHub Actions workflow
- ✅ Monthly scheduling
- ✅ Artifact management
- ✅ Release automation
- ✅ Notifications

---

## Questions & Decisions Log

### Classic Wiki Handling
**Decision:** Separate database file (`irowiki-classic.db`)
**Rationale:** Clean separation, independent versioning, easier to manage

### File Download Strategy
**Decision:** SHA1-based incremental downloads
**Rationale:** Efficient, detects file changes, avoids redundant downloads

### Full-Text Search
**Decision:** Include SQLite FTS5 in schema
**Rationale:** Enables fast search without external dependencies

### Release Artifact Size
**Decision:** Split archives if needed, provide both GitHub + external hosting
**Rationale:** GitHub has 2GB limit, external for full archives

### SDK Language
**Decision:** Go SDK as primary, Python bindings later if needed
**Rationale:** Fast, portable, great for CLI tools

---

**Remember:** Complete preservation is the goal. Every edit matters. Every file matters.
