package wikitext

import (
	"regexp"
	"strings"
	"unicode"
)

// invocation is one scanned template invocation.
type invocation struct {
	name   string   // normalized, lowercase, no leading ':'
	params []string // top-level split on '|'
}

// replaceTemplates finds all {{...}} invocations (balanced-brace scan,
// innermost-first) and replaces them with their rendered text.
func replaceTemplates(src string) string {
	for {
		out, changed := replaceInnermost(src)
		if !changed {
			return out
		}
		src = out
	}
}

// replaceInnermost replaces every invocation whose body contains no nested
// invocation. Returns the new string and whether anything changed.
func replaceInnermost(src string) (string, bool) {
	var sb strings.Builder
	changed := false
	i := 0
	for i < len(src) {
		if strings.HasPrefix(src[i:], "{{") {
			if end, inv, ok := scanInvocation(src, i); ok {
				inner := src[i+2 : end-2]
				if !strings.Contains(inner, "{{") {
					sb.WriteString(renderInvocation(inv))
					changed = true
					i = end
					continue
				}
				// Nested: copy the opener and continue scanning inside.
				sb.WriteString("{{")
				i += 2
				continue
			}
		}
		sb.WriteByte(src[i])
		i++
	}
	return sb.String(), changed
}

// scanInvocation finds the end index (exclusive, past "}}") of the
// invocation starting at start, tracking brace depth. It tolerates stray
// single braces inside parameters.
func scanInvocation(src string, start int) (end int, inv invocation, ok bool) {
	depth := 0
	i := start
	var bodyEnd = -1
	for i < len(src) {
		switch {
		case strings.HasPrefix(src[i:], "{{"):
			depth++
			i += 2
		case strings.HasPrefix(src[i:], "}}"):
			depth--
			i += 2
			if depth == 0 {
				bodyEnd = i
			}
		default:
			i++
		}
		if bodyEnd >= 0 {
			break
		}
	}
	if bodyEnd < 0 {
		return 0, inv, false
	}
	body := src[start+2 : bodyEnd-2]
	inv = parseInvocation(body)
	return bodyEnd, inv, true
}

// parseInvocation splits "name|p1|p2=..." at top-level pipes.
func parseInvocation(body string) invocation {
	parts := splitTopLevel(body, "|")
	name := normalizeTemplateName(parts[0])
	var params []string
	if len(parts) > 1 {
		params = make([]string, 0, len(parts)-1)
		for _, p := range parts[1:] {
			params = append(params, cleanParam(p))
		}
	}
	return invocation{name: name, params: params}
}

// splitTopLevel splits s on sep only at brace/bracket depth zero.
func splitTopLevel(s, sep string) []string {
	brace, bracket := 0, 0
	var out []string
	last := 0
	for i := 0; i < len(s); i++ {
		switch {
		case strings.HasPrefix(s[i:], "{{"):
			brace++
			i++
		case strings.HasPrefix(s[i:], "}}"):
			brace--
			i++
		case strings.HasPrefix(s[i:], "[["):
			bracket++
			i++
		case strings.HasPrefix(s[i:], "]]"):
			bracket--
			i++
		case s[i] == sep[0] && brace == 0 && bracket == 0 && len(sep) == 1:
			out = append(out, s[last:i])
			last = i + 1
		}
	}
	out = append(out, s[last:])
	return out
}

func normalizeTemplateName(raw string) string {
	n := strings.TrimSpace(raw)
	n = strings.TrimPrefix(n, ":")
	if strings.HasPrefix(n, "#") {
		// Parser function: keep only the function name, drop ":arg".
		if i := strings.IndexByte(n, ':'); i >= 0 {
			n = n[:i]
		}
	}
	n = strings.ReplaceAll(n, "_", " ")
	n = strings.Join(strings.Fields(n), " ")
	return strings.ToLower(n)
}

// cleanParam strips nowiki wrappers and trims a parameter value.
func cleanParam(p string) string {
	p = strings.ReplaceAll(p, "<nowiki>", "")
	p = strings.ReplaceAll(p, "</nowiki>", "")
	return strings.TrimSpace(p)
}

// templateClass classifies a normalized template name.
type templateClass int

const (
	classEntity templateClass = iota
	classEntityList
	classInfobox
	classInline
	classLocation
	classDrop
	classParserFn
	classUnknown
)

var classTable = map[string]templateClass{
	"monster":            classEntity,
	"item":               classEntity,
	"map":                classEntity,
	"card":               classEntity,
	"skill":              classEntity,
	"npc":                classEntity,
	"item list":          classEntityList,
	"item list 2":        classEntityList,
	"skill list":         classEntityList,
	"skill info":         classInfobox,
	"quest info":         classInfobox,
	"monster row":        classInfobox,
	"infobox job":        classInfobox,
	"infobox class":      classInfobox,
	"tooltip":            classInline,
	"plainlink":          classInline,
	"ucfirst":            classInline,
	"rh":                 classInline,
	"gr":                 classInline,
	"st":                 classInline,
	"navi":               classLocation,
	"mainpagenavigation": classDrop,
	"mainpagespotlight":  classDrop,
	"navi box":           classDrop,
}

func classify(name string) templateClass {
	if strings.HasPrefix(name, "#") {
		return classParserFn
	}
	if strings.HasPrefix(name, "infobox") {
		return classInfobox
	}
	if c, ok := classTable[name]; ok {
		return c
	}
	return classUnknown
}

// renderInvocation produces the replacement text for one invocation.
func renderInvocation(inv invocation) string {
	switch classify(inv.name) {
	case classEntity:
		return renderEntity(inv.name, inv.params)
	case classEntityList:
		var sb strings.Builder
		for _, p := range inv.params {
			if strings.TrimSpace(p) == "" {
				continue
			}
			sb.WriteString("\n- ")
			sb.WriteString(inlineConvert(p))
		}
		sb.WriteString("\n")
		return sb.String()
	case classInfobox:
		var sb strings.Builder
		sb.WriteString("\n")
		for _, p := range inv.params {
			k, v, isKV := splitKV(p)
			if !isKV || strings.TrimSpace(v) == "" {
				continue
			}
			sb.WriteString("- **")
			sb.WriteString(cleanLabel(k))
			sb.WriteString(":** ")
			sb.WriteString(inlineConvert(v))
			sb.WriteString("\n")
		}
		return sb.String()
	case classInline:
		return renderInline(inv)
	case classLocation:
		return renderNavi(inv.params)
	case classDrop:
		return ""
	case classParserFn, classUnknown:
		return "<!--template:" + escapeComment(inv.name) + "-->"
	}
	return ""
}

// entityArgRe parses "id=NNNN Display", "id=code Display", or bare display
// text. Whitespace around "=" and after the id is tolerated; display text
// may contain anything.
var entityIDRe = regexp.MustCompile(`^id\s*=\s*(\S+)\s*(.*)$`)
var numericIDRe = regexp.MustCompile(`^(\d+)\s+(.*)$`)

func renderEntity(kind string, params []string) string {
	if len(params) == 0 {
		return "<!--template:" + kind + "-->"
	}
	arg := cleanParam(params[0])
	id, display := "", arg
	if m := entityIDRe.FindStringSubmatch(arg); m != nil {
		id, display = m[1], m[2]
	} else if m := numericIDRe.FindStringSubmatch(arg); m != nil {
		id, display = m[1], m[2]
	}
	display = strings.TrimSpace(display)
	if display == "" {
		display = id
	}
	if id == "" {
		return display // no-id fallback: plain text
	}
	return "[" + escapeDisplay(display) + "](" + kind + ":" + escapeTarget(id) + ")"
}

func renderNavi(params []string) string {
	if len(params) < 3 {
		return "<!--template:navi-->"
	}
	m, x, y := cleanParam(params[0]), cleanParam(params[1]), cleanParam(params[2])
	return "[" + escapeDisplay(m+" "+x+"/"+y) + "](navi:" + escapeTarget(m) + ":" + x + ":" + y + ")"
}

func renderInline(inv invocation) string {
	switch inv.name {
	case "tooltip":
		if len(inv.params) == 0 {
			return ""
		}
		term := cleanParam(inv.params[0])
		if len(inv.params) > 1 {
			return term + " (" + cleanParam(inv.params[1]) + ")"
		}
		return term
	case "plainlink":
		// {{plainlink|url=URL label}}
		joined := strings.Join(inv.params, "|")
		m := regexp.MustCompile(`^url\s*=\s*(\S+)\s*(.*)$`).FindStringSubmatch(joined)
		if m == nil {
			return inlineConvert(joined)
		}
		label := strings.TrimSpace(m[2])
		if label == "" {
			label = m[1]
		}
		return "[" + escapeDisplay(label) + "](" + m[1] + ")"
	case "ucfirst":
		if len(inv.params) == 0 {
			return ""
		}
		r := []rune(cleanParam(inv.params[0]))
		if len(r) > 0 {
			r[0] = unicode.ToUpper(r[0])
		}
		return string(r)
	default: // rh, gr, st: passthrough of first param
		if len(inv.params) == 0 {
			return ""
		}
		return inlineConvert(cleanParam(inv.params[0]))
	}
}

// splitKV splits "key = value" once at the first "=".
func splitKV(p string) (string, string, bool) {
	i := strings.IndexByte(p, '=')
	if i < 0 {
		return "", "", false
	}
	return p[:i], p[i+1:], true
}

func cleanLabel(k string) string {
	k = strings.ReplaceAll(k, "_", " ")
	return strings.TrimSpace(k)
}

func escapeComment(s string) string {
	s = strings.ReplaceAll(s, "--", "- - ")
	return strings.ReplaceAll(s, ">", "")
}
