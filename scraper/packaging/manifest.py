"""Generate release manifest with metadata and statistics.

This module creates MANIFEST.json files with comprehensive release metadata.
"""

from pathlib import Path
from typing import Dict, Optional
import json
import sqlite3
from datetime import datetime

from scraper.storage.database import Database


class ManifestGenerator:
    """Generates release manifest files."""

    def __init__(self, database: Database):
        """
        Initialize manifest generator.

        Args:
            database: Database to extract statistics from
        """
        self.database = database

    def generate_manifest(
        self,
        version: str,
        release_dir: Path,
        checksums: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Generate release manifest.

        Args:
            version: Release version string
            release_dir: Path to release directory
            checksums: Optional dictionary of SHA256 checksums

        Returns:
            Dictionary with manifest data (JSON-serializable)
        """
        # Get current timestamp
        scrape_date = datetime.utcnow().isoformat() + "Z"

        # Get statistics from database
        stats = self._get_statistics(release_dir)

        # Get SQLite version
        sqlite_version = sqlite3.sqlite_version

        manifest = {
            "version": version,
            "scrape_date": scrape_date,
            "wiki_url": "https://irowiki.org",
            "generator": "iRO Wiki Scraper v1.0",
            "statistics": stats,
            "schema_version": "1.0",
            "sqlite_version": sqlite_version,
            "includes_classic_wiki": False,
        }

        # Add checksums if provided
        if checksums:
            manifest["checksums"] = checksums

        return manifest

    def write_manifest(self, manifest: Dict, output_path: Path) -> Path:
        """
        Write manifest to JSON file.

        Args:
            manifest: Manifest dictionary
            output_path: Path to output file

        Returns:
            Path to created manifest file
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return output_path

    def _get_statistics(self, release_dir: Path) -> Dict:
        """
        Get statistics from database and files.

        Args:
            release_dir: Path to release directory

        Returns:
            Dictionary with statistics
        """
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

        # Get file sizes
        db_path = release_dir / "irowiki.db"
        database_size_mb = 0
        if db_path.exists():
            database_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2)

        xml_path = release_dir / "irowiki-export.xml"
        export_xml_size_mb = 0
        if xml_path.exists():
            export_xml_size_mb = round(xml_path.stat().st_size / (1024 * 1024), 2)

        files_dir = release_dir / "files"
        files_size_mb = 0
        if files_dir.exists():
            # Calculate total size of all files in directory
            total_bytes = sum(
                f.stat().st_size for f in files_dir.rglob("*") if f.is_file()
            )
            files_size_mb = round(total_bytes / (1024 * 1024), 2)

        return {
            "total_pages": total_pages,
            "total_revisions": total_revisions,
            "total_files": total_files,
            "database_size_mb": database_size_mb,
            "files_size_mb": files_size_mb,
            "export_xml_size_mb": export_xml_size_mb,
        }
