// Command materialize converts the latest revision of every page in the
// selected namespaces of an archive database to deterministic markdown
// (wikitext converter) and stores the result in pages_md / pages_md_fts.
//
// Usage:
//
//	go run ./cmd/materialize -db path/to/irowiki.db [-namespace 0,4] [-limit N]
//
// The command is idempotent: it rebuilds pages_md from scratch each run.
// Raw wikitext remains authoritative; markdown is derived data.
package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"log"
	"sort"
	"strings"
	"time"

	"github.com/lenaxia/iroWikiScraper/sdk/irowiki/wikitext"
	_ "modernc.org/sqlite"
)

func main() {
	dbPath := flag.String("db", "data/irowiki.db", "path to the archive SQLite database")
	namespacesFlag := flag.String("namespace", "0", "comma-separated namespaces to materialize (default: 0 = Main)")
	limit := flag.Int("limit", 0, "materialize at most N pages (0 = all, for smoke tests)")
	flag.Parse()

	if *dbPath == "" {
		log.Fatal("--db is required")
	}
	namespaces, err := parseIntList(*namespacesFlag)
	if err != nil {
		log.Fatalf("--namespace: %v", err)
	}

	db, err := sql.Open("sqlite", *dbPath)
	if err != nil {
		log.Fatalf("open database: %v", err)
	}
	defer db.Close()

	if err := run(context.Background(), db, namespaces, *limit); err != nil {
		log.Fatal(err)
	}
}

func run(ctx context.Context, db *sql.DB, namespaces []int, limit int) error {
	if _, err := db.ExecContext(ctx, `
		DROP TABLE IF EXISTS pages_md;
		DROP TABLE IF EXISTS pages_md_fts;
		CREATE TABLE pages_md (
			page_id  INTEGER NOT NULL,
			anchor   TEXT    NOT NULL,
			heading  TEXT    NOT NULL DEFAULT '',
			level    INTEGER NOT NULL DEFAULT 0,
			markdown TEXT    NOT NULL,
			PRIMARY KEY (page_id, anchor)
		) WITHOUT ROWID;
		CREATE VIRTUAL TABLE pages_md_fts USING fts5(
			markdown, page_id UNINDEXED, anchor UNINDEXED
		);
	`); err != nil {
		return fmt.Errorf("create schema: %w", err)
	}

	nsFilter := make([]string, len(namespaces))
	args := make([]any, len(namespaces))
	for i, ns := range namespaces {
		nsFilter[i] = "?"
		args[i] = ns
	}
	query := fmt.Sprintf(`
		SELECT p.page_id, p.title, r.content, r.timestamp
		FROM revisions r
		JOIN pages p ON p.page_id = r.page_id
		JOIN (
			SELECT page_id, MAX(timestamp) AS mt
			FROM revisions GROUP BY page_id
		) lr ON lr.page_id = r.page_id AND lr.mt = r.timestamp
		WHERE p.namespace IN (%s)
		ORDER BY p.page_id
	`, strings.Join(nsFilter, ","))
	if limit > 0 {
		query += " LIMIT ?"
		args = append(args, limit)
	}

	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("select latest revisions: %w", err)
	}
	defer rows.Close()

	type pending struct {
		pageID          int64
		anchor, heading string
		level           int
		markdown        string
	}
	var batch []pending
	pages, sections, redirects := 0, 0, 0
	watermark := time.Time{}

	flush := func() error {
		if len(batch) == 0 {
			return nil
		}
		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		insertMD, err := tx.PrepareContext(ctx,
			"INSERT INTO pages_md (page_id, anchor, heading, level, markdown) VALUES (?, ?, ?, ?, ?)")
		if err != nil {
			tx.Rollback()
			return err
		}
		insertFTS, err := tx.PrepareContext(ctx,
			"INSERT INTO pages_md_fts (markdown, page_id, anchor) VALUES (?, ?, ?)")
		if err != nil {
			tx.Rollback()
			return err
		}
		for _, p := range batch {
			if _, err := insertMD.ExecContext(ctx, p.pageID, p.anchor, p.heading, p.level, p.markdown); err != nil {
				tx.Rollback()
				return err
			}
			if _, err := insertFTS.ExecContext(ctx, p.markdown, p.pageID, p.anchor); err != nil {
				tx.Rollback()
				return err
			}
		}
		batch = batch[:0]
		return tx.Commit()
	}

	for rows.Next() {
		var pageID int64
		var title, content string
		var ts time.Time
		if err := rows.Scan(&pageID, &title, &content, &ts); err != nil {
			return fmt.Errorf("scan row: %w", err)
		}
		doc := wikitext.Convert(title, content)
		if doc.Redirect != "" {
			redirects++
		} else {
			pages++
		}
		sections += len(doc.Sections)
		for _, sec := range doc.Sections {
			batch = append(batch, pending{
				pageID: pageID, anchor: sec.Anchor, heading: sec.Heading,
				level: sec.Level, markdown: sec.Markdown,
			})
		}
		if ts.After(watermark) {
			watermark = ts
		}
		if len(batch) >= 500 {
			if err := flush(); err != nil {
				return fmt.Errorf("flush batch: %w", err)
			}
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}
	if err := flush(); err != nil {
		return err
	}

	// Deterministic meta row.
	if _, err := db.ExecContext(ctx, `
		CREATE TABLE IF NOT EXISTS materialization_meta (
			converter_version TEXT NOT NULL,
			watermark         TEXT NOT NULL,
			run_at            TEXT NOT NULL,
			namespaces        TEXT NOT NULL
		);
		DELETE FROM materialization_meta;
		INSERT INTO materialization_meta VALUES (?, ?, ?, ?);
	`, wikitext.Version, watermark.UTC().Format(time.RFC3339),
		time.Now().UTC().Format(time.RFC3339), intSliceString(namespaces)); err != nil {
		return fmt.Errorf("write meta: %w", err)
	}

	fmt.Printf("materialized %d pages (%d redirects) / %d sections with converter %s; watermark %s\n",
		pages, redirects, sections, wikitext.Version, watermark.UTC().Format(time.RFC3339))
	return nil
}

func parseIntList(s string) ([]int, error) {
	var out []int
	for _, part := range strings.Split(s, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		n := 0
		ok := part[0] >= '0' && part[0] <= '9'
		for _, ch := range part {
			if ch < '0' || ch > '9' {
				ok = false
				break
			}
			n = n*10 + int(ch-'0')
		}
		if !ok {
			return nil, fmt.Errorf("invalid namespace %q", part)
		}
		out = append(out, n)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("at least one namespace required")
	}
	return out, nil
}

func intSliceString(ns []int) string {
	sorted := append([]int(nil), ns...)
	sort.Ints(sorted)
	parts := make([]string, len(sorted))
	for i, n := range sorted {
		parts[i] = fmt.Sprint(n)
	}
	return strings.Join(parts, ",")
}
