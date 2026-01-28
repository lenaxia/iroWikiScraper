"""Command implementations for scraper CLI."""

import json
import logging
import sys
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict

from scraper.api.client import MediaWikiAPIClient
from scraper.api.rate_limiter import RateLimiter
from scraper.config import Config, ConfigError
from scraper.incremental.models import IncrementalStats
from scraper.incremental.page_scraper import (
    FirstRunRequiresFullScrapeError,
    IncrementalPageScraper,
)
from scraper.orchestration.checkpoint import CheckpointManager
from scraper.orchestration.full_scraper import FullScraper, ScrapeResult
from scraper.storage.database import Database

logger = logging.getLogger(__name__)

# Namespace name mappings
NAMESPACE_NAMES = {
    0: "Main",
    1: "Talk",
    2: "User",
    3: "User talk",
    4: "Project",
    5: "Project talk",
    6: "File",
    7: "File talk",
    8: "MediaWiki",
    9: "MediaWiki talk",
    10: "Template",
    11: "Template talk",
    12: "Help",
    13: "Help talk",
    14: "Category",
    15: "Category talk",
}


def _setup_logging(log_level: str) -> None:
    """Configure logging for CLI.

    Args:
        log_level: Logging level string (DEBUG, INFO, etc.)
    """
    level = getattr(logging, log_level)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Ensure root logger level is set (basicConfig may not update if already configured)
    logging.getLogger().setLevel(level)


def _load_config(args: Namespace) -> Config:
    """Load configuration from file or use defaults.

    Args:
        args: Parsed command-line arguments

    Returns:
        Config instance

    Raises:
        SystemExit: If configuration loading or validation fails
    """
    # Load from file or use defaults
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        try:
            config = Config.from_yaml(args.config, validate=False)
        except ConfigError as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
    else:
        logger.info("Using default configuration")
        config = Config()

    # Override config with CLI arguments
    if hasattr(args, "rate_limit"):
        config.scraper.rate_limit = args.rate_limit

    if args.database:
        config.storage.database_file = args.database

    config.logging.level = args.log_level

    # Validate merged configuration
    try:
        config.validate()
    except ConfigError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    return config


def _create_database(config: Config) -> Database:
    """Create and initialize database.

    Args:
        config: Configuration instance

    Returns:
        Initialized Database instance
    """
    db_path = config.storage.database_file

    # Create parent directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Opening database: {db_path}")
    database = Database(str(db_path))
    database.initialize_schema()

    return database


def _print_progress(stage: str, current: int, total: int) -> None:
    """Print progress update.

    Args:
        stage: Stage name (discover, scrape, etc.)
        current: Current item number
        total: Total items
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"[{stage}] {current}/{total} ({percentage:.1f}%)", flush=True)


def _format_number(num: int) -> str:
    """Format number with thousand separators.

    Args:
        num: Number to format

    Returns:
        Formatted string with commas (e.g., "1,234")
    """
    return f"{num:,}"


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "245.3s (4m 5s)")
    """
    minutes = int(seconds // 60)
    secs = seconds % 60

    if minutes > 0:
        return f"{seconds:.1f}s ({minutes}m {int(secs)}s)"
    return f"{seconds:.1f}s"


def _prompt_resume(checkpoint_manager: CheckpointManager) -> bool:
    """Prompt user to resume from checkpoint.

    Args:
        checkpoint_manager: Checkpoint manager with existing checkpoint

    Returns:
        True if user wants to resume, False otherwise
    """
    checkpoint = checkpoint_manager.get_checkpoint()
    if not checkpoint:
        return False

    # Display checkpoint info
    print(f"\nFound existing scrape checkpoint from {checkpoint.started_at}")
    print(f"\nProgress:")

    completed_ns = checkpoint.progress.get("namespaces_completed", [])
    current_ns = checkpoint.progress.get("current_namespace", 0)
    pages_scraped = checkpoint.statistics.get("pages_scraped", 0)

    if completed_ns:
        print(f"  Namespaces completed: {completed_ns}")
    print(f"  Current namespace: {current_ns}")
    print(f"  Pages scraped: {_format_number(pages_scraped)}")

    # Get user input
    response = input("\nDo you want to resume this scrape? [y/N]: ")
    return response.lower() in ["y", "yes"]


def _get_namespace_stats(database: Database) -> Dict[int, Dict[str, int]]:
    """Get statistics breakdown by namespace from database.

    Args:
        database: Database instance

    Returns:
        Dict mapping namespace ID to {"pages": count, "revisions": count}
    """
    conn = database.get_connection()

    # Query pages and revisions per namespace
    query = """
        SELECT 
            p.namespace,
            COUNT(DISTINCT p.page_id) as page_count,
            COUNT(r.revision_id) as revision_count
        FROM pages p
        LEFT JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.namespace
        ORDER BY p.namespace
    """

    cursor = conn.execute(query)
    stats = {}

    for row in cursor:
        ns_id, page_count, revision_count = row
        stats[ns_id] = {
            "pages": page_count or 0,
            "revisions": revision_count or 0,
        }

    return stats


def _print_full_scrape_statistics(result: ScrapeResult, database: Database) -> None:
    """Print statistics for full scrape in human-readable format.

    Args:
        result: Scrape result with statistics
        database: Database for querying namespace stats
    """
    print(f"\n{'=' * 60}")
    print("FULL SCRAPE COMPLETE")
    print(f"{'=' * 60}")

    # Basic statistics
    print(f"Pages scraped:     {_format_number(result.pages_count)}")
    print(f"Revisions scraped: {_format_number(result.revisions_count)}")

    if result.pages_count > 0:
        avg_revs = result.revisions_count / result.pages_count
        print(f"Avg revisions:     {avg_revs:.1f} per page")

    print(f"Duration:          {_format_duration(result.duration)}")

    if result.duration > 0:
        rate = result.pages_count / result.duration
        print(f"Rate:              {rate:.1f} pages/sec")

    # Namespace breakdown
    namespace_stats = _get_namespace_stats(database)
    if namespace_stats:
        print(f"\nBreakdown by namespace:")
        for ns_id in sorted(namespace_stats.keys()):
            stats = namespace_stats[ns_id]
            ns_name = NAMESPACE_NAMES.get(ns_id, str(ns_id))
            pages = _format_number(stats["pages"])
            revisions = _format_number(stats["revisions"])
            print(
                f"  {ns_id:2d} ({ns_name:12s}): {pages:>8s} pages    {revisions:>8s} revisions"
            )

    # Error reporting
    if result.failed_pages:
        failed_count = len(result.failed_pages)
        percentage = (
            (failed_count / result.pages_count * 100) if result.pages_count > 0 else 0
        )
        print(f"\nFailed pages:      {failed_count} ({percentage:.1f}%)")

        # Show first 5 page IDs
        sample_ids = result.failed_pages[:5]
        ids_str = ", ".join(str(id) for id in sample_ids)
        if failed_count > 5:
            print(f"  Sample IDs: {ids_str}, and {failed_count - 5} more")
        else:
            print(f"  IDs: {ids_str}")

    if result.errors:
        error_count = len(result.errors)
        print(f"\nErrors (first 3 of {error_count}):")
        for error in result.errors[:3]:
            print(f"  - {error}")
        if error_count > 3:
            print(f"  ... and {error_count - 3} more errors")

    print(f"{'=' * 60}")


def _print_incremental_scrape_statistics(stats: IncrementalStats) -> None:
    """Print statistics for incremental scrape in human-readable format.

    Args:
        stats: Incremental scrape statistics
    """
    print(f"\n{'=' * 60}")
    print("INCREMENTAL SCRAPE COMPLETE")
    print(f"{'=' * 60}")

    # Changes detected
    print("Changes detected:")
    print(f"  New pages:         {_format_number(stats.pages_new)}")
    print(f"  Modified pages:    {_format_number(stats.pages_modified)}")
    print(f"  Deleted pages:     {_format_number(stats.pages_deleted)}")
    print(f"  Moved pages:       {_format_number(stats.pages_moved)}")

    # Data updated
    print(f"\nData updated:")
    print(f"  Revisions added:   {_format_number(stats.revisions_added)}")
    print(f"  Files downloaded:  {_format_number(stats.files_downloaded)}")

    # Summary
    total_affected = stats.total_pages_affected
    duration = stats.duration.total_seconds()

    print(f"\nTotal affected:    {_format_number(total_affected)} pages")
    print(f"Duration:          {_format_duration(duration)}")

    if duration > 0 and total_affected > 0:
        rate = total_affected / duration
        print(f"Rate:              {rate:.1f} pages/sec")

    print(f"{'=' * 60}")


def _output_full_scrape_json(result: ScrapeResult, database: Database) -> None:
    """Output full scrape statistics as JSON.

    Args:
        result: Scrape result with statistics
        database: Database for querying namespace stats
    """
    namespace_stats = _get_namespace_stats(database)

    data = {
        "scrape_type": "full",
        "success": result.success,
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_seconds": result.duration,
        "statistics": {
            "pages_count": result.pages_count,
            "revisions_count": result.revisions_count,
            "average_revisions_per_page": (
                result.revisions_count / result.pages_count
                if result.pages_count > 0
                else 0
            ),
            "rate_pages_per_second": (
                result.pages_count / result.duration if result.duration > 0 else 0
            ),
            "namespaces": {
                str(ns_id): stats for ns_id, stats in namespace_stats.items()
            },
        },
        "errors": {
            "count": len(result.errors),
            "failed_pages": result.failed_pages,
            "messages": result.errors,
        },
    }

    print(json.dumps(data, indent=2))


def _output_incremental_scrape_json(stats: IncrementalStats) -> None:
    """Output incremental scrape statistics as JSON.

    Args:
        stats: Incremental scrape statistics
    """
    duration = stats.duration.total_seconds()
    total_affected = stats.total_pages_affected

    data = {
        "scrape_type": "incremental",
        "success": True,
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_seconds": duration,
        "statistics": {
            "pages_new": stats.pages_new,
            "pages_modified": stats.pages_modified,
            "pages_deleted": stats.pages_deleted,
            "pages_moved": stats.pages_moved,
            "revisions_added": stats.revisions_added,
            "files_downloaded": stats.files_downloaded,
            "total_pages_affected": total_affected,
            "rate_pages_per_second": (total_affected / duration if duration > 0 else 0),
        },
    }

    print(json.dumps(data, indent=2))


def full_scrape_command(args: Namespace) -> int:
    """Execute full scrape command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Setup
        _setup_logging(args.log_level)
        config = _load_config(args)

        # Check for existing data if not forcing
        if not args.force:
            db_path = config.storage.database_file
            if db_path.exists():
                # Check if database has data
                db = Database(str(db_path))
                conn = db.get_connection()
                cursor = conn.execute("SELECT COUNT(*) FROM pages")
                page_count = cursor.fetchone()[0]

                if page_count > 0:
                    logger.error(
                        f"Database already contains {page_count} pages. "
                        f"Use --force to scrape anyway."
                    )
                    return 1

        # Check for JSON output format
        output_json = hasattr(args, "format") and args.format == "json"

        # Dry run check - handle before creating database
        if args.dry_run:
            print("DRY RUN MODE: Will discover pages but not scrape revisions")

            # Create only components needed for discovery (no database)
            rate_limiter = RateLimiter(requests_per_second=config.scraper.rate_limit)
            api_client = MediaWikiAPIClient(
                base_url=config.wiki.base_url,
                user_agent=config.scraper.user_agent,
                timeout=config.scraper.timeout,
                max_retries=config.scraper.max_retries,
                rate_limiter=rate_limiter,
            )

            # Determine namespaces
            namespaces = args.namespace if args.namespace else None

            # Only discover pages
            from scraper.scrapers.page_scraper import PageDiscovery

            discovery = PageDiscovery(api_client)
            pages = discovery.discover_all_pages(namespaces)

            print(f"\nDRY RUN COMPLETE")
            print(f"Would scrape {_format_number(len(pages))} pages")

            # Show breakdown by namespace
            from collections import Counter

            ns_counts = Counter(p.namespace for p in pages)
            print("\nBreakdown by namespace:")
            for ns in sorted(ns_counts.keys()):
                ns_name = NAMESPACE_NAMES.get(ns, str(ns))
                print(
                    f"  {ns:2d} ({ns_name:12s}): {_format_number(ns_counts[ns])} pages"
                )

            # Estimate API calls and duration
            estimated_calls = len(pages)  # Discovery + revision calls per page
            estimated_duration = estimated_calls / config.scraper.rate_limit

            print(f"\nEstimated API calls: {_format_number(estimated_calls)}")
            print(
                f"Estimated duration: {_format_duration(estimated_duration)} at {config.scraper.rate_limit} req/sec"
            )

            print("\nNOTE: Actual duration will be longer due to revision scraping")
            print("      and may vary based on page complexity.")

            return 0

        # Handle --clean flag
        if hasattr(args, "clean") and args.clean:
            checkpoint_file = config.storage.checkpoint_file
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                print(f"Removed checkpoint file: {checkpoint_file}")
                logger.info(f"Removed checkpoint file: {checkpoint_file}")
                return 0
            else:
                print("No checkpoint file found")
                return 0

        # Create components for actual scrape
        database = _create_database(config)

        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager(config.storage.checkpoint_file)

        # Handle resume logic
        resume = False
        if checkpoint_manager.exists():
            # Determine if we should resume
            if hasattr(args, "no_resume") and args.no_resume:
                # User explicitly requested no resume
                logger.info("--no-resume specified, ignoring checkpoint")
                checkpoint_manager.clear()
            elif hasattr(args, "resume") and args.resume:
                # User explicitly requested resume
                resume = True
                logger.info("--resume specified, will resume from checkpoint")
            else:
                # Prompt user
                if not output_json:
                    resume = _prompt_resume(checkpoint_manager)
                else:
                    # In JSON mode, don't prompt - default to no resume
                    resume = False

        rate_limiter = RateLimiter(requests_per_second=config.scraper.rate_limit)
        api_client = MediaWikiAPIClient(
            base_url=config.wiki.base_url,
            user_agent=config.scraper.user_agent,
            timeout=config.scraper.timeout,
            max_retries=config.scraper.max_retries,
            rate_limiter=rate_limiter,
        )

        scraper = FullScraper(config, api_client, database, checkpoint_manager)

        # Determine namespaces
        namespaces = args.namespace if args.namespace else None

        # Only show progress messages if not outputting JSON
        if not output_json:
            print(f"Starting full scrape...")
            if resume:
                print("Resuming from checkpoint...")
            if namespaces:
                print(f"Namespaces: {namespaces}")
            else:
                print(f"Namespaces: all common namespaces (0-15)")

        # Run scrape
        progress_callback = None if (args.quiet or output_json) else _print_progress

        result = scraper.scrape(
            namespaces=namespaces, progress_callback=progress_callback, resume=resume
        )

        # Output results based on format
        if output_json:
            _output_full_scrape_json(result, database)
        else:
            _print_full_scrape_statistics(result, database)

        # Return exit code based on success
        if result.success:
            return 0
        else:
            logger.warning(f"Scrape completed with {len(result.errors)} errors")
            return 1 if len(result.failed_pages) > result.pages_count * 0.1 else 0

    except KeyboardInterrupt:
        logger.info("Scrape interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Full scrape failed: {e}", exc_info=True)
        return 1


def incremental_scrape_command(args: Namespace) -> int:
    """Execute incremental scrape command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Setup
        _setup_logging(args.log_level)
        config = _load_config(args)

        # Check database exists
        db_path = config.storage.database_file
        if not db_path.exists():
            logger.error(
                f"Database not found: {db_path}. "
                f"Run 'scraper full' first to create baseline."
            )
            return 1

        # Create components
        database = _create_database(config)
        rate_limiter = RateLimiter(requests_per_second=config.scraper.rate_limit)
        api_client = MediaWikiAPIClient(
            base_url=config.wiki.base_url,
            user_agent=config.scraper.user_agent,
            timeout=config.scraper.timeout,
            max_retries=config.scraper.max_retries,
            rate_limiter=rate_limiter,
        )

        # Create download directory for files
        download_dir = config.storage.data_dir / "files"
        download_dir.mkdir(parents=True, exist_ok=True)

        scraper = IncrementalPageScraper(api_client, database, download_dir)

        # Check for JSON output format
        output_json = hasattr(args, "format") and args.format == "json"

        if not output_json:
            print(f"Starting incremental scrape...")

        # Run incremental scrape
        stats = scraper.scrape_incremental()

        # Output results based on format
        if output_json:
            _output_incremental_scrape_json(stats)
        else:
            _print_incremental_scrape_statistics(stats)

        return 0

    except FirstRunRequiresFullScrapeError as e:
        logger.error(str(e))
        print(f"\nERROR: {e}")
        print(f"Run 'scraper full' first to create baseline.")
        return 1
    except KeyboardInterrupt:
        logger.info("Scrape interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Incremental scrape failed: {e}", exc_info=True)
        return 1
