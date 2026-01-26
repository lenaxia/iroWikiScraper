// Package vector provides utilities for working with iRO Wiki vector databases
package vector

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// SearchResult represents a single search result from the vector database
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

// LoadMetadata loads metadata.json from the vector database directory
func LoadMetadata(dbPath string) (*Metadata, error) {
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
