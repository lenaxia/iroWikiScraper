"""MediaWiki XML export functionality."""

from scraper.export.schema import MEDIAWIKI_NS, MEDIAWIKI_VERSION, MEDIAWIKI_NAMESPACES
from scraper.export.xml_generator import XMLGenerator
from scraper.export.xml_exporter import XMLExporter

__all__ = [
    "MEDIAWIKI_NS",
    "MEDIAWIKI_VERSION",
    "MEDIAWIKI_NAMESPACES",
    "XMLGenerator",
    "XMLExporter",
]
