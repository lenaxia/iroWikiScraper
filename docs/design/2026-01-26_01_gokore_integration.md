# Integration with goKore Bot Manager

**Date**: 2026-01-26
**Author**: AI Assistant
**Status**: Approved

## Overview

Design document for integrating the iRO Wiki database into the goKore bot manager as a shared knowledge resource, enabling bot instances to query game lore, item information, quest details, and other wiki content.

## Goals

- **Enable bot intelligence**: Bots can look up item stats, quest information, monster data, and game lore
- **Shared resource pattern**: Follow existing SharedResources architecture
- **Minimal overhead**: Keep deployment simple and performant
- **Easy updates**: Support monthly wiki database updates
- **Future-proof**: Design allows migration to microservice if needed

## Non-Goals

- Real-time wiki updates (monthly updates are sufficient)
- Image serving (metadata only, images fetched from URLs)
- Wiki editing capabilities
- Search engine optimization

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    goKore Container                      │
│                                                          │
│  ┌──────────────┐                                       │
│  │ BotManager   │                                       │
│  └──────┬───────┘                                       │
│         │                                                │
│         │ shares                                         │
│         ▼                                                │
│  ┌──────────────────────────────────────┐              │
│  │      SharedResources                  │              │
│  │  ┌────────────────────────────────┐  │              │
│  │  │  WikiDB *sdk.Database          │  │              │
│  │  │  ├─ Pages (10,516)             │  │              │
│  │  │  ├─ Revisions (84,486)         │  │              │
│  │  │  └─ Files metadata             │  │              │
│  │  └────────────────────────────────┘  │              │
│  │  ┌────────────────────────────────┐  │              │
│  │  │  MapCache, MonsterCache, etc   │  │              │
│  │  └────────────────────────────────┘  │              │
│  └──────────────────────────────────────┘              │
│         ▲                 ▲                 ▲            │
│         │                 │                 │            │
│  ┌──────┴──┐       ┌─────┴─────┐    ┌─────┴────┐      │
│  │  Bot1   │       │   Bot2    │    │  Bot3    │      │
│  └─────────┘       └───────────┘    └──────────┘      │
│                                                          │
│  Data: /app/data/irowiki.db (159 MB compressed)        │
└─────────────────────────────────────────────────────────┘
```

### Integration Pattern

**Embedded Database Approach** (Recommended)

1. Include SQLite database in Docker image
2. Initialize in SharedResources
3. All bots share single DB connection pool
4. Queries are local (no network latency)
5. Updates via Docker image rebuild

### Code Integration Points

#### 1. SharedResources Extension

```go
// internal/bot/shared_resources.go

import "github.com/lenaxia/iRO-Wiki-Scraper/sdk"

type SharedResources struct {
    // Existing fields
    MapCache           *MapCache
    MonsterCache       *MonsterCache
    GlobalActorManager *actor.GlobalManager
    HookDispatcher     *hook.Dispatcher
    FieldManager       *field.Manager
    AsyncLLMClient     *llm.AsyncLLMClient
    
    // Wiki Knowledge Base
    WikiDB             *sdk.Database  // Direct SQLite access
}

func NewSharedResources(dispatcher ...*hook.Dispatcher) *SharedResources {
    // ... existing initialization ...
    
    // Initialize wiki database
    wikiDB, err := sdk.OpenDatabase("/app/data/irowiki.db")
    if err != nil {
        logger.WithError(err).Warn("Failed to load wiki database, lore queries disabled")
        wikiDB = nil  // Continue without wiki (graceful degradation)
    } else {
        logger.Info("Wiki database loaded successfully")
    }
    
    resources := &SharedResources{
        // ... existing fields ...
        WikiDB: wikiDB,
    }
    
    return resources
}

// Cleanup
func (r *SharedResources) Close() error {
    if r.WikiDB != nil {
        return r.WikiDB.Close()
    }
    return nil
}
```

#### 2. Bot Usage Example

```go
// internal/bot/bot_instance.go or bot behaviors

func (b *BotInstance) LookupItem(itemName string) (*wiki.Page, error) {
    if b.sharedResources.WikiDB == nil {
        return nil, fmt.Errorf("wiki database not available")
    }
    
    // Search for item page
    pages, err := b.sharedResources.WikiDB.SearchPages(itemName)
    if err != nil {
        return nil, err
    }
    
    if len(pages) == 0 {
        return nil, fmt.Errorf("item not found: %s", itemName)
    }
    
    return pages[0], nil
}

func (b *BotInstance) GetQuestInfo(questName string) (string, error) {
    if b.sharedResources.WikiDB == nil {
        return "", fmt.Errorf("wiki database not available")
    }
    
    // Get quest page with latest content
    pages, err := b.sharedResources.WikiDB.SearchPages(questName)
    if err != nil {
        return "", err
    }
    
    if len(pages) == 0 {
        return "", fmt.Errorf("quest not found: %s", questName)
    }
    
    // Get latest revision content
    revisions, err := b.sharedResources.WikiDB.GetRevisions(pages[0].PageID, 1)
    if err != nil {
        return "", err
    }
    
    return revisions[0].Content, nil
}
```

#### 3. Cognitive/AI Integration

```go
// internal/bot/cognitive/wiki_context.go

// WikiContextProvider provides wiki context to LLM
type WikiContextProvider struct {
    wikiDB *sdk.Database
}

func (p *WikiContextProvider) GetContext(query string) (string, error) {
    // Search wiki for relevant pages
    pages, err := p.wikiDB.SearchPages(query)
    if err != nil {
        return "", err
    }
    
    // Build context summary from top 3 results
    var context strings.Builder
    for i, page := range pages[:min(3, len(pages))] {
        revisions, _ := p.wikiDB.GetRevisions(page.PageID, 1)
        if len(revisions) > 0 {
            // Extract first 500 chars as summary
            summary := revisions[0].Content
            if len(summary) > 500 {
                summary = summary[:500] + "..."
            }
            context.WriteString(fmt.Sprintf("\n=== %s ===\n%s\n", page.Title, summary))
        }
    }
    
    return context.String(), nil
}
```

### Docker Integration

#### Dockerfile Changes

```dockerfile
# Stage 1: Build
FROM golang:1.21-alpine AS builder
# ... existing build steps ...

# Stage 2: Runtime
FROM alpine:3.19

# Install SQLite for wiki database
RUN apk add --no-cache ca-certificates tzdata sqlite

# Create data directory
WORKDIR /app
RUN mkdir -p /app/data /app/configs /app/plugins

# Copy binary
COPY --from=builder /app/bin/gokore /app/gokore

# Copy configs
COPY configs/ /app/configs/

# Copy wiki database (download from latest release)
# Option 1: Include in repo (add to .dockerignore for dev)
COPY data/irowiki.db /app/data/irowiki.db

# Option 2: Download during build (preferred)
# RUN wget https://github.com/lenaxia/iroWikiScraper/releases/download/v2026-01-26/irowiki-database-2026-01-26.tar.gz \
#     && tar -xzf irowiki-database-2026-01-26.tar.gz -C /app/data/ \
#     && rm irowiki-database-2026-01-26.tar.gz

# ... rest of Dockerfile ...
```

#### docker-compose.yml Changes

```yaml
services:
  gokore:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: gokore
    restart: unless-stopped
    volumes:
      - ./configs:/app/configs:ro
      - ./plugins:/app/plugins:ro
      - ./logs:/app/logs
      # Optional: Mount wiki DB for easy updates without rebuild
      - ./data/irowiki.db:/app/data/irowiki.db:ro
    # ... rest of config ...
```

### Database Statistics

Based on actual scrape (2026-01-26):

- **Pages**: 10,516
- **Revisions**: 84,486 with full content
- **Content Size**: 960.45 MB
- **Database Size**: 1.1 GB uncompressed, 159 MB compressed
- **Scrape Duration**: 3 hours 7 minutes
- **Update Frequency**: Monthly (incremental)

### Query Performance

SQLite read performance (approximate):
- **Page lookup**: < 1ms (indexed by title)
- **Revision history**: < 5ms (10-50 revisions)
- **Full-text search**: 10-50ms (FTS5 index)
- **Batch queries**: 100-500ms (100 pages)

No performance concerns for bot queries.

## Data Access Patterns

### Common Query Patterns

1. **Item Lookup**
   ```sql
   SELECT * FROM pages WHERE title = 'Poring Card' AND namespace = 0;
   ```

2. **Quest Information**
   ```sql
   SELECT r.content FROM pages p 
   JOIN revisions r ON p.page_id = r.page_id 
   WHERE p.title = 'Eden Group Quest' 
   ORDER BY r.timestamp DESC LIMIT 1;
   ```

3. **Map Information**
   ```sql
   SELECT * FROM pages WHERE title LIKE 'Prontera%' AND namespace = 0;
   ```

4. **Monster Data**
   ```sql
   SELECT r.content FROM pages p
   JOIN revisions r ON p.page_id = r.page_id
   WHERE p.title = 'Angeling'
   ORDER BY r.timestamp DESC LIMIT 1;
   ```

### SDK Usage Examples

```go
// Search by title
pages, _ := wikiDB.SearchPages("Poring")

// Get page by ID
page, _ := wikiDB.GetPage(213)  // Izlude

// Get revision history
revisions, _ := wikiDB.GetRevisions(213, 10)  // Last 10 revisions

// Get latest content
content, _ := wikiDB.GetLatestContent(213)

// Full-text search (if implemented)
results, _ := wikiDB.Search("healing items")
```

## Deployment Strategy

### Phase 1: Embedded Database (Current)

1. Download latest wiki release
2. Add to Docker image
3. Initialize in SharedResources
4. Bots query locally

**Pros**: Simple, fast, no infrastructure
**Cons**: Larger image, updates need rebuild

### Phase 2: Mounted Volume (Optional)

1. Keep database as mounted volume
2. Update volume without rebuild
3. Still local queries

**Pros**: Easy updates, faster deployments
**Cons**: Volume management

### Phase 3: Microservice (Future, if needed)

Only if you need:
- Multiple services using wiki data
- Independent scaling
- Different update schedules

```
┌──────────────┐         ┌──────────────┐
│   goKore     │────────▶│ wiki-service │
│  BotManager  │  HTTP   │   (gRPC)     │
└──────────────┘         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  irowiki.db  │
                         └──────────────┘
```

Would implement:
- gRPC API for queries
- Caching layer
- Rate limiting
- Monitoring

## Update Process

### Monthly Wiki Updates

```bash
# 1. Run incremental scrape
cd ~/personal/iRO-Wiki-Scraper
./scripts/local-scrape-and-release.sh --incremental --release

# 2. Download new database
cd ~/personal/goKore
wget https://github.com/lenaxia/iroWikiScraper/releases/download/v2026-02-26/irowiki-database-2026-02-26.tar.gz
tar -xzf irowiki-database-2026-02-26.tar.gz -C data/
rm irowiki-database-2026-02-26.tar.gz

# 3. Rebuild Docker image
docker-compose build

# 4. Restart services
docker-compose up -d
```

### Automated Update (Future)

```dockerfile
# Dockerfile with build arg for version
ARG WIKI_VERSION=v2026-01-26
RUN wget https://github.com/lenaxia/iroWikiScraper/releases/download/${WIKI_VERSION}/irowiki-database-*.tar.gz
```

## Alternatives Considered

### 1. Microservice Architecture

**Rejected for initial implementation**

Reasons:
- Over-engineering for single-service use case
- Adds network latency and complexity
- Requires API layer, service discovery, etc.
- Can be added later if needed

Keep as future option if:
- Multiple services need wiki data
- Need independent scaling
- Want dynamic wiki updates

### 2. In-Memory Database

**Rejected**

Reasons:
- 1.1 GB is too large for memory
- SQLite already caches hot data
- No performance benefit
- Higher resource usage

### 3. Remote Database (PostgreSQL/MySQL)

**Rejected**

Reasons:
- SQLite is read-only, perfect for this use case
- No need for concurrent writes
- Simpler deployment
- Better performance for single-reader scenarios

## Implementation Checklist

- [ ] Add iRO-Wiki-Scraper SDK as Go module dependency
- [ ] Extend SharedResources with WikiDB field
- [ ] Update Dockerfile to include SQLite and database
- [ ] Add WikiDB initialization in NewSharedResources
- [ ] Add graceful degradation if DB missing
- [ ] Implement bot helper methods (LookupItem, GetQuestInfo, etc.)
- [ ] Add cognitive/LLM context provider using wiki
- [ ] Update docker-compose.yml
- [ ] Document usage in goKore README
- [ ] Create monthly update process documentation
- [ ] Add health check for wiki DB availability

## Open Questions

- [ ] Should we extract specific game data (items, monsters) into optimized caches?
- [ ] Do we need a query abstraction layer for future service migration?
- [ ] Should we implement request caching for frequent queries?
- [ ] What's the strategy for handling corrupted or missing wiki data?

## Performance Considerations

### Resource Usage

- **Memory**: SQLite uses ~10-50 MB memory for caching
- **Disk I/O**: Read-only, low I/O (OS caches hot pages)
- **CPU**: Negligible (indexed queries are fast)
- **Startup**: +100-200ms to open database

### Optimization Opportunities

1. **Prepared statements**: Cache common queries
2. **Connection pooling**: SQLite supports read-only connections
3. **Selective loading**: Only load relevant namespaces
4. **Summary tables**: Pre-compute common aggregations

Not needed initially - SQLite is already fast enough.

## Testing Strategy

### Unit Tests

```go
func TestWikiDBIntegration(t *testing.T) {
    resources := NewSharedResources()
    defer resources.Close()
    
    if resources.WikiDB == nil {
        t.Skip("Wiki database not available")
    }
    
    // Test page lookup
    pages, err := resources.WikiDB.SearchPages("Poring")
    assert.NoError(t, err)
    assert.NotEmpty(t, pages)
    
    // Test revision retrieval
    revisions, err := resources.WikiDB.GetRevisions(pages[0].PageID, 1)
    assert.NoError(t, err)
    assert.NotEmpty(t, revisions[0].Content)
}
```

### Integration Tests

```go
func TestBotWikiQuery(t *testing.T) {
    manager := setupTestBotManager()
    bot, _ := manager.CreateBot("test", testConfig)
    
    // Test item lookup
    item, err := bot.LookupItem("Poring Card")
    assert.NoError(t, err)
    assert.Equal(t, "Poring Card", item.Title)
}
```

## Security Considerations

- **Read-only access**: Database opened in read-only mode
- **SQL injection**: SDK uses parameterized queries
- **Resource limits**: SQLite has built-in memory limits
- **File permissions**: Database file readable only by container

No security concerns for read-only local database.

## Monitoring & Observability

### Metrics to Track

```go
// Potential metrics (if monitoring added)
type WikiMetrics struct {
    QueriesTotal     int64
    QueryLatencyP50  time.Duration
    QueryLatencyP99  time.Duration
    CacheHitRate     float64
    ErrorRate        float64
}
```

### Logging

```go
logger.WithFields(log.Fields{
    "query": "item_lookup",
    "term": itemName,
    "duration_ms": duration.Milliseconds(),
    "results": len(pages),
}).Debug("Wiki query executed")
```

## References

- [iRO Wiki Scraper Repository](https://github.com/lenaxia/iroWikiScraper)
- [Go SDK Documentation](https://github.com/lenaxia/iroWikiScraper/tree/main/sdk)
- [SQLite Read-Only Mode](https://www.sqlite.org/uri.html#uriimmutable)
- [goKore SharedResources Pattern](https://github.com/lenaxia/goKore/blob/main/internal/bot/shared_resources.go)

## Revision History

- **2026-01-26**: Initial design - embedded database approach approved
