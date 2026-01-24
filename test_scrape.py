#!/usr/bin/env python3
"""
Test script to scrape a few pages from iRO Wiki.

This will scrape a small set of pages and save them to a test database.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.api.client import MediaWikiAPIClient
from scraper.storage.database import Database
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.models import Page, Revision
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Scrape a few test pages."""
    # Test pages to scrape
    test_pages = ["Main_Page", "Poring", "Ragnarok_Online", "Prontera", "Archer"]

    # Setup
    output_dir = Path("./test_data")
    output_dir.mkdir(exist_ok=True)

    db_path = output_dir / "test_scrape.db"

    logger.info(f"Initializing database: {db_path}")
    db = Database(str(db_path))
    db.initialize_schema()

    logger.info("Connecting to iRO Wiki API...")
    api = MediaWikiAPIClient("https://irowiki.org")

    page_repo = PageRepository(db)
    revision_repo = RevisionRepository(db)
    revision_scraper = RevisionScraper(api)

    stats = {"pages_scraped": 0, "revisions_scraped": 0, "pages_failed": 0}

    print("\n" + "=" * 70)
    print(f"Starting scrape of {len(test_pages)} pages from iRO Wiki")
    print("=" * 70 + "\n")

    for page_title in test_pages:
        try:
            logger.info(f"Scraping page: {page_title}")
            print(
                f"\n[{stats['pages_scraped'] + 1}/{len(test_pages)}] Scraping: {page_title}"
            )

            # Get page info
            result = api.get_page(page_title)
            pages = result.get("query", {}).get("pages", {})

            if not pages:
                logger.warning(f"Page not found: {page_title}")
                stats["pages_failed"] += 1
                continue

            page_data = list(pages.values())[0]
            page_id = int(page_data["pageid"])
            namespace = page_data.get("ns", 0)
            title = page_data["title"]
            is_redirect = "redirect" in page_data

            # Save page
            page = Page(
                page_id=page_id,
                namespace=namespace,
                title=title,
                is_redirect=is_redirect,
            )

            page_repo.insert_page(page)
            logger.info(f"  ✓ Saved page: {title} (ID: {page_id})")
            print(f"  ✓ Page saved: {title}")

            # Get revisions
            print(f"  → Fetching revisions...")
            revisions = revision_scraper.fetch_revisions(page_id)

            revision_count = 0
            for rev in revisions:
                try:
                    # Revision model expects datetime, already has it
                    revision = Revision(
                        revision_id=rev.revision_id,
                        page_id=page_id,
                        parent_id=rev.parent_id,
                        timestamp=rev.timestamp,  # Already a datetime
                        user=rev.user,
                        user_id=rev.user_id,
                        comment=rev.comment or "",
                        content=rev.content,
                        size=rev.size,
                        sha1=rev.sha1,
                        minor=rev.minor,
                        tags=None,
                    )

                    revision_repo.insert_revision(revision)
                    revision_count += 1
                except Exception as e:
                    logger.warning(
                        f"  ! Failed to save revision {rev.revision_id}: {e}"
                    )

            logger.info(f"  ✓ Saved {revision_count} revisions")
            print(f"  ✓ Saved {revision_count} revisions")

            stats["pages_scraped"] += 1
            stats["revisions_scraped"] += revision_count

        except Exception as e:
            logger.error(f"  ✗ Failed to scrape {page_title}: {e}")
            print(f"  ✗ Error: {e}")
            stats["pages_failed"] += 1

    # Print summary
    print("\n" + "=" * 70)
    print("SCRAPE COMPLETE")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  ✓ Pages scraped: {stats['pages_scraped']}")
    print(f"  ✓ Revisions scraped: {stats['revisions_scraped']}")
    print(f"  ✗ Pages failed: {stats['pages_failed']}")
    print(f"\nDatabase: {db_path}")
    print(f"Size: {db_path.stat().st_size / 1024:.2f} KB")
    print("=" * 70 + "\n")

    db.close()

    return stats


if __name__ == "__main__":
    try:
        stats = main()
        sys.exit(0 if stats["pages_failed"] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\nScrape interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
