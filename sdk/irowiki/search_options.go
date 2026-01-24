package irowiki

import (
	"fmt"
)

// Validate checks if the SearchOptions are valid.
func (opts *SearchOptions) Validate() error {
	if opts.Limit < 0 {
		return fmt.Errorf("limit must be non-negative")
	}
	if opts.Limit > 1000 {
		return fmt.Errorf("limit must not exceed 1000")
	}
	if opts.Offset < 0 {
		return fmt.Errorf("offset must be non-negative")
	}

	// Validate date ranges
	if opts.CreatedAfter != nil && opts.CreatedBefore != nil {
		if opts.CreatedAfter.After(*opts.CreatedBefore) {
			return fmt.Errorf("created_after must be before or equal to created_before")
		}
	}

	if opts.ModifiedAfter != nil && opts.ModifiedBefore != nil {
		if opts.ModifiedAfter.After(*opts.ModifiedBefore) {
			return fmt.Errorf("modified_after must be before or equal to modified_before")
		}
	}

	// Validate size ranges
	if opts.MinSize != nil && *opts.MinSize < 0 {
		return fmt.Errorf("min_size must be non-negative")
	}
	if opts.MaxSize != nil && *opts.MaxSize < 0 {
		return fmt.Errorf("max_size must be non-negative")
	}
	if opts.MinSize != nil && opts.MaxSize != nil {
		if *opts.MinSize > *opts.MaxSize {
			return fmt.Errorf("min_size must be less than or equal to max_size")
		}
	}

	// Validate redirect filters (only one can be true)
	conflictCount := 0
	if opts.OnlyRedirects {
		conflictCount++
	}
	if opts.ExcludeRedirects {
		conflictCount++
	}
	if conflictCount > 1 {
		return fmt.Errorf("only one of OnlyRedirects or ExcludeRedirects can be true")
	}

	// Validate sort options
	if opts.SortBy != "" {
		validSortBy := map[string]bool{
			"relevance": true,
			"title":     true,
			"date":      true,
			"size":      true,
		}
		if !validSortBy[opts.SortBy] {
			return fmt.Errorf("invalid sort_by: must be 'relevance', 'title', 'date', or 'size'")
		}
	}

	if opts.SortOrder != "" {
		if opts.SortOrder != "asc" && opts.SortOrder != "desc" {
			return fmt.Errorf("invalid sort_order: must be 'asc' or 'desc'")
		}
	}

	return nil
}

// SetDefaults applies sensible default values to SearchOptions.
func (opts *SearchOptions) SetDefaults() {
	if opts.Limit == 0 {
		opts.Limit = 20
	}

	if opts.SortBy == "" {
		if opts.Query != "" {
			opts.SortBy = "relevance"
		} else {
			opts.SortBy = "title"
		}
	}

	// Default sort order
	if opts.SortOrder == "" {
		if opts.SortBy == "relevance" || opts.SortBy == "date" {
			opts.SortOrder = "desc"
		} else {
			opts.SortOrder = "asc"
		}
	}

	// Default to including redirects unless explicitly excluded
	if !opts.OnlyRedirects && !opts.ExcludeRedirects {
		opts.IncludeRedirects = true
	}
}
