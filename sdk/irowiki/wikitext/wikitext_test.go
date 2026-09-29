package wikitext

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var update = flag.Bool("update", false, "rewrite golden files")

func TestConvert_EntityTemplateVariants(t *testing.T) {
	cases := []struct{ in, want string }{
		{"{{monster|id=1002 Porings}}", "[Porings](monster:1002)"},
		{"{{monster | id=1012 Roda Frogs}}", "[Roda Frogs](monster:1012)"},
		{"{{Monster |id =1504 Dullahan}}", "[Dullahan](monster:1504)"},
		{"{{item | id=2304 Jacket<nowiki>[0]</nowiki>}}", "[Jacket\\[0\\]](item:2304)"},
		{"{{item|id=14459 iRO community headgear}}", "[iRO community headgear](item:14459)"},
		{"{{map | id=xmas Lutie}}", "[Lutie](map:xmas)"},
		{"{{card|1002 Poring Card}}", "[Poring Card](card:1002)"},
		{"{{skill|Alchemy}}", "Alchemy"}, // no-id fallback: plain text
	}
	for _, tc := range cases {
		got := strings.TrimSpace(Convert("T", tc.in).Markdown)
		if got != tc.want {
			t.Errorf("Convert(%q)\n got  %q\n want %q", tc.in, got, tc.want)
		}
	}
}

func TestConvert_Navi(t *testing.T) {
	got := strings.TrimSpace(Convert("T", "{{navi|prontera|154|185}}").Markdown)
	want := "[prontera 154/185](navi:prontera:154:185)"
	if got != want {
		t.Errorf("navi: got %q want %q", got, want)
	}
}

func TestConvert_UnknownAndParserFn(t *testing.T) {
	got := strings.TrimSpace(Convert("T", "{{expert}}").Markdown)
	if got != "<!--template:expert-->" {
		t.Errorf("unknown template: got %q", got)
	}
	got = strings.TrimSpace(Convert("T", "{{#if:x|y|z}}").Markdown)
	if got != "<!--template:#if-->" {
		t.Errorf("parser function: got %q", got)
	}
}

func TestConvert_Infobox(t *testing.T) {
	src := "{{Quest Info\n|levelreq = 50\n|partyreq = Party of 2+\n|items = none\n}}"
	doc := Convert("T", src)
	for _, want := range []string{"**levelreq:** 50", "**partyreq:** Party of 2+", "**items:** none"} {
		if !strings.Contains(doc.Markdown, want) {
			t.Errorf("infobox missing %q in:\n%s", want, doc.Markdown)
		}
	}
}

func TestConvert_EntityList(t *testing.T) {
	src := "{{item list\n|{{item|id=501 Red Potion}}\n|{{item|id=502 White Potion}}\n}}"
	doc := Convert("T", src)
	for _, want := range []string{"- [Red Potion](item:501)", "- [White Potion](item:502)"} {
		if !strings.Contains(doc.Markdown, want) {
			t.Errorf("entity list missing %q in:\n%s", want, doc.Markdown)
		}
	}
}

func TestConvert_WikiLinksAndFragments(t *testing.T) {
	cases := []struct{ in, want string }{
		{"[[Stats#AGI|AGI]]", "[AGI](wiki:Stats)"},
		{"[[Prontera]]", "[Prontera](wiki:Prontera)"},
		{"[[Zeny]]", "[Zeny](wiki:Zeny)"},
		{"[[File:Example.png]]", ""},
		{"[https://irowiki.org iRO Wiki]", "[iRO Wiki](https://irowiki.org)"},
	}
	for _, tc := range cases {
		got := strings.TrimSpace(Convert("T", tc.in).Markdown)
		if got != tc.want {
			t.Errorf("Convert(%q): got %q want %q", tc.in, got, tc.want)
		}
	}
}

func TestConvert_TableSpanFlattening(t *testing.T) {
	src := `{| class="wikitable"
|+ Damage table
|-
! Weapon !! rowspan="2" |vs Poring
|-
| Falchion || 120
|-
| colspan="2" | Total row
|}`
	doc := Convert("T", src)
	md := doc.Markdown
	for _, want := range []string{"| --- | --- |", "vs Poring", "Falchion", "Total row | Total row"} {
		if !strings.Contains(md, want) {
			t.Errorf("table missing %q in:\n%s", want, md)
		}
	}
}

func TestConvert_SectionsAndAnchors(t *testing.T) {
	src := "Intro text.\n== Overview ==\nFirst.\n== Notes ==\nA.\n== Notes ==\nB."
	doc := Convert("T", src)
	if len(doc.Sections) != 4 {
		t.Fatalf("expected 4 sections, got %d: %+v", len(doc.Sections), doc.Sections)
	}
	anchors := map[string]bool{}
	for _, s := range doc.Sections {
		anchors[s.Anchor] = true
	}
	if !anchors["overview"] || !anchors["notes"] || !anchors["notes-2"] {
		t.Errorf("anchor dedup failed: %+v", doc.Sections)
	}
	if doc.Sections[1].Level != 1 {
		t.Errorf("expected level 1 heading, got %d", doc.Sections[1].Level)
	}
}

func TestConvert_RedirectDocument(t *testing.T) {
	doc := Convert("Monsters", "#REDIRECT [[Monster]]")
	if doc.Redirect != "Monster" {
		t.Errorf("expected redirect target 'Monster', got %q", doc.Redirect)
	}
	if doc.Markdown != "→ [Monster](wiki:Monster)" {
		t.Errorf("unexpected redirect markdown: %q", doc.Markdown)
	}
}

func TestConvert_Deterministic(t *testing.T) {
	src, _ := os.ReadFile("testdata/poringwar.wiki")
	a := Convert("Poring War", string(src))
	b := Convert("Poring War", string(src))
	if a.Markdown != b.Markdown || len(a.Sections) != len(b.Sections) {
		t.Error("conversion is not deterministic")
	}
	for i := range a.Sections {
		if a.Sections[i] != b.Sections[i] {
			t.Errorf("section %d differs between runs", i)
		}
	}
}

func TestGoldenFiles(t *testing.T) {
	files, err := filepath.Glob("testdata/*.wiki")
	if err != nil || len(files) == 0 {
		t.Fatalf("no fixtures: %v", err)
	}
	for _, f := range files {
		name := strings.TrimSuffix(filepath.Base(f), ".wiki")
		t.Run(name, func(t *testing.T) {
			src, err := os.ReadFile(f)
			if err != nil {
				t.Fatal(err)
			}
			goldenPath := strings.TrimSuffix(f, ".wiki") + ".golden.md"
			got := Convert(name, string(src))
			if *update {
				if err := os.WriteFile(goldenPath, []byte(got.Markdown), 0o644); err != nil {
					t.Fatal(err)
				}
				return
			}
			golden, err := os.ReadFile(goldenPath)
			if os.IsNotExist(err) {
				t.Fatalf("golden file missing: %s (regenerate with -update)", goldenPath)
			}
			if err != nil {
				t.Fatal(err)
			}
			if got.Markdown != string(golden) {
				t.Errorf("output diverges from golden %s\ngot:\n%s\nwant:\n%s", goldenPath, got.Markdown, golden)
			}
		})
	}
}
