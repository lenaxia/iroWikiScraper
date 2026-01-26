// Package vector provides a Go client for iRO Wiki vector databases
package vector

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	qdrant "github.com/qdrant/go-client/qdrant"
)

// SearchResult represents a single search result
type SearchResult struct {
	PageTitle    string  `json:"page_title"`
	SectionTitle *string `json:"section_title,omitempty"`
	Content      string  `json:"content"`
	Score        float32 `json:"score"`
	ChunkType    string  `json:"chunk_type"`
	Namespace    int     `json:"namespace"`
	PageID       int     `json:"page_id"`
}

// Metadata contains vector database metadata
type Metadata struct {
	GeneratedAt   string  `json:"generated_at"`
	Model         string  `json:"model"`
	EmbeddingDim  int     `json:"embedding_dim"`
	ChunkLevel    string  `json:"chunk_level"`
	TotalPages    int     `json:"total_pages"`
	TotalChunks   int     `json:"total_chunks"`
	ChunksPerPage float64 `json:"chunks_per_page"`
}

// VectorClient is the interface for vector database clients
type VectorClient interface {
	Search(ctx context.Context, query string, limit int) ([]SearchResult, error)
	SearchWithFilters(ctx context.Context, query string, limit int, filters map[string]interface{}) ([]SearchResult, error)
	GetMetadata() (*Metadata, error)
	Close() error
}

// QdrantClient implements VectorClient for Qdrant
type QdrantClient struct {
	client         *qdrant.Client
	collectionName string
	metadata       *Metadata
	embedder       Embedder
}

// Embedder generates embeddings for text
type Embedder interface {
	Embed(text string) ([]float32, error)
}

// NewQdrantClient creates a new Qdrant client
func NewQdrantClient(dbPath string, collectionName string, embedder Embedder) (*QdrantClient, error) {
	if collectionName == "" {
		collectionName = "irowiki"
	}

	// Connect to Qdrant
	client, err := qdrant.NewClient(&qdrant.Config{
		Host: dbPath,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create qdrant client: %w", err)
	}

	// Load metadata
	metadata, err := loadMetadata(dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load metadata: %w", err)
	}

	return &QdrantClient{
		client:         client,
		collectionName: collectionName,
		metadata:       metadata,
		embedder:       embedder,
	}, nil
}

// Search performs semantic search
func (c *QdrantClient) Search(ctx context.Context, query string, limit int) ([]SearchResult, error) {
	return c.SearchWithFilters(ctx, query, limit, nil)
}

// SearchWithFilters performs semantic search with filters
func (c *QdrantClient) SearchWithFilters(ctx context.Context, query string, limit int, filters map[string]interface{}) ([]SearchResult, error) {
	// Generate embedding
	embedding, err := c.embedder.Embed(query)
	if err != nil {
		return nil, fmt.Errorf("failed to embed query: %w", err)
	}

	// Build filter
	var filter *qdrant.Filter
	if filters != nil {
		conditions := make([]*qdrant.Condition, 0, len(filters))
		for key, value := range filters {
			conditions = append(conditions, &qdrant.Condition{
				ConditionOneOf: &qdrant.Condition_Field{
					Field: &qdrant.FieldCondition{
						Key: key,
						Match: &qdrant.Match{
							MatchValue: &qdrant.Match_Keyword{
								Keyword: fmt.Sprintf("%v", value),
							},
						},
					},
				},
			})
		}
		filter = &qdrant.Filter{
			Must: conditions,
		}
	}

	// Search
	searchResult, err := c.client.Search(ctx, &qdrant.SearchPoints{
		CollectionName: c.collectionName,
		Vector:         embedding,
		Limit:          uint64(limit),
		Filter:         filter,
		WithPayload:    &qdrant.WithPayloadSelector{SelectorOptions: &qdrant.WithPayloadSelector_Enable{Enable: true}},
	})
	if err != nil {
		return nil, fmt.Errorf("search failed: %w", err)
	}

	// Format results
	results := make([]SearchResult, 0, len(searchResult))
	for _, point := range searchResult {
		result := SearchResult{
			Score: point.Score,
		}

		// Extract payload
		if payload := point.Payload; payload != nil {
			if v, ok := payload["page_title"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					result.PageTitle = s.StringValue
				}
			}
			if v, ok := payload["section_title"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					title := s.StringValue
					result.SectionTitle = &title
				}
			}
			if v, ok := payload["content"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					result.Content = s.StringValue
				}
			}
			if v, ok := payload["chunk_type"]; ok {
				if s, ok := v.GetKind().(*qdrant.Value_StringValue); ok {
					result.ChunkType = s.StringValue
				}
			}
			if v, ok := payload["namespace"]; ok {
				if i, ok := v.GetKind().(*qdrant.Value_IntegerValue); ok {
					result.Namespace = int(i.IntegerValue)
				}
			}
			if v, ok := payload["page_id"]; ok {
				if i, ok := v.GetKind().(*qdrant.Value_IntegerValue); ok {
					result.PageID = int(i.IntegerValue)
				}
			}
		}

		results = append(results, result)
	}

	return results, nil
}

// GetMetadata returns database metadata
func (c *QdrantClient) GetMetadata() (*Metadata, error) {
	return c.metadata, nil
}

// Close closes the client connection
func (c *QdrantClient) Close() error {
	if c.client != nil {
		return c.client.Close()
	}
	return nil
}

// loadMetadata loads metadata.json from the database directory
func loadMetadata(dbPath string) (*Metadata, error) {
	metadataPath := filepath.Join(dbPath, "metadata.json")

	data, err := os.ReadFile(metadataPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read metadata file: %w", err)
	}

	var metadata Metadata
	if err := json.Unmarshal(data, &metadata); err != nil {
		return nil, fmt.Errorf("failed to parse metadata: %w", err)
	}

	return &metadata, nil
}
