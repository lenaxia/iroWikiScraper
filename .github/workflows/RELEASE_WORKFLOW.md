# Release Automation Workflow

## Overview

The `release-vector.yml` workflow automatically generates vector databases and client libraries when a new release is published, then uploads them to the release.

## Workflow Diagram

```text
GitHub Release Published
    ↓
┌─────────────────────────────────────────┐
│  Generate Vector Databases (6 hours)   │
│  - Download latest SQLite database      │
│  - Generate Qdrant (MiniLM)            │
│  - Generate ChromaDB (MiniLM)          │
│  - Package and checksum                 │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Build Python Client                    │
│  - Build wheel package                  │
│  - Test installation                    │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Build Go Client                        │
│  - Build library                        │
│  - Run tests                            │
│  - Package with vendor deps             │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Upload to Release                      │
│  - Vector databases                     │
│  - Python wheel                         │
│  - Go package                           │
│  - Checksums                            │
│  - Update release notes                 │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Publish Python Package (Optional)      │
│  - Upload to PyPI                       │
└─────────────────────────────────────────┘
```

## Triggers

### Automatic (Release Published)

```yaml
on:
  release:
    types: [published]
```

When you publish a release on GitHub, the workflow runs automatically.

### Manual (Workflow Dispatch)

```yaml
on:
  workflow_dispatch:
    inputs:
      release_tag:
        description: 'Release tag to attach artifacts to'
        required: true
        type: string
```

Manually trigger from Actions tab with a specific release tag.

## Jobs

### 1. `generate-vector-databases`

**Duration:** ~6 hours  
**Runner:** `ubuntu-latest`

**Steps:**

1. Download latest SQLite database from artifacts
2. Generate Qdrant database with MiniLM embeddings
3. Generate ChromaDB database with MiniLM embeddings
4. (Optional) Generate additional configurations (BGE model, page-level chunking)
5. Package databases as `.tar.gz`
6. Generate SHA256 checksums

**Outputs:**

- `irowiki-qdrant-minilm-section-{tag}.tar.gz` (~500 MB)
- `irowiki-chromadb-minilm-section-{tag}.tar.gz` (~250 MB)
- `checksums.txt`

### 2. `build-python-client`

**Duration:** ~5 minutes  
**Runner:** `ubuntu-latest`

**Steps:**

1. Build Python package using `python -m build`
2. Create wheel (`.whl`) and source distribution (`.tar.gz`)
3. Upload artifacts

**Outputs:**

- `irowiki_vector_client-1.0.0-py3-none-any.whl`
- `irowiki_vector_client-1.0.0.tar.gz`

### 3. `build-go-client`

**Duration:** ~3 minutes  
**Runner:** `ubuntu-latest`

**Steps:**

1. Build Go library
2. Run tests
3. Vendor dependencies
4. Create archive

**Outputs:**

- `irowiki-go-vector-client-{tag}.tar.gz`

### 4. `upload-to-release`

**Duration:** ~2 minutes  
**Runner:** `ubuntu-latest`

**Steps:**

1. Download all artifacts from previous jobs
2. Upload to GitHub release
3. Generate and append release notes

**Artifacts Uploaded:**

- All vector databases
- Python wheel
- Go package
- Checksums

### 5. `publish-python-package` (Optional)

**Duration:** ~1 minute  
**Runner:** `ubuntu-latest`  
**Condition:** Only on release publish (not manual trigger)

**Steps:**

1. Download Python package
2. Publish to PyPI using API token

**Requirements:**
- `PYPI_API_TOKEN` secret configured

## Configuration

### Required Secrets

#### For PyPI Publishing (Optional)
```
PYPI_API_TOKEN
```

Get from: https://pypi.org/manage/account/token/

Add to: Repository Settings → Secrets → Actions

### Environment Variables

```yaml
PYTHON_VERSION: '3.11'
GO_VERSION: '1.22'
```

Adjust versions as needed in the workflow file.

## Usage

### Automatic Release
1. Create a new release on GitHub
2. Workflow runs automatically
3. Wait ~6 hours for completion
4. Artifacts appear in the release

### Manual Trigger
1. Go to Actions tab
2. Select "Release with Vector Databases" workflow
3. Click "Run workflow"
4. Enter release tag (e.g., `v2026-01-26`)
5. Click "Run workflow"

## Generated Release Assets

After workflow completion, the release will contain:

```
Release: v2026-01-26
├── irowiki-database-2026-01-26.tar.gz           (SQLite, from previous scrape)
├── irowiki-qdrant-minilm-section-v2026-01-26.tar.gz     (~500 MB)
├── irowiki-chromadb-minilm-section-v2026-01-26.tar.gz   (~250 MB)
├── irowiki_vector_client-1.0.0-py3-none-any.whl
├── irowiki_vector_client-1.0.0.tar.gz
├── irowiki-go-vector-client-v2026-01-26.tar.gz
└── checksums.txt
```

## Release Notes Format

The workflow automatically appends to release notes:

```markdown
## Vector Databases

Pre-vectorized databases for semantic search and RAG:

### Qdrant (Recommended for Production)
- `irowiki-qdrant-minilm-section-*.tar.gz` - Section-level chunking with MiniLM embeddings

### ChromaDB (Development-Friendly)
- `irowiki-chromadb-minilm-section-*.tar.gz` - Section-level chunking with MiniLM embeddings

## Client Libraries

### Python
- `irowiki_vector_client-*.whl` - Install with: `pip install irowiki_vector_client-*.whl`

### Go
- `irowiki-go-vector-client-*.tar.gz` - Extract and use as Go module

## Quick Start

[Usage examples...]
```

## Monitoring

### View Progress
1. Go to Actions tab
2. Click on the running workflow
3. Expand jobs to see real-time logs

### Check Artifacts
During the run, artifacts are available in the workflow summary:
- `vector-databases` (available for 7 days)
- `python-vector-client` (available for 7 days)
- `go-vector-client` (available for 7 days)

### Notifications
The workflow sends a completion notification at the end (can be extended to Slack/email).

## Troubleshooting

### Workflow Fails at Vectorization
**Cause:** Database not found or vectorization error

**Solution:**
1. Check if previous scrape workflow completed
2. Verify database artifact exists
3. Check vectorization logs for specific errors

### Workflow Fails at PyPI Publish
**Cause:** Missing or invalid `PYPI_API_TOKEN`

**Solution:**
1. Verify secret is configured
2. Check token hasn't expired
3. Ensure package version doesn't already exist on PyPI

### Timeout After 6 Hours
**Cause:** Vectorization taking too long

**Solution:**
1. Increase `timeout-minutes` in workflow
2. Consider generating fewer vector databases
3. Use workflow_dispatch for manual retry

### Artifact Upload Fails
**Cause:** File too large or network issue

**Solution:**
1. Check artifact sizes
2. Verify GitHub storage limits
3. Retry the job

## Customization

### Add More Vector Databases

Edit `.github/workflows/release-vector.yml`:

```yaml
- name: Generate BGE model database
  run: |
    python scripts/vectorize-wiki.py \
      --db data/irowiki.db \
      --output vector_qdrant_bge_section \
      --vector-db qdrant \
      --model BAAI/bge-large-en-v1.5 \
      --chunk-level section \
      --batch-size 16
```

### Change Embedding Model

Modify the `--model` parameter:
```bash
--model all-MiniLM-L6-v2           # Default (fast, good)
--model BAAI/bge-large-en-v1.5     # Better quality
--model text-embedding-3-small     # OpenAI (requires API key)
```

### Change Chunking Strategy

Modify the `--chunk-level` parameter:
```bash
--chunk-level section    # Default (balanced)
--chunk-level page       # Coarser (fewer chunks)
--chunk-level paragraph  # Finer (more chunks)
```

## Performance Optimization

### Parallel Generation
Currently runs sequentially. To parallelize:

```yaml
strategy:
  matrix:
    config:
      - {db: qdrant, model: all-MiniLM-L6-v2}
      - {db: chromadb, model: all-MiniLM-L6-v2}
```

### Use GPU
Add GPU runner (self-hosted):

```yaml
runs-on: [self-hosted, gpu]
```

Then modify vectorization to use GPU:
```python
--device cuda
```

### Caching
Add model caching:

```yaml
- name: Cache models
  uses: actions/cache@v3
  with:
    path: ~/.cache/huggingface
    key: ${{ runner.os }}-models-${{ hashFiles('requirements-vector.txt') }}
```

## Cost Considerations

### GitHub Actions Minutes
- Free tier: 2,000 minutes/month (public repos: unlimited)
- Vector generation: ~360 minutes per release
- Estimate: ~5-6 releases per month on free tier

### Storage
- Free tier: 500 MB (public repos: unlimited)
- Vector databases: ~750 MB per release
- Consider cleaning up old artifacts

### PyPI Storage
- Unlimited for open source projects
- Package size: ~2 MB (Python wheel)

## Related Workflows

- `scrape.yml` - Runs monthly to scrape wiki and generate SQLite database
- `test.yml` - Runs on PRs to test code changes
- This workflow depends on artifacts from `scrape.yml`

## Best Practices

1. **Release Cadence:** Monthly releases aligned with scrape schedule
2. **Versioning:** Use date-based tags (e.g., `v2026-01-26`)
3. **Testing:** Test vector databases locally before release
4. **Documentation:** Update release notes with known issues
5. **Cleanup:** Delete old draft releases and artifacts

## Future Enhancements

- [ ] Automated quality checks on generated vectors
- [ ] Multi-model comparison reports
- [ ] Docker images with embedded vector DBs
- [ ] Automated benchmarking
- [ ] Incremental vectorization (only changed pages)

## Support

For issues with the workflow:
1. Check workflow logs
2. Review this documentation
3. Open an issue: https://github.com/lenaxia/iroWikiScraper/issues
