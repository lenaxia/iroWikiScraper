"""Link extraction from MediaWiki wikitext content.

This module provides functionality to extract internal links from wikitext,
including regular page links, template transclusions, file references, and
category memberships.
"""

import re
from typing import List, Set

from scraper.storage.models import Link


class LinkExtractor:
    """
    Extracts internal links from MediaWiki wikitext content.

    This class parses wikitext to identify and extract four types of internal links:
    - Page links: [[Page Name]] or [[Page Name|Display Text]]
    - Template transclusions: {{Template Name}} or {{Template Name|params}}
    - File references: [[File:Name.ext]] or [[Image:Name.ext]]
    - Category memberships: [[Category:Name]] or [[Category:Name|Sort Key]]

    The extractor handles:
    - Links with display text or parameters
    - Namespace prefixes (Help:, Template:, etc.)
    - Title normalization (underscores to spaces, whitespace stripping)
    - Deduplication (same link appearing multiple times)
    - Malformed wikitext (graceful error handling)

    Example:
        >>> extractor = LinkExtractor()
        >>> wikitext = "See [[Main Page]] and {{Stub}} template."
        >>> links = extractor.extract_links(page_id=1, wikitext=wikitext)
        >>> len(links)
        2
        >>> links[0].link_type
        'page'
        >>> links[1].link_type
        'template'
    """

    def __init__(self) -> None:
        """
        Initialize the LinkExtractor with compiled regex patterns.

        Compiles regex patterns for efficient matching of:
        - Page links (excluding File: and Category: prefixes)
        - Template transclusions
        - File references (both File: and Image: prefixes)
        - Category memberships
        """
        # Pattern for page links [[Target]] or [[Target|Display]]
        # Negative lookahead to exclude File: and Category: which are handled separately
        # Use [^\[\]\n] to avoid matching across lines or nested brackets
        self._page_link_pattern = re.compile(
            r"\[\[(?!File:|Image:|Category:)([^\[\]\n|]+)(?:\|[^\[\]\n]+)?\]\]",
            re.IGNORECASE,
        )

        # Pattern for template transclusions {{Template}} or {{Template|params}}
        # Use [^\{\}\n] to avoid matching across lines or nested brackets
        self._template_pattern = re.compile(r"\{\{([^\{\}\n|]+)(?:\|[^\{\}\n]+)?\}\}")

        # Pattern for file references [[File:...]] or [[Image:...]]
        self._file_pattern = re.compile(
            r"\[\[(?:File|Image):([^\[\]\n|]+)(?:\|[^\[\]\n]+)?\]\]", re.IGNORECASE
        )

        # Pattern for category memberships [[Category:...]]
        self._category_pattern = re.compile(
            r"\[\[Category:([^\[\]\n|]+)(?:\|[^\[\]\n]+)?\]\]", re.IGNORECASE
        )

        # Pattern for template transclusions {{Template}} or {{Template|params}}
        self._template_pattern = re.compile(r"\{\{([^\}|]+)(?:\|[^\}]+)?\}\}")

        # Pattern for file references [[File:...]] or [[Image:...]]
        self._file_pattern = re.compile(
            r"\[\[(?:File|Image):([^\]|]+)(?:\|[^\]]+)?\]\]", re.IGNORECASE
        )

        # Pattern for category memberships [[Category:...]]
        self._category_pattern = re.compile(
            r"\[\[Category:([^\]|]+)(?:\|[^\]]+)?\]\]", re.IGNORECASE
        )

    def extract_links(self, page_id: int, wikitext: str) -> List[Link]:
        """
        Extract all internal links from wikitext content.

        Parses the wikitext and extracts all four types of internal links:
        page links, template transclusions, file references, and category
        memberships. Handles title normalization and deduplication.

        Args:
            page_id: The ID of the page containing this wikitext (source page)
            wikitext: The MediaWiki wikitext content to parse

        Returns:
            List of Link objects representing all unique links found in the wikitext.
            Links are deduplicated (same target + type appears only once).
            List is sorted by link type, then target title for consistency.

        Example:
            >>> extractor = LinkExtractor()
            >>> wikitext = '''
            ... Visit [[Main Page]] for help.
            ... {{Stub}}
            ... [[File:Logo.png]]
            ... [[Category:Pages]]
            ... '''
            >>> links = extractor.extract_links(1, wikitext)
            >>> [link.link_type for link in links]
            ['page', 'template', 'file', 'category']

        Note:
            - Duplicate links (same target appearing multiple times) are deduplicated
            - Titles are normalized: underscores -> spaces, whitespace trimmed
            - Malformed wikitext is handled gracefully (invalid links are skipped)
            - Empty wikitext returns empty list
        """
        if not wikitext:
            return []

        # Remove HTML comments to avoid extracting commented-out links
        wikitext = self._remove_html_comments(wikitext)

        # Use a set to deduplicate links (frozen dataclass is hashable)
        unique_links: Set[Link] = set()

        # Extract page links
        for match in self._page_link_pattern.finditer(wikitext):
            target = self._normalize_title(match.group(1))
            if target:  # Skip empty titles
                try:
                    link = Link(
                        source_page_id=page_id, target_title=target, link_type="page"
                    )
                    unique_links.add(link)
                except ValueError:
                    # Skip invalid links (validation failed)
                    pass

        # Extract template transclusions
        for match in self._template_pattern.finditer(wikitext):
            target = self._normalize_title(match.group(1))
            if target:  # Skip empty titles
                try:
                    link = Link(
                        source_page_id=page_id,
                        target_title=target,
                        link_type="template",
                    )
                    unique_links.add(link)
                except ValueError:
                    # Skip invalid links
                    pass

        # Extract file references
        for match in self._file_pattern.finditer(wikitext):
            target = self._normalize_title(match.group(1))
            if target:  # Skip empty titles
                try:
                    link = Link(
                        source_page_id=page_id, target_title=target, link_type="file"
                    )
                    unique_links.add(link)
                except ValueError:
                    # Skip invalid links
                    pass

        # Extract category memberships
        for match in self._category_pattern.finditer(wikitext):
            target = self._normalize_title(match.group(1))
            if target:  # Skip empty titles
                try:
                    link = Link(
                        source_page_id=page_id,
                        target_title=target,
                        link_type="category",
                    )
                    unique_links.add(link)
                except ValueError:
                    # Skip invalid links
                    pass

        # Convert set to list and sort for consistent ordering
        return sorted(
            list(unique_links), key=lambda link: (link.link_type, link.target_title)
        )

    def _normalize_title(self, title: str) -> str:
        """
        Normalize a wiki title by replacing underscores with spaces and stripping whitespace.

        Args:
            title: The raw title extracted from wikitext

        Returns:
            Normalized title with underscores replaced by spaces and whitespace trimmed

        Example:
            >>> extractor = LinkExtractor()
            >>> extractor._normalize_title("Main_Page  ")
            'Main Page'
            >>> extractor._normalize_title("  Help_Topics  ")
            'Help Topics'
        """
        # Replace underscores with spaces (MediaWiki convention)
        title = title.replace("_", " ")

        # Strip leading/trailing whitespace
        title = title.strip()

        return title

    def _remove_html_comments(self, wikitext: str) -> str:
        """
        Remove HTML comments from wikitext.

        This prevents extraction of links that are commented out in the wiki source.

        Args:
            wikitext: The wikitext content

        Returns:
            Wikitext with HTML comments removed

        Example:
            >>> extractor = LinkExtractor()
            >>> text = "[[Real]] <!-- [[Commented]] --> [[Another]]"
            >>> extractor._remove_html_comments(text)
            '[[Real]]  [[Another]]'
        """
        # Remove HTML comments: <!-- ... -->
        return re.sub(r"<!--.*?-->", "", wikitext, flags=re.DOTALL)
