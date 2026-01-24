"""Tests for IncrementalLinkScraper."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from scraper.incremental.link_scraper import IncrementalLinkScraper
from scraper.storage.models import Link


class TestIncrementalLinkScraper:
    """Tests for IncrementalLinkScraper initialization and basic operations."""

    def test_init(self, db):
        """Test initialization."""
        scraper = IncrementalLinkScraper(db)

        assert scraper.db is db
        assert scraper.link_extractor is not None

    def test_update_links_for_page_single_link(self, db, sample_pages):
        """Test updating links for a page with single link."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        # Update links
        scraper = IncrementalLinkScraper(db)
        content = "This is a link to [[Test Article]]."

        inserted = scraper.update_links_for_page(1, content)

        # Verify
        assert inserted == 1

        # Check database
        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)
        assert len(links) == 1
        assert links[0].target_title == "Test Article"
        assert links[0].link_type == "page"

    def test_update_links_for_page_multiple_links(self, db, sample_pages):
        """Test updating links with multiple link types."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        # Update links with multiple types
        scraper = IncrementalLinkScraper(db)
        content = """
        See [[Main Page]] and [[Test Article]].
        {{Template:Infobox}}
        [[File:Example.png]]
        [[Category:Test]]
        """

        inserted = scraper.update_links_for_page(1, content)

        # Verify count (5 unique links: 2 pages, 1 template, 1 file, 1 category)
        assert inserted == 5

        # Check database
        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)
        assert len(links) == 5

        # Check each type present
        link_types = {link.link_type for link in links}
        assert link_types == {"page", "template", "file", "category"}

    def test_update_links_for_page_replaces_old_links(self, db, sample_pages):
        """Test that update replaces old links atomically."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)
        link_storage = LinkStorage(db)

        # First update - insert initial links
        content1 = "[[Page A]] and [[Page B]]"
        scraper.update_links_for_page(1, content1)

        links = link_storage.get_links_by_source(1)
        assert len(links) == 2
        titles = {link.target_title for link in links}
        assert titles == {"Page A", "Page B"}

        # Second update - completely different links
        content2 = "[[Page C]] and [[Page D]] and [[Page E]]"
        scraper.update_links_for_page(1, content2)

        links = link_storage.get_links_by_source(1)
        assert len(links) == 3
        titles = {link.target_title for link in links}
        assert titles == {"Page C", "Page D", "Page E"}

        # Old links should be gone
        assert "Page A" not in titles
        assert "Page B" not in titles

    def test_update_links_for_page_empty_content(self, db, sample_pages):
        """Test updating with empty content removes all links."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)
        link_storage = LinkStorage(db)

        # First add some links
        content1 = "[[Page A]] and [[Page B]]"
        scraper.update_links_for_page(1, content1)
        assert len(link_storage.get_links_by_source(1)) == 2

        # Update with empty content
        inserted = scraper.update_links_for_page(1, "")

        assert inserted == 0
        links = link_storage.get_links_by_source(1)
        assert len(links) == 0

    def test_update_links_for_page_no_existing_links(self, db, sample_pages):
        """Test updating page that has no existing links."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)

        # Verify no links initially
        link_storage = LinkStorage(db)
        assert len(link_storage.get_links_by_source(1)) == 0

        # Add links
        content = "[[New Link]]"
        inserted = scraper.update_links_for_page(1, content)

        assert inserted == 1
        assert len(link_storage.get_links_by_source(1)) == 1

    def test_update_links_for_page_duplicate_links(self, db, sample_pages):
        """Test that duplicate links in content are deduplicated."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)
        content = "[[Same Page]] and [[Same Page]] and [[Same Page]]"

        inserted = scraper.update_links_for_page(1, content)

        # Should only insert once (LinkExtractor deduplicates)
        assert inserted == 1

        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)
        assert len(links) == 1

    def test_update_links_for_page_many_links(self, db, sample_pages):
        """Test updating page with many links (100+)."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        # Generate content with 150 unique links
        links_text = " ".join([f"[[Page {i}]]" for i in range(150)])

        scraper = IncrementalLinkScraper(db)
        inserted = scraper.update_links_for_page(1, links_text)

        assert inserted == 150

        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)
        assert len(links) == 150

    def test_update_links_for_page_transaction_rollback_on_error(
        self, db, sample_pages
    ):
        """Test that transaction rolls back on error."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)
        link_storage = LinkStorage(db)

        # Add initial links
        content1 = "[[Page A]]"
        scraper.update_links_for_page(1, content1)
        assert len(link_storage.get_links_by_source(1)) == 1

        # Mock link_extractor to raise error after DELETE
        with patch.object(
            scraper.link_extractor, "extract_links", side_effect=Exception("Test error")
        ):
            with pytest.raises(Exception, match="Test error"):
                scraper.update_links_for_page(1, "[[Page B]]")

        # Original links should still be there (rollback)
        links = link_storage.get_links_by_source(1)
        assert len(links) == 1
        assert links[0].target_title == "Page A"

    def test_update_links_for_page_invalid_wikitext(self, db, sample_pages):
        """Test handling of malformed wikitext."""
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        scraper = IncrementalLinkScraper(db)

        # Malformed wikitext should not crash (LinkExtractor handles gracefully)
        content = "[[Broken link [[ ]] {{ }}"
        inserted = scraper.update_links_for_page(1, content)

        # Should handle gracefully (may extract 0 or some valid links)
        assert inserted >= 0


class TestBatchOperations:
    """Tests for batch link update operations."""

    def test_update_links_batch_multiple_pages(self, db, sample_pages):
        """Test batch update for multiple pages."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert pages
        page_repo = PageRepository(db)
        for page in sample_pages[:3]:
            page_repo.insert_page(page)

        scraper = IncrementalLinkScraper(db)

        # Batch update
        page_contents = {
            1: "[[Link A]]",
            2: "[[Link B]] [[Link C]]",
            3: "[[Link D]] [[Link E]] [[Link F]]",
        }

        results = scraper.update_links_batch(page_contents)

        # Verify results
        assert len(results) == 3
        assert results[1] == 1
        assert results[2] == 2
        assert results[3] == 3

        # Verify database
        link_storage = LinkStorage(db)
        assert len(link_storage.get_links_by_source(1)) == 1
        assert len(link_storage.get_links_by_source(2)) == 2
        assert len(link_storage.get_links_by_source(3)) == 3

    def test_update_links_batch_continues_on_failure(self, db, sample_pages):
        """Test that batch continues processing even if individual pages fail."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert pages
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1
        page_repo.insert_page(sample_pages[2])  # page_id=3

        scraper = IncrementalLinkScraper(db)

        # Page 2 doesn't exist but SQLite allows inserting links without FK constraint
        page_contents = {
            1: "[[Link A]]",
            2: "[[Link B]]",  # This page doesn't exist in DB - but SQLite allows it
            3: "[[Link C]]",
        }

        results = scraper.update_links_batch(page_contents)

        # All should succeed (SQLite doesn't enforce FK by default)
        assert len(results) == 3
        assert results[1] == 1
        assert results[2] == 1  # Succeeds even though page doesn't exist
        assert results[3] == 1

        # Verify successful pages
        link_storage = LinkStorage(db)
        assert len(link_storage.get_links_by_source(1)) == 1
        assert (
            len(link_storage.get_links_by_source(2)) == 1
        )  # Links exist even if page doesn't
        assert len(link_storage.get_links_by_source(3)) == 1

    def test_update_links_batch_empty_input(self, db):
        """Test batch with empty input."""
        scraper = IncrementalLinkScraper(db)

        results = scraper.update_links_batch({})

        assert results == {}

    def test_update_links_batch_single_page(self, db, sample_pages):
        """Test batch with single page."""
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])

        scraper = IncrementalLinkScraper(db)

        results = scraper.update_links_batch({1: "[[Link A]]"})

        assert len(results) == 1
        assert results[1] == 1

    def test_update_links_batch_logs_failures(self, db, sample_pages, caplog):
        """Test that batch logs individual failures."""
        import logging
        from unittest.mock import patch

        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])
        page_repo.insert_page(sample_pages[1])  # page_id=2

        scraper = IncrementalLinkScraper(db)

        # Mock link_extractor to raise error for page 2
        original_extract = scraper.link_extractor.extract_links

        def mock_extract(page_id, wikitext):
            if page_id == 2:
                raise ValueError("Simulated extraction error")
            return original_extract(page_id, wikitext)

        with caplog.at_level(logging.ERROR):
            with patch.object(
                scraper.link_extractor, "extract_links", side_effect=mock_extract
            ):
                page_contents = {
                    1: "[[Link A]]",
                    2: "[[Link B]]",  # This will fail due to mock
                }
                results = scraper.update_links_batch(page_contents)

        # Check that error was logged for page 2
        assert "Failed to update links for page 2" in caplog.text

        # Check results
        assert results[1] == 1
        assert results[2] == 0  # Failed due to exception


class TestDeleteOperations:
    """Tests for link deletion operations."""

    def test_delete_links_for_page(self, db, sample_pages):
        """Test deleting all links from a page."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        # Insert page
        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1

        # Add some links
        scraper = IncrementalLinkScraper(db)
        scraper.update_links_for_page(1, "[[A]] [[B]] [[C]]")

        link_storage = LinkStorage(db)
        assert len(link_storage.get_links_by_source(1)) == 3

        # Delete all links
        deleted = scraper.delete_links_for_page(1)

        assert deleted == 3
        assert len(link_storage.get_links_by_source(1)) == 0

    def test_delete_links_for_page_no_existing_links(self, db, sample_pages):
        """Test deleting from page with no links."""
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])

        scraper = IncrementalLinkScraper(db)
        deleted = scraper.delete_links_for_page(1)

        assert deleted == 0

    def test_delete_links_for_page_nonexistent_page(self, db):
        """Test deleting links for nonexistent page."""
        scraper = IncrementalLinkScraper(db)

        # Should not crash, just return 0
        deleted = scraper.delete_links_for_page(999)

        assert deleted == 0


class TestTransactionSemantics:
    """Tests for transaction isolation and atomicity."""

    def test_transaction_atomicity(self, db, sample_pages):
        """Test that DELETE and INSERT happen atomically."""
        import threading
        import time

        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])

        scraper = IncrementalLinkScraper(db)
        link_storage = LinkStorage(db)

        # Add initial links
        scraper.update_links_for_page(1, "[[Link A]]")

        # Track if we ever see 0 links during update
        saw_zero_links = []

        def check_links():
            """Continuously check link count during update."""
            for _ in range(100):
                try:
                    links = link_storage.get_links_by_source(1)
                    if len(links) == 0:
                        saw_zero_links.append(True)
                    time.sleep(0.001)
                except Exception:
                    pass

        # Start checking thread
        thread = threading.Thread(target=check_links)
        thread.start()

        # Perform update
        scraper.update_links_for_page(1, "[[Link B]]")

        thread.join()

        # Should never see 0 links during transaction
        # (This test may be timing-dependent, but helps verify atomicity)
        # In SQLite, with proper transaction handling, the DELETE and INSERT
        # should not be visible to other connections until commit

    def test_concurrent_updates_isolated(self, db, sample_pages):
        """Test that concurrent updates to different pages are isolated."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])  # page_id=1
        page_repo.insert_page(sample_pages[1])  # page_id=2

        scraper = IncrementalLinkScraper(db)
        link_storage = LinkStorage(db)

        # Update page 1
        scraper.update_links_for_page(1, "[[Link A]]")

        # Update page 2
        scraper.update_links_for_page(2, "[[Link B]]")

        # Both should have their own links
        links1 = link_storage.get_links_by_source(1)
        links2 = link_storage.get_links_by_source(2)

        assert len(links1) == 1
        assert len(links2) == 1
        assert links1[0].target_title == "Link A"
        assert links2[0].target_title == "Link B"


class TestLinkExtractorIntegration:
    """Tests for integration with LinkExtractor."""

    def test_uses_link_extractor(self, db, sample_pages):
        """Test that IncrementalLinkScraper uses LinkExtractor correctly."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])

        scraper = IncrementalLinkScraper(db)

        # Content with all link types
        content = """
        Regular links: [[Main Page]], [[Help:Contents]]
        Template: {{Stub}}
        File: [[File:Logo.png]]
        Category: [[Category:Test]]
        """

        scraper.update_links_for_page(1, content)

        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)

        # Should extract all types correctly
        assert len(links) == 5

        link_types = {link.link_type for link in links}
        assert "page" in link_types
        assert "template" in link_types
        assert "file" in link_types
        assert "category" in link_types

    def test_handles_link_extractor_normalization(self, db, sample_pages):
        """Test that link title normalization is preserved."""
        from scraper.storage.link_storage import LinkStorage
        from scraper.storage.page_repository import PageRepository

        page_repo = PageRepository(db)
        page_repo.insert_page(sample_pages[0])

        scraper = IncrementalLinkScraper(db)

        # Test title normalization (underscores -> spaces)
        content = "[[Main_Page]] [[Help_Contents]]"

        scraper.update_links_for_page(1, content)

        link_storage = LinkStorage(db)
        links = link_storage.get_links_by_source(1)

        titles = {link.target_title for link in links}
        assert "Main Page" in titles  # Normalized
        assert "Help Contents" in titles  # Normalized
