"""Generic pagination handler for MediaWiki API queries.

This module provides a reusable pagination handler that can work with any
MediaWiki API query that uses continuation tokens.

Example:
    >>> from scraper.api.client import MediaWikiAPIClient
    >>> from scraper.api.pagination import PaginatedQuery
    >>>
    >>> api = MediaWikiAPIClient("https://irowiki.org")
    >>> query = PaginatedQuery(
    ...     api_client=api,
    ...     initial_params={'list': 'allpages', 'aplimit': 500},
    ...     result_path=['query', 'allpages']
    ... )
    >>>
    >>> for page in query:
    ...     process(page)
"""

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional

from scraper.api.client import MediaWikiAPIClient

logger = logging.getLogger(__name__)


class PaginatedQuery:
    """Generic pagination handler for MediaWiki API queries.

    This class handles automatic pagination of MediaWiki API queries by following
    continuation tokens. It yields results incrementally using the generator pattern.

    Attributes:
        api: MediaWiki API client instance
        params: Initial query parameters
        result_path: Path to navigate to results in response (e.g., ['query', 'allpages'])
        progress_callback: Optional callback function invoked after each batch

    Example:
        >>> query = PaginatedQuery(
        ...     api_client=api,
        ...     initial_params={'list': 'allpages', 'aplimit': 500},
        ...     result_path=['query', 'allpages']
        ... )
        >>> pages = list(query)

        With progress callback:
        >>> def progress(batch_num, items_count):
        ...     print(f"Batch {batch_num}: {items_count} items")
        >>> query = PaginatedQuery(
        ...     api_client=api,
        ...     initial_params={'list': 'allpages'},
        ...     result_path=['query', 'allpages'],
        ...     progress_callback=progress
        ... )
    """

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        initial_params: Dict[str, Any],
        result_path: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Initialize pagination handler.

        Args:
            api_client: MediaWiki API client instance to use for queries
            initial_params: Initial query parameters (must include query type)
            result_path: List of keys to navigate to results in response
            progress_callback: Optional callback(batch_num, items_count) called after each batch

        Raises:
            TypeError: If api_client is None or not MediaWikiAPIClient instance
            ValueError: If initial_params or result_path are invalid

        Example:
            >>> query = PaginatedQuery(
            ...     api_client=client,
            ...     initial_params={'list': 'allpages', 'aplimit': 100},
            ...     result_path=['query', 'allpages']
            ... )
        """
        # Validate api_client
        if api_client is None:
            raise TypeError("api_client cannot be None")
        if not isinstance(api_client, MediaWikiAPIClient):
            raise TypeError(
                f"api_client must be MediaWikiAPIClient instance, got: {type(api_client).__name__}"
            )

        # Validate initial_params
        if initial_params is None or (
            isinstance(initial_params, dict) and len(initial_params) == 0
        ):
            raise ValueError("initial_params cannot be None or empty")
        if not isinstance(initial_params, dict):
            raise ValueError(
                f"initial_params must be a dictionary, got: {type(initial_params).__name__}"
            )

        # Validate result_path
        if result_path is None or (
            isinstance(result_path, list) and len(result_path) == 0
        ):
            raise ValueError("result_path cannot be None or empty")
        if not isinstance(result_path, list):
            raise ValueError(
                f"result_path must be a list, got: {type(result_path).__name__}"
            )

        # Validate result_path elements are strings
        for i, element in enumerate(result_path):
            if not isinstance(element, str):
                raise ValueError(
                    f"result_path elements must be strings, got: {type(element).__name__} at index {i}"
                )

        self.api = api_client
        self.params = initial_params
        self.result_path = result_path
        self.progress_callback = progress_callback

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all results, automatically following continuation tokens.

        Yields:
            Individual result items from the API response

        Raises:
            KeyError: If result_path cannot be navigated in response
            TypeError: If continue token is malformed or result is not iterable
            APIError: If API returns an error during pagination

        Example:
            >>> query = PaginatedQuery(api, params, ['query', 'allpages'])
            >>> for page in query:
            ...     print(page['title'])
        """
        continue_token: Optional[Dict[str, Any]] = None
        batch_num = 0

        while True:
            batch_num += 1

            # Merge continue token into params
            params = {**self.params}
            if continue_token:
                params.update(continue_token)

            # Log the request
            logger.info(f"Fetching batch {batch_num} with params: {params}")

            # Query the API
            response = self.api.query(params)

            # Navigate to results using result_path
            try:
                data = self._navigate_result_path(response)
            except (KeyError, TypeError) as e:
                # Re-raise with context
                raise

            # Validate that data is iterable
            if not hasattr(data, "__iter__") or isinstance(data, (str, dict)):
                raise TypeError(
                    f"Result at path {self.result_path} is not iterable. Got type: {type(data).__name__}"
                )

            # Convert to list to get count
            items = list(data)
            items_count = len(items)

            # Log batch info
            logger.info(f"Batch {batch_num}: Retrieved {items_count} items")

            # Invoke progress callback if provided
            if self.progress_callback is not None:
                try:
                    self.progress_callback(batch_num=batch_num, items_count=items_count)
                except Exception as e:
                    # Log but don't break iteration
                    logger.warning(
                        f"Progress callback raised exception: {e}", exc_info=True
                    )

            # Yield items
            yield from items

            # Check for continuation
            if "continue" not in response:
                logger.info(f"Pagination complete after {batch_num} batches")
                break

            # Validate and extract continue token
            continue_token = response["continue"]
            if not isinstance(continue_token, dict):
                raise TypeError(
                    f"continue token must be a dictionary, got: {type(continue_token).__name__}"
                )

            logger.debug(f"Continue token: {continue_token}")

    def _navigate_result_path(self, response: Dict[str, Any]) -> Any:
        """Navigate nested dictionary structure using result_path.

        Args:
            response: API response dictionary

        Returns:
            Data found at the result_path

        Raises:
            KeyError: If any key in result_path is not found, with helpful context

        Example:
            >>> response = {'query': {'allpages': [...]}}
            >>> result = self._navigate_result_path(response)
        """
        data = response
        path_so_far = []

        for key in self.result_path:
            path_so_far.append(key)

            if not isinstance(data, dict):
                raise KeyError(
                    f"Failed to navigate result_path {self.result_path}. "
                    f"Expected dict at path {path_so_far[:-1]}, got: {type(data).__name__}"
                )

            if key not in data:
                available_keys = list(data.keys()) if isinstance(data, dict) else []
                raise KeyError(
                    f"Failed to navigate result_path {self.result_path}. "
                    f"Key '{key}' not found at path {path_so_far[:-1]}. "
                    f"Available keys: {available_keys}"
                )

            data = data[key]

        return data
