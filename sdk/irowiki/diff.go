package irowiki

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

// GetRevisionDiff computes the diff between two revisions.
func (c *sqliteClient) GetRevisionDiff(ctx context.Context, fromRevID, toRevID int64) (*DiffResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Fetch both revisions
	fromRev, err := c.GetRevision(ctx, fromRevID)
	if err != nil {
		return nil, fmt.Errorf("failed to get from revision: %w", err)
	}

	toRev, err := c.GetRevision(ctx, toRevID)
	if err != nil {
		return nil, fmt.Errorf("failed to get to revision: %w", err)
	}

	// Ensure they're for the same page
	if fromRev.PageID != toRev.PageID {
		return nil, fmt.Errorf("%w: revisions are for different pages", ErrInvalidInput)
	}

	return computeDiff(fromRev, toRev), nil
}

// GetConsecutiveDiff computes the diff from a revision to its parent.
func (c *sqliteClient) GetConsecutiveDiff(ctx context.Context, revID int64) (*DiffResult, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}

	// Get the revision
	toRev, err := c.GetRevision(ctx, revID)
	if err != nil {
		return nil, err
	}

	// Check if it has a parent
	if toRev.ParentID == nil {
		// This is the first revision - diff from empty
		return computeDiffFromEmpty(toRev), nil
	}

	// Get parent revision
	const query = `
		SELECT revision_id, page_id, parent_id, timestamp, user, user_id,
		       comment, content, size, sha1, minor, tags
		FROM revisions
		WHERE revision_id = ?
	`

	var fromRev Revision
	var parentID sql.NullInt64
	var user sql.NullString
	var userID sql.NullInt64
	var comment sql.NullString
	var tagsJSON sql.NullString

	err = c.db.QueryRowContext(ctx, query, *toRev.ParentID).Scan(
		&fromRev.ID, &fromRev.PageID, &parentID, &fromRev.Timestamp, &user, &userID,
		&comment, &fromRev.Content, &fromRev.Size, &fromRev.SHA1, &fromRev.Minor, &tagsJSON,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	// Handle nullable fields
	if parentID.Valid {
		pid := parentID.Int64
		fromRev.ParentID = &pid
	}
	if user.Valid {
		fromRev.User = user.String
	}
	if userID.Valid {
		uid := int(userID.Int64)
		fromRev.UserID = &uid
	}
	if comment.Valid {
		fromRev.Comment = comment.String
	}

	return computeDiff(&fromRev, toRev), nil
}

// computeDiff generates a unified diff between two revisions.
// This implements a simple line-by-line diff algorithm.
func computeDiff(from, to *Revision) *DiffResult {
	result := &DiffResult{
		FromRevision:  from.ID,
		ToRevision:    to.ID,
		FromTimestamp: from.Timestamp,
		ToTimestamp:   to.Timestamp,
	}

	fromLines := strings.Split(from.Content, "\n")
	toLines := strings.Split(to.Content, "\n")

	// Compute simple line-by-line diff using LCS
	diff := simpleDiff(fromLines, toLines)
	result.Unified = formatUnified(diff, fromLines, toLines)
	result.Stats = computeStats(diff, from.Content, to.Content)

	return result
}

// computeDiffFromEmpty generates a diff from an empty state (first revision).
func computeDiffFromEmpty(to *Revision) *DiffResult {
	result := &DiffResult{
		FromRevision: 0,
		ToRevision:   to.ID,
		ToTimestamp:  to.Timestamp,
	}

	lines := strings.Split(to.Content, "\n")
	var unified strings.Builder
	unified.WriteString("@@ -0,0 +1,")
	unified.WriteString(fmt.Sprintf("%d", len(lines)))
	unified.WriteString(" @@\n")

	for _, line := range lines {
		unified.WriteString("+")
		unified.WriteString(line)
		unified.WriteString("\n")
	}

	result.Unified = unified.String()
	result.Stats = DiffStats{
		LinesAdded:    len(lines),
		CharsAdded:    len(to.Content),
		ChangePercent: 100.0,
	}

	return result
}

// diffOp represents a diff operation.
type diffOp struct {
	Type string // "equal", "delete", "insert"
	Line int
	Text string
}

// simpleDiff performs a simple line-by-line diff using longest common subsequence.
func simpleDiff(from, to []string) []diffOp {
	// Build LCS matrix
	m, n := len(from), len(to)
	lcs := make([][]int, m+1)
	for i := range lcs {
		lcs[i] = make([]int, n+1)
	}

	for i := 1; i <= m; i++ {
		for j := 1; j <= n; j++ {
			if from[i-1] == to[j-1] {
				lcs[i][j] = lcs[i-1][j-1] + 1
			} else {
				lcs[i][j] = max(lcs[i-1][j], lcs[i][j-1])
			}
		}
	}

	// Backtrack to build diff operations
	var ops []diffOp
	i, j := m, n

	for i > 0 || j > 0 {
		if i > 0 && j > 0 && from[i-1] == to[j-1] {
			ops = append([]diffOp{{Type: "equal", Line: i, Text: from[i-1]}}, ops...)
			i--
			j--
		} else if j > 0 && (i == 0 || lcs[i][j-1] >= lcs[i-1][j]) {
			ops = append([]diffOp{{Type: "insert", Line: j, Text: to[j-1]}}, ops...)
			j--
		} else if i > 0 {
			ops = append([]diffOp{{Type: "delete", Line: i, Text: from[i-1]}}, ops...)
			i--
		}
	}

	return ops
}

// formatUnified formats diff operations into unified diff format.
func formatUnified(ops []diffOp, fromLines, toLines []string) string {
	var result strings.Builder
	var fromStart, toStart int
	var fromCount, toCount int
	var hunkLines []string

	flushHunk := func() {
		if len(hunkLines) > 0 {
			result.WriteString(fmt.Sprintf("@@ -%d,%d +%d,%d @@\n",
				fromStart+1, fromCount, toStart+1, toCount))
			for _, line := range hunkLines {
				result.WriteString(line)
				result.WriteString("\n")
			}
			hunkLines = nil
		}
	}

	for i, op := range ops {
		if i == 0 || (i > 0 && ops[i-1].Type == "equal") {
			flushHunk()
			fromStart = 0
			toStart = 0
			fromCount = 0
			toCount = 0
		}

		switch op.Type {
		case "equal":
			hunkLines = append(hunkLines, " "+op.Text)
			fromCount++
			toCount++
		case "delete":
			hunkLines = append(hunkLines, "-"+op.Text)
			fromCount++
		case "insert":
			hunkLines = append(hunkLines, "+"+op.Text)
			toCount++
		}
	}

	flushHunk()
	return result.String()
}

// computeStats calculates diff statistics.
func computeStats(ops []diffOp, fromContent, toContent string) DiffStats {
	stats := DiffStats{}

	for _, op := range ops {
		switch op.Type {
		case "delete":
			stats.LinesRemoved++
			stats.CharsRemoved += len(op.Text)
		case "insert":
			stats.LinesAdded++
			stats.CharsAdded += len(op.Text)
		}
	}

	// Calculate change percentage
	fromLineCount := len(strings.Split(fromContent, "\n"))
	if fromLineCount > 0 {
		changedLines := stats.LinesAdded + stats.LinesRemoved
		stats.ChangePercent = float64(changedLines) / float64(fromLineCount) * 100
		if stats.ChangePercent > 100 {
			stats.ChangePercent = 100
		}
	} else {
		stats.ChangePercent = 100
	}

	return stats
}

// max returns the maximum of two integers.
func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
