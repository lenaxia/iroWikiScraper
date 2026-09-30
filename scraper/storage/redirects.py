"""Redirect detection and backfill for the pages table.

The ``is_redirect`` column of the ``pages`` table is derived data: a page is
a redirect when the *latest* revision's wikitext begins with the MediaWiki
redirect magic word (``#REDIRECT`` or the localized ``#WEITERLEITUNG``)
followed by a link to the target page.

The ``allpages`` discovery API does not report the redirect marker on this
wiki, so the flag cannot be trusted from discovery alone. This module owns
the content-based detection shared by:

- the full scraper (flag set while storing revisions),
- the incremental scraper (new and modified pages),
- the ``backfill`` command (repairs archives scraped before the flag was
  populated).

Detection semantics intentionally mirror the Go SDK's
``sdk/irowiki/redirect.go`` (which keeps its own content sniffing as
defense in depth for old archives).
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from scraper.storage.database import Database

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, int, int], None]]

# Matches the redirect magic word at the start of page content, optionally
# preceded by whitespace and followed by an optional colon, then a wikilink
# whose target is non-empty. Mirrors redirectTargetRe in the Go SDK, plus
# the localized #WEITERLEITUNG magic word.
_REDIRECT_RE = re.compile(r"(?i)^\s*#(?:REDIRECT|WEITERLEITUNG)\s*:?\s*\[\[([^\]|]*)")


def detect_redirect(content: str) -> bool:
    """Return True when wikitext content begins with a redirect.

    A page counts as a redirect only if the magic word is followed by a
    wikilink with a non-empty target (MediaWiki requires the link for the
    redirect to be effective).

    Args:
        content: Wikitext content of a revision

    Returns:
        True if the content starts with a redirect directive
    """
    if not content:
        return False
    match = _REDIRECT_RE.match(content)
    if match is None:
        return False
    return match.group(1).strip() != ""


@dataclass
class RedirectBackfillResult:
    """Summary of a redirect flag backfill pass."""

    pages_scanned: int = 0
    redirects_found: int = 0
    flags_set: int = 0
    flags_cleared: int = 0
    pages_missing_revisions: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def flags_updated(self) -> int:
        """Total number of rows changed (set plus cleared)."""
        return self.flags_set + self.flags_cleared


def _latest_revision_rows(conn: sqlite3.Connection):
    """Yield (page_id, latest_content, stored_flag) per page, streaming.

    Only the latest revision of each page participates. The latest
    revision is the one with the newest timestamp; ties on identical
    timestamps are broken deterministically by highest revision_id.
    Rows are yielded lazily from the cursor so the wikitext of all
    pages is never held in memory at once (large archives hold
    gigabytes of content in revisions).
    """
    cursor = conn.execute("""
        SELECT r.page_id, r.content, p.is_redirect
        FROM revisions r
        JOIN pages p ON p.page_id = r.page_id
        JOIN (
            SELECT page_id, MAX(timestamp) AS max_ts
            FROM revisions
            GROUP BY page_id
        ) latest
          ON latest.page_id = r.page_id
         AND latest.max_ts = r.timestamp
        ORDER BY r.page_id, r.revision_id DESC
    """)
    seen = set()
    for page_id, content, is_redirect in cursor:
        if page_id in seen:
            # Timestamp tie: rows are ordered revision_id DESC, so the
            # first row seen for a page is the deterministic latest.
            continue
        seen.add(page_id)
        yield page_id, content or "", int(is_redirect or 0)


def backfill_redirect_flags(
    database: Database,
    progress_callback: ProgressCallback = None,
) -> RedirectBackfillResult:
    """Populate ``pages.is_redirect`` from stored revision content.

    Streams the latest revision of every page (content is never fully
    materialized in memory), recomputes the redirect flag and updates
    only rows whose stored flag differs. Pages without any stored
    revision are counted but left untouched. Idempotent: a second run
    performs no writes.

    Args:
        database: Database instance with the archive schema initialized
        progress_callback: Optional callback(stage, current, total)

    Returns:
        RedirectBackfillResult with scan and update counters
    """
    result = RedirectBackfillResult(start_time=datetime.utcnow())
    conn = database.get_connection()

    total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    total_with_revisions = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT page_id FROM revisions)"
    ).fetchone()[0]

    updates: List[Tuple[int, int]] = []
    scanned = 0
    # The updates list holds only (flag, page_id) tuples; wikitext is
    # consumed one row at a time from the cursor.
    for page_id, content, stored_flag in _latest_revision_rows(conn):
        scanned += 1
        detected = 1 if detect_redirect(content) else 0
        if detected:
            result.redirects_found += 1
        if detected != stored_flag:
            updates.append((detected, page_id))
            if detected:
                result.flags_set += 1
            else:
                result.flags_cleared += 1
        if progress_callback and (
            scanned % 500 == 0 or scanned == total_with_revisions
        ):
            progress_callback("redirects", scanned, total_with_revisions)

    result.pages_scanned = scanned
    result.pages_missing_revisions = max(total_pages - scanned, 0)

    if updates:
        now = datetime.utcnow().isoformat()
        conn.executemany(
            """
            UPDATE pages
            SET is_redirect = ?, updated_at = ?
            WHERE page_id = ?
        """,
            [(flag, now, page_id) for flag, page_id in updates],
        )
        conn.commit()

    result.end_time = datetime.utcnow()
    logger.info(
        f"Redirect backfill complete: {result.redirects_found} redirects "
        f"among {result.pages_scanned} pages with revisions "
        f"({result.flags_set} flags set, {result.flags_cleared} cleared)"
    )
    return result
