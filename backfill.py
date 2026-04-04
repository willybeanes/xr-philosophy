#!/usr/bin/env python3
"""Backfill xR scores for past games.

Usage:
    python backfill.py 2026-04-01 2026-04-03   # date range
    python backfill.py 2026-04-01               # single date

Fetches final games for each date, calculates xR, saves to scores.json,
and marks games in posted_games.json (to prevent future re-posting).
Does NOT post to Bluesky — backfills shouldn't look like live alerts.
"""

import json
import os
import sys
import time
from datetime import date, timedelta

from src.mlb_fetcher import get_todays_games, get_play_by_play
from src.re24_engine import calculate_xr
from src.site_updater import save_score, load_scores, regenerate_site

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POSTED_FILE = os.path.join(DATA_DIR, "posted_games.json")


def load_posted() -> set:
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE) as f:
        data = json.load(f)
    return set(str(pk) for pk in data.get("posted", []))


def save_posted(posted: set) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(POSTED_FILE, "w") as f:
        json.dump({"posted": sorted(posted)}, f, indent=2)


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} <start_date> [end_date]")
        print(f"  Dates in YYYY-MM-DD format")
        sys.exit(1)

    start = parse_date(sys.argv[1])
    end = parse_date(sys.argv[2]) if len(sys.argv) == 3 else start

    if end < start:
        print("Error: end date must be >= start date")
        sys.exit(1)

    print(f"Backfilling {start} to {end}")
    print()

    # Load existing state
    existing_pks = {s["gamePk"] for s in load_scores()}
    posted = load_posted()
    total_new = 0
    total_errors = 0

    d = start
    while d <= end:
        print(f"=== {d} ===")

        try:
            games = get_todays_games(game_date=d)
        except Exception as e:
            print(f"  ERROR fetching games: {e}")
            d += timedelta(days=1)
            continue

        new_games = [g for g in games if g["gamePk"] not in existing_pks]
        print(f"  {len(games)} final games, {len(new_games)} new")

        for game in new_games:
            gpk = game["gamePk"]
            label = f"{game['away_team']} @ {game['home_team']}"

            try:
                plays = get_play_by_play(gpk)
                xr = calculate_xr(plays)
                away_xr = xr["away_xr"]
                home_xr = xr["home_xr"]

                print(f"  {label}: {game['away_score']}-{game['home_score']} "
                      f"(xR: {away_xr:.2f}-{home_xr:.2f})")

                save_score(game, away_xr, home_xr, chart_data=xr.get("cumulative"))
                existing_pks.add(gpk)
                posted.add(str(gpk))
                total_new += 1

            except Exception as e:
                print(f"  ERROR {label}: {e}")
                total_errors += 1

            time.sleep(0.5)  # Be respectful to the API

        d += timedelta(days=1)
        print()

    # Save posted state and regenerate site
    save_posted(posted)
    regenerate_site()

    print(f"Done: {total_new} games backfilled, {total_errors} errors")


if __name__ == "__main__":
    main()
