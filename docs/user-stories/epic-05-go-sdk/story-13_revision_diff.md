# Story 13: Revision Diff

**Story ID**: epic-05-story-13  
**Epic**: Epic 05 - Go SDK  
**Priority**: Medium  
**Estimate**: 5 hours  
**Status**: Not Started

## User Story

**As a** developer  
**I want** to generate diffs between wiki page revisions  
**So that** I can see exactly what changed between versions

## Acceptance Criteria

1. **Diff Generation**
   - [ ] Generate unified diff between two revisions
   - [ ] Support line-by-line diff
   - [ ] Support word-by-word diff
   - [ ] Support character-by-character diff

2. **Diff Formats**
   - [ ] Unified diff format (standard patch format)
   - [ ] Side-by-side comparison
   - [ ] HTML diff with highlighting
   - [ ] JSON structured diff

3. **Statistics**
   - [ ] Lines added/removed/changed
   - [ ] Words added/removed
   - [ ] Characters added/removed
   - [ ] Change percentage

4. **Performance**
   - [ ] Efficient diff algorithm (Myers, or similar)
   - [ ] Handle large content efficiently
   - [ ] Cache computed diffs
   - [ ] Support streaming for large diffs

## Technical Details

### Diff Implementation

```go
package irowiki

import (
    "context"
    "fmt"
    "strings"
    
    "github.com/sergi/go-diff/diffmatchpatch"
)

// DiffFormat specifies the output format
type DiffFormat string

const (
    DiffUnified    DiffFormat = "unified"
    DiffSideBySide DiffFormat = "sidebyside"
    DiffHTML       DiffFormat = "html"
    DiffJSON       DiffFormat = "json"
)

// DiffGranularity specifies the level of comparison
type DiffGranularity string

const (
    DiffLine      DiffGranularity = "line"
    DiffWord      DiffGranularity = "word"
    DiffCharacter DiffGranularity = "character"
)

// DiffResult contains the comparison between two revisions
type DiffResult struct {
    FromRevision  int64
    ToRevision    int64
    FromTimestamp time.Time
    ToTimestamp   time.Time
    Format        DiffFormat
    Granularity   DiffGranularity
    
    // Diff content
    Diff          string
    Patches       []Patch
    
    // Statistics
    Stats         DiffStats
}

// DiffStats contains statistical information about changes
type DiffStats struct {
    LinesAdded    int
    LinesRemoved  int
    LinesChanged  int
    WordsAdded    int
    WordsRemoved  int
    CharsAdded    int
    CharsRemoved  int
    ChangePercent float64
}

// Patch represents a single change
type Patch struct {
    Type      string // "add", "remove", "change"
    Line      int
    OldText   string
    NewText   string
    Context   []string
}

// DiffOptions configures diff generation
type DiffOptions struct {
    Format      DiffFormat
    Granularity DiffGranularity
    Context     int  // Lines of context (for unified diff)
    IgnoreCase  bool
    IgnoreWhitespace bool
}

// GetRevisionDiff computes diff between two revisions
func (c *sqliteClient) GetRevisionDiff(ctx context.Context, fromID, toID int64, opts DiffOptions) (*DiffResult, error) {
    // Fetch both revisions
    from, err := c.GetRevision(ctx, fromID)
    if err != nil {
        return nil, fmt.Errorf("failed to get from revision: %w", err)
    }
    
    to, err := c.GetRevision(ctx, toID)
    if err != nil {
        return nil, fmt.Errorf("failed to get to revision: %w", err)
    }
    
    // Ensure they're for the same page
    if from.PageID != to.PageID {
        return nil, fmt.Errorf("revisions are for different pages")
    }
    
    return c.computeDiff(from, to, opts)
}

// GetConsecutiveDiff computes diff from a revision to its previous one
func (c *sqliteClient) GetConsecutiveDiff(ctx context.Context, revID int64, opts DiffOptions) (*DiffResult, error) {
    // Get the revision
    to, err := c.GetRevision(ctx, revID)
    if err != nil {
        return nil, err
    }
    
    // Get previous revision
    const query = `
        SELECT rev_id, content
        FROM revisions
        WHERE page_id = ? AND rev_timestamp < ?
        ORDER BY rev_timestamp DESC
        LIMIT 1
    `
    
    var fromID int64
    var fromContent string
    err = c.db.QueryRowContext(ctx, query, to.PageID, to.Timestamp).Scan(&fromID, &fromContent)
    
    if err == sql.ErrNoRows {
        // This is the first revision
        return c.computeDiffFromEmpty(to, opts)
    }
    if err != nil {
        return nil, err
    }
    
    from := &Revision{
        ID:      fromID,
        PageID:  to.PageID,
        Content: fromContent,
    }
    
    return c.computeDiff(from, to, opts)
}

// computeDiff generates the actual diff
func (c *sqliteClient) computeDiff(from, to *Revision, opts DiffOptions) (*DiffResult, error) {
    result := &DiffResult{
        FromRevision:  from.ID,
        ToRevision:    to.ID,
        FromTimestamp: from.Timestamp,
        ToTimestamp:   to.Timestamp,
        Format:        opts.Format,
        Granularity:   opts.Granularity,
    }
    
    // Preprocess content
    fromContent := from.Content
    toContent := to.Content
    
    if opts.IgnoreCase {
        fromContent = strings.ToLower(fromContent)
        toContent = strings.ToLower(toContent)
    }
    
    if opts.IgnoreWhitespace {
        fromContent = normalizeWhitespace(fromContent)
        toContent = normalizeWhitespace(toContent)
    }
    
    // Generate diff based on granularity
    switch opts.Granularity {
    case DiffLine:
        result.Diff, result.Patches = c.diffLines(fromContent, toContent, opts)
    case DiffWord:
        result.Diff = c.diffWords(fromContent, toContent, opts)
    case DiffCharacter:
        result.Diff = c.diffCharacters(fromContent, toContent, opts)
    default:
        return nil, fmt.Errorf("unsupported granularity: %s", opts.Granularity)
    }
    
    // Compute statistics
    result.Stats = c.computeDiffStats(fromContent, toContent, result.Patches)
    
    // Format output
    switch opts.Format {
    case DiffUnified:
        result.Diff = c.formatUnified(result.Patches, opts.Context)
    case DiffHTML:
        result.Diff = c.formatHTML(result.Patches)
    case DiffJSON:
        // Already in structured format
    }
    
    return result, nil
}

// diffLines performs line-by-line diff
func (c *sqliteClient) diffLines(from, to string, opts DiffOptions) (string, []Patch) {
    fromLines := strings.Split(from, "\n")
    toLines := strings.Split(to, "\n")
    
    dmp := diffmatchpatch.New()
    diffs := dmp.DiffMain(from, to, false)
    
    var patches []Patch
    lineNum := 1
    
    for _, diff := range diffs {
        patch := Patch{
            Line: lineNum,
        }
        
        switch diff.Type {
        case diffmatchpatch.DiffInsert:
            patch.Type = "add"
            patch.NewText = diff.Text
        case diffmatchpatch.DiffDelete:
            patch.Type = "remove"
            patch.OldText = diff.Text
        case diffmatchpatch.DiffEqual:
            continue
        }
        
        patches = append(patches, patch)
        lineNum += strings.Count(diff.Text, "\n")
    }
    
    return dmp.DiffPrettyText(diffs), patches
}

// diffWords performs word-by-word diff
func (c *sqliteClient) diffWords(from, to string, opts DiffOptions) string {
    dmp := diffmatchpatch.New()
    
    // Convert to word-level diffs
    fromWords := strings.Fields(from)
    toWords := strings.Fields(to)
    
    fromText := strings.Join(fromWords, "\n")
    toText := strings.Join(toWords, "\n")
    
    diffs := dmp.DiffMain(fromText, toText, false)
    diffs = dmp.DiffCleanupSemantic(diffs)
    
    return dmp.DiffPrettyText(diffs)
}

// diffCharacters performs character-by-character diff
func (c *sqliteClient) diffCharacters(from, to string, opts DiffOptions) string {
    dmp := diffmatchpatch.New()
    diffs := dmp.DiffMain(from, to, true)
    diffs = dmp.DiffCleanupEfficiency(diffs)
    
    return dmp.DiffPrettyText(diffs)
}

// computeDiffStats calculates change statistics
func (c *sqliteClient) computeDiffStats(from, to string, patches []Patch) DiffStats {
    stats := DiffStats{}
    
    fromLines := strings.Split(from, "\n")
    toLines := strings.Split(to, "\n")
    
    for _, patch := range patches {
        switch patch.Type {
        case "add":
            stats.LinesAdded++
            stats.WordsAdded += len(strings.Fields(patch.NewText))
            stats.CharsAdded += len(patch.NewText)
        case "remove":
            stats.LinesRemoved++
            stats.WordsRemoved += len(strings.Fields(patch.OldText))
            stats.CharsRemoved += len(patch.OldText)
        case "change":
            stats.LinesChanged++
        }
    }
    
    // Calculate change percentage
    totalLines := len(fromLines)
    if totalLines > 0 {
        changedLines := stats.LinesAdded + stats.LinesRemoved + stats.LinesChanged
        stats.ChangePercent = float64(changedLines) / float64(totalLines) * 100
    }
    
    return stats
}

// formatUnified generates unified diff format
func (c *sqliteClient) formatUnified(patches []Patch, context int) string {
    var builder strings.Builder
    
    for _, patch := range patches {
        builder.WriteString(fmt.Sprintf("@@ -%d +%d @@\n", patch.Line, patch.Line))
        
        // Add context lines
        for _, ctx := range patch.Context {
            builder.WriteString(" " + ctx + "\n")
        }
        
        // Add changes
        if patch.Type == "remove" || patch.Type == "change" {
            lines := strings.Split(patch.OldText, "\n")
            for _, line := range lines {
                builder.WriteString("-" + line + "\n")
            }
        }
        
        if patch.Type == "add" || patch.Type == "change" {
            lines := strings.Split(patch.NewText, "\n")
            for _, line := range lines {
                builder.WriteString("+" + line + "\n")
            }
        }
    }
    
    return builder.String()
}

// formatHTML generates HTML diff with highlighting
func (c *sqliteClient) formatHTML(patches []Patch) string {
    var builder strings.Builder
    builder.WriteString("<div class=\"diff\">")
    
    for _, patch := range patches {
        switch patch.Type {
        case "add":
            builder.WriteString(fmt.Sprintf(
                "<div class=\"diff-add\"><ins>%s</ins></div>",
                htmlEscape(patch.NewText),
            ))
        case "remove":
            builder.WriteString(fmt.Sprintf(
                "<div class=\"diff-remove\"><del>%s</del></div>",
                htmlEscape(patch.OldText),
            ))
        case "change":
            builder.WriteString(fmt.Sprintf(
                "<div class=\"diff-change\"><del>%s</del><ins>%s</ins></div>",
                htmlEscape(patch.OldText),
                htmlEscape(patch.NewText),
            ))
        }
    }
    
    builder.WriteString("</div>")
    return builder.String()
}

// Helper functions

func normalizeWhitespace(s string) string {
    return strings.Join(strings.Fields(s), " ")
}

func htmlEscape(s string) string {
    s = strings.ReplaceAll(s, "&", "&amp;")
    s = strings.ReplaceAll(s, "<", "&lt;")
    s = strings.ReplaceAll(s, ">", "&gt;")
    return s
}

func (c *sqliteClient) computeDiffFromEmpty(to *Revision, opts DiffOptions) (*DiffResult, error) {
    result := &DiffResult{
        FromRevision:  0,
        ToRevision:    to.ID,
        ToTimestamp:   to.Timestamp,
        Format:        opts.Format,
        Granularity:   opts.Granularity,
    }
    
    // All content is new
    result.Stats.LinesAdded = len(strings.Split(to.Content, "\n"))
    result.Stats.CharsAdded = len(to.Content)
    result.Stats.WordsAdded = len(strings.Fields(to.Content))
    result.Stats.ChangePercent = 100.0
    
    result.Diff = "+ " + to.Content
    
    return result, nil
}
```

## Dependencies

- Story 01: Client Interface Design
- Story 02: SQLite Backend
- Story 05: Data Models
- Story 10: Page History Query
- External: github.com/sergi/go-diff/diffmatchpatch

## Implementation Notes

- Use Myers diff algorithm or similar (via diffmatchpatch library)
- Consider caching diffs for frequently compared revisions
- Handle large content efficiently (stream or chunk)
- Support various output formats for different use cases
- Provide both raw and formatted diffs
- Consider semantic diff cleaning for better readability

## Testing Requirements

- [ ] Line diff tests
- [ ] Word diff tests
- [ ] Character diff tests
- [ ] Format tests (unified, HTML, JSON)
- [ ] Statistics calculation tests
- [ ] Edge cases (empty content, identical content)
- [ ] Large content performance tests
- [ ] Unicode handling tests

## Definition of Done

- [ ] Diff generation implemented for all granularities
- [ ] All output formats working
- [ ] Statistics calculation accurate
- [ ] All tests passing
- [ ] Performance acceptable for large diffs
- [ ] Documentation complete
- [ ] Code reviewed and approved
