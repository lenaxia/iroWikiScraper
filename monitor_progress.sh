#!/bin/bash
# Continuous monitoring script

DB_PATH="data/irowiki.db"
START_TIME=$(date -d "2026-01-25 23:19:28" +%s 2>/dev/null || date -j -f "%Y-%m-%d %H:%M:%S" "2026-01-25 23:19:28" +%s)

echo "=== iRO Wiki Scrape Monitor ==="
echo "Started: 2026-01-25 23:19:28 UTC"
echo "Press Ctrl+C to exit (scrape will continue)"
echo ""

LAST_REVS=0
LAST_CHECK=$(date +%s)

while pgrep -f "python3 -m scraper" > /dev/null; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    HOURS=$((ELAPSED / 3600))
    MINUTES=$(((ELAPSED % 3600) / 60))
    
    if [[ -f "$DB_PATH" ]]; then
        PAGES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pages" 2>/dev/null || echo "0")
        REVISIONS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM revisions" 2>/dev/null || echo "0")
        CONTENT_MB=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(LENGTH(content))/1024.0/1024.0, 2) FROM revisions" 2>/dev/null || echo "0")
        
        # Calculate rate
        TIME_SINCE_LAST=$((CURRENT_TIME - LAST_CHECK))
        if [[ $TIME_SINCE_LAST -gt 0 ]]; then
            REVS_DELTA=$((REVISIONS - LAST_REVS))
            REVS_PER_MIN=$(echo "scale=1; $REVS_DELTA * 60 / $TIME_SINCE_LAST" | bc 2>/dev/null || echo "0")
        else
            REVS_PER_MIN="0"
        fi
        
        LAST_REVS=$REVISIONS
        LAST_CHECK=$CURRENT_TIME
        
        # Calculate percentage (approximate)
        TOTAL_PAGES=10516
        if [[ $ELAPSED -gt 0 ]]; then
            REVS_PER_HOUR=$(echo "scale=0; $REVISIONS * 3600 / $ELAPSED" | bc 2>/dev/null || echo "0")
            
            # Estimate total revisions (conservative: 15 per page average)
            ESTIMATED_TOTAL_REVS=$((TOTAL_PAGES * 15))
            PERCENT_COMPLETE=$(echo "scale=1; $REVISIONS * 100 / $ESTIMATED_TOTAL_REVS" | bc 2>/dev/null || echo "0")
            
            # Estimate time remaining
            REVS_REMAINING=$((ESTIMATED_TOTAL_REVS - REVISIONS))
            if [[ $REVS_PER_HOUR -gt 0 ]]; then
                HOURS_REMAINING=$(echo "scale=1; $REVS_REMAINING / $REVS_PER_HOUR" | bc 2>/dev/null || echo "?")
            else
                HOURS_REMAINING="?"
            fi
        else
            REVS_PER_HOUR=0
            PERCENT_COMPLETE="0"
            HOURS_REMAINING="?"
        fi
        
        clear
        echo "=== iRO Wiki Scrape Monitor ==="
        echo "Started: 2026-01-25 23:19:28 UTC"
        echo "Elapsed: ${HOURS}h ${MINUTES}m"
        echo ""
        echo "Progress:"
        echo "  Pages: $PAGES / $TOTAL_PAGES"
        echo "  Revisions: $REVISIONS (~${PERCENT_COMPLETE}% estimated)"
        echo "  Content: ${CONTENT_MB} MB"
        echo ""
        echo "Performance:"
        echo "  Rate: ${REVS_PER_MIN} revisions/min (${REVS_PER_HOUR}/hour)"
        echo "  Est. remaining: ${HOURS_REMAINING} hours"
        echo ""
        echo "Last updated: $(date '+%H:%M:%S')"
        echo "Press Ctrl+C to exit (scrape continues in background)"
    fi
    
    sleep 60
done

echo ""
echo "=== Scrape Complete! ==="
echo "Run ./check_and_release.sh to create GitHub release"
