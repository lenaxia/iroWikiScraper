"""Integration tests for FullScraper with real components and mocked API.

Tests the full scraping workflow end-to-end with actual component instances
but mocked API responses.
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from scraper.api.client import MediaWikiAPIClient
from scraper.config import Config
from scraper.orchestration.full_scraper import FullScraper, ScrapeResult
from scraper.storage.database import Database
from scraper.storage.models import Page, Revision


class TestFullScraperIntegration:
    """Integration tests for complete scraping workflow."""

    def setup_method(self):
        """Set up test environment with real components."""
        # Create temporary database
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Initialize database
        self.database = Database(self.db_path)
        self.database.initialize_schema()

        # Create minimal config
        self.config = Mock(spec=Config)

        # Create API client (will be mocked)
        self.api_client = Mock(spec=MediaWikiAPIClient)
        self.api_client.api_version_detected = (
            True  # Mock attribute needed by PageDiscovery
        )

        # Create scraper with real components
        self.scraper = FullScraper(self.config, self.api_client, self.database)

    def teardown_method(self):
        """Clean up test database."""
        self.database.close()
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def test_full_workflow_single_namespace(self):
        """Test complete workflow with single namespace."""
        # Mock API responses for page discovery
        discovery_response = {
            "query": {
                "allpages": [
                    {"pageid": 1, "ns": 0, "title": "Main_Page"},
                    {"pageid": 2, "ns": 0, "title": "Test_Page"},
                ]
            }
        }

        # Mock API responses for revision fetching
        revisions_page1 = {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "Main_Page",
                        "revisions": [
                            {
                                "revid": 101,
                                "parentid": 0,
                                "timestamp": "2024-01-01T10:00:00Z",
                                "user": "Admin",
                                "userid": 1,
                                "comment": "Initial creation",
                                "size": 100,
                                "sha1": "a" * 40,
                                "minor": False,
                                "tags": [],
                                "slots": {"main": {"*": "Welcome to the wiki"}},
                            }
                        ],
                    }
                }
            }
        }

        revisions_page2 = {
            "query": {
                "pages": {
                    "2": {
                        "pageid": 2,
                        "title": "Test_Page",
                        "revisions": [
                            {
                                "revid": 201,
                                "parentid": 0,
                                "timestamp": "2024-01-02T10:00:00Z",
                                "user": "Editor",
                                "userid": 2,
                                "comment": "Test page creation",
                                "size": 50,
                                "sha1": "b" * 40,
                                "minor": False,
                                "tags": [],
                                "slots": {"main": {"*": "Test content"}},
                            },
                            {
                                "revid": 202,
                                "parentid": 201,
                                "timestamp": "2024-01-03T10:00:00Z",
                                "user": "Editor",
                                "userid": 2,
                                "comment": "Updated content",
                                "size": 60,
                                "sha1": "c" * 40,
                                "minor": True,
                                "tags": [],
                                "slots": {"main": {"*": "Test content updated"}},
                            },
                        ],
                    }
                }
            }
        }

        # Configure mock API to return appropriate responses
        def query_side_effect(params):
            if "list" in params and params["list"] == "allpages":
                return discovery_response
            elif "prop" in params and params["prop"] == "revisions":
                page_id = params["pageids"]
                if page_id == 1:
                    return revisions_page1
                elif page_id == 2:
                    return revisions_page2
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0])

        # Verify result
        assert result.success is True
        assert result.pages_count == 2
        assert result.revisions_count == 3
        assert result.namespaces_scraped == [0]
        assert len(result.errors) == 0
        assert len(result.failed_pages) == 0

        # Verify data was stored in database
        conn = self.database.get_connection()

        # Check pages
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        assert cursor.fetchone()[0] == 2

        # Check revisions
        cursor = conn.execute("SELECT COUNT(*) FROM revisions")
        assert cursor.fetchone()[0] == 3

        # Verify specific page data
        cursor = conn.execute("SELECT namespace, title FROM pages WHERE page_id = 1")
        row = cursor.fetchone()
        assert row[0] == 0  # namespace
        assert row[1] == "Main_Page"  # title

    def test_workflow_with_namespace_failure(self):
        """Test workflow handles namespace discovery failures gracefully."""

        # Mock to raise error for namespace 0, succeed for namespace 4
        def query_side_effect(params):
            if "list" in params and params["list"] == "allpages":
                namespace = params["apnamespace"]
                if namespace == 0:
                    raise Exception("API Error for namespace 0")
                elif namespace == 4:
                    return {
                        "query": {
                            "allpages": [
                                {"pageid": 10, "ns": 4, "title": "Project:Help"},
                            ]
                        }
                    }
            elif "prop" in params and params["prop"] == "revisions":
                page_id = params["pageids"]
                if page_id == 10:
                    return {
                        "query": {
                            "pages": {
                                "10": {
                                    "pageid": 10,
                                    "title": "Project:Help",
                                    "revisions": [
                                        {
                                            "revid": 1001,
                                            "parentid": 0,
                                            "timestamp": "2024-01-01T10:00:00Z",
                                            "user": "Admin",
                                            "userid": 1,
                                            "comment": "Help page",
                                            "size": 100,
                                            "sha1": "x" * 40,
                                            "minor": False,
                                            "tags": [],
                                            "slots": {"main": {"*": "Help content"}},
                                        }
                                    ],
                                }
                            }
                        }
                    }
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0, 4])

        # Should continue despite namespace 0 failure
        assert result.pages_count == 1  # Only namespace 4
        assert result.revisions_count == 1
        # Namespace failures are now recorded as errors (US-0706)
        assert len(result.errors) == 1
        assert "namespace 0" in result.errors[0].lower()

    def test_workflow_with_page_failure(self):
        """Test workflow handles individual page scraping failures."""
        # Mock page discovery to return 2 pages
        discovery_response = {
            "query": {
                "allpages": [
                    {"pageid": 1, "ns": 0, "title": "Page_1"},
                    {"pageid": 2, "ns": 0, "title": "Page_2"},
                ]
            }
        }

        # Mock revisions: page 1 fails, page 2 succeeds
        def query_side_effect(params):
            if "list" in params and params["list"] == "allpages":
                return discovery_response
            elif "prop" in params and params["prop"] == "revisions":
                page_id = params["pageids"]
                if page_id == 1:
                    raise Exception("API timeout for page 1")
                elif page_id == 2:
                    return {
                        "query": {
                            "pages": {
                                "2": {
                                    "pageid": 2,
                                    "title": "Page_2",
                                    "revisions": [
                                        {
                                            "revid": 201,
                                            "parentid": 0,
                                            "timestamp": "2024-01-01T10:00:00Z",
                                            "user": "User",
                                            "userid": 1,
                                            "comment": "Content",
                                            "size": 50,
                                            "sha1": "b" * 40,
                                            "minor": False,
                                            "tags": [],
                                            "slots": {"main": {"*": "Content"}},
                                        }
                                    ],
                                }
                            }
                        }
                    }
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0])

        # Verify error was recorded
        assert result.pages_count == 2
        assert result.revisions_count == 1  # Only page 2 succeeded
        assert result.success is False
        assert len(result.errors) == 1
        assert "Failed to scrape page 1" in result.errors[0]
        assert result.failed_pages == [1]

    def test_workflow_with_progress_tracking(self):
        """Test workflow invokes progress callbacks correctly."""
        # Mock minimal API responses
        discovery_response = {
            "query": {
                "allpages": [
                    {"pageid": 1, "ns": 0, "title": "Page_1"},
                ]
            }
        }

        revisions_response = {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "Page_1",
                        "revisions": [
                            {
                                "revid": 101,
                                "parentid": 0,
                                "timestamp": "2024-01-01T10:00:00Z",
                                "user": "User",
                                "userid": 1,
                                "comment": "Content",
                                "size": 50,
                                "sha1": "a" * 40,
                                "minor": False,
                                "tags": [],
                                "slots": {"main": {"*": "Content"}},
                            }
                        ],
                    }
                }
            }
        }

        def query_side_effect(params):
            if "list" in params:
                return discovery_response
            elif "prop" in params:
                return revisions_response
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Track progress callbacks
        callback_history = []

        def progress_callback(stage: str, current: int, total: int):
            callback_history.append((stage, current, total))

        # Execute scrape with callback
        result = self.scraper.scrape(
            namespaces=[0], progress_callback=progress_callback
        )

        # Verify callbacks were invoked
        assert len(callback_history) > 0

        # Check discovery callback
        discover_calls = [c for c in callback_history if c[0] == "discover"]
        assert len(discover_calls) == 1
        assert discover_calls[0] == ("discover", 1, 1)

        # Check scrape callback
        scrape_calls = [c for c in callback_history if c[0] == "scrape"]
        assert len(scrape_calls) == 1
        assert scrape_calls[0] == ("scrape", 1, 1)

    def test_workflow_with_empty_pages(self):
        """Test workflow handles pages with no revisions."""
        # Mock page discovery
        discovery_response = {
            "query": {
                "allpages": [
                    {"pageid": 1, "ns": 0, "title": "Empty_Page"},
                ]
            }
        }

        # Mock empty revisions
        empty_revisions = {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "Empty_Page",
                        # No revisions key
                    }
                }
            }
        }

        def query_side_effect(params):
            if "list" in params:
                return discovery_response
            elif "prop" in params:
                return empty_revisions
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0])

        # Should handle gracefully
        assert result.pages_count == 1
        assert result.revisions_count == 0
        assert result.success is True

    def test_workflow_multiple_namespaces_batch_operations(self):
        """Test workflow efficiently batches operations across namespaces."""

        # Mock discovery for multiple namespaces
        def query_side_effect(params):
            if "list" in params and params["list"] == "allpages":
                namespace = params["apnamespace"]
                if namespace == 0:
                    return {
                        "query": {
                            "allpages": [
                                {"pageid": 1, "ns": 0, "title": "Main_Page"},
                            ]
                        }
                    }
                elif namespace == 4:
                    return {
                        "query": {
                            "allpages": [
                                {"pageid": 2, "ns": 4, "title": "Project_Page"},
                            ]
                        }
                    }
            elif "prop" in params and params["prop"] == "revisions":
                page_id = params["pageids"]
                return {
                    "query": {
                        "pages": {
                            str(page_id): {
                                "pageid": page_id,
                                "title": f"Page_{page_id}",
                                "revisions": [
                                    {
                                        "revid": page_id * 100,
                                        "parentid": 0,
                                        "timestamp": "2024-01-01T10:00:00Z",
                                        "user": "User",
                                        "userid": 1,
                                        "comment": "Content",
                                        "size": 50,
                                        "sha1": "a" * 40,
                                        "minor": False,
                                        "tags": [],
                                        "slots": {"main": {"*": "Content"}},
                                    }
                                ],
                            }
                        }
                    }
                }
            return {}

        self.api_client.query.side_effect = query_side_effect

        # Execute scrape
        result = self.scraper.scrape(namespaces=[0, 4])

        # Verify both namespaces were processed
        assert result.pages_count == 2
        assert result.revisions_count == 2
        assert result.success is True

        # Verify data in database
        conn = self.database.get_connection()

        # Check namespace distribution
        cursor = conn.execute("SELECT DISTINCT namespace FROM pages ORDER BY namespace")
        namespaces = [row[0] for row in cursor.fetchall()]
        assert namespaces == [0, 4]
