#!/bin/bash
# Remux Library Daily Automation Script
# 1. Scrapes fresh tweets from X.com
# 2. Extracts title, year, quality, and verifies link health
# 3. Commits and pushes the updated CSV to GitHub

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

echo "🎉 All done for today!"
