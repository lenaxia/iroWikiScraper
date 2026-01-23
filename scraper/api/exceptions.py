"""Custom exceptions for MediaWiki API client.

This module provides a hierarchy of exceptions for different error conditions
that can occur when interacting with the MediaWiki API. All exceptions include
context information for debugging.
"""

from typing import Any, Dict, Optional


class APIError(Exception):
    """Base exception for MediaWiki API errors.

    All API-related exceptions inherit from this class and provide
    context for debugging including HTTP status codes, API error codes,
    and request parameters.

    Attributes:
        message: Human-readable error message
        cause: Original exception that caused this error
        http_status: HTTP status code if applicable
        api_code: MediaWiki API error code if applicable
        request_params: Request parameters for debugging
    """

    def __init__(
        self,
        message: str,
        cause: Optional[Exception] = None,
        http_status: Optional[int] = None,
        api_code: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize API error with context.

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
            parts.append(f"Caused by: {type(self.cause).__name__}")

        return " | ".join(parts)


class NetworkError(APIError):
    """Network-related errors (timeout, connection, DNS).

    Raised when network-level issues prevent the request from reaching
    the server or receiving a response. These are typically transient
    and may be retried.

    Examples:
        - Connection timeout
        - Connection refused
        - DNS resolution failure
        - Network unreachable
    """


class HTTPError(APIError):
    """HTTP status code errors.

    Base class for errors indicated by HTTP status codes. Subclasses
    distinguish between client errors (4xx) and server errors (5xx).
    """


class ClientError(HTTPError):
    """Client errors (4xx status codes).

    Indicates the request was invalid or cannot be fulfilled. These
    errors generally should NOT be retried as they indicate a problem
    with the request itself.

    Examples:
        - 400 Bad Request
        - 401 Unauthorized
        - 403 Forbidden
        - 404 Not Found
    """


class ServerError(HTTPError):
    """Server errors (5xx status codes).

    Indicates the server encountered an error processing the request.
    These are typically transient and may be retried with backoff.

    Examples:
        - 500 Internal Server Error
        - 502 Bad Gateway
        - 503 Service Unavailable
        - 504 Gateway Timeout
    """


class PageNotFoundError(ClientError):
    """Requested page not found (404).

    Raised when the requested page or resource does not exist on the wiki.
    This should NOT be retried.
    """


class RateLimitError(ClientError):
    """API rate limit exceeded (429).

    Raised when too many requests have been made in a short time period.
    Should be retried with exponential backoff.
    """


class APIRequestError(APIError):
    """HTTP request failed.

    Generic error for HTTP request failures that don't fit other categories.
    Used for unexpected request errors.
    """


class APIResponseError(APIError):
    """API response parsing/validation failed.

    Raised when the API returns a response that cannot be parsed
    (e.g., malformed JSON) or doesn't match the expected structure.
    These errors should NOT be retried.
    """


__all__ = [
    "APIError",
    "NetworkError",
    "HTTPError",
    "ClientError",
    "ServerError",
    "PageNotFoundError",
    "RateLimitError",
    "APIRequestError",
    "APIResponseError",
]
