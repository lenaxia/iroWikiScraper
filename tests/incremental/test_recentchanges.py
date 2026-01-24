"""Tests for RecentChanges API client."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from scraper.api.recentchanges import RecentChange, RecentChangesClient


class TestRecentChange:
    """Tests for RecentChange data model."""

    def test_create_recent_change(self):
        """Test creating a basic RecentChange object."""
        rc = RecentChange(
            rcid=12345,
            type="edit",
            namespace=0,
            title="Test_Page",
            pageid=100,
            revid=1001,
            old_revid=1000,
            timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            user="TestUser",
            userid=42,
            comment="Test edit",
            oldlen=100,
            newlen=150,
        )

        assert rc.rcid == 12345
        assert rc.type == "edit"
        assert rc.title == "Test_Page"
        assert rc.is_edit
        assert not rc.is_new_page
        assert not rc.is_deletion
        assert rc.size_change == 50

    def test_new_page_properties(self):
        """Test new page identification."""
        rc = RecentChange(
            rcid=12345,
            type="new",
            namespace=0,
            title="New_Page",
            pageid=200,
            revid=2001,
            old_revid=0,
            timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            user="Creator",
            userid=10,
            comment="Created page",
            oldlen=0,
            newlen=500,
        )

        assert rc.is_new_page
        assert not rc.is_edit
        assert not rc.is_deletion
        assert rc.size_change == 500

    def test_deletion_properties(self):
        """Test deletion identification."""
        rc = RecentChange(
            rcid=12347,
            type="log",
            namespace=0,
            title="Deleted_Page",
            pageid=0,
            revid=0,
            old_revid=0,
            timestamp=datetime(2026, 1, 16, 9, 0, 0, tzinfo=timezone.utc),
            user="Admin",
            userid=1,
            comment="Spam",
            oldlen=0,
            newlen=0,
            log_type="delete",
            log_action="delete",
        )

        assert rc.is_deletion
        assert not rc.is_new_page
        assert not rc.is_edit
        assert rc.size_change == 0


class TestRecentChangesClient:
    """Tests for RecentChangesClient."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = Mock()
        return api

    @pytest.fixture
    def rc_client(self, mock_api):
        """Create RecentChangesClient with mock API."""
        return RecentChangesClient(mock_api)

    def test_init(self, mock_api):
        """Test client initialization."""
        client = RecentChangesClient(mock_api)
        assert client.api == mock_api

    def test_get_recent_changes_empty(self, rc_client, mock_api, load_fixture):
        """Test fetching recent changes with no results."""
        mock_api._request.return_value = load_fixture("recentchanges_empty.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 0
        mock_api._request.assert_called_once()

    def test_get_recent_changes_single_edit(self, rc_client, mock_api, load_fixture):
        """Test fetching single edit."""
        mock_api._request.return_value = load_fixture("recentchanges_edit.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.type == "edit"
        assert change.title == "Prontera"
        assert change.pageid == 100
        assert change.revid == 100001
        assert change.user == "Admin"

    def test_get_recent_changes_new_page(self, rc_client, mock_api, load_fixture):
        """Test fetching new page creation."""
        mock_api._request.return_value = load_fixture("recentchanges_new.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.is_new_page
        assert change.title == "New_Page"
        assert change.old_revid == 0

    def test_get_recent_changes_deletion(self, rc_client, mock_api, load_fixture):
        """Test fetching page deletion."""
        mock_api._request.return_value = load_fixture("recentchanges_delete.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 1
        change = changes[0]
        assert change.is_deletion
        assert change.pageid == 0
        assert change.log_action == "delete"

    def test_get_recent_changes_mixed(self, rc_client, mock_api, load_fixture):
        """Test fetching mixed change types."""
        mock_api._request.return_value = load_fixture("recentchanges_mixed.json")

        start = datetime(2026, 1, 10, tzinfo=timezone.utc)
        end = datetime(2026, 1, 12, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        assert len(changes) == 4

        # Check we have different types
        types = [c.type for c in changes]
        assert "new" in types
        assert "edit" in types
        assert "log" in types

    def test_get_recent_changes_pagination(self, rc_client, mock_api, load_fixture):
        """Test pagination handling."""
        # First call returns page with continue token
        mock_api._request.side_effect = [
            load_fixture("recentchanges_page2.json"),
            load_fixture("recentchanges_edit.json"),
        ]

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end)

        # Should have called API twice for pagination
        assert mock_api._request.call_count == 2
        assert len(changes) == 2  # One from each page

    def test_get_recent_changes_with_namespace_filter(
        self, rc_client, mock_api, load_fixture
    ):
        """Test namespace filtering."""
        mock_api._request.return_value = load_fixture("recentchanges_edit.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, namespace=0)  # noqa: F841

        # Check namespace parameter was passed
        call_args = mock_api._request.call_args[0][1]
        assert "rcnamespace" in call_args
        assert call_args["rcnamespace"] == "0"

    def test_get_recent_changes_with_change_type_filter(
        self, rc_client, mock_api, load_fixture
    ):
        """Test change type filtering."""
        mock_api._request.return_value = load_fixture("recentchanges_edit.json")

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        changes = rc_client.get_recent_changes(start, end, change_type="edit")  # noqa: F841

        # Check type parameter was passed
        call_args = mock_api._request.call_args[0][1]
        assert "rctype" in call_args
        assert call_args["rctype"] == "edit"

    def test_get_recent_changes_invalid_time_range(self, rc_client):
        """Test error when start >= end."""
        start = datetime(2026, 1, 31, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="start must be before end"):
            rc_client.get_recent_changes(start, end)

    def test_format_timestamp(self, rc_client):
        """Test timestamp formatting."""
        dt = datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        formatted = rc_client._format_timestamp(dt)

        assert formatted == "2026-01-15T14:30:00Z"

    def test_parse_change_entry(self, rc_client):
        """Test parsing raw change data."""
        data = {
            "rcid": 12345,
            "type": "edit",
            "ns": 0,
            "title": "Test_Page",
            "pageid": 100,
            "revid": 1001,
            "old_revid": 1000,
            "timestamp": "2026-01-15T10:00:00Z",
            "user": "TestUser",
            "userid": 42,
            "comment": "Test edit",
            "oldlen": 100,
            "newlen": 150,
        }

        change = rc_client._parse_change_entry(data)

        assert change.rcid == 12345
        assert change.type == "edit"
        assert change.title == "Test_Page"
        assert change.pageid == 100
        assert change.user == "TestUser"
