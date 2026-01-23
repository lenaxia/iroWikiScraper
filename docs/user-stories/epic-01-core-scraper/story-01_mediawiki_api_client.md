# Story 01: MediaWiki API Client

**Epic**: Epic 01 - Core Scraper Implementation  
**Story ID**: epic-01-story-01  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 3-4 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **a robust MediaWiki API client**,  
So that **I can reliably fetch data from irowiki.org with proper error handling and configuration**.

## Description

Implement a Python client class that wraps the MediaWiki API for irowiki.org. This client will be the foundation for all data fetching operations in the scraper. It must handle HTTP requests, parse JSON responses, manage sessions, validate API responses, and provide clear error messages.

The client should be reusable across different API endpoints (pages, revisions, files) and support both the main wiki and classic wiki with minimal configuration changes.

## Background & Context

**What is the MediaWiki API?**
- RESTful API for querying wiki content
- Returns JSON or XML responses
- Requires specific parameters for each action
- Supports pagination via "continue" tokens
- Documentation: https://www.mediawiki.org/wiki/API:Main_page

**iRO Wiki Details:**
- Main API: https://irowiki.org/w/api.php
- Classic API: https://irowiki.org/classic/w/api.php (separate instance)
- MediaWiki version: 1.44.0
- No authentication required for read operations
- Rate limiting recommended: 1 request/second

**Why This Story Matters:**
- All scraping operations depend on this client
- Error handling here prevents cascading failures
- Proper session management improves performance
- Configuration support enables multi-wiki archival

## Acceptance Criteria

### 1. API Client Class Implementation
- [ ] Create `scraper/api/client.py` with `MediaWikiAPIClient` class
- [ ] Client initialized with base URL and optional config
- [ ] Uses `requests.Session` for connection pooling
- [ ] Sets User-Agent header identifying the scraper
- [ ] Supports custom timeout configuration (default 30s)

### 2. Core Request Method
- [ ] Implement `_request(action, params)` method
- [ ] Automatically adds `action`, `format=json` to params
- [ ] Handles HTTP errors (404, 429, 500, 503, timeout)
- [ ] Retries on transient failures (429, 500, 503) with exponential backoff
- [ ] Raises custom exceptions for different error types
- [ ] Logs all requests at DEBUG level

### 3. Response Parsing
- [ ] Validates response is valid JSON
- [ ] Checks for API error responses (response['error'])
- [ ] Checks for API warnings (response['warnings'])
- [ ] Returns parsed JSON data
- [ ] Raises `APIError` with clear message on errors

### 4. High-Level API Methods
- [ ] Implement `get_page(title, namespace=0)` - fetch single page
- [ ] Implement `get_pages(titles, namespace=0)` - fetch multiple pages
- [ ] Implement `query(params)` - generic query method
- [ ] All methods return parsed data, not raw responses

### 5. Configuration Support
- [ ] Accept config dict or Config object in constructor
- [ ] Support configuring: base_url, timeout, user_agent, verify_ssl
- [ ] Use sensible defaults for all config values
- [ ] Validate config parameters on initialization

### 6. Error Handling
- [ ] Create custom exception hierarchy in `scraper/api/exceptions.py`:
  - `APIError` (base)
  - `APIRequestError` (HTTP errors)
  - `APIResponseError` (malformed responses)
  - `PageNotFoundError` (404)
  - `RateLimitError` (429)
- [ ] All exceptions include original error context
- [ ] Error messages are clear and actionable

### 7. Testing
- [ ] Test infrastructure: Create `fixtures/api/` with sample responses
- [ ] Test infrastructure: Create `tests/mocks/mock_http_session.py`
- [ ] Test infrastructure: Create `tests/conftest.py` with API fixtures
- [ ] Unit test: Successful API request returns parsed data
- [ ] Unit test: HTTP 404 raises PageNotFoundError
- [ ] Unit test: HTTP 429 triggers retry with backoff
- [ ] Unit test: HTTP 500 retries up to max attempts
- [ ] Unit test: Timeout raises APIRequestError
- [ ] Unit test: Malformed JSON raises APIResponseError
- [ ] Unit test: API error response raises APIError
- [ ] Unit test: User-Agent header is set correctly
- [ ] Unit test: Session is reused across requests
- [ ] Integration test: Fetch real page from irowiki.org (live test, can be skipped)

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `fixtures/api/` directory
- [ ] Create `fixtures/api/successful_page_response.json`
- [ ] Create `fixtures/api/error_response.json`
- [ ] Create `fixtures/api/malformed_response.txt`
- [ ] Create `tests/mocks/mock_http_session.py` with MockSession class
- [ ] Create `tests/conftest.py` with API client fixtures
- [ ] Verify test infrastructure loads correctly

### Exception Classes
- [ ] Create `scraper/api/__init__.py`
- [ ] Create `scraper/api/exceptions.py`
- [ ] Define exception hierarchy with docstrings
- [ ] Add `__all__` exports

### API Client Implementation
- [ ] Create `scraper/api/client.py`
- [ ] Implement `MediaWikiAPIClient.__init__()`
- [ ] Implement `MediaWikiAPIClient._request()` with retry logic
- [ ] Implement `MediaWikiAPIClient._parse_response()`
- [ ] Implement `MediaWikiAPIClient.get_page()`
- [ ] Implement `MediaWikiAPIClient.get_pages()`
- [ ] Implement `MediaWikiAPIClient.query()`
- [ ] Add comprehensive docstrings to all methods

### Testing (After Implementation)
- [ ] Write tests in `tests/test_api_client.py`
- [ ] Run tests: `pytest tests/test_api_client.py -v`
- [ ] Verify 80%+ code coverage
- [ ] Fix any failing tests

### Documentation
- [ ] Add module docstring to `client.py`
- [ ] Add usage examples in docstrings
- [ ] Document all parameters and return types
- [ ] Add type hints to all methods

## Technical Details

### File Structure
```
scraper/
├── api/
│   ├── __init__.py
│   ├── client.py          # MediaWikiAPIClient class
│   └── exceptions.py      # Custom exceptions

tests/
├── conftest.py            # Pytest fixtures
├── mocks/
│   └── mock_http_session.py
└── test_api_client.py     # API client tests

fixtures/
└── api/
    ├── successful_page_response.json
    ├── error_response.json
    └── malformed_response.txt
```

### API Client Implementation Skeleton

```python
# scraper/api/client.py
import requests
import logging
import time
from typing import Dict, List, Optional, Any
from .exceptions import (
    APIError, APIRequestError, APIResponseError,
    PageNotFoundError, RateLimitError
)

logger = logging.getLogger(__name__)

class MediaWikiAPIClient:
    """Client for interacting with MediaWiki API."""
    
    def __init__(
        self,
        base_url: str,
        user_agent: str = "iROWikiArchiver/1.0",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """
        Initialize MediaWiki API client.
        
        Args:
            base_url: Base URL of the wiki (e.g., "https://irowiki.org")
            user_agent: User-Agent header for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.base_url = base_url.rstrip('/')
        self.api_endpoint = f"{self.base_url}/w/api.php"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
    
    def _request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with retry logic.
        
        Args:
            action: MediaWiki API action (e.g., "query")
            params: Additional parameters for the request
            
        Returns:
            Parsed JSON response
            
        Raises:
            APIRequestError: HTTP request failed
            APIResponseError: Response parsing failed
            RateLimitError: Rate limit exceeded
            PageNotFoundError: Page not found
        """
        # Add required parameters
        params['action'] = action
        params['format'] = 'json'
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"API request: {action} {params}")
                response = self.session.get(
                    self.api_endpoint,
                    params=params,
                    timeout=self.timeout
                )
                
                # Handle HTTP errors
                if response.status_code == 404:
                    raise PageNotFoundError(f"Page not found: {params}")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Server error {response.status_code}, retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    raise APIRequestError(f"Server error: {response.status_code}")
                
                response.raise_for_status()
                return self._parse_response(response)
                
            except requests.Timeout as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Request timeout, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                raise APIRequestError(f"Request timeout after {self.max_retries} attempts") from e
            
            except requests.RequestException as e:
                raise APIRequestError(f"Request failed: {e}") from e
        
        raise APIRequestError(f"Max retries ({self.max_retries}) exceeded")
    
    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse and validate API response."""
        try:
            data = response.json()
        except ValueError as e:
            raise APIResponseError("Invalid JSON response") from e
        
        # Check for API errors
        if 'error' in data:
            raise APIError(f"API error: {data['error'].get('info', 'Unknown error')}")
        
        # Log warnings
        if 'warnings' in data:
            logger.warning(f"API warnings: {data['warnings']}")
        
        return data
    
    def get_page(self, title: str, namespace: int = 0) -> Dict[str, Any]:
        """
        Fetch a single page by title.
        
        Args:
            title: Page title
            namespace: Namespace ID (default 0 = Main)
            
        Returns:
            Page data dictionary
        """
        params = {
            'titles': title,
            'prop': 'info',
            'inprop': 'url'
        }
        
        if namespace != 0:
            params['titles'] = f"{namespace}:{title}"
        
        return self._request('query', params)
    
    def query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic query method.
        
        Args:
            params: Query parameters
            
        Returns:
            Query results
        """
        return self._request('query', params)
```

### Exception Classes

```python
# scraper/api/exceptions.py

class APIError(Exception):
    """Base exception for MediaWiki API errors."""
    pass

class APIRequestError(APIError):
    """HTTP request failed."""
    pass

class APIResponseError(APIError):
    """API response parsing failed."""
    pass

class PageNotFoundError(APIError):
    """Requested page not found."""
    pass

class RateLimitError(APIError):
    """API rate limit exceeded."""
    pass
```

### Test Fixtures

```json
// fixtures/api/successful_page_response.json
{
    "batchcomplete": "",
    "query": {
        "pages": {
            "1": {
                "pageid": 1,
                "ns": 0,
                "title": "Main_Page",
                "contentmodel": "wikitext",
                "pagelanguage": "en"
            }
        }
    }
}
```

```json
// fixtures/api/error_response.json
{
    "error": {
        "code": "missingtitle",
        "info": "The page you specified doesn't exist.",
        "*": "See https://irowiki.org/w/api.php for API usage."
    }
}
```

### Mock HTTP Session

```python
# tests/mocks/mock_http_session.py
from pathlib import Path
import json

class MockResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
    
    def json(self):
        if self._json_data is None:
            raise ValueError("Invalid JSON")
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

class MockSession:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir
        self.headers = {}
        self.get_call_count = 0
    
    def update(self, headers):
        self.headers.update(headers)
    
    def get(self, url, params=None, timeout=None):
        self.get_call_count += 1
        
        # Load appropriate fixture based on request
        if params and params.get('titles') == 'NonexistentPage':
            return MockResponse(404)
        
        fixture_file = self.fixtures_dir / "api" / "successful_page_response.json"
        with open(fixture_file) as f:
            data = json.load(f)
        
        return MockResponse(200, json_data=data)
```

### Pytest Fixtures

```python
# tests/conftest.py
import pytest
from pathlib import Path
from tests.mocks.mock_http_session import MockSession

@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def mock_session(fixtures_dir):
    """Return mock HTTP session."""
    return MockSession(fixtures_dir)

@pytest.fixture
def api_client(mock_session, monkeypatch):
    """Return API client with mocked session."""
    from scraper.api.client import MediaWikiAPIClient
    
    client = MediaWikiAPIClient("https://irowiki.org")
    monkeypatch.setattr(client, 'session', mock_session)
    
    return client
```

## Dependencies

### Requires
- Python 3.11+
- `requests` library
- `pytest` for testing

### Blocks
- Story 02: Rate Limiter (uses this client)
- Story 04: Page Discovery (uses this client)
- All other scraping stories

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] All tests passing (pytest tests/test_api_client.py -v)
- [ ] Code coverage ≥80% on client.py
- [ ] Type hints on all methods
- [ ] Docstrings on all public methods
- [ ] No pylint warnings
- [ ] Code formatted with black
- [ ] Imports sorted with isort
- [ ] Manual test: Successfully fetch page from live irowiki.org
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Start with test infrastructure**: Create fixtures and mocks BEFORE writing any client code
2. **Read MediaWiki API docs**: Understand the API response format
3. **Test incrementally**: Write one test, implement feature, repeat
4. **Handle errors properly**: Don't swallow exceptions
5. **Log everything**: Use DEBUG level for requests, WARNING for retries

### Common Pitfalls

- **Forgetting to set User-Agent**: Some wikis block requests without proper UA
- **Not handling continue tokens**: We'll add pagination in Story 06
- **Retrying non-transient errors**: Only retry 429, 500, 503, timeouts
- **Not validating JSON**: Always check response is valid before parsing

### Testing Tips

- Use `monkeypatch` to replace `requests.Session` with mock
- Test both happy path and error cases
- Verify retry logic with counter in mock
- Test with real API as integration test (mark with `@pytest.mark.integration`)

## References

- MediaWiki API: https://www.mediawiki.org/wiki/API:Main_page
- iRO Wiki API: https://irowiki.org/w/api.php
- requests library: https://requests.readthedocs.io/
- pytest documentation: https://docs.pytest.org/
