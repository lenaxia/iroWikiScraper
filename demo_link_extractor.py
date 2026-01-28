#!/usr/bin/env python3
"""
Demonstration of LinkExtractor functionality.

This script shows how to extract internal links from wikitext content.
"""

from scraper.scrapers.link_extractor import LinkExtractor


def main():
    # Create a LinkExtractor instance
    extractor = LinkExtractor()

    # Example wikitext content
    wikitext = """
    '''Poring''' is a level 1 monster in [[Ragnarok Online]].

    == Description ==
    Porings are cute pink blobs found in [[Prontera Field]].
    See the [[Monster Database]] for more information.

    == Drops ==
    * [[Apple]]
    * [[Jellopy]]

    {{Infobox Monster
    |name=Poring
    |level=1
    |hp=50
    }}

    [[File:Poring.png|thumb|A Poring monster]]

    [[Category:Monsters]]
    [[Category:Level 1 Monsters]]
    """

    # Extract links
    page_id = 123
    links = extractor.extract_links(page_id, wikitext)

    # Display results
    print(f"Extracted {len(links)} unique links:\n")

    # Group by link type
    by_type = {}
    for link in links:
        if link.link_type not in by_type:
            by_type[link.link_type] = []
        by_type[link.link_type].append(link)

    # Display each type
    for link_type in ["page", "template", "file", "category"]:
        if link_type in by_type:
            print(f"{link_type.upper()} links ({len(by_type[link_type])}):")
            for link in by_type[link_type]:
                print(f"  - {link.target_title}")
            print()


if __name__ == "__main__":
    main()
