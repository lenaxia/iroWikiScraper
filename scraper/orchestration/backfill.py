"""Backfill orchestrator for completing an existing archive.

The initial :class:`~scraper.orchestration.full_scraper.FullScraper` runs only
captured pages and revisions. This module fills in the remaining data on an
*existing* database without re-scraping revision history:

1. Retry pages that previously failed (present in ``pages`` but with zero
   revisions), e.g. the historical sha1 / foreign-key bugs.
2. Extract and store internal links from the latest stored revision of each
   page (pure local computation, no API calls).
3. Discover file (media) metadata via the ``allimages`` API and download the
   file content to disk with SHA1 verification.
4. Record the operation in the ``scrape_runs`` table.

This is intentionally idempotent: re-running it will not duplicate links,
re-download unchanged files, or double-count revisions.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, List, Optional

from scraper.api.client import MediaWikiAPIClient
from scraper.config import Config
from scraper.incremental.scrape_run_tracker import ScrapeRunTracker
from scraper.scrapers.file_scraper import FileDiscovery, FileDownloader
from scraper.scrapers.link_extractor import LinkExtractor
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database
from scraper.storage.file_repository import FileRepository
from scraper.storage.revision_repository import RevisionRepository

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, int, int], None]]


@dataclass
class BackfillResult:
    """Summary of a backfill operation."""

    failed_pages_retried: int = 0
    failed_pages_fixed: int = 0
    revisions_added: int = 0
    links_added: int = 0
    pages_linked: int = 0
    files_stored: int = 0
    files_downloaded: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class Backfiller:
    """Fills files, links, run metadata and retries failed pages on a DB."""

    def __init__(
        self,
        config: Config,
        api_client: MediaWikiAPIClient,
        database: Database,
        *,
        download_dir: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.api = api_client
        self.db = database
        self.conn = database.get_connection()
        self.download_dir = Path(
            download_dir
            if download_dir is not None
            else config.storage.data_dir / "files"
        )

        self.revision_scraper = RevisionScraper(api_client)
        self.revision_repo = RevisionRepository(database)
        self.link_extractor = LinkExtractor()
        self.file_discovery = FileDiscovery(api_client)
        self.file_downloader = FileDownloader(self.download_dir)
        self.file_repo = FileRepository(database)
        self.run_tracker = ScrapeRunTracker(database)

    def run(
        self,
        *,
        do_failed_pages: bool = True,
        do_links: bool = True,
        do_files: bool = True,
        download_files: bool = True,
        progress_callback: ProgressCallback = None,
    ) -> BackfillResult:
        """Execute the backfill.

        Args:
            do_failed_pages: Retry pages that have no revisions
            do_links: Rebuild the links table from stored revisions
            do_files: Discover + store file metadata
            download_files: Download file content (implies do_files)
            progress_callback: Optional callback(stage, current, total)
        """
        result = BackfillResult(start_time=datetime.now(UTC))
        do_files = do_files or download_files

        run_id: Optional[int] = None
        try:
            run_id = self.run_tracker.create_scrape_run("full")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not create scrape_runs record: {e}")

        try:
            if do_failed_pages:
                self._retry_failed_pages(result, progress_callback)
            if do_links:
                self._backfill_links(result, progress_callback)
            if do_files:
                self._backfill_files(result, download_files, progress_callback)
        except Exception as e:
            logger.error(f"Backfill failed: {e}", exc_info=True)
            result.errors.append(str(e))

        result.end_time = datetime.now(UTC)

        if run_id is not None:
            try:
                self.run_tracker.complete_scrape_run(
                    run_id,
                    {
                        "pages_new": result.failed_pages_fixed,
                        "revisions_added": result.revisions_added,
                        "files_downloaded": result.files_downloaded
                        + result.files_skipped,
                    },
                )
            except Exception as e:  # pragma: no cover
                logger.warning(f"Could not finalize scrape_runs record: {e}")

        return result

    # ------------------------------------------------------------------ #
    # Failed pages
    # ------------------------------------------------------------------ #
    def _find_pages_without_revisions(self) -> List[int]:
        cursor = self.conn.execute("""
            SELECT p.page_id
            FROM pages p
            LEFT JOIN revisions r ON r.page_id = p.page_id
            WHERE r.revision_id IS NULL
            ORDER BY p.page_id
            """)
        return [row[0] for row in cursor.fetchall()]

    def _retry_failed_pages(
        self, result: BackfillResult, progress_callback: ProgressCallback
    ) -> None:
        page_ids = self._find_pages_without_revisions()
        result.failed_pages_retried = len(page_ids)
        if not page_ids:
            logger.info("No pages missing revisions; nothing to retry")
            return

        logger.info(f"Retrying {len(page_ids)} page(s) with no revisions")
        for i, page_id in enumerate(page_ids, 1):
            if progress_callback:
                progress_callback("retry", i, len(page_ids))
            try:
                revisions = self.revision_scraper.fetch_revisions(page_id)
                if not revisions:
                    logger.warning(f"Page {page_id}: still no revisions returned")
                    continue
                self.revision_repo.insert_revisions_batch(revisions)
                result.revisions_added += len(revisions)
                result.failed_pages_fixed += 1
                logger.info(f"Recovered page {page_id}: {len(revisions)} revisions")
            except Exception as e:
                msg = f"Failed to recover page {page_id}: {e}"
                logger.error(msg)
                result.errors.append(msg)

    # ------------------------------------------------------------------ #
    # Links
    # ------------------------------------------------------------------ #
    def _latest_revision_contents(self):
        """Yield (page_id, content) for the latest revision of every page."""
        cursor = self.conn.execute("""
            SELECT r.page_id, r.content
            FROM revisions r
            JOIN (
                SELECT page_id, MAX(timestamp) AS max_ts
                FROM revisions
                GROUP BY page_id
            ) latest
              ON latest.page_id = r.page_id
             AND latest.max_ts = r.timestamp
            """)
        seen = set()
        for page_id, content in cursor:
            # Guard against ties on identical timestamps.
            if page_id in seen:
                continue
            seen.add(page_id)
            yield page_id, content or ""

    def _backfill_links(
        self, result: BackfillResult, progress_callback: ProgressCallback
    ) -> None:
        logger.info("Backfilling links from stored revisions")

        rows = list(self._latest_revision_contents())
        total = len(rows)

        # Rebuild the links table from scratch for a consistent snapshot.
        self.conn.execute("DELETE FROM links")
        self.conn.commit()

        batch: List[tuple] = []
        for i, (page_id, content) in enumerate(rows, 1):
            try:
                links = self.link_extractor.extract_links(page_id, content)
                for link in links:
                    batch.append(
                        (link.source_page_id, link.target_title, link.link_type)
                    )
                result.pages_linked += 1
            except Exception as e:
                logger.warning(f"Link extraction failed for page {page_id}: {e}")

            if len(batch) >= 5000:
                self._flush_links(batch, result)
                batch = []
            if progress_callback and (i % 250 == 0 or i == total):
                progress_callback("links", i, total)

        if batch:
            self._flush_links(batch, result)

        logger.info(
            f"Links backfill complete: {result.links_added} links from "
            f"{result.pages_linked} pages"
        )

    def _flush_links(self, batch: List[tuple], result: BackfillResult) -> None:
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO links (source_page_id, target_title, link_type)
            VALUES (?, ?, ?)
            """,
            batch,
        )
        self.conn.commit()
        result.links_added += len(batch)

    # ------------------------------------------------------------------ #
    # Files
    # ------------------------------------------------------------------ #
    def _backfill_files(
        self,
        result: BackfillResult,
        download_files: bool,
        progress_callback: ProgressCallback,
    ) -> None:
        logger.info("Discovering files via allimages API")
        try:
            files = self.file_discovery.discover_files()
        except Exception as e:
            msg = f"File discovery failed: {e}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)
            return

        if not files:
            logger.info("No files discovered")
            return

        try:
            self.file_repo.insert_files_batch(files)
            result.files_stored = len(files)
            logger.info(f"Stored metadata for {len(files)} files")
        except Exception as e:
            msg = f"Failed to store file metadata: {e}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)

        if not download_files:
            return

        def _dl_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("files", current, total)

        stats = self.file_downloader.download_files(
            files, progress_callback=_dl_progress
        )
        result.files_downloaded = stats.downloaded
        result.files_skipped = stats.skipped
        result.files_failed = stats.failed
        if stats.failed:
            result.errors.append(f"{stats.failed} file(s) failed to download")
        logger.info(
            f"File download complete: {stats.downloaded} downloaded, "
            f"{stats.skipped} skipped, {stats.failed} failed"
        )
