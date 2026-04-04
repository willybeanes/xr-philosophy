"""Bluesky posting via the AT Protocol."""

import os

from atproto import Client

# Standard MLB team abbreviations (FanGraphs style)
TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Athletics": "ATH",
    "Oakland Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}

# Map full team names to hashtag-friendly short names
TEAM_HASHTAGS = {
    "Arizona Diamondbacks": "Dbacks",
    "Atlanta Braves": "Braves",
    "Baltimore Orioles": "Orioles",
    "Boston Red Sox": "RedSox",
    "Chicago Cubs": "Cubs",
    "Chicago White Sox": "WhiteSox",
    "Cincinnati Reds": "Reds",
    "Cleveland Guardians": "Guardians",
    "Colorado Rockies": "Rockies",
    "Detroit Tigers": "Tigers",
    "Houston Astros": "Astros",
    "Kansas City Royals": "Royals",
    "Los Angeles Angels": "Angels",
    "Los Angeles Dodgers": "Dodgers",
    "Miami Marlins": "Marlins",
    "Milwaukee Brewers": "Brewers",
    "Minnesota Twins": "Twins",
    "New York Mets": "Mets",
    "New York Yankees": "Yankees",
    "Oakland Athletics": "Athletics",
    "Athletics": "Athletics",
    "Philadelphia Phillies": "Phillies",
    "Pittsburgh Pirates": "Pirates",
    "San Diego Padres": "Padres",
    "San Francisco Giants": "Giants",
    "Seattle Mariners": "Mariners",
    "St. Louis Cardinals": "Cardinals",
    "Tampa Bay Rays": "Rays",
    "Texas Rangers": "Rangers",
    "Toronto Blue Jays": "BlueJays",
    "Washington Nationals": "Nationals",
}

MAX_POST_LENGTH = 300


def _get_hashtag(team_name: str) -> str:
    return TEAM_HASHTAGS.get(team_name, team_name.split()[-1])


def format_post(game: dict, away_xr: float, home_xr: float) -> str:
    """Format a game result into a Bluesky post string.

    Args:
        game: Game dict with away_team, home_team, away_score, home_score,
              away_abbr, home_abbr.
        away_xr: Away team's expected runs.
        home_xr: Home team's expected runs.

    Returns:
        Formatted post string.
    """
    away_name = game["away_team"]
    home_name = game["home_team"]
    away_score = game["away_score"]
    home_score = game["home_score"]

    post = (
        f"{away_name} ({away_xr:.2f} xR) {away_score} \u2013 "
        f"{home_score} ({home_xr:.2f} xR) {home_name}"
    )

    # Fall back to abbreviations if too long
    if len(post) > MAX_POST_LENGTH:
        away_name = game.get("away_abbr", away_name)
        home_name = game.get("home_abbr", home_name)
        post = (
            f"{away_name} ({away_xr:.2f} xR) {away_score} \u2013 "
            f"{home_score} ({home_xr:.2f} xR) {home_name}"
        )

    return post


def post_game_result(game: dict, away_xr: float, home_xr: float) -> str | None:
    """Post a game result to Bluesky.

    Returns the post URI if successful, None otherwise.
    """
    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        print("  ERROR: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set")
        return None

    text = format_post(game, away_xr, home_xr)

    try:
        client = Client()
        client.login(handle, app_password)
        response = client.send_post(text=text)
        return response.uri
    except Exception as e:
        print(f"  ERROR posting to Bluesky: {e}")
        return None
