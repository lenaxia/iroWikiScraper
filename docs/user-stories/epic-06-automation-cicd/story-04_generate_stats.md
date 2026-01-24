# Story 04: Generate Statistics

**Story ID**: epic-06-story-04  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: High  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** CI/CD workflow  
**I want** to generate statistics and release notes after scraping  
**So that** users can see what changed in the new release

## Acceptance Criteria

1. **Statistics Generation**
   - [ ] Generate statistics from completed scrape
   - [ ] Include page counts, revision counts, file counts
   - [ ] Show incremental changes (new, updated, deleted)
   - [ ] Calculate growth percentages

2. **Release Notes Format**
   - [ ] Generate release notes in Markdown format
   - [ ] Include formatted statistics tables
   - [ ] Add timestamp and version information
   - [ ] Include comparison with previous release

3. **Change Summary**
   - [ ] List top changed pages by revision count
   - [ ] Show most active editors
   - [ ] Highlight significant changes
   - [ ] Include any warnings or issues

4. **Output Files**
   - [ ] Save release notes to `release-notes.md`
   - [ ] Save detailed statistics to `statistics.json`
   - [ ] Files ready for next workflow steps
   - [ ] Files include UTF-8 encoding

## Technical Details

### Statistics Generation Step

```yaml
- name: Generate statistics
  id: generate-stats
  run: |
    echo "Generating release statistics..."
    
    python -m scraper stats \
      --database data/irowiki.db \
      --output release-notes.md \
      --format markdown \
      --json statistics.json
    
    echo "✓ Statistics generated"
    
    # Display preview
    echo ""
    echo "=== Release Notes Preview ==="
    head -n 50 release-notes.md

- name: Set release version
  id: version
  run: |
    # Generate version from date and run number
    RELEASE_DATE=$(date -u +"%Y-%m")
    RELEASE_VERSION="v${RELEASE_DATE}.${GITHUB_RUN_NUMBER}"
    
    echo "release_version=$RELEASE_VERSION" >> $GITHUB_OUTPUT
    echo "release_date=$RELEASE_DATE" >> $GITHUB_OUTPUT
    echo "Release version: $RELEASE_VERSION"
```

### Release Notes Template

```markdown
# iRO Wiki Archive - {YYYY-MM}

**Release Date**: {YYYY-MM-DD}  
**Version**: v{YYYY-MM}.{RUN_NUMBER}  
**Archive Period**: {START_DATE} to {END_DATE}

## Summary

This release contains a {SCRAPE_TYPE} scrape of the iRO Wiki, capturing all changes from {START_DATE} to {END_DATE}.

## Statistics

| Metric | Count | Change |
|--------|------:|-------:|
| Pages | {PAGE_COUNT} | +{PAGE_CHANGE} |
| Revisions | {REVISION_COUNT} | +{REVISION_CHANGE} |
| Files | {FILE_COUNT} | +{FILE_CHANGE} |
| Total Size | {SIZE_GB} GB | +{SIZE_CHANGE_GB} GB |

## Changes This Month

### New Pages ({NEW_PAGE_COUNT})
- {NEW_PAGE_1}
- {NEW_PAGE_2}
- ...

### Updated Pages ({UPDATED_PAGE_COUNT})
The following pages had the most revisions:
1. {TOP_PAGE_1} ({REVISION_COUNT_1} revisions)
2. {TOP_PAGE_2} ({REVISION_COUNT_2} revisions)
3. {TOP_PAGE_3} ({REVISION_COUNT_3} revisions)

### Most Active Editors
1. {EDITOR_1} ({EDIT_COUNT_1} edits)
2. {EDITOR_2} ({EDIT_COUNT_2} edits)
3. {EDITOR_3} ({EDIT_COUNT_3} edits)

## Download

- **Database**: `irowiki-database-{VERSION}.tar.gz` ({SIZE} MB)
- **Full Archive**: `irowiki-full-{VERSION}.tar.gz` ({SIZE} GB)
- **Checksums**: `*.sha256`

## Installation

```bash
# Download and extract
wget https://github.com/{REPO}/releases/download/{VERSION}/irowiki-database-{VERSION}.tar.gz
tar -xzf irowiki-database-{VERSION}.tar.gz

# Query with Go SDK
go get github.com/{REPO}/sdk
```

## Notes

{SCRAPE_NOTES}
```

### Statistics Query Implementation

```python
# scraper/stats.py

import json
from datetime import datetime
from typing import Dict, Any
from .database import Database

class StatsGenerator:
    def __init__(self, db: Database):
        self.db = db
    
    def generate(self) -> Dict[str, Any]:
        """Generate comprehensive statistics"""
        stats = {
            'version': self._get_version(),
            'scrape_info': self._get_scrape_info(),
            'totals': self._get_totals(),
            'changes': self._get_changes(),
            'top_pages': self._get_top_pages(limit=10),
            'top_editors': self._get_top_editors(limit=10),
            'growth': self._calculate_growth(),
        }
        return stats
    
    def generate_markdown(self, stats: Dict[str, Any]) -> str:
        """Generate markdown release notes"""
        md = []
        
        # Header
        date = stats['scrape_info']['end_time'][:7]  # YYYY-MM
        md.append(f"# iRO Wiki Archive - {date}")
        md.append("")
        
        # Summary
        scrape_info = stats['scrape_info']
        md.append(f"**Release Date**: {scrape_info['end_time'][:10]}")
        md.append(f"**Version**: {stats['version']}")
        md.append(f"**Scrape Type**: {scrape_info['scrape_type']}")
        md.append("")
        
        # Statistics table
        md.append("## Statistics")
        md.append("")
        md.append("| Metric | Count | Change |")
        md.append("|--------|------:|-------:|")
        
        totals = stats['totals']
        changes = stats['changes']
        
        md.append(f"| Pages | {totals['pages']:,} | +{changes['pages_added']:,} |")
        md.append(f"| Revisions | {totals['revisions']:,} | +{changes['revisions_added']:,} |")
        md.append(f"| Files | {totals['files']:,} | +{changes['files_added']:,} |")
        md.append("")
        
        # Top pages
        if stats['top_pages']:
            md.append("## Most Changed Pages")
            md.append("")
            for i, page in enumerate(stats['top_pages'], 1):
                md.append(f"{i}. **{page['title']}** ({page['revision_count']} revisions)")
            md.append("")
        
        # Top editors
        if stats['top_editors']:
            md.append("## Most Active Editors")
            md.append("")
            for i, editor in enumerate(stats['top_editors'], 1):
                md.append(f"{i}. {editor['username']} ({editor['edit_count']} edits)")
            md.append("")
        
        return "\n".join(md)
```

### SQL Queries for Statistics

```yaml
- name: Query statistics from database
  run: |
    # Generate statistics directly with SQL
    sqlite3 data/irowiki.db <<'SQL' > stats.txt
-- Current totals
SELECT 'Total Pages: ' || COUNT(*) FROM pages;
SELECT 'Total Revisions: ' || COUNT(*) FROM revisions;
SELECT 'Total Files: ' || COUNT(*) FROM files;

-- Current run changes
SELECT 'Pages Added: ' || pages_created FROM scrape_runs ORDER BY start_time DESC LIMIT 1;
SELECT 'Pages Updated: ' || pages_updated FROM scrape_runs ORDER BY start_time DESC LIMIT 1;
SELECT 'Revisions Added: ' || revisions_added FROM scrape_runs ORDER BY start_time DESC LIMIT 1;
SQL
    
    cat stats.txt
```

## Dependencies

- **Story 03**: Run incremental scrape (must complete first)
- **Epic 02**: Database storage (for querying statistics)

## Implementation Notes

- Statistics should be fast (<30 seconds)
- Use indexed queries for performance
- Format numbers with thousands separators
- Include both absolute and percentage changes
- Consider adding charts/graphs in future
- Statistics are used in GitHub release description

## Testing Requirements

- [ ] Test statistics generation after full scrape
- [ ] Test statistics generation after incremental scrape
- [ ] Test with empty database (first run)
- [ ] Verify release notes format is valid Markdown
- [ ] Test JSON output is valid
- [ ] Verify statistics are accurate
- [ ] Test with non-ASCII characters in page titles
- [ ] Check file encoding (UTF-8)

## Definition of Done

- [ ] Statistics generation command implemented
- [ ] Release notes Markdown template created
- [ ] JSON output format implemented
- [ ] SQL queries for statistics optimized
- [ ] Workflow step implemented
- [ ] Version number generation implemented
- [ ] Tested with real scrape data
- [ ] Documentation updated
- [ ] Code reviewed and approved
