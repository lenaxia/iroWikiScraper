"""Tests for IncrementalRevisionScraper."""

from datetime import datetime, timezone
from unittest.mock import Mock

from scraper.incremental.models import PageUpdateInfo
from scraper.incremental.revision_scraper import IncrementalRevisionScraper


class TestIncrementalRevisionScraper:
    """Tests for IncrementalRevisionScraper."""

    def test_init(self):
        """Test initialization."""
        mock_api = Mock()
        mock_db = Mock()

        scraper = IncrementalRevisionScraper(mock_api, mock_db)

        assert scraper.api is mock_api
        assert scraper.db is mock_db

    def test_fetch_new_revisions_single(self):
        """Test fetching single new revision."""
        mock_api = Mock()
        mock_db = Mock()

        # Mock API response
        mock_api.query.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "revisions": [
                            {
                                "revid": 1001,
                                "parentid": 1000,
                                "timestamp": "2026-01-15T10:00:00Z",
                                "user": "TestUser",
                                "userid": 42,
                                "comment": "Test edit",
                                "*": "Test content",
                                "size": 100,
                                "sha1": "abc123",
                                "tags": [],
                            }
                        ],
                    }
                }
            }
        }

        scraper = IncrementalRevisionScraper(mock_api, mock_db)
        info = PageUpdateInfo(
            page_id=123,
            namespace=0,
            title="Test",
            is_redirect=False,
            highest_revision_id=1000,
            last_revision_timestamp=datetime.now(timezone.utc),
            total_revisions_stored=1,
        )

        revisions = scraper.fetch_new_revisions(info)

        assert len(revisions) == 1
        assert revisions[0].revision_id == 1001
        assert revisions[0].page_id == 123

    def test_fetch_new_revisions_none(self):
        """Test when no new revisions exist."""
        mock_api = Mock()
        mock_db = Mock()

        # Mock API response with no revisions
        mock_api.query.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123
                        # No "revisions" key
                    }
                }
            }
        }

        scraper = IncrementalRevisionScraper(mock_api, mock_db)
        info = PageUpdateInfo(
            page_id=123,
            namespace=0,
            title="Test",
            is_redirect=False,
            highest_revision_id=1000,
            last_revision_timestamp=datetime.now(timezone.utc),
            total_revisions_stored=1,
        )

        revisions = scraper.fetch_new_revisions(info)

        assert len(revisions) == 0

    def test_fetch_new_revisions_batch(self):
        """Test batch fetching for multiple pages."""
        mock_api = Mock()
        mock_db = Mock()

        # Mock API responses
        def mock_query(params):
            page_id = params["pageids"]
            return {
                "query": {
                    "pages": {
                        str(page_id): {
                            "pageid": page_id,
                            "revisions": [
                                {
                                    "revid": page_id * 10,
                                    "parentid": 0,
                                    "timestamp": "2026-01-15T10:00:00Z",
                                    "user": "User",
                                    "userid": 1,
                                    "comment": "Edit",
                                    "*": "Content",
                                    "size": 100,
                                    "sha1": "abc",
                                    "tags": [],
                                }
                            ],
                        }
                    }
                }
            }

        mock_api.query.side_effect = mock_query

        scraper = IncrementalRevisionScraper(mock_api, mock_db)
        infos = [
            PageUpdateInfo(
                page_id=i,
                namespace=0,
                title=f"Page{i}",
                is_redirect=False,
                highest_revision_id=i - 1,
                last_revision_timestamp=datetime.now(timezone.utc),
                total_revisions_stored=1,
            )
            for i in [100, 200, 300]
        ]

        results = scraper.fetch_new_revisions_batch(infos)

        assert len(results) == 3
        assert 100 in results
        assert 200 in results
        assert 300 in results

    def test_insert_new_revisions_deduplication(self, db, sample_revisions):
        """Test deduplication when inserting revisions."""
        from scraper.storage.models import Page
        from scraper.storage.page_repository import PageRepository
        from scraper.storage.revision_repository import RevisionRepository

        # Insert page and one revision
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)
        page_repo.insert_page(page)
        rev_repo.insert_revision(sample_revisions[0])  # revision_id=1001

        # Try to insert same revision again
        mock_api = Mock()
        scraper = IncrementalRevisionScraper(mock_api, db)

        inserted = scraper.insert_new_revisions(1, [sample_revisions[0]])

        # Should skip duplicate
        assert inserted == 0


class TestRevisionParsing:
    """Tests for revision parsing."""

    def test_parse_revision_complete(self):
        """Test parsing revision with all fields."""
        mock_api = Mock()
        mock_db = Mock()

        scraper = IncrementalRevisionScraper(mock_api, mock_db)

        rev_data = {
            "revid": 1001,
            "parentid": 1000,
            "timestamp": "2026-01-15T10:00:00Z",
            "user": "TestUser",
            "userid": 42,
            "comment": "Test comment",
            "*": "Test content",
            "size": 100,
            "sha1": "abcdef123",
            "minor": True,
            "tags": ["tag1", "tag2"],
        }

        revision = scraper._parse_revision(rev_data, 123)

        assert revision.revision_id == 1001
        assert revision.page_id == 123
        assert revision.parent_id == 1000
        assert revision.user == "TestUser"
        assert revision.content == "Test content"
        assert revision.minor is True
        assert revision.tags == ["tag1", "tag2"]

    def test_parse_revision_minimal(self):
        """Test parsing revision with minimal fields."""
        mock_api = Mock()
        mock_db = Mock()

        scraper = IncrementalRevisionScraper(mock_api, mock_db)

        rev_data = {
            "revid": 1001,
            "timestamp": "2026-01-15T10:00:00Z",
            "sha1": "placeholder",  # Required field
        }

        revision = scraper._parse_revision(rev_data, 123)

        assert revision.revision_id == 1001
        assert revision.page_id == 123
        assert revision.parent_id is None  # Should be None, not 0
        assert revision.user == ""
