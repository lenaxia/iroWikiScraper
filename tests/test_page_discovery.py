"""Tests for page discovery functionality."""

import pytest

from scraper.scrapers.page_scraper import PageDiscovery
from scraper.storage.models import Page
from tests.mocks.mock_http_session import MockResponse


class TestPageModel:
    """Tests for Page dataclass."""

    def test_page_creation_valid(self):
        """Test creating valid page."""
        page = Page(page_id=1, namespace=0, title="Main Page")

        assert page.page_id == 1
        assert page.namespace == 0
        assert page.title == "Main Page"
        assert page.is_redirect is False

    def test_page_with_redirect(self):
        """Test page marked as redirect."""
        page = Page(page_id=2, namespace=0, title="Redirect Page", is_redirect=True)

        assert page.is_redirect is True

    def test_page_invalid_page_id(self):
        """Test page_id validation."""
        with pytest.raises(ValueError, match="page_id must be positive"):
            Page(page_id=0, namespace=0, title="Test")

        with pytest.raises(ValueError, match="page_id must be positive"):
            Page(page_id=-1, namespace=0, title="Test")

    def test_page_invalid_namespace(self):
        """Test namespace validation."""
        with pytest.raises(ValueError, match="namespace must be non-negative"):
            Page(page_id=1, namespace=-1, title="Test")

    def test_page_invalid_title(self):
        """Test title validation."""
        with pytest.raises(ValueError, match="title cannot be empty"):
            Page(page_id=1, namespace=0, title="")

        with pytest.raises(ValueError, match="title cannot be empty"):
            Page(page_id=1, namespace=0, title="   ")

    def test_page_title_normalization(self):
        """Test title whitespace normalization."""
        page = Page(page_id=1, namespace=0, title="  Test Page  ")
        assert page.title == "Test Page"


class TestPageDiscovery:
    """Tests for PageDiscovery class."""

    def test_discover_namespace_single_batch(
        self, api_client, mock_session, fixtures_dir
    ):
        """Test discovering namespace with single batch."""
        # Load fixture
        fixture_file = fixtures_dir / "api" / "allpages_single.json"
        import json

        with open(fixture_file) as f:
            data = json.load(f)

        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_namespace(0)

        assert len(pages) == 3
        assert pages[0].page_id == 1
        assert pages[0].title == "Main Page"
        assert pages[2].is_redirect is True

    def test_discover_namespace_with_pagination(
        self, api_client, mock_session, fixtures_dir
    ):
        """Test discovering namespace with pagination."""
        import json

        # Load fixtures
        continue_fixture = fixtures_dir / "api" / "allpages_continue.json"
        final_fixture = fixtures_dir / "api" / "allpages_final.json"

        with open(continue_fixture) as f:
            continue_data = json.load(f)
        with open(final_fixture) as f:
            final_data = json.load(f)

        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=continue_data),
                MockResponse(200, json_data=final_data),
            ]
        )

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_namespace(0)

        # Should have pages from both batches
        assert len(pages) == 3  # 2 from continue + 1 from final
        assert mock_session.get_call_count == 2

    def test_discover_all_pages(self, api_client, mock_session, fixtures_dir):
        """Test discovering all pages across namespaces."""
        import json

        fixture_file = fixtures_dir / "api" / "allpages_single.json"
        with open(fixture_file) as f:
            data = json.load(f)

        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        # Return same fixture for all namespace requests
        responses = [MockResponse(200, json_data=data) for _ in range(16)]
        mock_session.set_response_sequence(responses)

        discovery = PageDiscovery(api_client)
        all_pages = discovery.discover_all_pages()

        # Should have 3 pages * 16 namespaces = 48
        assert len(all_pages) == 48
        assert mock_session.get_call_count == 16

    def test_discover_namespace_empty(self, api_client, mock_session):
        """Test discovering empty namespace."""
        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        empty_response = {"batchcomplete": "", "query": {"allpages": []}}

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=empty_response)]
        )

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_namespace(99)

        assert len(pages) == 0

    def test_page_limit_capped_at_500(self, api_client):
        """Test page limit is capped at API maximum."""
        discovery = PageDiscovery(api_client, page_limit=1000)
        assert discovery.page_limit == 500

    def test_custom_namespaces(self, api_client, mock_session, fixtures_dir):
        """Test discovering specific namespaces only."""
        import json

        fixture_file = fixtures_dir / "api" / "allpages_single.json"
        with open(fixture_file) as f:
            data = json.load(f)

        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        responses = [MockResponse(200, json_data=data) for _ in range(2)]
        mock_session.set_response_sequence(responses)

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_all_pages(namespaces=[0, 6])  # Main and File

        assert len(pages) == 6  # 3 pages * 2 namespaces
        assert mock_session.get_call_count == 2

    def test_discover_all_pages_with_error(
        self, api_client, mock_session, fixtures_dir
    ):
        """Test that errors in one namespace don't stop discovery of others."""
        import json

        fixture_file = fixtures_dir / "api" / "allpages_single.json"
        with open(fixture_file) as f:
            data = json.load(f)

        # Pre-set version detection to avoid extra API call
        api_client.api_version_detected = True
        api_client.api_version = "MediaWiki 1.44.0"

        # First namespace succeeds, second fails, third succeeds
        responses = [
            MockResponse(200, json_data=data),
            MockResponse(500, json_data={"error": "Internal error"}),
            MockResponse(500, json_data={"error": "Internal error"}),
            MockResponse(500, json_data={"error": "Internal error"}),
            MockResponse(200, json_data=data),
        ]
        mock_session.set_response_sequence(responses)

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_all_pages(namespaces=[0, 1, 2])

        # Should have pages from namespace 0 and 2 (namespace 1 failed)
        assert len(pages) == 6  # 3 pages * 2 successful namespaces
        assert mock_session.get_call_count == 5
