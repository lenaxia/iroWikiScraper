# Story 13: Statistics Queries

**Epic**: Epic 02 - Database & Storage  
**Story ID**: epic-02-story-13  
**Priority**: Low  
**Status**: Not Started  
**Estimated Effort**: 1 day  
**Assignee**: TBD

## User Story

As an **analyst**,  
I want **database statistics and analytics**,  
So that **I can understand wiki structure, activity patterns, and generate reports**.

## Description

Implement statistical query functions that provide insights into wiki data: page counts, revision statistics, contributor metrics, namespace distribution, and database size.

## Acceptance Criteria

### 1. Statistics Functions
- [ ] Add to `scraper/storage/queries.py`
- [ ] Function: `get_db_stats(db) -> Dict` - Overall database statistics
- [ ] Function: `get_page_stats(db, page_id) -> Dict` - Per-page statistics
- [ ] Function: `get_namespace_stats(db) -> Dict[int, NamespaceStats]`
- [ ] Function: `get_contributor_stats(db, top_n=10) -> List[ContributorStats]`
- [ ] Function: `get_activity_timeline(db, granularity='day') -> List[ActivityPoint]`
- [ ] Dataclass: `NamespaceStats(namespace, page_count, revision_count, total_size)`
- [ ] Dataclass: `ContributorStats(user, edit_count, total_bytes, first_edit, last_edit)`
- [ ] Dataclass: `ActivityPoint(timestamp, edit_count, contributor_count)`

### 2. Database Statistics
- [ ] Total pages, revisions, files, links
- [ ] Database file size
- [ ] Average content size
- [ ] Date range (first/last edit)

### 3. Performance
- [ ] All queries < 100ms
- [ ] Use indexes where available
- [ ] Aggregate efficiently

### 4. Testing
- [ ] Test all statistics functions
- [ ] Verify accuracy of counts
- [ ] Test with realistic data
- [ ] Test coverage: 80%+

## Technical Details

### Implementation Outline

```python
# Add to scraper/storage/queries.py

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class NamespaceStats:
    """Statistics for a namespace."""
    namespace: int
    page_count: int
    revision_count: int
    total_size: int  # Total bytes of content


@dataclass
class ContributorStats:
    """Statistics for a contributor."""
    user: str
    edit_count: int
    total_bytes: int
    first_edit: datetime
    last_edit: datetime


@dataclass
class ActivityPoint:
    """Activity data point for timeline."""
    timestamp: datetime
    edit_count: int
    contributor_count: int


def get_db_stats(connection: sqlite3.Connection) -> Dict:
    """
    Get overall database statistics.
    
    Returns:
        Dictionary with statistics:
        - total_pages: Number of pages
        - total_revisions: Number of revisions
        - total_files: Number of files
        - total_links: Number of links
        - db_size_mb: Database file size in MB
        - avg_content_size: Average revision content size
        - first_edit: Timestamp of oldest revision
        - last_edit: Timestamp of newest revision
    """
    cursor = connection.execute("""
        SELECT 
            (SELECT COUNT(*) FROM pages) as total_pages,
            (SELECT COUNT(*) FROM revisions) as total_revisions,
            (SELECT COUNT(*) FROM files) as total_files,
            (SELECT COUNT(*) FROM links) as total_links,
            (SELECT AVG(size) FROM revisions) as avg_content_size,
            (SELECT MIN(timestamp) FROM revisions) as first_edit,
            (SELECT MAX(timestamp) FROM revisions) as last_edit
    """)
    
    row = cursor.fetchone()
    
    # Get database file size
    db_path = connection.execute("PRAGMA database_list").fetchone()[2]
    db_size_mb = Path(db_path).stat().st_size / (1024 * 1024) if db_path else 0
    
    return {
        'total_pages': row['total_pages'],
        'total_revisions': row['total_revisions'],
        'total_files': row['total_files'],
        'total_links': row['total_links'],
        'db_size_mb': round(db_size_mb, 2),
        'avg_content_size': round(row['avg_content_size'], 2) if row['avg_content_size'] else 0,
        'first_edit': datetime.fromisoformat(row['first_edit']) if row['first_edit'] else None,
        'last_edit': datetime.fromisoformat(row['last_edit']) if row['last_edit'] else None,
    }


def get_page_stats(connection: sqlite3.Connection, page_id: int) -> Dict:
    """
    Get statistics for a specific page.
    
    Returns:
        Dictionary with page statistics:
        - revision_count: Number of revisions
        - contributor_count: Number of unique contributors
        - first_edit: Timestamp of first revision
        - last_edit: Timestamp of last revision
        - avg_edit_size: Average bytes per edit
        - total_size: Current size in bytes
    """
    cursor = connection.execute("""
        SELECT 
            COUNT(*) as revision_count,
            COUNT(DISTINCT user) as contributor_count,
            MIN(timestamp) as first_edit,
            MAX(timestamp) as last_edit,
            AVG(size) as avg_edit_size,
            (SELECT size FROM revisions WHERE page_id = ? ORDER BY timestamp DESC LIMIT 1) as total_size
        FROM revisions
        WHERE page_id = ?
    """, (page_id, page_id))
    
    row = cursor.fetchone()
    
    return {
        'revision_count': row['revision_count'],
        'contributor_count': row['contributor_count'],
        'first_edit': datetime.fromisoformat(row['first_edit']) if row['first_edit'] else None,
        'last_edit': datetime.fromisoformat(row['last_edit']) if row['last_edit'] else None,
        'avg_edit_size': round(row['avg_edit_size'], 2) if row['avg_edit_size'] else 0,
        'total_size': row['total_size'] or 0,
    }


def get_namespace_stats(connection: sqlite3.Connection) -> Dict[int, NamespaceStats]:
    """
    Get statistics by namespace.
    
    Returns:
        Dictionary mapping namespace ID to NamespaceStats
    """
    cursor = connection.execute("""
        SELECT 
            p.namespace,
            COUNT(DISTINCT p.page_id) as page_count,
            COUNT(r.revision_id) as revision_count,
            SUM(r.size) as total_size
        FROM pages p
        LEFT JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.namespace
        ORDER BY p.namespace
    """)
    
    stats = {}
    for row in cursor.fetchall():
        stats[row['namespace']] = NamespaceStats(
            namespace=row['namespace'],
            page_count=row['page_count'],
            revision_count=row['revision_count'] or 0,
            total_size=row['total_size'] or 0
        )
    
    return stats


def get_contributor_stats(
    connection: sqlite3.Connection,
    top_n: int = 10
) -> List[ContributorStats]:
    """
    Get top contributors by edit count.
    
    Args:
        connection: Database connection
        top_n: Number of top contributors to return
    
    Returns:
        List of ContributorStats, ordered by edit count descending
    """
    cursor = connection.execute("""
        SELECT 
            user,
            COUNT(*) as edit_count,
            SUM(size) as total_bytes,
            MIN(timestamp) as first_edit,
            MAX(timestamp) as last_edit
        FROM revisions
        WHERE user IS NOT NULL
        GROUP BY user
        ORDER BY edit_count DESC
        LIMIT ?
    """, (top_n,))
    
    contributors = []
    for row in cursor.fetchall():
        contributors.append(ContributorStats(
            user=row['user'],
            edit_count=row['edit_count'],
            total_bytes=row['total_bytes'],
            first_edit=datetime.fromisoformat(row['first_edit']),
            last_edit=datetime.fromisoformat(row['last_edit'])
        ))
    
    return contributors


def get_activity_timeline(
    connection: sqlite3.Connection,
    granularity: str = 'day'
) -> List[ActivityPoint]:
    """
    Get edit activity over time.
    
    Args:
        connection: Database connection
        granularity: 'day', 'week', or 'month'
    
    Returns:
        List of ActivityPoint instances
    """
    # SQLite date truncation by granularity
    date_format = {
        'day': '%Y-%m-%d',
        'week': '%Y-%W',
        'month': '%Y-%m'
    }.get(granularity, '%Y-%m-%d')
    
    cursor = connection.execute(f"""
        SELECT 
            strftime('{date_format}', timestamp) as period,
            COUNT(*) as edit_count,
            COUNT(DISTINCT user) as contributor_count
        FROM revisions
        GROUP BY period
        ORDER BY period
    """)
    
    timeline = []
    for row in cursor.fetchall():
        # Parse period back to datetime
        if granularity == 'day':
            timestamp = datetime.strptime(row['period'], '%Y-%m-%d')
        elif granularity == 'month':
            timestamp = datetime.strptime(row['period'], '%Y-%m')
        else:  # week
            # Week format is YYYY-WW, parse accordingly
            year, week = row['period'].split('-')
            timestamp = datetime.strptime(f'{year}-{week}-1', '%Y-%W-%w')
        
        timeline.append(ActivityPoint(
            timestamp=timestamp,
            edit_count=row['edit_count'],
            contributor_count=row['contributor_count']
        ))
    
    return timeline
```

## Dependencies

### Requires
- All previous stories (uses all tables)
- Story 06: Database Initialization

### Blocks
- Epic 04: Export with statistics
- Future: Analytics dashboard

## Testing Requirements

- [ ] Test all statistics functions
- [ ] Verify counts are accurate
- [ ] Test with empty database
- [ ] Test with realistic data
- [ ] Performance < 100ms per query
- [ ] Test coverage: 80%+

## Definition of Done

- [ ] All statistics functions implemented
- [ ] All tests passing
- [ ] Accurate counts verified
- [ ] Performance benchmarks met
- [ ] Code coverage ≥80%
- [ ] Code review completed

## Notes

**Use cases:**
- Generate reports
- Understand wiki activity
- Identify top contributors
- Analyze namespace distribution
- Track editing trends over time

**Performance:**
- Most queries are aggregations
- Should complete in < 100ms
- May add indexes if needed
