"""Tests for redirect detection and pages.is_redirect backfill."""

from datetime import datetime, timedelta

import pytest

from scraper.storage.models import Page, Revision
from scraper.storage.page_repository import PageRepository
from scraper.storage.redirects import (
    RedirectBackfillResult,
    backfill_redirect_flags,
    detect_redirect,
)
from scraper.storage.revision_repository import RevisionRepository


def make_revision(
    revision_id,
    page_id,
    content,
    timestamp=None,
):
    """Build a minimal valid Revision for storage tests."""
    return Revision(
        revision_id=revision_id,
        page_id=page_id,
        parent_id=None,
        timestamp=timestamp or datetime(2026, 1, 1),
        user="TestUser",
        user_id=1,
        comment="test",
        content=content,
        size=len(content),
        sha1="a" * 40,
        minor=False,
        tags=None,
    )


def seed_page(db, page_id, content, is_redirect=False, namespace=0):
    """Insert a page plus a single revision with the given content."""
    page_repo = PageRepository(db)
    rev_repo = RevisionRepository(db)
    page_repo.insert_page(
        Page(
            page_id=page_id,
            namespace=namespace,
            title=f"Page_{page_id}",
            is_redirect=is_redirect,
        )
    )
    rev_repo.insert_revision(
        make_revision(revision_id=page_id * 100, page_id=page_id, content=content)
    )


class TestDetectRedirect:
    """Test the content-based redirect detector."""

    @pytest.mark.parametrize(
        "content",
        [
            "#REDIRECT [[Target]]",
            "#redirect [[Target]]",
            "#Redirect [[Target]]",
            "#REDIRECT:[[Target]]",
            "#REDIRECT: [[Target]]",
            "#REDIRECT   [[Target]]",
            "  #REDIRECT [[Target]]",
            "#REDIRECT [[Target|label]]",
            "#REDIRECT [[Target#Section]]",
            "#WEITERLEITUNG [[Ziel]]",
            "#weiterleitung [[Ziel]]",
        ],
    )
    def test_detects_redirect_variants(self, content):
        """All recognized redirect forms are detected."""
        assert detect_redirect(content) is True

    @pytest.mark.parametrize(
        "content",
        [
            "",
            "Normal page content.",
            "#REDIRECT",
            "#REDIRECT [[ ]]",
            "Some text\n#REDIRECT [[Target]]",
            "REDIRECT [[Target]]",
            "##REDIRECT [[Target]]",
            "#REDIRECTIONS [[Target]]",
            "See also [[Target]]",
        ],
    )
    def test_rejects_non_redirects(self, content):
        """Non-redirect content is not flagged."""
        assert detect_redirect(content) is False

    def test_requires_non_empty_target(self):
        """Magic word without a link target is not a redirect."""
        assert detect_redirect("#REDIRECT no link here") is False


class TestBackfillRedirectFlags:
    """Test the storage-layer backfill pass."""

    def test_sets_flag_for_redirect_content(self, db):
        """Redirect pages get the flag set."""
        seed_page(db, 1, "#REDIRECT [[Target]]")
        seed_page(db, 2, "Normal content")

        result = backfill_redirect_flags(db)

        assert result.pages_scanned == 2
        assert result.redirects_found == 1
        assert result.flags_set == 1
        assert result.flags_cleared == 0

        repo = PageRepository(db)
        assert repo.get_page_by_id(1).is_redirect is True
        assert repo.get_page_by_id(2).is_redirect is False

    def test_clears_stale_flag(self, db):
        """A page stored as redirect but no longer redirect gets cleared."""
        seed_page(db, 1, "Rewritten as a normal page", is_redirect=True)

        result = backfill_redirect_flags(db)

        assert result.redirects_found == 0
        assert result.flags_cleared == 1
        assert PageRepository(db).get_page_by_id(1).is_redirect is False

    def test_uses_latest_revision_only(self, db):
        """A page that became a redirect in a later revision is a redirect."""
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False)
        )
        base = datetime(2026, 1, 1)
        rev_repo.insert_revision(
            make_revision(100, 1, "Original content", timestamp=base)
        )
        rev_repo.insert_revision(
            make_revision(
                101,
                1,
                "#REDIRECT [[New_Home]]",
                timestamp=base + timedelta(days=1),
            )
        )

        result = backfill_redirect_flags(db)

        assert result.redirects_found == 1
        assert page_repo.get_page_by_id(1).is_redirect is True

    def test_idempotent(self, db):
        """A second backfill run performs no writes."""
        seed_page(db, 1, "#REDIRECT [[Target]]")

        first = backfill_redirect_flags(db)
        second = backfill_redirect_flags(db)

        assert first.flags_updated == 1
        assert second.flags_updated == 0
        assert second.redirects_found == 1

    def test_pages_without_revisions_counted_not_written(self, db):
        """Pages lacking revisions are reported but left untouched."""
        page_repo = PageRepository(db)
        page_repo.insert_page(
            Page(page_id=7, namespace=0, title="Lonely", is_redirect=False)
        )
        seed_page(db, 1, "#REDIRECT [[Target]]")

        result = backfill_redirect_flags(db)

        assert result.pages_scanned == 1
        assert result.pages_missing_revisions == 1
        assert page_repo.get_page_by_id(7).is_redirect is False

    def test_progress_callback_invoked(self, db):
        """Progress is reported while scanning."""
        seed_page(db, 1, "#REDIRECT [[Target]]")

        calls = []
        backfill_redirect_flags(
            db,
            progress_callback=lambda stage, cur, tot: calls.append((stage, cur, tot)),
        )

        assert calls
        assert calls[-1] == ("redirects", 1, 1)

    def test_result_dataclass_defaults(self):
        """RedirectBackfillResult defaults are sane."""
        result = RedirectBackfillResult()
        assert result.flags_updated == 0
        assert result.pages_scanned == 0

    def test_localized_magic_word_detected(self, db):
        """The German magic word is honored like #REDIRECT."""
        seed_page(db, 1, "#WEITERLEITUNG [[Ziel]]")

        result = backfill_redirect_flags(db)

        assert result.redirects_found == 1
        assert PageRepository(db).get_page_by_id(1).is_redirect is True


class TestBackfillRealWorldParity:
    """Cross-check detection against the semantics used by the Go SDK."""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("#REDIRECT [[Poring]]", True),
            ("#redirect [[Poring|Porings]]", True),
            ("#REDIRECT: [[Drops]]", True),
            ("\n#REDIRECT [[Drops]]", True),  # leading whitespace incl. newline
            ("#REDIRECT [[ ]]", False),
            ("{{Item | name = Poring}}", False),
        ],
    )
    def test_parity_cases(self, content, expected):
        """Detection matches the SDK's redirectTargetRe behavior classes."""
        assert detect_redirect(content) is expected


class TestTimestampTiebreak:
    """Deterministic latest-revision pick on identical timestamps."""

    def _seed_tied_revisions(self, db, first_content, second_content):
        """Insert one page with two revisions sharing a timestamp.

        The lower revision_id holds first_content; the higher (later)
        revision_id holds second_content.
        """
        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)
        page_repo.insert_page(
            Page(page_id=1, namespace=0, title="Page_1", is_redirect=False)
        )
        tied = datetime(2026, 5, 5, 12, 0, 0)
        rev_repo.insert_revision(make_revision(100, 1, first_content, timestamp=tied))
        rev_repo.insert_revision(make_revision(101, 1, second_content, timestamp=tied))

    def test_highest_revision_id_wins_on_tie(self, db):
        """Tied timestamps pick the highest revision_id: redirect wins."""
        self._seed_tied_revisions(
            db, first_content="Normal", second_content="#REDIRECT [[Target]]"
        )

        result = backfill_redirect_flags(db)

        assert result.redirects_found == 1
        assert PageRepository(db).get_page_by_id(1).is_redirect is True

    def test_highest_revision_id_wins_on_tie_reverse(self, db):
        """Tied timestamps pick the highest revision_id: redirect dropped."""
        self._seed_tied_revisions(
            db, first_content="#REDIRECT [[Target]]", second_content="Normal"
        )

        result = backfill_redirect_flags(db)

        assert result.redirects_found == 0
        assert PageRepository(db).get_page_by_id(1).is_redirect is False
