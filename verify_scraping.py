#!/usr/bin/env python3
"""Comprehensive verification that scraping actually works correctly."""

import sqlite3
import sys
from scraper.api.client import MediaWikiAPIClient
from scraper.scrapers.revision_scraper import RevisionScraper
from scraper.storage.database import Database
from scraper.storage.page_repository import PageRepository
from scraper.storage.revision_repository import RevisionRepository


def test_known_page():
    """Test scraping a known page and verify content is correct."""
    print("=" * 70)
    print("TEST 1: Scraping and verifying a known wiki page")
    print("=" * 70)

    # Use Main Page (usually page_id 1 or well-known)
    client = MediaWikiAPIClient("https://irowiki.org")

    # First get the Main Page to know its ID
    print("\n1. Looking up 'Main Page'...")
    response = client.query(
        {"list": "allpages", "apnamespace": 0, "aplimit": 1, "apfrom": "Main Page"}
    )

    pages = response.get("query", {}).get("allpages", [])
    if not pages or pages[0]["title"] != "Main Page":
        print("   Trying alternative lookup...")
        response = client.query({"titles": "Main Page", "prop": "info"})
        page_data = response.get("query", {}).get("pages", {})
        page_id = int(list(page_data.keys())[0])
        page_title = page_data[str(page_id)]["title"]
    else:
        page = pages[0]
        page_id = page["pageid"]
        page_title = page["title"]

    print(f"   ✓ Found: '{page_title}' (ID: {page_id})")

    # Scrape the page
    print(f"\n2. Scraping page {page_id}...")
    scraper = RevisionScraper(client, include_content=True)
    revisions = scraper.fetch_revisions(page_id)
    print(f"   ✓ Fetched {len(revisions)} revisions")

    if not revisions:
        print("   ✗ ERROR: No revisions found!")
        return False

    # Check latest revision
    latest = revisions[-1]
    print(f"\n3. Verifying latest revision (ID: {latest.revision_id})...")
    print(f"   - Timestamp: {latest.timestamp}")
    print(f"   - User: {latest.user or '(anonymous)'}")
    print(
        f"   - Comment: {latest.comment[:60]}..."
        if len(latest.comment) > 60
        else f"   - Comment: {latest.comment}"
    )
    print(f"   - Content length: {len(latest.content)} bytes")
    print(f"   - Size (from API): {latest.size} bytes")

    if len(latest.content) == 0 and latest.size > 0:
        print("   ✗ ERROR: Content is empty but size is not!")
        return False

    if len(latest.content) > 0:
        print("\n   Content preview (first 200 chars):")
        print(f"   {'-' * 66}")
        print(f"   {latest.content[:200]}")
        print(f"   {'-' * 66}")
        print("   ✓ Content retrieved successfully")

    # Now verify by getting content directly from API
    print("\n4. Cross-checking with direct API call...")
    api_response = client.query(
        {
            "prop": "revisions",
            "revids": latest.revision_id,
            "rvprop": "content|ids|size",
            "rvslots": "main",
        }
    )

    api_pages = api_response.get("query", {}).get("pages", {})
    api_page_data = list(api_pages.values())[0]
    api_rev = api_page_data["revisions"][0]
    api_content = api_rev["slots"]["main"]["*"]
    api_size = api_rev["size"]

    if api_content == latest.content:
        print("   ✓ Content matches API response exactly!")
    else:
        print("   ✗ ERROR: Content mismatch!")
        print(f"   - Scraped length: {len(latest.content)}")
        print(f"   - API length: {len(api_content)}")
        return False

    if api_size == latest.size:
        print("   ✓ Size matches API response!")
    else:
        print(f"   ✗ WARNING: Size mismatch (scraped: {latest.size}, API: {api_size})")

    return True


def test_anonymous_edits():
    """Test that pages with user_id=0 (anonymous edits) work."""
    print("\n" + "=" * 70)
    print("TEST 2: Testing anonymous edits (user_id=0)")
    print("=" * 70)

    # Page 2 had user_id=0 errors before
    print("\n1. Scraping page 2 (had user_id=0 errors before)...")
    client = MediaWikiAPIClient("https://irowiki.org")
    scraper = RevisionScraper(client, include_content=True)

    try:
        revisions = scraper.fetch_revisions(2)
        print(f"   ✓ Successfully fetched {len(revisions)} revisions")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        return False

    # Count anonymous edits
    anon_count = sum(1 for r in revisions if r.user_id == 0)
    print("\n2. Checking for anonymous edits...")
    print(f"   - Found {anon_count} revision(s) with user_id=0")

    if anon_count > 0:
        print("   ✓ Anonymous edits handled successfully!")
        # Show one example
        anon_rev = next(r for r in revisions if r.user_id == 0)
        print("\n   Example anonymous edit:")
        print(f"   - Revision ID: {anon_rev.revision_id}")
        print(f"   - User: {anon_rev.user}")
        print(f"   - Has content: {len(anon_rev.content) > 0}")
        return True
    else:
        print("   ⚠ No anonymous edits in this page's history")
        return True  # Still pass, just no anonymous edits on this page


def test_database_storage():
    """Test that content is actually stored in database."""
    print("\n" + "=" * 70)
    print("TEST 3: Testing database storage")
    print("=" * 70)

    import tempfile
    import os

    # Create temporary database
    db_file = tempfile.mktemp(suffix=".db")
    print(f"\n1. Creating test database: {os.path.basename(db_file)}")

    try:
        # Initialize database with schema
        db = Database(db_file)
        db.initialize_schema()

        client = MediaWikiAPIClient("https://irowiki.org")
        scraper = RevisionScraper(client, include_content=True)

        # Scrape a small page
        print("\n2. Scraping namespace 4 (Project pages)...")
        response = client.query({"list": "allpages", "apnamespace": 4, "aplimit": 3})
        pages = response.get("query", {}).get("allpages", [])

        if not pages:
            print("   ✗ ERROR: No pages found")
            return False

        print(f"   ✓ Found {len(pages)} pages to test")

        page_repo = PageRepository(db)
        rev_repo = RevisionRepository(db)

        total_revisions = 0
        total_content_bytes = 0

        for page in pages:
            page_id = page["pageid"]
            title = page["title"]
            namespace = page["ns"]

            print(f"\n   Scraping: {title} (ID: {page_id})")

            # Create and store page first (for foreign key constraint)
            from scraper.storage.models import Page

            page_obj = Page(
                page_id=page_id, namespace=namespace, title=title, is_redirect=False
            )
            page_repo.insert_page(page_obj)

            # Scrape revisions
            revisions = scraper.fetch_revisions(page_id)
            print(f"   - Fetched {len(revisions)} revisions")

            # Store in database
            for rev in revisions:
                rev_repo.insert_revision(rev)

            total_revisions += len(revisions)
            total_content_bytes += sum(len(r.content) for r in revisions)

        print("\n3. Verifying database content...")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Check revision count
        cursor.execute("SELECT COUNT(*) FROM revisions")
        db_count = cursor.fetchone()[0]
        print(f"   - Revisions in DB: {db_count}")

        if db_count != total_revisions:
            print(f"   ✗ ERROR: Expected {total_revisions} revisions, got {db_count}")
            return False
        print("   ✓ Revision count matches!")

        # Check content
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN LENGTH(content) > 0 THEN 1 ELSE 0 END) as with_content,
                SUM(LENGTH(content)) as total_bytes,
                AVG(LENGTH(content)) as avg_bytes
            FROM revisions
        """)
        stats = cursor.fetchone()

        print("\n   Content statistics:")
        print(f"   - Total revisions: {stats[0]}")
        print(f"   - With content: {stats[1]}")
        print(f"   - Total bytes: {stats[2]:,}")
        print(f"   - Average bytes: {stats[3]:.1f}")

        if stats[2] == 0:
            print("   ✗ ERROR: No content in database!")
            return False

        if stats[2] != total_content_bytes:
            print("   ✗ ERROR: Content size mismatch!")
            print(f"      Expected: {total_content_bytes:,} bytes")
            print(f"      Got: {stats[2]:,} bytes")
            return False

        print("   ✓ Content stored correctly in database!")

        # Sample a random revision and verify its content
        cursor.execute("""
            SELECT revision_id, content, size
            FROM revisions
            WHERE LENGTH(content) > 0
            LIMIT 1
        """)
        sample = cursor.fetchone()

        if sample:
            rev_id, content, size = sample
            print(f"\n   Sample revision {rev_id}:")
            print(f"   - Content length in DB: {len(content)} bytes")
            print(f"   - Size field: {size} bytes")
            print(f"   - Preview: {content[:100]}")
            print("   ✓ Content is readable from database!")

        conn.close()

        # Cleanup
        os.unlink(db_file)

        return True

    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        if os.path.exists(db_file):
            os.unlink(db_file)
        return False


def main():
    """Run all verification tests."""
    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  COMPREHENSIVE SCRAPING VERIFICATION".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)

    tests = [
        ("Known Page Content", test_known_page),
        ("Anonymous Edits", test_anonymous_edits),
        ("Database Storage", test_database_storage),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {name}: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Scraping is working correctly!")
        print("=" * 70)
        return 0
    else:
        print("❌ SOME TESTS FAILED! There are still issues.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
