#!/usr/bin/env python3
"""
Example usage of the MediaWiki API Client.

This demonstrates how to use the MediaWikiAPIClient to fetch data from
irowiki.org.

Run this script to test the client against the live API:
    python3 examples/api_client_demo.py
"""

from scraper.api.client import MediaWikiAPIClient
from scraper.api.exceptions import APIError, PageNotFoundError


def main():
    """Demonstrate API client usage."""
    # Initialize the client
    print("Initializing MediaWiki API Client...")
    client = MediaWikiAPIClient("https://irowiki.org")

    # Example 1: Fetch a single page
    print("\n" + "=" * 60)
    print("Example 1: Fetching Main_Page")
    print("=" * 60)
    try:
        result = client.get_page("Main_Page")
        pages = result["query"]["pages"]
        for page_id, page_data in pages.items():
            print(f"Page ID: {page_id}")
            print(f"Title: {page_data.get('title', 'N/A')}")
            print(f"Namespace: {page_data.get('ns', 'N/A')}")
    except APIError as e:
        print(f"Error fetching page: {e}")

    # Example 2: Fetch multiple pages
    print("\n" + "=" * 60)
    print("Example 2: Fetching multiple pages")
    print("=" * 60)
    try:
        result = client.get_pages(["Prontera", "Geffen", "Payon"])
        pages = result["query"]["pages"]
        print(f"Found {len(pages)} pages:")
        for page_id, page_data in pages.items():
            print(f"  - {page_data.get('title', 'N/A')}")
    except APIError as e:
        print(f"Error fetching pages: {e}")

    # Example 3: Generic query (list all pages)
    print("\n" + "=" * 60)
    print("Example 3: Using generic query to list pages")
    print("=" * 60)
    try:
        result = client.query({"list": "allpages", "aplimit": 5, "apnamespace": 0})
        pages = result["query"]["allpages"]
        print(f"First 5 pages in Main namespace:")
        for page in pages:
            print(f"  - {page.get('title', 'N/A')}")
    except APIError as e:
        print(f"Error executing query: {e}")

    # Example 4: Handling errors
    print("\n" + "=" * 60)
    print("Example 4: Error handling")
    print("=" * 60)
    try:
        # Try to fetch a non-existent page
        result = client.get_page("ThisPageDefinitelyDoesNotExist12345")
        print("Page found (unexpected)")
    except PageNotFoundError as e:
        print(f"Expected error caught: {e}")
    except APIError as e:
        print(f"API error: {e}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
