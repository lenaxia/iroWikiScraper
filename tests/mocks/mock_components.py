"""Mock components for testing FullScraper orchestration."""

from typing import List

from scraper.storage.models import Page, Revision


class MockPageDiscovery:
    """Mock PageDiscovery for testing orchestration."""

    DEFAULT_NAMESPACES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    def __init__(self, api_client=None):
        """Initialize mock page discovery."""
        self.api_client = api_client
        self.discover_namespace_calls = []
        self.pages_to_return = {}
        self.should_fail = {}

    def set_pages_for_namespace(self, namespace: int, pages: List[Page]):
        """Configure pages to return for a namespace."""
        self.pages_to_return[namespace] = pages

    def set_namespace_failure(self, namespace: int, exception: Exception):
        """Configure namespace to fail with exception."""
        self.should_fail[namespace] = exception

    def discover_namespace(self, namespace: int) -> List[Page]:
        """Mock discover_namespace method."""
        self.discover_namespace_calls.append(namespace)

        if namespace in self.should_fail:
            raise self.should_fail[namespace]

        return self.pages_to_return.get(namespace, [])


class MockRevisionScraper:
    """Mock RevisionScraper for testing orchestration."""

    def __init__(self, api_client=None):
        """Initialize mock revision scraper."""
        self.api_client = api_client
        self.fetch_revisions_calls = []
        self.revisions_to_return = {}
        self.should_fail = {}

    def set_revisions_for_page(self, page_id: int, revisions: List[Revision]):
        """Configure revisions to return for a page."""
        self.revisions_to_return[page_id] = revisions

    def set_page_failure(self, page_id: int, exception: Exception):
        """Configure page to fail with exception."""
        self.should_fail[page_id] = exception

    def fetch_revisions(self, page_id: int) -> List[Revision]:
        """Mock fetch_revisions method."""
        self.fetch_revisions_calls.append(page_id)

        if page_id in self.should_fail:
            raise self.should_fail[page_id]

        return self.revisions_to_return.get(page_id, [])


class MockPageRepository:
    """Mock PageRepository for testing orchestration."""

    def __init__(self, db=None):
        """Initialize mock page repository."""
        self.db = db
        self.insert_pages_batch_calls = []
        self.inserted_pages = []
        self.should_fail = False
        self.failure_exception = None

    def set_batch_insert_failure(self, exception: Exception):
        """Configure batch insert to fail."""
        self.should_fail = True
        self.failure_exception = exception

    def insert_pages_batch(self, pages: List[Page]) -> None:
        """Mock insert_pages_batch method."""
        self.insert_pages_batch_calls.append(len(pages))

        if self.should_fail:
            raise self.failure_exception

        self.inserted_pages.extend(pages)


class MockRevisionRepository:
    """Mock RevisionRepository for testing orchestration."""

    def __init__(self, db=None):
        """Initialize mock revision repository."""
        self.db = db
        self.insert_revisions_batch_calls = []
        self.inserted_revisions = []
        self.should_fail = False
        self.failure_exception = None

    def set_batch_insert_failure(self, exception: Exception):
        """Configure batch insert to fail."""
        self.should_fail = True
        self.failure_exception = exception

    def insert_revisions_batch(self, revisions: List[Revision]) -> None:
        """Mock insert_revisions_batch method."""
        self.insert_revisions_batch_calls.append(len(revisions))

        if self.should_fail:
            raise self.failure_exception

        self.inserted_revisions.extend(revisions)
