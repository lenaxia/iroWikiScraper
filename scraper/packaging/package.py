"""Main packaging orchestrator - end-to-end release packaging.

This module provides the main package_release() function that orchestrates
the complete release packaging workflow.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from scraper.export.xml_exporter import XMLExporter
from scraper.packaging.checksums import generate_checksums, write_checksums_file
from scraper.packaging.compression import compress_directory, split_archive
from scraper.packaging.manifest import ManifestGenerator
from scraper.packaging.release import ReleaseBuilder
from scraper.packaging.verify import verify_release
from scraper.storage.database import Database


class PackagingConfig:
    """Configuration for release packaging."""

    def __init__(
        self,
        database_path: Path,
        files_dir: Optional[Path],
        output_dir: Path,
        version: str,
        compress: bool = True,
        split_large: bool = True,
        chunk_size_mb: int = 1900,
    ):
        """
        Initialize packaging configuration.

        Args:
            database_path: Path to SQLite database
            files_dir: Path to media files directory (optional)
            output_dir: Output directory for release
            version: Release version string
            compress: Whether to compress the release
            split_large: Whether to split large archives
            chunk_size_mb: Chunk size for splitting (MB)
        """
        self.database_path = database_path
        self.files_dir = files_dir
        self.output_dir = output_dir
        self.version = version
        self.compress = compress
        self.split_large = split_large
        self.chunk_size_mb = chunk_size_mb


def package_release(config: PackagingConfig) -> dict:
    """
    Package complete release with all steps.

    Steps:
    1. Create release directory
    2. Export XML from database
    3. Copy database to release
    4. Copy files to release (if provided)
    5. Generate checksums
    6. Generate manifest
    7. Create README
    8. Compress to tar.gz (if enabled)
    9. Split if size > chunk_size (if enabled)
    10. Verify release

    Args:
        config: PackagingConfig with all settings

    Returns:
        Dictionary with packaging results and statistics

    Raises:
        FileNotFoundError: If input files don't exist
        ValueError: If configuration is invalid
        OSError: If packaging fails
    """
    print("=" * 70)
    print(f"iRO Wiki Release Packager v1.0")
    print(f"Version: {config.version}")
    print("=" * 70)
    print()

    results = {}

    # Step 1: Create release directory
    print("[1/10] Creating release directory...")
    builder = ReleaseBuilder()
    release_dir = builder.create_release_directory(config.version, config.output_dir)
    results["release_dir"] = str(release_dir)
    print(f"  ✓ Created: {release_dir}")
    print()

    # Step 2: Export XML
    print("[2/10] Exporting MediaWiki XML...")
    database = Database(config.database_path)
    exporter = XMLExporter(database)
    xml_path = release_dir / "irowiki-export.xml"
    export_stats = exporter.export_to_file(xml_path, show_progress=True)
    results["xml_export"] = export_stats
    print(
        f"  ✓ Exported {export_stats['pages_exported']} pages, "
        f"{export_stats['revisions_exported']} revisions"
    )
    print()

    # Step 3: Copy database
    print("[3/10] Copying database...")
    builder.copy_database(config.database_path, release_dir)
    db_size_mb = (release_dir / "irowiki.db").stat().st_size / (1024 * 1024)
    print(f"  ✓ Database copied ({db_size_mb:.2f} MB)")
    print()

    # Step 4: Copy files (if provided)
    if config.files_dir and config.files_dir.exists():
        print("[4/10] Copying media files...")
        files_copied = builder.copy_files(
            config.files_dir, release_dir, show_progress=True
        )
        results["files_copied"] = files_copied
        print(f"  ✓ Copied {files_copied} files")
    else:
        print("[4/10] Skipping media files (not provided)")
        results["files_copied"] = 0
    print()

    # Step 5: Generate checksums
    print("[5/10] Generating SHA256 checksums...")
    checksums = generate_checksums(release_dir, show_progress=True)
    write_checksums_file(checksums, release_dir / "checksums.sha256")
    results["checksums_count"] = len(checksums)
    print(f"  ✓ Generated checksums for {len(checksums)} files")
    print()

    # Step 6: Generate manifest
    print("[6/10] Generating manifest...")
    manifest_gen = ManifestGenerator(database)
    manifest = manifest_gen.generate_manifest(config.version, release_dir, checksums)
    manifest_gen.write_manifest(manifest, release_dir / "MANIFEST.json")
    results["manifest"] = manifest
    print(f"  ✓ Manifest created")
    print(f"     - Pages: {manifest['statistics']['total_pages']}")
    print(f"     - Revisions: {manifest['statistics']['total_revisions']}")
    print(f"     - Files: {manifest['statistics']['total_files']}")
    print()

    # Step 7: Create README
    print("[7/10] Creating README...")
    builder.create_readme(release_dir, config.version)
    print(f"  ✓ README.txt created")
    print()

    # Step 8: Compress (if enabled)
    archive_path = None
    if config.compress:
        print("[8/10] Compressing archive...")
        archive_path = config.output_dir / f"irowiki-archive-{config.version}.tar.gz"
        compress_stats = compress_directory(
            release_dir, archive_path, show_progress=True
        )
        results["compression"] = compress_stats
        print(f"  ✓ Compressed: {compress_stats['compressed_size'] / (1024**3):.2f} GB")
        print(f"     - Compression ratio: {compress_stats['compression_ratio']:.1%}")
    else:
        print("[8/10] Skipping compression")
    print()

    # Step 9: Split (if enabled and needed)
    if config.compress and config.split_large and archive_path:
        print("[9/10] Checking if splitting is needed...")
        split_stats = split_archive(
            archive_path, chunk_size_mb=config.chunk_size_mb, show_progress=True
        )
        results["split"] = split_stats
        if split_stats["chunk_count"] > 1:
            print(f"  ✓ Split into {split_stats['chunk_count']} chunks")
        else:
            print(f"  ✓ No splitting needed (size < {config.chunk_size_mb} MB)")
    else:
        print("[9/10] Skipping archive splitting")
    print()

    # Step 10: Verify
    print("[10/10] Verifying release...")
    verification = verify_release(release_dir)
    results["verification"] = {
        "is_valid": verification.is_valid,
        "errors": verification.error_count,
        "warnings": verification.warning_count,
        "checks_passed": len(verification.checks_passed),
    }

    if verification.is_valid:
        print(f"  ✓ Verification PASSED")
        print(f"     - {len(verification.checks_passed)} checks passed")
        if verification.warning_count > 0:
            print(f"     - {verification.warning_count} warnings")
    else:
        print(f"  ✗ Verification FAILED")
        print(f"     - {verification.error_count} errors")
        for error in verification.errors[:3]:
            print(f"       • {error.message}")
    print()

    print("=" * 70)
    if verification.is_valid:
        print("✓ RELEASE PACKAGING COMPLETE")
    else:
        print("⚠ RELEASE PACKAGING COMPLETE WITH ERRORS")
    print("=" * 70)
    print()
    print(f"Release directory: {release_dir}")
    if archive_path:
        print(f"Archive: {archive_path}")
    print()

    return results


def main():
    """Command-line interface for release packaging."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Package iRO Wiki release archive")
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--files",
        type=Path,
        help="Path to media files directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for release",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release version (e.g., 2026.01)",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Don't compress the release",
    )
    parser.add_argument(
        "--no-split",
        action="store_true",
        help="Don't split large archives",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1900,
        help="Chunk size in MB for splitting (default: 1900)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.database.exists():
        print(f"Error: Database file not found: {args.database}", file=sys.stderr)
        sys.exit(1)

    if args.files and not args.files.exists():
        print(f"Error: Files directory not found: {args.files}", file=sys.stderr)
        sys.exit(1)

    # Create config
    config = PackagingConfig(
        database_path=args.database,
        files_dir=args.files,
        output_dir=args.output,
        version=args.version,
        compress=not args.no_compress,
        split_large=not args.no_split,
        chunk_size_mb=args.chunk_size,
    )

    # Package release
    try:
        results = package_release(config)

        if results["verification"]["is_valid"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
