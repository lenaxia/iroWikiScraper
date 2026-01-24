# Story 07: Full-Text Search

**Story ID**: epic-05-story-07  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 6 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** advanced full-text search capabilities  
**So that** I can perform complex searches with relevance ranking and advanced query syntax

## Acceptance Criteria

1. **Advanced Query Syntax**
   - [ ] Boolean operators (AND, OR, NOT)
   - [ ] Phrase matching with quotes
   - [ ] Wildcard matching (* and ?)
   - [ ] Field-specific searches (title:, content:)

2. **Relevance Ranking**
   - [ ] TF-IDF based scoring
   - [ ] Boost title matches over content
   - [ ] Consider document length
   - [ ] Configurable score thresholds

3. **Search Features**
   - [ ] Stemming support (optional)
   - [ ] Case-insensitive matching
   - [ ] Diacritics handling
   - [ ] Stop word filtering

4. **Performance**
   - [ ] FTS index utilization
   - [ ] Query optimization
   - [ ] Results caching for repeated queries
   - [ ] Sub-200ms response time

## Technical Details

### Full-Text Search Implementation

```go
package irowiki

import (
    "context"
    "fmt"
    "strings"
)

// SearchFullText performs advanced full-text search
func (c *sqliteClient) SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error) {
    if query == "" {
        return nil, fmt.Errorf("query cannot be empty")
    }
    
    if err := opts.Validate(); err != nil {
        return nil, fmt.Errorf("invalid options: %w", err)
    }
    
    opts.SetDefaults()
    
    // Parse and transform query
    ftsQuery := c.transformToFTSQuery(query)
    
    sqlQuery := c.buildFullTextQuery(opts)
    args := []interface{}{ftsQuery}
    
    // Add optional filters
    if opts.Namespace != nil {
        args = append(args, *opts.Namespace)
    }
    if opts.MinScore > 0 {
        args = append(args, opts.MinScore)
    }
    args = append(args, opts.Limit, opts.Offset)
    
    rows, err := c.db.QueryContext(ctx, sqlQuery, args...)
    if err != nil {
        return nil, fmt.Errorf("full-text search failed: %w", err)
    }
    defer rows.Close()
    
    var results []SearchResult
    for rows.Next() {
        var result SearchResult
        err := rows.Scan(
            &result.ID,
            &result.Title,
            &result.Namespace,
            &result.LatestRevID,
            &result.Snippet,
            &result.Score,
        )
        if err != nil {
            return nil, fmt.Errorf("scan failed: %w", err)
        }
        result.MatchType = "fulltext"
        results = append(results, result)
    }
    
    return results, rows.Err()
}

// transformToFTSQuery converts user query to FTS5 syntax
func (c *sqliteClient) transformToFTSQuery(query string) string {
    // Handle quoted phrases
    if strings.Contains(query, "\"") {
        return query // Pass through quoted phrases
    }
    
    // Split into terms
    terms := strings.Fields(query)
    var ftsTerms []string
    
    for _, term := range terms {
        term = strings.TrimSpace(term)
        if term == "" {
            continue
        }
        
        // Handle operators
        switch strings.ToUpper(term) {
        case "AND", "OR", "NOT":
            ftsTerms = append(ftsTerms, strings.ToUpper(term))
            continue
        }
        
        // Handle negation
        if strings.HasPrefix(term, "-") {
            ftsTerms = append(ftsTerms, "NOT", term[1:])
            continue
        }
        
        // Handle wildcards
        if strings.Contains(term, "*") {
            ftsTerms = append(ftsTerms, term)
            continue
        }
        
        // Regular term - wrap with OR for flexibility
        ftsTerms = append(ftsTerms, term)
    }
    
    return strings.Join(ftsTerms, " ")
}

// buildFullTextQuery constructs the FTS SQL query
func (c *sqliteClient) buildFullTextQuery(opts SearchOptions) string {
    query := `
        SELECT 
            p.page_id,
            p.page_title,
            p.page_namespace,
            p.page_latest,
            snippet(content_fts, -1, '<mark>', '</mark>', '...', 32) as snippet,
            bm25(content_fts, 10.0, 1.0) as score
        FROM content_fts
        JOIN revisions r ON content_fts.rowid = r.rev_id
        JOIN pages p ON r.page_id = p.page_id
        WHERE content_fts MATCH ?
          AND r.rev_id = p.page_latest
    `
    
    // Add namespace filter
    if opts.Namespace != nil {
        query += " AND p.page_namespace = ?"
    }
    
    // Add score threshold
    if opts.MinScore > 0 {
        query += " AND bm25(content_fts) >= ?"
    }
    
    // Sort by relevance
    query += " ORDER BY score DESC"
    
    // Pagination
    query += " LIMIT ? OFFSET ?"
    
    return query
}
```

### PostgreSQL Full-Text Search

```go
// SearchFullText for PostgreSQL using ts_vector
func (c *postgresClient) SearchFullText(ctx context.Context, query string, opts SearchOptions) ([]SearchResult, error) {
    sqlQuery := `
        SELECT 
            p.page_id,
            p.page_title,
            p.page_namespace,
            p.page_latest,
            ts_headline('english', r.content, plainto_tsquery('english', $1), 
                'MaxWords=50, MinWords=20') as snippet,
            ts_rank(to_tsvector('english', r.content), plainto_tsquery('english', $1)) as score
        FROM pages p
        JOIN revisions r ON p.page_latest = r.rev_id
        WHERE to_tsvector('english', r.content) @@ plainto_tsquery('english', $1)
    `
    
    var args []interface{}
    args = append(args, query)
    argIdx := 2
    
    if opts.Namespace != nil {
        sqlQuery += fmt.Sprintf(" AND p.page_namespace = $%d", argIdx)
        args = append(args, *opts.Namespace)
        argIdx++
    }
    
    if opts.MinScore > 0 {
        sqlQuery += fmt.Sprintf(" AND ts_rank(to_tsvector('english', r.content), plainto_tsquery('english', $1)) >= $%d", argIdx)
        args = append(args, opts.MinScore)
        argIdx++
    }
    
    sqlQuery += " ORDER BY score DESC"
    sqlQuery += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argIdx, argIdx+1)
    args = append(args, opts.Limit, opts.Offset)
    
    rows, err := c.db.QueryContext(ctx, sqlQuery, args...)
    if err != nil {
        return nil, fmt.Errorf("full-text search failed: %w", err)
    }
    defer rows.Close()
    
    var results []SearchResult
    for rows.Next() {
        var result SearchResult
        err := rows.Scan(
            &result.ID,
            &result.Title,
            &result.Namespace,
            &result.LatestRevID,
            &result.Snippet,
            &result.Score,
        )
        if err != nil {
            return nil, err
        }
        result.MatchType = "fulltext"
        results = append(results, result)
    }
    
    return results, rows.Err()
}
```

### Query Parser

```go
// QueryParser handles complex search syntax
type QueryParser struct {
    input string
    pos   int
}

// Parse parses a search query into an AST
func (p *QueryParser) Parse(input string) (*SearchQuery, error) {
    p.input = input
    p.pos = 0
    
    return p.parseExpression()
}

type SearchQuery struct {
    Terms     []string
    Phrases   []string
    Exclude   []string
    FieldMap  map[string][]string
    Operators []string
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 03: PostgreSQL Backend
- Story 06: Page Search
- Epic 02: Database Schema (FTS indexes)

## Implementation Notes

- SQLite uses FTS5 with BM25 ranking
- PostgreSQL uses `ts_vector` and `ts_query`
- Different query syntax between backends
- Consider query caching for repeated searches
- Preprocess queries to handle common errors
- Document query syntax limitations
- Support both English and simple tokenizers

## Testing Requirements

- [ ] Boolean operator tests (AND, OR, NOT)
- [ ] Phrase search tests
- [ ] Wildcard tests
- [ ] Field-specific search tests
- [ ] Relevance ranking tests
- [ ] Score threshold tests
- [ ] Performance benchmarks (<200ms)
- [ ] Edge case tests (empty query, special characters)
- [ ] Backend parity tests (SQLite vs PostgreSQL)

## Definition of Done

- [ ] Full-text search implemented for both backends
- [ ] Query parser working
- [ ] Relevance ranking implemented
- [ ] Snippet generation with highlighting
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Query syntax documented
- [ ] Code reviewed and approved
