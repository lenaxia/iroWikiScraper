# Vector Embeddings Enhancement for iRO Wiki Database

**Date:** 2026-01-26  
**Status:** Design & Implementation  
**Related:** [goKore Integration Design](./2026-01-26_01_gokore_integration.md)

## Executive Summary

This document describes the addition of semantic search capabilities to the iRO Wiki scraper through vector embeddings. By pre-vectorizing wiki content, we enable natural language queries, contextual understanding, and RAG (Retrieval-Augmented Generation) integration for AI-powered bots.

## Motivation

### Current Limitations
- **Exact Match Only:** SQLite full-text search requires exact keyword matches
- **No Semantic Understanding:** Can't find "monster drops" when searching "mob loot"
- **Poor AI Context:** LLMs can't efficiently search 84K revisions
- **Manual Navigation:** Users must know exact page names

### Use Cases Enabled by Vector Search

1. **Natural Language Queries**
   ```
   User: "What's the best weapon for killing undead?"
   Bot: Searches semantically → finds Holy Avenger, Grand Cross skill, etc.
   ```

2. **Contextual Bot Responses**
   ```
   User: "How do I get to Glast Heim?"
   Bot: Finds navigation guides, quest prerequisites, mob warnings
   ```

3. **RAG Integration**
   ```
   LLM Query: "Explain the renewal damage formula"
   System: Retrieves relevant wiki sections → injects into context
   ```

4. **Cross-Reference Discovery**
   ```
   Query: "poison resistance"
   Finds: Poison resistance gear, Antidote items, Detoxify skill
   ```

## Architecture Design

### Multi-Release Strategy (Recommended)

Provide multiple release formats to support different deployment scenarios:

```
Releases:
├── irowiki-database-2026-01-26.tar.gz          # Base (SQLite only, 159 MB)
├── irowiki-qdrant-2026-01-26.tar.gz            # Qdrant + SQLite (~300 MB)
├── irowiki-chromadb-2026-01-26.tar.gz          # ChromaDB + SQLite (~250 MB)
└── irowiki-pgvector-2026-01-26.sql.gz          # PostgreSQL dump (~400 MB)
```

**Rationale:**
- Users download only what they need
- Smaller base package for simple use cases
- Easy to add new vector DB formats
- Clear versioning per release

### Alternative: Unified Package

Single release with all formats:
```
irowiki-complete-2026-01-26.tar.gz (~800 MB)
├── sqlite/irowiki.db
├── qdrant/collections/
├── chromadb/chroma.db
└── configs/
```

**Trade-offs:**
- ✅ One download for everything
- ❌ Larger download (5x base size)
- ❌ Complexity in unpacking

**Decision:** Start with multi-release, add unified package if users request it.

## Chunking Strategy

### Three-Level Approach

We'll support multiple chunking levels, with section-level as default:

#### 1. Page-Level Chunking
```python
# One vector per page
chunk = {
    "page_id": 123,
    "page_title": "Izlude",
    "content": "<full page content>",
    "metadata": {"namespace": 0, "last_modified": "2024-11-20"}
}
```

**Pros:** Simple, maintains full context  
**Cons:** Poor granularity (84K pages = 84K vectors)  
**Use Case:** Small wikis, general topic search

#### 2. Section-Level Chunking (Default)
```python
# Split by MediaWiki section headers (==, ===, etc.)
chunk = {
    "page_id": 123,
    "section_id": "History",
    "page_title": "Izlude",
    "section_title": "History",
    "content": "<section content>",
    "metadata": {
        "level": 2,  # == heading level
        "parent_section": None
    }
}
```

**Pros:** Good balance of context and granularity (~300K chunks)  
**Cons:** Section size varies  
**Use Case:** Most general-purpose searches (RECOMMENDED)

#### 3. Paragraph-Level Chunking
```python
# Split by paragraphs, preserve section context
chunk = {
    "page_id": 123,
    "paragraph_id": 5,
    "page_title": "Izlude",
    "section_title": "NPCs",
    "content": "<paragraph content>",
    "metadata": {
        "section_hierarchy": ["NPCs", "Quest Givers"]
    }
}
```

**Pros:** Highest precision (~1M chunks)  
**Cons:** May lose context, more storage  
**Use Case:** Fine-grained RAG retrieval

### Implementation Decision

**Default:** Section-level chunking
- Best balance for most use cases
- Reasonable chunk count (~300K)
- Preserves logical content boundaries
- Easy to understand for debugging

**Configurable:** Users can regenerate with different chunking via script flags.

## Embedding Models

### Comparison Matrix

| Model | Dimensions | Cost | Speed | Quality | License |
|-------|-----------|------|-------|---------|---------|
| `all-MiniLM-L6-v2` | 384 | Free | ⚡⚡⚡ Fast | ⭐⭐⭐ Good | Apache 2.0 |
| `bge-large-en-v1.5` | 1024 | Free | ⚡⚡ Medium | ⭐⭐⭐⭐ Better | MIT |
| `text-embedding-3-small` | 1536 | Paid | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Best | OpenAI |
| `text-embedding-3-large` | 3072 | Paid | ⚡ Slow | ⭐⭐⭐⭐⭐ Best | OpenAI |

### Performance Estimates

**For 300K chunks (section-level):**

| Model | Embed Time | Storage Size | Monthly Cost |
|-------|-----------|--------------|--------------|
| MiniLM | ~2 hours | ~460 MB | $0 |
| BGE-Large | ~6 hours | ~1.2 GB | $0 |
| OpenAI Small | ~4 hours | ~1.8 GB | ~$12 |
| OpenAI Large | ~8 hours | ~3.6 GB | ~$24 |

### Recommendation

**For Public Releases:** `all-MiniLM-L6-v2`
- Free for all users
- Fast inference (important for bots)
- Good quality for game wiki content
- Small storage footprint

**For Premium/Self-Hosted:** `bge-large-en-v1.5`
- Better quality than MiniLM
- Still free and open-source
- Reasonable performance

**For Production AI Services:** `text-embedding-3-small`
- Best quality for RAG
- Worth the cost for commercial use
- Reliable and maintained

## Vector Database Selection

### Primary: Qdrant

**Why Qdrant:**
- Self-hosted, no vendor lock-in
- Excellent performance (HNSW index)
- Rich filtering on metadata
- Docker-friendly deployment
- Active development, good docs

**Integration:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(path="./qdrant_storage")
client.create_collection(
    collection_name="irowiki_sections",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
```

**Query Example:**
```python
results = client.search(
    collection_name="irowiki_sections",
    query_vector=embed("best weapon for undead"),
    limit=10,
    query_filter={
        "must": [{"key": "namespace", "match": {"value": 0}}]
    }
)
```

### Secondary: ChromaDB

**Why ChromaDB:**
- Easiest setup (pip install)
- Good for development/testing
- Embedded mode (no separate service)
- Simple API

**Use Case:** Local development, small deployments

### Tertiary: pgvector

**Why pgvector:**
- For users already running PostgreSQL
- Unified database (relational + vector)
- ACID guarantees
- Familiar SQL interface

**Use Case:** Enterprise deployments with existing PostgreSQL infrastructure

## Metadata Schema

Each vector includes rich metadata for filtering and reference:

```json
{
  "page_id": 123,
  "revision_id": 456789,
  "page_title": "Izlude",
  "namespace": 0,
  "section_title": "NPCs",
  "section_level": 2,
  "chunk_type": "section",
  "last_modified": "2024-11-20T12:34:56Z",
  "contributor": "WikiEditor123",
  "word_count": 342,
  "has_templates": true,
  "categories": ["Cities", "Renewal"],
  "links_to": ["Prontera", "Izlude_Dungeon"],
  "db_reference": "sqlite://irowiki.db#pages.123"
}
```

**Benefits:**
- Filter by namespace (skip Talk/Template pages)
- Time-based filtering (recent changes)
- Category-based retrieval
- Cross-reference to SQLite for full data

## Implementation Plan

### Phase 1: Core Infrastructure (This Session)

1. ✅ Design document
2. ⏳ Vectorization script (`scripts/vectorize-wiki.py`)
3. ⏳ Chunking logic (section-level default)
4. ⏳ Qdrant integration
5. ⏳ Configuration system

### Phase 2: Additional Vector DBs

6. ChromaDB integration
7. pgvector SQL generation
8. Model comparison tool

### Phase 3: Testing & Documentation

9. Semantic search examples
10. RAG integration examples
11. Performance benchmarks
12. User documentation

### Phase 4: Release Packaging

13. Automated release generation
14. GitHub releases for each format
15. Docker images with pre-loaded data
16. goKore integration examples

## Usage Examples

### Example 1: Semantic Search in Bot

```go
// In goKore bot
func (b *WikiBot) HandleQuery(query string) (string, error) {
    // Embed user query
    embedding := b.embedModel.Embed(query)
    
    // Search vector DB
    results := b.vectorDB.Search(embedding, limit=5)
    
    // Fetch full content from SQLite
    for _, result := range results {
        page := b.wikiDB.GetPage(result.Metadata["page_id"])
        // Return formatted response
    }
}
```

### Example 2: RAG Context Injection

```python
# LLM context builder
def build_context(user_query: str, max_tokens: int = 2000):
    # Semantic search
    chunks = vector_db.search(embed(user_query), limit=10)
    
    # Rank by relevance
    ranked = rerank(chunks, user_query)
    
    # Build context within token limit
    context = []
    tokens = 0
    for chunk in ranked:
        chunk_tokens = count_tokens(chunk.content)
        if tokens + chunk_tokens > max_tokens:
            break
        context.append(chunk.content)
        tokens += chunk_tokens
    
    return "\n\n".join(context)
```

### Example 3: Cross-Reference Discovery

```python
# Find related content
def find_related(page_title: str, limit: int = 5):
    # Get page embedding
    page = db.get_page(page_title)
    page_vector = vector_db.get_by_id(page.id)
    
    # Find similar vectors
    similar = vector_db.search(
        query_vector=page_vector,
        limit=limit + 1,  # +1 to exclude self
        filter={"namespace": 0}
    )
    
    return [s for s in similar if s.page_title != page_title]
```

## Performance Targets

### Indexing Performance
- ⚡ 300K chunks in <4 hours (MiniLM on CPU)
- 💾 <500 MB storage per collection (MiniLM)
- 🔄 Incremental updates in <1 minute

### Query Performance
- ⚡ <50ms for single query (p95)
- ⚡ <5ms for batch queries (10 queries)
- 🎯 >0.85 relevance score for top-5 results

### Accuracy Targets
- 🎯 >90% recall@10 for known good matches
- 🎯 >95% precision@5 for highly relevant results
- 🎯 Human evaluation: >4/5 stars for top result

## Versioning Strategy

### Release Naming Convention
```
irowiki-{format}-{game-version}-{date}.tar.gz

Examples:
- irowiki-qdrant-renewal-2026-01-26.tar.gz
- irowiki-chromadb-classic-2026-01-26.tar.gz
```

### Version Tracking
Each vector DB includes metadata:
```json
{
  "scrape_date": "2026-01-26",
  "game_version": "renewal",
  "wiki_snapshot": "https://irowiki.org/w/index.php?title=Special:Version",
  "model": "all-MiniLM-L6-v2",
  "model_version": "v2",
  "chunk_strategy": "section-level",
  "total_chunks": 287543,
  "namespaces_included": [0, 6],
  "generator_version": "1.0.0"
}
```

## Future Enhancements

1. **Hybrid Search:** Combine vector + keyword search
2. **Multi-Modal:** Embed images from File: namespace
3. **Dynamic Updates:** Incremental vectorization for new revisions
4. **Cross-Wiki:** Embed multiple wikis (iRO + RMS + divine-pride)
5. **Fine-Tuned Models:** Train domain-specific embeddings on RO content

## Security Considerations

- Vector DBs contain only public wiki content
- No user data or credentials embedded
- Rate limiting for API-based embedding models
- Validate chunk content before embedding (strip personal data if any)

## Cost Analysis

### One-Time Costs (Initial Vectorization)
| Item | Cost |
|------|------|
| MiniLM (local) | $0 |
| OpenAI API (300K chunks) | $12-24 |
| Compute time (4-8 hours) | $0-5 (if cloud) |

### Ongoing Costs (Monthly Updates)
| Item | Cost |
|------|------|
| Incremental updates (~1K new chunks) | $0-0.50 |
| Storage (S3/GitHub) | $0-1 |
| CI/CD compute | $0-2 |

**Total Monthly:** <$5 for free models, <$30 for premium

## Success Metrics

- ✅ Vector DB releases published to GitHub
- ✅ <4 hour generation time for full vectorization
- ✅ goKore bot integration example working
- ✅ Documentation with 5+ usage examples
- ✅ User adoption: >10 downloads per release
- ✅ Community feedback: >4/5 stars for search quality

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

---

**Next Steps:** Implement `scripts/vectorize-wiki.py` with section-level chunking and Qdrant integration.
