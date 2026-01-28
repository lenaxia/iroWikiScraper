"""Command-line interface for iRO-Wiki-Scraper."""

from scraper.cli.args import create_parser
from scraper.cli.commands import full_scrape_command, incremental_scrape_command

__all__ = ["create_parser", "full_scrape_command", "incremental_scrape_command"]
