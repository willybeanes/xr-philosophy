"""xR Philosophy — Main entry point for the MLB xR bot."""

import json
import os
import sys
import time
from datetime import date

from src.mlb_fetcher import get_todays_games, get_play_by_play
from src.re24_engine import calculate_xr, extract_player_xr
from src.bluesky_poster import post_game_result, format_post, TEAM_ABBR
from src.site_updater import save_score, regenerate_site

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POSTED_FILE = os.path.join(DATA_DIR, "posted_games.json")
PLAYER_STATS_PATH = os.path.join(DATA_DIR, "player_stats.json")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("true", "1", "yes")


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


def load_player_stats() -> dict:
    if not os.path.exists(PLAYER_STATS_PATH):
        return {"batters": {}, "pitchers": {}, "processed_games": []}
    with open(PLAYER_STATS_PATH) as f:
        return json.load(f)


def save_player_stats(stats: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PLAYER_STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)


def update_player_stats(game: dict, plays: list, player_stats: dict) -> None:
    """Accumulate per-player xR from a single game's play-by-play."""
    pa_list = extract_player_xr(plays)
    batters = player_stats["batters"]
    pitchers = player_stats["pitchers"]

    for pa in pa_list:
        bid = str(pa["batter_id"])
        pid = str(pa["pitcher_id"])
        team = game["away_team"] if pa["is_top"] else game["home_team"]
        opp_team = game["home_team"] if pa["is_top"] else game["away_team"]

        if bid not in batters:
            batters[bid] = {"name": pa["batter_name"], "team": team,
                            "pa": 0, "xr": 0.0}
        b = batters[bid]
        b["name"] = pa["batter_name"]
        b["team"] = team
        b["pa"] += 1
        b["xr"] = round(b["xr"] + pa["xr"], 4)

        if pid not in pitchers:
            pitchers[pid] = {"name": pa["pitcher_name"], "team": opp_team,
                             "bf": 0, "xr_allowed": 0.0}
        p = pitchers[pid]
        p["name"] = pa["pitcher_name"]
        p["team"] = opp_team
        p["bf"] += 1
        p["xr_allowed"] = round(p["xr_allowed"] + pa["xr"], 4)

    player_stats["processed_games"].append(game["gamePk"])


def main():
    if DRY_RUN:
        print("=== DRY RUN MODE — will not post to Bluesky ===\n")

    print("Loading posted games...")
    posted = load_posted()
    print(f"  {len(posted)} games already posted")

    # Support GAME_DATE env var for targeting a specific date
    game_date = None
    if os.environ.get("GAME_DATE"):
        game_date = date.fromisoformat(os.environ["GAME_DATE"])
        print(f"Targeting date: {game_date}")

    # Fetch games for the target date(s)
    # When no date is specified, check both today AND yesterday (UTC) since
    # MLB game dates are in ET but GitHub Actions runs in UTC — games finishing
    # after 8 PM ET are already "tomorrow" in UTC
    games = []
    if game_date:
        dates_to_check = [game_date]
    else:
        from datetime import timedelta
        today = date.today()
        dates_to_check = [today, today - timedelta(days=1)]

    for d in dates_to_check:
        print(f"Fetching final games for {d.isoformat()}...")
        try:
            day_games = get_todays_games(game_date=d)
            print(f"  {len(day_games)} final game(s)")
            games.extend(day_games)
        except Exception as e:
            print(f"  ERROR fetching games for {d}: {e}")

    # Deduplicate across date windows (same game can appear in today + yesterday)
    seen: dict = {}
    for g in games:
        seen.setdefault(str(g["gamePk"]), g)
    games = list(seen.values())

    print(f"Total: {len(games)} final game(s) found")

    new_games = [g for g in games if str(g["gamePk"]) not in posted]
    if not new_games:
        print("  No new games to process.")
        regenerate_site()
        return

    print(f"  {len(new_games)} new game(s) to process\n")

    POST_DELAY = 10  # seconds between Bluesky posts

    player_stats = load_player_stats()
    errors = 0
    posted_count = 0
    for game in new_games:
        gpk = game["gamePk"]
        label = f"{game['away_team']} @ {game['home_team']}"
        print(f"Processing: {label} (gamePk={gpk})")

        try:
            plays = get_play_by_play(gpk)
            print(f"  {len(plays)} plays fetched")

            xr = calculate_xr(plays)
            away_xr = xr["away_xr"]
            home_xr = xr["home_xr"]
            print(f"  xR: {game['away_team']} {away_xr} | {game['home_team']} {home_xr}")

            post_text = format_post(game, away_xr, home_xr)
            print(f"  Post: {post_text}")

            if DRY_RUN:
                print("  [DRY RUN] Skipping Bluesky post")
            else:
                # Wait between posts so they don't all fire at once
                if posted_count > 0:
                    print(f"  Waiting {POST_DELAY}s before posting...")
                    time.sleep(POST_DELAY)

                uri = post_game_result(game, away_xr, home_xr)
                if uri:
                    print(f"  Posted: {uri}")
                    posted_count += 1
                else:
                    print("  WARNING: Post may have failed")

            # Save score, update player stats, and mark as posted
            save_score(game, away_xr, home_xr, chart_data=xr.get("cumulative"))
            update_player_stats(game, plays, player_stats)
            posted.add(str(gpk))
            save_posted(posted)

        except Exception as e:
            print(f"  ERROR processing {label}: {e}")
            errors += 1

        print()

    save_player_stats(player_stats)
    regenerate_site()

    if errors:
        print(f"\nCompleted with {errors} error(s)")
    else:
        print("\nAll games processed successfully")


if __name__ == "__main__":
    main()
