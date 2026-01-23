# Story 02: Rate Limiter with Backoff

**Epic**: Epic 01 - Core Scraper Implementation  
**Story ID**: epic-01-story-02  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Assignee**: TBD

## User Story

As a **scraper developer**,  
I want **a rate limiter that controls request frequency with exponential backoff**,  
So that **I respect the wiki's resources and avoid getting blocked or rate-limited**.

## Description

Implement a rate limiter that ensures API requests are spaced appropriately (default 1 request/second) with support for exponential backoff when rate limit errors occur. The rate limiter should be configurable, thread-safe, and integrate seamlessly with the API client.

This is critical for being a "good citizen" when archiving - we want to preserve the wiki without impacting its availability for users.

## Background & Context

**Why Rate Limiting Matters:**
- Prevents overwhelming the wiki server
- Avoids getting IP banned
- Respects HTTP 429 (Too Many Requests) responses
- Industry best practice for web scraping
- Required for 24-48 hour scraping sessions

**Rate Limiting Strategies:**
- **Fixed delay**: Simple wait between requests
- **Token bucket**: Allows bursts but maintains average rate
- **Exponential backoff**: Increasing delays after failures

**iRO Wiki Specifics:**
- No published rate limit (be conservative)
- Recommended: 1 request/second
- Should respect 429 responses with Retry-After header

## Acceptance Criteria

### 1. Rate Limiter Class
- [ ] Create `scraper/api/rate_limiter.py` with `RateLimiter` class
- [ ] Initialize with requests_per_second parameter (default 1.0)
- [ ] Track time of last request
- [ ] Thread-safe implementation (use threading.Lock)

### 2. Wait Method
- [ ] Implement `wait()` method that blocks until rate limit allows
- [ ] Calculate time elapsed since last request
- [ ] Sleep for remaining time if under rate limit
- [ ] Update last request timestamp
- [ ] Log delays at DEBUG level

### 3. Backoff Method
- [ ] Implement `backoff(attempt)` method for exponential backoff
- [ ] Base delay: configurable (default 5 seconds)
- [ ] Exponential formula: base_delay * (2 ** attempt)
- [ ] Maximum backoff: configurable (default 300s = 5 min)
- [ ] Log backoff delays at WARNING level

### 4. Integration with API Client
- [ ] Modify `MediaWikiAPIClient` to accept rate_limiter parameter
- [ ] Call `rate_limiter.wait()` before each request
- [ ] Call `rate_limiter.backoff(attempt)` on 429 errors
- [ ] Make rate limiter optional (for testing)

### 5. Configuration
- [ ] Support config via constructor parameters
- [ ] Support config via Config object
- [ ] Validate config values (rates must be positive)
- [ ] Allow disabling rate limiter (for testing)

### 6. Testing
- [ ] Test infrastructure: Create mock time module
- [ ] Test infrastructure: Create fixtures for rate limiter tests
- [ ] Unit test: First request passes immediately
- [ ] Unit test: Second request waits appropriate time
- [ ] Unit test: Multiple rapid requests wait correctly
- [ ] Unit test: Backoff increases exponentially
- [ ] Unit test: Maximum backoff respected
- [ ] Unit test: Thread safety (multiple threads)
- [ ] Unit test: Integration with API client
- [ ] Unit test: Disabled rate limiter doesn't wait

## Tasks

### Test Infrastructure (Do FIRST)
- [ ] Create `tests/mocks/mock_time.py` with controllable time
- [ ] Create `tests/conftest.py` fixtures for rate limiter
- [ ] Verify mock time module works correctly

### Rate Limiter Implementation
- [ ] Create `scraper/api/rate_limiter.py`
- [ ] Implement `RateLimiter.__init__()`
- [ ] Implement `RateLimiter.wait()`
- [ ] Implement `RateLimiter.backoff()`
- [ ] Add thread safety with Lock
- [ ] Add comprehensive docstrings

### API Client Integration
- [ ] Modify `MediaWikiAPIClient.__init__()` to accept rate_limiter
- [ ] Add `rate_limiter.wait()` call in `_request()`
- [ ] Add `rate_limiter.backoff()` call on 429 errors
- [ ] Update tests to work with rate limiter

### Testing
- [ ] Write tests in `tests/test_rate_limiter.py`
- [ ] Run tests: `pytest tests/test_rate_limiter.py -v`
- [ ] Verify 80%+ code coverage
- [ ] Fix any failing tests

### Documentation
- [ ] Add module docstring
- [ ] Add usage examples in docstrings
- [ ] Document thread safety guarantees
- [ ] Add type hints

## Technical Details

### Rate Limiter Implementation

```python
# scraper/api/rate_limiter.py
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiter with exponential backoff support.
    
    Ensures requests are spaced according to configured rate limit
    and provides exponential backoff for handling rate limit errors.
    
    Thread-safe: Multiple threads can share a rate limiter instance.
    """
    
    def __init__(
        self,
        requests_per_second: float = 1.0,
        base_backoff_delay: float = 5.0,
        max_backoff_delay: float = 300.0,
        enabled: bool = True
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_second: Maximum requests per second (default 1.0)
            base_backoff_delay: Base delay for exponential backoff (seconds)
            max_backoff_delay: Maximum backoff delay (seconds)
            enabled: Enable rate limiting (disable for testing)
        
        Raises:
            ValueError: If requests_per_second is not positive
        """
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        
        self.min_interval = 1.0 / requests_per_second
        self.base_backoff_delay = base_backoff_delay
        self.max_backoff_delay = max_backoff_delay
        self.enabled = enabled
        
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        
        logger.info(
            f"Rate limiter initialized: {requests_per_second} req/s "
            f"(min interval: {self.min_interval:.2f}s)"
        )
    
    def wait(self) -> None:
        """
        Wait until rate limit allows next request.
        
        Blocks the current thread if insufficient time has passed since
        the last request. Thread-safe.
        """
        if not self.enabled:
            return
        
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            
            self._last_request_time = time.time()
    
    def backoff(self, attempt: int) -> None:
        """
        Perform exponential backoff delay.
        
        Used when encountering rate limit errors (HTTP 429) or server
        errors (HTTP 5xx). Delay doubles with each attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Example:
            attempt=0 -> 5s
            attempt=1 -> 10s
            attempt=2 -> 20s
            attempt=3 -> 40s
        """
        if not self.enabled:
            return
        
        # Calculate exponential backoff
        delay = self.base_backoff_delay * (2 ** attempt)
        
        # Cap at maximum
        delay = min(delay, self.max_backoff_delay)
        
        logger.warning(
            f"Backoff attempt {attempt}: waiting {delay:.1f}s "
            f"(max: {self.max_backoff_delay:.1f}s)"
        )
        
        time.sleep(delay)
        
        # Update last request time to prevent immediate retry
        with self._lock:
            self._last_request_time = time.time()
```

### Integration with API Client

```python
# scraper/api/client.py (modified)

class MediaWikiAPIClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str = "iROWikiArchiver/1.0",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        rate_limiter: Optional['RateLimiter'] = None
    ):
        # ... existing code ...
        
        # Use provided rate limiter or create default
        if rate_limiter is None:
            from .rate_limiter import RateLimiter
            rate_limiter = RateLimiter(requests_per_second=1.0)
        
        self.rate_limiter = rate_limiter
    
    def _request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Wait for rate limit before making request
        self.rate_limiter.wait()
        
        for attempt in range(self.max_retries):
            try:
                # ... existing request code ...
                
            except RateLimitError as e:
                # Use exponential backoff for rate limit errors
                if attempt < self.max_retries - 1:
                    self.rate_limiter.backoff(attempt)
                    continue
                raise
```

### Mock Time Module for Testing

```python
# tests/mocks/mock_time.py

class MockTime:
    """Controllable time for testing rate limiter."""
    
    def __init__(self):
        self.current_time = 0.0
    
    def time(self):
        """Return current mock time."""
        return self.current_time
    
    def sleep(self, seconds):
        """Advance mock time by seconds."""
        self.current_time += seconds
    
    def advance(self, seconds):
        """Advance time without sleeping."""
        self.current_time += seconds
```

### Test Examples

```python
# tests/test_rate_limiter.py
import pytest
from scraper.api.rate_limiter import RateLimiter
from tests.mocks.mock_time import MockTime

def test_first_request_no_delay(monkeypatch):
    """First request should pass immediately."""
    mock_time = MockTime()
    monkeypatch.setattr('time.time', mock_time.time)
    monkeypatch.setattr('time.sleep', mock_time.sleep)
    
    limiter = RateLimiter(requests_per_second=1.0)
    
    start_time = mock_time.current_time
    limiter.wait()
    end_time = mock_time.current_time
    
    assert end_time == start_time  # No delay

def test_second_request_waits(monkeypatch):
    """Second request should wait for rate limit."""
    mock_time = MockTime()
    monkeypatch.setattr('time.time', mock_time.time)
    monkeypatch.setattr('time.sleep', mock_time.sleep)
    
    limiter = RateLimiter(requests_per_second=1.0)  # 1 req/s = 1s interval
    
    # First request
    limiter.wait()
    
    # Advance time by 0.5s (less than 1s interval)
    mock_time.advance(0.5)
    
    # Second request should wait additional 0.5s
    start_time = mock_time.current_time
    limiter.wait()
    end_time = mock_time.current_time
    
    assert end_time - start_time == pytest.approx(0.5, abs=0.01)

def test_backoff_exponential(monkeypatch):
    """Backoff should increase exponentially."""
    mock_time = MockTime()
    monkeypatch.setattr('time.sleep', mock_time.sleep)
    
    limiter = RateLimiter(base_backoff_delay=5.0)
    
    # Attempt 0: 5s
    limiter.backoff(0)
    assert mock_time.current_time == 5.0
    
    # Attempt 1: 10s
    mock_time.current_time = 0
    limiter.backoff(1)
    assert mock_time.current_time == 10.0
    
    # Attempt 2: 20s
    mock_time.current_time = 0
    limiter.backoff(2)
    assert mock_time.current_time == 20.0

def test_backoff_max_delay(monkeypatch):
    """Backoff should respect maximum delay."""
    mock_time = MockTime()
    monkeypatch.setattr('time.sleep', mock_time.sleep)
    
    limiter = RateLimiter(base_backoff_delay=5.0, max_backoff_delay=30.0)
    
    # Attempt 5: would be 160s but capped at 30s
    limiter.backoff(5)
    assert mock_time.current_time == 30.0

def test_disabled_rate_limiter():
    """Disabled rate limiter should not wait."""
    limiter = RateLimiter(enabled=False)
    
    # Should return immediately
    start = time.time()
    limiter.wait()
    limiter.wait()
    limiter.wait()
    end = time.time()
    
    assert end - start < 0.1  # No significant delay
```

## Dependencies

### Requires
- Story 01: MediaWiki API Client (integrates with this)

### Blocks
- Story 04: Page Discovery (uses rate-limited client)
- All scraping operations

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Code coverage ≥80%
- [ ] Thread safety verified
- [ ] Type hints on all methods
- [ ] Docstrings on all public methods
- [ ] Code formatted with black
- [ ] No pylint warnings
- [ ] Integration test with API client works
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Use mock time**: Real time.sleep() makes tests slow
2. **Test thread safety**: Use threading in tests to verify Lock works
3. **Log everything**: Debug rate limit waits, warning backoffs
4. **Make it configurable**: Different wikis need different rates

### Common Pitfalls

- **Not using Lock**: Race conditions in multi-threaded scraping
- **Forgetting to update last_request_time**: Rate limit won't work
- **Not handling disabled mode**: Tests need to disable rate limiting
- **Wrong backoff formula**: Should be 2^attempt, not 2*attempt

### Testing Tips

- Mock time module is essential for fast tests
- Test both enabled and disabled modes
- Verify backoff respects max delay
- Test integration with real API client

## References

- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket
- Exponential Backoff: https://en.wikipedia.org/wiki/Exponential_backoff
- Python threading.Lock: https://docs.python.org/3/library/threading.html#lock-objects
