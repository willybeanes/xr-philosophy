#!/bin/bash
# Render cron job wrapper for the weekly tier chart post.
set -euo pipefail

echo "=== Weekly Tier Post: $(date -u) ==="

REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/willybeanes/xr-philosophy.git"
WORK_DIR="/tmp/xr-philosophy"

# Clone fresh copy with latest data
rm -rf "$WORK_DIR"
git clone --depth 1 "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"

# Post the weekly tier chart
python weekly_tier_post.py

echo "=== Done ==="
