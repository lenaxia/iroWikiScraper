// Package wikitext converts MediaWiki wikitext into deterministic,
// entity-annotated markdown for LLM and programmatic consumption.
//
// The converter is tokenizer-based rather than regex-based: template
// invocations are found with a balanced-brace scanner and their parameters
// split at top-level pipes, which is required by the real archive content
// (whitespace-laden forms like "{{monster | id=1012 Roda Frogs}}",
// <nowiki> fragments inside parameters, and nested invocations all defeat
// naive regular expressions).
//
// Determinism rules (issue #11): input is Unicode NFC-normalized, output
// serialization never depends on map iteration order, and the converter
// version is available as wikitext.Version for archive materialization
// metadata. Identical input always produces identical output.
//
// Template rendering follows a class table. Semantic entity templates
// become structured markers preserving the entity id:
//
//	{{monster | id=1002 Porings}}  ->  [Porings](monster:1002)
//	{{item|id=2304 Jacket[0]}}     ->  [Jacket\[0\]](item:2304)
//	{{navi|prontera|154|185}}      ->  [prontera 154/185](navi:prontera:154:185)
//
// Full MediaWiki template rendering is impossible offline; parser functions
// and unknown templates collapse to "<!--template:name-->" markers rather
// than being silently dropped.
package wikitext

// Version is the converter version. Archives materialized with different
// versions must not be diffed against each other without re-materialization.
const Version = "1.0.0"
