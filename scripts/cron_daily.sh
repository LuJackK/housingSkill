#!/bin/bash
# Daily housing pipeline: scrape → enrich → score → analyze (LLM) → PDF → deliver
set -e

# Set up PATH for nvm/openclaw
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/.nvm/versions/node/v24.14.0/bin:$PATH"

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
HOUSING_DIR="$(dirname "$SCRIPTS_DIR")"
WORKSPACE="$(dirname "$HOUSING_DIR")"

cd "$WORKSPACE"
TODAY=$(date +%Y-%m-%d)
LOG="$HOUSING_DIR/logs/cron.log"
INQUIRIES=("summer-1p" "school-year-4p")

echo "=== Housing cron: $TODAY ===" >> "$LOG"

# Step 1: Scrape + enrich
echo "[$(date +%H:%M)] Scraping and enriching..." >> "$LOG"
python3 "$SCRIPTS_DIR/enrich.py" >> "$LOG" 2>&1

# Step 2: Pre-filter and score (programmatic, fast)
echo "[$(date +%H:%M)] Pre-filtering and scoring..." >> "$LOG"
python3 "$SCRIPTS_DIR/score.py" >> "$LOG" 2>&1

# Step 3: Trigger agent analysis (handles both inquiries in one run)
echo "[$(date +%H:%M)] Triggering LLM analysis..." >> "$LOG"
ANALYSIS_CRON_ID="8f14aa8e-d0b4-47a1-94ef-0b9ac431717e"
openclaw cron run "$ANALYSIS_CRON_ID" >> "$LOG" 2>&1 || echo "WARNING: Cron trigger may have failed" >> "$LOG"

# Step 4: Wait for analysis files (up to 20 minutes for both inquiries)
echo "[$(date +%H:%M)] Waiting for analysis files..." >> "$LOG"
ALL_READY=true
for inquiry in "${INQUIRIES[@]}"; do
    ANALYSIS_FILE="$HOUSING_DIR/reports/analysis_${inquiry}_${TODAY}.json"
    READY=false
    for i in $(seq 1 120); do
        if [ -f "$ANALYSIS_FILE" ]; then
            echo "[$(date +%H:%M)] $inquiry analysis ready after ${i}0 seconds" >> "$LOG"
            READY=true
            break
        fi
        sleep 10
    done
    if [ "$READY" = false ]; then
        echo "[$(date +%H:%M)] WARNING: No analysis for $inquiry after 20 minutes" >> "$LOG"
        ALL_READY=false
    fi
done

# Step 5: Generate HTML reports (one per inquiry, top 20)
echo "[$(date +%H:%M)] Generating reports..." >> "$LOG"
python3 "$SCRIPTS_DIR/report.py" >> "$LOG" 2>&1

# Step 6: Convert each HTML to PDF
for inquiry in "${INQUIRIES[@]}"; do
    HTML_FILE="$HOUSING_DIR/reports/report_${inquiry}_${TODAY}.html"
    PDF_FILE="$HOUSING_DIR/reports/report_${inquiry}_${TODAY}.pdf"

    if [ -f "$HTML_FILE" ]; then
        echo "[$(date +%H:%M)] Converting $inquiry to PDF..." >> "$LOG"
        cd /tmp && node -e "
        const { chromium } = require('playwright-core');
        const fs = require('fs');
        (async () => {
          const browser = await chromium.launch({
            executablePath: '/home/luka/.cache/ms-playwright/chromium-1208/chrome-linux/chrome'
          });
          const page = await browser.newPage();
          const html = fs.readFileSync('$HTML_FILE', 'utf8');
          await page.setContent(html, { waitUntil: 'networkidle', timeout: 30000 });
          await page.pdf({
            path: '$PDF_FILE',
            format: 'A4',
            printBackground: true,
            margin: { top: '12px', bottom: '12px', left: '12px', right: '12px' }
          });
          await browser.close();
        })();
        " >> "$LOG" 2>&1
        echo "[$(date +%H:%M)] PDF: $PDF_FILE ($(du -h $PDF_FILE | cut -f1))" >> "$LOG"
    fi
done

# Step 7: Deliver to Telegram
echo "[$(date +%H:%M)] Delivering..." >> "$LOG"
cd "$WORKSPACE" && python3 "$SCRIPTS_DIR/deliver.py" >> "$LOG" 2>&1

echo "[$(date +%H:%M)] === Done ===" >> "$LOG"
