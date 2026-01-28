"""Command-line argument parsing for scraper CLI."""

import argparse
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="iRO Wiki Scraper - Archive MediaWiki content",
        epilog="For more information, visit https://github.com/lenaxia/iroWikiScraper",
    )

    # Global options
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration YAML file (default: use built-in defaults)",
    )

    parser.add_argument(
        "--database",
        type=Path,
        help="Path to SQLite database file (default: data/irowiki.db)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (errors still shown)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True,
    )

    # Full scrape command
    full_epilog = """
Examples:
  # Full scrape with defaults
  python -m scraper full

  # Scrape specific namespaces only (0=Main, 4=Project, 6=File)
  python -m scraper full --namespace 0 4 6

  # Dry run to estimate time and page count
  python -m scraper full --dry-run

  # Resume from checkpoint automatically
  python -m scraper full --resume

  # Force new scrape (ignore existing data)
  python -m scraper full --force
"""

    full_parser = subparsers.add_parser(
        "full",
        help="Perform a full scrape of the wiki",
        description="Scrape all pages and their complete revision history from the wiki",
        epilog=full_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    full_parser.add_argument(
        "--namespace",
        type=int,
        nargs="+",
        metavar="NS",
        help="Namespace IDs to scrape (default: all common namespaces 0-15)",
    )

    full_parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        metavar="RATE",
        help="Maximum requests per second (default: 2.0)",
    )

    full_parser.add_argument(
        "--force",
        action="store_true",
        help="Force scrape even if data already exists",
    )

    full_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover pages but don't scrape revisions or store data",
    )

    full_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for statistics (default: text)",
    )

    # Resume flags (mutually exclusive)
    resume_group = full_parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume",
        action="store_true",
        help="Automatically resume from checkpoint without prompting",
    )
    resume_group.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing checkpoint and start fresh",
    )

    full_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove old checkpoint file and exit",
    )

    # Incremental scrape command
    incr_epilog = """
Examples:
  # Incremental update (auto-detect last scrape time)
  python -m scraper incremental

  # Update only specific namespaces
  python -m scraper incremental --namespace 0 6

  # Update since specific timestamp
  python -m scraper incremental --since 2025-01-01T00:00:00Z

  # Output JSON for automation
  python -m scraper incremental --format json
"""

    incr_parser = subparsers.add_parser(
        "incremental",
        help="Perform an incremental update",
        description="Update the database with recent changes (requires prior full scrape)",
        epilog=incr_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    incr_parser.add_argument(
        "--since",
        type=str,
        metavar="TIMESTAMP",
        help="Only scrape changes since this timestamp (ISO format: 2025-01-01T00:00:00Z)",
    )

    incr_parser.add_argument(
        "--namespace",
        type=int,
        nargs="+",
        metavar="NS",
        help="Limit updates to specific namespaces",
    )

    incr_parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        metavar="RATE",
        help="Maximum requests per second (default: 2.0)",
    )

    incr_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for statistics (default: text)",
    )

    return parser
