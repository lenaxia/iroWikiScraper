#!/bin/bash
# Download images from scraped database
# This is a separate step from the main scrape

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Image Downloader for iRO Wiki Scraper ==="
echo ""

# Configuration
DB_PATH="data/irowiki.db"
DOWNLOAD_DIR="data/images"
MAX_SIZE_MB=""
MIME_FILTER=""
SKIP_EXISTING="true"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-size)
            MAX_SIZE_MB="$2"
            shift 2
            ;;
        --mime-type)
            MIME_FILTER="$2"
            shift 2
            ;;
        --force)
            SKIP_EXISTING="false"
            shift
            ;;
        --help)
            echo "Download images from scraped database"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --max-size MB        Only download images smaller than MB (e.g., 10)"
            echo "  --mime-type TYPE     Filter by MIME type (e.g., 'image/png')"
            echo "  --force              Re-download existing files"
            echo "  --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  # Download all images"
            echo "  $0"
            echo ""
            echo "  # Only PNG images under 5MB"
            echo "  $0 --mime-type 'image/png' --max-size 5"
            echo ""
            echo "  # Re-download everything"
            echo "  $0 --force"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if database exists
if [[ ! -f "$DB_PATH" ]]; then
    echo "❌ Database not found: $DB_PATH"
    echo "   Run a scrape first: ./scripts/local-scrape-and-release.sh"
    exit 1
fi

# Create download directory
mkdir -p "$DOWNLOAD_DIR"

echo "Configuration:"
echo "  Database: $DB_PATH"
echo "  Download to: $DOWNLOAD_DIR"
[[ -n "$MAX_SIZE_MB" ]] && echo "  Max size: ${MAX_SIZE_MB} MB"
[[ -n "$MIME_FILTER" ]] && echo "  MIME filter: $MIME_FILTER"
echo "  Skip existing: $SKIP_EXISTING"
echo ""

# Get file count
echo "=== Analyzing Database ==="
TOTAL_FILES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files")
echo "  Total files in database: $TOTAL_FILES"

if [[ $TOTAL_FILES -eq 0 ]]; then
    echo ""
    echo "⚠️  No files found in database"
    echo "   The full scraper doesn't include file discovery yet."
    echo "   You need to run incremental scrape or add file discovery to full scraper."
    exit 0
fi

# Build SQL query based on filters
SQL_FILTER=""
if [[ -n "$MAX_SIZE_MB" ]]; then
    MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))
    SQL_FILTER="WHERE size <= $MAX_SIZE_BYTES"
fi
if [[ -n "$MIME_FILTER" ]]; then
    if [[ -n "$SQL_FILTER" ]]; then
        SQL_FILTER="$SQL_FILTER AND mime_type = '$MIME_FILTER'"
    else
        SQL_FILTER="WHERE mime_type = '$MIME_FILTER'"
    fi
fi

FILTERED_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files $SQL_FILTER")
TOTAL_SIZE=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(size)/1024.0/1024.0, 2) FROM files $SQL_FILTER")

echo "  Files to download: $FILTERED_COUNT"
echo "  Total size: ${TOTAL_SIZE} MB"
echo ""

read -p "Continue with download? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "=== Downloading Images ==="
echo ""

# Download using Python script
python3 << 'PYTHON_EOF'
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse
import requests
from datetime import datetime
import hashlib

db_path = sys.argv[1]
download_dir = Path(sys.argv[2])
sql_filter = sys.argv[3] if len(sys.argv) > 3 else ""
skip_existing = sys.argv[4] == "true" if len(sys.argv) > 4 else True

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get files to download
query = f"SELECT filename, url, sha1, size FROM files {sql_filter}"
cursor.execute(query)
files = cursor.fetchall()

downloaded = 0
skipped = 0
failed = 0
bytes_downloaded = 0

for idx, (filename, url, expected_sha1, size) in enumerate(files, 1):
    # Create subdirectory based on first letter
    first_char = filename[0].upper() if filename else 'Other'
    if not first_char.isalnum():
        first_char = 'Other'
    
    file_dir = download_dir / first_char
    file_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = file_dir / filename
    
    # Check if file exists and is correct
    if skip_existing and file_path.exists():
        # Verify SHA1
        sha1 = hashlib.sha1()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        
        if sha1.hexdigest() == expected_sha1:
            print(f"[{idx}/{len(files)}] ⏭️  Skipped (exists): {filename}")
            skipped += 1
            continue
    
    # Download file
    try:
        print(f"[{idx}/{len(files)}] ⬇️  Downloading: {filename} ({size:,} bytes)")
        
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
        
        # Download with SHA1 verification
        sha1 = hashlib.sha1()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                sha1.update(chunk)
        
        # Verify SHA1
        if sha1.hexdigest() != expected_sha1:
            print(f"    ❌ SHA1 mismatch! Expected {expected_sha1}, got {sha1.hexdigest()}")
            file_path.unlink()
            failed += 1
            continue
        
        downloaded += 1
        bytes_downloaded += size
        
    except Exception as e:
        print(f"    ❌ Download failed: {e}")
        if file_path.exists():
            file_path.unlink()
        failed += 1
        continue

conn.close()

# Print summary
print("\n=== Download Complete ===")
print(f"  Downloaded: {downloaded}")
print(f"  Skipped: {skipped}")
print(f"  Failed: {failed}")
print(f"  Total size: {bytes_downloaded / 1024 / 1024:.2f} MB")

PYTHON_EOF "$DB_PATH" "$DOWNLOAD_DIR" "$SQL_FILTER" "$SKIP_EXISTING"

echo ""
echo "Images saved to: $DOWNLOAD_DIR"
echo ""
echo "To package for release:"
echo "  cd data"
echo "  tar -czf irowiki-images-\$(date +%Y-%m-%d).tar.gz images/"
