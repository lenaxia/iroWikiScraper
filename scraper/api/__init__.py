"""MediaWiki API client package."""

from .exceptions import (
    APIError,
    APIRequestError,
    APIResponseError,
    PageNotFoundError,
    RateLimitError,
)
from .pagination import PaginatedQuery

__all__ = [
    "APIError",
    "APIRequestError",
    "APIResponseError",
    "PageNotFoundError",
    "RateLimitError",
    "PaginatedQuery",
]
