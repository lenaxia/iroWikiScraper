"""Tests for rate limiter with exponential backoff."""

import time
import threading
from typing import List

import pytest

from scraper.api.rate_limiter import RateLimiter
from tests.mocks.mock_time import MockTime


class TestRateLimiterBasics:
    """Test basic rate limiter functionality."""

    def test_initialization_default_params(self):
        """Test rate limiter initializes with default parameters."""
        limiter = RateLimiter()

        assert limiter.min_interval == 1.0  # 1 req/s
        assert limiter.base_backoff_delay == 5.0
        assert limiter.max_backoff_delay == 300.0
        assert limiter.enabled is True

    def test_initialization_custom_params(self):
        """Test rate limiter initializes with custom parameters."""
        limiter = RateLimiter(
            requests_per_second=2.0,
            base_backoff_delay=10.0,
            max_backoff_delay=600.0,
            enabled=False,
        )

        assert limiter.min_interval == 0.5  # 2 req/s = 0.5s interval
        assert limiter.base_backoff_delay == 10.0
        assert limiter.max_backoff_delay == 600.0
        assert limiter.enabled is False

    def test_initialization_invalid_rate(self):
        """Test rate limiter rejects invalid request rate."""
        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            RateLimiter(requests_per_second=0)

        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            RateLimiter(requests_per_second=-1.0)


class TestRateLimiterWait:
    """Test rate limiter wait functionality."""

    def test_first_request_no_delay(self):
        """First request should pass immediately without delay."""
        mock_time = MockTime()

        limiter = RateLimiter(requests_per_second=1.0, time_module=mock_time)

        start_time = mock_time.current_time
        limiter.wait()
        end_time = mock_time.current_time

        # First request should not wait
        assert end_time == start_time

    def test_second_request_waits_for_interval(self):
        """Second request should wait for minimum interval."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=1.0, time_module=mock_time
        )  # 1 req/s = 1s interval

        # First request
        limiter.wait()
        assert mock_time.current_time == 0.0

        # Advance time by 0.5s (less than 1s interval)
        mock_time.advance(0.5)

        # Second request should wait additional 0.5s
        limiter.wait()

        # Total time should be at least 1s from first request
        assert mock_time.current_time >= 1.0

    def test_multiple_rapid_requests(self):
        """Multiple rapid requests should be properly spaced."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=2.0, time_module=mock_time
        )  # 2 req/s = 0.5s interval

        # Make 5 rapid requests
        for _ in range(5):
            limiter.wait()

        # Total time should be at least 4 intervals (between 5 requests)
        # 4 intervals * 0.5s = 2.0s
        assert mock_time.current_time >= 2.0

    def test_requests_after_long_pause(self):
        """Request after long pause should not wait."""
        mock_time = MockTime()

        limiter = RateLimiter(requests_per_second=1.0, time_module=mock_time)

        # First request
        limiter.wait()

        # Advance time by 10s (well past 1s interval)
        mock_time.advance(10.0)

        # Second request should not wait
        start_time = mock_time.current_time
        limiter.wait()
        end_time = mock_time.current_time

        assert end_time == start_time  # No additional delay

    def test_disabled_limiter_no_delay(self):
        """Disabled rate limiter should not delay requests."""
        limiter = RateLimiter(enabled=False)

        # Should return immediately
        start = time.time()
        limiter.wait()
        limiter.wait()
        limiter.wait()
        end = time.time()

        # No significant delay
        assert end - start < 0.1


class TestRateLimiterBackoff:
    """Test exponential backoff functionality."""

    def test_backoff_exponential_increase(self):
        """Backoff should increase exponentially with each attempt."""
        mock_time = MockTime()

        limiter = RateLimiter(base_backoff_delay=5.0, time_module=mock_time)

        # Attempt 0: 5s (5 * 2^0)
        mock_time.reset()
        limiter.backoff(0)
        assert mock_time.current_time == 5.0

        # Attempt 1: 10s (5 * 2^1)
        mock_time.reset()
        limiter.backoff(1)
        assert mock_time.current_time == 10.0

        # Attempt 2: 20s (5 * 2^2)
        mock_time.reset()
        limiter.backoff(2)
        assert mock_time.current_time == 20.0

        # Attempt 3: 40s (5 * 2^3)
        mock_time.reset()
        limiter.backoff(3)
        assert mock_time.current_time == 40.0

    def test_backoff_max_delay(self):
        """Backoff should respect maximum delay limit."""
        mock_time = MockTime()

        limiter = RateLimiter(
            base_backoff_delay=5.0, max_backoff_delay=30.0, time_module=mock_time
        )

        # Attempt 5: would be 160s (5 * 2^5) but capped at 30s
        limiter.backoff(5)
        assert mock_time.current_time == 30.0

        # Attempt 10: would be huge but still capped at 30s
        mock_time.reset()
        limiter.backoff(10)
        assert mock_time.current_time == 30.0

    def test_backoff_custom_base_delay(self):
        """Backoff should use custom base delay."""
        mock_time = MockTime()

        limiter = RateLimiter(base_backoff_delay=2.0, time_module=mock_time)

        # Attempt 0: 2s (2 * 2^0)
        limiter.backoff(0)
        assert mock_time.current_time == 2.0

        # Attempt 2: 8s (2 * 2^2)
        mock_time.reset()
        limiter.backoff(2)
        assert mock_time.current_time == 8.0

    def test_backoff_updates_last_request_time(self):
        """Backoff should update last request time to prevent immediate retry."""
        mock_time = MockTime()

        limiter = RateLimiter(requests_per_second=1.0, time_module=mock_time)

        # Perform backoff
        limiter.backoff(0)  # Sleeps 5s

        # Advance time just slightly (simulate time passing during backoff)
        mock_time.advance(1.0)

        # Next wait() should not wait additional time since we're past the interval
        start_time = mock_time.current_time
        limiter.wait()
        end_time = mock_time.current_time

        # Should not wait since 6 seconds have passed (more than 1s interval)
        assert end_time == start_time

    def test_disabled_limiter_no_backoff(self):
        """Disabled rate limiter should not perform backoff."""
        limiter = RateLimiter(enabled=False)

        # Should return immediately
        start = time.time()
        limiter.backoff(0)
        limiter.backoff(5)
        end = time.time()

        # No significant delay
        assert end - start < 0.1


class TestRateLimiterThreadSafety:
    """Test thread safety of rate limiter."""

    def test_concurrent_waits_are_serialized(self):
        """Concurrent wait() calls should be properly serialized."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=10.0, time_module=mock_time
        )  # 0.1s interval

        wait_times: List[float] = []

        def do_wait():
            limiter.wait()
            wait_times.append(mock_time.current_time)

        # Create 5 threads that all call wait() simultaneously
        threads = [threading.Thread(target=do_wait) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All wait times should be recorded
        assert len(wait_times) == 5

        # Wait times should be properly spaced (at least min_interval apart)
        # Note: Due to threading, exact timing may vary slightly
        # We check that total time is at least 4 intervals
        assert mock_time.current_time >= 0.4  # 4 intervals * 0.1s

    def test_concurrent_backoffs_are_safe(self):
        """Concurrent backoff() calls should not cause race conditions."""
        mock_time = MockTime()

        limiter = RateLimiter(base_backoff_delay=1.0, time_module=mock_time)

        def do_backoff():
            limiter.backoff(0)

        # Create multiple threads that all call backoff() simultaneously
        threads = [threading.Thread(target=do_backoff) for _ in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without errors (main check is no exceptions)
        # Time should have advanced
        assert mock_time.current_time > 0


class TestRateLimiterIntegration:
    """Test rate limiter integration scenarios."""

    def test_wait_then_backoff_sequence(self):
        """Test sequence of wait() followed by backoff()."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=1.0, base_backoff_delay=2.0, time_module=mock_time
        )

        # Normal request
        limiter.wait()
        time1 = mock_time.current_time

        # Advance a bit
        mock_time.advance(0.5)

        # Another request (should wait)
        limiter.wait()
        time2 = mock_time.current_time
        assert time2 >= time1 + 1.0

        # Hit rate limit, need to backoff
        limiter.backoff(0)
        time3 = mock_time.current_time
        assert time3 >= time2 + 2.0

    def test_multiple_backoff_attempts(self):
        """Test multiple consecutive backoff attempts."""
        mock_time = MockTime()

        limiter = RateLimiter(base_backoff_delay=1.0, time_module=mock_time)

        # Simulate multiple retry attempts with increasing backoff
        limiter.backoff(0)  # 1s
        t1 = mock_time.current_time
        assert t1 == 1.0

        limiter.backoff(1)  # 2s
        t2 = mock_time.current_time
        assert t2 == 3.0  # 1 + 2

        limiter.backoff(2)  # 4s
        t3 = mock_time.current_time
        assert t3 == 7.0  # 1 + 2 + 4

    def test_high_rate_limiter(self):
        """Test rate limiter with high request rate."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=100.0, time_module=mock_time
        )  # 0.01s interval

        # Make many requests
        for _ in range(10):
            limiter.wait()

        # Total time should be at least 9 intervals
        # 9 intervals * 0.01s = 0.09s
        assert mock_time.current_time >= 0.09

    def test_low_rate_limiter(self):
        """Test rate limiter with low request rate."""
        mock_time = MockTime()

        limiter = RateLimiter(
            requests_per_second=0.5, time_module=mock_time
        )  # 2s interval

        # Make 3 requests
        for _ in range(3):
            limiter.wait()

        # Total time should be at least 2 intervals
        # 2 intervals * 2s = 4s
        assert mock_time.current_time >= 4.0
