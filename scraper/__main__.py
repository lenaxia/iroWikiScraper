"""Command-line interface for iRO Wiki Scraper."""

import argparse
import logging
import sys
from pathlib import Path

from scraper.api.client import MediaWikiAPIClient
from scraper.scrapers.page_scraper import PageDiscovery
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the scraper."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_scrape(args: argparse.Namespace) -> int:
    """Run the scraper."""
    try:
        # Setup logging
        setup_logging(args.log_level)
        logger = logging.getLogger(__name__)

        logger.info("Starting iRO Wiki scraper")
        logger.info(f"Database: {args.database}")
        logger.info(f"Base URL: {args.base_url}")

        # Initialize database
        db_path = Path(args.database)
        db = Database(str(db_path))

        # Check if database exists
        db_exists = db_path.exists()

        if not db_exists or args.force:
            logger.info("Initializing database schema")
            db.initialize_schema()
        else:
            logger.info("Using existing database")

        # Create API client
        api_client = MediaWikiAPIClient(base_url=args.base_url)

        # Create page discovery
        page_discovery = PageDiscovery(api_client)

        # Create revision scraper
        revision_scraper = RevisionScraper(api_client)

        # Run scrape
        logger.info("Discovering pages...")
        pages = []

        if args.namespaces:
            logger.info(f"Discovering pages in namespaces: {args.namespaces}")
            pages = page_discovery.discover_all_pages(namespaces=args.namespaces)
        else:
            logger.info("Discovering all pages")
            pages = page_discovery.discover_all_pages()

        logger.info(f"Found {len(pages)} total pages")

        # Apply limit if specified
        if args.limit:
            pages = pages[: args.limit]
            logger.info(f"Limited to {len(pages)} pages")

        # Scrape revisions for each page
        logger.info(f"Scraping revisions for {len(pages)} pages...")
        total_revisions = 0

        for i, page in enumerate(pages, 1):
            if i % 100 == 0:
                logger.info(
                    f"Progress: {i}/{len(pages)} pages, {total_revisions} revisions"
                )

            # Get revisions for this page
            revisions = revision_scraper.fetch_revisions(page.page_id)
            total_revisions += len(revisions)

            # TODO: Store pages and revisions to database
            logger.debug(
                f"Page {page.page_id}: {page.title} ({len(revisions)} revisions)"
            )

        logger.info(
            f"Scrape completed successfully: {len(pages)} pages, {total_revisions} revisions"
        )
        logger.warning(
            "Note: Data is not yet stored to database (storage implementation pending)"
        )
        return 0

    except Exception as e:
        logging.error(f"Scrape failed: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="iRO Wiki Scraper - Archive MediaWiki content",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape wiki content",
    )
    scrape_parser.add_argument(
        "--database",
        type=str,
        default="irowiki.db",
        help="Path to SQLite database file",
    )
    scrape_parser.add_argument(
        "--base-url",
        type=str,
        default="https://irowiki.org",
        help="Base URL of the MediaWiki instance",
    )
    scrape_parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (YAML)",
    )
    scrape_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    scrape_parser.add_argument(
        "--force-full",
        action="store_true",
        help="Force full scrape even if database exists",
    )
    scrape_parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing database",
    )
    scrape_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run incremental scrape (only new/updated pages)",
    )
    scrape_parser.add_argument(
        "--namespaces",
        type=int,
        nargs="+",
        help="Specific namespaces to scrape (default: all)",
    )
    scrape_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of pages to scrape (for testing)",
    )
    scrape_parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        help="Requests per second rate limit",
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
