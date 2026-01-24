"""MediaWiki XML export schema definitions.

This module defines the structure and constants for generating MediaWiki-compatible
XML exports according to the MediaWiki export schema version 0.11.

References:
    - https://www.mediawiki.org/xml/export-0.11.xsd
    - https://www.mediawiki.org/wiki/Help:Export
"""

# MediaWiki XML namespace and version
MEDIAWIKI_NS = "http://www.mediawiki.org/xml/export-0.11/"
MEDIAWIKI_VERSION = "0.11"
MEDIAWIKI_LANG = "en"

# MediaWiki namespace definitions
# Maps namespace ID to namespace name prefix
MEDIAWIKI_NAMESPACES = {
    -2: "Media",
    -1: "Special",
    0: "",  # Main/Article namespace (no prefix)
    1: "Talk",
    2: "User",
    3: "User talk",
    4: "iRO Wiki",  # Project namespace (site-specific)
    5: "iRO Wiki talk",
    6: "File",
    7: "File talk",
    8: "MediaWiki",
    9: "MediaWiki talk",
    10: "Template",
    11: "Template talk",
    12: "Help",
    13: "Help talk",
    14: "Category",
    15: "Category talk",
}

# Case sensitivity for namespaces ("first-letter" or "case-sensitive")
NAMESPACE_CASE = "first-letter"

# Content model and format
CONTENT_MODEL = "wikitext"
CONTENT_FORMAT = "text/x-wiki"

# Site information
SITE_NAME = "iRO Wiki"
SITE_DBNAME = "irowiki"
SITE_BASE_URL = "https://irowiki.org/wiki/Main_Page"
SITE_GENERATOR = "iRO Wiki Scraper"
