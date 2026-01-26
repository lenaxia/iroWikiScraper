# Local Scraping Workflow

Since irowiki.org blocks GitHub Actions IP addresses, the recommended workflow is to run scrapes locally and publish releases manually.

## What Gets Scraped

### ✅ Included by Default
- **Page content** - All wiki pages and revision history
- **File metadata** - Filenames, URLs, sizes, dimensions, upload dates
- **Links** - Internal page links and references
- **Users** - Contributor information

### ⚠️ Images (Optional)
By default, only image **metadata** is scraped (URLs, sizes, etc.), not the actual image files.

**Why?** 
- Keeps database small (50-200 MB vs 500 MB - 5+ GB)
- Faster scraping
- Users can fetch images on-demand from URLs

**To download images:**
```bash
# After scraping, download all images
./scripts/download-images.sh

# Or only specific types
./scripts/download-images.sh --mime-type 'image/png' --max-size 5
```

See [Image Download Options](#image-download-options) below for details.

## Quick Start

### Initial Full Scrape

```bash
# Full scrape of all namespaces (will take several hours)
./scripts/local-scrape-and-release.sh --rate-limit 1

# Or scrape specific namespaces only
./scripts/local-scrape-and-release.sh --namespaces "0 4 6"
```

### Create GitHub Release

```bash
# After scraping, create a release
./scripts/local-scrape-and-release.sh --release

# Or do both in one command
./scripts/local-scrape-and-release.sh --rate-limit 1 --release
```

### Monthly Updates

```bash
# Run incremental update and publish
./scripts/local-scrape-and-release.sh --incremental --release
```

## Estimated Times

Based on ~4,000 pages in namespace 0:

- **Full scrape (all namespaces)**: 8-12 hours
- **Single namespace**: 1-2 hours  
- **Incremental update**: 10-30 minutes

Times depend on:
- Number of pages
- Revision history depth
- Rate limiting (default: 1 req/sec)
- Network speed

## Storage Requirements

- **Database**: 50-200 MB (compressed: 10-40 MB)
- **With images**: 500 MB - 5 GB additional
- **Git repository**: Keep under 100 MB

## Process Details

### What the Script Does

1. **Scrape**: Runs the scraper with checkpoint/resume
2. **Statistics**: Generates page/revision counts
3. **Package**: Creates compressed `.tar.gz` archive
4. **Release**: (optional) Creates GitHub release with artifact

### Checkpoint & Resume

The scraper automatically saves progress to `data/.checkpoint.json`:

```bash
# Resume interrupted scrape
python -m scraper full --resume

# Start fresh (ignore checkpoint)
python -m scraper full --no-resume

# Clean checkpoint and exit
python -m scraper full --clean
```

### Manual Release Process

If you prefer manual control:

```bash
# 1. Scrape locally
python -m scraper full --rate-limit 1 --resume

# 2. Package database
cd data
tar -czf irowiki-database-$(date +%Y-%m-%d).tar.gz irowiki.db
cd ..

# 3. Create release
git tag -a v$(date +%Y-%m-%d) -m "Snapshot $(date +%Y-%m-%d)"
git push origin v$(date +%Y-%m-%d)

gh release create v$(date +%Y-%m-%d) \
  data/irowiki-database-$(date +%Y-%m-%d).tar.gz \
  --title "iRO Wiki Archive - $(date +%Y-%m-%d)" \
  --notes "Complete wiki snapshot"
```

## Rate Limiting

Be respectful to the wiki server:

```bash
# Conservative (recommended for first run)
--rate-limit 1    # 1 request per second

# Moderate (if server handles it well)
--rate-limit 2    # 2 requests per second

# Aggressive (only if approved by wiki admins)
--rate-limit 5    # 5 requests per second
```

Monitor the scraper output for errors or warnings about rate limiting.

## Alternative: CI/CD on Other Platforms

If you want automated monthly scrapes, consider:

### Self-Hosted GitHub Runner
```yaml
# .github/workflows/monthly-scrape-selfhosted.yml
jobs:
  scrape:
    runs-on: self-hosted  # Your own machine
```

### DigitalOcean, AWS, Azure
- Set up a VM with the scraper
- Run as cron job: `0 0 1 * * /path/to/local-scrape-and-release.sh --incremental --release`
- Different IP range may not be blocked

### Ask Wiki Admins
Contact irowiki.org administrators:
- Explain you're creating a public archive
- Request API key or IP whitelisting
- Offer to donate/support their hosting

## Troubleshooting

### Scrape Interrupted

```bash
# Just run again with --resume
./scripts/local-scrape-and-release.sh --resume
```

### Database Corrupt

```bash
# Start fresh
rm data/irowiki.db data/.checkpoint.json
./scripts/local-scrape-and-release.sh
```

### Rate Limited (HTTP 429)

```bash
# Reduce rate limit
./scripts/local-scrape-and-release.sh --rate-limit 0.5
```

### Out of Disk Space

```bash
# Check database size
du -h data/irowiki.db

# Vacuum database to reclaim space
sqlite3 data/irowiki.db "VACUUM;"
```

## Image Download Options

### Option 1: Metadata Only (Default) ⭐ Recommended

**What you get:**
- File URLs, sizes, dimensions, SHA1 hashes
- Users can fetch images on-demand from irowiki.org
- Database: ~50-200 MB

**Good for:**
- Most users who just need text content
- Quick scrapes and small releases
- When disk space is limited

**Usage:** Just run the normal scrape - metadata is included automatically.

### Option 2: Download All Images

**What you get:**
- Complete offline archive
- All images preserved even if wiki goes down
- Database: ~50-200 MB + Images: ~500 MB - 5+ GB

**Good for:**
- Complete archival
- Offline mirrors
- When you need guaranteed access

**Usage:**
```bash
# 1. Scrape wiki (gets metadata)
./scripts/local-scrape-and-release.sh

# 2. Download all images
./scripts/download-images.sh

# 3. Package everything
cd data
tar -czf irowiki-images-$(date +%Y-%m-%d).tar.gz images/

# 4. Create separate release for images (optional)
gh release upload v$(date +%Y-%m-%d) irowiki-images-$(date +%Y-%m-%d).tar.gz
```

### Option 3: Selective Download

**Download only specific images:**

```bash
# Only PNG images under 5MB
./scripts/download-images.sh --mime-type 'image/png' --max-size 5

# Only game item images (would need custom filter)
sqlite3 data/irowiki.db "SELECT filename FROM files WHERE filename LIKE '%Item%'" | \
  while read f; do wget -P data/images/ "$(sqlite3 data/irowiki.db "SELECT url FROM files WHERE filename='$f'")"; done
```

### Image Storage Options

**GitHub Releases:**
- Pros: Free, integrated with repo
- Cons: 2GB limit per file, 10GB per release
- Best for: Metadata-only or small image sets

**External Storage:**
- Pros: Unlimited size, CDN support
- Cons: Costs money, separate infrastructure
- Options: AWS S3, Backblaze B2, DigitalOcean Spaces
- Best for: Complete archives with many images

**Torrent:**
- Pros: Distributed, no hosting costs
- Cons: Requires seeders, complex setup
- Best for: Large community-driven archives

## Next Steps

After your first successful scrape and release:

1. **Test the SDK** - Try querying your database with the Go SDK
2. **Schedule updates** - Set up monthly incremental scrapes
3. **Document usage** - Add examples to README showing users how to download and use
4. **Monitor size** - Track database growth over time
5. **Consider images** - Decide if you want to archive image files too

## Questions?

- Check main README.md for scraper documentation
- See SDK documentation for query examples
- Open an issue for problems or feature requests
