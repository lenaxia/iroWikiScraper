package irowiki

import (
	"context"
	"database/sql"
	"fmt"
	"regexp"
	"strings"
	"unicode"
)

// maxRedirectHops bounds redirect chain following to guard against
// redirect loops and long chains in malformed archives.
const maxRedirectHops = 5

// ErrRedirectLoop is returned when following redirects exceeds maxRedirectHops,
// indicating a redirect cycle or an excessively long chain.
var ErrRedirectLoop = fmt.Errorf("redirect loop or chain exceeding %d hops", maxRedirectHops)

// redirectTargetRe matches the MediaWiki redirect magic word at the start of
// page content and captures the target title. Real archives contain variants:
//
//	#REDIRECT [[Target]]
//	#redirect [[Target|label]]
//	#REDIRECT: [[Target#Section]]
var redirectTargetRe = regexp.MustCompile(`(?i)^\s*#REDIRECT\s*:?\s*\[\[([^\]|]*)`)

// dotEscapes maps MediaWiki dot-encoding sequences found in stored link
// targets (e.g. ".26" for "&", ".2F" for "/") back to their characters.
var dotEscapes = map[string]string{
	".26": "&",
	".2F": "/",
	".2D": "-",
	".3F": "?",
	".3A": ":",
}

// normalizeTitle canonicalizes a wiki title or redirect target for lookup:
//   - decodes MediaWiki dot-escapes (".26" -> "&", ".2F" -> "/")
//   - strips the "#fragment" section anchor
//   - converts underscores to spaces
//   - collapses runs of whitespace and trims
//
// The result uses space-form; use titleCandidates for DB matching since
// stored titles may use either form.
func normalizeTitle(s string) string {
	for esc, ch := range dotEscapes {
		s = strings.ReplaceAll(s, esc, ch)
	}
	if i := strings.IndexByte(s, '#'); i >= 0 {
		s = s[:i]
	}
	s = strings.ReplaceAll(s, "_", " ")
	s = strings.Join(strings.Fields(s), " ")
	return s
}

// parseRedirectTarget extracts the redirect target from page content.
// Returns the raw target and true when content begins with the redirect
// magic word; otherwise returns("", false).
func parseRedirectTarget(content string) (string, bool) {
	m := redirectTargetRe.FindStringSubmatch(content)
	if m == nil {
		return "", false
	}
	target := strings.TrimSpace(m[1])
	if target == "" {
		return "", false
	}
	return target, true
}

// titleCandidates builds the set of stored-title forms to try for a
// normalized title: space-form and underscore-form, each with the first
// letter upper- and lower-cased (MediaWiki titles are case-sensitive
// except for the first character).
func titleCandidates(normalized string) []string {
	if normalized == "" {
		return nil
	}
	underscore := strings.ReplaceAll(normalized, " ", "_")
	seen := make(map[string]struct{}, 4)
	var out []string
	for _, t := range []string{normalized, underscore} {
		for _, v := range []string{upperFirst(t), lowerFirst(t)} {
			if _, dup := seen[v]; !dup {
				seen[v] = struct{}{}
				out = append(out, v)
			}
		}
	}
	return out
}

func upperFirst(s string) string {
	if s == "" {
		return s
	}
	r := []rune(s)
	r[0] = unicode.ToUpper(r[0])
	return string(r)
}

func lowerFirst(s string) string {
	if s == "" {
		return s
	}
	r := []rune(s)
	r[0] = unicode.ToLower(r[0])
	return string(r)
}

// resolveRedirectFrom follows redirect chains starting at title, using
// fetchPage to retrieve (canonicalTitle, latestContent) for each hop.
// Shared by the SQLite and PostgreSQL backends.
func resolveRedirectFrom(ctx context.Context, title string, fetchPage func(context.Context, []string) (string, string, error)) (string, error) {
	current := normalizeTitle(title)
	for hop := 0; hop < maxRedirectHops; hop++ {
		canonical, content, err := fetchPage(ctx, titleCandidates(current))
		if err != nil {
			return "", err
		}
		if target, ok := parseRedirectTarget(content); ok {
			next := normalizeTitle(target)
			if next == "" {
				return canonical, nil
			}
			current = next
			continue
		}
		return canonical, nil
	}
	return "", ErrRedirectLoop
}

// fetchLatestTitleContentSQLite returns the canonical stored title and the
// latest revision content for the first page matching any candidate title.
// Candidates are ordered deterministically (lowest namespace, newest revision).
func fetchLatestTitleContentSQLite(ctx context.Context, db *sql.DB, candidates []string) (string, string, error) {
	if len(candidates) == 0 {
		return "", "", ErrNotFound
	}
	placeholders := make([]string, len(candidates))
	args := make([]interface{}, len(candidates))
	for i, c := range candidates {
		placeholders[i] = "?"
		args[i] = c
	}
	const queryPrefix = `
		SELECT p.title, r.content
		FROM pages p
		LEFT JOIN revisions r ON p.page_id = r.page_id
		WHERE p.title IN (%s)
		ORDER BY p.namespace ASC, r.timestamp DESC
		LIMIT 1
	`
	var title, content sql.NullString
	err := db.QueryRowContext(ctx, fmt.Sprintf(queryPrefix, strings.Join(placeholders, ",")), args...).Scan(&title, &content)
	if err == sql.ErrNoRows {
		return "", "", ErrNotFound
	}
	if err != nil {
		return "", "", fmt.Errorf("%w: %v", ErrDatabaseError, err)
	}
	return title.String, content.String, nil
}
