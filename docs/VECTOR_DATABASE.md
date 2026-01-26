# Vector Database & Semantic Search

This directory contains tools and examples for creating and using vector embeddings of the iRO Wiki database for semantic search and RAG (Retrieval-Augmented Generation).

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-vector.txt
```

This installs:
- `sentence-transformers` - For generating embeddings
- `qdrant-client` - For Qdrant vector database
- `chromadb` - For ChromaDB (alternative)
- `numpy` - For numerical operations

### 2. Vectorize the Database

```bash
# Default: Section-level chunking with MiniLM model to Qdrant
python scripts/vectorize-wiki.py --db data/irowiki.db --output vector_storage

# Use ChromaDB instead
python scripts/vectorize-wiki.py --vector-db chromadb --output chroma_storage

# Use different embedding model
python scripts/vectorize-wiki.py --model bge-large-en-v1.5

# Use paragraph-level chunking for finer granularity
python scripts/vectorize-wiki.py --chunk-level paragraph
```

**Expected Performance:**
- ~300K chunks from 10K pages (section-level)
- ~2-4 hours on CPU with MiniLM model
- ~500 MB storage for Qdrant
- ~250 MB for ChromaDB

### 3. Run Semantic Search

```bash
# Basic search
python examples/semantic_search_example.py "best weapon for undead"

# Get more results
python examples/semantic_search_example.py --top-k 10 "how to get to glast heim"

# Search in ChromaDB
python examples/semantic_search_example.py --vector-db chromadb "poison resistance"
```

### 4. Use for RAG

```bash
# Build context for LLM
python examples/rag_example.py "What's the best way to level from 1 to 99?"

# Show full prompt
python examples/rag_example.py --show-prompt "Explain renewal damage formula"

# Larger context window
python examples/rag_example.py --max-context 4000 "Tell me about Izlude"
```

## Architecture

### Chunking Strategies

**Page-Level** (Simple)
- One vector per page
- Maintains full context
- ~10K chunks for full wiki
- Good for: Small wikis, general topic search

**Section-Level** (Default, Recommended)
- Split by MediaWiki headings (`==`, `===`, etc.)
- Balanced context and granularity
- ~300K chunks for full wiki
- Good for: Most use cases

**Paragraph-Level** (Fine-grained)
- Split by paragraphs
- Highest precision
- ~1M chunks for full wiki
- Good for: RAG with small context windows

### Embedding Models

| Model | Dimensions | Speed | Quality | Cost |
|-------|-----------|-------|---------|------|
| `all-MiniLM-L6-v2` (default) | 384 | ⚡⚡⚡ | ⭐⭐⭐ | Free |
| `bge-large-en-v1.5` | 1024 | ⚡⚡ | ⭐⭐⭐⭐ | Free |
| `text-embedding-3-small` | 1536 | ⚡⚡ | ⭐⭐⭐⭐⭐ | $0.02/1M tokens |

### Vector Databases

**Qdrant** (Recommended)
- Self-hosted, production-ready
- Excellent performance (HNSW index)
- Rich metadata filtering
- Docker-friendly

**ChromaDB**
- Easy setup (`pip install`)
- Good for development
- Embedded mode (no separate service)

**pgvector**
- For PostgreSQL users
- Unified relational + vector database
- SQL interface

## Examples

### Semantic Search

```python
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

# Load model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Connect to Qdrant
client = QdrantClient(path='vector_storage')

# Search
query_vector = model.encode("best weapon for undead")
results = client.search(
    collection_name="irowiki",
    query_vector=query_vector.tolist(),
    limit=5
)

for result in results:
    print(f"{result.payload['page_title']}: {result.score:.3f}")
```

### RAG Context Building

```python
def build_rag_context(query: str, max_tokens: int = 2000):
    # Embed query
    query_vector = model.encode(query)
    
    # Retrieve relevant chunks
    results = client.search(
        collection_name="irowiki",
        query_vector=query_vector.tolist(),
        limit=20
    )
    
    # Build context within token limit
    context = []
    tokens = 0
    for result in results:
        content = result.payload['content']
        chunk_tokens = len(content) // 4  # Rough estimate
        
        if tokens + chunk_tokens > max_tokens:
            break
        
        context.append(content)
        tokens += chunk_tokens
    
    return "\n\n".join(context)

# Use with LLM
context = build_rag_context("How do I get to Glast Heim?")
prompt = f"""Context: {context}

Question: How do I get to Glast Heim?

Answer:"""

# Send to GPT-4, Claude, etc.
```

### goKore Bot Integration

```go
// In goKore bot
type WikiBot struct {
    vectorDB *qdrant.Client
    embedder *embeddings.Model
    wikiDB   *sql.DB
}

func (b *WikiBot) HandleQuery(query string) (string, error) {
    // Embed query
    vector, err := b.embedder.Embed(query)
    if err != nil {
        return "", err
    }
    
    // Search vector DB
    results, err := b.vectorDB.Search(ctx, &qdrant.SearchPoints{
        CollectionName: "irowiki",
        Vector:         vector,
        Limit:          5,
    })
    
    // Format response
    var response strings.Builder
    for _, hit := range results {
        page := hit.Payload["page_title"].(string)
        content := hit.Payload["content"].(string)
        
        response.WriteString(fmt.Sprintf("**%s**\n%s\n\n", page, content))
    }
    
    return response.String(), nil
}
```

## Performance Tuning

### Speed Up Vectorization

1. **Use GPU:**
   ```python
   model = SentenceTransformer('all-MiniLM-L6-v2', device='cuda')
   ```

2. **Increase Batch Size:**
   ```bash
   python scripts/vectorize-wiki.py --batch-size 64
   ```

3. **Use Faster Model:**
   ```bash
   python scripts/vectorize-wiki.py --model all-MiniLM-L6-v2
   ```

### Improve Search Quality

1. **Use Better Model:**
   ```bash
   python scripts/vectorize-wiki.py --model bge-large-en-v1.5
   ```

2. **Adjust Chunking:**
   ```bash
   # More context per chunk
   python scripts/vectorize-wiki.py --chunk-level page
   
   # More precise matching
   python scripts/vectorize-wiki.py --chunk-level paragraph
   ```

3. **Hybrid Search:**
   Combine vector search with keyword search for best results.

## File Structure

```
scripts/
  vectorize-wiki.py          # Main vectorization script

examples/
  semantic_search_example.py # Semantic search demo
  rag_example.py             # RAG integration demo

docs/design/
  2026-01-26_02_vector_embeddings.md  # Full design document

vector_storage/              # Generated Qdrant database
  collection/
  metadata.json

chroma_storage/              # Generated ChromaDB database
  chroma.db
  metadata.json
```

## Troubleshooting

### "Vector database not found"
Run vectorization first:
```bash
python scripts/vectorize-wiki.py
```

### "Model download failed"
Models are downloaded from HuggingFace on first use. Check internet connection.

### "Out of memory"
Reduce batch size:
```bash
python scripts/vectorize-wiki.py --batch-size 16
```

### "Search returns irrelevant results"
- Use a better embedding model (`bge-large-en-v1.5`)
- Try different chunking strategy
- Increase `top_k` to see more candidates

## Advanced Usage

### Incremental Updates

```bash
# Vectorize only new revisions
python scripts/vectorize-wiki.py --incremental --since 2026-01-26
```

### Multi-Language Support

```bash
# Use multilingual model
python scripts/vectorize-wiki.py --model paraphrase-multilingual-MiniLM-L12-v2
```

### Custom Metadata Filtering

```python
# Search only in specific namespace
results = client.search(
    collection_name="irowiki",
    query_vector=query_vector.tolist(),
    query_filter={
        "must": [
            {"key": "namespace", "match": {"value": 0}}  # Main namespace only
        ]
    },
    limit=5
)
```

## References

- [Design Document](../docs/design/2026-01-26_02_vector_embeddings.md)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence Transformers](https://www.sbert.net/)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

## Next Steps

1. Generate vector database from latest scrape
2. Test search quality with sample queries
3. Integrate with goKore bots
4. Create GitHub releases with pre-vectorized databases
5. Add Docker images with embedded vector DBs
