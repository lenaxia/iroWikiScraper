package irowiki

import "testing"

func TestNormalizeTitle(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{"Main_Page", "Main Page"},
		{"  Poring  ", "Poring"},
		{"Prontera#Central Plaza", "Prontera"},
		{"Equipment_Sets.26Extras", "Equipment Sets&Extras"},
		{"a.2Fb", "a/b"},
		{"Multiple   Spaces", "Multiple Spaces"},
		{"", ""},
	}
	for _, tc := range cases {
		if got := normalizeTitle(tc.in); got != tc.want {
			t.Errorf("normalizeTitle(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestParseRedirectTarget(t *testing.T) {
	cases := []struct {
		content    string
		wantTarget string
		wantOK     bool
	}{
		{"#REDIRECT [[Main Page]]", "Main Page", true},
		{"#redirect [[Main Page]]", "Main Page", true},
		{"#REDIRECT: [[Main Page]]", "Main Page", true},
		{"  #REDIRECT [[Target|display label]]", "Target", true},
		{"#REDIRECT [[Prontera#Central Plaza]]", "Prontera#Central Plaza", true},
		{"Some content\n#REDIRECT [[X]]", "", false},
		{"REDIRECT [[X]]", "", false}, // missing '#' is not a redirect
		{"#REDIRECT [[ ]]", "", false},
		{"", "", false},
	}
	for _, tc := range cases {
		target, ok := parseRedirectTarget(tc.content)
		if ok != tc.wantOK || (ok && target != tc.wantTarget) {
			t.Errorf("parseRedirectTarget(%q) = (%q, %v), want (%q, %v)",
				tc.content, target, ok, tc.wantTarget, tc.wantOK)
		}
	}
}

func TestTitleCandidates(t *testing.T) {
	got := titleCandidates("main page")
	want := []string{"Main page", "main page", "Main_page", "main_page"}
	if len(got) != len(want) {
		t.Fatalf("expected %d candidates, got %d: %v", len(want), len(got), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("candidate[%d] = %q, want %q", i, got[i], want[i])
		}
	}
	if titleCandidates("") != nil {
		t.Error("expected nil candidates for empty title")
	}
}
