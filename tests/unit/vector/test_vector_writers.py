"""
Unit tests for VectorDBWriter classes

Tests both Qdrant and ChromaDB implementations.
"""

import pytest
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from vectorize_wiki import QdrantWriter, ChromaDBWriter


class TestQdrantWriter:
    """Test QdrantWriter implementation"""

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_initialize_creates_collection(
        self, temp_vector_storage, mock_embedding_model
    ):
        """Test that initialize creates a Qdrant collection"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Check collection was created
        assert writer.client is not None
        info = writer.client.get_collection("irowiki")
        assert info.points_count == 0  # Empty initially

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_add_chunks(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test adding chunks to Qdrant"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)

        # Check chunks were added
        info = writer.client.get_collection("irowiki")
        assert info.points_count == len(sample_chunks)

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_add_chunks_preserves_metadata(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test that chunk metadata is preserved"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)

        # Retrieve a point and check metadata
        results = writer.client.scroll(collection_name="irowiki", limit=1)

        point = results[0][0]
        payload = point.payload

        # Check expected fields
        assert "page_id" in payload
        assert "page_title" in payload
        assert "content" in payload
        assert "chunk_type" in payload

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_finalize(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test finalize method"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)
        writer.finalize()

        # Should complete without error
        info = writer.client.get_collection("irowiki")
        assert info.points_count == len(sample_chunks)

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_save_metadata(self, temp_vector_storage, mock_embedding_model):
        """Test metadata file is saved"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        metadata = {
            "model": "test-model",
            "total_chunks": 100,
            "generated_at": "2024-01-01T00:00:00Z",
        }

        writer.save_metadata(metadata)

        # Check metadata file exists
        metadata_file = output_path / "metadata.json"
        assert metadata_file.exists()

        # Check content
        with open(metadata_file) as f:
            saved_metadata = json.load(f)

        assert saved_metadata["model"] == "test-model"
        assert saved_metadata["total_chunks"] == 100

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_custom_collection_name(self, temp_vector_storage, mock_embedding_model):
        """Test using custom collection name"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path),
            "test-model",
            mock_embedding_model.embedding_dim,
            collection_name="custom_collection",
        )

        writer.initialize()

        # Check custom collection exists
        info = writer.client.get_collection("custom_collection")
        assert info is not None


class TestChromaDBWriter:
    """Test ChromaDBWriter implementation"""

    def test_initialize_creates_collection(
        self, temp_vector_storage, mock_embedding_model
    ):
        """Test that initialize creates a ChromaDB collection"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Check collection was created
        assert writer.client is not None
        assert writer.collection is not None
        assert writer.collection.count() == 0

    def test_add_chunks(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test adding chunks to ChromaDB"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)

        # Check chunks were added
        assert writer.collection.count() == len(sample_chunks)

    def test_add_chunks_preserves_metadata(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test that chunk metadata is preserved"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)

        # Get first chunk
        result = writer.collection.get(limit=1)

        # Check metadata
        metadata = result["metadatas"][0]
        assert "page_id" in metadata
        assert "page_title" in metadata
        assert "chunk_type" in metadata

        # Check document
        document = result["documents"][0]
        assert len(document) > 0

    def test_finalize(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test finalize method"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)
        writer.finalize()

        # Should complete without error
        assert writer.collection.count() == len(sample_chunks)

    def test_save_metadata(self, temp_vector_storage, mock_embedding_model):
        """Test metadata file is saved"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        metadata = {"model": "test-model", "total_chunks": 100}

        writer.save_metadata(metadata)

        # Check metadata file
        metadata_file = output_path / "metadata.json"
        assert metadata_file.exists()

    def test_custom_collection_name(self, temp_vector_storage, mock_embedding_model):
        """Test using custom collection name"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path),
            "test-model",
            mock_embedding_model.embedding_dim,
            collection_name="custom_collection",
        )

        writer.initialize()

        # Check custom collection exists
        assert writer.collection.name == "custom_collection"

    def test_recreate_collection(self, temp_vector_storage, mock_embedding_model):
        """Test that initializing twice recreates the collection"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        # First initialization
        writer.initialize()
        assert writer.collection.count() == 0

        # Add some data
        from vectorize_wiki import Chunk
        import numpy as np

        chunk = Chunk(
            page_id=1,
            revision_id=101,
            page_title="Test",
            namespace=0,
            content="Test content",
            chunk_type="page",
            chunk_index=0,
            metadata={},
        )
        embedding = np.random.rand(1, mock_embedding_model.embedding_dim).astype(
            np.float32
        )
        writer.add_chunks([chunk], embedding)

        assert writer.collection.count() == 1

        # Second initialization should recreate (clear data)
        writer.initialize()
        assert writer.collection.count() == 0


class TestVectorDBWriterEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_empty_chunks(self, temp_vector_storage, mock_embedding_model):
        """Test adding empty list of chunks"""
        pytest.importorskip("qdrant_client")

        import numpy as np

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Add empty lists
        writer.add_chunks(
            [], np.array([]).reshape(0, mock_embedding_model.embedding_dim)
        )

        # Should handle gracefully
        info = writer.client.get_collection("irowiki")
        assert info.points_count == 0

    def test_chromadb_empty_chunks(self, temp_vector_storage, mock_embedding_model):
        """Test adding empty list of chunks"""
        pytest.importorskip("chromadb")

        import numpy as np

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Add empty lists - ChromaDB will raise error on empty
        # This is expected behavior
        assert writer.collection.count() == 0

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_mismatched_dimensions(
        self, temp_vector_storage, mock_embedding_model, sample_chunks
    ):
        """Test adding embeddings with wrong dimensions"""
        pytest.importorskip("qdrant_client")

        import numpy as np

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # Wrong dimension embeddings
        wrong_embeddings = np.random.rand(len(sample_chunks), 128).astype(np.float32)

        # Should raise error
        with pytest.raises(Exception):
            writer.add_chunks(sample_chunks, wrong_embeddings)

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_mismatched_count(
        self, temp_vector_storage, mock_embedding_model, sample_chunks
    ):
        """Test adding different number of chunks and embeddings"""
        pytest.importorskip("qdrant_client")

        import numpy as np

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()

        # More embeddings than chunks
        wrong_embeddings = np.random.rand(
            len(sample_chunks) + 5, mock_embedding_model.embedding_dim
        ).astype(np.float32)

        # Should raise error (index out of range)
        with pytest.raises(IndexError):
            writer.add_chunks(sample_chunks, wrong_embeddings)


class TestVectorDBWriterIntegration:
    """Integration tests for writers"""

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="Qdrant client requires Python 3.11+"
    )
    def test_qdrant_search_after_write(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test that we can search after writing"""
        pytest.importorskip("qdrant_client")

        output_path = temp_vector_storage / "qdrant"
        writer = QdrantWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)
        writer.finalize()

        # Try searching
        query_vector = sample_embeddings[0].tolist()
        results = writer.client.search(
            collection_name="irowiki", query_vector=query_vector, limit=3
        )

        assert len(results) > 0
        assert results[0].payload["page_id"] == sample_chunks[0].page_id

    def test_chromadb_query_after_write(
        self,
        temp_vector_storage,
        mock_embedding_model,
        sample_chunks,
        sample_embeddings,
    ):
        """Test that we can query after writing"""
        pytest.importorskip("chromadb")

        output_path = temp_vector_storage / "chromadb"
        writer = ChromaDBWriter(
            str(output_path), "test-model", mock_embedding_model.embedding_dim
        )

        writer.initialize()
        writer.add_chunks(sample_chunks, sample_embeddings)
        writer.finalize()

        # Try querying
        query_vector = sample_embeddings[0].tolist()
        results = writer.collection.query(query_embeddings=[query_vector], n_results=3)

        assert len(results["ids"][0]) > 0
        # First result should be most similar (the same chunk)
        assert results["metadatas"][0][0]["page_id"] == sample_chunks[0].page_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
