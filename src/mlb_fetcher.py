"""MLB Stats API integration for fetching game data and play-by-play."""

import time
from datetime import date

import requests

BASE_URL = "https://statsapi.mlb.com/api"
TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2


def _get(url: str) -> dict:
    """Make a GET request with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} for {url}: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise


def get_todays_games(game_date: date | None = None) -> list[dict]:
    """Fetch today's final regular-season games.

    Returns a list of game dicts with keys:
        gamePk, away_team, home_team, away_abbr, home_abbr,
        away_score, home_score, status
    """
    d = game_date or date.today()
    url = f"{BASE_URL}/v1/schedule?sportId=1&date={d.isoformat()}&gameType=R&hydrate=linescore"
    data = _get(url)

    games = []
    for game_date_entry in data.get("dates", []):
        for game in game_date_entry.get("games", []):
            status = game.get("status", {})
            if status.get("abstractGameState") != "Final":
                continue
            # Skip postponed/suspended games that the API marks as "Final"
            detailed = status.get("detailedState", "")
            if detailed in ("Postponed", "Suspended", "Cancelled"):
                continue

            teams = game.get("teams", {})
            linescore = game.get("linescore", {})

            games.append({
                "gamePk": game["gamePk"],
                "game_date": game_date_entry.get("date", d.isoformat()),
                "away_team": teams["away"]["team"]["name"],
                "home_team": teams["home"]["team"]["name"],
                "away_abbr": teams["away"]["team"].get("abbreviation", ""),
                "home_abbr": teams["home"]["team"].get("abbreviation", ""),
                "away_score": linescore.get("teams", {}).get("away", {}).get("runs", 0),
                "home_score": linescore.get("teams", {}).get("home", {}).get("runs", 0),
                "status": status.get("detailedState", "Final"),
            })

    return games


def get_play_by_play(game_pk: int) -> list[dict]:
    """Fetch play-by-play data for a specific game.

    Returns the allPlays list from liveData.plays.
    """
    url = f"{BASE_URL}/v1.1/game/{game_pk}/feed/live"
    data = _get(url)
    return data.get("liveData", {}).get("plays", {}).get("allPlays", [])
