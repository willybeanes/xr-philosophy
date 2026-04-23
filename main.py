"""xR Philosophy — Main entry point for the MLB xR bot."""

import json
import os
import sys
import time
from datetime import date

from src.mlb_fetcher import get_todays_games, get_play_by_play
from src.re24_engine import calculate_xr
from src.bluesky_poster import post_game_result, format_post
from src.site_updater import save_score, regenerate_site

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POSTED_FILE = os.path.join(DATA_DIR, "posted_games.json")
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

    print(f"Total: {len(games)} final game(s) found")

    new_games = [g for g in games if str(g["gamePk"]) not in posted]
    if not new_games:
        print("  No new games to process.")
        regenerate_site()
        return

    print(f"  {len(new_games)} new game(s) to process\n")

    POST_DELAY = 60  # seconds between Bluesky posts

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

            # Save score and mark as posted regardless of post success
            save_score(game, away_xr, home_xr, chart_data=xr.get("cumulative"))
            posted.add(str(gpk))
            save_posted(posted)

        except Exception as e:
            print(f"  ERROR processing {label}: {e}")
            errors += 1

        print()

    regenerate_site()

    if errors:
        print(f"\nCompleted with {errors} error(s)")
    else:
        print("\nAll games processed successfully")


if __name__ == "__main__":
    main()
