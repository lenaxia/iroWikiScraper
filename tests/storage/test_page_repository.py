"""
Test Page CRUD operations (Story 07).

Tests the PageRepository class for:
- Insert single page
- Batch insert
- Get by ID
- Get by title
- List pages with pagination
- Update page
- Delete page
- Count pages
- Upsert/duplicate handling
"""

import pytest
from scraper.storage.models import Page
from scraper.storage.page_repository import PageRepository


class TestPageInsertion:
    """Test page insertion operations."""

    def test_insert_single_page(self, db):
        """Test inserting single page."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="TestPage", is_redirect=False)

        page_id = repo.insert_page(page)

        assert page_id > 0

        # Verify inserted
        loaded = repo.get_page_by_id(page_id)
        assert loaded is not None
        assert loaded.title == "TestPage"
        assert loaded.namespace == 0
        assert loaded.is_redirect == False

    def test_insert_redirect_page(self, db):
        """Test inserting redirect page."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="RedirectPage", is_redirect=True)

        page_id = repo.insert_page(page)

        loaded = repo.get_page_by_id(page_id)
        assert loaded is not None
        assert loaded.is_redirect == True

    def test_insert_pages_batch(self, db):
        """Test batch insert performance."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=i, namespace=0, title=f"Page{i}", is_redirect=False)
            for i in range(1, 101)
        ]

        repo.insert_pages_batch(pages)

        count = repo.count_pages()
        assert count == 100

    def test_insert_pages_batch_large(self, db):
        """Test batch insert with 1000 pages."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=i, namespace=0, title=f"Page{i:04d}", is_redirect=False)
            for i in range(1, 1001)
        ]

        repo.insert_pages_batch(pages)

        count = repo.count_pages()
        assert count == 1000

    def test_insert_pages_batch_empty(self, db):
        """Test batch insert with empty list."""
        repo = PageRepository(db)

        # Should not raise error
        repo.insert_pages_batch([])

        count = repo.count_pages()
        assert count == 0

    def test_insert_pages_different_namespaces(self, db):
        """Test inserting pages in different namespaces."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=1, namespace=0, title="Main Page", is_redirect=False),
            Page(page_id=2, namespace=1, title="Talk:Main Page", is_redirect=False),
            Page(page_id=3, namespace=6, title="File:Example.png", is_redirect=False),
            Page(page_id=4, namespace=14, title="Category:Test", is_redirect=False),
        ]

        repo.insert_pages_batch(pages)

        # Verify all inserted
        assert repo.count_pages(namespace=0) == 1
        assert repo.count_pages(namespace=1) == 1
        assert repo.count_pages(namespace=6) == 1
        assert repo.count_pages(namespace=14) == 1


class TestPageRetrieval:
    """Test page retrieval operations."""

    def test_get_page_by_id_exists(self, db, sample_pages):
        """Test get page by ID when it exists."""
        repo = PageRepository(db)
        repo.insert_pages_batch(sample_pages)

        loaded = repo.get_page_by_id(1)
        assert loaded is not None
        assert loaded.page_id == 1
        assert loaded.title == "Main Page"

    def test_get_page_by_id_not_exists(self, db):
        """Test get page by ID when it doesn't exist."""
        repo = PageRepository(db)

        loaded = repo.get_page_by_id(999)
        assert loaded is None

    def test_get_page_by_title(self, db, sample_pages):
        """Test lookup by title."""
        repo = PageRepository(db)
        repo.insert_pages_batch(sample_pages)

        loaded = repo.get_page_by_title(0, "Main Page")
        assert loaded is not None
        assert loaded.title == "Main Page"
        assert loaded.namespace == 0

    def test_get_page_by_title_not_exists(self, db):
        """Test get page by title when it doesn't exist."""
        repo = PageRepository(db)

        loaded = repo.get_page_by_title(0, "NonexistentPage")
        assert loaded is None

    def test_get_page_by_title_wrong_namespace(self, db, sample_pages):
        """Test get page by title with wrong namespace."""
        repo = PageRepository(db)
        repo.insert_pages_batch(sample_pages)

        # Main Page is in namespace 0, not 1
        loaded = repo.get_page_by_title(1, "Main Page")
        assert loaded is None


class TestPageListing:
    """Test page listing and pagination."""

    def test_list_pages_default(self, db, sample_pages):
        """Test list pages with default parameters."""
        repo = PageRepository(db)
        repo.insert_pages_batch(sample_pages)

        pages = repo.list_pages()
        assert len(pages) <= 100  # Default limit
        assert len(pages) == 5  # We have 5 sample pages

    def test_list_pages_with_limit(self, db):
        """Test list pages with limit."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=i, namespace=0, title=f"Page{i:03d}", is_redirect=False)
            for i in range(1, 51)
        ]
        repo.insert_pages_batch(pages)

        result = repo.list_pages(limit=20)
        assert len(result) == 20

    def test_list_pages_pagination(self, db):
        """Test pagination."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=i, namespace=0, title=f"Page{i:03d}", is_redirect=False)
            for i in range(1, 51)
        ]
        repo.insert_pages_batch(pages)

        # First page
        page1 = repo.list_pages(limit=20, offset=0)
        assert len(page1) == 20

        # Second page
        page2 = repo.list_pages(limit=20, offset=20)
        assert len(page2) == 20

        # Third page (partial)
        page3 = repo.list_pages(limit=20, offset=40)
        assert len(page3) == 10

        # No overlap
        titles1 = {p.title for p in page1}
        titles2 = {p.title for p in page2}
        titles3 = {p.title for p in page3}
        assert len(titles1 & titles2) == 0
        assert len(titles1 & titles3) == 0
        assert len(titles2 & titles3) == 0

    def test_list_pages_by_namespace(self, db):
        """Test list pages filtered by namespace."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page2", is_redirect=False),
            Page(page_id=3, namespace=1, title="Talk:Page1", is_redirect=False),
            Page(page_id=4, namespace=1, title="Talk:Page2", is_redirect=False),
            Page(page_id=5, namespace=6, title="File:Example.png", is_redirect=False),
        ]
        repo.insert_pages_batch(pages)

        # List namespace 0
        ns0_pages = repo.list_pages(namespace=0)
        assert len(ns0_pages) == 2
        assert all(p.namespace == 0 for p in ns0_pages)

        # List namespace 1
        ns1_pages = repo.list_pages(namespace=1)
        assert len(ns1_pages) == 2
        assert all(p.namespace == 1 for p in ns1_pages)

        # List namespace 6
        ns6_pages = repo.list_pages(namespace=6)
        assert len(ns6_pages) == 1
        assert all(p.namespace == 6 for p in ns6_pages)

    def test_list_pages_empty_database(self, db):
        """Test list pages on empty database."""
        repo = PageRepository(db)

        pages = repo.list_pages()
        assert len(pages) == 0


class TestPageUpdate:
    """Test page update operations."""

    def test_update_page(self, db):
        """Test updating existing page."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="Original", is_redirect=False)

        page_id = repo.insert_page(page)

        # Update the page
        updated_page = Page(
            page_id=page_id, namespace=0, title="Updated", is_redirect=True
        )
        repo.update_page(updated_page)

        # Verify update
        loaded = repo.get_page_by_id(page_id)
        assert loaded.title == "Updated"
        assert loaded.is_redirect == True

    def test_update_page_without_id(self, db):
        """Test update page without page_id raises error."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="Test", is_redirect=False)

        # Manually create a page-like object without page_id
        class PageWithoutId:
            namespace = 0
            title = "Test"
            is_redirect = False

        page_without_id = PageWithoutId()

        with pytest.raises(ValueError):
            repo.update_page(page_without_id)


class TestPageDeletion:
    """Test page deletion operations."""

    def test_delete_page(self, db):
        """Test deleting page by ID."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="ToDelete", is_redirect=False)

        page_id = repo.insert_page(page)

        # Verify it exists
        assert repo.get_page_by_id(page_id) is not None

        # Delete it
        repo.delete_page(page_id)

        # Verify deleted
        assert repo.get_page_by_id(page_id) is None

    def test_delete_nonexistent_page(self, db):
        """Test deleting nonexistent page doesn't raise error."""
        repo = PageRepository(db)

        # Should not raise error
        repo.delete_page(999)


class TestPageCount:
    """Test page counting operations."""

    def test_count_pages_empty(self, db):
        """Test count on empty database."""
        repo = PageRepository(db)

        count = repo.count_pages()
        assert count == 0

    def test_count_pages_all(self, db, sample_pages):
        """Test count all pages."""
        repo = PageRepository(db)
        repo.insert_pages_batch(sample_pages)

        count = repo.count_pages()
        assert count == 5

    def test_count_pages_by_namespace(self, db):
        """Test count pages by namespace."""
        repo = PageRepository(db)
        pages = [
            Page(page_id=1, namespace=0, title="Page1", is_redirect=False),
            Page(page_id=2, namespace=0, title="Page2", is_redirect=False),
            Page(page_id=3, namespace=0, title="Page3", is_redirect=False),
            Page(page_id=4, namespace=1, title="Talk:Page1", is_redirect=False),
            Page(page_id=5, namespace=1, title="Talk:Page2", is_redirect=False),
        ]
        repo.insert_pages_batch(pages)

        assert repo.count_pages(namespace=0) == 3
        assert repo.count_pages(namespace=1) == 2
        assert repo.count_pages(namespace=2) == 0
        assert repo.count_pages() == 5


class TestPageUpsert:
    """Test upsert/duplicate handling."""

    def test_upsert_idempotency(self, db):
        """Test that inserting same page twice works (upsert)."""
        repo = PageRepository(db)
        page = Page(page_id=1, namespace=0, title="TestPage", is_redirect=False)

        repo.insert_pages_batch([page])
        repo.insert_pages_batch([page])  # Should not error

        count = repo.count_pages()
        assert count == 1  # Only one copy

    def test_upsert_updates_data(self, db):
        """Test that upsert updates existing data."""
        repo = PageRepository(db)

        # Insert initial page
        page1 = Page(page_id=1, namespace=0, title="TestPage", is_redirect=False)
        repo.insert_pages_batch([page1])

        # Insert again with same namespace/title but different is_redirect (upsert)
        page2 = Page(page_id=1, namespace=0, title="TestPage", is_redirect=True)
        repo.insert_pages_batch([page2])

        # Should have updated is_redirect
        loaded = repo.get_page_by_title(0, "TestPage")
        assert loaded.is_redirect == True

        # Still only one page
        count = repo.count_pages()
        assert count == 1


class TestPageDataConversion:
    """Test Page dataclass <-> database row conversion."""

    def test_roundtrip_conversion(self, db):
        """Test that data survives roundtrip conversion."""
        repo = PageRepository(db)
        original = Page(
            page_id=123,  # This will be ignored - DB uses AUTOINCREMENT
            namespace=6,
            title="File:Example.png",
            is_redirect=True,
        )

        page_id = repo.insert_page(original)
        loaded = repo.get_page_by_id(page_id)

        # Check all fields except page_id (which is auto-generated)
        assert loaded.namespace == original.namespace
        assert loaded.title == original.title
        assert loaded.is_redirect == original.is_redirect

    def test_boolean_conversion(self, db):
        """Test that is_redirect boolean is stored and retrieved correctly."""
        repo = PageRepository(db)

        # Test False
        page_false = Page(
            page_id=1, namespace=0, title="NotRedirect", is_redirect=False
        )
        repo.insert_page(page_false)
        loaded_false = repo.get_page_by_id(1)
        assert loaded_false.is_redirect == False
        assert isinstance(loaded_false.is_redirect, bool)

        # Test True
        page_true = Page(page_id=2, namespace=0, title="IsRedirect", is_redirect=True)
        repo.insert_page(page_true)
        loaded_true = repo.get_page_by_id(2)
        assert loaded_true.is_redirect == True
        assert isinstance(loaded_true.is_redirect, bool)
