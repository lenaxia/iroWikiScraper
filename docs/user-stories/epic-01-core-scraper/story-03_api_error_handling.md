# Story 03: API Error Handling

**Epic**: Epic 01 - Core Scraper Implementation  
**Story ID**: epic-01-story-03  
**Priority**: High  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **comprehensive error handling with clear error messages and retry strategies**,  
So that **the scraper can recover from transient failures and provide actionable error information**.

## Description

Enhance the API client with robust error handling that distinguishes between different failure types, provides clear error messages, implements appropriate retry strategies, and logs errors with sufficient context for debugging. This includes handling network errors, HTTP errors, API errors, and malformed responses.

## Background & Context

**Types of Errors:**
1. **Network errors**: Timeouts, connection refused, DNS failures
2. **HTTP errors**: 404, 429, 500, 503
3. **API errors**: MediaWiki API returns error response
4. **Parse errors**: Malformed JSON, unexpected response structure

**Error Handling Strategy:**
- **Retry**: Transient errors (timeout, 429, 500, 503)
- **Fail fast**: Permanent errors (404, invalid config)
- **Log and continue**: Warnings (API warnings, deprecated parameters)

**Why This Matters:**
- 24-48 hour scraping sessions will encounter errors
- Clear errors help debugging
- Proper retries prevent unnecessary failures
- Logged context helps identify patterns

## Acceptance Criteria

### 1. Exception Hierarchy Enhancement
- [ ] Extend exceptions in `scraper/api/exceptions.py`
- [ ] Add `NetworkError` for connection/timeout issues
- [ ] Add `HTTPError` as base for HTTP status errors
- [ ] Add `ServerError` for 5xx responses
- [ ] Add context fields: original_error, http_status, api_code, message
- [ ] All exceptions inherit from `APIError`

### 2. Error Context
- [ ] Exceptions store original exception as `cause`
- [ ] Exceptions store HTTP status code if applicable
- [ ] Exceptions store API error code if applicable
- [ ] Exceptions store request parameters for debugging
- [ ] `__str__()` method returns clear, actionable message

### 3. Retry Logic
- [ ] Retry on network timeouts (max_retries)
- [ ] Retry on 429 with exponential backoff
- [ ] Retry on 500, 502, 503 with exponential backoff
- [ ] Don't retry on 400, 401, 403, 404
- [ ] Don't retry on parse errors
- [ ] Log each retry attempt with reason

### 4. Error Logging
- [ ] Log all errors with full context
- [ ] DEBUG: Every request and response
- [ ] WARNING: Retry attempts
- [ ] ERROR: Failed requests after retries
- [ ] Include request URL, params, status code, error message

### 5. API Warning Handling
- [ ] Parse API warnings from response
- [ ] Log warnings at WARNING level
- [ ] Continue execution (don't raise exception)
- [ ] Collect warnings for later review

### 6. Testing
- [ ] Test infrastructure: Create error response fixtures
- [ ] Unit test: Network timeout raises NetworkError
- [ ] Unit test: Connection error raises NetworkError
- [ ] Unit test: HTTP 404 raises PageNotFoundError (no retry)
- [ ] Unit test: HTTP 429 retries with backoff
- [ ] Unit test: HTTP 500 retries
- [ ] Unit test: HTTP 503 retries
- [ ] Unit test: Malformed JSON raises APIResponseError
- [ ] Unit test: API error response raises APIError
- [ ] Unit test: API warnings logged but don't raise
- [ ] Unit test: Exception context includes original error
- [ ] Unit test: Max retries exceeded raises error

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `fixtures/api/http_errors/` directory
- [ ] Create fixtures for each HTTP error type
- [ ] Create `fixtures/api/network_errors.json` with scenarios
- [ ] Create `tests/mocks/mock_http_errors.py` for simulating errors
- [ ] Update `tests/conftest.py` with error fixtures

### Exception Classes
- [ ] Enhance `scraper/api/exceptions.py`
- [ ] Add new exception classes with context
- [ ] Implement `__str__()` for clear messages
- [ ] Add docstrings explaining when each is raised

### Error Handling Implementation
- [ ] Enhance `MediaWikiAPIClient._request()` error handling
- [ ] Add network error handling
- [ ] Add HTTP error handling with retry logic
- [ ] Add API error parsing
- [ ] Add warning extraction and logging
- [ ] Add error context to all exceptions

### Logging Enhancement
- [ ] Add structured logging with context
- [ ] Log request details at DEBUG
- [ ] Log retry attempts at WARNING
- [ ] Log final errors at ERROR
- [ ] Include timestamps, URLs, params

### Testing
- [ ] Write tests in `tests/test_api_error_handling.py`
- [ ] Test all error types
- [ ] Test retry behavior
- [ ] Verify error messages are clear
- [ ] Run tests: `pytest tests/test_api_error_handling.py -v`

## Technical Details

### Enhanced Exception Classes

```python
# scraper/api/exceptions.py
from typing import Optional, Any, Dict

class APIError(Exception):
    """
    Base exception for MediaWiki API errors.
    
    All API-related exceptions inherit from this class and provide
    context for debugging.
    """
    
    def __init__(
        self,
        message: str,
        cause: Optional[Exception] = None,
        http_status: Optional[int] = None,
        api_code: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize API error with context.
        
        Args:
            message: Human-readable error message
            cause: Original exception that caused this error
            http_status: HTTP status code if applicable
            api_code: MediaWiki API error code if applicable
            request_params: Request parameters for debugging
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.http_status = http_status
        self.api_code = api_code
        self.request_params = request_params or {}
    
    def __str__(self) -> str:
        """Return formatted error message with context."""
        parts = [self.message]
        
        if self.http_status:
            parts.append(f"HTTP {self.http_status}")
        
        if self.api_code:
            parts.append(f"API code: {self.api_code}")
        
        if self.cause:
            parts.append(f"Caused by: {str(self.cause)}")
        
        return " | ".join(parts)

class NetworkError(APIError):
    """Network-related errors (timeout, connection, DNS)."""
    pass

class HTTPError(APIError):
    """HTTP status code errors."""
    pass

class ServerError(HTTPError):
    """Server errors (5xx status codes)."""
    pass

class ClientError(HTTPError):
    """Client errors (4xx status codes)."""
    pass

class PageNotFoundError(ClientError):
    """Requested page not found (404)."""
    pass

class RateLimitError(ClientError):
    """API rate limit exceeded (429)."""
    pass

class APIResponseError(APIError):
    """API response parsing/validation failed."""
    pass
```

### Enhanced Error Handling in API Client

```python
# scraper/api/client.py (enhanced _request method)

def _request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make API request with comprehensive error handling.
    
    Handles network errors, HTTP errors, and API errors with
    appropriate retry logic and clear error messages.
    """
    # Wait for rate limit
    self.rate_limiter.wait()
    
    # Add required parameters
    full_params = {**params, 'action': action, 'format': 'json'}
    
    logger.debug(f"API request: {action}", extra={
        'action': action,
        'params': params,
        'endpoint': self.api_endpoint
    })
    
    for attempt in range(self.max_retries):
        try:
            response = self.session.get(
                self.api_endpoint,
                params=full_params,
                timeout=self.timeout
            )
            
            # Handle HTTP errors
            if response.status_code == 404:
                raise PageNotFoundError(
                    f"Page not found",
                    http_status=404,
                    request_params=full_params
                )
            
            elif response.status_code == 429:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Rate limit hit (429), attempt {attempt + 1}/{self.max_retries}",
                        extra={'attempt': attempt, 'max_retries': self.max_retries}
                    )
                    self.rate_limiter.backoff(attempt)
                    continue
                
                raise RateLimitError(
                    f"Rate limit exceeded after {self.max_retries} attempts",
                    http_status=429,
                    request_params=full_params
                )
            
            elif response.status_code >= 500:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Server error {response.status_code}, "
                        f"attempt {attempt + 1}/{self.max_retries}",
                        extra={
                            'status_code': response.status_code,
                            'attempt': attempt
                        }
                    )
                    self.rate_limiter.backoff(attempt)
                    continue
                
                raise ServerError(
                    f"Server error after {self.max_retries} attempts",
                    http_status=response.status_code,
                    request_params=full_params
                )
            
            elif response.status_code >= 400:
                raise ClientError(
                    f"Client error: {response.status_code}",
                    http_status=response.status_code,
                    request_params=full_params
                )
            
            # Parse and return successful response
            return self._parse_response(response)
        
        except requests.Timeout as e:
            if attempt < self.max_retries - 1:
                logger.warning(
                    f"Request timeout, attempt {attempt + 1}/{self.max_retries}",
                    extra={'timeout': self.timeout, 'attempt': attempt}
                )
                self.rate_limiter.backoff(attempt)
                continue
            
            raise NetworkError(
                f"Request timeout after {self.max_retries} attempts",
                cause=e,
                request_params=full_params
            )
        
        except requests.ConnectionError as e:
            raise NetworkError(
                f"Connection error: {str(e)}",
                cause=e,
                request_params=full_params
            )
        
        except requests.RequestException as e:
            raise NetworkError(
                f"Network error: {str(e)}",
                cause=e,
                request_params=full_params
            )
    
    # Should never reach here due to explicit raises above
    raise NetworkError(
        f"Max retries ({self.max_retries}) exceeded",
        request_params=full_params
    )

def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
    """Parse and validate API response with error handling."""
    try:
        data = response.json()
    except ValueError as e:
        logger.error(
            "Invalid JSON response",
            extra={'response_text': response.text[:200]}
        )
        raise APIResponseError(
            "Invalid JSON in API response",
            cause=e,
            http_status=response.status_code
        )
    
    # Check for API errors
    if 'error' in data:
        error_info = data['error']
        api_code = error_info.get('code', 'unknown')
        api_message = error_info.get('info', 'Unknown error')
        
        logger.error(
            f"API error: {api_code}",
            extra={'api_code': api_code, 'api_message': api_message}
        )
        
        raise APIError(
            f"API error: {api_message}",
            api_code=api_code,
            http_status=response.status_code
        )
    
    # Log warnings but don't raise
    if 'warnings' in data:
        for warning_type, warning_data in data['warnings'].items():
            logger.warning(
                f"API warning: {warning_type}",
                extra={'warning_type': warning_type, 'warning_data': warning_data}
            )
    
    logger.debug("API request successful", extra={'response_keys': list(data.keys())})
    
    return data
```

### Test Examples

```python
# tests/test_api_error_handling.py
import pytest
import requests
from scraper.api.client import MediaWikiAPIClient
from scraper.api.exceptions import (
    NetworkError, PageNotFoundError, RateLimitError,
    ServerError, APIError, APIResponseError
)

def test_timeout_raises_network_error(api_client, mock_session):
    """Timeout should raise NetworkError with context."""
    mock_session.set_behavior('timeout')
    
    with pytest.raises(NetworkError) as exc_info:
        api_client.get_page("Test")
    
    error = exc_info.value
    assert "timeout" in str(error).lower()
    assert isinstance(error.cause, requests.Timeout)
    assert error.request_params is not None

def test_404_raises_page_not_found(api_client, mock_session):
    """404 should raise PageNotFoundError without retry."""
    mock_session.set_status_code(404)
    
    with pytest.raises(PageNotFoundError) as exc_info:
        api_client.get_page("NonexistentPage")
    
    error = exc_info.value
    assert error.http_status == 404
    assert mock_session.get_call_count == 1  # No retries

def test_429_retries_with_backoff(api_client, mock_session):
    """429 should retry with exponential backoff."""
    # Fail twice with 429, then succeed
    mock_session.set_status_codes([429, 429, 200])
    
    result = api_client.get_page("Test")
    
    assert result is not None
    assert mock_session.get_call_count == 3

def test_500_retries(api_client, mock_session):
    """500 should retry up to max_retries."""
    mock_session.set_status_code(500)
    
    with pytest.raises(ServerError) as exc_info:
        api_client.get_page("Test")
    
    error = exc_info.value
    assert error.http_status == 500
    assert mock_session.get_call_count == 3  # max_retries

def test_malformed_json_raises_response_error(api_client, mock_session):
    """Malformed JSON should raise APIResponseError."""
    mock_session.set_response_text("Not valid JSON {{{")
    
    with pytest.raises(APIResponseError) as exc_info:
        api_client.get_page("Test")
    
    error = exc_info.value
    assert "Invalid JSON" in str(error)

def test_api_error_response(api_client, mock_session, fixtures_dir):
    """API error response should raise APIError with code."""
    error_fixture = fixtures_dir / "api" / "error_response.json"
    mock_session.set_fixture(error_fixture)
    
    with pytest.raises(APIError) as exc_info:
        api_client.get_page("Test")
    
    error = exc_info.value
    assert error.api_code is not None
    assert error.message

def test_api_warnings_logged_not_raised(api_client, mock_session, caplog):
    """API warnings should be logged but not raise exception."""
    mock_session.set_warning("deprecation", "Parameter X is deprecated")
    
    result = api_client.get_page("Test")
    
    assert result is not None
    assert "API warning" in caplog.text
    assert "deprecation" in caplog.text
```

## Dependencies

### Requires
- Story 01: MediaWiki API Client
- Story 02: Rate Limiter (for backoff)

### Blocks
- All scraping stories (depend on error handling)

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Code coverage ≥80%
- [ ] All error types tested
- [ ] Retry logic verified
- [ ] Error messages are clear
- [ ] Logging includes context
- [ ] Type hints on all methods
- [ ] Docstrings complete
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Test error paths thoroughly**: More edge cases than happy path
2. **Don't catch Exception**: Be specific with exception types
3. **Always chain exceptions**: Use `from e` to preserve context
4. **Log before raising**: Helps debugging production issues
5. **Test with real API**: Some errors only appear in production

### Common Pitfalls

- Catching too broad exceptions (Exception, BaseException)
- Not preserving original exception context
- Retrying non-transient errors
- Poor error messages without context
- Not testing all error paths

### Testing Tips

- Mock different HTTP status codes
- Simulate network failures
- Test retry counts with counters
- Verify backoff timing with mock time
- Use caplog fixture to test logging

## References

- Requests exceptions: https://requests.readthedocs.io/en/latest/user/quickstart/#errors-and-exceptions
- Python exception chaining: https://peps.python.org/pep-3134/
- HTTP status codes: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
