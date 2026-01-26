#!/bin/bash
# Full scrape with timing and monitoring

START_TIME=$(date +%s)
START_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== Full Scrape of iRO Wiki ===" | tee scrape_timing.log
echo "Start time: $START_DATETIME" | tee -a scrape_timing.log
echo "Rate limit: 1 req/sec" | tee -a scrape_timing.log
echo "Namespaces: 0-15 (all)" | tee -a scrape_timing.log
echo "" | tee -a scrape_timing.log

# Run scrape
python3 -m scraper full \
  --namespace 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 \
  --rate-limit 1 \
  --force 2>&1 | tee scrape.log

# Calculate timing
END_TIME=$(date +%s)
END_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_SECONDS=$((END_TIME - START_TIME))
HOURS=$((TOTAL_SECONDS / 3600))
MINUTES=$(((TOTAL_SECONDS % 3600) / 60))
SECONDS=$((TOTAL_SECONDS % 60))

echo "" | tee -a scrape_timing.log
echo "=== Scrape Completed ===" | tee -a scrape_timing.log
echo "End time: $END_DATETIME" | tee -a scrape_timing.log
echo "Total duration: ${HOURS}h ${MINUTES}m ${SECONDS}s (${TOTAL_SECONDS}s)" | tee -a scrape_timing.log
echo "" | tee -a scrape_timing.log

# Final statistics
if [[ -f data/irowiki.db ]]; then
  echo "=== Final Statistics ===" | tee -a scrape_timing.log
  PAGES=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages")
  REVISIONS=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM revisions")
  CONTENT_MB=$(sqlite3 data/irowiki.db "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions")
  DB_SIZE=$(du -h data/irowiki.db | cut -f1)
  
  echo "  Total pages: $PAGES" | tee -a scrape_timing.log
  echo "  Total revisions: $REVISIONS" | tee -a scrape_timing.log
  echo "  Content size: ${CONTENT_MB} MB" | tee -a scrape_timing.log
  echo "  Database size: $DB_SIZE" | tee -a scrape_timing.log
  
  # Performance metrics
  if [[ $TOTAL_SECONDS -gt 0 ]]; then
    PAGES_PER_HOUR=$(echo "scale=2; $PAGES * 3600 / $TOTAL_SECONDS" | bc)
    REVISIONS_PER_HOUR=$(echo "scale=2; $REVISIONS * 3600 / $TOTAL_SECONDS" | bc)
    AVG_REVS=$(echo "scale=2; $REVISIONS / $PAGES" | bc)
    
    echo "" | tee -a scrape_timing.log
    echo "=== Performance Metrics ===" | tee -a scrape_timing.log
    echo "  Pages/hour: $PAGES_PER_HOUR" | tee -a scrape_timing.log
    echo "  Revisions/hour: $REVISIONS_PER_HOUR" | tee -a scrape_timing.log
    echo "  Avg revisions/page: $AVG_REVS" | tee -a scrape_timing.log
  fi
fi

echo "" | tee -a scrape_timing.log
echo "Results saved to:"
echo "  - scrape.log (detailed output)"
echo "  - scrape_timing.log (timing summary)"
echo "  - data/irowiki.db (database)"
