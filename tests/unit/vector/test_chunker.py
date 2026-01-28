"""
Unit tests for WikiChunker class

Tests all chunking strategies, WikiText cleaning, and edge cases.
"""

import sys
from pathlib import Path

import pytest

# Skip all tests if numpy is not available (optional dependency)
pytest.importorskip("numpy")

# Skip all tests if numpy is not available (optional dependency)
pytest.importorskip("numpy")

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from vectorize_wiki import Chunk, WikiChunker  # noqa: E402


class TestWikiTextCleaning:
    """Test WikiText markup cleaning"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_clean_simple_text(self, sample_wiki_content):
        """Test cleaning plain text (no markup)"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["simple"])
        assert cleaned == "This is a simple page with plain text."

    def test_clean_internal_links(self, sample_wiki_content):
        """Test removal of internal wiki links"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["with_links"])

        # [[internal links]] -> internal links
        assert "internal links" in cleaned
        assert "[[" not in cleaned
        assert "]]" not in cleaned

        # [[Link|link with text]] -> link with text
        assert "link with text" in cleaned
        assert "Link|" not in cleaned

    def test_clean_external_links(self, sample_wiki_content):
        """Test removal of external links"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["with_links"])

        # [https://example.com Example Site] -> Example Site
        assert "Example Site" in cleaned
        assert "https://" not in cleaned
        assert "[" not in cleaned
        assert "]" not in cleaned

    def test_clean_templates(self, sample_wiki_content):
        """Test removal of MediaWiki templates"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["with_templates"])

        # Templates should be completely removed
        assert "{{" not in cleaned
        assert "}}" not in cleaned
        assert "templates" not in cleaned
        assert "param=value" not in cleaned

    def test_clean_formatting(self, sample_wiki_content):
        """Test removal of wiki formatting"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["with_formatting"])

        # '''bold text''' -> bold text
        assert "bold text" in cleaned
        assert "'''" not in cleaned

        # ''italic text'' -> italic text
        assert "italic text" in cleaned
        assert "''" not in cleaned

        # <b>HTML tags</b> -> HTML tags
        assert "HTML tags" in cleaned
        assert "<b>" not in cleaned
        assert "</b>" not in cleaned

    def test_clean_images(self, sample_wiki_content):
        """Test removal of image/file references"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["with_images"])

        # File references should be removed
        assert "File:" not in cleaned
        assert "Image:" not in cleaned
        assert "Example.jpg" not in cleaned
        assert "thumb" not in cleaned

    def test_clean_empty_string(self, sample_wiki_content):
        """Test cleaning empty string"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["empty"])
        assert cleaned == ""

    def test_clean_none(self):
        """Test cleaning None value"""
        cleaned = self.chunker.clean_wikitext(None)
        assert cleaned == ""

    def test_clean_whitespace_normalization(self):
        """Test whitespace is properly normalized"""
        text = "Text with    multiple   spaces\n\n\n\nand newlines"
        cleaned = self.chunker.clean_wikitext(text)

        # Multiple spaces -> single space
        assert "    " not in cleaned
        assert "multiple   spaces" not in cleaned

        # Multiple newlines -> double newline max
        assert "\n\n\n" not in cleaned

    def test_clean_complex_page(self, sample_wiki_content):
        """Test cleaning complex page with multiple markup types"""
        cleaned = self.chunker.clean_wikitext(sample_wiki_content["complex"])

        # Should have plain text content
        assert "complex page" in cleaned
        assert "History" in cleaned
        assert "Characteristics" in cleaned

        # Should not have markup
        assert "{{" not in cleaned
        assert "[[" not in cleaned
        assert "'''" not in cleaned
        assert "Category:" not in cleaned


class TestWordCount:
    """Test word counting utility"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_word_count_simple(self):
        """Test word count on simple text"""
        assert self.chunker.word_count("one two three") == 3

    def test_word_count_empty(self):
        """Test word count on empty string"""
        assert self.chunker.word_count("") == 0

    def test_word_count_single_word(self):
        """Test word count on single word"""
        assert self.chunker.word_count("word") == 1

    def test_word_count_multiple_spaces(self):
        """Test word count ignores extra spaces"""
        assert self.chunker.word_count("word   with    spaces") == 3


class TestPageLevelChunking:
    """Test page-level chunking strategy"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_chunk_simple_page(self):
        """Test chunking a simple page"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test_Page",
            "namespace": 0,
            "content": "This is a test page with enough content to not be filtered out.",
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_page_level(page_data))

        assert len(chunks) == 1
        assert chunks[0].page_id == 1
        assert chunks[0].page_title == "Test_Page"
        assert chunks[0].chunk_type == "page"
        assert "test page" in chunks[0].content.lower()

    def test_chunk_page_filters_short_content(self):
        """Test that very short pages are filtered out"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Short",
            "namespace": 0,
            "content": "Short.",  # Less than MIN_CHUNK_SIZE words
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_page_level(page_data))
        assert len(chunks) == 0

    def test_chunk_page_cleans_markup(self):
        """Test that page-level chunking cleans markup"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": "'''Bold text''' with [[links]] and {{templates}} repeated many times "
            * 10,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_page_level(page_data))

        assert len(chunks) == 1
        assert "'''" not in chunks[0].content
        assert "[[" not in chunks[0].content
        assert "{{" not in chunks[0].content


class TestSectionLevelChunking:
    """Test section-level chunking strategy"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_chunk_page_with_sections(self, sample_wiki_content):
        """Test chunking page with multiple sections"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test_Page",
            "namespace": 0,
            "content": sample_wiki_content["with_sections"],
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_section_level(page_data))

        # Should have intro + sections
        assert len(chunks) > 1

        # Check intro chunk
        intro_chunk = chunks[0]
        assert intro_chunk.section_title == "Introduction"
        assert intro_chunk.section_level == 1
        assert "introduction paragraph" in intro_chunk.content.lower()

        # Check named sections exist
        section_titles = [c.section_title for c in chunks]
        assert "First Section" in section_titles
        assert "Second Section" in section_titles
        assert "Subsection" in section_titles

    def test_chunk_section_levels(self):
        """Test that section levels are correctly identified"""
        content = """
Intro text here.

== Level 2 ==
Content.

=== Level 3 ===
More content.

==== Level 4 ====
Even more content.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_section_level(page_data))

        # Check section levels
        levels = {c.section_title: c.section_level for c in chunks if c.section_title}
        assert levels["Level 2"] == 2
        assert levels["Level 3"] == 3
        assert levels["Level 4"] == 4

    def test_chunk_section_filters_short_sections(self):
        """Test that very short sections are filtered out"""
        content = """
This is a good introduction with enough words to pass the filter.

== Short ==
Hi.

== Good Section ==
This section has enough content to not be filtered out during chunking.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_section_level(page_data))
        section_titles = [c.section_title for c in chunks]

        # Short section should be filtered
        assert "Short" not in section_titles
        # Good sections should remain
        assert "Introduction" in section_titles
        assert "Good Section" in section_titles

    def test_chunk_section_includes_heading_in_content(self):
        """Test that section heading is prepended to content"""
        content = """
== Test Section ==
Section content here.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_section_level(page_data))

        # Find the Test Section chunk
        test_chunk = [c for c in chunks if c.section_title == "Test Section"][0]

        # Heading should be in content for better context
        assert "Test Section" in test_chunk.content
        assert "Section content" in test_chunk.content

    def test_chunk_section_indices(self, sample_wiki_content):
        """Test that chunk indices are sequential"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": sample_wiki_content["with_sections"],
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_section_level(page_data))
        indices = [c.chunk_index for c in chunks]

        # Should be sequential starting from 0
        assert indices == list(range(len(chunks)))


class TestParagraphLevelChunking:
    """Test paragraph-level chunking strategy"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_chunk_multiple_paragraphs(self):
        """Test chunking page with multiple paragraphs"""
        content = """
First paragraph with enough content to pass the minimum word filter.

Second paragraph also with sufficient content for the chunking test.

Third paragraph continuing the pattern with enough words to include.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_paragraph_level(page_data))

        # Should have 3 chunks
        assert len(chunks) == 3
        assert all(c.chunk_type == "paragraph" for c in chunks)

        # Check content
        assert "First paragraph" in chunks[0].content
        assert "Second paragraph" in chunks[1].content
        assert "Third paragraph" in chunks[2].content

    def test_chunk_paragraph_filters_short(self):
        """Test that very short paragraphs are filtered"""
        content = """
This is a good paragraph with many words that will pass the minimum filter.

Short.

Another good paragraph with enough words to be included in the output.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_paragraph_level(page_data))

        # Should only have 2 chunks (short one filtered)
        assert len(chunks) == 2
        assert "Short" not in " ".join(c.content for c in chunks)

    def test_chunk_paragraph_splits_long(self, sample_wiki_content):
        """Test that very long paragraphs are split"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": sample_wiki_content["long_paragraph"],
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_paragraph_level(page_data))

        # Long paragraph should be split into multiple chunks
        assert len(chunks) > 1

        # Each chunk should be under MAX_CHUNK_SIZE
        for chunk in chunks:
            assert self.chunker.word_count(chunk.content) <= self.chunker.MAX_CHUNK_SIZE

    def test_chunk_paragraph_tracks_sections(self):
        """Test that paragraphs track their parent section"""
        content = """
Section Header:

Paragraph under this section with enough content to be included.

Another Section:

Paragraph under second section also with sufficient content.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_paragraph_level(page_data))

        # Check section attribution
        assert chunks[0].section_title == "Section Header"
        assert chunks[1].section_title == "Another Section"


class TestChunkGeneration:
    """Test Chunk object generation and properties"""

    def test_chunk_to_dict(self):
        """Test Chunk serialization to dict"""
        chunk = Chunk(
            page_id=1,
            revision_id=101,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="section",
            section_title="Intro",
            section_level=2,
            chunk_index=0,
            metadata={"key": "value"},
        )

        data = chunk.to_dict()

        assert data["page_id"] == 1
        assert data["revision_id"] == 101
        assert data["page_title"] == "Test"
        assert data["content"] == "Content"
        assert data["chunk_type"] == "section"
        assert data["section_title"] == "Intro"
        assert data["metadata"]["key"] == "value"

    def test_chunk_get_id_page(self):
        """Test unique ID generation for page chunks"""
        chunk = Chunk(
            page_id=123,
            revision_id=456,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="page",
            chunk_index=0,
            metadata={},
        )

        assert chunk.get_id() == "page_123"

    def test_chunk_get_id_section(self):
        """Test unique ID generation for section chunks"""
        chunk = Chunk(
            page_id=123,
            revision_id=456,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="section",
            section_title="Test Section",
            chunk_index=0,
            metadata={},
        )

        chunk_id = chunk.get_id()
        assert chunk_id.startswith("page_123_section_")
        assert "test_section" in chunk_id  # Slugified

    def test_chunk_get_id_paragraph(self):
        """Test unique ID generation for paragraph chunks"""
        chunk = Chunk(
            page_id=123,
            revision_id=456,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="paragraph",
            chunk_index=5,
            metadata={},
        )

        assert chunk.get_id() == "page_123_para_5"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        self.chunker = WikiChunker()

    def test_empty_page_content(self):
        """Test handling of empty page content"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Empty",
            "namespace": 0,
            "content": "",
            "metadata": {},
        }

        # All chunking strategies should handle empty content
        assert list(self.chunker.chunk_page_level(page_data)) == []
        assert list(self.chunker.chunk_section_level(page_data)) == []
        assert list(self.chunker.chunk_paragraph_level(page_data)) == []

    def test_only_markup_content(self):
        """Test page with only markup (no actual content)"""
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Markup",
            "namespace": 0,
            "content": "{{template}} [[link]] [[Category:Test]]",
            "metadata": {},
        }

        chunks = list(self.chunker.chunk_page_level(page_data))

        # Should be filtered out due to insufficient content
        assert len(chunks) == 0

    def test_malformed_section_headers(self):
        """Test handling of malformed section headers"""
        content = """
Normal intro.

= Wrong level =
Content.

== Good Section ==
More content here with many words.

=== Unmatched ===
Final content.
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        # Should not crash on malformed headers
        chunks = list(self.chunker.chunk_section_level(page_data))
        assert len(chunks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
