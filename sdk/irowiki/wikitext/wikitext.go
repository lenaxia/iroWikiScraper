package wikitext

import (
	"regexp"
	"strings"
	"unicode"
)

// redirectTargetRe mirrors the SDK's redirect detection so the converter can
// render redirect pages without importing package irowiki (which imports
// this package for materialization).
var redirectTargetRe = regexp.MustCompile(`(?i)^\s*#REDIRECT\s*:?\s*\[\[([^\]|]*)`)

// Document is the conversion result for one page.
type Document struct {
	// Title is the page title passed to Convert.
	Title string

	// Redirect is the normalized redirect target when the page is a
	// redirect; empty otherwise. Redirect pages produce a one-line
	// markdown body rather than a full conversion.
	Redirect string

	// Markdown is the full converted page (all sections).
	Markdown string

	// Sections holds per-section content with stable anchors. The section
	// before the first heading has anchor "" and Heading "".
	Sections []Section
}

// Section is one addressable chunk of a converted page.
type Section struct {
	// Anchor is the stable slug for this section ("" for the preamble).
	Anchor string

	// Heading is the raw heading text ("" for the preamble).
	Heading string

	// Level is the markdown heading level (1 for "== x ==").
	Level int

	// Markdown is the converted section body (without the heading line).
	Markdown string
}

// Convert converts one page's wikitext into a deterministic markdown
// Document. See the package documentation for rendering rules.
func Convert(title, source string) Document {
	src := nfc(source)

	if m := redirectTargetRe.FindStringSubmatch(src); m != nil {
		target := strings.TrimSpace(m[1])
		if target != "" {
			return Document{
				Title:    title,
				Redirect: target,
				Markdown: "→ [" + escapeDisplay(target) + "](wiki:" + escapeTarget(target) + ")",
				Sections: []Section{{Anchor: "", Heading: "", Level: 0, Markdown: "→ [" + escapeDisplay(target) + "](wiki:" + escapeTarget(target) + ")"}},
			}
		}
	}

	src = stripDiscardable(src)
	replaced := replaceTemplates(src)
	blocks := convertBlocks(replaced)
	var body []string
	for _, b := range blocks {
		if strings.HasPrefix(b, "#\x00") {
			continue // heading sentinel consumed by splitSections
		}
		body = append(body, b)
	}
	md := strings.TrimRight(strings.Join(body, "\n"), "\n")

	doc := Document{Title: title, Markdown: md}
	splitSections(&doc, blocks)
	return doc
}

// splitSections assigns blocks to sections based on heading markers
// produced by convertBlocks ("#\x00..." sentinel prefixes).
func splitSections(doc *Document, blocks []string) {
	cur := Section{}
	var sb strings.Builder
	flush := func() {
		cur.Markdown = strings.TrimRight(sb.String(), "\n")
		if cur.Markdown != "" || cur.Anchor != "" {
			doc.Sections = append(doc.Sections, cur)
		}
		sb.Reset()
	}
	for _, b := range blocks {
		if lvl, text, ok := headingMarker(b); ok {
			flush()
			cur = Section{Anchor: slug(text), Heading: text, Level: lvl}
			continue
		}
		sb.WriteString(b)
		sb.WriteByte('\n')
	}
	flush()
	// Deduplicate anchors deterministically.
	seen := map[string]int{}
	for i := range doc.Sections {
		base := doc.Sections[i].Anchor
		if base == "" {
			continue
		}
		if n, dup := seen[base]; dup {
			seen[base] = n + 1
			doc.Sections[i].Anchor = base + "-" + itoa(n+1)
		} else {
			seen[base] = 1
		}
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [8]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}

// slug builds a stable section anchor: lowercase, alphanumerics and
// dashes, runs of separators collapsed, trimmed.
func slug(s string) string {
	var sb strings.Builder
	prevDash := false
	for _, r := range strings.ToLower(s) {
		switch {
		case unicode.IsLetter(r) || unicode.IsDigit(r):
			sb.WriteRune(r)
			prevDash = false
		default:
			if !prevDash && sb.Len() > 0 {
				sb.WriteByte('-')
				prevDash = true
			}
		}
	}
	return strings.Trim(sb.String(), "-")
}
