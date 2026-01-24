"""Integration tests for API resilience features."""

import logging

import pytest

from scraper.api.client import MediaWikiAPIClient
from scraper.api.exceptions import APIResponseError
from scraper.scrapers.page_scraper import PageDiscovery
from tests.mocks.mock_http_session import MockResponse


class TestAPIVersionDetection:
    """Tests for MediaWiki API version detection."""

    def test_version_detection_success(self, api_client, mock_session, load_fixture):
        """Test successful version detection with known version."""
        version_response = load_fixture("version_1_44.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        api_client._detect_api_version()

        assert api_client.api_version == "MediaWiki 1.44.0"
        assert api_client.api_version_detected is True

    def test_version_detection_warns_on_unknown(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test warning is logged for untested version."""
        caplog.set_level(logging.WARNING)

        version_response = load_fixture("version_1_50_untested.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        api_client._detect_api_version()

        assert api_client.api_version == "MediaWiki 1.50.0"
        assert "Untested MediaWiki version" in caplog.text
        assert "1.50.0" in caplog.text

    def test_version_detection_handles_missing_generator(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test graceful handling when generator field is missing."""
        caplog.set_level(logging.WARNING)

        version_response = load_fixture("version_missing_generator.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        api_client._detect_api_version()

        assert api_client.api_version == "Unknown"
        assert api_client.api_version_detected is True

    def test_version_detection_handles_malformed_response(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test graceful handling of malformed version response."""
        caplog.set_level(logging.WARNING)

        version_response = load_fixture("version_malformed.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        api_client._detect_api_version()

        assert api_client.api_version == "Unknown"
        assert api_client.api_version_detected is True

    def test_version_detection_only_runs_once(
        self, api_client, mock_session, load_fixture
    ):
        """Test version detection only runs once."""
        version_response = load_fixture("version_1_44.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        # First call
        api_client._detect_api_version()
        assert mock_session.get_call_count == 1

        # Second call should not make another request
        api_client._detect_api_version()
        assert mock_session.get_call_count == 1  # Still 1

    def test_version_detection_logs_info(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test version detection logs info message."""
        caplog.set_level(logging.INFO)

        version_response = load_fixture("version_1_44.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=version_response)]
        )

        api_client._detect_api_version()

        assert "MediaWiki version" in caplog.text
        assert "1.44.0" in caplog.text

    def test_version_detection_on_error(self, api_client, mock_session, caplog):
        """Test version detection handles errors gracefully."""
        caplog.set_level(logging.WARNING)

        # Simulate network error
        mock_session.set_response_sequence([MockResponse(500)])

        api_client._detect_api_version()

        assert api_client.api_version == "Unknown"
        assert api_client.api_version_detected is True
        assert "Could not detect MediaWiki version" in caplog.text


class TestAPIWarningTracking:
    """Tests for API warning tracking system."""

    def test_new_warning_logged_prominently(self, api_client, mock_session, caplog):
        """Test that new warnings are logged prominently."""
        caplog.set_level(logging.WARNING)

        warning_response = {
            "warnings": {"main": {"*": "First warning message"}},
            "query": {"pages": {}},
        }

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=warning_response)]
        )
        api_client.query({"list": "allpages"})

        assert "NEW API WARNING" in caplog.text
        assert "main" in caplog.text
        assert len(api_client.api_warnings_seen) == 1

    def test_repeated_warning_not_duplicated(self, api_client, mock_session, caplog):
        """Test that repeated warnings are only logged once prominently."""
        caplog.set_level(logging.DEBUG)

        warning_response = {
            "warnings": {"main": {"*": "Same warning"}},
            "query": {"pages": {}},
        }

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=warning_response),
                MockResponse(200, json_data=warning_response),
            ]
        )

        # First call - should log as NEW
        api_client.query({"list": "allpages"})
        first_log = caplog.text
        assert "NEW API WARNING" in first_log

        # Second call - should only log at debug level
        caplog.clear()
        api_client.query({"list": "allpages"})
        second_log = caplog.text
        assert "NEW API WARNING" not in second_log
        assert len(api_client.api_warnings_seen) == 1  # Still only one unique warning

    def test_multiple_warnings_in_single_response(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test tracking multiple warnings in a single response."""
        caplog.set_level(logging.WARNING)

        warning_response = load_fixture("response_multiple_warnings.json")

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=warning_response)]
        )
        api_client.query({"list": "allpages"})

        # Should have 3 unique warnings
        assert len(api_client.api_warnings_seen) == 3
        assert caplog.text.count("NEW API WARNING") == 3

    def test_warning_summary(self, api_client, mock_session):
        """Test warning summary provides correct statistics."""
        warning_response = {
            "warnings": {
                "main": {"*": "Warning 1"},
                "query": {"*": "Warning 2"},
            },
            "query": {"pages": {}},
        }

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=warning_response)]
        )
        api_client.query({"list": "allpages"})

        summary = api_client.get_warning_summary()

        assert summary["total_unique_warnings"] == 2
        assert len(summary["warnings"]) == 2
        assert "api_version" in summary

    def test_warning_summary_no_warnings(self, api_client):
        """Test warning summary with no warnings."""
        summary = api_client.get_warning_summary()

        assert summary["total_unique_warnings"] == 0
        assert summary["warnings"] == []

    def test_different_warnings_all_logged(self, api_client, mock_session, caplog):
        """Test that different warnings are all logged as NEW."""
        caplog.set_level(logging.WARNING)

        responses = [
            {"warnings": {"warn1": {"*": "Message 1"}}, "query": {"pages": {}}},
            {"warnings": {"warn2": {"*": "Message 2"}}, "query": {"pages": {}}},
            {"warnings": {"warn3": {"*": "Message 3"}}, "query": {"pages": {}}},
        ]

        mock_session.set_response_sequence(
            [MockResponse(200, json_data=r) for r in responses]
        )

        for _ in range(3):
            api_client.query({"list": "allpages"})

        assert caplog.text.count("NEW API WARNING") == 3
        assert len(api_client.api_warnings_seen) == 3


class TestPageDiscoveryWithResilience:
    """Tests for PageDiscovery with API resilience features."""

    def test_parse_page_data_valid(self, api_client):
        """Test parsing valid page data."""
        discovery = PageDiscovery(api_client)

        page_data = {
            "pageid": 1,
            "ns": 0,
            "title": "Main Page",
            "redirect": "",
        }

        page = discovery._parse_page_data(page_data)

        assert page.page_id == 1
        assert page.namespace == 0
        assert page.title == "Main Page"
        assert page.is_redirect is True

    def test_parse_page_data_without_redirect(self, api_client):
        """Test parsing page data without redirect field."""
        discovery = PageDiscovery(api_client)

        page_data = {
            "pageid": 2,
            "ns": 0,
            "title": "Regular Page",
        }

        page = discovery._parse_page_data(page_data)

        assert page.page_id == 2
        assert page.is_redirect is False

    def test_parse_page_data_missing_required_field(self, api_client):
        """Test parsing fails gracefully with missing required field."""
        discovery = PageDiscovery(api_client)

        page_data = {
            "pageid": 1,
            "ns": 0,
            # Missing 'title'
        }

        with pytest.raises(APIResponseError) as exc_info:
            discovery._parse_page_data(page_data)

        error = exc_info.value
        assert "title" in str(error)
        assert "missing" in str(error).lower()

    def test_parse_page_data_wrong_type(self, api_client):
        """Test parsing fails when field has wrong type."""
        discovery = PageDiscovery(api_client)

        page_data = {
            "pageid": "not_an_int",  # Should be int
            "ns": 0,
            "title": "Test",
        }

        with pytest.raises(APIResponseError) as exc_info:
            discovery._parse_page_data(page_data)

        error = exc_info.value
        assert "type" in str(error).lower()
        assert "pageid" in str(error)

    def test_discover_namespace_missing_query_field(
        self, api_client, mock_session, load_fixture
    ):
        """Test handling of response missing query field."""
        response = load_fixture("response_missing_query.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)

        with pytest.raises(APIResponseError) as exc_info:
            discovery.discover_namespace(0)

        error = exc_info.value
        assert "query" in str(error).lower()

    def test_discover_namespace_invalid_continuation(
        self, api_client, mock_session, load_fixture
    ):
        """Test handling of invalid continuation token format."""
        response = load_fixture("response_invalid_continuation.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)

        with pytest.raises(APIResponseError) as exc_info:
            discovery.discover_namespace(0)

        error = exc_info.value
        assert "continuation" in str(error).lower()

    def test_discover_namespace_handles_malformed_pages(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test that discovery continues despite malformed page data."""
        caplog.set_level(logging.ERROR)

        response = load_fixture("allpages_missing_pageid.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)

        # Should get the valid pages, skip the malformed one
        pages = discovery.discover_namespace(0)

        # Should have 2 valid pages (1 and 3), skip page without pageid
        assert len(pages) == 2
        assert pages[0].page_id == 1
        assert pages[1].page_id == 3

        # Should log error for the malformed page
        assert "Failed to parse page data" in caplog.text

    def test_discover_namespace_type_validation(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test that discovery validates field types."""
        caplog.set_level(logging.ERROR)

        response = load_fixture("allpages_wrong_type.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)

        pages = discovery.discover_namespace(0)

        # Should have 0 valid pages due to type error
        assert len(pages) == 0
        assert "Failed to parse page data" in caplog.text
        assert "type" in caplog.text.lower()

    def test_discover_namespace_renamed_field(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test handling of renamed fields (simulating API change)."""
        caplog.set_level(logging.ERROR)

        response = load_fixture("allpages_renamed_field.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)

        pages = discovery.discover_namespace(0)

        # Should have 0 pages due to renamed field
        assert len(pages) == 0
        assert "Failed to parse page data" in caplog.text
        assert "pageid" in caplog.text

    def test_discover_namespace_version_detection(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test that discover_namespace triggers version detection."""
        caplog.set_level(logging.INFO)

        version_response = load_fixture("version_1_44.json")
        allpages_response = load_fixture("allpages_single.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=version_response),
                MockResponse(200, json_data=allpages_response),
            ]
        )

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_namespace(0)

        # Version should be detected
        assert api_client.api_version_detected is True
        assert "MediaWiki version" in caplog.text

        # Pages should be discovered
        assert len(pages) == 3


class TestContinuationTokenValidation:
    """Tests for continuation token validation."""

    def test_valid_continuation_token(self, api_client):
        """Test that valid continuation tokens are accepted."""
        from scraper.api.validation import ResponseValidator

        continuation = {"continue": "-||", "apcontinue": "Page_Name"}

        # Should not raise
        ResponseValidator.validate_continuation(continuation, "test")

    def test_invalid_continuation_string(self, api_client):
        """Test that string continuation tokens are rejected."""
        from scraper.api.validation import ResponseValidator

        continuation = "invalid_string_format"

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_continuation(continuation, "test")

        error = exc_info.value
        assert "continuation" in str(error).lower()

    def test_invalid_continuation_none(self, api_client):
        """Test that None continuation tokens are rejected."""
        from scraper.api.validation import ResponseValidator

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_continuation(None, "test")

        error = exc_info.value
        assert "continuation" in str(error).lower()

    def test_empty_continuation_dict_valid(self, api_client):
        """Test that empty dict is valid continuation."""
        from scraper.api.validation import ResponseValidator

        # Empty dict is valid (no more pages)
        ResponseValidator.validate_continuation({}, "test")


class TestResponseStructureValidation:
    """Tests for general response structure validation."""

    def test_validate_query_field_exists(self, api_client):
        """Test validation of query field existence."""
        from scraper.api.validation import ResponseValidator

        response = {"query": {"allpages": []}}

        query = ResponseValidator.validate_query(response, "test")
        assert query == {"allpages": []}

    def test_validate_query_field_missing(self, api_client):
        """Test validation fails when query field is missing."""
        from scraper.api.validation import ResponseValidator

        response = {"batchcomplete": ""}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_query(response, "test")

        error = exc_info.value
        assert "query" in str(error).lower()

    def test_validate_query_field_wrong_type(self, api_client):
        """Test validation fails when query field has wrong type."""
        from scraper.api.validation import ResponseValidator

        response = {"query": "not_a_dict"}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_query(response, "test")

        error = exc_info.value
        assert "query" in str(error).lower()
        assert "type" in str(error).lower()


class TestDefensiveFieldAccess:
    """Tests for defensive field access patterns."""

    def test_safe_access_to_nested_fields(self, api_client):
        """Test safe access to nested fields."""
        from scraper.api.validation import ResponseValidator

        data = {"query": {"pages": {"1": {"pageid": 1, "title": "Test"}}}}

        query = ResponseValidator.safe_get(data, "query", dict, "response")
        assert "pages" in query

        pages = ResponseValidator.safe_get(query, "pages", dict, "query")
        assert "1" in pages

    def test_safe_access_handles_missing_nested(self, api_client):
        """Test safe access fails gracefully on missing nested fields."""
        from scraper.api.validation import ResponseValidator

        data = {"query": {}}

        query = ResponseValidator.safe_get(data, "query", dict, "response")

        with pytest.raises(APIResponseError):
            ResponseValidator.safe_get(query, "pages", dict, "query")

    def test_optional_field_access(self, api_client):
        """Test optional field access returns defaults."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1, "title": "Test"}

        # Optional field not present
        redirect = ResponseValidator.optional_get(data, "redirect", str, None)
        assert redirect is None

        # Optional field present
        title = ResponseValidator.optional_get(data, "title", str, "default")
        assert title == "Test"


class TestGracefulDegradation:
    """Tests for graceful degradation when API changes occur."""

    def test_continues_despite_some_invalid_pages(
        self, api_client, mock_session, load_fixture, caplog
    ):
        """Test that scraper continues when some pages are invalid."""
        caplog.set_level(logging.ERROR)

        response = load_fixture("allpages_missing_pageid.json")

        mock_session.set_response_sequence([MockResponse(200, json_data=response)])

        discovery = PageDiscovery(api_client)
        pages = discovery.discover_namespace(0)

        # Should successfully parse valid pages
        assert len(pages) > 0
        # Should log errors for invalid pages
        assert "Failed to parse" in caplog.text

    def test_clear_error_messages_for_debugging(self, api_client):
        """Test that errors include sufficient debugging information."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": "wrong_type", "ns": 0}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "pageid", int, "page data")

        error = exc_info.value
        # Error should mention the field name
        assert "pageid" in str(error)
        # Error should mention the type issue
        assert "type" in str(error).lower()
        # Error should have context
        assert error.request_params is not None
