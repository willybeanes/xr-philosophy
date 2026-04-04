"""Bluesky posting via the AT Protocol."""

import os

from atproto import Client

# Official MLB team primary colors
TEAM_COLORS = {
    "Arizona Diamondbacks": "#A71930",
    "Atlanta Braves": "#CE1141",
    "Baltimore Orioles": "#DF4601",
    "Boston Red Sox": "#BD3039",
    "Chicago Cubs": "#0E3386",
    "Chicago White Sox": "#27251F",
    "Cincinnati Reds": "#C6011F",
    "Cleveland Guardians": "#00385D",
    "Colorado Rockies": "#333366",
    "Detroit Tigers": "#0C2340",
    "Houston Astros": "#002D62",
    "Kansas City Royals": "#004687",
    "Los Angeles Angels": "#BA0021",
    "Los Angeles Dodgers": "#005A9C",
    "Miami Marlins": "#00A3E0",
    "Milwaukee Brewers": "#FFC52F",
    "Minnesota Twins": "#002B5C",
    "New York Mets": "#002D72",
    "New York Yankees": "#003087",
    "Athletics": "#003831",
    "Oakland Athletics": "#003831",
    "Philadelphia Phillies": "#E81828",
    "Pittsburgh Pirates": "#FDB827",
    "San Diego Padres": "#2F241D",
    "San Francisco Giants": "#FD5A1E",
    "Seattle Mariners": "#0C2C56",
    "St. Louis Cardinals": "#C41E3A",
    "Tampa Bay Rays": "#092C5C",
    "Texas Rangers": "#003278",
    "Toronto Blue Jays": "#134A8E",
    "Washington Nationals": "#AB0003",
}

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


def post_game_result(game: dict, away_xr: float, home_xr: float,
                     chart_png: bytes | None = None) -> str | None:
    """Post a game result to Bluesky, optionally with a chart image.

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

        if chart_png:
            away_abbr = TEAM_ABBR.get(game["away_team"], "Away")
            home_abbr = TEAM_ABBR.get(game["home_team"], "Home")
            alt_text = (
                f"Cumulative xR chart: {away_abbr} {away_xr:.2f} xR "
                f"vs {home_abbr} {home_xr:.2f} xR"
            )
            response = client.send_image(
                text=text,
                image=chart_png,
                image_alt=alt_text,
            )
        else:
            response = client.send_post(text=text)

        return response.uri
    except Exception as e:
        print(f"  ERROR posting to Bluesky: {e}")
        return None
