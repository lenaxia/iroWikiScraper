package irowiki_test

import (
	"context"
	"errors"
	"testing"

	irowiki "github.com/lenaxia/iroWikiScraper/sdk/irowiki"
	"github.com/lenaxia/iroWikiScraper/sdk/internal/testutil"
)

func TestSQLiteClient_ResolveRedirect(t *testing.T) {
	tdb := testutil.SetupTestDBFile(t)
	defer tdb.Close()

	client, err := irowiki.OpenSQLite(tdb.Path)
	if err != nil {
		t.Fatalf("failed to open client: %v", err)
	}
	defer client.Close()

	ctx := context.Background()

	t.Run("non-redirect returns canonical title", func(t *testing.T) {
		title, err := client.ResolveRedirect(ctx, "Poring")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if title != "Poring" {
			t.Errorf("expected canonical 'Poring', got %q", title)
		}
	})

	t.Run("underscore and first-letter case normalization", func(t *testing.T) {
		// MediaWiki folds only the first character; "main_Page" matches the
		// stored "Main_Page" via first-letter casefolding. Interior case
		// differences ("Main_page") are a genuine no-match, as on the live wiki.
		title, err := client.ResolveRedirect(ctx, "main_Page")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if title != "Main_Page" {
			t.Errorf("expected canonical 'Main_Page', got %q", title)
		}
	})

	t.Run("non-first-letter case differences do not match", func(t *testing.T) {
		// MediaWiki titles are case-sensitive after the first character,
		// so "main page" must not resolve to "Main_Page".
		if _, err := client.ResolveRedirect(ctx, "main page"); err != irowiki.ErrNotFound {
			t.Errorf("expected ErrNotFound for case-mismatched title, got %v", err)
		}
	})

	t.Run("simple redirect follows to target", func(t *testing.T) {
		title, err := client.ResolveRedirect(ctx, "Redirect_Test")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if title != "Main_Page" {
			t.Errorf("expected 'Main_Page', got %q", title)
		}
	})

	t.Run("redirect chain follows to end", func(t *testing.T) {
		title, err := client.ResolveRedirect(ctx, "Chain_Start")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if title != "Poring" {
			t.Errorf("expected 'Poring', got %q", title)
		}
	})

	t.Run("fragment anchor is stripped", func(t *testing.T) {
		title, err := client.ResolveRedirect(ctx, "Frag_Redirect")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if title != "Prontera" {
			t.Errorf("expected 'Prontera', got %q", title)
		}
	})

	t.Run("redirect loop returns ErrRedirectLoop", func(t *testing.T) {
		_, err := client.ResolveRedirect(ctx, "Loop_A")
		if !errors.Is(err, irowiki.ErrRedirectLoop) {
			t.Errorf("expected ErrRedirectLoop, got %v", err)
		}
	})

	t.Run("missing title returns ErrNotFound", func(t *testing.T) {
		_, err := client.ResolveRedirect(ctx, "Does_Not_Exist")
		if err != irowiki.ErrNotFound {
			t.Errorf("expected ErrNotFound, got %v", err)
		}
	})
}
