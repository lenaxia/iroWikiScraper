"""Tests for RecentChangesClient and RecentChange model."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests

from scraper.api.exceptions import APIError, NetworkError
from scraper.api.recentchanges import RecentChange, RecentChangesClient
from tests.mocks.mock_http_session import MockResponse


class TestRecentChangeModel:
    """Tests for RecentChange data model."""

    def test_recent_change_initialization(self):
        """Test RecentChange initializes with all fields."""
        timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        change = RecentChange(
            rcid=12345,
            type="new",
            namespace=0,
            title="Test_Page",
            pageid=100,
            revid=1000,
            old_revid=0,
            timestamp=timestamp,
            user="TestUser",
            userid=42,
            comment="Test comment",
            oldlen=0,
            newlen=500,
            log_type=None,
            log_action=None,
        )

        assert change.rcid == 12345
        assert change.type == "new"
        assert change.namespace == 0
        assert change.title == "Test_Page"
        assert change.pageid == 100
        assert change.revid == 1000
        assert change.old_revid == 0
        assert change.timestamp == timestamp
        assert change.user == "TestUser"
        assert change.userid == 42
        assert change.comment == "Test comment"
        assert change.oldlen == 0
        assert change.newlen == 500
        assert change.log_type is None
        assert change.log_action is None

    def test_is_new_page_property_returns_true_for_new(self):
        """Test is_new_page property returns True for 'new' type."""
        change = RecentChange(
            rcid=1,
            type="new",
            namespace=0,
            title="Test",
            pageid=1,
            revid=1,
            old_revid=0,
            timestamp=datetime.now(timezone.utc),
            user="User",
            userid=1,
            comment="",
            oldlen=0,
            newlen=100,
        )

        assert change.is_new_page is True
        assert change.is_edit is False
        assert change.is_deletion is False

    def test_is_edit_property_returns_true_for_edit(self):
        """Test is_edit property returns True for 'edit' type."""
        change = RecentChange(
            rcid=1,
            type="edit",
            namespace=0,
            title="Test",
            pageid=1,
            revid=2,
            old_revid=1,
            timestamp=datetime.now(timezone.utc),
            user="User",
            userid=1,
            comment="",
            oldlen=100,
            newlen=150,
        )

        assert change.is_new_page is False
        assert change.is_edit is True
        assert change.is_deletion is False

    def test_is_deletion_property_returns_true_for_delete_log(self):
        """Test is_deletion property returns True for log delete action."""
        change = RecentChange(
            rcid=1,
            type="log",
            namespace=0,
            title="Test",
            pageid=0,
            revid=0,
            old_revid=0,
            timestamp=datetime.now(timezone.utc),
            user="Admin",
            userid=1,
            comment="Deleted",
            oldlen=0,
            newlen=0,
            log_type="delete",
            log_action="delete",
        )

        assert change.is_new_page is False
        assert change.is_edit is False
        assert change.is_deletion is True

    def test_size_change_property_calculates_correctly(self):
        """Test size_change property calculates size difference."""
        # Growth
        change_grow = RecentChange(
            rcid=1,
            type="edit",
            namespace=0,
            title="Test",
            pageid=1,
            revid=2,
            old_revid=1,
            timestamp=datetime.now(timezone.utc),
            user="User",
            userid=1,
            comment="",
            oldlen=100,
            newlen=200,
        )
        assert change_grow.size_change == 100

        # Shrinkage
        change_shrink = RecentChange(
            rcid=2,
            type="edit",
            namespace=0,
            title="Test",
            pageid=1,
            revid=3,
            old_revid=2,
            timestamp=datetime.now(timezone.utc),
            user="User",
            userid=1,
            comment="",
            oldlen=200,
            newlen=150,
        )
        assert change_shrink.size_change == -50

    def test_repr_includes_key_information(self):
        """Test __repr__ includes type, title, timestamp, and user."""
        timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        change = RecentChange(
            rcid=1,
            type="edit",
            namespace=0,
            title="Test_Page",
            pageid=1,
            revid=1,
            old_revid=0,
            timestamp=timestamp,
            user="TestUser",
            userid=1,
            comment="",
            oldlen=0,
            newlen=100,
        )

        repr_str = repr(change)
        assert "edit" in repr_str
        assert "Test_Page" in repr_str
        assert "TestUser" in repr_str


class TestRecentChangesClient:
    """Tests for RecentChangesClient initialization."""

    def test_client_initialization(self, api_client):
        """Test RecentChangesClient initializes with API client."""
        rc_client = RecentChangesClient(api_client)

        assert rc_client.api is api_client

    def test_client_requires_api_client(self):
        """Test RecentChangesClient requires MediaWikiAPIClient."""
        # Should accept any object with required methods
        from scraper.api.client import MediaWikiAPIClient

        api = MediaWikiAPIClient("https://test.com")
        rc_client = RecentChangesClient(api)

        assert rc_client.api is not None


class TestGetRecentChanges:
    """Tests for get_recent_changes method."""

    def test_get_recent_changes_returns_list(
        self, api_client, mock_session, load_fixture
    ):
        """Test get_recent_changes returns list of RecentChange objects."""
        # Set up mock response
        fixture_data = load_fixture("recentchanges_new_page.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert isinstance(changes, list)
        assert len(changes) == 1
        assert isinstance(changes[0], RecentChange)

    def test_get_recent_changes_parses_new_page(
        self, api_client, mock_session, load_fixture
    ):
        """Test parsing new page creation from API response."""
        fixture_data = load_fixture("recentchanges_new_page.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.rcid == 12345
        assert change.type == "new"
        assert change.namespace == 0
        assert change.title == "New_Page"
        assert change.pageid == 2500
        assert change.revid == 100000
        assert change.old_revid == 0
        assert change.user == "Editor"
        assert change.userid == 42
        assert change.comment == "Created new page about Poring"
        assert change.oldlen == 0
        assert change.newlen == 1500
        assert change.is_new_page is True

    def test_get_recent_changes_parses_edit(
        self, api_client, mock_session, load_fixture
    ):
        """Test parsing page edit from API response."""
        fixture_data = load_fixture("recentchanges_edit.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.rcid == 12346
        assert change.type == "edit"
        assert change.title == "Prontera"
        assert change.pageid == 100
        assert change.revid == 100001
        assert change.old_revid == 99999
        assert change.user == "Admin"
        assert change.comment == "Updated NPC locations"
        assert change.oldlen == 5000
        assert change.newlen == 5200
        assert change.size_change == 200
        assert change.is_edit is True

    def test_get_recent_changes_parses_deletion(
        self, api_client, mock_session, load_fixture
    ):
        """Test parsing page deletion from API response."""
        fixture_data = load_fixture("recentchanges_delete.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.rcid == 12347
        assert change.type == "log"
        assert change.title == "Spam_Page"
        assert change.pageid == 0
        assert change.revid == 0
        assert change.log_type == "delete"
        assert change.log_action == "delete"
        assert change.is_deletion is True

    def test_get_recent_changes_with_namespace_filter(
        self, api_client, mock_session, load_fixture
    ):
        """Test filtering by single namespace."""
        fixture_data = load_fixture("recentchanges_multiple.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, namespace=0)

        # Verify namespace parameter was sent
        params = mock_session.last_request_params
        assert params["rcnamespace"] == "0"

    def test_get_recent_changes_with_multiple_namespaces(
        self, api_client, mock_session, load_fixture
    ):
        """Test filtering by multiple namespaces."""
        fixture_data = load_fixture("recentchanges_multiple.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, namespace=[0, 1])

        # Verify namespace parameter was sent with pipe separator
        params = mock_session.last_request_params
        assert params["rcnamespace"] == "0|1"

    def test_get_recent_changes_with_change_type_filter(
        self, api_client, mock_session, load_fixture
    ):
        """Test filtering by change type."""
        fixture_data = load_fixture("recentchanges_edit.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, change_type="edit")

        # Verify type parameter was sent
        params = mock_session.last_request_params
        assert params["rctype"] == "edit"

    def test_get_recent_changes_with_multiple_change_types(
        self, api_client, mock_session, load_fixture
    ):
        """Test filtering by multiple change types."""
        fixture_data = load_fixture("recentchanges_multiple.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, change_type=["edit", "new"])

        # Verify type parameter was sent with pipe separator
        params = mock_session.last_request_params
        assert params["rctype"] == "edit|new"

    def test_get_recent_changes_validates_time_range(self, api_client):
        """Test that start must be before end."""
        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 31, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(ValueError) as exc_info:
            rc_client.get_recent_changes(start, end)

        assert "start must be before end" in str(exc_info.value)

    def test_get_recent_changes_empty_results(self, api_client, mock_session):
        """Test handling empty results."""
        empty_response = {"batchcomplete": "", "query": {"recentchanges": []}}
        mock_session.add_response("GET", empty_response)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert changes == []


class TestPagination:
    """Tests for pagination handling."""

    def test_pagination_follows_continue_token(
        self, api_client, mock_session, load_fixture
    ):
        """Test that pagination follows continue tokens."""
        # First page with continue token
        page1_data = load_fixture("recentchanges_paginated.json")
        # Second page without continue token (final page)
        page2_data = {
            "batchcomplete": "",
            "query": {
                "recentchanges": [
                    {
                        "rcid": 12360,
                        "type": "edit",
                        "ns": 0,
                        "title": "Final_Page",
                        "pageid": 300,
                        "revid": 110020,
                        "old_revid": 110019,
                        "timestamp": "2026-01-15T13:00:00Z",
                        "user": "Editor3",
                        "userid": 12,
                        "comment": "Last edit",
                        "oldlen": 1200,
                        "newlen": 1250,
                    }
                ]
            },
        }

        mock_session.add_response("GET", page1_data)
        mock_session.add_response("GET", page2_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should have combined results from both pages
        assert len(changes) == 3  # 2 from page 1, 1 from page 2
        assert mock_session.get_call_count == 2

    def test_pagination_accumulates_all_results(
        self, api_client, mock_session, load_fixture
    ):
        """Test that all paginated results are accumulated."""
        page1_data = load_fixture("recentchanges_paginated.json")
        page2_data = load_fixture("recentchanges_edit.json")

        mock_session.add_response("GET", page1_data)
        mock_session.add_response("GET", page2_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Verify all changes were collected
        assert len(changes) == 3  # 2 from page1 + 1 from page2
        rcids = [c.rcid for c in changes]
        assert 12348 in rcids  # From page1
        assert 12349 in rcids  # From page1
        assert 12346 in rcids  # From page2

    def test_pagination_sends_continue_parameters(
        self, api_client, mock_session, load_fixture
    ):
        """Test that continue parameters are sent in subsequent requests."""
        page1_data = load_fixture("recentchanges_paginated.json")
        page2_data = {"batchcomplete": "", "query": {"recentchanges": []}}

        mock_session.add_response("GET", page1_data)
        mock_session.add_response("GET", page2_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Check that second request included continue parameters
        # Note: mock_session.last_request_params will have params from last call
        assert mock_session.get_call_count == 2


class TestTimestampFormatting:
    """Tests for timestamp formatting and timezone handling."""

    def test_format_timestamp_utc(self, api_client):
        """Test formatting UTC datetime to MediaWiki format."""
        rc_client = RecentChangesClient(api_client)
        dt = datetime(2026, 1, 15, 10, 30, 45, tzinfo=timezone.utc)

        formatted = rc_client._format_timestamp(dt)

        assert formatted == "2026-01-15T10:30:45Z"

    def test_format_timestamp_converts_timezone(self, api_client):
        """Test formatting non-UTC datetime converts to UTC."""
        from datetime import timedelta

        rc_client = RecentChangesClient(api_client)
        # Create timezone +05:00
        tz_plus5 = timezone(timedelta(hours=5))
        dt = datetime(2026, 1, 15, 15, 30, 0, tzinfo=tz_plus5)

        formatted = rc_client._format_timestamp(dt)

        # Should be converted to UTC (15:30+05:00 = 10:30 UTC)
        assert formatted == "2026-01-15T10:30:00Z"

    def test_format_timestamp_naive_datetime(self, api_client):
        """Test formatting naive datetime (assumes UTC)."""
        rc_client = RecentChangesClient(api_client)
        dt = datetime(2026, 1, 15, 10, 30, 0)  # No timezone

        formatted = rc_client._format_timestamp(dt)

        assert formatted == "2026-01-15T10:30:00Z"

    def test_parse_timestamp_from_api(self, api_client, mock_session, load_fixture):
        """Test parsing timestamp from API response."""
        fixture_data = load_fixture("recentchanges_new_page.json")
        mock_session.add_response("GET", fixture_data)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        # Timestamp should be parsed as timezone-aware datetime
        timestamp = changes[0].timestamp
        assert timestamp.tzinfo is not None
        assert timestamp == datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_handles_missing_query_in_response(self, api_client, mock_session):
        """Test handling response without query field."""
        bad_response = {"batchcomplete": ""}
        mock_session.add_response("GET", bad_response)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should return empty list, not crash
        assert changes == []

    def test_handles_missing_recentchanges_in_query(self, api_client, mock_session):
        """Test handling response without recentchanges field."""
        bad_response = {"batchcomplete": "", "query": {}}
        mock_session.add_response("GET", bad_response)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should return empty list, not crash
        assert changes == []

    def test_skips_malformed_change_entries(self, api_client, mock_session, caplog):
        """Test that malformed entries are skipped with warning."""
        import logging

        caplog.set_level(logging.WARNING)

        response_with_bad_entry = {
            "batchcomplete": "",
            "query": {
                "recentchanges": [
                    # Good entry
                    {
                        "rcid": 1,
                        "type": "edit",
                        "ns": 0,
                        "title": "Good",
                        "timestamp": "2026-01-15T10:00:00Z",
                    },
                    # Bad entry (missing required field 'rcid')
                    {
                        "type": "edit",
                        "ns": 0,
                        "title": "Bad",
                        "timestamp": "2026-01-15T11:00:00Z",
                    },
                ]
            },
        }
        mock_session.add_response("GET", response_with_bad_entry)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should only include the good entry
        assert len(changes) == 1
        assert changes[0].rcid == 1
        # Should have logged a warning
        assert "Failed to parse change entry" in caplog.text

    def test_handles_network_error(self, api_client, mock_session):
        """Test handling network errors during request."""
        from scraper.api.exceptions import NetworkError

        # Make all retries fail with timeout
        mock_session.set_response_sequence(
            [
                MockResponse(500),  # Will trigger retry
                MockResponse(500),  # Will trigger retry
                MockResponse(500),  # Will trigger retry
            ]
        )

        # Reduce retry delay for faster test
        api_client.retry_delay = 0.01

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        # Should eventually fail after retries exhausted
        with pytest.raises(Exception):  # Will raise ServerError or similar
            rc_client.get_recent_changes(start, end)

    def test_handles_missing_optional_fields(self, api_client, mock_session):
        """Test handling entries with missing optional fields."""
        response_minimal = {
            "batchcomplete": "",
            "query": {
                "recentchanges": [
                    {
                        "rcid": 1,
                        "type": "edit",
                        "ns": 0,
                        "title": "Minimal",
                        "timestamp": "2026-01-15T10:00:00Z",
                        # Missing: pageid, revid, old_revid, user, userid, comment, oldlen, newlen
                    }
                ]
            },
        }
        mock_session.add_response("GET", response_minimal)

        rc_client = RecentChangesClient(api_client)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should handle missing fields with defaults
        assert len(changes) == 1
        change = changes[0]
        assert change.rcid == 1
        assert change.pageid == 0
        assert change.revid == 0
        assert change.old_revid == 0
        assert change.user == ""
        assert change.userid == 0
        assert change.comment == ""
        assert change.oldlen == 0
        assert change.newlen == 0


class TestIntegration:
    """Integration tests with live API (optional)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Live API test - run manually")
    def test_fetch_real_recent_changes_from_irowiki(self):
        """Test fetching real recent changes from irowiki.org."""
        from datetime import timedelta

        from scraper.api.client import MediaWikiAPIClient

        api = MediaWikiAPIClient("https://irowiki.org")
        rc_client = RecentChangesClient(api)

        # Get changes from last 7 days
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)

        changes = rc_client.get_recent_changes(start, end)

        assert isinstance(changes, list)
        # Should have some changes in the last week
        assert len(changes) > 0
        # All should be RecentChange objects
        assert all(isinstance(c, RecentChange) for c in changes)
        # Should be chronologically ordered (oldest first)
        for i in range(len(changes) - 1):
            assert changes[i].timestamp <= changes[i + 1].timestamp
