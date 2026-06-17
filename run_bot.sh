#!/bin/bash
# Render cron job wrapper for the xR bot.
# Clones the repo fresh, runs the bot, pushes results back to GitHub.
set -euo pipefail

echo "=== xR Bot cron run: $(date -u) ==="

REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/willybeanes/xr-philosophy.git"
WORK_DIR="/tmp/xr-philosophy"

# Clone fresh copy with latest data
rm -rf "$WORK_DIR"
git clone --depth 1 "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"

git config user.name "xR Bot"
git config user.email "xrbot@users.noreply.github.com"

# Run the bot
python main.py

# Commit and push results
git add data/posted_games.json data/scores.json data/player_stats.json docs/index.html
if git diff --staged --quiet; then
    echo "No changes to commit"
else
    git commit -m "Update xR scores [skip ci]"
    # Rebase onto any changes pushed by a concurrent run, then push
    git pull --rebase origin main
    git push origin main
fi

echo "=== Done ==="
