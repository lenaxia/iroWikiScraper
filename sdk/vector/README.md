# iRO Wiki Vector Utilities (Go)

Go utilities for working with iRO Wiki vector databases. This package provides helper types and functions for loading metadata and working with search results.

**Note:** This package provides utilities only. You'll need to use the [Qdrant Go client](https://github.com/qdrant/go-client) directly for vector database operations.

## Installation

```bash
go get github.com/lenaxia/iroWikiScraper/sdk/vector
go get github.com/qdrant/go-client
```

## Quick Start

```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/lenaxia/iroWikiScraper/sdk/vector"
	qdrant "github.com/qdrant/go-client/qdrant"
)

func main() {
	// Load metadata
	metadata, err := vector.LoadMetadata("path/to/vector_db")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Database: %s, %d chunks from %d pages\n", 
		metadata.Model, metadata.TotalChunks, metadata.TotalPages)

	// Create Qdrant client
	client, err := qdrant.NewClient(&qdrant.Config{
		Host: "localhost",
		Port: 6334,
	})
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	// Perform search (you'll need to generate embeddings separately)
	// See https://github.com/qdrant/go-client for full API
}
```

## API Reference

### Types

```go
type SearchResult struct {
	PageTitle    string  `json:"page_title"`
	SectionTitle *string `json:"section_title,omitempty"`
	Content      string  `json:"content"`
	Score        float32 `json:"score"`
	ChunkType    string  `json:"chunk_type"`
	Namespace    int     `json:"namespace"`
	PageID       int     `json:"page_id"`
}

type Metadata struct {
	GeneratedAt   string  `json:"generated_at"`
	Model         string  `json:"model"`
	EmbeddingDim  int     `json:"embedding_dim"`
	ChunkLevel    string  `json:"chunk_level"`
	TotalPages    int     `json:"total_pages"`
	TotalChunks   int     `json:"total_chunks"`
	ChunksPerPage float64 `json:"chunks_per_page"`
}
```

### Functions

```go
// LoadMetadata loads metadata.json from the vector database directory
func LoadMetadata(dbPath string) (*Metadata, error)
```

## Complete Example with Qdrant

```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/lenaxia/iroWikiScraper/sdk/vector"
	qdrant "github.com/qdrant/go-client/qdrant"
)

func main() {
	// Load metadata
	metadata, err := vector.LoadMetadata("./vector_qdrant_minilm_section")
	if err != nil {
		log.Fatal(err)
	}

	// Create Qdrant client
	client, err := qdrant.NewClient(&qdrant.Config{
		Host: "localhost",
		Port: 6334,
	})
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	// Generate query embedding (you need an embedding model)
	queryEmbedding := getEmbedding("best weapon for undead")

	// Search
	searchResult, err := client.Query(context.Background(), &qdrant.QueryPoints{
		CollectionName: "irowiki",
		Query:          qdrant.NewQuery(queryEmbedding...),
		Limit:          qdrant.PtrOf(uint64(5)),
		WithPayload:    qdrant.NewWithPayload(true),
	})
	if err != nil {
		log.Fatal(err)
	}

	// Process results
	for _, point := range searchResult {
		result := vector.SearchResult{
			Score: point.Score,
		}
		
		// Extract payload
		if payload := point.Payload; payload != nil {
			if v, ok := payload["page_title"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					result.PageTitle = s.StringValue
				}
			}
			if v, ok := payload["content"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					result.Content = s.StringValue
				}
			}
		}

		fmt.Printf("%s: %.3f\n", result.PageTitle, result.Score)
		fmt.Printf("  %s...\n", result.Content[:min(200, len(result.Content))])
	}
}

func getEmbedding(text string) []float32 {
	// Implement using your embedding model
	// E.g., sentence-transformers, OpenAI, etc.
	return []float32{}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
```

## Generating Embeddings

You'll need to generate embeddings separately. Here are some options:

### Option 1: Using sentence-transformers via HTTP

Run a local embedding server:
```bash
pip install sentence-transformers flask
python -m flask run
```

Then call it from Go using HTTP requests.

### Option 2: Using OpenAI API

```go
import "github.com/sashabaranov/go-openai"

func getEmbedding(text string) ([]float32, error) {
	client := openai.NewClient("your-api-key")
	resp, err := client.CreateEmbeddings(
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

### Option 3: Using a Go ML library

Consider libraries like:
- [gorgonia](https://github.com/gorgonia/gorgonia) for tensor operations
- [onnxruntime-go](https://github.com/yalue/onnxruntime_go) to run ONNX models

## License

MIT
