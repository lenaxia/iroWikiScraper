"""Stream MediaWiki XML export from database.

This module provides the main XMLExporter class that streams XML export
from a database to a file, handling large databases efficiently.
"""

from pathlib import Path

from tqdm import tqdm

from scraper.export.xml_generator import XMLGenerator
from scraper.storage.database import Database


class XMLExporter:
    """
    Export database content to MediaWiki XML format.

    Uses streaming/generator approach to avoid loading entire database into memory.
    """

    def __init__(self, database: Database):
        """
        Initialize exporter with database connection.

        Args:
            database: Database instance to export from
        """
        self.database = database
        self.generator = XMLGenerator()

    def export_to_file(
        self,
        output_path: Path,
        show_progress: bool = True,
    ) -> dict:
        """
        Export database to MediaWiki XML file.

        Args:
            output_path: Path to output XML file
            show_progress: Whether to show progress bar

        Returns:
            Dictionary with export statistics:
                - pages_exported: Number of pages exported
                - revisions_exported: Number of revisions exported
                - output_size_bytes: Size of output file in bytes
        """
        # Get total page count for progress bar
        total_pages = self._count_pages()

        pages_exported = 0
        revisions_exported = 0

        with open(output_path, "w", encoding="utf-8") as f:
            # Write XML header
            f.write(self.generator.generate_xml_header())

            # Write siteinfo
            f.write(self.generator.generate_siteinfo())

            # Stream pages with progress bar
            progress_bar = None
            if show_progress:
                progress_bar = tqdm(
                    total=total_pages,
                    desc="Exporting pages",
                    unit="pages",
                )

            try:
                # Stream pages one at a time
                for page_data in self._stream_pages():
                    page, revisions = page_data

                    # Generate and write page XML
                    page_xml = self.generator.generate_page_xml(page, revisions)
                    f.write(page_xml)

                    pages_exported += 1
                    revisions_exported += len(revisions)

                    if progress_bar:
                        progress_bar.update(1)

            finally:
                if progress_bar:
                    progress_bar.close()

            # Write XML footer
            f.write(self.generator.generate_xml_footer())

        # Get output file size
        output_size = output_path.stat().st_size

        return {
            "pages_exported": pages_exported,
            "revisions_exported": revisions_exported,
            "output_size_bytes": output_size,
        }

    def _count_pages(self) -> int:
        """
        Count total number of pages in database.

        Returns:
            Total page count
        """
        with self.database.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM pages")
            result = cursor.fetchone()
            return result[0] if result else 0

    def _stream_pages(self):
        """
        Stream pages and their revisions from database.

        Yields:
            Tuple of (Page, List[Revision]) for each page
        """
        with self.database.get_connection() as conn:
            # Get all pages ordered by page_id
            pages_cursor = conn.execute("""
                SELECT page_id, namespace, title, is_redirect
                FROM pages
                ORDER BY page_id
                """)

            for page_row in pages_cursor:
                # Import here to avoid circular dependency
                from scraper.storage.models import Page, Revision

                # Create Page object
                page = Page.from_db_row(page_row)

                # Get all revisions for this page
                revisions_cursor = conn.execute(
                    """
                    SELECT revision_id, page_id, parent_id, timestamp,
                           user, user_id, comment, content, size, sha1, minor, tags
                    FROM revisions
                    WHERE page_id = ?
                    ORDER BY timestamp ASC
                    """,
                    (page.page_id,),
                )

                revisions = []
                for revision_row in revisions_cursor:
                    revision = Revision.from_db_row(revision_row)
                    revisions.append(revision)

                yield (page, revisions)


def main():
    """Command-line interface for XML export."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Export iRO Wiki database to MediaWiki XML format"
    )
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output XML file",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar",
    )

    args = parser.parse_args()

    # Validate input
    if not args.database.exists():
        print(f"Error: Database file not found: {args.database}", file=sys.stderr)
        sys.exit(1)

    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Export
    print(f"Exporting database: {args.database}")
    print(f"Output file: {args.output}")
    print()

    database = Database(args.database)
    exporter = XMLExporter(database)

    stats = exporter.export_to_file(
        args.output,
        show_progress=not args.no_progress,
    )

    print()
    print("Export complete!")
    print(f"  Pages exported: {stats['pages_exported']}")
    print(f"  Revisions exported: {stats['revisions_exported']}")
    print(f"  Output size: {stats['output_size_bytes'] / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
