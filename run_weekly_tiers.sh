#!/bin/bash
# Render cron job wrapper for the weekly tier chart post.
set -euo pipefail

echo "=== Weekly Tier Post: $(date -u) ==="

# Configure git for pulling latest data
git config user.name "xR Bot"
git config user.email "xrbot@users.noreply.github.com"
git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/willybeanes/xr-philosophy.git"

# Pull latest data
echo "Pulling latest..."
git pull --rebase origin main || {
    echo "Pull failed, resetting to remote"
    git fetch origin main
    git reset --hard origin/main
}

# Post the weekly tier chart
python weekly_tier_post.py

echo "=== Done ==="
