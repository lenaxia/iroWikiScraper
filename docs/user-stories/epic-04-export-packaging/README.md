# Epic 04: Export & Packaging

**Epic ID**: epic-04  
**Priority**: Medium  
**Status**: Not Started  
**Estimated Effort**: 1 week

## Overview

Implement MediaWiki XML export and release packaging for re-hosting and distribution. Generate standard MediaWiki XML dumps compatible with importDump.php, and package complete archives (database + files + XML) for monthly releases.

## Goals

1. Generate MediaWiki XML export from database
2. Package database, files, and XML into versioned releases
3. Generate checksums for integrity verification
4. Create release manifests with metadata
5. Optimize compression for distribution
6. Support split archives for large releases (>2GB)

## Success Criteria

- ✅ XML export compatible with MediaWiki importDump.php
- ✅ Complete archive packages all content
- ✅ SHA256 checksums for all files
- ✅ Manifest includes statistics and metadata
- ✅ Archives compressed efficiently (gzip or xz)
- ✅ Can split large archives for GitHub Releases (2GB limit)
- ✅ 80%+ test coverage on export/packaging

## User Stories

### MediaWiki XML Export
- [Story 01: XML Export Schema](story-01_xml_schema.md)
- [Story 02: Page XML Generation](story-02_page_xml.md)
- [Story 03: Revision XML Generation](story-03_revision_xml.md)
- [Story 04: Streaming XML Writer](story-04_streaming_xml.md)
- [Story 05: Validate XML Output](story-05_validate_xml.md)

### Archive Packaging
- [Story 06: Release Directory Structure](story-06_release_structure.md)
- [Story 07: Archive Compression](story-07_compression.md)
- [Story 08: Split Large Archives](story-08_split_archives.md)

### Metadata & Verification
- [Story 09: Generate Checksums](story-09_checksums.md)
- [Story 10: Create Manifest](story-10_manifest.md)
- [Story 11: Integrity Verification Script](story-11_verification.md)

### Tooling
- [Story 12: Package Release Script](story-12_package_script.md)
- [Story 13: Release Notes Generator](story-13_release_notes.md)

## Dependencies

### Requires:
- Epic 01: Core scraper (scraped data to export)
- Epic 02: Database (data to export from)

### Blocks:
- Epic 06: Automation (automated release publishing)

## Technical Notes

### MediaWiki XML Format

Standard MediaWiki dump format:
```xml
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <siteinfo>
    <sitename>iRO Wiki</sitename>
    <dbname>irowiki</dbname>
    <base>https://irowiki.org/wiki/Main_Page</base>
    <!-- ... -->
  </siteinfo>
  <page>
    <title>Main Page</title>
    <ns>0</ns>
    <id>1</id>
    <revision>
      <id>100</id>
      <timestamp>2020-01-01T00:00:00Z</timestamp>
      <contributor>
        <username>Admin</username>
      </contributor>
      <comment>Initial version</comment>
      <text xml:space="preserve">Page content here</text>
    </revision>
  </page>
</mediawiki>
```

### Release Package Structure

```
irowiki-archive-2026-01.tar.gz
├── irowiki.db                  # SQLite database
├── files/                      # All media files
│   ├── File/A/...
│   ├── File/B/...
│   └── ...
├── irowiki-export.xml          # MediaWiki XML dump
├── MANIFEST.json               # Release metadata
├── README.txt                  # Usage instructions
└── checksums.sha256            # SHA256 checksums
```

### MANIFEST.json Format

```json
{
  "version": "2026.01",
  "scrape_date": "2026-01-01T00:00:00Z",
  "wiki_url": "https://irowiki.org",
  "statistics": {
    "total_pages": 2400,
    "total_revisions": 86500,
    "total_files": 4000,
    "database_size_mb": 3200,
    "files_size_mb": 12800
  },
  "schema_version": "1.0",
  "sqlite_version": "3.35.0",
  "includes_classic_wiki": true,
  "checksums": {
    "irowiki.db": "sha256:...",
    "irowiki-export.xml": "sha256:..."
  }
}
```

### Compression Strategy

**Small archives (<2GB):**
- Single tar.gz file
- Good compression ratio
- Fast decompression

**Large archives (>2GB):**
- Option 1: Split into 1.9GB chunks
- Option 2: Separate archives (db.tar.gz, files.tar.gz, xml.tar.gz)
- Option 3: Use external hosting for full archive

### Streaming XML Export

For large wikis, stream XML to avoid memory issues:
```python
with open('irowiki-export.xml', 'w') as f:
    f.write('<mediawiki>\n')
    f.write(generate_siteinfo())
    
    for page in database.get_all_pages():
        f.write(generate_page_xml(page))
    
    f.write('</mediawiki>\n')
```

## Test Infrastructure Requirements

### Fixtures Needed
- `fixtures/export/sample_wiki.db` - Small test database
- `fixtures/export/expected_output.xml` - Expected XML output
- `fixtures/export/sample_files/` - Test file structure
- `fixtures/export/valid_mediawiki_dump.xml` - Valid reference dump

### Mocks Needed
- `tests/mocks/mock_database_for_export.py` - Mock database for export

### Test Utilities
- `tests/utils/xml_validator.py` - Validate XML structure
- `tests/utils/archive_helpers.py` - Create/extract test archives
- `tests/utils/checksum_validator.py` - Verify checksums

## Progress Tracking

| Story | Status | Assignee | Completed |
|-------|--------|----------|-----------|
| Story 01 | Not Started | - | - |
| Story 02 | Not Started | - | - |
| Story 03 | Not Started | - | - |
| Story 04 | Not Started | - | - |
| Story 05 | Not Started | - | - |
| Story 06 | Not Started | - | - |
| Story 07 | Not Started | - | - |
| Story 08 | Not Started | - | - |
| Story 09 | Not Started | - | - |
| Story 10 | Not Started | - | - |
| Story 11 | Not Started | - | - |
| Story 12 | Not Started | - | - |
| Story 13 | Not Started | - | - |

## Definition of Done

- [ ] All 13 user stories completed
- [ ] XML export validates against MediaWiki schema
- [ ] Successfully imported into test MediaWiki instance
- [ ] Complete archive packages all content
- [ ] Checksums validate correctly
- [ ] Manifest contains accurate statistics
- [ ] All tests passing (80%+ coverage)
- [ ] Packaging script works end-to-end
- [ ] Documentation complete (examples, troubleshooting)
- [ ] Design document created and approved
- [ ] Code reviewed and merged
