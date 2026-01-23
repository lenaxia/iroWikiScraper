"""Mock time module for testing rate limiter without real delays.

This module provides a controllable time implementation that allows tests
to run quickly without waiting for actual time.sleep() calls.
"""


class MockTime:
    """Controllable time for testing rate limiter.

    Provides time.time() and time.sleep() replacements that use simulated
    time instead of real wall-clock time. This allows tests to run instantly
    while still exercising timing logic.

    Example:
        >>> mock_time = MockTime()
        >>> mock_time.time()  # Returns 0.0
        >>> mock_time.sleep(5)
        >>> mock_time.time()  # Returns 5.0
    """

    def __init__(self, initial_time: float = 0.0):
        """Initialize mock time.

        Args:
            initial_time: Starting time value (default 0.0)
        """
        self.current_time = initial_time

    def time(self) -> float:
        """Return current mock time.

        Replacement for time.time() that returns simulated time.

        Returns:
            Current mock time value
        """
        return self.current_time

    def sleep(self, seconds: float) -> None:
        """Advance mock time by seconds.

        Replacement for time.sleep() that advances simulated time
        instantly without blocking.

        Args:
            seconds: Amount of time to advance (seconds)
        """
        self.current_time += seconds

    def advance(self, seconds: float) -> None:
        """Advance time without sleeping.

        Useful for simulating external time passage between operations.

        Args:
            seconds: Amount of time to advance (seconds)
        """
        self.current_time += seconds

    def reset(self) -> None:
        """Reset time to zero."""
        self.current_time = 0.0
