"""Custom exceptions for MediaWiki API client."""


class APIError(Exception):
    """Base exception for MediaWiki API errors."""


class APIRequestError(APIError):
    """HTTP request failed."""


class APIResponseError(APIError):
    """API response parsing failed."""


class PageNotFoundError(APIError):
    """Requested page not found."""


class RateLimitError(APIError):
    """API rate limit exceeded."""


__all__ = [
    "APIError",
    "APIRequestError",
    "APIResponseError",
    "PageNotFoundError",
    "RateLimitError",
]
