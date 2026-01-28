"""Full scraper orchestrator for initial baseline scraping.

This module provides the FullScraper class which orchestrates a complete
scrape of the wiki, coordinating between page discovery, revision scraping,
and storage operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, List, Optional

from scraper.api.client import MediaWikiAPIClient
from scraper.config import Config
from scraper.orchestration.checkpoint import CheckpointManager
from scraper.orchestration.retry import retry_with_backoff
from scraper.scrapers.page_scraper import PageDiscovery
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database
from scraper.storage.models import Page
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a full scrape operation.

    Attributes:
        pages_count: Number of pages discovered
        revisions_count: Number of revisions scraped
        namespaces_scraped: List of namespace IDs that were scraped
        start_time: When the scrape started
        end_time: When the scrape completed
        errors: List of error messages encountered
        failed_pages: List of page IDs that failed to scrape
    """

    pages_count: int = 0
    revisions_count: int = 0
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
    ):
        """Initialize full scraper.

        Args:
            config: Configuration object
            api_client: MediaWiki API client
            database: Database instance with initialized schema
            checkpoint_manager: Optional checkpoint manager for resume capability
        """
        self.config = config
        self.api = api_client
        self.db = database
        self.checkpoint = checkpoint_manager

        # Initialize components
        self.page_discovery = PageDiscovery(api_client)
        self.revision_scraper = RevisionScraper(api_client)
        self.page_repo = PageRepository(database)
        self.revision_repo = RevisionRepository(database)

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

        try:
            # Phase 1: Discover all pages
            all_pages = self._discover_pages(namespaces, progress_callback, result)
            result.pages_count = len(all_pages)

            logger.info(
                f"Discovered {result.pages_count} pages across {len(namespaces)} namespaces"
            )

            # Phase 2: Scrape revisions for each page
            result.revisions_count = self._scrape_revisions(
                all_pages, progress_callback, result
            )

            logger.info(
                f"Scraped {result.revisions_count} revisions for {result.pages_count} pages"
            )

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

        logger.info(
            f"Full scrape completed in {result.duration:.1f}s: "
            f"{result.pages_count} pages, {result.revisions_count} revisions, "
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
