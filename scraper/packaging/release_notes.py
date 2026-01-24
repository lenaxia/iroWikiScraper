"""Generate release notes comparing releases.

This module generates markdown-formatted release notes by comparing
current release with previous release.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from scraper.storage.database import Database


class ReleaseNotesGenerator:
    """Generates release notes with statistics and changes."""

    def __init__(self, database: Database):
        """
        Initialize release notes generator.

        Args:
            database: Current database to generate notes for
        """
        self.database = database

    def generate_release_notes(
        self,
        version: str,
        previous_manifest_path: Optional[Path] = None,
    ) -> str:
        """
        Generate release notes in Markdown format.

        Args:
            version: Current release version
            previous_manifest_path: Path to previous release's MANIFEST.json (optional)

        Returns:
            Markdown-formatted release notes
        """
        # Get current statistics
        current_stats = self._get_current_stats()

        # Load previous statistics if available
        previous_stats = None
        if previous_manifest_path and previous_manifest_path.exists():
            previous_stats = self._load_previous_stats(previous_manifest_path)

        # Build release notes
        notes = self._build_notes(version, current_stats, previous_stats)

        return notes

    def _get_current_stats(self) -> Dict:
        """Get statistics from current database."""
        with self.database.get_connection() as conn:
            # Count pages
            cursor = conn.execute("SELECT COUNT(*) FROM pages")
            total_pages = cursor.fetchone()[0]

            # Count revisions
            cursor = conn.execute("SELECT COUNT(*) FROM revisions")
            total_revisions = cursor.fetchone()[0]

            # Count files
            cursor = conn.execute("SELECT COUNT(*) FROM files")
            total_files = cursor.fetchone()[0]

        return {
            "total_pages": total_pages,
            "total_revisions": total_revisions,
            "total_files": total_files,
        }

    def _load_previous_stats(self, manifest_path: Path) -> Dict:
        """Load statistics from previous manifest."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        return manifest.get("statistics", {})

    def _build_notes(
        self,
        version: str,
        current_stats: Dict,
        previous_stats: Optional[Dict],
    ) -> str:
        """Build release notes markdown."""
        lines = []

        # Header
        lines.append(f"# iRO Wiki Archive Release {version}")
        lines.append("")
        lines.append(f"**Release Date:** {datetime.utcnow().strftime('%Y-%m-%d')}")
        lines.append("")

        # Statistics section
        lines.append("## Statistics")
        lines.append("")

        # Format statistics with changes
        stats_items = [
            ("Total Pages", "total_pages"),
            ("Total Revisions", "total_revisions"),
            ("Total Files", "total_files"),
        ]

        for label, key in stats_items:
            current_value = current_stats.get(key, 0)
            value_str = f"{current_value:,}"

            if previous_stats and key in previous_stats:
                previous_value = previous_stats[key]
                diff = current_value - previous_value
                if diff > 0:
                    value_str += f" (+{diff:,} from last release)"
                elif diff < 0:
                    value_str += f" ({diff:,} from last release)"

            lines.append(f"- **{label}:** {value_str}")

        lines.append("")

        # Changes section (if we have previous data)
        if previous_stats:
            lines.append("## Changes Since Last Release")
            lines.append("")

            # Calculate changes
            pages_diff = current_stats.get("total_pages", 0) - previous_stats.get(
                "total_pages", 0
            )
            revisions_diff = current_stats.get(
                "total_revisions", 0
            ) - previous_stats.get("total_revisions", 0)
            files_diff = current_stats.get("total_files", 0) - previous_stats.get(
                "total_files", 0
            )

            if pages_diff > 0:
                lines.append(f"- **New Pages:** {pages_diff:,}")
            elif pages_diff < 0:
                lines.append(f"- **Deleted Pages:** {abs(pages_diff):,}")

            if revisions_diff > 0:
                lines.append(f"- **New Revisions:** {revisions_diff:,}")

            if files_diff > 0:
                lines.append(f"- **New Files:** {files_diff:,}")
            elif files_diff < 0:
                lines.append(f"- **Deleted Files:** {abs(files_diff):,}")

            lines.append("")

        # Archive contents section
        lines.append("## Archive Contents")
        lines.append("")
        lines.append(
            "- **Database:** `irowiki.db` - SQLite database with all wiki content"
        )
        lines.append(
            "- **MediaWiki XML Export:** `irowiki-export.xml` - Compatible with MediaWiki import"
        )
        lines.append(
            "- **Media Files:** `files/` - All images, videos, and other media"
        )
        lines.append(
            "- **Manifest:** `MANIFEST.json` - Release metadata and statistics"
        )
        lines.append(
            "- **Checksums:** `checksums.sha256` - SHA256 checksums for verification"
        )
        lines.append("")

        # Download section
        lines.append("## Download")
        lines.append("")
        lines.append(f"- **Full Archive:** `irowiki-archive-{version}.tar.gz`")
        lines.append("")
        lines.append("If the archive is split into multiple parts:")
        lines.append(f"- `irowiki-archive-{version}.tar.gz.001`")
        lines.append(f"- `irowiki-archive-{version}.tar.gz.002`")
        lines.append("- ...")
        lines.append("")
        lines.append(
            "Use the provided `reassemble.sh` script to combine split archives."
        )
        lines.append("")

        # Verification section
        lines.append("## Verification")
        lines.append("")
        lines.append("Verify the archive integrity using SHA256 checksums:")
        lines.append("")
        lines.append("```bash")
        lines.append("sha256sum -c checksums.sha256")
        lines.append("```")
        lines.append("")

        # Usage section
        lines.append("## Usage")
        lines.append("")
        lines.append("### Extract the Archive")
        lines.append("")
        lines.append("```bash")
        lines.append(f"tar -xzf irowiki-archive-{version}.tar.gz")
        lines.append(f"cd irowiki-archive-{version}")
        lines.append("```")
        lines.append("")
        lines.append("### Query the Database")
        lines.append("")
        lines.append("```python")
        lines.append("import sqlite3")
        lines.append("")
        lines.append("conn = sqlite3.connect('irowiki.db')")
        lines.append("cursor = conn.cursor()")
        lines.append("")
        lines.append("# Get all pages")
        lines.append("cursor.execute('SELECT title FROM pages WHERE namespace = 0')")
        lines.append("pages = cursor.fetchall()")
        lines.append("```")
        lines.append("")
        lines.append("### Import to MediaWiki")
        lines.append("")
        lines.append("```bash")
        lines.append("php maintenance/importDump.php irowiki-export.xml")
        lines.append("```")
        lines.append("")

        # Footer
        lines.append("## Links")
        lines.append("")
        lines.append("- **iRO Wiki:** https://irowiki.org")
        lines.append(
            "- **Source Code:** https://github.com/[your-repo]/iRO-Wiki-Scraper"
        )
        lines.append("")
        lines.append("## License")
        lines.append("")
        lines.append(
            "The iRO Wiki content is licensed under the Creative Commons Attribution-ShareAlike license."  # noqa: E501
        )
        lines.append("The scraper and tooling are MIT licensed.")
        lines.append("")

        return "\n".join(lines)

    def write_release_notes(self, notes: str, output_path: Path) -> Path:
        """
        Write release notes to file.

        Args:
            notes: Release notes content
            output_path: Path to output file

        Returns:
            Path to created file
        """
        output_path.write_text(notes, encoding="utf-8")
        return output_path


def main():
    """Command-line interface for release notes generation."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Generate iRO Wiki release notes")
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Path to current SQLite database",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release version (e.g., 2026.01)",
    )
    parser.add_argument(
        "--previous-manifest",
        type=Path,
        help="Path to previous release's MANIFEST.json (for comparison)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("RELEASE_NOTES.md"),
        help="Output file path (default: RELEASE_NOTES.md)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.database.exists():
        print(f"Error: Database file not found: {args.database}", file=sys.stderr)
        sys.exit(1)

    if args.previous_manifest and not args.previous_manifest.exists():
        print(
            f"Error: Previous manifest not found: {args.previous_manifest}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate release notes
    print(f"Generating release notes for version {args.version}...")

    database = Database(args.database)
    generator = ReleaseNotesGenerator(database)

    notes = generator.generate_release_notes(args.version, args.previous_manifest)
    generator.write_release_notes(notes, args.output)

    print(f"✓ Release notes written to: {args.output}")
    print()


if __name__ == "__main__":
    main()
