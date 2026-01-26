# iRO Wiki Vector Client

Python client library for semantic search on iRO Wiki vector databases.

## Installation

### From PyPI
```bash
pip install irowiki-vector-client
```

### With Qdrant support
```bash
pip install irowiki-vector-client[qdrant]
```

### With ChromaDB support
```bash
pip install irowiki-vector-client[chromadb]
```

### With all backends
```bash
pip install irowiki-vector-client[all]
```

### From wheel file
```bash
pip install irowiki_vector_client-1.0.0-py3-none-any.whl
```

## Quick Start

### Qdrant Client

```python
from irowiki_vector_client import QdrantClient

# Initialize client
client = QdrantClient("path/to/qdrant_storage")

# Search
results = client.search("best weapon for undead", limit=5)

for result in results:
    print(f"{result['page_title']}: {result['score']:.3f}")
    print(f"  {result['content'][:200]}...")
```

### ChromaDB Client

```python
from irowiki_vector_client import ChromaDBClient

# Initialize client
client = ChromaDBClient("path/to/chromadb_storage")

# Search with filters
results = client.search(
    "poison resistance",
    limit=5,
    filters={"namespace": 0}  # Main namespace only
)

for result in results:
    print(f"{result['page_title']}")
    print(f"  Distance: {result['distance']:.3f}")
```

### RAG Context Builder

```python
from irowiki_vector_client import QdrantClient, RAGContextBuilder

# Initialize
client = QdrantClient("path/to/qdrant_storage")
rag = RAGContextBuilder(client)

# Build context for LLM
context, sources = rag.build_context(
    query="How do I get to Glast Heim?",
    max_tokens=2000,
    top_k=20
)

# Build complete prompt
prompt = rag.build_rag_prompt(
    query="How do I get to Glast Heim?",
    context=context
)

# Send to your LLM
# response = openai.ChatCompletion.create(...)
```

## API Reference

### QdrantClient

```python
QdrantClient(db_path: str, collection_name: str = "irowiki")
```

**Methods:**
- `search(query: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict]`
- `get_collection_info() -> Dict[str, Any]`
- `get_metadata() -> Dict[str, Any]`

### ChromaDBClient

```python
ChromaDBClient(db_path: str, collection_name: str = "irowiki")
```

**Methods:**
- `search(query: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict]`
- `get_collection_info() -> Dict[str, Any]`
- `get_metadata() -> Dict[str, Any]`

### RAGContextBuilder

```python
RAGContextBuilder(client: BaseVectorClient)
```

**Methods:**
- `build_context(query: str, max_tokens: int = 2000, top_k: int = 20, filters: Optional[Dict] = None) -> tuple[str, List[Dict]]`
- `build_rag_prompt(query: str, context: str) -> str`
- `count_tokens(text: str) -> int` (static)

## Examples

See [examples/](https://github.com/lenaxia/iroWikiScraper/tree/main/examples) for more usage examples.

## License

MIT
