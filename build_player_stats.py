#!/usr/bin/env python3
"""Build aggregated player xR stats from all scored games.

Processes every game in scores.json, fetches play-by-play from the MLB API,
and writes data/player_stats.json with per-player batting and pitching xR.

Usage:
    python build_player_stats.py              # full rebuild
    python build_player_stats.py --incremental # only process new games
"""

import json
import os
import sys
import time
from collections import defaultdict

from src.mlb_fetcher import get_play_by_play
from src.re24_engine import extract_player_xr

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SCORES_PATH = os.path.join(DATA_DIR, "scores.json")
PLAYER_STATS_PATH = os.path.join(DATA_DIR, "player_stats.json")


def load_scores() -> list[dict]:
    with open(SCORES_PATH) as f:
        return json.load(f)


def load_player_stats() -> dict:
    if not os.path.exists(PLAYER_STATS_PATH):
        return {"batters": {}, "pitchers": {}, "processed_games": []}
    with open(PLAYER_STATS_PATH) as f:
        return json.load(f)


def save_player_stats(stats: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PLAYER_STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)


def process_game(game: dict, stats: dict) -> None:
    """Fetch play-by-play for a game and accumulate player xR."""
    gpk = game["gamePk"]
    away_team = game["away_team"]
    home_team = game["home_team"]

    plays = get_play_by_play(gpk)
    pa_list = extract_player_xr(plays)

    batters = stats["batters"]
    pitchers = stats["pitchers"]

    for pa in pa_list:
        bid = str(pa["batter_id"])
        pid = str(pa["pitcher_id"])
        team = away_team if pa["is_top"] else home_team
        opp_team = home_team if pa["is_top"] else away_team

        # Batter stats
        if bid not in batters:
            batters[bid] = {"name": pa["batter_name"], "team": team,
                            "pa": 0, "xr": 0.0}
        b = batters[bid]
        b["name"] = pa["batter_name"]  # update in case of name changes
        b["team"] = team
        b["pa"] += 1
        b["xr"] = round(b["xr"] + pa["xr"], 4)

        # Pitcher stats
        if pid not in pitchers:
            pitchers[pid] = {"name": pa["pitcher_name"], "team": opp_team,
                             "bf": 0, "xr_allowed": 0.0}
        p = pitchers[pid]
        p["name"] = pa["pitcher_name"]
        p["team"] = opp_team
        p["bf"] += 1
        p["xr_allowed"] = round(p["xr_allowed"] + pa["xr"], 4)


def main():
    incremental = "--incremental" in sys.argv

    scores = load_scores()
    print(f"Loaded {len(scores)} games from scores.json")

    if incremental:
        stats = load_player_stats()
        processed = set(stats.get("processed_games", []))
        to_process = [g for g in scores if g["gamePk"] not in processed]
        print(f"Incremental: {len(processed)} already processed, {len(to_process)} new")
    else:
        stats = {"batters": {}, "pitchers": {}, "processed_games": []}
        to_process = scores
        print(f"Full rebuild: processing all {len(to_process)} games")

    if not to_process:
        print("Nothing to process.")
        return

    errors = 0
    for i, game in enumerate(to_process, 1):
        gpk = game["gamePk"]
        label = f"{game['away_team']} @ {game['home_team']} ({game['date']})"
        print(f"  [{i}/{len(to_process)}] {label}")

        try:
            process_game(game, stats)
            stats["processed_games"].append(gpk)
        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1

        # Save periodically (every 25 games)
        if i % 25 == 0:
            save_player_stats(stats)
            print(f"    (saved checkpoint: {i} games)")

        time.sleep(0.3)  # respect the API

    save_player_stats(stats)

    n_bat = len(stats["batters"])
    n_pit = len(stats["pitchers"])
    print(f"\nDone: {n_bat} batters, {n_pit} pitchers, {errors} errors")
    print(f"Saved to {PLAYER_STATS_PATH}")


if __name__ == "__main__":
    main()
