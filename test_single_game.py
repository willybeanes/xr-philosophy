#!/usr/bin/env python3
"""Test script: fetch a single game by gamePk, calculate xR, print the post.

Usage:
    python test_single_game.py <gamePk>

Example:
    python test_single_game.py 745612
"""

import sys

from src.mlb_fetcher import get_play_by_play
from src.re24_engine import calculate_xr
from src.bluesky_poster import format_post


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <gamePk>")
        sys.exit(1)

    game_pk = int(sys.argv[1])
    print(f"Fetching play-by-play for gamePk={game_pk}...\n")

    plays = get_play_by_play(game_pk)
    print(f"Total plays: {len(plays)}")

    xr = calculate_xr(plays)
    print(f"Away xR: {xr['away_xr']}  (actual: {xr['away_actual']})")
    print(f"Home xR: {xr['home_xr']}  (actual: {xr['home_actual']})")

    # Build a minimal game dict from the API data for formatting
    # We need to fetch the game info separately
    import requests
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    data = requests.get(url, timeout=10).json()
    game_data = data.get("gameData", {})
    teams = game_data.get("teams", {})
    linescore = data.get("liveData", {}).get("linescore", {})

    game = {
        "gamePk": game_pk,
        "away_team": teams.get("away", {}).get("name", "Away"),
        "home_team": teams.get("home", {}).get("name", "Home"),
        "away_abbr": teams.get("away", {}).get("abbreviation", "AWY"),
        "home_abbr": teams.get("home", {}).get("abbreviation", "HME"),
        "away_score": linescore.get("teams", {}).get("away", {}).get("runs", 0),
        "home_score": linescore.get("teams", {}).get("home", {}).get("runs", 0),
    }

    print(f"\nActual score: {game['away_team']} {game['away_score']} - {game['home_score']} {game['home_team']}")

    post = format_post(game, xr["away_xr"], xr["home_xr"])
    print(f"\n--- Formatted Post ({len(post)} chars) ---")
    print(post)
    print("---")


if __name__ == "__main__":
    main()
