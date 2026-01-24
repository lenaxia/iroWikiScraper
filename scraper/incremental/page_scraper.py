"""Incremental page scraper - main orchestrator for incremental updates."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Set

from scraper.api.client import MediaWikiAPIClient
from scraper.api.recentchanges import RecentChangesClient
from scraper.incremental.change_detector import ChangeDetector
from scraper.incremental.file_scraper import IncrementalFileScraper
from scraper.incremental.link_scraper import IncrementalLinkScraper
from scraper.incremental.models import IncrementalStats, MovedPage
from scraper.incremental.modified_page_detector import ModifiedPageDetector
from scraper.incremental.new_page_detector import NewPageDetector
from scraper.incremental.revision_scraper import IncrementalRevisionScraper
from scraper.incremental.scrape_run_tracker import ScrapeRunTracker
from scraper.scrapers.link_extractor import LinkExtractor
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database
from scraper.storage.models import Page
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository

logger = logging.getLogger(__name__)


class IncrementalPageScraper:
    """
    Main orchestrator for incremental updates.

    Coordinates all incremental scraping operations:
    - Change detection via ChangeDetector
    - New page scraping (full history)
    - Modified page updating (new revisions only)
    - Deleted/moved page handling
    - File downloading
    - Scrape run tracking

    This class is the entry point for incremental updates and manages
    the entire workflow from change detection to completion.

    Example:
        >>> scraper = IncrementalPageScraper(api, db, download_dir)
        >>> stats = scraper.scrape_incremental()
        >>> print(f"Updated {stats.total_pages_affected} pages")
    """

    def __init__(
        self,
        api_client: MediaWikiAPIClient,
        database: Database,
        download_dir: Path,
    ):
        """
        Initialize incremental page scraper.

        Args:
            api_client: MediaWiki API client
            database: Database with initialized schema
            download_dir: Directory for file downloads
        """
        self.api = api_client
        self.db = database
        self.download_dir = Path(download_dir)

        # Initialize all components
        self.run_tracker = ScrapeRunTracker(database)
        self.page_repo = PageRepository(database)
        self.revision_repo = RevisionRepository(database)

        # Change detection
        rc_client = RecentChangesClient(api_client)
        self.change_detector = ChangeDetector(database, rc_client)
        self.modified_detector = ModifiedPageDetector(database)
        self.new_detector = NewPageDetector(database)

        # Incremental scrapers
        self.revision_scraper = IncrementalRevisionScraper(api_client, database)
        self.link_scraper = IncrementalLinkScraper(database)
        self.file_scraper = IncrementalFileScraper(api_client, database, download_dir)

        # Full revision scraper for new pages
        self.full_revision_scraper = RevisionScraper(api_client)
        self.link_extractor = LinkExtractor()

    def scrape_incremental(self) -> IncrementalStats:
        """
        Perform incremental update.

        Main workflow:
        1. Create scrape run record
        2. Detect changes since last scrape
        3. Handle first run (requires full scrape)
        4. Process new pages (full scrape)
        5. Process modified pages (incremental)
        6. Process deleted pages
        7. Process moved pages
        8. Process files
        9. Complete scrape run

        Returns:
            IncrementalStats with summary of changes processed

        Raises:
            Exception: If scrape fails (run marked as failed)

        Example:
            >>> stats = scraper.scrape_incremental()
            >>> print(f"New: {stats.pages_new}, Modified: {stats.pages_modified}")
        """
        stats = IncrementalStats(start_time=datetime.utcnow())

        # Create scrape run
        run_id = self.run_tracker.create_scrape_run("incremental")
        logger.info(f"Started incremental scrape run {run_id}")

        try:
            # Detect changes
            change_set = self.change_detector.detect_changes()

            if change_set.requires_full_scrape:
                logger.info("First run detected - requires full scrape")
                # Mark this run as failed/skipped and recommend full scrape
                self.run_tracker.fail_scrape_run(
                    run_id, "First run requires full scrape"
                )
                raise FirstRunRequiresFullScrapeError(
                    "No previous scrape found. Run full scrape first."
                )

            logger.info(
                f"Detected {change_set.total_changes} changes: "
                f"new={len(change_set.new_page_ids)}, "
                f"modified={len(change_set.modified_page_ids)}, "
                f"deleted={len(change_set.deleted_page_ids)}, "
                f"moved={len(change_set.moved_pages)}"
            )

            # Process all change types
            stats.pages_new = self._process_new_pages(change_set.new_page_ids)
            modified_stats = self._process_modified_pages(change_set.modified_page_ids)
            stats.pages_modified = modified_stats[0]
            stats.revisions_added = modified_stats[1]
            stats.pages_deleted = self._process_deleted_pages(
                change_set.deleted_page_ids
            )
            stats.pages_moved = self._process_moved_pages(change_set.moved_pages)

            # Process files
            file_changes = self.file_scraper.detect_file_changes()
            stats.files_downloaded = self.file_scraper.download_new_files(file_changes)

            # Complete run
            stats.end_time = datetime.utcnow()
            self.run_tracker.complete_scrape_run(run_id, stats.to_dict())

            logger.info(
                f"Incremental scrape completed: {stats.total_pages_affected} pages, "
                f"{stats.revisions_added} revisions, {stats.files_downloaded} files"
            )

            return stats

        except Exception as e:
            logger.error(f"Incremental scrape failed: {e}")
            self.run_tracker.fail_scrape_run(run_id, str(e))
            raise

    def _process_new_pages(self, page_ids: Set[int]) -> int:
        """
        Process new pages with full history scrape.

        Args:
            page_ids: Set of new page IDs

        Returns:
            Number of pages successfully processed
        """
        if not page_ids:
            return 0

        logger.info(f"Processing {len(page_ids)} new pages")

        # Verify pages are genuinely new
        verified = self.new_detector.verify_new_pages(list(page_ids))

        processed = 0
        for page_id in verified:
            try:
                # Scrape full revision history for new page
                revisions = self.full_revision_scraper.fetch_revisions(page_id)

                if not revisions:
                    logger.warning(f"No revisions found for page {page_id}")
                    continue

                # Create page from first revision metadata
                revisions[0]
                page = Page(
                    page_id=page_id,
                    namespace=0,  # TODO: Get from API
                    title=f"Page_{page_id}",  # TODO: Get from API
                    is_redirect=False,  # TODO: Detect redirects
                )
                self.page_repo.insert_page(page)

                # Insert all revisions
                for rev in revisions:
                    self.revision_repo.insert_revision(rev)

                # Extract and store links from latest revision
                latest_content = revisions[-1].content
                self.link_extractor.extract_links(page_id, latest_content)
                # TODO: Store links

                processed += 1
                logger.debug(
                    f"Scraped new page {page_id} with {len(revisions)} revisions"
                )
            except Exception as e:
                logger.error(f"Failed to scrape new page {page_id}: {e}")

        logger.info(f"Processed {processed}/{len(page_ids)} new pages")
        return processed

    def _process_modified_pages(self, page_ids: Set[int]) -> tuple[int, int]:
        """
        Process modified pages with incremental revision updates.

        Args:
            page_ids: Set of modified page IDs

        Returns:
            Tuple of (pages_processed, revisions_added)
        """
        if not page_ids:
            return (0, 0)

        logger.info(f"Processing {len(page_ids)} modified pages")

        # Get update info for all modified pages
        update_infos = self.modified_detector.get_batch_update_info(list(page_ids))

        pages_processed = 0
        total_revisions = 0

        for info in update_infos:
            try:
                # Fetch new revisions
                new_revisions = self.revision_scraper.fetch_new_revisions(info)

                if not new_revisions:
                    logger.debug(f"No new revisions for page {info.page_id}")
                    continue

                # Insert new revisions
                inserted = self.revision_scraper.insert_new_revisions(
                    info.page_id, new_revisions
                )
                total_revisions += inserted

                # Update links from latest revision
                latest_content = new_revisions[-1].content
                self.link_scraper.update_links_for_page(info.page_id, latest_content)

                pages_processed += 1
                logger.debug(f"Updated page {info.page_id}: {inserted} new revisions")

            except Exception as e:
                logger.error(f"Failed to update page {info.page_id}: {e}")

        logger.info(
            f"Processed {pages_processed} modified pages, "
            f"added {total_revisions} revisions"
        )
        return (pages_processed, total_revisions)

    def _process_deleted_pages(self, page_ids: Set[int]) -> int:
        """
        Mark pages as deleted.

        Note: Does not delete from database, just marks as deleted.
        Historical data is preserved.

        Args:
            page_ids: Set of deleted page IDs

        Returns:
            Number of pages marked as deleted
        """
        if not page_ids:
            return 0

        logger.info(f"Processing {len(page_ids)} deleted pages")

        processed = 0
        for page_id in page_ids:
            try:
                # TODO: Add is_deleted column to pages table in future
                # For now, just log the deletion
                logger.info(f"Page {page_id} was deleted")
                processed += 1
            except Exception as e:
                logger.error(f"Failed to mark page {page_id} as deleted: {e}")

        return processed

    def _process_moved_pages(self, moved_pages: list[MovedPage]) -> int:
        """
        Update titles for moved/renamed pages.

        Args:
            moved_pages: List of MovedPage objects

        Returns:
            Number of pages updated
        """
        if not moved_pages:
            return 0

        logger.info(f"Processing {len(moved_pages)} moved pages")

        processed = 0
        for moved in moved_pages:
            try:
                # Update page title in database
                page = self.page_repo.get_page_by_id(moved.page_id)
                if page:
                    # Create updated page with new title
                    updated_page = Page(
                        page_id=page.page_id,
                        namespace=moved.namespace,
                        title=moved.new_title,
                        is_redirect=page.is_redirect,
                    )
                    self.page_repo.update_page(updated_page)
                    logger.info(
                        f"Updated page {moved.page_id} title: "
                        f"{moved.old_title} -> {moved.new_title}"
                    )
                    processed += 1
            except Exception as e:
                logger.error(f"Failed to update moved page {moved.page_id}: {e}")

        return processed


class FirstRunRequiresFullScrapeError(Exception):
    """Raised when incremental scrape attempted on empty database."""
