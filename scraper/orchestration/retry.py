"""Retry logic with exponential backoff for error handling.

This module provides utilities for retrying operations that may fail due to
transient errors, using exponential backoff to avoid overwhelming services.
"""

import logging
import sqlite3
import time
from typing import Callable, TypeVar

import requests

from scraper.api.exceptions import (
    APIResponseError,
    NetworkError,
    PageNotFoundError,
    RateLimitError,
    ServerError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_transient_error(error: Exception) -> bool:
    """Determine if an error is transient and should be retried.

    Transient errors are temporary issues that may succeed on retry:
    - Network timeouts and connection failures
    - API rate limiting
    - Server errors (5xx)
    - Database locking issues

    Permanent errors should not be retried:
    - 404 Not Found
    - Data validation errors
    - API response parsing errors

    Args:
        error: Exception to classify

    Returns:
        True if error is transient and should be retried, False otherwise
    """
    # Network-level errors (transient)
    if isinstance(error, (NetworkError, requests.exceptions.Timeout)):
        return True

    if isinstance(error, (requests.exceptions.ConnectionError, ConnectionError)):
        return True

    # Rate limiting (transient)
    if isinstance(error, RateLimitError):
        return True

    # Server errors (transient)
    if isinstance(error, ServerError):
        return True

    # Database locking (transient)
    if isinstance(error, sqlite3.OperationalError):
        if "locked" in str(error).lower():
            return True

    # Client errors (permanent)
    if isinstance(error, PageNotFoundError):
        return False

    # Validation errors (permanent)
    if isinstance(error, (ValueError, TypeError, APIResponseError)):
        return False

    # Unknown errors - default to permanent (don't retry)
    return False


def retry_with_backoff(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Retry an operation with exponential backoff.

    Attempts to execute the operation, retrying on transient errors with
    exponentially increasing delays between attempts. Permanent errors are
    not retried and are raised immediately.

    Args:
        operation: Callable that performs the operation to retry
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds, doubled each retry (default: 1.0)

    Returns:
        Result of the operation if successful

    Raises:
        Exception: The last exception if all retries are exhausted,
                   or immediately if error is not transient

    Example:
        >>> def fetch_page():
        ...     # May raise NetworkError on timeout
        ...     return api.get_page("Main_Page")
        >>> result = retry_with_backoff(fetch_page, max_retries=3)
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return operation()

        except Exception as e:
            last_error = e

            # Check if error is transient
            if not is_transient_error(e):
                logger.debug(
                    f"Non-transient error, not retrying: {type(e).__name__}: {e}"
                )
                raise

            # Check if we have retries left
            if attempt >= max_retries - 1:
                logger.error(
                    f"All {max_retries} retry attempts exhausted: {type(e).__name__}: {e}"
                )
                raise

            # Calculate delay with exponential backoff
            delay = base_delay * (2**attempt)

            logger.warning(
                f"Transient error on attempt {attempt + 1}/{max_retries}, "
                f"retrying after {delay:.1f}s: {type(e).__name__}: {e}"
            )

            time.sleep(delay)

    # This should never be reached, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error: no attempts made")
