#!/usr/bin/env python3
"""Demo script for LinkStorage functionality.

This script demonstrates the key features of the LinkStorage class:
- Adding links (single and batch)
- Deduplication
- Querying by source and type
- Statistics
"""

from scraper.storage.link_storage import LinkStorage
from scraper.storage.models import Link


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print("=" * 60)


def main():
    """Run LinkStorage demo."""
    print("\n🔗 LinkStorage Demo - iRO Wiki Scraper")

    # Initialize storage
    print_section("1. Initialize Storage")
    storage = LinkStorage()
    print("✓ Storage initialized")
    print(f"  Initial count: {storage.get_link_count()}")
    print(f"  Initial stats: {storage.get_stats()}")

    # Add single links
    print_section("2. Add Single Links")
    link1 = Link(source_page_id=1, target_title="Main Page", link_type="page")
    link2 = Link(source_page_id=1, target_title="Help", link_type="page")
    link3 = Link(source_page_id=1, target_title="Stub", link_type="template")

    print(f"Adding: {link1}")
    result = storage.add_link(link1)
    print(f"  Result: {result} (True = new link added)")

    print(f"Adding: {link2}")
    result = storage.add_link(link2)
    print(f"  Result: {result}")

    print(f"Adding: {link3}")
    result = storage.add_link(link3)
    print(f"  Result: {result}")

    print(f"\n  Total links: {storage.get_link_count()}")

    # Demonstrate deduplication
    print_section("3. Deduplication")
    print(f"Adding duplicate: {link1}")
    result = storage.add_link(link1)
    print(f"  Result: {result} (False = duplicate, not added)")
    print(f"  Total links: {storage.get_link_count()} (unchanged)")

    # Batch add
    print_section("4. Batch Add Links")
    batch_links = [
        Link(source_page_id=2, target_title="About", link_type="page"),
        Link(source_page_id=2, target_title="Contact", link_type="page"),
        Link(source_page_id=2, target_title="Logo.png", link_type="file"),
        Link(source_page_id=3, target_title="Monsters", link_type="category"),
        Link(source_page_id=1, target_title="Main Page", link_type="page"),  # Duplicate
    ]

    print(f"Adding batch of {len(batch_links)} links...")
    added = storage.add_links(batch_links)
    print(f"  Added: {added} new links (1 was duplicate)")
    print(f"  Total links: {storage.get_link_count()}")

    # Query by source
    print_section("5. Query by Source Page")
    for page_id in [1, 2, 3]:
        links = storage.get_links_by_source(page_id)
        print(f"\nLinks from page {page_id}:")
        for link in links:
            print(f"  - {link.target_title} ({link.link_type})")

    # Query by type
    print_section("6. Query by Link Type")
    for link_type in ["page", "template", "file", "category"]:
        links = storage.get_links_by_type(link_type)
        print(f"\n{link_type.capitalize()} links ({len(links)}):")
        for link in links:
            print(f"  - Page {link.source_page_id} → {link.target_title}")

    # Statistics
    print_section("7. Statistics")
    stats = storage.get_stats()
    print(f"Total links:     {stats['total']}")
    print(f"  Page links:    {stats['page']}")
    print(f"  Template links: {stats['template']}")
    print(f"  File links:    {stats['file']}")
    print(f"  Category links: {stats['category']}")

    # Get all links
    print_section("8. Get All Links")
    all_links = storage.get_links()
    print(f"All {len(all_links)} links:")
    for link in all_links:
        print(
            f"  - Page {link.source_page_id} → {link.target_title} ({link.link_type})"
        )

    # Clear storage
    print_section("9. Clear Storage")
    print(f"Before clear: {storage.get_link_count()} links")
    storage.clear()
    print(f"After clear:  {storage.get_link_count()} links")
    print(f"Stats after clear: {storage.get_stats()}")

    # Unicode support
    print_section("10. Unicode Support")
    unicode_links = [
        Link(source_page_id=99, target_title="日本語", link_type="page"),
        Link(source_page_id=99, target_title="Café", link_type="page"),
        Link(source_page_id=99, target_title="🎮 Gaming", link_type="page"),
    ]
    added = storage.add_links(unicode_links)
    print(f"Added {added} unicode links:")
    for link in storage.get_links():
        print(f"  - {link.target_title}")

    print("\n" + "=" * 60)
    print(" ✓ Demo Complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
