#!/usr/bin/env python3
"""
Example: Semantic Search on iRO Wiki Vector Database

This script demonstrates how to perform semantic search queries on the vectorized
wiki database.

Usage:
    python examples/semantic_search_example.py "best weapon for undead"
    python examples/semantic_search_example.py --vector-db chromadb "how to get to glast heim"
"""

import argparse
import sys
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print(
        "ERROR: sentence-transformers not installed. Run: pip install -r requirements-vector.txt"
    )
    sys.exit(1)


def search_qdrant(query: str, vector_path: str, model_name: str, top_k: int = 5):
    """Search using Qdrant vector database"""
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("ERROR: qdrant-client not installed. Run: pip install qdrant-client")
        sys.exit(1)

    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"Connecting to Qdrant at: {vector_path}")
    client = QdrantClient(path=vector_path)

    print(f"\nQuery: {query}")
    print("Generating embedding...")
    query_vector = model.encode(query)

    print("Searching...")
    results = client.search(
        collection_name="irowiki", query_vector=query_vector.tolist(), limit=top_k
    )

    print(f"\n{'=' * 80}")
    print(f"Top {len(results)} Results:")
    print("=" * 80)

    for i, result in enumerate(results, 1):
        payload = result.payload
        print(f"\n[{i}] Score: {result.score:.4f}")
        print(f"    Page: {payload.get('page_title')}")
        if payload.get("section_title"):
            print(f"    Section: {payload.get('section_title')}")
        print(f"    Type: {payload.get('chunk_type')}")
        print(f"    Content preview:")
        content = payload.get("content", "")
        preview = content[:200] + "..." if len(content) > 200 else content
        print(f"    {preview}")


def search_chromadb(query: str, vector_path: str, model_name: str, top_k: int = 5):
    """Search using ChromaDB vector database"""
    try:
        import chromadb
    except ImportError:
        print("ERROR: chromadb not installed. Run: pip install chromadb")
        sys.exit(1)

    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"Connecting to ChromaDB at: {vector_path}")
    client = chromadb.PersistentClient(path=vector_path)
    collection = client.get_collection(name="irowiki")

    print(f"\nQuery: {query}")
    print("Generating embedding...")
    query_vector = model.encode(query)

    print("Searching...")
    results = collection.query(
        query_embeddings=[query_vector.tolist()], n_results=top_k
    )

    print(f"\n{'=' * 80}")
    print(f"Top {len(results['ids'][0])} Results:")
    print("=" * 80)

    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i]
        document = results["documents"][0][i]
        distance = results["distances"][0][i] if "distances" in results else None

        print(f"\n[{i + 1}] {'Distance: ' + str(distance) if distance else ''}")
        print(f"    Page: {metadata.get('page_title')}")
        if metadata.get("section_title"):
            print(f"    Section: {metadata.get('section_title')}")
        print(f"    Type: {metadata.get('chunk_type')}")
        print(f"    Content preview:")
        preview = document[:200] + "..." if len(document) > 200 else document
        print(f"    {preview}")


def main():
    parser = argparse.ArgumentParser(
        description="Semantic search on iRO Wiki vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search in Qdrant database
  python examples/semantic_search_example.py "best weapon for undead"
  
  # Search in ChromaDB database
  python examples/semantic_search_example.py --vector-db chromadb "glast heim location"
  
  # Get more results
  python examples/semantic_search_example.py --top-k 10 "poison resistance"
        """,
    )

    parser.add_argument("query", help="Search query")

    parser.add_argument(
        "--vector-path",
        default="vector_storage",
        help="Path to vector database (default: vector_storage)",
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
        help="Embedding model name (must match vectorization model)",
    )

    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of results to return (default: 5)"
    )

    args = parser.parse_args()

    # Validate vector database exists
    if not Path(args.vector_path).exists():
        print(f"ERROR: Vector database not found at: {args.vector_path}")
        print("\nFirst run vectorization:")
        print(
            f"  python scripts/vectorize-wiki.py --vector-db {args.vector_db} --output {args.vector_path}"
        )
        sys.exit(1)

    # Run search
    if args.vector_db == "qdrant":
        search_qdrant(args.query, args.vector_path, args.model, args.top_k)
    else:
        search_chromadb(args.query, args.vector_path, args.model, args.top_k)


if __name__ == "__main__":
    main()
