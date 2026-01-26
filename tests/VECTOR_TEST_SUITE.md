# Vector Database Test Suite

## Overview

Comprehensive test suite for the iRO Wiki vector database implementation, covering unit tests, integration tests, and error handling.

## Test Structure

```
tests/
├── unit/vector/
│   ├── conftest.py                  # Test fixtures and utilities
│   ├── test_chunker.py              # WikiChunker tests (400+ lines)
│   ├── test_database_reader.py      # DatabaseReader tests (350+ lines)
│   ├── test_vector_writers.py       # VectorDBWriter tests (400+ lines)
│   └── test_error_handling.py       # Error/edge case tests (400+ lines)
└── integration/
    └── test_vectorization_pipeline.py  # End-to-end tests (500+ lines)
```

**Total:** ~2,000+ lines of test code

## Test Coverage

### Unit Tests (tests/unit/vector/)

#### test_chunker.py - WikiChunker Tests
- **WikiText Cleaning** (11 tests)
  - ✅ Clean simple text
  - ✅ Remove internal/external links
  - ✅ Remove templates and formatting
  - ✅ Remove images
  - ✅ Handle empty/None values
  - ✅ Normalize whitespace
  - ✅ Complex page with mixed markup

- **Word Counting** (4 tests)
  - ✅ Count words accurately
  - ✅ Handle empty strings
  - ✅ Ignore extra whitespace

- **Page-Level Chunking** (3 tests)
  - ✅ Chunk simple pages
  - ✅ Filter short content
  - ✅ Clean markup during chunking

- **Section-Level Chunking** (7 tests)
  - ✅ Split by MediaWiki headings
  - ✅ Identify section levels (==, ===, etc.)
  - ✅ Filter short sections
  - ✅ Include headings in content
  - ✅ Sequential chunk indices
  - ✅ Handle intro sections

- **Paragraph-Level Chunking** (4 tests)
  - ✅ Split by paragraphs
  - ✅ Filter short paragraphs
  - ✅ Split very long paragraphs
  - ✅ Track parent sections

- **Chunk Object** (3 tests)
  - ✅ Serialize to dict
  - ✅ Generate unique IDs (page/section/paragraph)

- **Edge Cases** (3 tests)
  - ✅ Empty content
  - ✅ Only markup (no real content)
  - ✅ Malformed section headers

**Total: 35 tests**

#### test_database_reader.py - DatabaseReader Tests
- **Basic Operations** (8 tests)
  - ✅ Count pages in namespaces
  - ✅ Iterate pages
  - ✅ Exclude redirects
  - ✅ Exclude empty content
  - ✅ Retrieve content correctly
  - ✅ Include metadata
  - ✅ Order by page ID
  - ✅ Filter by namespace

- **Context Manager** (1 test)
  - ✅ Proper connection lifecycle

- **Edge Cases** (8 tests)
  - ✅ Non-existent database
  - ✅ Empty database
  - ✅ No data in tables
  - ✅ Invalid namespace
  - ✅ Empty namespace list
  - ✅ Duplicate namespaces
  - ✅ Negative namespaces

- **Performance** (3 tests)
  - ✅ Lazy loading (generator)
  - ✅ Multiple iterations
  - ✅ Memory efficiency

- **Data Integrity** (4 tests)
  - ✅ Page-revision relationships
  - ✅ Content encoding
  - ✅ Metadata structure
  - ✅ Special characters in titles

**Total: 24 tests**

#### test_vector_writers.py - VectorDBWriter Tests
- **QdrantWriter** (7 tests)
  - ✅ Initialize collection
  - ✅ Add chunks with embeddings
  - ✅ Preserve metadata
  - ✅ Finalize collection
  - ✅ Save metadata file
  - ✅ Custom collection name
  - ✅ Search after write (integration)

- **ChromaDBWriter** (7 tests)
  - ✅ Initialize collection
  - ✅ Add chunks with embeddings
  - ✅ Preserve metadata
  - ✅ Finalize collection
  - ✅ Save metadata file
  - ✅ Custom collection name
  - ✅ Recreate collection
  - ✅ Query after write (integration)

- **Edge Cases** (6 tests)
  - ✅ Empty chunks
  - ✅ Mismatched dimensions
  - ✅ Mismatched count
  - ✅ Invalid dimensions
  - ✅ Duplicate collections
  - ✅ Invalid metadata types

**Total: 20 tests**

#### test_error_handling.py - Error Handling Tests
- **Malformed Inputs** (5 tests)
  - ✅ None content
  - ✅ Missing content key
  - ✅ Binary data
  - ✅ Very large content (1MB+)
  - ✅ Unicode characters (emoji, CJK, etc.)

- **Database Errors** (3 tests)
  - ✅ Corrupted database
  - ✅ Missing columns
  - ✅ Lost connection

- **Vector DB Errors** (3 tests)
  - ✅ Invalid dimensions
  - ✅ Duplicate collections
  - ✅ Invalid metadata types

- **Resource Exhaustion** (2 tests)
  - ✅ Memory-efficient iteration
  - ✅ Large batch processing

- **Edge Case Content** (3 tests)
  - ✅ Only whitespace
  - ✅ Infinite loop protection
  - ✅ Deeply nested sections

- **Concurrent Access** (1 test)
  - ✅ Multiple readers

- **Input Validation** (3 tests)
  - ✅ Invalid page IDs
  - ✅ Empty titles
  - ✅ Special characters in titles

**Total: 20 tests**

### Integration Tests (tests/integration/)

#### test_vectorization_pipeline.py - End-to-End Tests
- **Full Pipeline** (2 tests)
  - ✅ SQLite → Chunks → Qdrant
  - ✅ SQLite → Chunks → ChromaDB

- **Batch Processing** (1 test)
  - ✅ Process in configurable batches

- **Metadata Generation** (1 test)
  - ✅ Generate complete metadata with stats

- **Chunking Strategies** (2 tests)
  - ✅ Page-level end-to-end
  - ✅ Paragraph-level end-to-end

- **Error Handling** (2 tests)
  - ✅ Handle corrupt page data
  - ✅ Handle empty database

- **Performance Metrics** (1 test)
  - ✅ Track processing stats (pages/sec, chunks/sec)

- **Namespace Filtering** (2 tests)
  - ✅ Single namespace pipeline
  - ✅ Multiple namespaces pipeline

**Total: 11 tests**

## Summary

### Test Count by Category
- **Unit Tests:** 99 tests
  - Chunker: 35 tests
  - Database Reader: 24 tests
  - Vector Writers: 20 tests
  - Error Handling: 20 tests

- **Integration Tests:** 11 tests

**Grand Total: 110 tests**

### Coverage Areas

#### Happy Paths ✅
- Basic functionality of all components
- Standard workflows
- Expected inputs and outputs
- Integration between components

#### Unhappy Paths ✅
- Invalid inputs (None, empty, malformed)
- Database errors (corrupted, missing data)
- Resource constraints (memory, large files)
- Edge cases (unicode, special chars, deep nesting)
- Error recovery

#### Performance ✅
- Memory efficiency (generators/iterators)
- Batch processing
- Large content handling
- Concurrent access

#### Data Integrity ✅
- Content preservation
- Metadata accuracy
- Encoding/decoding
- Unicode support

## Running Tests

### All Tests
```bash
pytest tests/
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Integration Tests Only
```bash
pytest tests/integration/ -m integration
```

### Specific Test File
```bash
pytest tests/unit/vector/test_chunker.py -v
```

### Specific Test Class
```bash
pytest tests/unit/vector/test_chunker.py::TestWikiTextCleaning -v
```

### Specific Test
```bash
pytest tests/unit/vector/test_chunker.py::TestWikiTextCleaning::test_clean_simple_text -v
```

### Skip Slow Tests
```bash
pytest tests/ -m "not slow"
```

### Run Tests Requiring Vector Dependencies
```bash
pytest tests/ -m requires_vector_deps
```

### With Coverage
```bash
pytest tests/ --cov=scripts --cov=examples --cov-report=html
```

### Parallel Execution
```bash
pytest tests/ -n auto  # Requires pytest-xdist
```

## Test Fixtures

### conftest.py
- **sample_wiki_content**: Various WikiText markup examples
- **test_database**: SQLite database with sample pages
- **mock_embedding_model**: Mock SentenceTransformer model
- **temp_vector_storage**: Temporary directory for vector DBs
- **sample_chunks**: Pre-created Chunk objects
- **sample_embeddings**: Sample embedding vectors

## Test Requirements

### Base Requirements
```
pytest>=7.4.0
pytest-cov>=4.1.0  # For coverage
```

### Vector Database Requirements
```
sentence-transformers>=2.2.0
qdrant-client>=1.7.0  # Python 3.11+ only
chromadb>=0.4.0
numpy>=1.24.0
```

### Optional Requirements
```
pytest-xdist  # For parallel execution
pytest-timeout  # For timeout control
pytest-mock  # For advanced mocking
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Test Vector Database

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-vector.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: pytest tests/ --cov --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Maintenance

### Adding New Tests
1. Add test to appropriate file
2. Use existing fixtures where possible
3. Mark with appropriate pytest markers
4. Update this document

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*` (descriptive name)
- Test methods: `test_*` (action + expected result)

### Examples
```python
# Good test names
def test_chunk_page_filters_short_content():
def test_database_reader_excludes_redirects():
def test_qdrant_writer_preserves_metadata():

# Bad test names
def test_1():
def test_chunk():
def test_works():
```

## Known Limitations

1. **Qdrant tests require Python 3.11+** - Skipped on earlier versions
2. **Mock embedding model** - Uses random vectors, not real embeddings
3. **Small test database** - Only 6 pages, may not catch scale issues
4. **No GPU tests** - All tests run on CPU

## Future Test Additions

- [ ] Performance benchmarks
- [ ] Stress tests with large datasets
- [ ] Real embedding model tests
- [ ] GPU acceleration tests
- [ ] Hybrid search tests
- [ ] Incremental update tests
- [ ] Multi-language content tests
- [ ] Memory profiling tests

## Success Metrics

✅ **110 comprehensive tests** covering:
- ✅ All major code paths
- ✅ Happy and unhappy paths
- ✅ Edge cases and error conditions
- ✅ Integration scenarios
- ✅ Performance characteristics
- ✅ Data integrity

**Status:** Production-ready test suite
