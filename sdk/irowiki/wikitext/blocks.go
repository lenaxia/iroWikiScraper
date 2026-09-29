package wikitext

import (
	"regexp"
	"strings"
)

var (
	wikilinkRe   = regexp.MustCompile(`\[\[([^\]|]+)(?:\|([^\]]*))?\]\]`)
	extlinkRe    = regexp.MustCompile(`\[(https?://[^\s\]]+)(?:[ \t]+([^\]]*))?\]`)
	boldRe       = regexp.MustCompile(`'''([^']+|[^']*[^']'''?)'''`)
	italicRe     = regexp.MustCompile(`''([^']+)''`)
	htmlTagRe    = regexp.MustCompile(`</?(span|font|small|sub|sup|b|i|u|s|code|div|center)(\s[^>]*)?>`)
	refRe        = regexp.MustCompile(`(?s)<ref[^>]*>.*?</ref>|<ref[^>]*/>`)
	commentRe    = regexp.MustCompile(`(?s)<!--.*?-->`)
	magicWordRe  = regexp.MustCompile(`__[A-Z]+__`)
	signatureRe  = regexp.MustCompile(`~{3,5}`)
	galleryRe    = regexp.MustCompile(`(?s)<gallery>.*?</gallery>`)
	hrRe         = regexp.MustCompile(`^-{4,}$`)
	htmlEntityRe = regexp.MustCompile(`&(amp|lt|gt|quot|#39|nbsp);`)
)

var htmlEntity = map[string]string{
	"amp": "&", "lt": "<", "gt": ">", "quot": "\"", "#39": "'", "nbsp": " ",
}

// headingMarker extracts the level and text from a block carrying the
// heading sentinel prefix.
func headingMarker(block string) (level int, text string, ok bool) {
	if !strings.HasPrefix(block, "#\x00") {
		return 0, "", false
	}
	rest := block[2:]
	i := strings.IndexByte(rest, '\x00')
	if i < 0 {
		return 0, "", false
	}
	return int(rest[0] - '0'), rest[i+1:], true
}

// convertBlocks converts template-replaced wikitext into markdown blocks.
// Heading blocks carry a "#\x00<level>\x00<text>" sentinel consumed by
// splitSections and are emitted as markdown headings right after it.
func convertBlocks(src string) []string {
	lines := strings.Split(src, "\n")
	var out []string
	var table []string
	flushTable := func() {
		if len(table) > 0 {
			out = append(out, convertTable(table)...)
			table = nil
		}
	}
	inPre := false
	for _, raw := range lines {
		line := strings.TrimRight(raw, "\r")
		if len(table) > 0 {
			table = append(table, line)
			if strings.HasPrefix(strings.TrimSpace(line), "|}") {
				flushTable()
			}
			continue
		}
		if strings.HasPrefix(strings.TrimSpace(line), "{|") {
			table = append(table, line)
			continue
		}
		if b, handled := convertLine(line, &inPre); handled {
			out = append(out, b...)
		}
	}
	flushTable()
	return out
}

// parseHeading detects MediaWiki heading syntax ("== x ==", 2-6 marks,
// balanced) without regular-expression backreferences.
func parseHeading(s string) (level int, text string, ok bool) {
	n := 0
	for n < len(s) && s[n] == '=' {
		n++
	}
	if n < 2 || n > 6 || n > len(s)-n {
		return 0, "", false
	}
	rest := strings.TrimRight(s[n:], " \t")
	rep := strings.Repeat("=", n)
	if !strings.HasSuffix(rest, rep) {
		return 0, "", false
	}
	text = strings.TrimSpace(rest[:len(rest)-n])
	if text == "" || strings.HasPrefix(text, "=") {
		return 0, "", false
	}
	return n - 1, text, true
}

// convertLine handles one non-table line, returning emitted blocks.
func convertLine(line string, inPre *bool) ([]string, bool) {
	if strings.HasPrefix(line, " ") && strings.TrimSpace(line) != "" {
		body := inlineConvert(line)
		if len(body) > 0 && body[0] == ' ' {
			body = body[1:] // drop the indent space
		}
		if !*inPre {
			if body == "" {
				return nil, false
			}
			*inPre = true
			return []string{"```", body}, true
		}
		if body == "" {
			return nil, false
		}
		return []string{body}, true
	}
	if *inPre {
		*inPre = false
		return []string{"```"}, true
	}

	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return nil, false
	}

	if h, text, ok := parseHeading(trimmed); ok {
		return []string{
			"#\x00" + string(rune('0'+h)) + "\x00" + text,
			strings.Repeat("#", h) + " " + inlineConvert(text),
		}, true
	}

	if hrRe.MatchString(trimmed) {
		return []string{"---"}, true
	}

	if c := trimmed[0]; c == '*' || c == '#' || c == ';' || c == ':' {
		return []string{convertListLine(trimmed)}, true
	}

	return []string{inlineConvert(trimmed)}, true
}

// convertListLine converts wiki list syntax to markdown.
func convertListLine(line string) string {
	switch {
	case strings.HasPrefix(line, "*"):
		depth := 0
		for depth < len(line) && line[depth] == '*' {
			depth++
		}
		return strings.Repeat("  ", depth-1) + "- " + inlineConvert(strings.TrimSpace(line[depth:]))
	case strings.HasPrefix(line, "#"):
		depth := 0
		for depth < len(line) && line[depth] == '#' {
			depth++
		}
		return strings.Repeat("  ", depth-1) + "1. " + inlineConvert(strings.TrimSpace(line[depth:]))
	case strings.HasPrefix(line, ";"):
		rest := strings.TrimSpace(line[1:])
		if i := strings.IndexByte(rest, ':'); i >= 0 {
			return "- **" + inlineConvert(rest[:i]) + "**: " + inlineConvert(rest[i+1:])
		}
		return "- **" + inlineConvert(rest) + "**"
	default: // ':' definition continuation
		return "  " + inlineConvert(strings.TrimSpace(line[1:]))
	}
}

// stripDiscardable removes constructs that must never reach the output
// BEFORE template markers are inserted: HTML comments (which would
// otherwise swallow "<!--template:...-->" markers), refs, galleries,
// signatures, and magic words.
func stripDiscardable(s string) string {
	s = signatureRe.ReplaceAllString(s, "")
	s = refRe.ReplaceAllString(s, "")
	s = commentRe.ReplaceAllString(s, "")
	s = galleryRe.ReplaceAllString(s, "")
	s = magicWordRe.ReplaceAllString(s, "")
	return s
}

// inlineConvert applies inline transformations: HTML stripping, wikilinks,
// external links, bold/italic, entities.
func inlineConvert(s string) string {
	s = htmlTagRe.ReplaceAllString(s, "")
	s = strings.ReplaceAll(s, "<br>", "\n")
	s = strings.ReplaceAll(s, "<br />", "\n")
	s = strings.ReplaceAll(s, "<br/>", "\n")

	s = wikilinkRe.ReplaceAllStringFunc(s, func(m string) string {
		parts := wikilinkRe.FindStringSubmatch(m)
		target, label := parts[1], parts[2]
		ns, page := splitNamespace(target)
		switch ns {
		case "File", "Image", "Category":
			return "" // media references and categorization chrome dropped
		}
		if i := strings.IndexByte(page, '#'); i >= 0 {
			page = page[:i]
		}
		if page == "" {
			return escapeDisplay(label)
		}
		if label == "" {
			label = page
		}
		return "[" + escapeDisplay(label) + "](wiki:" + escapeTarget(page) + ")"
	})

	s = extlinkRe.ReplaceAllStringFunc(s, func(m string) string {
		parts := extlinkRe.FindStringSubmatch(m)
		url, label := parts[1], parts[2]
		if label == "" {
			return "<" + url + ">"
		}
		return "[" + escapeDisplay(label) + "](" + url + ")"
	})

	s = boldRe.ReplaceAllString(s, "**$1**")
	s = italicRe.ReplaceAllString(s, "*$1*")

	s = htmlEntityRe.ReplaceAllStringFunc(s, func(m string) string {
		e := strings.TrimSuffix(strings.TrimPrefix(m, "&"), ";")
		if r, ok := htmlEntity[e]; ok {
			return r
		}
		return m
	})
	return strings.TrimSpace(s)
}

// splitNamespace splits "Namespace:Page" (first colon only).
func splitNamespace(target string) (string, string) {
	target = strings.TrimSpace(target)
	if i := strings.IndexByte(target, ':'); i >= 0 {
		return target[:i], strings.TrimSpace(target[i+1:])
	}
	return "", target
}

// tableCell is one parsed cell pending span expansion.
type tableCell struct {
	text             string
	rowspan, colspan int
}

// convertTable converts one wikitext table into markdown blocks,
// flattening rowspan/colspan by repeating cell content (deterministic,
// information-preserving).
func convertTable(lines []string) []string {
	var caption string
	var rows [][]tableCell

	for _, ln := range lines {
		t := strings.TrimSpace(ln)
		switch {
		case strings.HasPrefix(t, "{|") || strings.HasPrefix(t, "|}") || strings.HasPrefix(t, "|-"):
			if strings.HasPrefix(t, "|-") {
				rows = append(rows, nil)
			}
			continue
		case strings.HasPrefix(t, "|+"):
			caption = inlineConvert(strings.TrimSpace(t[2:]))
			continue
		case strings.HasPrefix(t, "|") || strings.HasPrefix(t, "!"):
			if len(rows) == 0 {
				rows = append(rows, nil)
			}
			body := t[1:]
			body = strings.ReplaceAll(body, "!!", "\x00CELL\x00")
			body = strings.ReplaceAll(body, "||", "\x00CELL\x00")
			for _, c := range strings.Split(body, "\x00CELL\x00") {
				ct := strings.TrimSpace(c)
				if ct == "" {
					continue
				}
				attrs := ""
				if i := strings.IndexByte(ct, '|'); i >= 0 && looksLikeAttrs(ct[:i]) {
					attrs, ct = ct[:i], strings.TrimSpace(ct[i+1:])
				}
				rs, cs := parseSpans(attrs)
				rows[len(rows)-1] = append(rows[len(rows)-1], tableCell{
					text: inlineConvert(ct), rowspan: rs, colspan: cs,
				})
			}
		}
	}

	// Expand spans into a dense grid by repeating cell content.
	width := 0
	for _, r := range rows {
		w := 0
		for _, c := range r {
			w += c.colspan
		}
		if w > width {
			width = w
		}
	}
	if width == 0 || len(rows) == 0 {
		return nil
	}
	grid := make([][]string, len(rows))
	for i := range grid {
		grid[i] = make([]string, width)
	}
	for r, row := range rows {
		col := 0
		for _, c := range row {
			for col < width && grid[r][col] != "" {
				col++
			}
			if col >= width {
				break
			}
			for rr := r; rr < r+c.rowspan && rr < len(grid); rr++ {
				for cc := col; cc < col+c.colspan && cc < width; cc++ {
					grid[rr][cc] = c.text
				}
			}
			col += c.colspan
		}
	}

	var out []string
	if caption != "" {
		out = append(out, "**"+caption+"**")
	}
	var sb strings.Builder
	sb.WriteString("|")
	for i := 0; i < width; i++ {
		sb.WriteString(" --- |")
	}
	out = append(out, sb.String())
	for _, row := range grid {
		sb.Reset()
		sb.WriteString("|")
		for _, txt := range row {
			cell := strings.ReplaceAll(txt, "\n", " ")
			sb.WriteString(" " + escapeCell(cell) + " |")
		}
		out = append(out, sb.String())
	}
	return out
}

func looksLikeAttrs(s string) bool {
	s = strings.TrimSpace(s)
	if s == "" || !strings.Contains(s, "=") {
		return false
	}
	// Cell attributes are single key="value" tokens; reject anything
	// containing content separators or prose punctuation.
	return !strings.ContainsAny(s, "|!.?")
}

// parseSpans extracts rowspan/colspan counts from a cell attribute string.
func parseSpans(attrs string) (rowspan, colspan int) {
	rowspan, colspan = 1, 1
	low := strings.ToLower(attrs)
	if m := spanRe("rowspan").FindStringSubmatch(low); m != nil {
		if n := atoi(m[1]); n > 1 {
			rowspan = n
		}
	}
	if m := spanRe("colspan").FindStringSubmatch(low); m != nil {
		if n := atoi(m[1]); n > 1 {
			colspan = n
		}
	}
	return
}

func spanRe(attr string) *regexp.Regexp {
	return regexp.MustCompile(attr + `\s*=\s*"?(\d+)"?`)
}

func atoi(s string) int {
	n := 0
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			return n
		}
		n = n*10 + int(ch-'0')
	}
	return n
}

// escapeCell escapes pipe characters for markdown table cells.
func escapeCell(s string) string {
	return strings.ReplaceAll(s, "|", "\\|")
}

// escapeDisplay escapes characters that break markdown link display text.
func escapeDisplay(s string) string {
	s = strings.ReplaceAll(s, "[", "\\[")
	s = strings.ReplaceAll(s, "]", "\\]")
	s = strings.ReplaceAll(s, "\n", " ")
	return s
}

// escapeTarget escapes characters that break markdown link targets.
func escapeTarget(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, " ", "_")
	s = strings.ReplaceAll(s, "(", "%28")
	s = strings.ReplaceAll(s, ")", "%29")
	return s
}

// nfc normalizes the input for deterministic conversion. Wiki content is
// overwhelmingly ASCII; ToValidUTF8 also drops invalid byte sequences so
// output is always well-formed.
func nfc(s string) string {
	return strings.ToValidUTF8(s, "")
}
