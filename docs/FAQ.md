# FAQ

Frequently asked questions about the iRO Wiki Scraper.

## How long does a full scrape take?

A full scrape of all standard namespaces takes roughly 3 hours at the
default rate limit (about 1 request per second, 2 req/s with
`--rate-limit 2`). Discovery is fast (a few dozen requests); the duration
is dominated by fetching every revision with content. Use
`python -m scraper full --dry-run` to estimate the scope for your
namespace selection before committing.

## How much disk space is needed?

The SQLite archive for a full scrape is currently ~1.2 GB, plus media
files if downloads are enabled (several GB). The MediaWiki XML export
adds roughly the size of the database again. Budget ~10 GB for a full
archive including images; database-only setups need ~3 GB.

## What if the scrape is interrupted?

Interrupted scrapes are resumable. The scraper writes a checkpoint file
(`data/.checkpoint.json` by default) tracking completed namespaces and
pages. Re-run the same command with `--resume` (or answer the prompt) to
continue from the checkpoint instead of starting over.

## Can I resume a failed scrape?

Yes. Pages that failed during a run are recorded in the checkpoint; use
`python -m scraper full --resume` to retry them, or `python -m scraper
backfill --pages` to fill gaps left by earlier runs.

## How do I control the rate limit?

The scraper defaults to 2 requests per second. Lower it for a gentler
pace (`--rate-limit 1` or one request every two seconds with
`--rate-limit 0.5`), or set `scraper.rate_limit` in the config file. The
client backs off automatically on HTTP 429 responses.

## What namespaces can I scrape?

All standard MediaWiki namespaces (0-15: Main, Talk, User, Project,
File, MediaWiki, Template, Help, Category and their talk pages). Select
subsets with `--namespace 0 4 6`; the default full scrape covers 0-15.

## What do the monthly release archives contain?

Each release ships the SQLite database post-processed before packaging:

- `pages.is_redirect` is populated from the latest revision content
  (`#REDIRECT` / `#WEITERLEITUNG` prefix), so redirect-based filtering
  (e.g. the Go SDK's `OnlyRedirects` / `ExcludeRedirects` search options)
  works out of the box.
- `pages_md` / `pages_md_fts` are materialized for namespace 0 (Main)
  via `sdk/cmd/materialize`: per-page-section markdown plus a full-text
  search index, ready to query with no local build step.

Media files and the MediaWiki XML export are packaged alongside the
database when present.

## The redirect flags in my old archive are all zero. Can I fix that?

Yes. Archives scraped before September 2026 never populated
`pages.is_redirect`. Repair them offline (no network access needed)
against the existing database:

```bash
python -m scraper backfill --no-failed-pages --no-links --no-files
```

This recomputes the flag for every page from its stored latest revision
and only writes rows whose flag actually changes.
