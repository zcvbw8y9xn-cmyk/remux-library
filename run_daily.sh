#!/bin/bash
# Remux Library Daily Automation Script
# 1. Scrapes fresh tweets from X.com
# 2. Extracts title, year, quality, and verifies link health
# 3. Commits and pushes the updated CSV to GitHub

PROJECT_DIR="/Users/scottsnow/.gemini/antigravity/scratch/my-pi-project"
export PATH="$PROJECT_DIR/.shim:/Users/scottsnow/.gemini/antigravity/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export DEVELOPER_DIR="/Library/Developer/CommandLineTools"
export PYTHONUNBUFFERED=1

cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "🚀 Starting Daily Remux Scrape & Sync"
echo "📅 Date: $(date)"
echo "=========================================="

# Run scraper
echo "🔍 Scraping X.com for new remux links..."
python3 scrape_remux_scrapling.py

# Process titles, years, health checks & Google Sheet sync
echo "🔬 Extracting metadata, verifying links & updating Google Sheet..."
python3 process_and_sync.py

# Regenerate Web Dashboard
echo "🌐 Updating Web Dashboard (index.html)..."
python3 generate_dashboard.py

# Push to GitHub
if git remote get-url origin > /dev/null 2>&1; then
    echo "📤 Syncing changes to GitHub..."
    git add remux_links.json remux_library.csv index.html health_cache.json downloads_*.txt
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
