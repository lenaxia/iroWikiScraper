"""Tests for the Backfiller orchestrator (redirect flag pass)."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from scraper.orchestration.backfill import Backfiller
from scraper.storage.models import Page, Revision
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository


def _revision(page_id, content, rev_id):
    return Revision(
        revision_id=rev_id,
        page_id=page_id,
        parent_id=None,
        timestamp=datetime(2026, 1, 1),
        user="TestUser",
        user_id=1,
        comment="test",
        content=content,
        size=len(content),
        sha1="a" * 40,
        minor=False,
        tags=None,
    )


@pytest.fixture
def backfiller(db, tmp_path):
    """Backfiller over a real temp database with a mocked API client."""
    config = Mock()
    config.storage.data_dir = tmp_path
    api_client = Mock()
    return Backfiller(config, api_client, db, download_dir=tmp_path / "files")


class TestBackfillRedirects:
    """Tests for the redirect-flag backfill step."""

    def test_run_populates_redirect_flags(self, backfiller, db):
        """The redirect step fills flags from stored revisions."""
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(
            Page(page_id=1, namespace=0, title="Alias", is_redirect=False)
        )
        rev_repo.insert_revision(_revision(1, "#REDIRECT [[Target]]", 100))

        result = backfiller.run(
            do_failed_pages=False,
            do_links=False,
            do_files=False,
            do_redirects=True,
            download_files=False,
        )

        assert result.errors == []
        assert result.redirects_found == 1
        assert result.redirect_flags_set == 1
        assert page_repo.get_page_by_id(1).is_redirect is True

    def test_run_can_skip_redirects(self, backfiller, db):
        """--no-redirects leaves flags untouched."""
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(
            Page(page_id=1, namespace=0, title="Alias", is_redirect=False)
        )
        rev_repo.insert_revision(_revision(1, "#REDIRECT [[Target]]", 100))

        result = backfiller.run(
            do_failed_pages=False,
            do_links=False,
            do_files=False,
            do_redirects=False,
            download_files=False,
        )

        assert result.redirects_found == 0
        assert result.redirect_flags_set == 0
        assert page_repo.get_page_by_id(1).is_redirect is False

    def test_counts_cleared_flags(self, backfiller, db):
        """Stale flags are reported as cleared."""
        page_repo = PageRepository(db)
        page_repo.insert_page(
            Page(page_id=1, namespace=0, title="Former", is_redirect=True)
        )
        # No revision: page without revisions is skipped, flag untouched.

        result = backfiller.run(
            do_failed_pages=False,
            do_links=False,
            do_files=False,
            do_redirects=True,
            download_files=False,
        )

        assert result.redirect_flags_cleared == 0
        assert page_repo.get_page_by_id(1).is_redirect is True
