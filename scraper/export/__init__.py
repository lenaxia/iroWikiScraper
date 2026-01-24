"""MediaWiki XML export functionality."""

from scraper.export.schema import MEDIAWIKI_NAMESPACES, MEDIAWIKI_NS, MEDIAWIKI_VERSION
from scraper.export.xml_exporter import XMLExporter
from scraper.export.xml_generator import XMLGenerator

__all__ = [
    "MEDIAWIKI_NS",
    "MEDIAWIKI_VERSION",
    "MEDIAWIKI_NAMESPACES",
    "XMLGenerator",
    "XMLExporter",
]
