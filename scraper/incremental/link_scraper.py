"""Incremental link scraper for updating page links."""

import logging
from typing import Dict, List

from scraper.storage.database import Database
from scraper.scrapers.link_extractor import LinkExtractor

logger = logging.getLogger(__name__)


class IncrementalLinkScraper:
    """
    Updates links for pages atomically.

    Deletes old links and inserts new links in a transaction to ensure
    consistency. Reuses existing LinkExtractor for parsing wikitext.

    Example:
        >>> scraper = IncrementalLinkScraper(db)
        >>> scraper.update_links_for_page(123, "[[Page1]] and [[Page2]]")
    """

    def __init__(self, database: Database):
        """
        Initialize incremental link scraper.

        Args:
            database: Database instance
        """
        self.db = database
        self.link_extractor = LinkExtractor()

    def update_links_for_page(self, page_id: int, content: str) -> int:
        """
        Update links for a single page atomically.

        Deletes all outgoing links from the page and inserts new links
        extracted from content. Uses transaction to ensure atomicity.

        Args:
            page_id: Page ID to update links for
            content: Page content (wikitext) to extract links from

        Returns:
            Number of links inserted

        Example:
            >>> count = scraper.update_links_for_page(123, "See [[Page1]]")
            >>> print(f"Inserted {count} links")
        """
        conn = self.db.get_connection()

        try:
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")

            # Delete old links
            conn.execute("DELETE FROM links WHERE source_page_id = ?", (page_id,))

            # Extract new links
            extracted = self.link_extractor.extract_links(page_id, content)

            # Insert new links
            inserted = 0
            for link in extracted:
                conn.execute(
                    """
                    INSERT INTO links (source_page_id, target_title, link_type)
                    VALUES (?, ?, ?)
                    """,
                    (page_id, link.target_title, link.link_type),
                )
                inserted += 1

            # Commit transaction
            conn.commit()

            logger.debug(f"Updated {inserted} links for page {page_id}")
            return inserted

        except Exception as e:
            # Rollback on error
            conn.rollback()
            logger.error(f"Failed to update links for page {page_id}: {e}")
            raise

    def update_links_batch(self, page_contents: Dict[int, str]) -> Dict[int, int]:
        """
        Update links for multiple pages.

        Processes each page independently with separate transactions.
        Continues processing even if individual pages fail.

        Args:
            page_contents: Dict mapping page_id to content

        Returns:
            Dict mapping page_id to number of links inserted

        Example:
            >>> contents = {100: "[[A]]", 101: "[[B]] [[C]]"}
            >>> results = scraper.update_links_batch(contents)
            >>> print(f"Page 100: {results[100]} links")
        """
        logger.info(f"Updating links for {len(page_contents)} pages (batch)")

        results = {}
        failed = 0

        for page_id, content in page_contents.items():
            try:
                count = self.update_links_for_page(page_id, content)
                results[page_id] = count
            except Exception as e:
                logger.error(f"Failed to update links for page {page_id}: {e}")
                results[page_id] = 0
                failed += 1

        logger.info(
            f"Batch update complete: {len(results) - failed} succeeded, {failed} failed"
        )
        return results

    def delete_links_for_page(self, page_id: int) -> int:
        """
        Delete all links from a page.

        Used when a page is deleted to clean up link references.

        Args:
            page_id: Page ID to delete links for

        Returns:
            Number of links deleted
        """
        conn = self.db.get_connection()

        cursor = conn.execute("DELETE FROM links WHERE source_page_id = ?", (page_id,))
        conn.commit()

        deleted = cursor.rowcount
        logger.debug(f"Deleted {deleted} links for page {page_id}")
        return deleted
