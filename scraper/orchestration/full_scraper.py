"""Full scraper orchestrator for initial baseline scraping.

This module provides the FullScraper class which orchestrates a complete
scrape of the wiki, coordinating between page discovery, revision scraping,
and storage operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, List, Optional

from scraper.api.client import MediaWikiAPIClient
from scraper.config import Config
from scraper.orchestration.checkpoint import CheckpointManager
from scraper.orchestration.retry import retry_with_backoff
from scraper.scrapers.file_scraper import FileDiscovery, FileDownloader
from scraper.scrapers.link_extractor import LinkExtractor
from scraper.scrapers.page_scraper import PageDiscovery
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database
from scraper.storage.file_repository import FileRepository
from scraper.storage.link_storage import LinkStorage
from scraper.storage.models import Page
from scraper.storage.page_repository import PageRepository
from scraper.storage.redirects import detect_redirect
from scraper.storage.revision_repository import RevisionRepository

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a full scrape operation.

    Attributes:
        pages_count: Number of pages discovered
        revisions_count: Number of revisions scraped
        files_count: Number of file metadata records stored
        files_downloaded: Number of media files downloaded to disk
        links_count: Number of internal links extracted and stored
        namespaces_scraped: List of namespace IDs that were scraped
        start_time: When the scrape started
        end_time: When the scrape completed
        errors: List of error messages encountered
        failed_pages: List of page IDs that failed to scrape
    """

    pages_count: int = 0
    revisions_count: int = 0
    files_count: int = 0
    files_downloaded: int = 0
    links_count: int = 0
    namespaces_scraped: List[int] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    failed_pages: List[int] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success(self) -> bool:
        """Check if scrape was successful (no errors)."""
        return len(self.errors) == 0


class FullScraper:
    """Orchestrates a complete scrape of the wiki.

    This class coordinates all components needed for a full baseline scrape:
    - Page discovery across namespaces
    - Revision history scraping for each page
    - Storage of pages and revisions to database
    - Progress tracking and error handling

    Example:
        >>> config = Config()
        >>> api_client = MediaWikiAPIClient(
        ...     base_url=config.wiki.base_url,
        ...     user_agent=config.scraper.user_agent,
        ...     timeout=config.scraper.timeout,
        ...     max_retries=config.scraper.max_retries,
        ... )
        >>> database = Database(str(config.storage.database_file))
        >>> database.initialize_schema()
        >>> scraper = FullScraper(config, api_client, database)
        >>> result = scraper.scrape(namespaces=[0, 4])
        >>> print(f"Scraped {result.pages_count} pages")
    """

    def __init__(
        self,
        config: Config,
        api_client: MediaWikiAPIClient,
        database: Database,
        checkpoint_manager: Optional[CheckpointManager] = None,
        *,
        scrape_links: bool = True,
        scrape_files: bool = True,
        download_files: bool = True,
        download_dir: Optional[Path] = None,
    ):
        """Initialize full scraper.

        Args:
            config: Configuration object
            api_client: MediaWiki API client
            database: Database instance with initialized schema
            checkpoint_manager: Optional checkpoint manager for resume capability
            scrape_links: Extract and store internal links from page content
            scrape_files: Discover and store file (media) metadata
            download_files: Download file (media) content to disk (implies
                scrape_files); metadata is always stored when files are scraped
            download_dir: Directory for downloaded media files (defaults to
                ``<data_dir>/files``)
        """
        self.config = config
        self.api = api_client
        self.db = database
        self.checkpoint = checkpoint_manager

        self.scrape_links = scrape_links
        self.scrape_files = scrape_files or download_files
        self.download_files = download_files
        self.download_dir = self._resolve_download_dir(config, download_dir)

        # Initialize components
        self.page_discovery = PageDiscovery(api_client)
        self.revision_scraper = RevisionScraper(api_client)
        self.page_repo = PageRepository(database)
        self.revision_repo = RevisionRepository(database)

        # File + link + run-metadata components
        self.file_discovery = FileDiscovery(api_client)
        self.file_downloader = FileDownloader(self.download_dir)
        self.file_repo = FileRepository(database)
        self.link_extractor = LinkExtractor()
        self.link_storage = LinkStorage(database)

        # ScrapeRunTracker records a row in the scrape_runs table. Imported
        # lazily to avoid a heavy import chain at module load time.
        from scraper.incremental.scrape_run_tracker import ScrapeRunTracker

        self.run_tracker = ScrapeRunTracker(database)

    @staticmethod
    def _resolve_download_dir(config: Config, download_dir: Optional[Path]) -> Path:
        """Resolve the media download directory.

        Falls back to ``data/files`` when the configured ``data_dir`` is not a
        usable path (for example when a test passes a Mock config object).
        """
        if download_dir is not None:
            return Path(download_dir)
        try:
            return Path(config.storage.data_dir) / "files"
        except (TypeError, AttributeError):
            return Path("data") / "files"

    def scrape(
        self,
        namespaces: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        resume: bool = False,
    ) -> ScrapeResult:
        """Perform a full scrape of the wiki.

        Args:
            namespaces: List of namespace IDs to scrape (default: all common namespaces)
            progress_callback: Optional callback function(stage, current, total) for progress
            resume: Whether to resume from checkpoint

        Returns:
            ScrapeResult with statistics and status

        Example:
            >>> def progress(stage, current, total):
            ...     print(f"{stage}: {current}/{total}")
            >>> result = scraper.scrape(namespaces=[0], progress_callback=progress)
        """
        result = ScrapeResult(start_time=datetime.now(UTC))

        # Use default namespaces if none specified
        if namespaces is None:
            namespaces = PageDiscovery.DEFAULT_NAMESPACES

        result.namespaces_scraped = namespaces

        # Handle resume logic
        resumed = False
        if resume and self.checkpoint and self.checkpoint.exists():
            checkpoint_data = self.checkpoint.get_checkpoint()
            if checkpoint_data and self.checkpoint.is_compatible(namespaces):
                logger.info("Resuming from existing checkpoint")
                resumed = True
                # Filter out completed namespaces
                completed_ns = self.checkpoint.get_completed_namespaces()
                namespaces = [ns for ns in namespaces if ns not in completed_ns]
                logger.info(
                    f"Skipping {len(completed_ns)} completed namespaces: {completed_ns}"
                )
            else:
                logger.warning("Checkpoint incompatible, starting fresh")
                if self.checkpoint:
                    self.checkpoint.clear()

        # Initialize checkpoint if not resuming
        if not resumed and self.checkpoint:
            self.checkpoint.start_scrape(
                namespaces=namespaces,
                rate_limit=self.config.scraper.rate_limit,
            )

        logger.info(f"Starting full scrape of namespaces: {namespaces}")

        # Record this scrape run in the scrape_runs table.
        run_id: Optional[int] = None
        try:
            run_id = self.run_tracker.create_scrape_run("full")
        except Exception as e:  # pragma: no cover - metadata must never abort a scrape
            logger.warning(f"Could not create scrape_runs record: {e}")

        try:
            # Phase 1: Discover all pages
            all_pages = self._discover_pages(namespaces, progress_callback, result)
            result.pages_count = len(all_pages)

            logger.info(
                f"Discovered {result.pages_count} pages across {len(namespaces)} namespaces"
            )

            # Phase 2: Scrape revisions for each page (and extract links from the
            # latest revision content, reusing what we already fetched).
            result.revisions_count = self._scrape_revisions(
                all_pages, progress_callback, result
            )

            logger.info(
                f"Scraped {result.revisions_count} revisions for {result.pages_count} pages"
            )

            if self.scrape_links:
                logger.info(f"Extracted {result.links_count} internal links")

            # Phase 3: Discover file metadata and (optionally) download content.
            if self.scrape_files:
                self._scrape_files(progress_callback, result)

            # Clear checkpoint on successful completion
            if self.checkpoint and result.success:
                logger.info("Scrape completed successfully, clearing checkpoint")
                self.checkpoint.clear()

        except Exception as e:
            error_msg = f"Full scrape failed: {e}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            # Keep checkpoint on failure for resume

        result.end_time = datetime.now(UTC)

        # Finalize scrape_runs record.
        if run_id is not None:
            try:
                if result.errors and result.pages_count == 0:
                    self.run_tracker.fail_scrape_run(
                        run_id, "; ".join(result.errors[:3])
                    )
                else:
                    self.run_tracker.complete_scrape_run(
                        run_id,
                        {
                            "pages_new": result.pages_count,
                            "revisions_added": result.revisions_count,
                            "files_downloaded": result.files_downloaded,
                        },
                    )
            except Exception as e:  # pragma: no cover
                logger.warning(f"Could not finalize scrape_runs record: {e}")

        logger.info(
            f"Full scrape completed in {result.duration:.1f}s: "
            f"{result.pages_count} pages, {result.revisions_count} revisions, "
            f"{result.files_count} files, {result.links_count} links, "
            f"{len(result.failed_pages)} failures"
        )

        return result

    def _discover_pages(
        self,
        namespaces: List[int],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        result: Optional[ScrapeResult] = None,
    ) -> List[Page]:
        """Discover all pages across namespaces.

        Args:
            namespaces: List of namespace IDs to discover
            progress_callback: Optional progress callback
            result: Optional ScrapeResult to record namespace-level errors

        Returns:
            List of discovered Page objects
        """
        all_pages = []

        for i, namespace in enumerate(namespaces):
            # Skip if namespace already completed (resume logic)
            if self.checkpoint and self.checkpoint.is_namespace_complete(namespace):
                logger.info(f"Skipping completed namespace: {namespace}")
                continue

            if progress_callback:
                progress_callback("discover", i + 1, len(namespaces))

            # Set current namespace in checkpoint
            if self.checkpoint:
                self.checkpoint.set_current_namespace(namespace)

            try:
                pages = self.page_discovery.discover_namespace(namespace)

                # Store pages in database immediately (batch insert)
                self.page_repo.insert_pages_batch(pages)

                all_pages.extend(pages)

                logger.info(
                    f"Namespace {namespace}: discovered and stored {len(pages)} pages "
                    f"(Total: {len(all_pages)})"
                )

                # Mark namespace as complete in checkpoint
                if self.checkpoint:
                    self.checkpoint.mark_namespace_complete(namespace)

            except Exception as e:
                error_msg = f"Failed to discover namespace {namespace}: {e}"
                logger.error(error_msg, exc_info=True)

                # Record error in result if provided
                if result:
                    result.errors.append(error_msg)

                # Continue with other namespaces
                continue

        return all_pages

    def _scrape_revisions(
        self,
        pages: List[Page],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        result: Optional[ScrapeResult] = None,
    ) -> int:
        """Scrape revision history for all pages.

        Args:
            pages: List of Page objects to scrape
            progress_callback: Optional progress callback
            result: ScrapeResult to update with errors

        Returns:
            Total number of revisions scraped
        """
        total_revisions = 0
        total_pages = len(pages)

        for i, page in enumerate(pages):
            # Skip if page already completed (resume logic)
            if self.checkpoint and self.checkpoint.is_page_complete(page.page_id):
                logger.debug(f"Skipping completed page: {page.page_id} ({page.title})")
                continue

            if progress_callback:
                progress_callback("scrape", i + 1, total_pages)

            try:
                # Fetch all revisions for this page with retry logic
                def fetch_operation():
                    return self.revision_scraper.fetch_revisions(page.page_id)

                # Use config max_retries if available and is an integer, otherwise default to 3
                try:
                    max_retries = self.config.scraper.max_retries
                    if not isinstance(max_retries, int):
                        max_retries = 3
                except (AttributeError, TypeError):
                    max_retries = 3

                revisions = retry_with_backoff(
                    fetch_operation,
                    max_retries=max_retries,
                )

                if not revisions:
                    logger.warning(
                        f"No revisions found for page {page.page_id} ({page.title})"
                    )
                    continue

                # Store revisions in database (batch insert)
                self.revision_repo.insert_revisions_batch(revisions)

                total_revisions += len(revisions)

                # Refresh the redirect flag from the current content.
                # Discovery's allpages response does not carry the redirect
                # marker, so the authoritative signal is the latest
                # revision's wikitext (#REDIRECT / #WEITERLEITUNG prefix).
                try:
                    detected = detect_redirect(revisions[-1].content)
                    if detected != page.is_redirect:
                        self.page_repo.update_redirect_flag(page.page_id, detected)
                        page.is_redirect = detected
                except Exception as e:
                    logger.warning(
                        f"Could not update redirect flag for page "
                        f"{page.page_id}: {e}"
                    )

                # Extract and store internal links from the latest revision's
                # content. Revisions are chronological (oldest first), so the
                # last element is the current page content. No extra API calls.
                if self.scrape_links and result is not None:
                    try:
                        latest_content = revisions[-1].content
                        links = self.link_extractor.extract_links(
                            page.page_id, latest_content
                        )
                        if links:
                            self.link_storage.add_links(links)
                            result.links_count += len(links)
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract links for page {page.page_id}: {e}"
                        )

                # Mark page complete in checkpoint
                if self.checkpoint:
                    self.checkpoint.mark_page_complete(page.page_id)

                # Log progress every 10 pages
                if (i + 1) % 10 == 0 or (i + 1) == total_pages:
                    logger.info(
                        f"Progress: {i + 1}/{total_pages} pages, "
                        f"{total_revisions} revisions"
                    )

                    # Update checkpoint statistics periodically
                    if self.checkpoint:
                        self.checkpoint.update_statistics(
                            pages_scraped=i + 1,
                            revisions_scraped=total_revisions,
                            errors=len(result.errors) if result else 0,
                        )

            except Exception as e:
                error_msg = f"Failed to scrape page {page.page_id} ({page.title}): {e}"
                logger.error(error_msg)

                if result:
                    result.errors.append(error_msg)
                    result.failed_pages.append(page.page_id)

                # Continue with other pages
                continue

        return total_revisions

    def _scrape_files(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        result: Optional[ScrapeResult] = None,
    ) -> None:
        """Discover file metadata and optionally download file content.

        Uses the MediaWiki ``allimages`` API to enumerate every uploaded file,
        persists the metadata to the ``files`` table, and (when enabled)
        downloads each file to disk with SHA1 verification.

        Args:
            progress_callback: Optional progress callback(stage, current, total)
            result: ScrapeResult to update with counts/errors
        """
        logger.info("Starting file discovery")

        try:
            files = self.file_discovery.discover_files()
        except Exception as e:
            error_msg = f"Failed to discover files: {e}"
            logger.error(error_msg, exc_info=True)
            if result is not None:
                result.errors.append(error_msg)
            return

        if not files:
            logger.info("No files discovered")
            return

        # Persist metadata for every file (idempotent via INSERT OR REPLACE).
        try:
            self.file_repo.insert_files_batch(files)
            if result is not None:
                result.files_count = len(files)
            logger.info(f"Stored metadata for {len(files)} files")
        except Exception as e:
            error_msg = f"Failed to store file metadata: {e}"
            logger.error(error_msg, exc_info=True)
            if result is not None:
                result.errors.append(error_msg)

        if not self.download_files:
            return

        logger.info(f"Downloading {len(files)} files to {self.download_dir}")

        def _download_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("files", current, total)

        try:
            stats = self.file_downloader.download_files(
                files, progress_callback=_download_progress
            )
            if result is not None:
                result.files_downloaded = stats.downloaded + stats.skipped
            logger.info(
                f"File download complete: {stats.downloaded} downloaded, "
                f"{stats.skipped} skipped, {stats.failed} failed"
            )
            if stats.failed and result is not None:
                result.errors.append(f"{stats.failed} file(s) failed to download")
        except Exception as e:
            error_msg = f"File download phase failed: {e}"
            logger.error(error_msg, exc_info=True)
            if result is not None:
                result.errors.append(error_msg)
