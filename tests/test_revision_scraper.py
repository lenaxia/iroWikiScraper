"""Tests for the RevisionScraper class."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.models import Revision


class TestRevisionScraperInit:
    """Tests for RevisionScraper initialization."""

    def test_init_with_defaults(self, mock_api_client):
        """Test initialization with default parameters."""
        scraper = RevisionScraper(mock_api_client)

        assert scraper.api == mock_api_client
        assert scraper.revision_limit == 500
        assert scraper.include_content is True
        assert scraper.progress_interval == 100

    def test_init_with_custom_values(self, mock_api_client):
        """Test initialization with custom parameters."""
        scraper = RevisionScraper(
            api_client=mock_api_client,
            revision_limit=250,
            include_content=False,
            progress_interval=50,
        )

        assert scraper.revision_limit == 250
        assert scraper.include_content is False
        assert scraper.progress_interval == 50

    def test_init_revision_limit_capped_at_500(self, mock_api_client):
        """Test that revision_limit is capped at API maximum of 500."""
        scraper = RevisionScraper(mock_api_client, revision_limit=1000)

        assert scraper.revision_limit == 500


class TestRevisionScraperFetchSingleRevision:
    """Tests for fetching pages with single revisions."""

    def test_fetch_single_revision(self, mock_api_client, load_fixture):
        """Test fetching a page with a single revision."""
        fixture_data = load_fixture("revisions_single.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=1)

        assert len(revisions) == 1

        rev = revisions[0]
        assert rev.revision_id == 1001
        assert rev.page_id == 1
        assert rev.parent_id is None  # First revision
        assert rev.user == "Admin"
        assert rev.user_id == 1
        assert rev.comment == "Initial page creation"
        assert rev.size == 1234
        assert rev.sha1 == "abc123def456"
        assert "Welcome to the wiki!" in rev.content
        assert rev.minor is False
        assert rev.tags == []


class TestRevisionScraperFetchMultipleRevisions:
    """Tests for fetching pages with multiple revisions."""

    def test_fetch_multiple_revisions(self, mock_api_client, load_fixture):
        """Test fetching a page with multiple revisions."""
        fixture_data = load_fixture("revisions_multiple.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=2)

        assert len(revisions) == 3

        # Check first revision
        rev1 = revisions[0]
        assert rev1.revision_id == 2001
        assert rev1.parent_id is None
        assert rev1.user == "Editor1"
        assert rev1.comment == "Created page"

        # Check second revision
        rev2 = revisions[1]
        assert rev2.revision_id == 2002
        assert rev2.parent_id == 2001
        assert rev2.user == "Editor2"
        assert "visual edit" in rev2.tags

        # Check third revision (minor edit)
        rev3 = revisions[2]
        assert rev3.revision_id == 2003
        assert rev3.parent_id == 2002
        assert rev3.minor is True


class TestRevisionScraperPagination:
    """Tests for pagination handling."""

    def test_fetch_with_continuation(self, mock_api_client, load_fixture):
        """Test fetching revisions with pagination (continuation tokens)."""
        # First response with continuation
        fixture1 = load_fixture("revisions_continue.json")
        mock_api_client.session.add_response("GET", fixture1)

        # Second response (final batch)
        fixture2 = load_fixture("revisions_final.json")
        mock_api_client.session.add_response("GET", fixture2)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=5)

        # Should have revisions from both batches
        assert len(revisions) == 2
        assert revisions[0].revision_id == 5001
        assert revisions[1].revision_id == 5002

        # Verify API was called twice (for pagination)
        assert len(mock_api_client.session.responses) == 0  # All consumed


class TestRevisionScraperSpecialCases:
    """Tests for special cases and edge conditions."""

    def test_fetch_revisions_deleted_user(self, mock_api_client, load_fixture):
        """Test fetching revision by deleted/hidden user."""
        fixture_data = load_fixture("revisions_deleted_user.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=10)

        assert len(revisions) == 1

        rev = revisions[0]
        assert rev.user == ""  # Empty for deleted user
        assert rev.user_id is None  # None for deleted user

    def test_fetch_revisions_without_content(self, mock_api_client, load_fixture):
        """Test fetching revisions without content (metadata only)."""
        fixture_data = load_fixture("revisions_single.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client, include_content=False)
        revisions = scraper.fetch_revisions(page_id=1)

        assert len(revisions) == 1
        # Content should be empty when include_content=False
        assert revisions[0].content == ""

    def test_fetch_revisions_invalid_page_id(self, mock_api_client):
        """Test that invalid page_id raises ValueError."""
        scraper = RevisionScraper(mock_api_client)

        with pytest.raises(ValueError, match="page_id must be a positive integer"):
            scraper.fetch_revisions(page_id=0)

        with pytest.raises(ValueError, match="page_id must be a positive integer"):
            scraper.fetch_revisions(page_id=-1)

    def test_fetch_revisions_missing_page(self, mock_api_client):
        """Test fetching revisions for non-existent page."""
        # Mock response for missing page
        missing_page_response = {
            "batchcomplete": "",
            "query": {
                "pages": {
                    "999": {
                        "pageid": 999,
                        "ns": 0,
                        "title": "Missing Page",
                        "missing": "",
                    }
                }
            },
        }
        mock_api_client.session.add_response("GET", missing_page_response)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=999)

        # Should return empty list for missing page
        assert revisions == []

    def test_fetch_revisions_no_revisions(self, mock_api_client):
        """Test fetching revisions when page has no revision data."""
        # Mock response with page but no revisions
        no_revisions_response = {
            "batchcomplete": "",
            "query": {
                "pages": {"100": {"pageid": 100, "ns": 0, "title": "Empty Page"}}
            },
        }
        mock_api_client.session.add_response("GET", no_revisions_response)

        scraper = RevisionScraper(mock_api_client)
        revisions = scraper.fetch_revisions(page_id=100)

        # Should return empty list
        assert revisions == []


class TestRevisionScraperAPIParameters:
    """Tests for API parameter construction."""

    def test_api_params_with_content(self, mock_api_client, load_fixture):
        """Test that API parameters include content prop when requested."""
        fixture_data = load_fixture("revisions_single.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client, include_content=True)
        scraper.fetch_revisions(page_id=1)

        # Check the last call's parameters
        last_call = mock_api_client.session.last_request_params
        assert "content" in last_call.get("rvprop", "")

    def test_api_params_without_content(self, mock_api_client, load_fixture):
        """Test that API parameters exclude content prop when not requested."""
        fixture_data = load_fixture("revisions_single.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client, include_content=False)
        scraper.fetch_revisions(page_id=1)

        # Check the last call's parameters
        last_call = mock_api_client.session.last_request_params
        assert "content" not in last_call.get("rvprop", "")

    def test_api_params_chronological_order(self, mock_api_client, load_fixture):
        """Test that revisions are fetched in chronological order (oldest first)."""
        fixture_data = load_fixture("revisions_single.json")
        mock_api_client.session.add_response("GET", fixture_data)

        scraper = RevisionScraper(mock_api_client)
        scraper.fetch_revisions(page_id=1)

        # Check that rvdir=newer (oldest first)
        last_call = mock_api_client.session.last_request_params
        assert last_call.get("rvdir") == "newer"


class TestRevisionScraperParseRevision:
    """Tests for internal revision parsing logic."""

    def test_parse_revision_with_all_fields(self, mock_api_client):
        """Test parsing revision with all optional fields present."""
        scraper = RevisionScraper(mock_api_client)

        rev_data = {
            "revid": 1001,
            "parentid": 1000,
            "timestamp": "2024-01-15T10:30:00Z",
            "user": "TestUser",
            "userid": 10,
            "comment": "Test edit",
            "size": 100,
            "sha1": "abc123",
            "minor": "",  # Presence indicates minor edit
            "tags": ["visual edit"],
            "slots": {"main": {"content": "Test content"}},
        }

        revision = scraper._parse_revision(rev_data, page_id=1)

        assert revision.revision_id == 1001
        assert revision.parent_id == 1000
        assert revision.user == "TestUser"
        assert revision.user_id == 10
        assert revision.comment == "Test edit"
        assert revision.size == 100
        assert revision.sha1 == "abc123"
        assert revision.minor is True
        assert revision.tags == ["visual edit"]
        assert revision.content == "Test content"

    def test_parse_revision_first_revision(self, mock_api_client):
        """Test parsing first revision (parentid=0)."""
        scraper = RevisionScraper(mock_api_client)

        rev_data = {
            "revid": 1001,
            "parentid": 0,  # MediaWiki returns 0 for first revision
            "timestamp": "2024-01-15T10:30:00Z",
            "user": "Creator",
            "userid": 1,
            "comment": "Created page",
            "size": 50,
            "sha1": "xyz",
            "slots": {"main": {"content": "First content"}},
        }

        revision = scraper._parse_revision(rev_data, page_id=1)

        # parentid should be converted to None
        assert revision.parent_id is None

    def test_parse_revision_hidden_user(self, mock_api_client):
        """Test parsing revision with hidden user."""
        scraper = RevisionScraper(mock_api_client)

        rev_data = {
            "revid": 1001,
            "parentid": 1000,
            "timestamp": "2024-01-15T10:30:00Z",
            "userhidden": "",  # Indicates user is hidden
            "comment": "Edit by hidden user",
            "size": 50,
            "sha1": "xyz",
            "slots": {"main": {"content": "Content"}},
        }

        revision = scraper._parse_revision(rev_data, page_id=1)

        assert revision.user == ""
        assert revision.user_id is None

    def test_parse_revision_without_minor_flag(self, mock_api_client):
        """Test parsing revision without minor edit flag."""
        scraper = RevisionScraper(mock_api_client)

        rev_data = {
            "revid": 1001,
            "parentid": 1000,
            "timestamp": "2024-01-15T10:30:00Z",
            "user": "User",
            "userid": 1,
            "comment": "Major edit",
            "size": 50,
            "sha1": "xyz",
            "slots": {"main": {"content": "Content"}},
            # No "minor" key - not a minor edit
        }

        revision = scraper._parse_revision(rev_data, page_id=1)

        assert revision.minor is False

    def test_parse_revision_empty_tags(self, mock_api_client):
        """Test parsing revision with empty tags list."""
        scraper = RevisionScraper(mock_api_client)

        rev_data = {
            "revid": 1001,
            "parentid": 1000,
            "timestamp": "2024-01-15T10:30:00Z",
            "user": "User",
            "userid": 1,
            "comment": "Untagged edit",
            "size": 50,
            "sha1": "xyz",
            "tags": [],  # Empty tags
            "slots": {"main": {"content": "Content"}},
        }

        revision = scraper._parse_revision(rev_data, page_id=1)

        # Empty list should be converted to None by Revision.__post_init__
        assert revision.tags == []
