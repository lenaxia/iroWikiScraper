"""MediaWiki API client for iRO Wiki scraper."""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from .exceptions import (
    APIError,
    APIRequestError,
    APIResponseError,
    NetworkError,
    ServerError,
    ClientError,
    PageNotFoundError,
    RateLimitError,
)
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class MediaWikiAPIClient:
    """Client for interacting with MediaWiki API.

    This client provides a robust interface to the MediaWiki API with
    features including:
    - Automatic retry with exponential backoff
    - Connection pooling via requests.Session
    - Comprehensive error handling
    - Request/response validation

    Example:
        >>> client = MediaWikiAPIClient("https://irowiki.org")
        >>> page_data = client.get_page("Main_Page")
        >>> print(page_data['query']['pages'])
    """

    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str = "iROWikiArchiver/1.0",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize MediaWiki API client.

        Args:
            base_url: Base URL of the wiki (e.g., "https://irowiki.org")
            user_agent: User-Agent header for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for transient errors
            retry_delay: Initial delay between retries (exponential backoff)
            rate_limiter: Rate limiter instance (default: 1 req/s)
        """
        self.base_url = base_url.rstrip("/")
        self.api_endpoint = f"{self.base_url}/w/api.php"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        # Use provided rate limiter or create default one
        self.rate_limiter = (
            rate_limiter
            if rate_limiter is not None
            else RateLimiter(requests_per_second=1.0)
        )

    def _request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with retry logic.

        This method handles:
        - Adding required parameters (action, format)
        - Retrying transient errors (429, 500, 503, timeout)
        - Converting HTTP errors to custom exceptions
        - Parsing and validating responses

        Args:
            action: MediaWiki API action (e.g., "query", "parse")
            params: Additional parameters for the request

        Returns:
            Parsed JSON response as dictionary

        Raises:
            APIRequestError: HTTP request failed
            APIResponseError: Response parsing failed
            RateLimitError: Rate limit exceeded (429)
            PageNotFoundError: Page not found (404)
            APIError: API returned error response
        """
        # Add required parameters
        params["action"] = action
        params["format"] = "json"

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                # Wait for rate limit before making request
                self.rate_limiter.wait()

                logger.debug("API request: %s %s", action, params)
                response = self.session.get(
                    self.api_endpoint, params=params, timeout=self.timeout
                )

                # Handle HTTP errors
                if response.status_code == 404:
                    raise PageNotFoundError(
                        "Page not found", http_status=404, request_params=params
                    )
                if response.status_code == 429:
                    # Use rate limiter's exponential backoff for 429 errors
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "Rate limit exceeded, backing off (attempt %s/%s)",
                            attempt + 1,
                            self.max_retries,
                        )
                        self.rate_limiter.backoff(attempt)
                        continue
                    raise RateLimitError(
                        f"Rate limit exceeded after {self.max_retries} attempts",
                        http_status=429,
                        request_params=params,
                    )
                if response.status_code >= 500:
                    # Retry server errors with backoff
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "Server error %s, backing off (attempt %s/%s)",
                            response.status_code,
                            attempt + 1,
                            self.max_retries,
                        )
                        self.rate_limiter.backoff(attempt)
                        continue
                    raise ServerError(
                        f"Server error after {self.max_retries} attempts",
                        http_status=response.status_code,
                        request_params=params,
                    )
                if response.status_code >= 400:
                    raise ClientError(
                        f"Client error: {response.status_code}",
                        http_status=response.status_code,
                        request_params=params,
                    )

                response.raise_for_status()
                return self._parse_response(response)

            except requests.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "Request timeout, backing off (attempt %s/%s)",
                        attempt + 1,
                        self.max_retries,
                    )
                    self.rate_limiter.backoff(attempt)
                    continue
                raise NetworkError(
                    f"Request timeout after {self.max_retries} attempts",
                    cause=e,
                    request_params=params,
                )

            except requests.ConnectionError as e:
                raise NetworkError(
                    f"Connection error: {str(e)}", cause=e, request_params=params
                )

            except requests.RequestException as e:
                # Non-transient errors - don't retry
                raise NetworkError(
                    f"Network error: {str(e)}", cause=e, request_params=params
                )

        # If we exhausted retries
        raise NetworkError(
            f"Max retries ({self.max_retries}) exceeded",
            cause=last_exception,
            request_params=params,
        )

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parse and validate API response.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON data

        Raises:
            APIResponseError: Response is not valid JSON
            APIError: API returned error in response
        """
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "Invalid JSON response", extra={"response_text": response.text[:200]}
            )
            raise APIResponseError(
                "Invalid JSON in API response",
                cause=e,
                http_status=response.status_code,
            )

        # Check for API errors
        if "error" in data:
            error_info = data["error"]
            api_code = error_info.get("code", "unknown")
            api_message = error_info.get("info", "Unknown error")

            logger.error(
                f"API error: {api_code}",
                extra={"api_code": api_code, "api_message": api_message},
            )

            raise APIError(
                f"API error: {api_message}",
                api_code=api_code,
                http_status=response.status_code,
            )

        # Log warnings but don't raise
        if "warnings" in data:
            for warning_type, warning_data in data["warnings"].items():
                logger.warning(
                    f"API warning: {warning_type}",
                    extra={"warning_type": warning_type, "warning_data": warning_data},
                )

        logger.debug(
            "API request successful", extra={"response_keys": list(data.keys())}
        )

        return dict(data)

    def get_page(self, title: str, namespace: int = 0) -> Dict[str, Any]:
        """
        Fetch a single page by title.

        Args:
            title: Page title (without namespace prefix)
            namespace: Namespace ID (default 0 = Main namespace)

        Returns:
            Page data dictionary containing query results

        Example:
            >>> client = MediaWikiAPIClient("https://irowiki.org")
            >>> data = client.get_page("Prontera")
            >>> pages = data['query']['pages']
        """
        # Build the full title with namespace if needed
        if namespace != 0:
            full_title = f"{namespace}:{title}"
        else:
            full_title = title

        params = {"titles": full_title, "prop": "info", "inprop": "url"}

        return self._request("query", params)

    def get_pages(self, titles: List[str], namespace: int = 0) -> Dict[str, Any]:
        """
        Fetch multiple pages by titles.

        Args:
            titles: List of page titles (without namespace prefix)
            namespace: Namespace ID (default 0 = Main namespace)

        Returns:
            Page data dictionary containing query results for all pages

        Example:
            >>> client = MediaWikiAPIClient("https://irowiki.org")
            >>> data = client.get_pages(["Prontera", "Geffen", "Payon"])
            >>> pages = data['query']['pages']
        """
        # Build full titles with namespace if needed
        if namespace != 0:
            full_titles = [f"{namespace}:{title}" for title in titles]
        else:
            full_titles = titles

        # Join titles with pipe separator
        titles_param = "|".join(full_titles)

        params = {"titles": titles_param, "prop": "info", "inprop": "url"}

        return self._request("query", params)

    def query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute generic query with custom parameters.

        This method provides direct access to the MediaWiki API query action
        with custom parameters. Use this for advanced queries not covered by
        the convenience methods.

        Args:
            params: Query parameters (action and format will be added automatically)

        Returns:
            Query results

        Example:
            >>> client = MediaWikiAPIClient("https://irowiki.org")
            >>> data = client.query({
            ...     'list': 'allpages',
            ...     'aplimit': 10,
            ...     'apnamespace': 0
            ... })
            >>> pages = data['query']['allpages']
        """
        return self._request("query", params)
