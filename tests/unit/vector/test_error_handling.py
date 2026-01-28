"""
Error handling and unhappy path tests for vectorization

Tests failure modes, edge cases, and error recovery.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from vectorize_wiki import (
    Chunk,
    DatabaseReader,
    WikiChunker,
)


class TestMalformedInputs:
    """Test handling of malformed or invalid inputs"""

    def test_chunker_none_content(self):
        """Test chunking with None content"""
        chunker = WikiChunker()
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": None,  # None instead of string
            "metadata": {},
        }

        # Should handle None gracefully
        chunks = list(chunker.chunk_section_level(page_data))
        assert chunks == []

    def test_chunker_missing_content_key(self):
        """Test chunking with missing content key"""
        chunker = WikiChunker()
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            # Missing "content" key
            "metadata": {},
        }

        # Should raise KeyError
        with pytest.raises(KeyError):
            list(chunker.chunk_section_level(page_data))

    def test_chunker_binary_content(self):
        """Test chunking with binary data"""
        chunker = WikiChunker()
        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": b"\x00\x01\x02Binary data",  # Binary
            "metadata": {},
        }

        # Should handle or raise appropriate error
        with pytest.raises((TypeError, AttributeError)):
            list(chunker.chunk_section_level(page_data))

    def test_chunker_very_large_content(self):
        """Test chunking extremely large content"""
        chunker = WikiChunker()

        # 1MB of content
        large_content = "word " * 200000

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Large",
            "namespace": 0,
            "content": large_content,
            "metadata": {},
        }

        # Should handle without crashing
        chunks = list(chunker.chunk_paragraph_level(page_data))

        # Should be split into multiple chunks
        assert len(chunks) > 1

        # No chunk should be too large
        for chunk in chunks:
            word_count = chunker.word_count(chunk.content)
            assert word_count <= chunker.MAX_CHUNK_SIZE * 1.1  # Allow small overflow

    def test_chunker_unicode_content(self):
        """Test chunking with various unicode characters"""
        chunker = WikiChunker()

        unicode_content = """
        This has various unicode: 
        émojis 🎮, 中文, العربية, עברית, 日本語
        Special chars: © ® ™ € ¥ £
        Math: ∑ ∫ ∂ √ ∞
        """ * 10  # Repeat to meet minimum size

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Unicode",
            "namespace": 0,
            "content": unicode_content,
            "metadata": {},
        }

        # Should handle unicode properly
        chunks = list(chunker.chunk_section_level(page_data))
        assert len(chunks) > 0

        # Content should be preserved
        for chunk in chunks:
            assert isinstance(chunk.content, str)


class TestDatabaseErrorHandling:
    """Test database error conditions"""

    def test_corrupted_database(self, tmp_path):
        """Test handling corrupted database file"""
        db_path = tmp_path / "corrupted.db"

        # Create invalid database file
        with open(db_path, "w") as f:
            f.write("This is not a valid SQLite database")

        # Should raise appropriate error
        with pytest.raises(Exception):
            with DatabaseReader(str(db_path)) as db:
                db.count_pages()

    def test_database_missing_columns(self, tmp_path):
        """Test database with missing required columns"""
        import sqlite3

        db_path = tmp_path / "incomplete.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table with missing columns
        cursor.execute("""
            CREATE TABLE pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL
                -- Missing: namespace, latest_revision_id, is_redirect
            )
        """)

        conn.commit()
        conn.close()

        # Should raise error when querying
        with pytest.raises(Exception):
            with DatabaseReader(str(db_path)) as db:
                db.count_pages()

    def test_database_connection_lost(self, test_database):
        """Test handling lost database connection"""
        db = DatabaseReader(str(test_database))

        # Enter context
        db.__enter__()

        # Forcibly close connection
        if db.conn:
            db.conn.close()
            db.conn = None

        # Operations should fail gracefully
        with pytest.raises((AttributeError, Exception)):
            db.count_pages()


class TestVectorDBErrorHandling:
    """Test vector database error handling"""

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_invalid_dimensions(self, temp_vector_storage):
        """Test Qdrant with invalid embedding dimensions"""
        pytest.importorskip("qdrant_client")

        from vectorize_wiki import QdrantWriter

        output_path = temp_vector_storage / "qdrant"

        # Invalid dimension (negative)
        with pytest.raises((ValueError, Exception)):
            writer = QdrantWriter(
                str(output_path),
                "test-model",
                -1,  # Invalid
            )
            writer.initialize()

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_duplicate_collection(
        self, temp_vector_storage, mock_embedding_model
    ):
        """Test creating collection that already exists"""
        pytest.importorskip("qdrant_client")

        from vectorize_wiki import QdrantWriter

        output_path = temp_vector_storage / "qdrant"

        # First writer
        writer1 = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )
        writer1.initialize()

        # Second writer with same collection - should recreate
        writer2 = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )
        writer2.initialize()  # Should not crash

        # Collection should be empty after recreation
        info = writer2.client.get_collection("irowiki")
        assert info.points_count == 0

    def test_chromadb_invalid_metadata_types(
        self, temp_vector_storage, mock_embedding_model
    ):
        """Test ChromaDB with invalid metadata types"""
        pytest.importorskip("chromadb")

        import numpy as np
        from vectorize_wiki import ChromaDBWriter

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Create chunk with complex metadata
        chunk = Chunk(
            page_id=1,
            revision_id=101,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="section",
            chunk_index=0,
            metadata={"nested": {"dict": "value"}},  # ChromaDB doesn't support nested
        )

        embedding = np.random.rand(1, mock_embedding_model.embedding_dim).astype(
            np.float32
        )

        # Should handle or raise appropriate error
        # ChromaDB converts metadata fields appropriately
        writer.add_chunks([chunk], embedding)  # Should not crash


class TestResourceExhaustion:
    """Test behavior under resource constraints"""

    def test_memory_efficient_iteration(self, test_database):
        """Test that iteration doesn't load everything into memory"""
        # This test ensures we're using generators properly

        with DatabaseReader(str(test_database)) as db:
            iterator = db.iter_pages()

            # Should be a generator/iterator
            assert hasattr(iterator, "__iter__")
            assert hasattr(iterator, "__next__")

            # Get first item
            first = next(iterator)
            assert first is not None

            # Iterator should still be usable
            try:
                second = next(iterator)
            except StopIteration:
                # OK if only one page
                pass

    def test_large_batch_processing(self, test_database, mock_embedding_model):
        """Test processing very large batch"""
        chunker = WikiChunker()

        # Collect all chunks
        all_chunks = []
        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                chunks = list(chunker.chunk_section_level(page_data))
                all_chunks.extend(chunks)

        if all_chunks:
            # Process in one large batch
            contents = [c.content for c in all_chunks]
            embeddings = mock_embedding_model.encode(contents)

            # Should complete without memory error
            assert embeddings.shape[0] == len(all_chunks)


class TestEdgeCaseContent:
    """Test edge cases in content processing"""

    def test_only_whitespace(self):
        """Test page with only whitespace"""
        chunker = WikiChunker()

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Whitespace",
            "namespace": 0,
            "content": "   \n\n\t\t  \n   ",
            "metadata": {},
        }

        chunks = list(chunker.chunk_section_level(page_data))

        # Should be filtered out (no real content)
        assert len(chunks) == 0

    def test_infinite_loop_protection(self):
        """Test that malformed sections don't cause infinite loops"""
        chunker = WikiChunker()

        # Pathological case with many unclosed tags
        content = "==" * 1000 + "content" + "==" * 1000

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Test",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        # Should complete in reasonable time (not infinite loop)
        import time

        start = time.time()

        chunks = list(chunker.chunk_section_level(page_data))

        elapsed = time.time() - start

        # Should complete quickly (< 5 seconds for this size)
        assert elapsed < 5.0

    def test_deeply_nested_sections(self):
        """Test page with many section levels"""
        chunker = WikiChunker()

        content = """
Intro

== Level 2 ==
Content

=== Level 3 ===
Content

==== Level 4 ====
Content

===== Level 5 =====
Content

====== Level 6 ======
Content
        """

        page_data = {
            "page_id": 1,
            "revision_id": 101,
            "page_title": "Nested",
            "namespace": 0,
            "content": content,
            "metadata": {},
        }

        chunks = list(chunker.chunk_section_level(page_data))

        # Should handle all levels
        assert len(chunks) > 0

        # Check different levels are captured
        levels = {c.section_level for c in chunks if c.section_level}
        assert len(levels) > 1


class TestConcurrentAccess:
    """Test concurrent access scenarios"""

    def test_multiple_readers(self, test_database):
        """Test multiple concurrent database readers"""
        # Simulate multiple readers
        readers = []

        try:
            for i in range(3):
                reader = DatabaseReader(str(test_database))
                reader.__enter__()
                readers.append(reader)

            # All should be able to query
            for reader in readers:
                count = reader.count_pages()
                assert count > 0

        finally:
            # Clean up
            for reader in readers:
                try:
                    reader.__exit__(None, None, None)
                except:
                    pass


class TestInputValidation:
    """Test input validation"""

    def test_chunk_invalid_page_id(self):
        """Test chunk with invalid page ID"""
        chunk = Chunk(
            page_id=-1,  # Negative
            revision_id=101,
            page_title="Test",
            namespace=0,
            content="Content",
            chunk_type="page",
            chunk_index=0,
            metadata={},
        )

        # Should create successfully (no validation)
        assert chunk.page_id == -1

    def test_chunk_empty_title(self):
        """Test chunk with empty title"""
        chunk = Chunk(
            page_id=1,
            revision_id=101,
            page_title="",  # Empty
            namespace=0,
            content="Content",
            chunk_type="page",
            chunk_index=0,
            metadata={},
        )

        # Should create successfully
        assert chunk.page_title == ""

    def test_chunk_special_characters_in_title(self):
        """Test chunk with special characters in title"""
        special_title = "Test/Page:With-Special_Chars!@#$%"

        chunk = Chunk(
            page_id=1,
            revision_id=101,
            page_title=special_title,
            namespace=0,
            content="Content",
            chunk_type="section",
            section_title="Special: Section!",
            chunk_index=0,
            metadata={},
        )

        # Should handle special chars in ID generation
        chunk_id = chunk.get_id()
        assert isinstance(chunk_id, str)
        assert len(chunk_id) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
