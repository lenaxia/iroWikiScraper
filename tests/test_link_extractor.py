"""Tests for the LinkExtractor and Link model."""

import pytest
import time
from pathlib import Path
from scraper.storage.models import Link
from scraper.scrapers.link_extractor import LinkExtractor


# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "wikitext"


@pytest.fixture
def simple_wikitext():
    """Load simple page fixture."""
    return (FIXTURES_DIR / "simple_page.txt").read_text()


@pytest.fixture
def complex_wikitext():
    """Load complex page fixture."""
    return (FIXTURES_DIR / "complex_page.txt").read_text()


@pytest.fixture
def template_heavy_wikitext():
    """Load template-heavy page fixture."""
    return (FIXTURES_DIR / "template_heavy.txt").read_text()


@pytest.fixture
def file_references_wikitext():
    """Load file references page fixture."""
    return (FIXTURES_DIR / "file_references.txt").read_text()


@pytest.fixture
def categories_wikitext():
    """Load categories page fixture."""
    return (FIXTURES_DIR / "categories.txt").read_text()


@pytest.fixture
def nested_links_wikitext():
    """Load nested links page fixture."""
    return (FIXTURES_DIR / "nested_links.txt").read_text()


@pytest.fixture
def malformed_wikitext():
    """Load malformed wikitext fixture."""
    return (FIXTURES_DIR / "malformed.txt").read_text()


@pytest.fixture
def empty_wikitext():
    """Load empty page fixture."""
    return (FIXTURES_DIR / "empty.txt").read_text()


@pytest.fixture
def no_links_wikitext():
    """Load no links page fixture."""
    return (FIXTURES_DIR / "no_links.txt").read_text()


@pytest.fixture
def extractor():
    """Create a LinkExtractor instance."""
    return LinkExtractor()


class TestLinkModel:
    """Tests for Link dataclass validation and creation."""

    def test_link_creation_valid(self):
        """Test creating a valid link with all required fields."""
        link = Link(source_page_id=1, target_title="Main Page", link_type="page")

        assert link.source_page_id == 1
        assert link.target_title == "Main Page"
        assert link.link_type == "page"

    def test_link_creation_all_link_types(self):
        """Test creating links with all valid link types."""
        for link_type in ["page", "template", "file", "category"]:
            link = Link(source_page_id=1, target_title="Target", link_type=link_type)
            assert link.link_type == link_type

    def test_link_invalid_source_page_id_zero(self):
        """Test that source_page_id of 0 raises ValueError."""
        with pytest.raises(
            ValueError, match="source_page_id must be a positive integer"
        ):
            Link(source_page_id=0, target_title="Target", link_type="page")

    def test_link_invalid_source_page_id_negative(self):
        """Test that negative source_page_id raises ValueError."""
        with pytest.raises(
            ValueError, match="source_page_id must be a positive integer"
        ):
            Link(source_page_id=-1, target_title="Target", link_type="page")

    def test_link_invalid_target_title_empty(self):
        """Test that empty target_title raises ValueError."""
        with pytest.raises(ValueError, match="target_title cannot be empty"):
            Link(source_page_id=1, target_title="", link_type="page")

    def test_link_invalid_target_title_whitespace(self):
        """Test that whitespace-only target_title raises ValueError."""
        with pytest.raises(ValueError, match="target_title cannot be empty"):
            Link(source_page_id=1, target_title="   ", link_type="page")

    def test_link_invalid_link_type(self):
        """Test that invalid link_type raises ValueError."""
        with pytest.raises(ValueError, match="link_type must be one of"):
            Link(source_page_id=1, target_title="Target", link_type="invalid")

    def test_link_frozen_dataclass(self):
        """Test that Link is immutable (frozen)."""
        link = Link(source_page_id=1, target_title="Target", link_type="page")

        with pytest.raises(AttributeError):
            link.source_page_id = 2

    def test_link_equality(self):
        """Test that Links with same values are equal."""
        link1 = Link(source_page_id=1, target_title="Target", link_type="page")
        link2 = Link(source_page_id=1, target_title="Target", link_type="page")

        assert link1 == link2

    def test_link_inequality(self):
        """Test that Links with different values are not equal."""
        link1 = Link(source_page_id=1, target_title="Target1", link_type="page")
        link2 = Link(source_page_id=1, target_title="Target2", link_type="page")

        assert link1 != link2

    def test_link_hashable(self):
        """Test that Link is hashable and can be used in sets."""
        link1 = Link(source_page_id=1, target_title="Target", link_type="page")
        link2 = Link(source_page_id=1, target_title="Target", link_type="page")
        link3 = Link(source_page_id=1, target_title="Other", link_type="page")

        link_set = {link1, link2, link3}
        assert len(link_set) == 2  # link1 and link2 are same


class TestLinkExtractorInit:
    """Tests for LinkExtractor initialization."""

    def test_extractor_initialization(self, extractor):
        """Test that LinkExtractor initializes successfully."""
        assert extractor is not None
        assert isinstance(extractor, LinkExtractor)

    def test_extractor_has_patterns(self, extractor):
        """Test that LinkExtractor has regex patterns compiled."""
        # Check that pattern attributes exist
        assert hasattr(extractor, "_page_link_pattern")
        assert hasattr(extractor, "_template_pattern")
        assert hasattr(extractor, "_file_pattern")
        assert hasattr(extractor, "_category_pattern")


class TestLinkExtractorPageLinks:
    """Tests for extracting regular page links."""

    def test_extract_simple_page_links(self, extractor, simple_wikitext):
        """Test extracting simple [[Page]] links."""
        links = extractor.extract_links(1, simple_wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        assert "Main Page" in titles
        assert "Help" in titles
        assert "Poring" in titles
        assert "Drops" in titles
        assert "Equipment" in titles

    def test_extract_links_with_display_text(self, extractor):
        """Test extracting links with display text [[Page|Display]]."""
        wikitext = "Visit [[Main Page|the homepage]] for more info."
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 1
        assert page_links[0].target_title == "Main Page"

    def test_extract_links_with_namespace(self, extractor):
        """Test extracting links with namespace [[Help:Editing]]."""
        wikitext = "See [[Help:Editing]] and [[Template:Infobox]]."
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        assert "Help:Editing" in titles
        # Note: Template:Infobox should be page link, not template (templates use {{}})

    def test_normalize_titles_underscores_to_spaces(self, extractor):
        """Test that underscores in titles are normalized to spaces."""
        wikitext = "[[Main_Page]] and [[Help_Topics]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        assert "Main Page" in titles
        assert "Help Topics" in titles

    def test_normalize_titles_strip_whitespace(self, extractor):
        """Test that whitespace in titles is stripped."""
        wikitext = "[[ Main Page ]] and [[  Help  ]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        assert "Main Page" in titles
        assert "Help" in titles

    def test_deduplicate_duplicate_links(self, extractor):
        """Test that duplicate links are deduplicated."""
        wikitext = """
        [[Poring]] is cute.
        [[Poring]] drops items.
        [[Poring]] is level 1.
        """
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 1
        assert page_links[0].target_title == "Poring"

    def test_extract_empty_wikitext(self, extractor, empty_wikitext):
        """Test extracting from empty wikitext returns empty list."""
        links = extractor.extract_links(1, empty_wikitext)
        assert links == []

    def test_extract_no_links(self, extractor, no_links_wikitext):
        """Test extracting from plain text with no links."""
        links = extractor.extract_links(1, no_links_wikitext)
        assert links == []

    def test_source_page_id_preserved(self, extractor, simple_wikitext):
        """Test that source_page_id is correctly set on all links."""
        links = extractor.extract_links(42, simple_wikitext)

        for link in links:
            assert link.source_page_id == 42


class TestLinkExtractorTemplates:
    """Tests for extracting template transclusions."""

    def test_extract_simple_templates(self, extractor, template_heavy_wikitext):
        """Test extracting {{Template}} transclusions."""
        links = extractor.extract_links(1, template_heavy_wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        titles = {link.target_title for link in template_links}

        assert "Stub" in titles
        assert "Cleanup" in titles
        assert "Infobox Item" in titles

    def test_extract_templates_with_parameters(self, extractor):
        """Test extracting templates with parameters {{Template|param}}."""
        wikitext = "{{Infobox Monster|name=Poring|level=1}}"
        links = extractor.extract_links(1, wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        assert len(template_links) == 1
        assert template_links[0].target_title == "Infobox Monster"

    def test_extract_nested_templates(self, extractor, nested_links_wikitext):
        """Test extracting nested templates."""
        links = extractor.extract_links(1, nested_links_wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        titles = {link.target_title for link in template_links}

        # Should extract both ItemBox and Item templates
        assert "ItemBox" in titles or "Item" in titles

    def test_deduplicate_templates(self, extractor):
        """Test that duplicate templates are deduplicated."""
        wikitext = "{{Stub}} {{Stub}} {{Stub}}"
        links = extractor.extract_links(1, wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        assert len(template_links) == 1

    def test_template_normalize_titles(self, extractor):
        """Test that template titles are normalized."""
        wikitext = "{{ Infobox_Monster }} and {{  NavBox  }}"
        links = extractor.extract_links(1, wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        titles = {link.target_title for link in template_links}

        assert "Infobox Monster" in titles
        assert "NavBox" in titles


class TestLinkExtractorFileReferences:
    """Tests for extracting file references."""

    def test_extract_file_references(self, extractor, file_references_wikitext):
        """Test extracting [[File:Example.png]] references."""
        links = extractor.extract_links(1, file_references_wikitext)

        file_links = [link for link in links if link.link_type == "file"]
        titles = {link.target_title for link in file_links}

        assert "Monster Poring.png" in titles or "Monster_Poring.png" in titles
        assert "Icon Apple.png" in titles or "Icon_Apple.png" in titles

    def test_extract_image_alias(self, extractor):
        """Test extracting [[Image:Example.png]] (alias for File:)."""
        wikitext = "[[Image:Banner.jpg]]"
        links = extractor.extract_links(1, wikitext)

        file_links = [link for link in links if link.link_type == "file"]
        assert len(file_links) == 1
        assert "Banner.jpg" in file_links[0].target_title

    def test_extract_file_with_parameters(self, extractor):
        """Test extracting files with parameters [[File:X|thumb|caption]]."""
        wikitext = "[[File:Poring.png|thumb|200px|A cute Poring]]"
        links = extractor.extract_links(1, wikitext)

        file_links = [link for link in links if link.link_type == "file"]
        assert len(file_links) == 1
        assert file_links[0].target_title == "Poring.png"

    def test_file_not_page_link(self, extractor):
        """Test that file references are not classified as page links."""
        wikitext = "[[File:Example.png]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 0

    def test_deduplicate_files(self, extractor):
        """Test that duplicate file references are deduplicated."""
        wikitext = "[[File:Logo.png]] and [[File:Logo.png]]"
        links = extractor.extract_links(1, wikitext)

        file_links = [link for link in links if link.link_type == "file"]
        assert len(file_links) == 1


class TestLinkExtractorCategories:
    """Tests for extracting category memberships."""

    def test_extract_categories(self, extractor, categories_wikitext):
        """Test extracting [[Category:Name]] memberships."""
        links = extractor.extract_links(1, categories_wikitext)

        category_links = [link for link in links if link.link_type == "category"]
        titles = {link.target_title for link in category_links}

        assert "Monsters" in titles
        assert "Drops" in titles
        assert "Prontera Field" in titles

    def test_extract_category_with_sort_key(self, extractor):
        """Test extracting category with sort key [[Category:Name|Sort]]."""
        wikitext = "[[Category:Level 1 Monsters|Poring]]"
        links = extractor.extract_links(1, wikitext)

        category_links = [link for link in links if link.link_type == "category"]
        assert len(category_links) == 1
        assert category_links[0].target_title == "Level 1 Monsters"

    def test_category_not_page_link(self, extractor):
        """Test that categories are not classified as page links."""
        wikitext = "[[Category:Monsters]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 0

    def test_deduplicate_categories(self, extractor):
        """Test that duplicate categories are deduplicated."""
        wikitext = "[[Category:Items]] [[Category:Items]]"
        links = extractor.extract_links(1, wikitext)

        category_links = [link for link in links if link.link_type == "category"]
        assert len(category_links) == 1


class TestLinkExtractorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_malformed_wikitext_unclosed_brackets(self, extractor, malformed_wikitext):
        """Test that malformed wikitext doesn't crash the extractor."""
        # Should not raise exception
        links = extractor.extract_links(1, malformed_wikitext)

        # Should still extract valid links
        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        # Should extract "Valid Link" which is valid
        assert "Valid Link" in titles

    def test_very_long_wikitext(self, extractor):
        """Test extracting from very long wikitext."""
        # Create 10,000 links
        wikitext = "\n".join([f"[[Page{i}]]" for i in range(10000)])
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 10000

    def test_unicode_characters_in_links(self, extractor):
        """Test extracting links with unicode characters."""
        wikitext = "[[日本語]] [[한국어]] [[Français]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        titles = {link.target_title for link in page_links}

        assert "日本語" in titles
        assert "한국어" in titles
        assert "Français" in titles

    def test_special_characters_in_links(self, extractor):
        """Test extracting links with special characters."""
        wikitext = "[[Page (Disambiguation)]] [[Page/Subpage]] [[Page#Section]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) >= 1  # At least one should be extracted

    def test_nested_brackets(self, extractor):
        """Test handling of nested brackets."""
        wikitext = "[[Outer [[Inner]] Outer]]"
        links = extractor.extract_links(1, wikitext)

        # Should handle gracefully, may extract inner or outer depending on implementation
        assert isinstance(links, list)

    def test_external_links_ignored(self, extractor):
        """Test that external links [http://...] are ignored."""
        wikitext = "[https://example.com External] and [[Internal]]"
        links = extractor.extract_links(1, wikitext)

        # Should only get the internal link
        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 1
        assert page_links[0].target_title == "Internal"

    def test_empty_link_brackets(self, extractor):
        """Test that empty brackets [[]] are ignored."""
        wikitext = "[[]] and [[Valid Link]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        assert len(page_links) == 1
        assert page_links[0].target_title == "Valid Link"

    def test_empty_template_brackets(self, extractor):
        """Test that empty template brackets {{}} are ignored."""
        wikitext = "{{}} and {{Valid Template}}"
        links = extractor.extract_links(1, wikitext)

        template_links = [link for link in links if link.link_type == "template"]
        assert len(template_links) == 1
        assert template_links[0].target_title == "Valid Template"

    def test_triple_brackets(self, extractor):
        """Test handling of triple brackets [[[...]]]."""
        wikitext = "[[[Triple]]] and [[Normal]]"
        links = extractor.extract_links(1, wikitext)

        # Should handle gracefully
        assert isinstance(links, list)

    def test_commented_links_ignored(self, extractor):
        """Test that links in HTML comments are ignored."""
        wikitext = "<!-- [[Commented Link]] --> [[Real Link]]"
        links = extractor.extract_links(1, wikitext)

        page_links = [link for link in links if link.link_type == "page"]

        # Should only extract Real Link, not Commented Link
        titles = {link.target_title for link in page_links}
        assert "Real Link" in titles
        assert "Commented Link" not in titles


class TestLinkExtractorIntegration:
    """Integration tests with complex pages."""

    def test_complex_page_all_link_types(self, extractor, complex_wikitext):
        """Test extracting all link types from complex page."""
        links = extractor.extract_links(1, complex_wikitext)

        # Should have all four types
        link_types = {link.link_type for link in links}
        assert "page" in link_types
        assert "template" in link_types
        assert "file" in link_types
        assert "category" in link_types

    def test_complex_page_correct_counts(self, extractor, complex_wikitext):
        """Test that complex page extracts reasonable number of links."""
        links = extractor.extract_links(1, complex_wikitext)

        page_links = [link for link in links if link.link_type == "page"]
        template_links = [link for link in links if link.link_type == "template"]
        file_links = [link for link in links if link.link_type == "file"]
        category_links = [link for link in links if link.link_type == "category"]

        # Should have some of each
        assert len(page_links) > 0
        assert len(template_links) > 0
        assert len(file_links) > 0
        assert len(category_links) > 0

    def test_nested_links_page(self, extractor, nested_links_wikitext):
        """Test extracting from page with nested structures."""
        links = extractor.extract_links(1, nested_links_wikitext)

        # Should extract links from various contexts
        page_links = [link for link in links if link.link_type == "page"]

        # Check that we got links from table, lists, etc.
        assert len(page_links) > 5

    def test_all_links_have_valid_attributes(self, extractor, complex_wikitext):
        """Test that all extracted links have valid attributes."""
        links = extractor.extract_links(1, complex_wikitext)

        for link in links:
            # Check required attributes
            assert link.source_page_id == 1
            assert link.source_page_id > 0
            assert link.target_title
            assert len(link.target_title.strip()) > 0
            assert link.link_type in ["page", "template", "file", "category"]

    def test_performance_large_page(self, extractor):
        """Test performance with large wikitext content."""
        # Create a large page with many links
        wikitext = "\n".join(
            [
                f"[[Page{i}]] {{{{Template{i}}}}} [[File:Image{i}.png]] [[Category:Cat{i}]]"
                for i in range(1000)
            ]
        )

        start_time = time.time()
        links = extractor.extract_links(1, wikitext)
        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (< 1 second)
        assert elapsed_time < 1.0

        # Should extract all links
        assert len(links) == 4000  # 1000 of each type
