#!/usr/bin/env python3
"""
Vectorize iRO Wiki Database for Semantic Search

This script reads the SQLite database and creates vector embeddings for semantic search.
Supports multiple chunking strategies, embedding models, and vector databases.

Usage:
    python scripts/vectorize-wiki.py --db data/irowiki.db --output qdrant_storage
    python scripts/vectorize-wiki.py --model bge-large-en-v1.5 --chunk-level paragraph
    python scripts/vectorize-wiki.py --vector-db chromadb --output chroma_storage
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional, Dict, Any
from datetime import datetime

import numpy as np
from tqdm import tqdm

# Import will be conditional based on --vector-db flag
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print(
        "ERROR: sentence-transformers not installed. Run: pip install sentence-transformers"
    )
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a content chunk to be embedded"""

    page_id: int
    revision_id: int
    page_title: str
    namespace: int
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Chunk-specific fields
    chunk_type: str = "page"  # page, section, paragraph
    section_title: Optional[str] = None
    section_level: Optional[int] = None
    chunk_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage"""
        return {
            "page_id": self.page_id,
            "revision_id": self.revision_id,
            "page_title": self.page_title,
            "namespace": self.namespace,
            "content": self.content,
            "chunk_type": self.chunk_type,
            "section_title": self.section_title,
            "section_level": self.section_level,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }

    def get_id(self) -> str:
        """Generate unique ID for this chunk"""
        if self.chunk_type == "page":
            return f"page_{self.page_id}"
        elif self.chunk_type == "section":
            section_slug = (
                self.section_title.lower().replace(" ", "_")
                if self.section_title
                else "intro"
            )
            return f"page_{self.page_id}_section_{section_slug}_{self.chunk_index}"
        else:  # paragraph
            return f"page_{self.page_id}_para_{self.chunk_index}"


class WikiChunker:
    """Handles different chunking strategies for wiki content"""

    MIN_CHUNK_SIZE = 50  # Minimum words per chunk
    MAX_CHUNK_SIZE = 1000  # Maximum words per chunk (for paragraph mode)

    @staticmethod
    def clean_wikitext(text: str) -> str:
        """Clean MediaWiki markup from text"""
        if not text:
            return ""

        # Remove templates (e.g., {{template}})
        text = re.sub(r"\{\{[^}]+\}\}", "", text)

        # Remove file/image links
        text = re.sub(r"\[\[(File|Image):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

        # Convert wiki links to plain text [[link|text]] -> text or [[link]] -> link
        text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
        text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

        # Remove external links [url text] -> text
        text = re.sub(r"\[https?://[^\s\]]+ ([^\]]+)\]", r"\1", text)
        text = re.sub(r"\[https?://[^\s\]]+\]", "", text)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove wiki formatting
        text = re.sub(r"'''([^']+)'''", r"\1", text)  # Bold
        text = re.sub(r"''([^']+)''", r"\1", text)  # Italic

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = text.strip()

        return text

    @staticmethod
    def word_count(text: str) -> int:
        """Count words in text"""
        return len(text.split())

    def chunk_page_level(self, page_data: Dict[str, Any]) -> Iterator[Chunk]:
        """Chunk at page level (one chunk per page)"""
        content = self.clean_wikitext(page_data["content"])

        if self.word_count(content) < self.MIN_CHUNK_SIZE:
            return  # Skip very short pages

        yield Chunk(
            page_id=page_data["page_id"],
            revision_id=page_data["revision_id"],
            page_title=page_data["page_title"],
            namespace=page_data["namespace"],
            content=content,
            chunk_type="page",
            metadata=page_data["metadata"],
        )

    def chunk_section_level(self, page_data: Dict[str, Any]) -> Iterator[Chunk]:
        """Chunk at section level (split by MediaWiki headings)"""
        content = page_data["content"]
        page_title = page_data["page_title"]

        # Split by headings (==, ===, etc.)
        # Pattern: one or more = signs, text, same number of = signs
        sections = re.split(r"\n(={2,})([^=]+)\1\n", content)

        # First element is the intro (before first heading)
        intro = self.clean_wikitext(sections[0])
        if self.word_count(intro) >= self.MIN_CHUNK_SIZE:
            yield Chunk(
                page_id=page_data["page_id"],
                revision_id=page_data["revision_id"],
                page_title=page_title,
                namespace=page_data["namespace"],
                content=intro,
                chunk_type="section",
                section_title="Introduction",
                section_level=1,
                chunk_index=0,
                metadata=page_data["metadata"],
            )

        # Process remaining sections
        chunk_index = 1
        for i in range(1, len(sections), 3):
            if i + 2 >= len(sections):
                break

            heading_level = len(sections[i])
            heading_text = sections[i + 1].strip()
            section_content = sections[i + 2] if i + 2 < len(sections) else ""

            cleaned = self.clean_wikitext(section_content)
            if self.word_count(cleaned) < self.MIN_CHUNK_SIZE:
                continue

            # Prepend heading to content for better context
            full_content = f"{heading_text}\n\n{cleaned}"

            yield Chunk(
                page_id=page_data["page_id"],
                revision_id=page_data["revision_id"],
                page_title=page_title,
                namespace=page_data["namespace"],
                content=full_content,
                chunk_type="section",
                section_title=heading_text,
                section_level=heading_level,
                chunk_index=chunk_index,
                metadata=page_data["metadata"],
            )
            chunk_index += 1

    def chunk_paragraph_level(self, page_data: Dict[str, Any]) -> Iterator[Chunk]:
        """Chunk at paragraph level (split by double newlines)"""
        content = self.clean_wikitext(page_data["content"])
        page_title = page_data["page_title"]

        # Split by paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        chunk_index = 0
        current_section = None

        for para in paragraphs:
            # Check if this is a heading
            heading_match = re.match(r"^([^:]+):?\s*$", para)
            if heading_match and self.word_count(para) <= 10:
                current_section = heading_match.group(1).strip()
                continue

            if self.word_count(para) < self.MIN_CHUNK_SIZE:
                continue

            # Split very long paragraphs
            if self.word_count(para) > self.MAX_CHUNK_SIZE:
                sentences = re.split(r"[.!?]+\s+", para)
                current_chunk = []
                current_words = 0

                for sentence in sentences:
                    sentence_words = self.word_count(sentence)
                    if (
                        current_words + sentence_words > self.MAX_CHUNK_SIZE
                        and current_chunk
                    ):
                        # Yield current chunk
                        chunk_text = " ".join(current_chunk)
                        if self.word_count(chunk_text) >= self.MIN_CHUNK_SIZE:
                            yield Chunk(
                                page_id=page_data["page_id"],
                                revision_id=page_data["revision_id"],
                                page_title=page_title,
                                namespace=page_data["namespace"],
                                content=chunk_text,
                                chunk_type="paragraph",
                                section_title=current_section,
                                chunk_index=chunk_index,
                                metadata=page_data["metadata"],
                            )
                            chunk_index += 1
                        current_chunk = [sentence]
                        current_words = sentence_words
                    else:
                        current_chunk.append(sentence)
                        current_words += sentence_words

                # Yield remaining
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    if self.word_count(chunk_text) >= self.MIN_CHUNK_SIZE:
                        yield Chunk(
                            page_id=page_data["page_id"],
                            revision_id=page_data["revision_id"],
                            page_title=page_title,
                            namespace=page_data["namespace"],
                            content=chunk_text,
                            chunk_type="paragraph",
                            section_title=current_section,
                            chunk_index=chunk_index,
                            metadata=page_data["metadata"],
                        )
                        chunk_index += 1
            else:
                yield Chunk(
                    page_id=page_data["page_id"],
                    revision_id=page_data["revision_id"],
                    page_title=page_title,
                    namespace=page_data["namespace"],
                    content=para,
                    chunk_type="paragraph",
                    section_title=current_section,
                    chunk_index=chunk_index,
                    metadata=page_data["metadata"],
                )
                chunk_index += 1


class DatabaseReader:
    """Reads pages from SQLite database"""

    def __init__(self, db_path: str, namespaces: List[int] = None):
        self.db_path = db_path
        self.namespaces = namespaces or [0]  # Default to main namespace
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def count_pages(self) -> int:
        """Count total pages to process"""
        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(self.namespaces))
        query = f"""
            SELECT COUNT(*) as count
            FROM pages
            WHERE namespace IN ({placeholders})
        """
        result = cursor.execute(query, self.namespaces).fetchone()
        return result["count"]

    def iter_pages(self) -> Iterator[Dict[str, Any]]:
        """Iterate over pages with their latest revision"""
        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(self.namespaces))

        query = f"""
            SELECT 
                p.page_id,
                p.title as page_title,
                p.namespace,
                r.revision_id,
                r.content,
                r.timestamp,
                r.contributor_name,
                p.is_redirect
            FROM pages p
            JOIN (
                SELECT page_id, revision_id, content, timestamp, contributor_name
                FROM revisions
                WHERE (page_id, timestamp) IN (
                    SELECT page_id, MAX(timestamp)
                    FROM revisions
                    GROUP BY page_id
                )
            ) r ON p.page_id = r.page_id
            WHERE p.namespace IN ({placeholders})
                AND p.is_redirect = 0
                AND LENGTH(r.content) > 0
            ORDER BY p.page_id
        """

        for row in cursor.execute(query, self.namespaces):
            yield {
                "page_id": row["page_id"],
                "page_title": row["page_title"],
                "namespace": row["namespace"],
                "revision_id": row["revision_id"],
                "content": row["content"],
                "metadata": {
                    "timestamp": row["timestamp"],
                    "contributor": row["contributor_name"],
                    "is_redirect": row["is_redirect"],
                },
            }


class VectorDBWriter:
    """Base class for vector database writers"""

    def __init__(self, output_path: str, model_name: str, embedding_dim: int):
        self.output_path = output_path
        self.model_name = model_name
        self.embedding_dim = embedding_dim

    def initialize(self):
        """Initialize the vector database"""
        raise NotImplementedError

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Add chunks with their embeddings"""
        raise NotImplementedError

    def finalize(self):
        """Finalize and save the database"""
        raise NotImplementedError

    def save_metadata(self, metadata: Dict[str, Any]):
        """Save generation metadata"""
        metadata_path = Path(self.output_path) / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")


class QdrantWriter(VectorDBWriter):
    """Writes to Qdrant vector database"""

    def __init__(
        self,
        output_path: str,
        model_name: str,
        embedding_dim: int,
        collection_name: str = "irowiki",
    ):
        super().__init__(output_path, model_name, embedding_dim)
        self.collection_name = collection_name
        self.client = None

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct

            self.QdrantClient = QdrantClient
            self.Distance = Distance
            self.VectorParams = VectorParams
            self.PointStruct = PointStruct
        except ImportError:
            logger.error("Qdrant not installed. Run: pip install qdrant-client")
            sys.exit(1)

    def initialize(self):
        """Initialize Qdrant collection"""
        logger.info(f"Initializing Qdrant at {self.output_path}")
        self.client = self.QdrantClient(path=self.output_path)

        # Create collection
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=self.VectorParams(
                size=self.embedding_dim, distance=self.Distance.COSINE
            ),
        )
        logger.info(f"Created collection: {self.collection_name}")

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Add chunks to Qdrant"""
        points = []
        for i, chunk in enumerate(chunks):
            chunk_dict = chunk.to_dict()
            points.append(
                self.PointStruct(
                    id=hash(chunk.get_id()) % (10**10),  # Convert string ID to int
                    vector=embeddings[i].tolist(),
                    payload={"chunk_id": chunk.get_id(), **chunk_dict},
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)

    def finalize(self):
        """Finalize Qdrant database"""
        info = self.client.get_collection(self.collection_name)
        logger.info(f"Qdrant collection finalized: {info.points_count} points")


class ChromaDBWriter(VectorDBWriter):
    """Writes to ChromaDB vector database"""

    def __init__(
        self,
        output_path: str,
        model_name: str,
        embedding_dim: int,
        collection_name: str = "irowiki",
    ):
        super().__init__(output_path, model_name, embedding_dim)
        self.collection_name = collection_name
        self.client = None
        self.collection = None

        try:
            import chromadb

            self.chromadb = chromadb
        except ImportError:
            logger.error("ChromaDB not installed. Run: pip install chromadb")
            sys.exit(1)

    def initialize(self):
        """Initialize ChromaDB collection"""
        logger.info(f"Initializing ChromaDB at {self.output_path}")
        self.client = self.chromadb.PersistentClient(path=self.output_path)

        # Delete if exists
        try:
            self.client.delete_collection(name=self.collection_name)
        except:
            pass

        # Create collection
        self.collection = self.client.create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Created collection: {self.collection_name}")

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Add chunks to ChromaDB"""
        ids = [chunk.get_id() for chunk in chunks]
        metadatas = []
        documents = []

        for chunk in chunks:
            chunk_dict = chunk.to_dict()
            # ChromaDB requires metadata values to be strings, ints, floats, or bools
            metadata = {
                "page_id": chunk.page_id,
                "revision_id": chunk.revision_id,
                "page_title": chunk.page_title,
                "namespace": chunk.namespace,
                "chunk_type": chunk.chunk_type,
                "chunk_index": chunk.chunk_index,
            }
            if chunk.section_title:
                metadata["section_title"] = chunk.section_title
            if chunk.section_level:
                metadata["section_level"] = chunk.section_level

            metadatas.append(metadata)
            documents.append(chunk.content)

        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            documents=documents,
        )

    def finalize(self):
        """Finalize ChromaDB database"""
        count = self.collection.count()
        logger.info(f"ChromaDB collection finalized: {count} chunks")


def main():
    parser = argparse.ArgumentParser(
        description="Vectorize iRO Wiki database for semantic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: section-level chunking with MiniLM, output to Qdrant
  python scripts/vectorize-wiki.py --db data/irowiki.db --output qdrant_storage
  
  # Use different embedding model
  python scripts/vectorize-wiki.py --model bge-large-en-v1.5
  
  # Paragraph-level chunking
  python scripts/vectorize-wiki.py --chunk-level paragraph
  
  # Output to ChromaDB
  python scripts/vectorize-wiki.py --vector-db chromadb --output chroma_storage
  
  # Include File namespace (images metadata)
  python scripts/vectorize-wiki.py --namespaces 0 6
        """,
    )

    parser.add_argument(
        "--db",
        default="data/irowiki.db",
        help="Path to SQLite database (default: data/irowiki.db)",
    )

    parser.add_argument(
        "--output",
        default="vector_storage",
        help="Output directory for vector database (default: vector_storage)",
    )

    parser.add_argument(
        "--vector-db",
        choices=["qdrant", "chromadb"],
        default="qdrant",
        help="Vector database type (default: qdrant)",
    )

    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence transformer model name (default: all-MiniLM-L6-v2)",
    )

    parser.add_argument(
        "--chunk-level",
        choices=["page", "section", "paragraph"],
        default="section",
        help="Chunking strategy (default: section)",
    )

    parser.add_argument(
        "--namespaces",
        type=int,
        nargs="+",
        default=[0],
        help="Wiki namespaces to include (default: 0 for main namespace)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)",
    )

    parser.add_argument(
        "--collection-name",
        default="irowiki",
        help="Name of the vector collection (default: irowiki)",
    )

    args = parser.parse_args()

    # Validate database exists
    if not Path(args.db).exists():
        logger.error(f"Database not found: {args.db}")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load embedding model
    logger.info(f"Loading embedding model: {args.model}")
    try:
        model = SentenceTransformer(args.model)
        embedding_dim = model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {embedding_dim}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)

    # Initialize chunker
    chunker = WikiChunker()

    # Choose chunking method
    if args.chunk_level == "page":
        chunk_method = chunker.chunk_page_level
    elif args.chunk_level == "section":
        chunk_method = chunker.chunk_section_level
    else:
        chunk_method = chunker.chunk_paragraph_level

    # Initialize vector database writer
    if args.vector_db == "qdrant":
        writer = QdrantWriter(
            str(output_path), args.model, embedding_dim, args.collection_name
        )
    else:
        writer = ChromaDBWriter(
            str(output_path), args.model, embedding_dim, args.collection_name
        )

    writer.initialize()

    # Process pages
    start_time = time.time()
    total_chunks = 0
    total_pages = 0

    logger.info("Starting vectorization...")

    with DatabaseReader(args.db, args.namespaces) as db:
        page_count = db.count_pages()
        logger.info(f"Processing {page_count} pages from namespaces {args.namespaces}")

        batch_chunks = []
        batch_contents = []

        with tqdm(total=page_count, desc="Vectorizing pages") as pbar:
            for page_data in db.iter_pages():
                total_pages += 1

                # Generate chunks for this page
                for chunk in chunk_method(page_data):
                    batch_chunks.append(chunk)
                    batch_contents.append(chunk.content)
                    total_chunks += 1

                    # Process batch when full
                    if len(batch_chunks) >= args.batch_size:
                        # Generate embeddings
                        embeddings = model.encode(
                            batch_contents,
                            batch_size=args.batch_size,
                            show_progress_bar=False,
                            convert_to_numpy=True,
                        )

                        # Write to vector DB
                        writer.add_chunks(batch_chunks, embeddings)

                        # Clear batch
                        batch_chunks = []
                        batch_contents = []

                pbar.update(1)

        # Process remaining chunks
        if batch_chunks:
            embeddings = model.encode(
                batch_contents,
                batch_size=args.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            writer.add_chunks(batch_chunks, embeddings)

    # Finalize
    writer.finalize()

    # Save metadata
    elapsed = time.time() - start_time
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "database_path": args.db,
        "model": args.model,
        "embedding_dim": embedding_dim,
        "chunk_level": args.chunk_level,
        "namespaces": args.namespaces,
        "vector_db": args.vector_db,
        "collection_name": args.collection_name,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "elapsed_seconds": int(elapsed),
        "chunks_per_page": round(total_chunks / total_pages, 2)
        if total_pages > 0
        else 0,
    }
    writer.save_metadata(metadata)

    # Summary
    logger.info("=" * 60)
    logger.info("Vectorization complete!")
    logger.info(f"  Total pages processed: {total_pages:,}")
    logger.info(f"  Total chunks created: {total_chunks:,}")
    logger.info(f"  Chunks per page: {metadata['chunks_per_page']}")
    logger.info(f"  Time elapsed: {elapsed / 60:.1f} minutes")
    logger.info(f"  Chunks/second: {total_chunks / elapsed:.1f}")
    logger.info(f"  Output location: {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
