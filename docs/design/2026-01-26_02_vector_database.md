# Vector Database Integration for iRO Wiki

**Date**: 2026-01-26
**Author**: AI Assistant
**Status**: Draft

## Overview

Design for creating vectorized versions of the iRO Wiki database to enable semantic search and AI-powered knowledge retrieval for bot instances. Different releases would represent snapshots at different points in game history.

## Goals

- **Semantic search**: Bots can find relevant info without exact keyword matches
- **AI context**: Feed relevant wiki content to LLM for intelligent responses
- **Historical versions**: Track game changes over time (e.g., "pre-renewal" vs "renewal")
- **Efficient retrieval**: Fast similarity search for bot decision-making
- **Easy integration**: Drop-in addition to existing SQLite database

## Use Cases

### 1. Intelligent Item Queries
```
Bot query: "What's a good healing item for level 50?"
→ Vector search finds: White Potion, Yggdrasil Berry, healing items guide
→ LLM synthesizes: "White Potion is best for level 50 (500 HP, affordable)"
```

### 2. Quest Assistance
```
Bot query: "How do I get to Glast Heim?"
→ Vector search finds: Glast Heim page, travel guides, map connections
→ Bot navigates: Uses map data + wiki context
```

### 3. Monster Strategy
```
Bot query: "How to fight Angeling?"
→ Vector search finds: Angeling page, Holy element info, equipment guides
→ Bot adapts: Switches to shadow element attacks
```

### 4. Historical Queries
```
Bot query: "What was Prontera like in 2010?" [using v2010-snapshot]
→ Returns: Pre-renewal Prontera content
→ Compare with: v2024-snapshot for changes
```

## Architecture

### Multi-Release Strategy

```
GitHub Releases:
├── v2026-01-26/
│   ├── irowiki-database-2026-01-26.tar.gz          (159 MB) ← SQLite DB
│   └── irowiki-vectors-2026-01-26.tar.gz           (50-200 MB) ← Vector DB
├── v2026-02-26/
│   ├── irowiki-database-2026-02-26.tar.gz
│   └── irowiki-vectors-2026-02-26.tar.gz
└── snapshots/
    ├── v2010-pre-renewal/                           ← Historical snapshots
    │   ├── irowiki-database-2010-pre-renewal.tar.gz
    │   └── irowiki-vectors-2010-pre-renewal.tar.gz
    └── v2015-renewal/
        ├── irowiki-database-2015-renewal.tar.gz
        └── irowiki-vectors-2015-renewal.tar.gz
```

### Vector Database Options

#### Option 1: ChromaDB (Recommended) ⭐

**Pros:**
- ✅ Embeddable (no separate service needed)
- ✅ SQLite-backed (aligns with current architecture)
- ✅ Python & Go clients available
- ✅ Good documentation
- ✅ Persistent storage
- ✅ Filter by metadata

**Cons:**
- ❌ Requires Python runtime (or Go client)
- ❌ ~50-100 MB additional size

**Storage:**
```
data/
├── irowiki.db              # Original SQLite
└── chroma/                 # Vector DB
    ├── chroma.sqlite3      # ChromaDB storage
    └── embeddings/         # Vector data
```

#### Option 2: Qdrant Embedded

**Pros:**
- ✅ Rust-based (fast, small)
- ✅ Embeddable
- ✅ Good Go client
- ✅ Advanced filtering

**Cons:**
- ❌ Larger binary size
- ❌ More complex

#### Option 3: Simple Vector Files (Lightweight)

**Pros:**
- ✅ No dependencies
- ✅ Smallest footprint
- ✅ Easy to implement

**Cons:**
- ❌ Manual similarity search
- ❌ Slower queries
- ❌ Less features

**Format:**
```json
{
  "page_id": 213,
  "title": "Izlude",
  "embedding": [0.123, -0.456, ...],  // 384 or 768 dimensions
  "content_preview": "Izlude is a port town...",
  "metadata": {
    "namespace": 0,
    "last_updated": "2024-04-23T12:30:02Z",
    "size": 12683,
    "categories": ["Towns", "Locations"]
  }
}
```

## Data Structure

### What to Vectorize

#### 1. Page Content (Primary)
- **Latest revision content** per page
- Chunk large pages (e.g., 512 tokens per chunk)
- Store page_id, chunk_index, embedding

#### 2. Page Titles (Secondary)
- Just the title for quick matching
- Useful for exact/fuzzy matching

#### 3. Metadata Filters
- Namespace (Main, File, Category, etc.)
- Last modified date
- Content size
- Categories/tags

### Vector Schema

```python
# ChromaDB Collection
collection = {
    "name": "irowiki_pages",
    "embeddings": [...],  # 768-dim vectors
    "documents": [...],    # Text chunks
    "metadatas": [
        {
            "page_id": 213,
            "title": "Izlude",
            "namespace": 0,
            "chunk_index": 0,
            "total_chunks": 3,
            "timestamp": "2024-04-23T12:30:02Z",
            "size": 12683,
            "url": "https://irowiki.org/wiki/Izlude"
        }
    ],
    "ids": ["page_213_chunk_0", ...]
}
```

## Vectorization Pipeline

### Script: `scripts/vectorize-wiki.py`

```python
#!/usr/bin/env python3
"""
Vectorize iRO Wiki database for semantic search.

Usage:
    python scripts/vectorize-wiki.py data/irowiki.db \
        --output data/vectors/ \
        --model sentence-transformers/all-MiniLM-L6-v2 \
        --chunk-size 512
"""

import sqlite3
from sentence_transformers import SentenceTransformer
import chromadb

def vectorize_wiki(db_path, output_dir, model_name, chunk_size):
    # Load embedding model
    model = SentenceTransformer(model_name)
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all pages with latest content
    cursor.execute("""
        SELECT p.page_id, p.title, p.namespace, r.content, r.timestamp
        FROM pages p
        JOIN revisions r ON p.page_id = r.page_id
        WHERE r.revision_id = (
            SELECT MAX(revision_id) FROM revisions WHERE page_id = p.page_id
        )
        AND LENGTH(r.content) > 0
    """)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=output_dir)
    collection = client.get_or_create_collection(
        name="irowiki_pages",
        metadata={"description": "iRO Wiki pages with embeddings"}
    )
    
    # Vectorize in batches
    batch_size = 100
    documents = []
    embeddings = []
    metadatas = []
    ids = []
    
    for page_id, title, namespace, content, timestamp in cursor:
        # Chunk large content
        chunks = chunk_text(content, chunk_size)
        
        for chunk_idx, chunk in enumerate(chunks):
            # Create embedding
            embedding = model.encode(chunk)
            
            documents.append(chunk)
            embeddings.append(embedding.tolist())
            metadatas.append({
                "page_id": page_id,
                "title": title,
                "namespace": namespace,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks),
                "timestamp": timestamp,
                "size": len(content)
            })
            ids.append(f"page_{page_id}_chunk_{chunk_idx}")
            
            # Insert batch
            if len(documents) >= batch_size:
                collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                documents, embeddings, metadatas, ids = [], [], [], []
    
    # Insert remaining
    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    print(f"Vectorized {cursor.rowcount} pages")
    conn.close()
```

### Embedding Models

#### Option 1: all-MiniLM-L6-v2 (Recommended for Start)
- **Size**: 80 MB
- **Dimensions**: 384
- **Speed**: 14,000 sentences/sec
- **Quality**: Good for general semantic search
- **Vector DB size**: ~50-100 MB for 10k pages

#### Option 2: all-mpnet-base-v2 (Better Quality)
- **Size**: 420 MB
- **Dimensions**: 768
- **Speed**: 2,800 sentences/sec
- **Quality**: Better semantic understanding
- **Vector DB size**: ~100-200 MB for 10k pages

#### Option 3: OpenAI text-embedding-3-small (Cloud)
- **Cost**: $0.02 per 1M tokens (~$2-5 for full wiki)
- **Dimensions**: 1536
- **Quality**: Excellent
- **Speed**: API rate limited
- **Vector DB size**: ~200-400 MB

### Recommended: all-MiniLM-L6-v2
- Good balance of size/speed/quality
- Fully offline
- Fast vectorization (~5-10 minutes for full wiki)

## Release Strategy

### Standard Release (Current)

```
v2026-01-26/
└── irowiki-database-2026-01-26.tar.gz (159 MB)
    └── irowiki.db (1.1 GB)
        ├── Pages: 10,516
        ├── Revisions: 84,486
        └── Content: 960 MB
```

### Vector Release (New)

```
v2026-01-26/
├── irowiki-database-2026-01-26.tar.gz (159 MB)
└── irowiki-vectors-2026-01-26.tar.gz (50-100 MB)
    └── chroma/
        ├── chroma.sqlite3          # ChromaDB metadata
        └── data/                   # Vector embeddings
```

### Combined Usage

```bash
# Download both
wget https://github.com/.../v2026-01-26/irowiki-database-2026-01-26.tar.gz
wget https://github.com/.../v2026-01-26/irowiki-vectors-2026-01-26.tar.gz

# Extract
tar -xzf irowiki-database-2026-01-26.tar.gz -C data/
tar -xzf irowiki-vectors-2026-01-26.tar.gz -C data/

# Structure
data/
├── irowiki.db          # SQLite database
└── chroma/             # Vector database
```

## Historical Snapshots

### Game Version Tracking

Create special releases for major game updates:

```
Releases:
├── snapshots/pre-renewal-2010/
│   ├── irowiki-database-pre-renewal-2010.tar.gz
│   └── irowiki-vectors-pre-renewal-2010.tar.gz
├── snapshots/renewal-2015/
│   ├── irowiki-database-renewal-2015.tar.gz
│   └── irowiki-vectors-renewal-2015.tar.gz
├── snapshots/episode-17-2020/
│   ├── irowiki-database-ep17-2020.tar.gz
│   └── irowiki-vectors-ep17-2020.tar.gz
└── latest/  (symlink to current)
    ├── irowiki-database-2026-01-26.tar.gz
    └── irowiki-vectors-2026-01-26.tar.gz
```

### Use Cases for Historical Data

1. **Compare game evolution**
   ```
   Bot: "What changed about Prontera between 2010 and 2024?"
   → Query both snapshots, compare results
   ```

2. **Server-specific knowledge**
   ```
   Pre-renewal server bot → Use pre-renewal snapshot
   Renewal server bot → Use renewal snapshot
   ```

3. **Historical research**
   ```
   "What quests were available in Episode 13?"
   "When was X item introduced?"
   ```

## goKore Integration

### Embedded Vector DB Approach

```go
// internal/bot/shared_resources.go

import (
    wikisdk "github.com/lenaxia/iRO-Wiki-Scraper/sdk"
    chromadb "github.com/amikos-tech/chroma-go"  // Go client for ChromaDB
)

type SharedResources struct {
    // ... existing fields ...
    
    // Wiki databases
    WikiDB         *wikisdk.Database     // SQLite (structured data)
    WikiVectorDB   *chromadb.Client      // ChromaDB (semantic search)
    WikiVersion    string                 // e.g., "v2026-01-26"
}

func NewSharedResources(dispatcher ...*hook.Dispatcher) *SharedResources {
    // ... existing code ...
    
    // Load wiki databases
    wikiDB, err := wikisdk.OpenDatabase("/app/data/irowiki.db")
    if err != nil {
        logger.WithError(err).Warn("Wiki database unavailable")
    }
    
    // Load vector database (optional)
    vectorDB, err := chromadb.NewClient(chromadb.WithBasePath("/app/data/chroma"))
    if err != nil {
        logger.WithError(err).Warn("Vector database unavailable, semantic search disabled")
        vectorDB = nil  // Graceful degradation
    }
    
    resources := &SharedResources{
        // ... existing fields ...
        WikiDB:       wikiDB,
        WikiVectorDB: vectorDB,
        WikiVersion:  os.Getenv("WIKI_VERSION") or "v2026-01-26",
    }
    
    return resources
}
```

### Query Interface

```go
// internal/bot/wiki/query.go

type WikiQueryEngine struct {
    sqlDB    *wikisdk.Database
    vectorDB *chromadb.Client
    logger   *log.Logger
}

// SemanticSearch performs vector similarity search
func (q *WikiQueryEngine) SemanticSearch(query string, limit int) ([]SearchResult, error) {
    if q.vectorDB == nil {
        // Fallback to SQL full-text search
        return q.sqlDB.SearchPages(query)
    }
    
    // Get collection
    collection := q.vectorDB.GetCollection("irowiki_pages")
    
    // Query vectors
    results, err := collection.Query(
        queryTexts: []string{query},
        nResults:   limit,
        where:      map[string]interface{}{"namespace": 0},  // Filter to main namespace
    )
    
    // Enrich with full page data from SQLite
    enriched := make([]SearchResult, len(results.IDs[0]))
    for i, id := range results.IDs[0] {
        metadata := results.Metadatas[0][i]
        pageID := metadata["page_id"].(int)
        
        // Get full page from SQLite
        page, _ := q.sqlDB.GetPage(pageID)
        content, _ := q.sqlDB.GetLatestContent(pageID)
        
        enriched[i] = SearchResult{
            PageID:     pageID,
            Title:      page.Title,
            Content:    content,
            Similarity: results.Distances[0][i],
            Chunk:      results.Documents[0][i],
        }
    }
    
    return enriched, nil
}

// GetContextForLLM retrieves relevant wiki context for an LLM prompt
func (q *WikiQueryEngine) GetContextForLLM(query string, maxTokens int) (string, error) {
    results, err := q.SemanticSearch(query, 5)
    if err != nil {
        return "", err
    }
    
    // Build context string
    var context strings.Builder
    context.WriteString("=== Relevant Wiki Information ===\n\n")
    
    tokens := 0
    for _, result := range results {
        chunk := result.Chunk
        chunkTokens := len(chunk) / 4  // Rough estimate
        
        if tokens + chunkTokens > maxTokens {
            break
        }
        
        context.WriteString(fmt.Sprintf("## %s\n%s\n\n", result.Title, chunk))
        tokens += chunkTokens
    }
    
    return context.String(), nil
}
```

### Bot Usage Examples

```go
// Semantic search
results, _ := bot.sharedResources.WikiQuery.SemanticSearch("healing consumables", 5)
for _, r := range results {
    bot.logger.Infof("Found: %s (similarity: %.2f)", r.Title, r.Similarity)
}

// Get context for LLM
context, _ := bot.sharedResources.WikiQuery.GetContextForLLM("how to reach Glast Heim", 2000)
llmPrompt := fmt.Sprintf("%s\n\nUser question: %s", context, userQuestion)
response, _ := bot.sharedResources.AsyncLLMClient.Query(llmPrompt)

// Hybrid query (exact + semantic)
exactMatch, _ := bot.sharedResources.WikiDB.GetPageByTitle("Poring Card")
if exactMatch != nil {
    return exactMatch  // Exact match found
}
// Fall back to semantic search
semanticResults, _ := bot.sharedResources.WikiQuery.SemanticSearch("poring card", 3)
```

## Implementation Plan

### Phase 1: Vectorization Script

Create `scripts/vectorize-wiki.py`:

```bash
# Install dependencies
pip install sentence-transformers chromadb sqlite3

# Vectorize database
python scripts/vectorize-wiki.py \
    data/irowiki.db \
    --output data/chroma/ \
    --model sentence-transformers/all-MiniLM-L6-v2 \
    --chunk-size 512 \
    --batch-size 100
```

**Output:**
- `data/chroma/` directory with vector database
- Metadata about model, dimensions, chunk size

**Time estimate:** 10-30 minutes for 10k pages

### Phase 2: Release Packaging

Extend `scripts/local-scrape-and-release.sh`:

```bash
# After scraping completes
if [[ "$VECTORIZE" == "true" ]]; then
    echo "=== Vectorizing Wiki Content ==="
    python scripts/vectorize-wiki.py data/irowiki.db \
        --output data/chroma/ \
        --model all-MiniLM-L6-v2
    
    # Package vectors
    tar -czf data/irowiki-vectors-${DATE}.tar.gz -C data chroma/
    
    # Upload to release
    gh release upload "$VERSION" "data/irowiki-vectors-${DATE}.tar.gz"
fi
```

### Phase 3: goKore Integration

Add to goKore:
1. Add ChromaDB Go client dependency
2. Extend SharedResources
3. Create WikiQueryEngine
4. Update Dockerfile to include vector DB
5. Add environment variable for wiki version selection

### Phase 4: Historical Snapshots

Create snapshots manually for major game versions:

```bash
# Get old revisions from a specific date
python scripts/create-historical-snapshot.py \
    --date 2010-01-01 \
    --output data/irowiki-2010.db \
    --label "pre-renewal"

# Vectorize historical snapshot
python scripts/vectorize-wiki.py data/irowiki-2010.db \
    --output data/chroma-2010/ \
    --model all-MiniLM-L6-v2

# Create special release
gh release create snapshots/pre-renewal-2010 \
    data/irowiki-2010.db.tar.gz \
    data/chroma-2010.tar.gz \
    --title "iRO Wiki - Pre-Renewal (2010)" \
    --notes "Historical snapshot for pre-renewal servers"
```

## Cost & Size Analysis

### Storage Requirements

Based on 10,516 pages, 960 MB content:

| Component | Size (Uncompressed) | Size (Compressed) |
|-----------|---------------------|-------------------|
| SQLite DB | 1.1 GB | 159 MB |
| Vector DB (384-dim) | 100-150 MB | 30-50 MB |
| Vector DB (768-dim) | 200-300 MB | 60-100 MB |
| **Total (384-dim)** | **1.2-1.3 GB** | **~200 MB** |
| **Total (768-dim)** | **1.3-1.4 GB** | **~260 MB** |

### GitHub Release Limits

- ✅ 2 GB per file: Both fit comfortably
- ✅ 10 GB per release: Can store 40+ releases
- ✅ Bandwidth: Unlimited for public repos

### Docker Image Impact

```dockerfile
# Current goKore image: ~50 MB (Alpine + binary)
# With wiki DB: ~200 MB (+150 MB)
# With vectors: ~260 MB (+210 MB)

# Still acceptable for container image
```

### Compute Requirements

**Vectorization (one-time):**
- CPU: 10-30 minutes on laptop
- RAM: 2-4 GB
- GPU: Optional (5x faster with CUDA)

**Query (runtime):**
- CPU: <10ms per query
- RAM: 100-200 MB loaded in memory
- No GPU needed

## Update Process

### Monthly Updates

```bash
# 1. Scrape latest wiki
cd ~/personal/iRO-Wiki-Scraper
./scripts/local-scrape-and-release.sh --incremental

# 2. Vectorize
python scripts/vectorize-wiki.py data/irowiki.db \
    --output data/chroma/ \
    --model all-MiniLM-L6-v2

# 3. Package both
DATE=$(date +%Y-%m-%d)
tar -czf data/irowiki-database-${DATE}.tar.gz -C data irowiki.db
tar -czf data/irowiki-vectors-${DATE}.tar.gz -C data chroma/

# 4. Create release
gh release create v${DATE} \
    data/irowiki-database-${DATE}.tar.gz \
    data/irowiki-vectors-${DATE}.tar.gz \
    --title "iRO Wiki Archive - ${DATE}" \
    --notes "..."

# 5. Update goKore
cd ~/personal/goKore
# Update WIKI_VERSION in Dockerfile or download new DB
docker-compose build
docker-compose up -d
```

## Alternatives Considered

### 1. Separate Microservice (Vector Search API)

**Pros:**
- Can scale independently
- Reusable by multiple services
- Hot-reload new vectors

**Cons:**
- Network latency (10-50ms overhead)
- More infrastructure complexity
- Requires API layer

**Decision:** Reject for now, embedded is simpler

### 2. PostgreSQL with pgvector

**Pros:**
- Single database (SQL + vectors)
- Familiar SQL interface
- Good for production

**Cons:**
- Requires PostgreSQL (heavier than SQLite)
- More complex deployment
- Overkill for read-only data

**Decision:** Reject, SQLite + ChromaDB is lighter

### 3. In-Memory Vector Search

**Pros:**
- Fastest queries (<1ms)
- Simple implementation

**Cons:**
- 1+ GB RAM usage
- Lost on restart (need reload)
- Not scalable

**Decision:** Reject, persistent storage better

### 4. OpenAI Embeddings API (Cloud)

**Pros:**
- Best quality embeddings
- No local compute needed

**Cons:**
- Costs $2-5 per vectorization
- API dependency
- Privacy concerns (sending wiki text to OpenAI)
- Monthly cost for updates

**Decision:** Reject, local models are free and private

## Implementation Checklist

### Vectorization Pipeline
- [ ] Create `scripts/vectorize-wiki.py`
- [ ] Add requirements: `sentence-transformers`, `chromadb`
- [ ] Test on sample data (100 pages)
- [ ] Run full vectorization (10,516 pages)
- [ ] Verify embedding quality with test queries
- [ ] Document model choice and parameters

### Release Process
- [ ] Update `local-scrape-and-release.sh` to optionally vectorize
- [ ] Add `--vectorize` flag
- [ ] Package vector DB as separate artifact
- [ ] Update release notes template
- [ ] Test download and extraction

### goKore Integration
- [ ] Add ChromaDB Go client dependency
- [ ] Extend SharedResources with WikiVectorDB
- [ ] Create WikiQueryEngine wrapper
- [ ] Add semantic search methods
- [ ] Add LLM context provider
- [ ] Update Dockerfile to include vector DB
- [ ] Add WIKI_VERSION environment variable
- [ ] Test queries in bot instance

### Historical Snapshots
- [ ] Create script to extract historical snapshots by date
- [ ] Identify key game versions (pre-renewal, renewal, episodes)
- [ ] Create and vectorize historical snapshots
- [ ] Create special releases for each version
- [ ] Document version differences

### Documentation
- [ ] Add vectorization guide to LOCAL_SCRAPING.md
- [ ] Create usage examples for bot developers
- [ ] Document query patterns and best practices
- [ ] Add troubleshooting section

## Testing Strategy

### Vector Quality Tests

```python
# Test semantic similarity
test_queries = [
    ("healing items", ["White Potion", "Yggdrasil Berry", "Healing Items"]),
    ("prontera location", ["Prontera", "Capital City", "Travel Guide"]),
    ("poring monster", ["Poring", "Drops", "Monster Database"]),
]

for query, expected_results in test_queries:
    results = vector_db.query(query, n_results=5)
    assert any(exp in [r.title for r in results] for exp in expected_results)
```

### Integration Tests

```go
func TestWikiSemanticSearch(t *testing.T) {
    resources := setupTestResources()
    
    // Test semantic search
    results, err := resources.WikiQuery.SemanticSearch("healing consumables", 5)
    assert.NoError(t, err)
    assert.NotEmpty(t, results)
    
    // Results should include healing items
    titles := extractTitles(results)
    assert.Contains(t, titles, "White Potion", "Healing items should be found")
}

func TestLLMContextGeneration(t *testing.T) {
    resources := setupTestResources()
    
    context, err := resources.WikiQuery.GetContextForLLM("how to reach glast heim", 2000)
    assert.NoError(t, err)
    assert.Contains(t, context, "Glast Heim")
    assert.Less(t, len(context), 10000)  // Should be within token limit
}
```

## Performance Estimates

### Vectorization Performance

**Hardware:** Modern laptop (8-core CPU, 16 GB RAM)

| Pages | Model | Time | Vector DB Size |
|-------|-------|------|----------------|
| 1,000 | MiniLM-L6 | 2-3 min | 5-10 MB |
| 10,000 | MiniLM-L6 | 10-20 min | 50-100 MB |
| 10,000 | mpnet-base | 30-60 min | 100-200 MB |

### Query Performance

| Operation | SQLite | Vector DB | Combined |
|-----------|--------|-----------|----------|
| Exact match | <1ms | - | <1ms |
| Keyword search | 5-10ms | - | 5-10ms |
| Semantic search | - | 10-20ms | 10-20ms |
| Hybrid query | <1ms | 10-20ms | 10-20ms |
| Batch (10 queries) | 10-50ms | 100-200ms | 100-200ms |

**Conclusion:** Performance is excellent for bot use cases.

## Security & Privacy

### Data Privacy
- ✅ All processing local (no cloud APIs if using local models)
- ✅ No telemetry or data collection
- ✅ Self-contained embeddings

### Resource Limits
- ✅ Read-only databases (no write access)
- ✅ Memory limits via Docker
- ✅ Query timeouts

### Update Integrity
- ✅ SHA256 checksums for releases
- ✅ Git tags for version tracking
- ✅ Reproducible builds

## Cost Analysis

### One-Time Costs (Setup)
- Development time: 8-16 hours
- Initial vectorization: Free (local compute)

### Ongoing Costs (Monthly)
- Scraping: Free (local, 3 hours)
- Vectorization: Free (local, 15 minutes)
- Storage: Free (GitHub releases)
- Bandwidth: Free (GitHub)

**Total: $0/month** ✅

### Alternative: Cloud Embeddings
- OpenAI: $2-5/month
- Cohere: $1-3/month

## Migration Path

### Start: Embedded (Recommended)

```
goKore container (210 MB)
├── Binary
├── SQLite DB
└── Vector DB
```

### Later: Hybrid (If Needed)

```
goKore container (60 MB)
├── Binary
└── Vector client

wiki-service container (200 MB)
├── SQLite DB
├── Vector DB
└── gRPC API
```

### Future: Distributed (If Scaling)

```
goKore instances (60 MB each)
    ↓ gRPC
wiki-service cluster
    ↓
Vector DB cluster (Qdrant/Weaviate)
```

**Decision:** Start embedded, evolve as needed.

## Recommendations

### For Initial Implementation

1. ✅ **Use embedded approach** in goKore Docker image
2. ✅ **Use all-MiniLM-L6-v2** model (384-dim)
3. ✅ **Use ChromaDB** for vector storage
4. ✅ **Release both** SQLite + Vector DB together
5. ✅ **Graceful degradation** if vector DB missing

### For Production

1. Create monthly releases with both databases
2. Use vector search for semantic queries
3. Fall back to SQL for exact matches
4. Cache frequent queries in memory
5. Monitor query patterns and optimize

### For Historical Snapshots

1. Start with current version only
2. Add historical snapshots if users request them
3. Focus on major game milestones (pre-renewal, renewal, episodes)
4. Consider on-demand generation rather than pre-creating all

## Open Questions

- [ ] **Chunking strategy:** 512 tokens? Page-level? Section-level?
- [ ] **Update strategy:** Re-vectorize everything or incremental?
- [ ] **Model selection:** Prioritize size, speed, or quality?
- [ ] **Metadata filters:** What filters do bots need most?
- [ ] **Cache layer:** Should we cache frequent queries?
- [ ] **Historical demand:** Do users want pre-renewal data?

## Next Steps

1. **Validate approach:** Get feedback on design
2. **Create vectorization script:** Start with 100 pages
3. **Test embedding quality:** Run sample queries
4. **Full vectorization:** Process all 10,516 pages
5. **Create release:** Upload vector DB to v2026-01-26
6. **Document integration:** Add to goKore design docs
7. **Implement in goKore:** Add to SharedResources
8. **Test end-to-end:** Bot queries working

## References

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence Transformers Models](https://www.sbert.net/docs/pretrained_models.html)
- [ChromaDB Go Client](https://github.com/amikos-tech/chroma-go)
- [Vector Database Comparison](https://github.com/erikbern/ann-benchmarks)
- [Semantic Search Best Practices](https://www.pinecone.io/learn/semantic-search/)

---

**Recommendation: Proceed with embedded vector DB approach. Start with v2026-01-26 release, add historical snapshots later if needed.**
