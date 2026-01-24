"""Tests for MediaWiki XML schema definitions."""

import pytest

from scraper.export.schema import (
    MEDIAWIKI_NAMESPACES,
    MEDIAWIKI_NS,
    MEDIAWIKI_VERSION,
    SITE_DBNAME,
    SITE_NAME,
)


class TestSchema:
    """Test MediaWiki XML schema constants."""

    def test_namespace_url(self):
        """Test MediaWiki namespace URL is correct."""
        assert MEDIAWIKI_NS == "http://www.mediawiki.org/xml/export-0.11/"

    def test_version(self):
        """Test MediaWiki export version."""
        assert MEDIAWIKI_VERSION == "0.11"

    def test_namespaces_includes_main(self):
        """Test namespaces include main namespace (0)."""
        assert 0 in MEDIAWIKI_NAMESPACES
        assert MEDIAWIKI_NAMESPACES[0] == ""  # Main namespace has no prefix

    def test_namespaces_includes_standard(self):
        """Test namespaces include standard MediaWiki namespaces."""
        # Check standard namespaces
        assert MEDIAWIKI_NAMESPACES[1] == "Talk"
        assert MEDIAWIKI_NAMESPACES[2] == "User"
        assert MEDIAWIKI_NAMESPACES[6] == "File"
        assert MEDIAWIKI_NAMESPACES[10] == "Template"
        assert MEDIAWIKI_NAMESPACES[14] == "Category"

    def test_namespaces_includes_irowiki_specific(self):
        """Test namespaces include iRO Wiki specific namespaces."""
        assert MEDIAWIKI_NAMESPACES[4] == "iRO Wiki"
        assert MEDIAWIKI_NAMESPACES[5] == "iRO Wiki talk"

    def test_site_constants(self):
        """Test site-specific constants are set."""
        assert SITE_NAME == "iRO Wiki"
        assert SITE_DBNAME == "irowiki"
