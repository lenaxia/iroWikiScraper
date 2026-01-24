# Story 08: Advanced Filters

**Story ID**: epic-05-story-08  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 4 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** advanced filtering options for search queries  
**So that** I can narrow down results based on multiple criteria

## Acceptance Criteria

1. **Temporal Filters**
   - [ ] Filter by creation date range
   - [ ] Filter by last modified date range
   - [ ] Filter by specific time periods (year, month)
   - [ ] Relative date filters (last 7 days, last month)

2. **Content Filters**
   - [ ] Filter by page size (min/max bytes)
   - [ ] Filter by revision count
   - [ ] Filter by number of editors
   - [ ] Filter redirects (include/exclude)

3. **Namespace Filters**
   - [ ] Single namespace selection
   - [ ] Multiple namespace selection
   - [ ] Exclude namespaces
   - [ ] Predefined namespace groups

4. **Combination**
   - [ ] Combine multiple filters with AND logic
   - [ ] Filter validation and error handling
   - [ ] Default values for unspecified filters
   - [ ] Filter preset support

## Technical Details

### Enhanced SearchOptions

```go
package irowiki

import "time"

// SearchOptions with advanced filters
type SearchOptions struct {
    // Basic search
    Query       string
    MatchType   string
    
    // Namespace filters
    Namespace      *int
    Namespaces     []int
    ExcludeNS      []int
    
    // Temporal filters
    CreatedAfter   *time.Time
    CreatedBefore  *time.Time
    ModifiedAfter  *time.Time
    ModifiedBefore *time.Time
    
    // Content filters
    MinSize        *int
    MaxSize        *int
    MinRevisions   *int
    MaxRevisions   *int
    MinEditors     *int
    MaxEditors     *int
    
    // Page type filters
    IncludeRedirects bool
    OnlyRedirects    bool
    ExcludeRedirects bool
    
    // Sorting and pagination
    SortBy      string
    SortOrder   string
    Offset      int
    Limit       int
    MinScore    float64
}

// Validate checks if filter values are valid
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
            return fmt.Errorf("created_after must be before created_before")
        }
    }
    
    if opts.ModifiedAfter != nil && opts.ModifiedBefore != nil {
        if opts.ModifiedAfter.After(*opts.ModifiedBefore) {
            return fmt.Errorf("modified_after must be before modified_before")
        }
    }
    
    // Validate size ranges
    if opts.MinSize != nil && opts.MaxSize != nil {
        if *opts.MinSize > *opts.MaxSize {
            return fmt.Errorf("min_size must be less than max_size")
        }
    }
    
    // Validate redirect filters
    conflictCount := 0
    if opts.OnlyRedirects {
        conflictCount++
    }
    if opts.ExcludeRedirects {
        conflictCount++
    }
    if conflictCount > 1 {
        return fmt.Errorf("conflicting redirect filters")
    }
    
    return nil
}

// SetDefaults applies sensible defaults
func (opts *SearchOptions) SetDefaults() {
    if opts.Limit == 0 {
        opts.Limit = 20
    }
    if opts.SortBy == "" {
        opts.SortBy = "relevance"
    }
    if opts.SortOrder == "" {
        opts.SortOrder = "desc"
    }
    if opts.MatchType == "" {
        opts.MatchType = "any"
    }
}
```

### Filter Builder

```go
// FilterBuilder constructs SQL WHERE clauses from options
type FilterBuilder struct {
    conditions []string
    args       []interface{}
    argCount   int
}

func NewFilterBuilder() *FilterBuilder {
    return &FilterBuilder{
        conditions: make([]string, 0),
        args:       make([]interface{}, 0),
        argCount:   0,
    }
}

func (b *FilterBuilder) AddCondition(condition string, args ...interface{}) {
    b.conditions = append(b.conditions, condition)
    b.args = append(b.args, args...)
    b.argCount += len(args)
}

func (b *FilterBuilder) Build() (string, []interface{}) {
    if len(b.conditions) == 0 {
        return "", nil
    }
    return " WHERE " + strings.Join(b.conditions, " AND "), b.args
}

// buildFilters constructs WHERE clause from SearchOptions
func (c *sqliteClient) buildFilters(opts SearchOptions) *FilterBuilder {
    builder := NewFilterBuilder()
    
    // Namespace filters
    if opts.Namespace != nil {
        builder.AddCondition("p.page_namespace = ?", *opts.Namespace)
    } else if len(opts.Namespaces) > 0 {
        placeholders := make([]string, len(opts.Namespaces))
        args := make([]interface{}, len(opts.Namespaces))
        for i, ns := range opts.Namespaces {
            placeholders[i] = "?"
            args[i] = ns
        }
        builder.AddCondition(
            "p.page_namespace IN ("+strings.Join(placeholders, ",")+")",
            args...,
        )
    }
    
    if len(opts.ExcludeNS) > 0 {
        placeholders := make([]string, len(opts.ExcludeNS))
        args := make([]interface{}, len(opts.ExcludeNS))
        for i, ns := range opts.ExcludeNS {
            placeholders[i] = "?"
            args[i] = ns
        }
        builder.AddCondition(
            "p.page_namespace NOT IN ("+strings.Join(placeholders, ",")+")",
            args...,
        )
    }
    
    // Temporal filters
    if opts.CreatedAfter != nil {
        builder.AddCondition("p.page_created >= ?", *opts.CreatedAfter)
    }
    if opts.CreatedBefore != nil {
        builder.AddCondition("p.page_created <= ?", *opts.CreatedBefore)
    }
    if opts.ModifiedAfter != nil {
        builder.AddCondition("p.page_modified >= ?", *opts.ModifiedAfter)
    }
    if opts.ModifiedBefore != nil {
        builder.AddCondition("p.page_modified <= ?", *opts.ModifiedBefore)
    }
    
    // Content filters
    if opts.MinSize != nil {
        builder.AddCondition("r.content_size >= ?", *opts.MinSize)
    }
    if opts.MaxSize != nil {
        builder.AddCondition("r.content_size <= ?", *opts.MaxSize)
    }
    if opts.MinRevisions != nil {
        builder.AddCondition("p.revision_count >= ?", *opts.MinRevisions)
    }
    if opts.MaxRevisions != nil {
        builder.AddCondition("p.revision_count <= ?", *opts.MaxRevisions)
    }
    
    // Redirect filters
    if opts.OnlyRedirects {
        builder.AddCondition("p.is_redirect = 1")
    } else if opts.ExcludeRedirects {
        builder.AddCondition("p.is_redirect = 0")
    }
    
    return builder
}
```

### Helper Functions for Common Filters

```go
// NewLastNDaysFilter creates a filter for recent pages
func NewLastNDaysFilter(days int) SearchOptions {
    now := time.Now()
    start := now.AddDate(0, 0, -days)
    return SearchOptions{
        ModifiedAfter: &start,
    }
}

// NewDateRangeFilter creates a filter for a date range
func NewDateRangeFilter(start, end time.Time) SearchOptions {
    return SearchOptions{
        CreatedAfter:  &start,
        CreatedBefore: &end,
    }
}

// NewSizeRangeFilter creates a filter for page size
func NewSizeRangeFilter(minBytes, maxBytes int) SearchOptions {
    return SearchOptions{
        MinSize: &minBytes,
        MaxSize: &maxBytes,
    }
}

// NewNamespaceFilter creates a filter for specific namespaces
func NewNamespaceFilter(namespaces ...int) SearchOptions {
    return SearchOptions{
        Namespaces: namespaces,
    }
}

// MergeFilters combines multiple SearchOptions
func MergeFilters(filters ...SearchOptions) SearchOptions {
    result := SearchOptions{}
    
    for _, filter := range filters {
        // Merge namespace filters
        if filter.Namespace != nil {
            result.Namespace = filter.Namespace
        }
        result.Namespaces = append(result.Namespaces, filter.Namespaces...)
        result.ExcludeNS = append(result.ExcludeNS, filter.ExcludeNS...)
        
        // Merge temporal filters (take most restrictive)
        if filter.CreatedAfter != nil {
            if result.CreatedAfter == nil || filter.CreatedAfter.After(*result.CreatedAfter) {
                result.CreatedAfter = filter.CreatedAfter
            }
        }
        // ... similar for other fields
    }
    
    return result
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 05: Data Models
- Story 06: Page Search

## Implementation Notes

- Use pointer fields for optional filters (distinguishes unset from zero)
- Validate filter combinations to prevent logical conflicts
- Optimize queries by applying most selective filters first
- Consider adding filter presets for common use cases
- Document filter behavior and interactions
- Support builder pattern for complex filters

## Testing Requirements

- [ ] Individual filter tests
- [ ] Combined filter tests
- [ ] Filter validation tests
- [ ] Edge case tests (boundary values)
- [ ] Performance tests with multiple filters
- [ ] Filter preset tests
- [ ] Error handling tests

## Definition of Done

- [ ] Enhanced SearchOptions implemented
- [ ] Filter builder working
- [ ] All filter types functional
- [ ] Filter validation working
- [ ] Helper functions provided
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Code reviewed and approved
