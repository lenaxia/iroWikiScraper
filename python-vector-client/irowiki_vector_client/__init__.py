"""
iRO Wiki Vector Client

Python client library for semantic search on iRO Wiki vector databases.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseVectorClient:
    """Base class for vector database clients"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load database metadata"""
        metadata_file = self.db_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                return json.load(f)
        return {}

    def search(
        self, query: str, limit: int = 5, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar content

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters (e.g., {"namespace": 0})

        Returns:
            List of search results with content and metadata
        """
        raise NotImplementedError

    def get_metadata(self) -> Dict[str, Any]:
        """Get database metadata"""
        return self.metadata


class QdrantClient(BaseVectorClient):
    """Client for Qdrant vector database"""

    def __init__(self, db_path: str, collection_name: str = "irowiki"):
        super().__init__(db_path)
        self.collection_name = collection_name

        try:
            from qdrant_client import QdrantClient as QdrantSDK
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Qdrant dependencies not installed. "
                "Install with: pip install qdrant-client sentence-transformers"
            )

        self.client = QdrantSDK(path=str(self.db_path))

        # Load model from metadata
        model_name = self.metadata.get("model", "all-MiniLM-L6-v2")
        self.model = SentenceTransformer(model_name)

    def search(
        self, query: str, limit: int = 5, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar content using Qdrant

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters (e.g., {"namespace": 0})

        Returns:
            List of dicts with keys: page_title, content, score, metadata
        """
        # Generate query embedding
        query_vector = self.model.encode(query)

        # Build filter if provided
        query_filter = None
        if filters:
            query_filter = {
                "must": [
                    {"key": key, "match": {"value": value}}
                    for key, value in filters.items()
                ]
            }

        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            query_filter=query_filter,
            limit=limit,
        )

        # Format results
        formatted = []
        for result in results:
            formatted.append(
                {
                    "page_title": result.payload.get("page_title"),
                    "section_title": result.payload.get("section_title"),
                    "content": result.payload.get("content"),
                    "score": result.score,
                    "chunk_type": result.payload.get("chunk_type"),
                    "namespace": result.payload.get("namespace"),
                    "page_id": result.payload.get("page_id"),
                }
            )

        return formatted

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        info = self.client.get_collection(self.collection_name)
        return {
            "points_count": info.points_count,
            "vector_size": info.config.params.vectors.size,
        }


class ChromaDBClient(BaseVectorClient):
    """Client for ChromaDB vector database"""

    def __init__(self, db_path: str, collection_name: str = "irowiki"):
        super().__init__(db_path)
        self.collection_name = collection_name

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "ChromaDB dependencies not installed. "
                "Install with: pip install chromadb sentence-transformers"
            )

        self.chroma_client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.chroma_client.get_collection(name=self.collection_name)

        # Load model from metadata
        model_name = self.metadata.get("model", "all-MiniLM-L6-v2")
        self.model = SentenceTransformer(model_name)

    def search(
        self, query: str, limit: int = 5, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar content using ChromaDB

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters (e.g., {"namespace": 0})

        Returns:
            List of dicts with keys: page_title, content, distance, metadata
        """
        # Generate query embedding
        query_vector = self.model.encode(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_vector.tolist()], n_results=limit, where=filters
        )

        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            formatted.append(
                {
                    "page_title": metadata.get("page_title"),
                    "section_title": metadata.get("section_title"),
                    "content": results["documents"][0][i],
                    "distance": (
                        results["distances"][0][i] if "distances" in results else None
                    ),
                    "chunk_type": metadata.get("chunk_type"),
                    "namespace": metadata.get("namespace"),
                    "page_id": metadata.get("page_id"),
                }
            )

        return formatted

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        return {
            "count": self.collection.count(),
            "name": self.collection.name,
        }


class RAGContextBuilder:
    """Helper class for building RAG contexts"""

    def __init__(self, client: BaseVectorClient):
        self.client = client

    @staticmethod
    def count_tokens(text: str) -> int:
        """Rough token count estimate (1 token ≈ 4 characters)"""
        return len(text) // 4

    def build_context(
        self,
        query: str,
        max_tokens: int = 2000,
        top_k: int = 20,
        filters: Optional[Dict] = None,
    ) -> tuple[str, List[Dict]]:
        """
        Build RAG context from query

        Args:
            query: User query
            max_tokens: Maximum tokens for context
            top_k: Number of chunks to retrieve
            filters: Optional filters

        Returns:
            Tuple of (context_text, source_list)
        """
        # Retrieve relevant chunks
        results = self.client.search(query, limit=top_k, filters=filters)

        # Build context within token limit
        context_parts = []
        sources = []
        total_tokens = 0

        for result in results:
            content = result["content"]
            chunk_tokens = self.count_tokens(content)

            # Check if adding would exceed limit
            if total_tokens + chunk_tokens > max_tokens:
                break

            # Format with source attribution
            page_title = result["page_title"]
            section_title = result.get("section_title")

            header = f"[{page_title}"
            if section_title:
                header += f" - {section_title}"
            header += "]"

            formatted = f"{header}\n{content}"
            context_parts.append(formatted)

            # Track source
            sources.append(
                {
                    "page": page_title,
                    "section": section_title,
                    "score": result.get("score") or (1.0 - result.get("distance", 0)),
                }
            )

            total_tokens += chunk_tokens + self.count_tokens(header)

        context = "\n\n---\n\n".join(context_parts)

        return context, sources

    def build_rag_prompt(self, query: str, context: str) -> str:
        """
        Build complete RAG prompt with context

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Complete prompt for LLM
        """
        prompt = f"""You are an expert on Ragnarok Online (iRO). Answer the following question using ONLY the provided wiki context. If the context doesn't contain enough information, say so.

Wiki Context:
{context}

Question: {query}

Answer:"""
        return prompt


__all__ = [
    "BaseVectorClient",
    "QdrantClient",
    "ChromaDBClient",
    "RAGContextBuilder",
]
