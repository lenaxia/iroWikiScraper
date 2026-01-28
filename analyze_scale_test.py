#!/usr/bin/env python3
"""Analyze scale test results to prove scraping works correctly."""

import sqlite3
import sys


def analyze_database(db_path):
    """Comprehensive analysis of scraped data."""

    print("=" * 80)
    print("SCALE TEST ANALYSIS - Proving Scraping Works at Scale")
    print("=" * 80)
    print()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Overall statistics
    print("📊 OVERALL STATISTICS")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            COUNT(*) as total_pages,
            COUNT(DISTINCT namespace) as namespaces
        FROM pages
    """)
    pages_stats = cursor.fetchone()
    print(f"Total pages discovered:     {pages_stats['total_pages']:,}")
    print(f"Namespaces:                 {pages_stats['namespaces']}")

    cursor.execute("""
        SELECT 
            COUNT(*) as total_revisions,
            COUNT(DISTINCT page_id) as pages_with_revisions,
            AVG(CAST(LENGTH(content) AS FLOAT)) as avg_content_size,
            SUM(LENGTH(content)) as total_content_bytes,
            MIN(LENGTH(content)) as min_size,
            MAX(LENGTH(content)) as max_size
        FROM revisions
    """)
    rev_stats = cursor.fetchone()
    print(f"Total revisions scraped:    {rev_stats['total_revisions']:,}")
    print(f"Pages with revisions:       {rev_stats['pages_with_revisions']:,}")
    print(f"Avg content size:           {rev_stats['avg_content_size']:,.0f} bytes")
    print(
        f"Total content:              {rev_stats['total_content_bytes'] / (1024 * 1024):,.1f} MB"
    )
    print(
        f"Content size range:         {rev_stats['min_size']} - {rev_stats['max_size']:,} bytes"
    )
    print()

    # Content verification
    print("✅ CONTENT VERIFICATION")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN LENGTH(content) > 0 THEN 1 ELSE 0 END) as with_content,
            SUM(CASE WHEN LENGTH(content) = 0 AND size = 0 THEN 1 ELSE 0 END) as empty_valid,
            SUM(CASE WHEN LENGTH(content) = 0 AND size > 0 THEN 1 ELSE 0 END) as missing_content
        FROM revisions
    """)
    content_stats = cursor.fetchone()

    total = content_stats["total"]
    with_content = content_stats["with_content"]
    empty_valid = content_stats["empty_valid"]
    missing_content = content_stats["missing_content"]

    print(
        f"Revisions with content:     {with_content:,} ({100 * with_content / total:.1f}%)"
    )
    print(
        f"Empty pages (size=0):       {empty_valid:,} ({100 * empty_valid / total:.1f}%)"
    )
    print(
        f"MISSING content (ERROR):    {missing_content:,} ({100 * missing_content / total:.1f}%)"
    )

    if missing_content > 0:
        print(f"  ❌ FAILURE: {missing_content} revisions missing content!")
        return False
    else:
        print(f"  ✅ SUCCESS: All non-empty revisions have content!")
    print()

    # Anonymous edits (user_id=0)
    print("👤 ANONYMOUS EDITS (user_id=0)")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            COUNT(*) as total_anon,
            COUNT(DISTINCT page_id) as pages_with_anon
        FROM revisions
        WHERE user_id = 0
    """)
    anon_stats = cursor.fetchone()

    if anon_stats["total_anon"] > 0:
        print(f"Anonymous revisions:        {anon_stats['total_anon']:,}")
        print(f"Pages with anonymous edits: {anon_stats['pages_with_anon']:,}")
        print(f"  ✅ SUCCESS: user_id=0 handled correctly!")
    else:
        print(f"No anonymous edits found in this sample")
    print()

    # Sample content verification
    print("🔍 SAMPLE CONTENT VERIFICATION")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            r.revision_id,
            p.title,
            r.user,
            r.user_id,
            LENGTH(r.content) as content_len,
            r.size,
            SUBSTR(r.content, 1, 100) as preview
        FROM revisions r
        JOIN pages p ON r.page_id = p.page_id
        WHERE LENGTH(r.content) > 1000
        ORDER BY RANDOM()
        LIMIT 5
    """)

    samples = cursor.fetchall()
    for i, sample in enumerate(samples, 1):
        print(f"\nSample {i}:")
        print(f"  Page: {sample['title']}")
        print(f"  Revision: {sample['revision_id']}")
        print(f"  User: {sample['user'] or '(anonymous)'} (ID: {sample['user_id']})")
        print(
            f"  Content: {sample['content_len']:,} bytes (size field: {sample['size']})"
        )
        print(f"  Preview: {sample['preview']}...")
    print()

    # Pages by namespace
    print("📁 PAGES BY NAMESPACE")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            p.namespace,
            CASE p.namespace
                WHEN 0 THEN 'Main'
                WHEN 1 THEN 'Talk'
                WHEN 2 THEN 'User'
                WHEN 3 THEN 'User talk'
                WHEN 4 THEN 'Project'
                WHEN 6 THEN 'File'
                WHEN 10 THEN 'Template'
                WHEN 14 THEN 'Category'
                ELSE 'Other'
            END as ns_name,
            COUNT(DISTINCT p.page_id) as pages,
            COUNT(r.revision_id) as revisions,
            AVG(LENGTH(r.content)) as avg_size
        FROM pages p
        LEFT JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.namespace
        ORDER BY pages DESC
        LIMIT 10
    """)

    print(f"{'Namespace':<15} {'Pages':<10} {'Revisions':<12} {'Avg Size':<12}")
    print("-" * 80)
    for row in cursor.fetchall():
        ns = f"{row['namespace']} ({row['ns_name']})"
        print(
            f"{ns:<15} {row['pages']:<10,} {row['revisions']:<12,} {row['avg_size']:<12,.0f}"
        )
    print()

    # Top pages by revisions
    print("📈 TOP PAGES BY REVISION COUNT")
    print("-" * 80)

    cursor.execute("""
        SELECT 
            p.title,
            COUNT(r.revision_id) as revision_count,
            SUM(LENGTH(r.content)) as total_content
        FROM pages p
        JOIN revisions r ON p.page_id = r.page_id
        GROUP BY p.page_id
        ORDER BY revision_count DESC
        LIMIT 10
    """)

    print(f"{'Page Title':<50} {'Revisions':<12} {'Total Content':<15}")
    print("-" * 80)
    for row in cursor.fetchall():
        title = row["title"][:48]
        print(f"{title:<50} {row['revision_count']:<12,} {row['total_content']:<15,}")
    print()

    # Database size
    print("💾 DATABASE SIZE")
    print("-" * 80)

    cursor.execute(
        "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
    )
    db_size = cursor.fetchone()[0]
    print(f"Database file size:         {db_size / (1024 * 1024):.1f} MB")
    print()

    conn.close()

    # Final verdict
    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    if missing_content == 0 and with_content > 0:
        print("✅ SCRAPING WORKS CORRECTLY!")
        print(f"   - {with_content:,} revisions with valid content")
        print(
            f"   - {rev_stats['total_content_bytes'] / (1024 * 1024):.1f} MB of wiki content archived"
        )
        print(f"   - All revisions have content or are legitimately empty")
        print("=" * 80)
        return True
    else:
        print("❌ SCRAPING HAS ISSUES!")
        print("=" * 80)
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/scale-test.db"
    success = analyze_database(db_path)
    sys.exit(0 if success else 1)
