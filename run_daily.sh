#!/bin/bash
# Remux Library Daily Automation Script
# 1. Scrapes fresh tweets from X.com
# 2. Extracts title, year, quality, and verifies link health
# 3. Commits and pushes the updated CSV to GitHub

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/scottsnow/.gemini/antigravity/bin:$PATH"
export PYTHONUNBUFFERED=1

PROJECT_DIR="/Users/scottsnow/.gemini/antigravity/scratch/my-pi-project"
cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "🚀 Starting Daily Remux Scrape & Sync"
echo "📅 Date: $(date)"
echo "=========================================="

# Run scraper
echo "🔍 Scraping X.com for new remux links..."
python3 scrape_remux_scrapling.py

# Process titles, years & check health
echo "🔬 Extracting metadata & verifying link status..."
python3 process_and_sync.py

# Sync directly to Google Sheet
SPREADSHEET_ID="1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E"
echo "📊 Syncing to Google Sheet ($SPREADSHEET_ID)..."
gsheets mutate import-csv "$SPREADSHEET_ID" remux_library.csv
gsheets mutate autosize "$SPREADSHEET_ID" --sheet-id 0 --start-col 0 --end-col 8
echo "✅ Google Sheet updated!"

# Push to GitHub (if git remote is configured)
if git remote get-url origin > /dev/null 2>&1; then
    echo "📤 Syncing changes to GitHub..."
    git add remux_links.json remux_library.csv
    git commit -m "Auto-update remux library: $(date -u +'%Y-%m-%d %H:%M UTC')"
    git push origin main
    echo "✅ GitHub sync complete!"
else
    echo "⚠️ Git remote 'origin' not configured yet. Skipping git push."
fi

# Send native Mac notification
ACTIVE_COUNT=$(grep -c "Alive 🟢" "$PROJECT_DIR/remux_library.csv" 2>/dev/null || echo "0")
osascript -e "display notification \"Library updated: $ACTIVE_COUNT active movies ready in Google Sheets!\" with title \"🎬 Remux Library Sync Complete\" sound name \"Glass\"" 2>/dev/null

echo "🎉 All done! Desktop notification sent."
