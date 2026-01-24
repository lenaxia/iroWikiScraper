"""Integrity verification for incremental updates."""

import logging
from typing import Dict, List

from scraper.storage.database import Database

logger = logging.getLogger(__name__)


class IncrementalVerifier:
    """
    Verify data integrity after incremental updates.

    Performs various checks to ensure that incremental updates
    maintained database consistency and didn't introduce any
    data quality issues.

    Example:
        >>> verifier = IncrementalVerifier(db)
        >>> issues = verifier.verify_all()
        >>> if not any(issues.values()):
        ...     print("✅ All checks passed!")
    """

    def __init__(self, database: Database):
        """
        Initialize integrity verifier.

        Args:
            database: Database to verify
        """
        self.db = database
        self.conn = database.get_connection()

    def verify_all(self) -> Dict[str, List[str]]:
        """
        Run all integrity checks.

        Returns:
            Dictionary mapping check names to lists of issues found.
            Empty lists indicate no issues for that check.

        Example:
            >>> issues = verifier.verify_all()
            >>> total = sum(len(v) for v in issues.values())
            >>> print(f"Found {total} issues")
        """
        logger.info("Running integrity verification...")

        issues = {}
        issues["duplicates"] = self.verify_no_duplicates()
        issues["referential_integrity"] = self.verify_referential_integrity()
        issues["revision_continuity"] = self.verify_revision_continuity()
        issues["link_consistency"] = self.verify_link_consistency()

        total_issues = sum(len(v) for v in issues.values())
        if total_issues == 0:
            logger.info("✅ All integrity checks passed")
        else:
            logger.warning(f"⚠️ Found {total_issues} integrity issues")

        return issues

    def verify_no_duplicates(self) -> List[str]:
        """
        Check for duplicate revisions.

        Returns:
            List of issues found (empty if no duplicates)
        """
        issues = []

        # Check duplicate revision IDs
        query = """
            SELECT revision_id, COUNT(*) as count
            FROM revisions
            GROUP BY revision_id
            HAVING count > 1
        """
        duplicates = self.conn.execute(query).fetchall()
        if duplicates:
            issues.append(f"Found {len(duplicates)} duplicate revision IDs")
            logger.warning(f"Duplicate revisions: {duplicates[:5]}")

        return issues

    def verify_referential_integrity(self) -> List[str]:
        """
        Check foreign key constraints.

        Returns:
            List of issues found (empty if no violations)
        """
        issues = []

        # Check orphaned revisions (no parent page)
        query = """
            SELECT COUNT(*) as count
            FROM revisions r
            LEFT JOIN pages p ON r.page_id = p.page_id
            WHERE p.page_id IS NULL
        """
        result = self.conn.execute(query).fetchone()
        if result[0] > 0:
            issues.append(f"Found {result[0]} orphaned revisions (no parent page)")

        # Check orphaned links (no source page)
        query = """
            SELECT COUNT(*) as count
            FROM links l
            LEFT JOIN pages p ON l.source_page_id = p.page_id
            WHERE p.page_id IS NULL
        """
        result = self.conn.execute(query).fetchone()
        if result[0] > 0:
            issues.append(f"Found {result[0]} orphaned links (no source page)")

        return issues

    def verify_revision_continuity(self) -> List[str]:
        """
        Check for pages without revisions.

        Returns:
            List of issues found (empty if all pages have revisions)
        """
        issues = []

        # Check pages with no revisions (data integrity issue)
        query = """
            SELECT COUNT(*) as count
            FROM pages p
            LEFT JOIN revisions r ON p.page_id = r.page_id
            WHERE r.revision_id IS NULL
        """
        result = self.conn.execute(query).fetchone()
        if result[0] > 0:
            issues.append(f"Found {result[0]} pages with no revisions")
            logger.warning(f"Pages without revisions: {result[0]}")

        return issues

    def verify_link_consistency(self) -> List[str]:
        """
        Check link graph consistency.

        Note: Links pointing to non-existent pages are not necessarily errors
        (they could be external links or red links), so we just log them.

        Returns:
            List of issues found (always empty for this check)
        """
        issues = []

        # Check for broken internal links (informational only)
        # Links are stored by target_title, not target_page_id
        # So this is informational - many wikis have "red links" to non-existent pages
        query = """
            SELECT COUNT(DISTINCT l.target_title) as count
            FROM links l
            WHERE l.link_type = 'page'
            AND NOT EXISTS (
                SELECT 1 FROM pages p WHERE p.title = l.target_title
            )
        """
        result = self.conn.execute(query).fetchone()
        if result[0] > 0:
            logger.info(
                f"Info: {result[0]} links point to non-existent pages "
                "(expected for external/red links)"
            )

        return issues

    @property
    def has_issues(self) -> bool:
        """
        Quick check if there are any issues.

        Returns:
            True if any integrity issues found, False otherwise
        """
        issues = self.verify_all()
        return any(issues.values())
