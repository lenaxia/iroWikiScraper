"""Rate limiter with exponential backoff for API requests.

This module provides rate limiting functionality to ensure API requests
are properly spaced and handles rate limit errors with exponential backoff.
"""

import time
import threading
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff support.

    Ensures requests are spaced according to configured rate limit
    and provides exponential backoff for handling rate limit errors.

    Thread-safe: Multiple threads can share a rate limiter instance.

    Example:
        >>> limiter = RateLimiter(requests_per_second=2.0)
        >>> limiter.wait()  # Waits if necessary to respect rate limit
        >>> # ... make API request ...
        >>> limiter.backoff(0)  # Exponential backoff on error

    Attributes:
        min_interval: Minimum time between requests (seconds)
        base_backoff_delay: Base delay for exponential backoff (seconds)
        max_backoff_delay: Maximum backoff delay (seconds)
        enabled: Whether rate limiting is enabled
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        base_backoff_delay: float = 5.0,
        max_backoff_delay: float = 300.0,
        enabled: bool = True,
        time_module: Optional[Any] = None,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second (default 1.0)
            base_backoff_delay: Base delay for exponential backoff (seconds)
            max_backoff_delay: Maximum backoff delay (seconds)
            enabled: Enable rate limiting (disable for testing)
            time_module: Time module to use (for testing, default: time module)

        Raises:
            ValueError: If requests_per_second is not positive

        Example:
            >>> limiter = RateLimiter(requests_per_second=2.0)
            >>> limiter.min_interval
            0.5
        """
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self.min_interval = 1.0 / requests_per_second
        self.base_backoff_delay = base_backoff_delay
        self.max_backoff_delay = max_backoff_delay
        self.enabled = enabled
        self._time = time_module if time_module is not None else time

        self._last_request_time: Optional[float] = None
        self._lock = threading.Lock()

        logger.info(
            "Rate limiter initialized: %.2f req/s (min interval: %.2fs)",
            requests_per_second,
            self.min_interval,
        )

    def wait(self) -> None:
        """Wait until rate limit allows next request.

        Blocks the current thread if insufficient time has passed since
        the last request. Thread-safe.

        This method should be called before each API request to ensure
        requests are properly spaced according to the rate limit.

        Example:
            >>> limiter = RateLimiter(requests_per_second=1.0)
            >>> limiter.wait()  # First request: no delay
            >>> limiter.wait()  # Second request: waits ~1 second
        """
        if not self.enabled:
            return

        with self._lock:
            now = self._time.time()

            # Skip delay for first request
            if self._last_request_time is not None:
                elapsed = now - self._last_request_time

                if elapsed < self.min_interval:
                    wait_time = self.min_interval - elapsed
                    logger.debug("Rate limit: waiting %.2fs", wait_time)
                    self._time.sleep(wait_time)

            self._last_request_time = self._time.time()

    def backoff(self, attempt: int) -> None:
        """Perform exponential backoff delay.

        Used when encountering rate limit errors (HTTP 429) or server
        errors (HTTP 5xx). Delay doubles with each attempt.

        The backoff delay is calculated as: base_delay * (2 ** attempt)
        and is capped at max_backoff_delay.

        Args:
            attempt: Current attempt number (0-indexed)

        Example:
            >>> limiter = RateLimiter(base_backoff_delay=5.0)
            >>> limiter.backoff(0)  # Waits 5s
            >>> limiter.backoff(1)  # Waits 10s
            >>> limiter.backoff(2)  # Waits 20s
            >>> limiter.backoff(3)  # Waits 40s

        Note:
            This method updates the last request time to prevent
            immediate retries after backoff completes.
        """
        if not self.enabled:
            return

        # Calculate exponential backoff
        delay = self.base_backoff_delay * (2**attempt)

        # Cap at maximum
        delay = min(delay, self.max_backoff_delay)

        logger.warning(
            "Backoff attempt %d: waiting %.1fs (max: %.1fs)",
            attempt,
            delay,
            self.max_backoff_delay,
        )

        self._time.sleep(delay)

        # Update last request time to prevent immediate retry
        with self._lock:
            self._last_request_time = self._time.time()
