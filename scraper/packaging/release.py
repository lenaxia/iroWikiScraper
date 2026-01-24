"""Release directory structure builder.

This module creates the standard release directory structure for iRO Wiki archives.
"""

import shutil
from pathlib import Path


class ReleaseBuilder:
    """Builds release directory structure for wiki archives."""

    README_TEMPLATE = """# iRO Wiki Archive {version}

This archive contains a complete snapshot of the International Ragnarok Online (iRO) Wiki.

## Contents

- `irowiki.db` - SQLite database with all wiki content
- `irowiki-export.xml` - MediaWiki XML export (compatible with MediaWiki import)
- `files/` - All media files (images, videos, etc.)
- `MANIFEST.json` - Release metadata and statistics
- `checksums.sha256` - SHA256 checksums for verification

## Database Schema

The SQLite database contains the following tables:
- `pages` - Wiki pages with titles, namespaces, redirect info
- `revisions` - Complete revision history for all pages
- `files` - Media file metadata
- `links` - Internal links between pages
- `scrape_runs` - Scrape run history

## Verification

Verify the archive integrity:
```bash
sha256sum -c checksums.sha256
```

## MediaWiki Import

To import the XML export into MediaWiki:
```bash
php maintenance/importDump.php irowiki-export.xml
```

## Usage with Python

```python
import sqlite3
conn = sqlite3.connect('irowiki.db')
cursor = conn.cursor()

# Get all pages
cursor.execute("SELECT title FROM pages WHERE namespace = 0")
pages = cursor.fetchall()
```

## License

The iRO Wiki content is licensed under the Creative Commons Attribution-ShareAlike license.
The scraper and tooling are MIT licensed.

## Links

- Source Code: https://github.com/[your-repo]/iRO-Wiki-Scraper
- iRO Wiki: https://irowiki.org
"""

    def __init__(self):
        """Initialize release builder."""

    def create_release_directory(
        self,
        version: str,
        output_dir: Path,
    ) -> Path:
        """
        Create release directory structure.

        Args:
            version: Release version string (e.g., "2026.01")
            output_dir: Parent directory for release

        Returns:
            Path to created release directory

        Raises:
            ValueError: If version is invalid
            OSError: If directory creation fails
        """
        if not version or not version.strip():
            raise ValueError("Version cannot be empty")

        # Create release directory name
        release_name = f"irowiki-archive-{version}"
        release_dir = output_dir / release_name

        # Create directory
        release_dir.mkdir(parents=True, exist_ok=True)

        # Create files subdirectory
        files_dir = release_dir / "files"
        files_dir.mkdir(exist_ok=True)

        return release_dir

    def copy_database(self, db_path: Path, release_dir: Path) -> Path:
        """
        Copy database file to release directory.

        Args:
            db_path: Path to source database file
            release_dir: Release directory

        Returns:
            Path to copied database file

        Raises:
            FileNotFoundError: If source database doesn't exist
            OSError: If copy fails
        """
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        dest_path = release_dir / "irowiki.db"
        shutil.copy2(db_path, dest_path)

        return dest_path

    def copy_files(
        self,
        files_dir: Path,
        release_dir: Path,
        show_progress: bool = False,
    ) -> int:
        """
        Copy media files to release directory.

        Args:
            files_dir: Source directory with media files
            release_dir: Release directory
            show_progress: Whether to show progress bar

        Returns:
            Number of files copied

        Raises:
            FileNotFoundError: If source directory doesn't exist
            OSError: If copy fails
        """
        if not files_dir.exists():
            raise FileNotFoundError(f"Files directory not found: {files_dir}")

        dest_files_dir = release_dir / "files"
        dest_files_dir.mkdir(exist_ok=True)

        # Count files to copy
        all_files = list(files_dir.rglob("*"))
        file_list = [f for f in all_files if f.is_file()]

        if show_progress:
            from tqdm import tqdm

            file_list = tqdm(file_list, desc="Copying files", unit="files")

        files_copied = 0
        for src_file in file_list:
            # Calculate relative path
            rel_path = src_file.relative_to(files_dir)
            dest_file = dest_files_dir / rel_path

            # Create parent directories
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(src_file, dest_file)
            files_copied += 1

        return files_copied

    def create_readme(self, release_dir: Path, version: str) -> Path:
        """
        Create README.txt file in release directory.

        Args:
            release_dir: Release directory
            version: Release version string

        Returns:
            Path to created README file
        """
        readme_path = release_dir / "README.txt"
        readme_content = self.README_TEMPLATE.format(version=version)
        readme_path.write_text(readme_content, encoding="utf-8")

        return readme_path

    def copy_xml_export(self, xml_path: Path, release_dir: Path) -> Path:
        """
        Copy MediaWiki XML export to release directory.

        Args:
            xml_path: Path to source XML file
            release_dir: Release directory

        Returns:
            Path to copied XML file

        Raises:
            FileNotFoundError: If source XML doesn't exist
            OSError: If copy fails
        """
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")

        dest_path = release_dir / "irowiki-export.xml"
        shutil.copy2(xml_path, dest_path)

        return dest_path
