"""Page discovery functionality."""

import logging
from typing import Any, Dict, List, Optional

from scraper.api.client import MediaWikiAPIClient
from scraper.api.exceptions import APIResponseError
from scraper.api.validation import ResponseValidator
from scraper.storage.models import Page

logger = logging.getLogger(__name__)


class PageDiscovery:
    """Discovers pages across wiki namespaces.

    Uses MediaWiki's allpages API to iterate through all pages
    in specified namespaces with pagination support.
    """

    # Common MediaWiki namespaces
    DEFAULT_NAMESPACES = [
        0,  # Main
        1,  # Talk
        2,  # User
        3,  # User talk
        4,  # Project
        5,  # Project talk
        6,  # File
        7,  # File talk
        8,  # MediaWiki
        9,  # MediaWiki talk
        10,  # Template
        11,  # Template talk
        12,  # Help
        13,  # Help talk
        14,  # Category
        15,  # Category talk
    ]

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        page_limit: int = 500,
        progress_interval: int = 100,
    ):
        """Initialize page discovery.

        Args:
            api_client: MediaWiki API client instance
            page_limit: Pages per API request (max 500)
            progress_interval: Log progress every N pages
        """
        self.api = api_client
        self.page_limit = min(page_limit, 500)  # API max is 500
        self.progress_interval = progress_interval

    def discover_namespace(self, namespace: int) -> List[Page]:
        """Discover all pages in a specific namespace.

        Args:
            namespace: Namespace ID to discover

        Returns:
            List of Page objects in the namespace

        Example:
            >>> discovery = PageDiscovery(api_client)
            >>> pages = discovery.discover_namespace(0)  # Main namespace
            >>> len(pages)
            2400
        """
        pages = []
        continue_params: Optional[Dict[str, Any]] = None

        # Detect API version on first use
        if not self.api.api_version_detected:
            self.api._detect_api_version()

        logger.info(f"Starting discovery for namespace {namespace}")

        while True:
            # Build request parameters
            params = {
                "list": "allpages",
                "aplimit": self.page_limit,
                "apnamespace": namespace,
            }

            # Add continuation parameters if present
            if continue_params:
                # Validate continuation token format
                ResponseValidator.validate_continuation(
                    continue_params, "page discovery"
                )
                params.update(continue_params)

            # Make API request
            response = self.api.query(params)

            # Validate response structure
            query = ResponseValidator.validate_query(response, "page discovery")

            # Extract pages from response
            page_list = query.get("allpages", [])

            for page_data in page_list:
                try:
                    page = self._parse_page_data(page_data)
                    pages.append(page)
                except APIResponseError as e:
                    # Log error but continue with other pages
                    logger.error(
                        f"Failed to parse page data: {e}",
                        extra={"page_data": page_data},
                        exc_info=True,
                    )
                    continue

            # Log progress
            if (
                len(pages) % self.progress_interval == 0
                or len(pages) < self.progress_interval
            ):
                logger.info(f"Namespace {namespace}: {len(pages)} pages discovered")

            # Check for continuation
            if "continue" not in response:
                break

            continue_params = response["continue"]

        logger.info(f"Namespace {namespace} complete: {len(pages)} total pages")
        return pages

    def _parse_page_data(self, page_data: Dict[str, Any]) -> Page:
        """Parse page data with validation.

        Args:
            page_data: Raw page data from API

        Returns:
            Validated Page object

        Raises:
            APIResponseError: If page data is invalid
        """
        # Validate required fields
        ResponseValidator.validate_required_fields(
            page_data, required_fields=["pageid", "ns", "title"], context="page data"
        )

        # Safely extract fields with type validation
        page_id = ResponseValidator.safe_get(page_data, "pageid", int, "page data")
        namespace = ResponseValidator.safe_get(page_data, "ns", int, "page data")
        title = ResponseValidator.safe_get(page_data, "title", str, "page data")

        # Optional field - safe presence check
        is_redirect = "redirect" in page_data

        return Page(
            page_id=page_id,
            namespace=namespace,
            title=title,
            is_redirect=is_redirect,
        )

    def discover_all_pages(self, namespaces: Optional[List[int]] = None) -> List[Page]:
        """Discover all pages across multiple namespaces.

        Args:
            namespaces: List of namespace IDs (default: all common namespaces)

        Returns:
            List of all discovered Page objects

        Example:
            >>> discovery = PageDiscovery(api_client)
            >>> all_pages = discovery.discover_all_pages()
            >>> len(all_pages)
            2400
        """
        if namespaces is None:
            namespaces = self.DEFAULT_NAMESPACES

        all_pages = []

        logger.info(f"Starting full discovery across {len(namespaces)} namespaces")

        for ns in namespaces:
            try:
                pages = self.discover_namespace(ns)
                all_pages.extend(pages)
                logger.info(
                    f"Namespace {ns}: {len(pages)} pages (Total: {len(all_pages)})"
                )
            except Exception as e:
                logger.error(f"Failed to discover namespace {ns}: {e}", exc_info=True)
                # Continue with other namespaces
                continue

        logger.info(f"Discovery complete: {len(all_pages)} total pages")
        return all_pages
