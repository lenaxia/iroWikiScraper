#!/bin/bash
# Monitor scrape progress and track timing

SCRAPE_LOG="scrape.log"
START_TIME=$(date +%s)
START_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== Full Scrape Started ===" | tee -a scrape_timing.log
echo "Start time: $START_DATETIME" | tee -a scrape_timing.log
echo "Database: data/irowiki.db" | tee -a scrape_timing.log
echo "" | tee -a scrape_timing.log

# Start the scrape in background
nohup python3 -m scraper full \
  --namespace 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 \
  --rate-limit 1 \
  --force \
  > "$SCRAPE_LOG" 2>&1 &

SCRAPE_PID=$!
echo "Scrape PID: $SCRAPE_PID" | tee -a scrape_timing.log
echo "" | tee -a scrape_timing.log

# Monitor progress
echo "Monitoring progress (Ctrl+C to stop monitoring, scrape continues)..."
echo "Log file: $SCRAPE_LOG"
echo ""

# Function to show stats
show_stats() {
  if [[ -f data/irowiki.db ]]; then
    PAGES=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages" 2>/dev/null || echo "0")
    REVISIONS=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM revisions" 2>/dev/null || echo "0")
    CONTENT_MB=$(sqlite3 data/irowiki.db "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions" 2>/dev/null || echo "0")
    
    ELAPSED=$(($(date +%s) - START_TIME))
    HOURS=$((ELAPSED / 3600))
    MINUTES=$(((ELAPSED % 3600) / 60))
    
    echo "[$HOURS:$(printf '%02d' $MINUTES)] Pages: $PAGES | Revisions: $REVISIONS | Content: ${CONTENT_MB}MB"
  fi
}

# Monitor loop
while kill -0 $SCRAPE_PID 2>/dev/null; do
  sleep 60
  show_stats
done

# Scrape completed
END_TIME=$(date +%s)
END_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_SECONDS=$((END_TIME - START_TIME))
TOTAL_HOURS=$((TOTAL_SECONDS / 3600))
TOTAL_MINUTES=$(((TOTAL_SECONDS % 3600) / 60))
TOTAL_SECS=$((TOTAL_SECONDS % 60))

echo "" | tee -a scrape_timing.log
echo "=== Scrape Completed ===" | tee -a scrape_timing.log
echo "End time: $END_DATETIME" | tee -a scrape_timing.log
echo "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m ${TOTAL_SECS}s" | tee -a scrape_timing.log
echo "" | tee -a scrape_timing.log

# Final stats
if [[ -f data/irowiki.db ]]; then
  echo "=== Final Statistics ===" | tee -a scrape_timing.log
  PAGES=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM pages")
  REVISIONS=$(sqlite3 data/irowiki.db "SELECT COUNT(*) FROM revisions")
  CONTENT_MB=$(sqlite3 data/irowiki.db "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions")
  DB_SIZE=$(du -h data/irowiki.db | cut -f1)
  
  echo "  Pages: $PAGES" | tee -a scrape_timing.log
  echo "  Revisions: $REVISIONS" | tee -a scrape_timing.log
  echo "  Content: ${CONTENT_MB} MB" | tee -a scrape_timing.log
  echo "  Database size: $DB_SIZE" | tee -a scrape_timing.log
  echo "" | tee -a scrape_timing.log
  
  # Calculate rates
  PAGES_PER_HOUR=$((PAGES * 3600 / TOTAL_SECONDS))
  REVISIONS_PER_HOUR=$((REVISIONS * 3600 / TOTAL_SECONDS))
  
  echo "=== Performance ===" | tee -a scrape_timing.log
  echo "  Pages/hour: $PAGES_PER_HOUR" | tee -a scrape_timing.log
  echo "  Revisions/hour: $REVISIONS_PER_HOUR" | tee -a scrape_timing.log
  echo "  Average revisions per page: $((REVISIONS / PAGES))" | tee -a scrape_timing.log
fi

echo "" | tee -a scrape_timing.log
echo "Check scrape.log for detailed output"
echo "Timing logged to scrape_timing.log"
