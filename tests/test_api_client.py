"""Tests for MediaWiki API client."""

import pytest
import requests

from scraper.api.client import MediaWikiAPIClient
from scraper.api.exceptions import (
    APIError,
    APIResponseError,
    NetworkError,
    PageNotFoundError,
    RateLimitError,
    ServerError,
)
from tests.mocks.mock_http_session import MockResponse


class TestMediaWikiAPIClientInit:
    """Tests for MediaWikiAPIClient initialization."""

    def test_client_initialization_with_defaults(self):
        """Test client initializes with default values."""
        client = MediaWikiAPIClient("https://irowiki.org")

        assert client.base_url == "https://irowiki.org"
        assert client.api_endpoint == "https://irowiki.org/w/api.php"
        assert client.timeout == 30
        assert client.max_retries == 3
        assert client.retry_delay == 5.0
        assert client.session is not None

    def test_client_initialization_strips_trailing_slash(self):
        """Test client strips trailing slash from base URL."""
        client = MediaWikiAPIClient("https://irowiki.org/")

        assert client.base_url == "https://irowiki.org"
        assert client.api_endpoint == "https://irowiki.org/w/api.php"

    def test_client_initialization_with_custom_values(self):
        """Test client initializes with custom configuration."""
        client = MediaWikiAPIClient(
            base_url="https://example.com",
            user_agent="CustomBot/2.0",
            timeout=60,
            max_retries=5,
            retry_delay=10.0,
        )

        assert client.base_url == "https://example.com"
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.retry_delay == 10.0

    def test_client_sets_user_agent_header(self):
        """Test client sets User-Agent header correctly."""
        client = MediaWikiAPIClient("https://irowiki.org", user_agent="TestBot/1.0")

        assert "User-Agent" in client.session.headers
        assert client.session.headers["User-Agent"] == "TestBot/1.0"


class TestMediaWikiAPIClientRequest:
    """Tests for MediaWikiAPIClient._request method."""

    def test_successful_request_returns_parsed_data(self, api_client, mock_session):
        """Test successful API request returns parsed JSON data."""
        result = api_client._request("query", {"titles": "Main_Page"})

        assert "query" in result
        assert "pages" in result["query"]
        assert mock_session.get_call_count == 1

    def test_request_adds_required_parameters(self, api_client, mock_session):
        """Test request adds action and format parameters."""
        api_client._request("query", {"titles": "Main_Page"})

        params = mock_session.last_request_params
        assert params["action"] == "query"
        assert params["format"] == "json"
        assert params["titles"] == "Main_Page"

    def test_404_raises_page_not_found_error(self, api_client):
        """Test HTTP 404 raises PageNotFoundError."""
        with pytest.raises(PageNotFoundError) as exc_info:
            api_client._request("query", {"titles": "NonexistentPage"})

        assert "Page not found" in str(exc_info.value)

    def test_429_raises_rate_limit_error(self, api_client):
        """Test HTTP 429 raises RateLimitError."""
        with pytest.raises(RateLimitError) as exc_info:
            api_client._request("query", {"titles": "RateLimitPage"})

        assert "Rate limit exceeded" in str(exc_info.value)

    def test_timeout_raises_api_request_error(self, api_client):
        """Test request timeout raises NetworkError."""
        with pytest.raises(NetworkError) as exc_info:
            api_client._request("query", {"titles": "TimeoutPage"})

        assert "timeout" in str(exc_info.value).lower()

    def test_malformed_json_raises_api_response_error(self, api_client):
        """Test malformed JSON response raises APIResponseError."""
        with pytest.raises(APIResponseError) as exc_info:
            api_client._request("query", {"titles": "MalformedPage"})

        assert "Invalid JSON" in str(exc_info.value)

    def test_api_error_response_raises_api_error(self, api_client):
        """Test API error response raises APIError."""
        with pytest.raises(APIError) as exc_info:
            api_client._request("query", {"titles": "APIErrorPage"})

        assert "doesn't exist" in str(exc_info.value)

    def test_500_error_retries_with_backoff(self, api_client, mock_session):
        """Test server error triggers retry with exponential backoff."""
        # Set up mock to return 500 twice, then success
        mock_session.set_response_sequence(
            [
                MockResponse(500),
                MockResponse(500),
                MockResponse(
                    200, json_data={"query": {"pages": {"1": {"title": "Test"}}}}
                ),
            ]
        )

        # Reduce retry delay for faster test
        api_client.retry_delay = 0.1

        result = api_client._request("query", {"titles": "Test"})

        assert mock_session.get_call_count == 3
        assert "query" in result

    def test_max_retries_exceeded_raises_error(self, api_client, mock_session):
        """Test max retries exceeded raises ServerError."""
        # Set up mock to always return 500
        mock_session.set_response_sequence(
            [MockResponse(500), MockResponse(500), MockResponse(500), MockResponse(500)]
        )

        api_client.retry_delay = 0.1

        with pytest.raises(ServerError) as exc_info:
            api_client._request("query", {"titles": "Test"})

        assert "Server error" in str(exc_info.value)
        assert mock_session.get_call_count == 3  # max_retries default is 3

    def test_timeout_retries_before_failing(self, api_client, mock_session):
        """Test timeout triggers retry before failing."""
        # Set up mock to timeout twice, then succeed
        timeout_count = [0]

        def get_with_timeout(*args, **kwargs):
            timeout_count[0] += 1
            if timeout_count[0] < 3:
                raise requests.Timeout("Timeout")
            fixture_file = (
                mock_session.fixtures_dir / "api" / "successful_page_response.json"
            )
            import json

            with open(fixture_file, encoding="utf-8") as f:
                data = json.load(f)
            return MockResponse(200, json_data=data)

        mock_session.get = get_with_timeout
        api_client.retry_delay = 0.1

        result = api_client._request("query", {"titles": "Test"})

        assert timeout_count[0] == 3
        assert "query" in result


class TestMediaWikiAPIClientParseResponse:
    """Tests for MediaWikiAPIClient._parse_response method."""

    def test_parse_valid_json_response(self, api_client):
        """Test parsing valid JSON response."""
        mock_response = MockResponse(200, json_data={"test": "data"})

        result = api_client._parse_response(mock_response)

        assert result == {"test": "data"}

    def test_parse_invalid_json_raises_error(self, api_client):
        """Test parsing invalid JSON raises APIResponseError."""
        mock_response = MockResponse(200, text="Not JSON")

        with pytest.raises(APIResponseError) as exc_info:
            api_client._parse_response(mock_response)

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_error_response_raises_api_error(self, api_client):
        """Test parsing error response raises APIError."""
        mock_response = MockResponse(
            200,
            json_data={"error": {"code": "missingtitle", "info": "Page doesn't exist"}},
        )

        with pytest.raises(APIError) as exc_info:
            api_client._parse_response(mock_response)

        assert "Page doesn't exist" in str(exc_info.value)

    def test_parse_response_with_warnings_logs_warning(self, api_client, caplog):
        """Test parsing response with warnings logs warning message."""
        import logging

        caplog.set_level(logging.WARNING)

        mock_response = MockResponse(
            200,
            json_data={
                "warnings": {"main": {"*": "Some warning"}},
                "query": {"pages": {}},
            },
        )

        result = api_client._parse_response(mock_response)

        assert "warning" in caplog.text.lower()
        assert "main" in caplog.text.lower()
        assert "query" in result


class TestMediaWikiAPIClientGetPage:
    """Tests for MediaWikiAPIClient.get_page method."""

    def test_get_page_returns_page_data(self, api_client, mock_session):
        """Test get_page returns page data successfully."""
        result = api_client.get_page("Main_Page")

        assert "query" in result
        assert "pages" in result["query"]
        assert mock_session.get_call_count == 1

    def test_get_page_with_namespace(self, api_client, mock_session):
        """Test get_page with custom namespace."""
        result = api_client.get_page("Test", namespace=1)  # noqa: F841

        params = mock_session.last_request_params
        assert "1:Test" in params["titles"]

    def test_get_page_default_namespace_zero(self, api_client, mock_session):
        """Test get_page uses namespace 0 by default."""
        api_client.get_page("Test")

        params = mock_session.last_request_params
        assert params["titles"] == "Test"


class TestMediaWikiAPIClientGetPages:
    """Tests for MediaWikiAPIClient.get_pages method."""

    def test_get_pages_returns_multiple_pages(self, api_client, mock_session):
        """Test get_pages returns data for multiple pages."""
        result = api_client.get_pages(["Page1", "Page2", "Page3"])

        assert "query" in result
        params = mock_session.last_request_params
        assert "Page1|Page2|Page3" in params["titles"]

    def test_get_pages_with_namespace(self, api_client, mock_session):
        """Test get_pages with custom namespace."""
        result = api_client.get_pages(["Test1", "Test2"], namespace=2)  # noqa: F841

        params = mock_session.last_request_params
        # Each title should be prefixed with namespace
        assert "2:Test1" in params["titles"]
        assert "2:Test2" in params["titles"]


class TestMediaWikiAPIClientQuery:
    """Tests for MediaWikiAPIClient.query method."""

    def test_query_with_custom_parameters(self, api_client, mock_session):
        """Test query method with custom parameters."""
        custom_params = {"list": "allpages", "aplimit": 10, "apnamespace": 0}

        result = api_client.query(custom_params)

        assert "query" in result
        params = mock_session.last_request_params
        assert params["list"] == "allpages"
        assert params["aplimit"] == 10
        assert params["apnamespace"] == 0


class TestMediaWikiAPIClientSession:
    """Tests for MediaWikiAPIClient session management."""

    def test_session_is_reused_across_requests(self, api_client, mock_session):
        """Test session object is reused for multiple requests."""
        session_before = api_client.session

        api_client.get_page("Page1")
        api_client.get_page("Page2")

        assert api_client.session is session_before
        assert mock_session.get_call_count == 2


class TestMediaWikiAPIClientIntegration:
    """Integration tests with live API (can be skipped)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Live API test - run manually")
    def test_fetch_real_page_from_irowiki(self):
        """Test fetching a real page from irowiki.org."""
        client = MediaWikiAPIClient("https://irowiki.org")

        result = client.get_page("Main_Page")

        assert "query" in result
        assert "pages" in result["query"]
        # Should have at least one page
        assert len(result["query"]["pages"]) > 0
