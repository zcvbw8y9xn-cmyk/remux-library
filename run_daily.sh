#!/bin/bash
# Remux Library Twice-Daily Automation Script
# 1. Scrapes fresh tweets from X.com
# 2. Extracts title, year, quality, and verifies link health + syncs Google Sheet
# 3. Rebuilds dashboard & pushes updates to GitHub

PROJECT_DIR="/Users/scottsnow/.gemini/antigravity/scratch/my-pi-project"
export PATH="$PROJECT_DIR/.shim:/Users/scottsnow/.gemini/antigravity/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export DEVELOPER_DIR="/Library/Developer/CommandLineTools"
export PYTHONUNBUFFERED=1

PYTHON_BIN="/opt/homebrew/bin/python3"
LOCK_DIR="$PROJECT_DIR/.sync.lock"

cd "$PROJECT_DIR" || exit 1

# Prevent concurrent runs between LaunchAgent and Remux Vault.app
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    OLD_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️ Sync already running (PID $OLD_PID). Exiting cleanly."
        exit 0
    fi
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" || exit 1
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

echo "=========================================="
echo "🚀 Starting Remux Scrape & Sync"
echo "📅 Date: $(date)"
echo "=========================================="

# Run scraper
echo "🔍 Scraping X.com for new remux links..."
"$PYTHON_BIN" scrape_remux_scrapling.py || { echo "❌ Scraper failed"; exit 1; }

# Process titles, years, health checks & Google Sheet sync
echo "🔬 Extracting metadata, verifying links & updating Google Sheet..."
"$PYTHON_BIN" process_and_sync.py || { echo "❌ Processing/Sheet sync failed"; exit 1; }

# Regenerate Web Dashboard
echo "🌐 Updating Web Dashboard (index.html)..."
"$PYTHON_BIN" generate_dashboard.py || { echo "❌ Dashboard build failed"; exit 1; }

# Push to GitHub
if git remote get-url origin > /dev/null 2>&1; then
    echo "📤 Syncing changes to GitHub..."
    git add remux_links.json remux_library.csv index.html health_cache.json downloads_*.txt
    if git diff --cached --quiet; then
        echo "ℹ️ No new changes to commit."
    else
        git commit -m "Auto-update remux library: $(date -u +'%Y-%m-%d %H:%M UTC')" || exit 1
    fi
    git push origin main || { echo "❌ Git push failed"; exit 1; }
    echo "✅ GitHub sync complete!"
else
    echo "⚠️ Git remote 'origin' not configured yet. Skipping git push."
fi

# Send native Mac notification
ACTIVE_COUNT=$(grep -c "Alive 🟢" "$PROJECT_DIR/remux_library.csv" 2>/dev/null || echo "0")
osascript -e "display notification \"Library updated: $ACTIVE_COUNT active movies ready in Google Sheets!\" with title \"🎬 Remux Library Sync Complete\" sound name \"Glass\"" 2>/dev/null || true

echo "🎉 All done! Desktop notification sent."
