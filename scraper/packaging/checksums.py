"""SHA256 checksum generation and verification.

This module provides functions to generate and verify SHA256 checksums
for release archives.
"""

from pathlib import Path
from typing import Dict
import hashlib


def generate_checksums(directory: Path, show_progress: bool = False) -> Dict[str, str]:
    """
    Generate SHA256 checksums for all files in directory.

    Args:
        directory: Directory to scan for files
        show_progress: Whether to show progress bar

    Returns:
        Dictionary mapping filename to SHA256 hash (hex string)

    Raises:
        FileNotFoundError: If directory doesn't exist
        OSError: If file read fails
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path must be a directory: {directory}")

    # Get all files in directory (not recursive, just top level)
    files = [f for f in directory.iterdir() if f.is_file()]

    if show_progress:
        from tqdm import tqdm

        files = tqdm(files, desc="Computing checksums", unit="files")

    checksums = {}
    for file_path in files:
        sha256_hash = _compute_file_sha256(file_path)
        checksums[file_path.name] = sha256_hash

    return checksums


def write_checksums_file(
    checksums: Dict[str, str],
    output_path: Path,
) -> Path:
    """
    Write checksums to file in sha256sum format.

    Format: <hash>  <filename> (two spaces between hash and filename)

    Args:
        checksums: Dictionary mapping filename to SHA256 hash
        output_path: Path to output checksums file

    Returns:
        Path to created checksums file

    Raises:
        OSError: If file write fails
    """
    lines = []
    for filename, sha256_hash in sorted(checksums.items()):
        lines.append(f"{sha256_hash}  {filename}")

    content = "\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8")

    return output_path


def verify_checksums(
    directory: Path,
    checksums_file: Path,
    show_progress: bool = False,
) -> Dict[str, any]:
    """
    Verify files against checksums file.

    Args:
        directory: Directory containing files to verify
        checksums_file: Path to checksums file
        show_progress: Whether to show progress bar

    Returns:
        Dictionary with verification results:
            - verified: Number of files successfully verified
            - failed: Number of files that failed verification
            - missing: Number of files listed in checksums but not found
            - failures: List of (filename, expected_hash, actual_hash) for failed files
            - missing_files: List of filenames not found

    Raises:
        FileNotFoundError: If directory or checksums file doesn't exist
        OSError: If file read fails
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not checksums_file.exists():
        raise FileNotFoundError(f"Checksums file not found: {checksums_file}")

    # Parse checksums file
    expected_checksums = _parse_checksums_file(checksums_file)

    if show_progress:
        from tqdm import tqdm

        files_to_check = tqdm(
            expected_checksums.items(), desc="Verifying checksums", unit="files"
        )
    else:
        files_to_check = expected_checksums.items()

    verified = 0
    failed = 0
    missing = 0
    failures = []
    missing_files = []

    for filename, expected_hash in files_to_check:
        file_path = directory / filename

        if not file_path.exists():
            missing += 1
            missing_files.append(filename)
            continue

        actual_hash = _compute_file_sha256(file_path)

        if actual_hash == expected_hash:
            verified += 1
        else:
            failed += 1
            failures.append((filename, expected_hash, actual_hash))

    return {
        "verified": verified,
        "failed": failed,
        "missing": missing,
        "failures": failures,
        "missing_files": missing_files,
    }


def _compute_file_sha256(file_path: Path) -> str:
    """
    Compute SHA256 hash of file.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hash as lowercase hex string

    Raises:
        OSError: If file read fails
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def _parse_checksums_file(checksums_file: Path) -> Dict[str, str]:
    """
    Parse checksums file in sha256sum format.

    Args:
        checksums_file: Path to checksums file

    Returns:
        Dictionary mapping filename to SHA256 hash

    Raises:
        ValueError: If file format is invalid
    """
    content = checksums_file.read_text(encoding="utf-8")
    checksums = {}

    for line_num, line in enumerate(content.strip().split("\n"), start=1):
        if not line.strip():
            continue

        # Format: <hash>  <filename> (two spaces)
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid checksum format at line {line_num}: {line}")

        sha256_hash, filename = parts
        sha256_hash = sha256_hash.strip()
        filename = filename.strip()

        # Validate hash is 64 hex characters
        if len(sha256_hash) != 64:
            raise ValueError(
                f"Invalid SHA256 hash length at line {line_num}: {sha256_hash}"
            )

        try:
            int(sha256_hash, 16)
        except ValueError:
            raise ValueError(
                f"Invalid SHA256 hash format at line {line_num}: {sha256_hash}"
            )

        checksums[filename] = sha256_hash

    return checksums
