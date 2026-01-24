"""Generate MediaWiki XML elements from database models.

This module provides functions to convert database models (Page, Revision, etc.)
into MediaWiki-compatible XML elements.
"""

import html
from typing import List, Optional
from datetime import datetime

from scraper.storage.models import Page, Revision
from scraper.export.schema import (
    MEDIAWIKI_NS,
    MEDIAWIKI_VERSION,
    MEDIAWIKI_LANG,
    MEDIAWIKI_NAMESPACES,
    NAMESPACE_CASE,
    CONTENT_MODEL,
    CONTENT_FORMAT,
    SITE_NAME,
    SITE_DBNAME,
    SITE_BASE_URL,
    SITE_GENERATOR,
)


class XMLGenerator:
    """Generates MediaWiki XML elements from database models."""

    @staticmethod
    def escape_xml(text: str) -> str:
        """
        Escape special XML characters.

        Args:
            text: Text to escape

        Returns:
            XML-escaped text
        """
        return html.escape(text, quote=True)

    @staticmethod
    def generate_xml_header() -> str:
        """
        Generate XML declaration and opening mediawiki tag.

        Returns:
            XML header string
        """
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<mediawiki xmlns="{MEDIAWIKI_NS}" '
            f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:schemaLocation="{MEDIAWIKI_NS} '
            f'http://www.mediawiki.org/xml/export-{MEDIAWIKI_VERSION}.xsd" '
            f'version="{MEDIAWIKI_VERSION}" '
            f'xml:lang="{MEDIAWIKI_LANG}">\n'
        )

    @staticmethod
    def generate_siteinfo() -> str:
        """
        Generate <siteinfo> XML element with wiki metadata.

        Returns:
            Siteinfo XML string
        """
        namespaces_xml = []
        for ns_id, ns_name in sorted(MEDIAWIKI_NAMESPACES.items()):
            if ns_name == "":
                # Main namespace has no name attribute
                namespaces_xml.append(
                    f'    <namespace key="{ns_id}" case="{NAMESPACE_CASE}" />'
                )
            else:
                escaped_name = XMLGenerator.escape_xml(ns_name)
                namespaces_xml.append(
                    f'    <namespace key="{ns_id}" case="{NAMESPACE_CASE}">{escaped_name}</namespace>'
                )

        return (
            "  <siteinfo>\n"
            f"    <sitename>{XMLGenerator.escape_xml(SITE_NAME)}</sitename>\n"
            f"    <dbname>{XMLGenerator.escape_xml(SITE_DBNAME)}</dbname>\n"
            f"    <base>{XMLGenerator.escape_xml(SITE_BASE_URL)}</base>\n"
            f"    <generator>{XMLGenerator.escape_xml(SITE_GENERATOR)}</generator>\n"
            f"    <case>{NAMESPACE_CASE}</case>\n"
            "    <namespaces>\n" + "\n".join(namespaces_xml) + "\n"
            "    </namespaces>\n"
            "  </siteinfo>\n"
        )

    @staticmethod
    def generate_revision_xml(revision: Revision) -> str:
        """
        Generate <revision> XML element from a Revision model.

        Args:
            revision: Revision object to convert

        Returns:
            Revision XML string
        """
        # Format timestamp in ISO 8601 format
        timestamp = revision.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build contributor XML
        contributor_xml = "      <contributor>\n"
        if revision.user:
            contributor_xml += f"        <username>{XMLGenerator.escape_xml(revision.user)}</username>\n"
            if revision.user_id is not None:
                contributor_xml += f"        <id>{revision.user_id}</id>\n"
        else:
            # Deleted or anonymous user
            contributor_xml += "        <username />\n"
        contributor_xml += "      </contributor>\n"

        # Build comment XML
        comment_xml = ""
        if revision.comment:
            comment_xml = f"      <comment>{XMLGenerator.escape_xml(revision.comment)}</comment>\n"
        else:
            comment_xml = "      <comment />\n"

        # Build minor edit flag
        minor_xml = "      <minor />\n" if revision.minor else ""

        # Build text element with content
        content_bytes = len(revision.content.encode("utf-8"))
        text_xml = (
            f'      <text bytes="{content_bytes}" xml:space="preserve">'
            f"{XMLGenerator.escape_xml(revision.content)}</text>\n"
        )

        # Assemble revision XML
        revision_xml = f"    <revision>\n      <id>{revision.revision_id}</id>\n"

        # Add parent_id if present
        if revision.parent_id is not None:
            revision_xml += f"      <parentid>{revision.parent_id}</parentid>\n"

        revision_xml += (
            f"      <timestamp>{timestamp}</timestamp>\n"
            + contributor_xml
            + comment_xml
            + minor_xml
            + f"      <model>{CONTENT_MODEL}</model>\n"
            f"      <format>{CONTENT_FORMAT}</format>\n"
            + text_xml
            + f"      <sha1>{revision.sha1}</sha1>\n"
            "    </revision>\n"
        )

        return revision_xml

    @staticmethod
    def generate_page_xml(page: Page, revisions: List[Revision]) -> str:
        """
        Generate <page> XML element from a Page model and its revisions.

        Args:
            page: Page object to convert
            revisions: List of revisions for this page (should be in chronological order)

        Returns:
            Page XML string including all revisions
        """
        # Generate redirect tag if applicable
        redirect_xml = ""
        if page.is_redirect:
            # Note: We don't have the redirect target in Page model,
            # so we just mark it as a redirect without target
            redirect_xml = "    <redirect />\n"

        # Generate revisions XML
        revisions_xml = ""
        for revision in revisions:
            revisions_xml += XMLGenerator.generate_revision_xml(revision)

        # Assemble page XML
        page_xml = (
            "  <page>\n"
            f"    <title>{XMLGenerator.escape_xml(page.title)}</title>\n"
            f"    <ns>{page.namespace}</ns>\n"
            f"    <id>{page.page_id}</id>\n"
            + redirect_xml
            + revisions_xml
            + "  </page>\n"
        )

        return page_xml

    @staticmethod
    def generate_xml_footer() -> str:
        """
        Generate closing mediawiki tag.

        Returns:
            XML footer string
        """
        return "</mediawiki>\n"
