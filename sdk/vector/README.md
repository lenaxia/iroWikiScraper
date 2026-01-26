# iRO Wiki Vector Client (Go)

Go client library for semantic search on iRO Wiki vector databases.

## Installation

```bash
go get github.com/lenaxia/iroWikiScraper/sdk/vector
```

## Quick Start

```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/lenaxia/iroWikiScraper/sdk/vector"
)

func main() {
	// Create embedder (you need to provide your own implementation)
	embedder := &MyEmbedder{}  // Implement vector.Embedder interface

	// Initialize client
	client, err := vector.NewQdrantClient(
		"path/to/qdrant_storage",
		"irowiki",
		embedder,
	)
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	// Search
	results, err := client.Search(context.Background(), "best weapon for undead", 5)
	if err != nil {
		log.Fatal(err)
	}

	// Display results
	for _, result := range results {
		fmt.Printf("%s: %.3f\n", result.PageTitle, result.Score)
		fmt.Printf("  %s...\n", result.Content[:200])
	}
}
```

## Implementing an Embedder

You need to provide your own embedding implementation:

```go
type MyEmbedder struct {
	// Your embedding model
}

func (e *MyEmbedder) Embed(text string) ([]float32, error) {
	// Call your embedding API or model
	// Return embedding vector
	return embeddings, nil
}
```

### Using OpenAI

```go
import "github.com/sashabaranov/go-openai"

type OpenAIEmbedder struct {
	client *openai.Client
}

func NewOpenAIEmbedder(apiKey string) *OpenAIEmbedder {
	return &OpenAIEmbedder{
		client: openai.NewClient(apiKey),
	}
}

func (e *OpenAIEmbedder) Embed(text string) ([]float32, error) {
	resp, err := e.client.CreateEmbeddings(
		context.Background(),
		openai.EmbeddingRequest{
			Input: []string{text},
			Model: openai.AdaEmbeddingV2,
		},
	)
	if err != nil {
		return nil, err
	}

	return resp.Data[0].Embedding, nil
}
```

## API Reference

### Types

```go
type SearchResult struct {
	PageTitle    string
	SectionTitle *string
	Content      string
	Score        float32
	ChunkType    string
	Namespace    int
	PageID       int
}

type Metadata struct {
	GeneratedAt   string
	Model         string
	EmbeddingDim  int
	ChunkLevel    string
	TotalPages    int
	TotalChunks   int
	ChunksPerPage float64
}
```

### VectorClient Interface

```go
type VectorClient interface {
	Search(ctx context.Context, query string, limit int) ([]SearchResult, error)
	SearchWithFilters(ctx context.Context, query string, limit int, filters map[string]interface{}) ([]SearchResult, error)
	GetMetadata() (*Metadata, error)
	Close() error
}
```

### QdrantClient

```go
func NewQdrantClient(dbPath string, collectionName string, embedder Embedder) (*QdrantClient, error)
```

**Methods:**
- `Search(ctx context.Context, query string, limit int) ([]SearchResult, error)`
- `SearchWithFilters(ctx context.Context, query string, limit int, filters map[string]interface{}) ([]SearchResult, error)`
- `GetMetadata() (*Metadata, error)`
- `Close() error`

## Advanced Usage

### Search with Filters

```go
// Search only in main namespace
results, err := client.SearchWithFilters(
	context.Background(),
	"poison resistance",
	5,
	map[string]interface{}{
		"namespace": 0,
	},
)
```

### Context with Timeout

```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

results, err := client.Search(ctx, "query", 10)
```

## Example: RAG Integration

```go
func buildRAGContext(client vector.VectorClient, query string, maxTokens int) (string, error) {
	// Retrieve relevant chunks
	results, err := client.Search(context.Background(), query, 20)
	if err != nil {
		return "", err
	}

	// Build context within token limit
	var context strings.Builder
	tokens := 0

	for _, result := range results {
		chunkTokens := len(result.Content) / 4  // Rough estimate
		if tokens+chunkTokens > maxTokens {
			break
		}

		fmt.Fprintf(&context, "[%s]\n%s\n\n", result.PageTitle, result.Content)
		tokens += chunkTokens
	}

	return context.String(), nil
}
```

## License

MIT
