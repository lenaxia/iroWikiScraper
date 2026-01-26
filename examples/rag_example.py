#!/usr/bin/env python3
"""
Example: RAG (Retrieval-Augmented Generation) with iRO Wiki

This script demonstrates how to use the vectorized wiki database for RAG,
where relevant wiki content is retrieved and injected into an LLM context.

Usage:
    python examples/rag_example.py "What's the best way to level from 1 to 99?"
    python examples/rag_example.py --max-context 4000 "Explain the renewal damage formula"
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print(
        "ERROR: sentence-transformers not installed. Run: pip install -r requirements-vector.txt"
    )
    sys.exit(1)


def count_tokens(text: str) -> int:
    """Rough token count estimate (1 token ≈ 4 characters)"""
    return len(text) // 4


def build_context_qdrant(
    query: str,
    vector_path: str,
    model_name: str,
    max_tokens: int = 2000,
    top_k: int = 20,
) -> Tuple[str, List[dict]]:
    """Build RAG context using Qdrant"""
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("ERROR: qdrant-client not installed")
        sys.exit(1)

    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"Connecting to Qdrant...")
    client = QdrantClient(path=vector_path)

    print(f"Embedding query...")
    query_vector = model.encode(query)

    print(f"Retrieving top {top_k} relevant chunks...")
    results = client.search(
        collection_name="irowiki", query_vector=query_vector.tolist(), limit=top_k
    )

    print(f"\nBuilding context (max {max_tokens} tokens)...")
    context_parts = []
    sources = []
    total_tokens = 0

    for result in results:
        payload = result.payload
        content = payload.get("content", "")
        chunk_tokens = count_tokens(content)

        # Check if adding this chunk would exceed limit
        if total_tokens + chunk_tokens > max_tokens:
            print(f"  Reached token limit. Using {len(context_parts)} chunks.")
            break

        # Format chunk with source attribution
        page_title = payload.get("page_title", "Unknown")
        section_title = payload.get("section_title")

        header = f"[{page_title}"
        if section_title:
            header += f" - {section_title}"
        header += f"]"

        formatted = f"{header}\n{content}"
        context_parts.append(formatted)

        # Track source
        sources.append(
            {
                "page": page_title,
                "section": section_title,
                "score": result.score,
                "chunk_type": payload.get("chunk_type"),
            }
        )

        total_tokens += chunk_tokens + count_tokens(header)

    context = "\n\n---\n\n".join(context_parts)

    print(f"  Final context: {len(context_parts)} chunks, ~{total_tokens} tokens")

    return context, sources


def build_rag_prompt(query: str, context: str) -> str:
    """Build the full prompt with context and query"""
    prompt = f"""You are an expert on Ragnarok Online (iRO). Answer the following question using ONLY the provided wiki context. If the context doesn't contain enough information, say so.

Wiki Context:
{context}

Question: {query}

Answer:"""
    return prompt


def display_sources(sources: List[dict]):
    """Display source attributions"""
    print("\n" + "=" * 80)
    print("Sources Used:")
    print("=" * 80)

    seen_pages = set()
    for source in sources:
        page = source["page"]
        if page not in seen_pages:
            section = f" ({source['section']})" if source["section"] else ""
            score = source["score"]
            print(f"  • {page}{section} - Relevance: {score:.3f}")
            seen_pages.add(page)


def main():
    parser = argparse.ArgumentParser(
        description="RAG example with iRO Wiki vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic RAG query
  python examples/rag_example.py "What's the best weapon for a Knight?"
  
  # Larger context window
  python examples/rag_example.py --max-context 4000 "Explain the refining system"
  
  # More retrieval candidates
  python examples/rag_example.py --top-k 30 "How do I make money at low level?"
        """,
    )

    parser.add_argument("query", help="User query")

    parser.add_argument(
        "--vector-path",
        default="vector_storage",
        help="Path to vector database (default: vector_storage)",
    )

    parser.add_argument(
        "--model", default="all-MiniLM-L6-v2", help="Embedding model name"
    )

    parser.add_argument(
        "--max-context",
        type=int,
        default=2000,
        help="Maximum tokens for context (default: 2000)",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of chunks to retrieve (default: 20)",
    )

    parser.add_argument(
        "--show-prompt", action="store_true", help="Show the full prompt with context"
    )

    args = parser.parse_args()

    # Validate
    if not Path(args.vector_path).exists():
        print(f"ERROR: Vector database not found at: {args.vector_path}")
        print("\nFirst run vectorization:")
        print(f"  python scripts/vectorize-wiki.py --output {args.vector_path}")
        sys.exit(1)

    print(f"\nQuery: {args.query}")
    print("-" * 80)

    # Build context
    context, sources = build_context_qdrant(
        args.query, args.vector_path, args.model, args.max_context, args.top_k
    )

    # Build full prompt
    full_prompt = build_rag_prompt(args.query, context)

    # Display results
    if args.show_prompt:
        print("\n" + "=" * 80)
        print("Full Prompt to LLM:")
        print("=" * 80)
        print(full_prompt)
    else:
        print("\n" + "=" * 80)
        print("Context Retrieved (ready for LLM):")
        print("=" * 80)
        print(f"Token count: ~{count_tokens(full_prompt)}")
        print(f"Chunks used: {len(sources)}")
        print("\nPreview (first 500 chars):")
        print("-" * 80)
        preview = context[:500] + "..." if len(context) > 500 else context
        print(preview)

    # Display sources
    display_sources(sources)

    print("\n" + "=" * 80)
    print("Next Steps:")
    print("=" * 80)
    print("1. Send the full prompt to your LLM (GPT-4, Claude, etc.)")
    print("2. The LLM will use the wiki context to answer the question")
    print("3. Display the answer with source attributions")
    print("\nExample API call:")
    print("""
    import openai
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7
    )
    print(response.choices[0].message.content)
    """)


if __name__ == "__main__":
    main()
