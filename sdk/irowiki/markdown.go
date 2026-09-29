package irowiki

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
)

// MarkdownSection is one addressable section of a page's materialized
// markdown (see the wikitext package for anchor semantics).
type MarkdownSection struct {
	Anchor   string
	Heading  string
	Level    int
	Markdown string
}

// PageMarkdown is the materialized markdown view of a page.
type PageMarkdown struct {
	PageID int64
	Title  string

	// Redirect is the redirect target when the page is a redirect.
	Redirect string

	// Markdown is the full-page markdown (all sections).
	Markdown string

	// Sections are the per-section chunks with stable anchors.
	Sections []MarkdownSection
}

// MarkdownHit is one full-text search result over materialized markdown.
type MarkdownHit struct {
	PageID  int64
	Title   string
	Anchor  string
	Snippet string
}

// GetPageMarkdown retrieves the materialized markdown for a page by
// title, following redirects first. Returns ErrNotFound when the page
// does not exist and ErrNotMaterialized when the archive carries no
// pages_md content (run the materialize command on the database).
func (c *sqliteClient) GetPageMarkdown(ctx context.Context, title string) (*PageMarkdown, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	canonical, err := c.ResolveRedirect(ctx, title)
	if err != nil {
		return nil, err
	}

	var pageID int64
	var ns int
	err = c.db.QueryRowContext(ctx,
		"SELECT page_id, namespace FROM pages WHERE title = ?", canonical).Scan(&pageID, &ns)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}

	rows, err := c.db.QueryContext(ctx,
		"SELECT anchor, heading, level, markdown FROM pages_md WHERE page_id = ? ORDER BY anchor", pageID)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	pm := &PageMarkdown{PageID: pageID, Title: canonical}
	for rows.Next() {
		var sec MarkdownSection
		if err := rows.Scan(&sec.Anchor, &sec.Heading, &sec.Level, &sec.Markdown); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}
		if sec.Anchor == "" {
			pm.Markdown = sec.Markdown
			continue
		}
		pm.Sections = append(pm.Sections, sec)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	if pm.Markdown == "" && len(pm.Sections) == 0 {
		return nil, ErrNotMaterialized
	}
	if target, ok := redirectOf(pm.Markdown); ok {
		pm.Redirect = target
	}
	return pm, nil
}

// GetSection retrieves one materialized section by page title and anchor.
func (c *sqliteClient) GetSection(ctx context.Context, title, anchor string) (*MarkdownSection, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	canonical, err := c.ResolveRedirect(ctx, title)
	if err != nil {
		return nil, err
	}
	var sec MarkdownSection
	err = c.db.QueryRowContext(ctx, `
		SELECT m.anchor, m.heading, m.level, m.markdown
		FROM pages_md m JOIN pages p ON p.page_id = m.page_id
		WHERE p.title = ? AND m.anchor = ?`, canonical, anchor).
		Scan(&sec.Anchor, &sec.Heading, &sec.Level, &sec.Markdown)
	if err == sql.ErrNoRows {
		// Distinguish "page has no materialization" from "anchor absent".
		var one int
		e := c.db.QueryRowContext(ctx,
			"SELECT 1 FROM pages_md m JOIN pages p ON p.page_id = m.page_id WHERE p.title = ? LIMIT 1", canonical).Scan(&one)
		if e == sql.ErrNoRows {
			return nil, ErrNotMaterialized
		}
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	return &sec, nil
}

// SearchMarkdown performs full-text search over materialized markdown
// sections. Requires the pages_md_fts index (materialize command).
func (c *sqliteClient) SearchMarkdown(ctx context.Context, query string, opts SearchOptions) ([]MarkdownHit, error) {
	if err := c.ensureNotClosed(); err != nil {
		return nil, err
	}
	if strings.TrimSpace(query) == "" {
		return nil, ErrInvalidInput
	}
	limit := opts.Limit
	if limit <= 0 {
		limit = 20
	}
	q := `"` + strings.ReplaceAll(query, `"`, `""`) + `"`
	rows, err := c.db.QueryContext(ctx, `
		SELECT f.page_id, COALESCE(p.title, ''), f.anchor,
		       snippet(pages_md_fts, 0, '', '', '…', 12)
		FROM pages_md_fts f
		LEFT JOIN pages p ON p.page_id = f.page_id
		WHERE pages_md_fts MATCH ?
		ORDER BY rank
		LIMIT ?`, q, limit)
	if err != nil {
		if strings.Contains(err.Error(), "no such table") {
			return nil, ErrNotMaterialized
		}
		return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	defer rows.Close()

	var hits []MarkdownHit
	for rows.Next() {
		var h MarkdownHit
		if err := rows.Scan(&h.PageID, &h.Title, &h.Anchor, &h.Snippet); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrDatabaseError, err)
		}
		hits = append(hits, h)
	}
	return hits, rows.Err()
}

// redirectOf extracts the redirect target from a materialized one-line
// redirect body ("→ [Target](wiki:Target)").
func redirectOf(markdown string) (string, bool) {
	if !strings.HasPrefix(markdown, "→ [") {
		return "", false
	}
	open := strings.IndexByte(markdown, ']')
	if open < 0 {
		return "", false
	}
	target := strings.TrimSuffix(markdown[3:open], "\\]")
	target = strings.ReplaceAll(target, "\\[", "[")
	if target == "" {
		return "", false
	}
	return target, true
}

// GetPageMarkdown is not yet implemented on the PostgreSQL backend
// (design doc issue #11, open question 4). It always returns
// ErrNotMaterialized.
func (c *postgresClient) GetPageMarkdown(ctx context.Context, title string) (*PageMarkdown, error) {
	return nil, errors.Join(ErrNotMaterialized, errPgMarkdown)
}

// GetSection is not yet implemented on the PostgreSQL backend.
func (c *postgresClient) GetSection(ctx context.Context, title, anchor string) (*MarkdownSection, error) {
	return nil, errors.Join(ErrNotMaterialized, errPgMarkdown)
}

// SearchMarkdown is not yet implemented on the PostgreSQL backend.
func (c *postgresClient) SearchMarkdown(ctx context.Context, query string, opts SearchOptions) ([]MarkdownHit, error) {
	return nil, errors.Join(ErrNotMaterialized, errPgMarkdown)
}

var errPgMarkdown = errors.New("markdown materialization is SQLite-only in this release; see issue #11 open question 4")
