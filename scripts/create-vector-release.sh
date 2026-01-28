#!/bin/bash

# Script to create vector database releases for GitHub
# This script generates vector databases and packages them for distribution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATE=$(date +%Y-%m-%d)
VERSION="v${DATE}"

# Configuration
DB_PATH="${PROJECT_ROOT}/data/irowiki.db"
OUTPUT_DIR="${PROJECT_ROOT}/releases/${DATE}"
VECTOR_DIR="${OUTPUT_DIR}/vector_databases"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."
    
    if [ ! -f "$DB_PATH" ]; then
        log_error "Database not found at $DB_PATH"
        log_error "Run full scrape first: python -m scraper full"
        exit 1
    fi
    
    if ! python3 -c "import sentence_transformers" 2>/dev/null; then
        log_error "sentence-transformers not installed"
        log_error "Run: pip install -r requirements-vector.txt"
        exit 1
    fi
    
    log_info "All requirements satisfied"
}

create_directories() {
    log_info "Creating output directories..."
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$VECTOR_DIR"
}

generate_qdrant() {
    local model=$1
    local chunk_level=$2
    local output_name="qdrant-${model##*/}-${chunk_level}"
    
    log_info "Generating Qdrant database: $output_name"
    
    python3 "${PROJECT_ROOT}/scripts/vectorize-wiki.py" \
        --db "$DB_PATH" \
        --output "${VECTOR_DIR}/${output_name}" \
        --vector-db qdrant \
        --model "$model" \
        --chunk-level "$chunk_level" \
        --batch-size 32
    
    if [ $? -eq 0 ]; then
        log_info "Qdrant database created successfully"
    else
        log_error "Failed to create Qdrant database"
        return 1
    fi
}

generate_chromadb() {
    local model=$1
    local chunk_level=$2
    local output_name="chromadb-${model##*/}-${chunk_level}"
    
    log_info "Generating ChromaDB database: $output_name"
    
    python3 "${PROJECT_ROOT}/scripts/vectorize-wiki.py" \
        --db "$DB_PATH" \
        --output "${VECTOR_DIR}/${output_name}" \
        --vector-db chromadb \
        --model "$model" \
        --chunk-level "$chunk_level" \
        --batch-size 32
    
    if [ $? -eq 0 ]; then
        log_info "ChromaDB database created successfully"
    else
        log_error "Failed to create ChromaDB database"
        return 1
    fi
}

package_release() {
    local db_type=$1
    local model=$2
    local chunk_level=$3
    
    local model_short="${model##*/}"
    local source_dir="${VECTOR_DIR}/${db_type}-${model_short}-${chunk_level}"
    local archive_name="irowiki-${db_type}-${model_short}-${chunk_level}-${DATE}.tar.gz"
    local archive_path="${OUTPUT_DIR}/${archive_name}"
    
    log_info "Packaging: $archive_name"
    
    # Create archive
    tar -czf "$archive_path" -C "$VECTOR_DIR" "${db_type}-${model_short}-${chunk_level}"
    
    # Get size
    local size=$(du -h "$archive_path" | cut -f1)
    log_info "Package created: $archive_name ($size)"
    
    # Calculate checksum
    local checksum=$(sha256sum "$archive_path" | cut -d' ' -f1)
    echo "$checksum  $archive_name" >> "${OUTPUT_DIR}/checksums.txt"
    
    echo "$archive_name"
}

create_release_notes() {
    log_info "Creating release notes..."
    
    local notes_file="${OUTPUT_DIR}/RELEASE_NOTES.md"
    
    cat > "$notes_file" <<EOF
# iRO Wiki Vector Database Release - $DATE

## Overview

This release contains pre-vectorized databases of the iRO Wiki for semantic search and RAG applications.

**Generated from:** iRO Wiki scrape on $DATE
**Total Pages:** $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pages WHERE namespace=0")
**Total Revisions:** $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM revisions")

## Available Formats

### Qdrant Collections

Qdrant is recommended for production use. Self-hosted, high-performance vector database.

EOF

    # List all Qdrant packages
    for package in "${OUTPUT_DIR}"/irowiki-qdrant-*.tar.gz; do
        if [ -f "$package" ]; then
            local filename=$(basename "$package")
            local size=$(du -h "$package" | cut -f1)
            echo "- **$filename** ($size)" >> "$notes_file"
        fi
    done

    cat >> "$notes_file" <<EOF

### ChromaDB Collections

ChromaDB is recommended for development and testing. Easy setup with embedded mode.

EOF

    # List all ChromaDB packages
    for package in "${OUTPUT_DIR}"/irowiki-chromadb-*.tar.gz; do
        if [ -f "$package" ]; then
            local filename=$(basename "$package")
            local size=$(du -h "$package" | cut -f1)
            echo "- **$filename** ($size)" >> "$notes_file"
        fi
    done

    cat >> "$notes_file" <<EOF

## Embedding Models

### all-MiniLM-L6-v2
- **Dimensions:** 384
- **Speed:** Fast
- **Quality:** Good
- **Best for:** General use, production bots, fast queries

### bge-large-en-v1.5
- **Dimensions:** 1024
- **Speed:** Medium
- **Quality:** Better
- **Best for:** Higher quality results, willing to trade speed

## Chunking Strategies

### Section-Level (Default)
- Balanced context and granularity
- ~300K chunks from 10K pages
- Best for most use cases

### Page-Level
- One vector per page
- ~10K chunks
- Best for general topic search

### Paragraph-Level
- Fine-grained chunking
- ~1M chunks
- Best for precise RAG retrieval

## Quick Start

### Extract the Database

\`\`\`bash
# Extract Qdrant database
tar -xzf irowiki-qdrant-all-MiniLM-L6-v2-section-${DATE}.tar.gz

# Extract ChromaDB database
tar -xzf irowiki-chromadb-all-MiniLM-L6-v2-section-${DATE}.tar.gz
\`\`\`

### Search Examples

\`\`\`python
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

# Load model (must match the one used for vectorization)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Connect to database
client = QdrantClient(path='qdrant-all-MiniLM-L6-v2-section')

# Search
query_vector = model.encode("best weapon for undead")
results = client.search(
    collection_name="irowiki",
    query_vector=query_vector.tolist(),
    limit=5
)

for result in results:
    print(f"{result.payload['page_title']}: {result.score:.3f}")
\`\`\`

## Verification

All packages include SHA-256 checksums in \`checksums.txt\`.

Verify integrity:
\`\`\`bash
sha256sum -c checksums.txt
\`\`\`

## Documentation

For full documentation, see:
- [Vector Database Guide](https://github.com/lenaxia/iroWikiScraper/blob/main/docs/VECTOR_DATABASE.md)
- [Design Document](https://github.com/lenaxia/iroWikiScraper/blob/main/docs/design/2026-01-26_02_vector_embeddings.md)
- [Integration Examples](https://github.com/lenaxia/iroWikiScraper/tree/main/examples)

## License

Same as the main project. See LICENSE file.

---

Generated on: $(date)
EOF

    log_info "Release notes created: $notes_file"
}

main() {
    echo "=================================================="
    echo "  iRO Wiki Vector Database Release Generator"
    echo "  Version: $VERSION"
    echo "=================================================="
    echo ""
    
    check_requirements
    create_directories
    
    log_info "Starting vector database generation..."
    echo ""
    
    # Generate default configuration (MiniLM + section-level)
    log_info "=== Generating default databases (MiniLM, section-level) ==="
    generate_qdrant "all-MiniLM-L6-v2" "section"
    package_release "qdrant" "all-MiniLM-L6-v2" "section"
    
    generate_chromadb "all-MiniLM-L6-v2" "section"
    package_release "chromadb" "all-MiniLM-L6-v2" "section"
    
    # Optional: Generate additional configurations
    if [ "${GENERATE_ALL:-false}" == "true" ]; then
        log_info "=== Generating additional configurations ==="
        
        # BGE Large model
        generate_qdrant "BAAI/bge-large-en-v1.5" "section"
        package_release "qdrant" "BAAI/bge-large-en-v1.5" "section"
        
        # Page-level chunking
        generate_qdrant "all-MiniLM-L6-v2" "page"
        package_release "qdrant" "all-MiniLM-L6-v2" "page"
        
        # Paragraph-level chunking
        generate_qdrant "all-MiniLM-L6-v2" "paragraph"
        package_release "qdrant" "all-MiniLM-L6-v2" "paragraph"
    fi
    
    create_release_notes
    
    echo ""
    log_info "=================================================="
    log_info "  Release generation complete!"
    log_info "=================================================="
    log_info "Output directory: $OUTPUT_DIR"
    log_info ""
    log_info "Files created:"
    ls -lh "$OUTPUT_DIR"/*.tar.gz | awk '{print "  - " $9 " (" $5 ")"}'
    echo ""
    
    log_info "To upload to GitHub:"
    log_info "  gh release create $VERSION --title 'Vector Database Release $DATE' \\"
    log_info "    --notes-file '${OUTPUT_DIR}/RELEASE_NOTES.md' \\"
    log_info "    ${OUTPUT_DIR}/*.tar.gz \\"
    log_info "    ${OUTPUT_DIR}/checksums.txt"
}

# Run main function
main "$@"
