"""MediaWiki API client for iRO Wiki scraper."""

import logging
import time
from typing import Any, Dict, List

import requests

from .exceptions import (
    APIError,
    APIRequestError,
    APIResponseError,
    PageNotFoundError,
    RateLimitError,
)

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
    ):
        """
        Initialize MediaWiki API client.

        Args:
            base_url: Base URL of the wiki (e.g., "https://irowiki.org")
            user_agent: User-Agent header for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for transient errors
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.base_url = base_url.rstrip("/")
        self.api_endpoint = f"{self.base_url}/w/api.php"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

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
                logger.debug("API request: %s %s", action, params)
                response = self.session.get(
                    self.api_endpoint, params=params, timeout=self.timeout
                )

                # Handle HTTP errors
                if response.status_code == 404:
                    raise PageNotFoundError(f"Page not found: {params}")
                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")
                if response.status_code >= 500:
                    # Retry server errors
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2**attempt)
                        logger.warning(
                            "Server error %s, retrying in %ss (attempt %s/%s)",
                            response.status_code,
                            delay,
                            attempt + 1,
                            self.max_retries,
                        )
                        time.sleep(delay)
                        continue
                    raise APIRequestError(f"Server error: {response.status_code}")

                response.raise_for_status()
                return self._parse_response(response)

            except requests.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        "Request timeout, retrying in %ss (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    time.sleep(delay)
                    continue
                raise APIRequestError(
                    f"Request timeout after {self.max_retries} attempts"
                ) from e

            except requests.RequestException as e:
                # Non-transient errors - don't retry
                raise APIRequestError(f"Request failed: {e}") from e

        # If we exhausted retries
        raise APIRequestError(
            f"Max retries ({self.max_retries}) exceeded"
        ) from last_exception

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
            raise APIResponseError("Invalid JSON response") from e

        # Check for API errors
        if "error" in data:
            error_info = data["error"].get("info", "Unknown error")
            raise APIError(f"API error: {error_info}")

        # Log warnings
        if "warnings" in data:
            logger.warning("API warnings: %s", data["warnings"])

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
