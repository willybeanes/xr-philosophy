#!/bin/bash
# Render cron job wrapper for the xR bot.
# Pulls latest data, runs the bot, pushes results back to GitHub.
set -euo pipefail

echo "=== xR Bot cron run: $(date -u) ==="

# Configure git with the GitHub token for pushing
git config user.name "xR Bot"
git config user.email "xrbot@users.noreply.github.com"
git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/willybeanes/xr-philosophy.git"

# Pull latest data (another run may have pushed since build)
echo "Pulling latest..."
git pull --rebase origin main || {
    echo "Pull failed, resetting to remote"
    git fetch origin main
    git reset --hard origin/main
}

# Run the bot
python main.py

# Commit and push results
git add data/posted_games.json data/scores.json data/player_stats.json docs/index.html
if git diff --staged --quiet; then
    echo "No changes to commit"
else
    git commit -m "Update xR scores [skip ci]"
    # Retry push in case of concurrent update
    git push origin main || {
        echo "Push failed, rebasing and retrying..."
        git pull --rebase origin main
        git push origin main
    }
fi

echo "=== Done ==="
