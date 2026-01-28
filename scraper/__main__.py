"""Command-line interface for iRO Wiki Scraper."""

import logging
import signal
import sys

from scraper.cli import create_parser
from scraper.cli.commands import full_scrape_command, incremental_scrape_command


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\n\nInterrupted by user. Exiting...", file=sys.stderr)
    sys.exit(130)  # Standard exit code for SIGINT


def main() -> int:
    """Main entry point for CLI."""
    try:
        # Register signal handler for graceful interruption
        signal.signal(signal.SIGINT, signal_handler)

        parser = create_parser()
        args = parser.parse_args()

        # Route to appropriate command based on subcommand
        if args.command == "full":
            return full_scrape_command(args)
        elif args.command == "incremental":
            return incremental_scrape_command(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...", file=sys.stderr)
        return 130
    except Exception as e:
        logging.error(f"ERROR: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
