"""Comprehensive tests for LinkStorage class.

This module tests the link storage functionality including:
- Initialization
- Adding links (single and batch)
- Querying links (all, by source, by type)
- Deduplication
- Statistics
- Edge cases
"""

import pytest
from scraper.storage.models import Link
from scraper.storage.link_storage import LinkStorage


# ============================================================================
# Test Utilities & Fixtures
# ============================================================================


def create_link(source_page_id: int, target_title: str, link_type: str) -> Link:
    """Helper to create Link objects easily.

    Args:
        source_page_id: ID of source page
        target_title: Title of target page
        link_type: Type of link ('page', 'template', 'file', 'category')

    Returns:
        Link object
    """
    return Link(
        source_page_id=source_page_id, target_title=target_title, link_type=link_type
    )


@pytest.fixture
def storage(db):
    """Fixture providing a fresh LinkStorage instance for each test with database backend."""
    return LinkStorage(db)


@pytest.fixture
def sample_links():
    """Fixture providing a diverse collection of sample links."""
    return [
        # Page links from different sources
        create_link(1, "Main Page", "page"),
        create_link(1, "Help Page", "page"),
        create_link(2, "Main Page", "page"),  # Duplicate target, different source
        create_link(2, "About", "page"),
        # Template links
        create_link(1, "Navbox", "template"),
        create_link(3, "Stub", "template"),
        # File links
        create_link(1, "Logo.png", "file"),
        create_link(4, "Banner.jpg", "file"),
        # Category links
        create_link(1, "Monsters", "category"),
        create_link(5, "Items", "category"),
    ]


@pytest.fixture
def duplicate_links():
    """Fixture providing links with duplicates for deduplication testing."""
    return [
        create_link(1, "Main Page", "page"),
        create_link(1, "Main Page", "page"),  # Exact duplicate
        create_link(1, "Help", "page"),
        create_link(1, "Help", "page"),  # Exact duplicate
        create_link(2, "About", "page"),
    ]


@pytest.fixture
def large_link_set():
    """Fixture providing a large set of links for performance testing."""
    links = []
    # Create 10,000+ unique links
    for page_id in range(1, 101):
        for target_id in range(1, 101):
            links.append(create_link(page_id, f"Page_{target_id}", "page"))
    return links  # 10,000 links total


@pytest.fixture
def unicode_links():
    """Fixture providing links with unicode characters."""
    return [
        create_link(1, "日本語", "page"),
        create_link(1, "Café", "page"),
        create_link(1, "Ñoño", "page"),
        create_link(1, "Привет", "page"),
        create_link(1, "🎮 Gaming", "page"),
    ]


# ============================================================================
# TestLinkStorageInit - Initialization tests
# ============================================================================


class TestLinkStorageInit:
    """Test LinkStorage initialization."""

    def test_initialization_creates_empty_storage(self, storage):
        """Test that initialization creates an empty storage."""
        assert storage is not None
        assert isinstance(storage, LinkStorage)

    def test_initial_count_is_zero(self, storage):
        """Test that initial link count is zero."""
        assert storage.get_link_count() == 0

    def test_initial_stats_show_all_zeros(self, storage):
        """Test that initial stats show zero for all link types."""
        stats = storage.get_stats()
        assert stats["total"] == 0
        assert stats["page"] == 0
        assert stats["template"] == 0
        assert stats["file"] == 0
        assert stats["category"] == 0

    def test_get_links_returns_empty_list(self, storage):
        """Test that get_links returns empty list initially."""
        links = storage.get_links()
        assert links == []
        assert isinstance(links, list)


# ============================================================================
# TestLinkStorageAddLink - Single link addition tests
# ============================================================================


class TestLinkStorageAddLink:
    """Test adding single links."""

    def test_add_single_link_successfully(self, storage):
        """Test adding a single link returns True."""
        link = create_link(1, "Main Page", "page")
        result = storage.add_link(link)
        assert result is True

    def test_add_duplicate_link_returns_false(self, storage):
        """Test adding a duplicate link returns False."""
        link = create_link(1, "Main Page", "page")
        storage.add_link(link)
        result = storage.add_link(link)
        assert result is False

    def test_link_stored_correctly(self, storage):
        """Test that added link is stored and retrievable."""
        link = create_link(1, "Main Page", "page")
        storage.add_link(link)
        links = storage.get_links()
        assert len(links) == 1
        assert links[0] == link

    def test_count_increases_correctly(self, storage):
        """Test that count increases when adding links."""
        link1 = create_link(1, "Main Page", "page")
        link2 = create_link(1, "Help", "page")

        storage.add_link(link1)
        assert storage.get_link_count() == 1

        storage.add_link(link2)
        assert storage.get_link_count() == 2

    def test_count_does_not_increase_for_duplicate(self, storage):
        """Test that count doesn't increase when adding duplicate."""
        link = create_link(1, "Main Page", "page")
        storage.add_link(link)
        initial_count = storage.get_link_count()
        storage.add_link(link)
        assert storage.get_link_count() == initial_count

    def test_add_different_link_types(self, storage):
        """Test adding links of different types."""
        page_link = create_link(1, "Main", "page")
        template_link = create_link(1, "Stub", "template")
        file_link = create_link(1, "Logo.png", "file")
        category_link = create_link(1, "Items", "category")

        assert storage.add_link(page_link) is True
        assert storage.add_link(template_link) is True
        assert storage.add_link(file_link) is True
        assert storage.add_link(category_link) is True
        assert storage.get_link_count() == 4


# ============================================================================
# TestLinkStorageAddLinks - Batch addition tests
# ============================================================================


class TestLinkStorageAddLinks:
    """Test adding multiple links in batch."""

    def test_add_multiple_links_in_batch(self, storage, sample_links):
        """Test adding multiple links returns correct count."""
        added = storage.add_links(sample_links)
        assert added == len(sample_links)
        assert storage.get_link_count() == len(sample_links)

    def test_returns_correct_count_of_new_links(self, storage):
        """Test batch add returns only count of new links."""
        links = [
            create_link(1, "Page1", "page"),
            create_link(1, "Page2", "page"),
            create_link(1, "Page3", "page"),
        ]
        added = storage.add_links(links)
        assert added == 3

    def test_handles_duplicates_correctly(self, storage, duplicate_links):
        """Test batch add handles duplicates correctly."""
        # duplicate_links has 5 links but only 3 unique
        added = storage.add_links(duplicate_links)
        assert added == 3  # Only 3 unique links
        assert storage.get_link_count() == 3

    def test_handles_empty_list(self, storage):
        """Test batch add with empty list."""
        added = storage.add_links([])
        assert added == 0
        assert storage.get_link_count() == 0

    def test_batch_add_after_individual_adds(self, storage):
        """Test batch add after some individual adds."""
        # Add some individual links
        link1 = create_link(1, "Page1", "page")
        storage.add_link(link1)

        # Add batch including duplicate of link1
        batch = [
            link1,  # Duplicate
            create_link(1, "Page2", "page"),
            create_link(1, "Page3", "page"),
        ]
        added = storage.add_links(batch)
        assert added == 2  # Only 2 new links
        assert storage.get_link_count() == 3  # Total 3 unique

    def test_handles_large_batch_efficiently(self, storage, large_link_set):
        """Test batch add with large number of links."""
        added = storage.add_links(large_link_set)
        assert added == len(large_link_set)
        assert storage.get_link_count() == len(large_link_set)


# ============================================================================
# TestLinkStorageGetLinks - Retrieval tests
# ============================================================================


class TestLinkStorageGetLinks:
    """Test retrieving all links."""

    def test_get_all_links_returns_correct_list(self, storage, sample_links):
        """Test get_links returns all stored links."""
        storage.add_links(sample_links)
        retrieved = storage.get_links()
        assert len(retrieved) == len(sample_links)
        # Check all links are present (order may differ)
        assert set(retrieved) == set(sample_links)

    def test_returns_empty_list_when_storage_is_empty(self, storage):
        """Test get_links returns empty list when no links stored."""
        links = storage.get_links()
        assert links == []
        assert isinstance(links, list)

    def test_returned_list_is_independent_copy(self, storage):
        """Test that returned list is a copy (mutations don't affect storage)."""
        link = create_link(1, "Page1", "page")
        storage.add_link(link)

        retrieved = storage.get_links()
        retrieved.append(create_link(2, "Page2", "page"))

        # Storage should still have only 1 link
        assert storage.get_link_count() == 1


# ============================================================================
# TestLinkStorageGetLinksBySource - Query by source page
# ============================================================================


class TestLinkStorageGetLinksBySource:
    """Test retrieving links by source page ID."""

    def test_get_links_by_source_page_id(self, storage, sample_links):
        """Test retrieving links from specific source page."""
        storage.add_links(sample_links)

        # Get links from page 1
        page1_links = storage.get_links_by_source(1)
        expected_count = len([l for l in sample_links if l.source_page_id == 1])
        assert len(page1_links) == expected_count
        assert all(link.source_page_id == 1 for link in page1_links)

    def test_returns_correct_links_for_page(self, storage):
        """Test correct links are returned for each page."""
        links = [
            create_link(1, "PageA", "page"),
            create_link(1, "PageB", "page"),
            create_link(2, "PageC", "page"),
            create_link(3, "PageD", "page"),
        ]
        storage.add_links(links)

        page1_links = storage.get_links_by_source(1)
        assert len(page1_links) == 2
        assert {l.target_title for l in page1_links} == {"PageA", "PageB"}

    def test_returns_empty_list_for_page_with_no_links(self, storage, sample_links):
        """Test empty list returned for page with no links."""
        storage.add_links(sample_links)
        result = storage.get_links_by_source(999)
        assert result == []

    def test_multiple_pages_have_correct_links(self, storage):
        """Test that multiple pages have correct, independent link sets."""
        links = [
            create_link(1, "A", "page"),
            create_link(1, "B", "page"),
            create_link(2, "C", "page"),
            create_link(2, "D", "page"),
            create_link(3, "E", "page"),
        ]
        storage.add_links(links)

        page1 = storage.get_links_by_source(1)
        page2 = storage.get_links_by_source(2)
        page3 = storage.get_links_by_source(3)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1


# ============================================================================
# TestLinkStorageGetLinksByType - Query by link type
# ============================================================================


class TestLinkStorageGetLinksByType:
    """Test retrieving links by type."""

    def test_get_links_by_type_page(self, storage, sample_links):
        """Test retrieving page links."""
        storage.add_links(sample_links)
        page_links = storage.get_links_by_type("page")
        expected_count = len([l for l in sample_links if l.link_type == "page"])
        assert len(page_links) == expected_count
        assert all(link.link_type == "page" for link in page_links)

    def test_get_links_by_type_template(self, storage, sample_links):
        """Test retrieving template links."""
        storage.add_links(sample_links)
        template_links = storage.get_links_by_type("template")
        expected_count = len([l for l in sample_links if l.link_type == "template"])
        assert len(template_links) == expected_count
        assert all(link.link_type == "template" for link in template_links)

    def test_get_links_by_type_file(self, storage, sample_links):
        """Test retrieving file links."""
        storage.add_links(sample_links)
        file_links = storage.get_links_by_type("file")
        expected_count = len([l for l in sample_links if l.link_type == "file"])
        assert len(file_links) == expected_count
        assert all(link.link_type == "file" for link in file_links)

    def test_get_links_by_type_category(self, storage, sample_links):
        """Test retrieving category links."""
        storage.add_links(sample_links)
        category_links = storage.get_links_by_type("category")
        expected_count = len([l for l in sample_links if l.link_type == "category"])
        assert len(category_links) == expected_count
        assert all(link.link_type == "category" for link in category_links)

    def test_returns_empty_list_for_unused_type(self, storage):
        """Test empty list returned for link type with no links."""
        link = create_link(1, "Page1", "page")
        storage.add_link(link)

        # No template links exist
        result = storage.get_links_by_type("template")
        assert result == []

    def test_all_types_represented_correctly(self, storage):
        """Test that all link types are correctly categorized."""
        links = [
            create_link(1, "P1", "page"),
            create_link(1, "P2", "page"),
            create_link(1, "T1", "template"),
            create_link(1, "F1", "file"),
            create_link(1, "C1", "category"),
        ]
        storage.add_links(links)

        assert len(storage.get_links_by_type("page")) == 2
        assert len(storage.get_links_by_type("template")) == 1
        assert len(storage.get_links_by_type("file")) == 1
        assert len(storage.get_links_by_type("category")) == 1


# ============================================================================
# TestLinkStorageGetStats - Statistics tests
# ============================================================================


class TestLinkStorageGetStats:
    """Test statistics functionality."""

    def test_stats_show_correct_totals(self, storage, sample_links):
        """Test stats show correct total count."""
        storage.add_links(sample_links)
        stats = storage.get_stats()
        assert stats["total"] == len(sample_links)

    def test_stats_show_correct_counts_by_type(self, storage, sample_links):
        """Test stats show correct counts for each type."""
        storage.add_links(sample_links)
        stats = storage.get_stats()

        # Count expected values from sample_links
        expected_page = len([l for l in sample_links if l.link_type == "page"])
        expected_template = len([l for l in sample_links if l.link_type == "template"])
        expected_file = len([l for l in sample_links if l.link_type == "file"])
        expected_category = len([l for l in sample_links if l.link_type == "category"])

        assert stats["page"] == expected_page
        assert stats["template"] == expected_template
        assert stats["file"] == expected_file
        assert stats["category"] == expected_category

    def test_stats_update_after_adding_links(self, storage):
        """Test that stats update correctly after adding links."""
        # Initial stats
        stats = storage.get_stats()
        assert stats["total"] == 0

        # Add some links
        storage.add_link(create_link(1, "Page1", "page"))
        stats = storage.get_stats()
        assert stats["total"] == 1
        assert stats["page"] == 1

        # Add more
        storage.add_link(create_link(1, "Template1", "template"))
        stats = storage.get_stats()
        assert stats["total"] == 2
        assert stats["page"] == 1
        assert stats["template"] == 1

    def test_stats_show_zero_for_unused_types(self, storage):
        """Test that unused types show zero in stats."""
        # Only add page links
        storage.add_link(create_link(1, "Page1", "page"))
        stats = storage.get_stats()

        assert stats["page"] == 1
        assert stats["template"] == 0
        assert stats["file"] == 0
        assert stats["category"] == 0

    def test_stats_include_all_required_keys(self, storage):
        """Test that stats dict includes all required keys."""
        stats = storage.get_stats()
        required_keys = {"total", "page", "template", "file", "category"}
        assert set(stats.keys()) == required_keys


# ============================================================================
# TestLinkStorageDeduplication - Deduplication tests
# ============================================================================


class TestLinkStorageDeduplication:
    """Test deduplication functionality."""

    def test_adding_same_link_twice_stores_only_one(self, storage):
        """Test that adding the same link twice results in only one stored."""
        link = create_link(1, "Main Page", "page")
        storage.add_link(link)
        storage.add_link(link)
        assert storage.get_link_count() == 1

    def test_adding_link_with_same_attributes_deduplicates(self, storage):
        """Test that links with identical attributes are deduplicated."""
        link1 = create_link(1, "Main Page", "page")
        link2 = create_link(1, "Main Page", "page")
        storage.add_link(link1)
        storage.add_link(link2)
        assert storage.get_link_count() == 1

    def test_batch_add_with_duplicates_handles_correctly(
        self, storage, duplicate_links
    ):
        """Test batch add correctly deduplicates."""
        added = storage.add_links(duplicate_links)
        # duplicate_links has 5 items but only 3 unique
        assert added == 3
        assert storage.get_link_count() == 3

    def test_mixing_individual_and_batch_adds(self, storage):
        """Test deduplication works across individual and batch adds."""
        link1 = create_link(1, "Page1", "page")
        link2 = create_link(1, "Page2", "page")

        # Add individually
        storage.add_link(link1)

        # Add batch with duplicate
        batch = [link1, link2]
        added = storage.add_links(batch)

        assert added == 1  # Only link2 is new
        assert storage.get_link_count() == 2

    def test_different_source_same_target_not_duplicate(self, storage):
        """Test that links with same target but different source are distinct."""
        link1 = create_link(1, "Page1", "page")
        link2 = create_link(2, "Page1", "page")  # Different source

        storage.add_link(link1)
        storage.add_link(link2)

        assert storage.get_link_count() == 2

    def test_same_source_and_target_different_type_not_duplicate(self, storage):
        """Test that links with same source/target but different type are distinct."""
        link1 = create_link(1, "Name", "page")
        link2 = create_link(1, "Name", "template")  # Different type

        storage.add_link(link1)
        storage.add_link(link2)

        assert storage.get_link_count() == 2


# ============================================================================
# TestLinkStorageClear - Clear functionality tests
# ============================================================================


class TestLinkStorageClear:
    """Test clearing storage."""

    def test_clear_removes_all_links(self, storage, sample_links):
        """Test that clear removes all stored links."""
        storage.add_links(sample_links)
        assert storage.get_link_count() > 0

        storage.clear()
        assert storage.get_link_count() == 0
        assert storage.get_links() == []

    def test_count_becomes_zero_after_clear(self, storage, sample_links):
        """Test that count is zero after clear."""
        storage.add_links(sample_links)
        storage.clear()
        assert storage.get_link_count() == 0

    def test_stats_become_zero_after_clear(self, storage, sample_links):
        """Test that all stats are zero after clear."""
        storage.add_links(sample_links)
        storage.clear()

        stats = storage.get_stats()
        assert stats["total"] == 0
        assert stats["page"] == 0
        assert stats["template"] == 0
        assert stats["file"] == 0
        assert stats["category"] == 0

    def test_can_add_links_after_clearing(self, storage, sample_links):
        """Test that links can be added after clearing."""
        storage.add_links(sample_links)
        storage.clear()

        # Add new links
        new_link = create_link(99, "New Page", "page")
        result = storage.add_link(new_link)

        assert result is True
        assert storage.get_link_count() == 1

    def test_clear_on_empty_storage_is_safe(self, storage):
        """Test that clearing empty storage doesn't cause errors."""
        storage.clear()  # Should not raise
        assert storage.get_link_count() == 0


# ============================================================================
# TestLinkStorageEdgeCases - Edge cases and stress tests
# ============================================================================


class TestLinkStorageEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_number_of_links(self, storage, large_link_set):
        """Test storage handles large number of links (10,000+)."""
        storage.add_links(large_link_set)
        assert storage.get_link_count() == len(large_link_set)

        # Verify retrieval still works
        all_links = storage.get_links()
        assert len(all_links) == len(large_link_set)

    def test_link_with_unicode_characters(self, storage, unicode_links):
        """Test storage handles unicode characters correctly."""
        storage.add_links(unicode_links)
        assert storage.get_link_count() == len(unicode_links)

        # Verify retrieval
        retrieved = storage.get_links()
        assert len(retrieved) == len(unicode_links)

    def test_link_with_very_long_title(self, storage):
        """Test storage handles very long titles."""
        long_title = "A" * 1000  # 1000 character title
        link = create_link(1, long_title, "page")

        result = storage.add_link(link)
        assert result is True
        assert storage.get_link_count() == 1

    def test_empty_storage_queries_dont_error(self, storage):
        """Test that all query methods work on empty storage."""
        # All these should return empty results without errors
        assert storage.get_links() == []
        assert storage.get_links_by_source(1) == []
        assert storage.get_links_by_type("page") == []
        assert storage.get_link_count() == 0

        stats = storage.get_stats()
        assert stats["total"] == 0

    def test_query_by_source_with_large_dataset(self, storage, large_link_set):
        """Test query by source is efficient with large dataset."""
        storage.add_links(large_link_set)

        # Query specific page (should be fast)
        page_links = storage.get_links_by_source(50)
        assert len(page_links) > 0
        assert all(link.source_page_id == 50 for link in page_links)

    def test_query_by_type_with_large_dataset(self, storage, large_link_set):
        """Test query by type is efficient with large dataset."""
        storage.add_links(large_link_set)

        # Query specific type (should be fast)
        page_links = storage.get_links_by_type("page")
        assert len(page_links) == len(large_link_set)  # All are page links
