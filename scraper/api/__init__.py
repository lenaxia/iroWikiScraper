"""MediaWiki API client package."""

from .exceptions import (
    APIError,
    APIRequestError,
    APIResponseError,
    PageNotFoundError,
    RateLimitError,
)

__all__ = [
    "APIError",
    "APIRequestError",
    "APIResponseError",
    "PageNotFoundError",
    "RateLimitError",
]
