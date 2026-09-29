# iRO Wiki Scraper

A complete archival system for [irowiki.org](https://irowiki.org) with historical preservation, searchable database, and re-hosting capability.

## Project Status

🚧 **In Development** - Initial setup phase

## Overview

iRO Wiki Scraper is a data preservation tool designed to create comprehensive, versioned archives of the iRO Wiki (International Ragnarok Online Wiki) and Classic Wiki. The project captures:

- **Complete page content** with full revision history
- **All media files** (images, documents)
- **Edit metadata** (timestamps, authors, comments, checksums)
- **Internal link structure** for navigation preservation
- **Temporal snapshots** for point-in-time queries

## Features

### Core Capabilities

- ✅ **Complete Preservation**: Every page revision, every edit, every file
- ✅ **Historical Archive**: Query content at any point in time
- ✅ **Searchable Database**: Full-text search across content and metadata
- ✅ **Re-hostable**: MediaWiki XML export for easy restoration
- ✅ **Incremental Updates**: Monthly delta scrapes capture only new changes
- ✅ **Versioned Releases**: Automated archives published monthly

### Technical Features

- **MediaWiki API Integration**: Respectful scraping with rate limiting
- **SQLite/PostgreSQL Support**: Portable database with optional scaling
- **Checkpoint/Resume**: Handles interruptions gracefully
- **Integrity Verification**: SHA256 checksums for all content
- **Go SDK**: Idiomatic query interface for archived data

## Architecture

```
MediaWiki API → Python Scraper → SQLite Database → Go SDK
                      ↓
                Media Files + XML Export
                      ↓
              Monthly Release (tar.gz)
```

### Components

1. **Python Scraper** (`scraper/`)
   - MediaWiki API client with rate limiting
   - Page, revision, and file scrapers
   - Database storage with checkpointing
   - MediaWiki XML exporter

2. **Go SDK** (`sdk/`)
   - Query interface for archived data
   - SQLite and PostgreSQL backends
   - Timeline and search operations
   - CLI tool for interactive queries

3. **Database Schema** (`schema/`)
   - Compatible with SQLite and PostgreSQL
   - Full revision history
   - File metadata and checksums
   - Internal link graphs

4. **Automation** (`.github/workflows/`)
   - Monthly scheduled scraping
   - Automated release packaging
   - GitHub Actions integration

## Installation

### Prerequisites

- Python 3.11+
- Go 1.21+ (for SDK)
- SQLite 3.35+

### Python Scraper

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper.git
cd iRO-Wiki-Scraper

# Install Python dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# Configure
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your settings
```

### Go SDK

```bash
# Install SDK
go get github.com/YOUR_USERNAME/iRO-Wiki-Scraper/sdk/irowiki

# Install CLI tool
go install github.com/YOUR_USERNAME/iRO-Wiki-Scraper/sdk/cmd/irowiki-cli
```

## Usage

### Running the Scraper

```bash
# Full scrape (first time)
python -m scraper scrape --config config/config.yaml --full

# Incremental scrape (subsequent runs)
python -m scraper scrape --config config/config.yaml --incremental

# Generate statistics
python -m scraper stats --database data/irowiki.db

# Export to MediaWiki XML
python -m scraper export --database data/irowiki.db --output exports/
```

### Using the Go SDK

```go
package main

import (
    "fmt"
    "github.com/YOUR_USERNAME/iRO-Wiki-Scraper/sdk/irowiki"
)

func main() {
    // Open archive
    client, err := irowiki.OpenSQLite("irowiki.db")
    if err != nil {
        panic(err)
    }
    defer client.Close()
    
    // Search pages
    results, _ := client.Search(irowiki.SearchOptions{
        Query: "Poring",
        Limit: 10,
    })
    
    for _, result := range results {
        fmt.Printf("%s (ID: %d)\n", result.Title, result.PageID)
    }
}
```

### Using the CLI

```bash
# Search for pages
irowiki-cli search "Ragnarok"

# Get page history
irowiki-cli history "Main_Page"

# Get page at specific time
irowiki-cli snapshot "Main_Page" --date 2020-06-15

# Statistics
irowiki-cli stats
```

## Command Reference

The scraper CLI (`python -m scraper`) provides three commands:

### `full` — full archive scrape

```bash
python -m scraper full [--namespace NS [NS ...]] [--rate-limit RATE]
                       [--force] [--dry-run] [--resume | --no-resume]
                       [--no-links] [--no-files] [--no-download]
                       [--format text|json]
```

Discovers every page in the selected namespaces (default: all standard
namespaces 0-15) and stores the complete revision history.

- `--namespace` — namespace IDs to scrape (default: 0 1 2 ... 15)
- `--rate-limit` — max requests per second (default: 2.0)
- `--dry-run` — discover pages and estimate time without storing data
- `--force` — scrape even if data already exists
- `--resume` / `--no-resume` — resume from checkpoint or start fresh
- `--no-links` / `--no-files` / `--no-download` — skip link extraction,
  file metadata, or media downloads

**Dry run example** (estimate scope before committing):

```bash
python -m scraper full --dry-run --namespace 0
```

### `incremental` — delta update

```bash
python -m scraper incremental [--since ISO8601] [--namespace NS [NS ...]]
                              [--format text|json]
```

Fetches only pages changed since the last scrape (or `--since`).

### `backfill` — fill gaps in history

```bash
python -m scraper backfill [--pages] [--links] [--files]
```

Re-scrapes pages with missing revisions, links, or file metadata.

Global options for all commands: `--config PATH`, `--database PATH`,
`--log-level LEVEL`, `--quiet`.

## Troubleshooting

- **`Configuration validation failed: scraper.rate_limit must be positive`**
  — a config file value is invalid; CLI flags (e.g. `--rate-limit 2`)
  override file values, or fix the YAML file.
- **`Page not found` on a page you know exists** — iRO Wiki removed
  per-monster and per-item pages during its database externalization;
  check the live wiki or use a current title.
- **Scrape interrupted** — re-run with `--resume`; the checkpoint file
  tracks completed pages and namespaces.
- **`429` rate-limit errors in logs** — the scraper backs off
  automatically; lower `--rate-limit` if it persists.
- **Database locked / busy** — ensure no other process holds the SQLite
  file; incremental runs take an exclusive transaction during commits.

## Database Schema

The archive database stores:

- **Pages**: Page metadata (ID, title, namespace)
- **Revisions**: Complete edit history with content
- **Files**: Media files with checksums and metadata
- **Links**: Internal link structure
- **Scrape Runs**: Metadata about archival runs

See `schema/sqlite.sql` for complete schema.

## Monthly Releases

Archives are automatically published monthly via GitHub Actions:

- **Format**: `irowiki-archive-YYYY-MM.tar.gz`
- **Contents**: Database + media files + MediaWiki XML export
- **Size**: ~10-25 GB (varies by month)
- **Location**: GitHub Releases

Download the latest release from the [Releases](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/releases) page.

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Type checking
mypy scraper/

# Linting
black scraper/ tests/
flake8 scraper/
```

### Documentation

- **User Guide**: See [docs/USAGE.md](docs/USAGE.md)
- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Reference**: See [docs/API.md](docs/API.md)
- **LLM Guide**: See [README-LLM.md](README-LLM.md)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Data Source

- **Main Wiki**: https://irowiki.org/
- **Classic Wiki**: https://irowiki.org/classic/
- **API**: MediaWiki 1.44.0
- **License**: Content under GNU Free Documentation License 1.3

## Legal & Ethics

This project:
- ✅ Uses public MediaWiki API (no scraping of HTML)
- ✅ Respects rate limits (1 request/second default)
- ✅ Identifies requests with proper User-Agent
- ✅ Preserves license and attribution information
- ✅ Is for archival and preservation purposes

**We are not affiliated with WarpPortal or Gravity.**

## License

This project (code) is licensed under MIT License. See [LICENSE](LICENSE) for details.

The archived wiki content is licensed under GNU Free Documentation License 1.3 (GFDL), matching the source wiki.

## Acknowledgments

- iRO Wiki community for maintaining the wiki
- MediaWiki for excellent API documentation
- rAthena project for inspiration

## Contact

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/iRO-Wiki-Scraper/discussions)

---

**Status**: 🚧 In Development | Last Updated: 2026-01-23
