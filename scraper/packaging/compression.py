"""Archive compression and splitting utilities.

This module provides functions to compress release directories into tar.gz archives
and split large archives for GitHub Releases (2GB limit).
"""

import math
import tarfile
from pathlib import Path
from typing import Dict, Optional


def compress_directory(
    source_dir: Path,
    output_tar_gz: Path,
    compression_level: int = 6,
    show_progress: bool = False,
) -> Dict[str, any]:
    """
    Compress directory to tar.gz archive.

    Args:
        source_dir: Directory to compress
        output_tar_gz: Output tar.gz file path
        compression_level: Gzip compression level (0-9, default 6)
        show_progress: Whether to show progress bar

    Returns:
        Dictionary with compression statistics:
            - uncompressed_size: Size before compression (bytes)
            - compressed_size: Size after compression (bytes)
            - compression_ratio: Compression ratio (0.0-1.0)
            - file_count: Number of files compressed

    Raises:
        FileNotFoundError: If source directory doesn't exist
        ValueError: If compression level is invalid
        OSError: If compression fails
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    if not source_dir.is_dir():
        raise ValueError(f"Source must be a directory: {source_dir}")

    if compression_level < 0 or compression_level > 9:
        raise ValueError(f"Compression level must be 0-9, got {compression_level}")

    # Create parent directory if needed
    output_tar_gz.parent.mkdir(parents=True, exist_ok=True)

    # Get list of all files
    all_files = list(source_dir.rglob("*"))
    file_list = [f for f in all_files if f.is_file()]

    if show_progress:
        from tqdm import tqdm

        progress = tqdm(total=len(file_list), desc="Compressing", unit="files")
    else:
        progress = None

    # Calculate uncompressed size
    uncompressed_size = sum(f.stat().st_size for f in file_list)

    # Create tar.gz archive
    with tarfile.open(output_tar_gz, f"w:gz", compresslevel=compression_level) as tar:
        for file_path in file_list:
            # Calculate arcname (path relative to source_dir's parent)
            arcname = file_path.relative_to(source_dir.parent)
            tar.add(file_path, arcname=arcname)

            if progress:
                progress.update(1)

    if progress:
        progress.close()

    # Get compressed size
    compressed_size = output_tar_gz.stat().st_size

    # Calculate compression ratio
    compression_ratio = (
        compressed_size / uncompressed_size if uncompressed_size > 0 else 0.0
    )

    return {
        "uncompressed_size": uncompressed_size,
        "compressed_size": compressed_size,
        "compression_ratio": compression_ratio,
        "file_count": len(file_list),
    }


def split_archive(
    archive_path: Path,
    chunk_size_mb: int = 1900,
    show_progress: bool = False,
) -> Dict[str, any]:
    """
    Split large archive into smaller chunks for GitHub Releases.

    Creates files like: archive.tar.gz.001, archive.tar.gz.002, etc.
    Also creates reassemble.sh script to rejoin chunks.

    Args:
        archive_path: Path to archive file to split
        chunk_size_mb: Chunk size in megabytes (default 1900 for GitHub 2GB limit)
        show_progress: Whether to show progress bar

    Returns:
        Dictionary with split statistics:
            - chunk_count: Number of chunks created
            - chunk_size_bytes: Size of each chunk in bytes
            - chunk_paths: List of chunk file paths
            - reassemble_script: Path to reassemble script

    Raises:
        FileNotFoundError: If archive doesn't exist
        ValueError: If chunk size is invalid
        OSError: If splitting fails
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    if chunk_size_mb <= 0:
        raise ValueError(f"Chunk size must be positive, got {chunk_size_mb}")

    # Calculate chunk size in bytes
    chunk_size_bytes = chunk_size_mb * 1024 * 1024

    # Get archive size
    archive_size = archive_path.stat().st_size

    # Check if splitting is needed
    if archive_size <= chunk_size_bytes:
        return {
            "chunk_count": 1,
            "chunk_size_bytes": archive_size,
            "chunk_paths": [archive_path],
            "reassemble_script": None,
        }

    # Calculate number of chunks needed
    chunk_count = math.ceil(archive_size / chunk_size_bytes)

    if show_progress:
        from tqdm import tqdm

        progress = tqdm(
            total=archive_size, desc="Splitting archive", unit="B", unit_scale=True
        )
    else:
        progress = None

    # Split into chunks
    chunk_paths = []
    with open(archive_path, "rb") as f:
        for i in range(chunk_count):
            chunk_num = i + 1
            chunk_path = Path(f"{archive_path}.{chunk_num:03d}")

            with open(chunk_path, "wb") as chunk_file:
                bytes_to_read = min(chunk_size_bytes, archive_size - f.tell())
                chunk_data = f.read(bytes_to_read)
                chunk_file.write(chunk_data)

                if progress:
                    progress.update(len(chunk_data))

            chunk_paths.append(chunk_path)

    if progress:
        progress.close()

    # Create reassemble script
    script_path = archive_path.parent / "reassemble.sh"
    script_content = _generate_reassemble_script(archive_path.name, chunk_count)
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(0o755)  # Make executable

    return {
        "chunk_count": chunk_count,
        "chunk_size_bytes": chunk_size_bytes,
        "chunk_paths": chunk_paths,
        "reassemble_script": script_path,
    }


def _generate_reassemble_script(archive_name: str, chunk_count: int) -> str:
    """
    Generate shell script to reassemble split archive.

    Args:
        archive_name: Name of original archive file
        chunk_count: Number of chunks

    Returns:
        Shell script content
    """
    script = f"""#!/bin/bash
# Reassemble split archive: {archive_name}
# This script combines the split chunks back into the original archive.

set -e  # Exit on error

echo "Reassembling {archive_name}..."

# Check all chunks are present
for i in $(seq -f "%03g" 1 {chunk_count}); do
    chunk="{archive_name}.$i"
    if [ ! -f "$chunk" ]; then
        echo "ERROR: Missing chunk: $chunk"
        exit 1
    fi
done

# Combine chunks
cat {" ".join([f'"{archive_name}.{i:03d}"' for i in range(1, chunk_count + 1)])} > {archive_name}

# Verify file was created
if [ ! -f "{archive_name}" ]; then
    echo "ERROR: Failed to create {archive_name}"
    exit 1
fi

echo "SUCCESS: Reassembled {archive_name}"
echo "Size: $(du -h {archive_name} | cut -f1)"
echo ""
echo "You can now extract the archive:"
echo "  tar -xzf {archive_name}"
"""
    return script
