"""
Integration tests for full vectorization pipeline

Tests end-to-end workflows from database to vector DB.
"""

import pytest
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from vectorize_wiki import (
    DatabaseReader,
    WikiChunker,
    QdrantWriter,
    ChromaDBWriter,
)


class TestFullPipeline:
    """Test complete vectorization pipeline"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_database_to_qdrant(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test full pipeline: SQLite → Chunks → Qdrant"""
        pytest.importorskip("qdrant_client")

        # Setup
        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        # Initialize writer
        writer.initialize()

        # Process database
        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                # Generate chunks
                chunks = list(chunker.chunk_section_level(page_data))

                if chunks:
                    # Generate embeddings
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)

                    # Add to vector DB
                    writer.add_chunks(chunks, embeddings)

        # Finalize
        writer.finalize()

        # Verify
        info = writer.client.get_collection("irowiki")
        assert info.points_count > 0

        # Test search works
        query = "Poring"
        query_vector = mock_embedding_model.encode(query)
        results = writer.client.search(
            collection_name="irowiki", query_vector=query_vector.tolist(), limit=5
        )

        assert len(results) > 0

    @pytest.mark.integration
    def test_database_to_chromadb(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test full pipeline: SQLite → Chunks → ChromaDB"""
        pytest.importorskip("chromadb")

        # Setup
        output_path = temp_vector_storage / "chromadb"
        chunker = WikiChunker()
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        # Initialize writer
        writer.initialize()

        # Process database
        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                # Generate chunks
                chunks = list(chunker.chunk_section_level(page_data))

                if chunks:
                    # Generate embeddings
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)

                    # Add to vector DB
                    writer.add_chunks(chunks, embeddings)

        # Finalize
        writer.finalize()

        # Verify
        assert writer.collection.count() > 0

        # Test query works
        query = "Poring"
        query_vector = mock_embedding_model.encode(query)
        results = writer.collection.query(
            query_embeddings=[query_vector.tolist()], n_results=5
        )

        assert len(results["ids"][0]) > 0


class TestBatchProcessing:
    """Test batch processing scenarios"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_batch_chunking_and_embedding(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test processing in batches"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Collect chunks in batches
        batch_size = 2
        batch_chunks = []
        batch_contents = []

        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                chunks = list(chunker.chunk_section_level(page_data))

                for chunk in chunks:
                    batch_chunks.append(chunk)
                    batch_contents.append(chunk.content)

                    # Process when batch is full
                    if len(batch_chunks) >= batch_size:
                        embeddings = mock_embedding_model.encode(batch_contents)
                        writer.add_chunks(batch_chunks, embeddings)

                        batch_chunks = []
                        batch_contents = []

            # Process remaining
            if batch_chunks:
                embeddings = mock_embedding_model.encode(batch_contents)
                writer.add_chunks(batch_chunks, embeddings)

        writer.finalize()

        # Verify all chunks were processed
        info = writer.client.get_collection("irowiki")
        assert info.points_count > 0


class TestMetadataGeneration:
    """Test metadata generation and storage"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_generate_complete_metadata(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test generating complete metadata"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        total_pages = 0
        total_chunks = 0

        with DatabaseReader(str(test_database)) as db:
            page_count = db.count_pages()

            for page_data in db.iter_pages():
                total_pages += 1
                chunks = list(chunker.chunk_section_level(page_data))
                total_chunks += len(chunks)

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        writer.finalize()

        # Generate metadata
        metadata = {
            "generated_at": "2024-01-01T00:00:00Z",
            "database_path": str(test_database),
            "model": "test-model",
            "embedding_dim": mock_embedding_model.embedding_dim,
            "chunk_level": "section",
            "namespaces": [0],
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "chunks_per_page": (
                round(total_chunks / total_pages, 2) if total_pages > 0 else 0
            ),
        }

        writer.save_metadata(metadata)

        # Verify metadata file
        metadata_file = output_path / "metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            saved_metadata = json.load(f)

        assert saved_metadata["total_pages"] == total_pages
        assert saved_metadata["total_chunks"] == total_chunks
        assert saved_metadata["model"] == "test-model"


class TestDifferentChunkingStrategies:
    """Test all chunking strategies end-to-end"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_page_level_chunking_pipeline(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test page-level chunking end-to-end"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant_page"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path),
            "test-model",
            mock_embedding_model.embedding_dim,
            collection_name="page_chunks",
        )

        writer.initialize()

        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                chunks = list(chunker.chunk_page_level(page_data))

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        writer.finalize()

        # Should have one chunk per page (or 0 for very short pages)
        info = writer.client.get_collection("page_chunks")
        assert info.points_count > 0

    @pytest.mark.integration
    def test_paragraph_level_chunking_pipeline(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test paragraph-level chunking end-to-end"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb_para"
        chunker = WikiChunker()
        writer = ChromaDBWriter(
            str(output_path),
            "test-model",
            mock_embedding_model.embedding_dim,
            collection_name="para_chunks",
        )

        writer.initialize()

        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                chunks = list(chunker.chunk_paragraph_level(page_data))

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        writer.finalize()

        # Should have multiple chunks per page
        assert writer.collection.count() > 0


class TestErrorHandling:
    """Test error handling in pipeline"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_handle_corrupt_page_data(self, temp_vector_storage, mock_embedding_model):
        """Test handling of corrupt page data"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Page with missing required fields
        bad_page = {
            "page_id": 1,
            # Missing other required fields
        }

        # Should not crash
        try:
            chunks = list(chunker.chunk_section_level(bad_page))
        except KeyError:
            # Expected for missing required fields
            pass

    @pytest.mark.integration
    def test_handle_empty_database(
        self, tmp_path, temp_vector_storage, mock_embedding_model
    ):
        """Test handling empty database"""
        pytest.importorskip("chromadb")

        import sqlite3

        # Create empty database
        empty_db = tmp_path / "empty.db"
        conn = sqlite3.connect(empty_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                namespace INTEGER NOT NULL,
                latest_revision_id INTEGER,
                is_redirect INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE revisions (
                revision_id INTEGER PRIMARY KEY,
                page_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Process empty database - should not crash
        with DatabaseReader(str(empty_db)) as db:
            count = 0
            for page_data in db.iter_pages():
                count += 1

            assert count == 0

        writer.finalize()
        assert writer.collection.count() == 0


class TestPerformanceMetrics:
    """Test performance tracking"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_track_processing_stats(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test tracking processing statistics"""
        pytest.importorskip("qdrant_client")

        import time

        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        start_time = time.time()
        total_pages = 0
        total_chunks = 0

        with DatabaseReader(str(test_database)) as db:
            for page_data in db.iter_pages():
                total_pages += 1

                chunks = list(chunker.chunk_section_level(page_data))
                total_chunks += len(chunks)

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        elapsed = time.time() - start_time

        writer.finalize()

        # Calculate metrics
        pages_per_second = total_pages / elapsed if elapsed > 0 else 0
        chunks_per_second = total_chunks / elapsed if elapsed > 0 else 0

        # Basic sanity checks
        assert total_pages > 0
        assert total_chunks > 0
        assert elapsed > 0
        assert pages_per_second > 0
        assert chunks_per_second > 0


class TestNamespaceFiltering:
    """Test namespace filtering in pipeline"""

    @pytest.mark.integration
    def test_single_namespace_pipeline(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test processing only main namespace"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        chunker = WikiChunker()
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Process only namespace 0
        with DatabaseReader(str(test_database), namespaces=[0]) as db:
            for page_data in db.iter_pages():
                assert page_data["namespace"] == 0

                chunks = list(chunker.chunk_section_level(page_data))

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        writer.finalize()

        # Verify only namespace 0 chunks
        results = writer.collection.get()
        for metadata in results["metadatas"]:
            assert metadata["namespace"] == 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_multiple_namespaces_pipeline(
        self, test_database, temp_vector_storage, mock_embedding_model
    ):
        """Test processing multiple namespaces"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        chunker = WikiChunker()
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        namespaces_seen = set()

        # Process namespace 0 and 10
        with DatabaseReader(str(test_database), namespaces=[0, 10]) as db:
            for page_data in db.iter_pages():
                namespaces_seen.add(page_data["namespace"])

                chunks = list(chunker.chunk_section_level(page_data))

                if chunks:
                    contents = [c.content for c in chunks]
                    embeddings = mock_embedding_model.encode(contents)
                    writer.add_chunks(chunks, embeddings)

        writer.finalize()

        # Should have processed both namespaces
        assert 0 in namespaces_seen
        assert 10 in namespaces_seen


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
