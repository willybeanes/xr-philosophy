"""Regenerate the GitHub Pages dashboard from scores data."""

import json
import os
from datetime import date

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
SCORES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scores.json")


def load_scores() -> list[dict]:
    """Load scores from data/scores.json."""
    if not os.path.exists(SCORES_PATH):
        return []
    with open(SCORES_PATH) as f:
        return json.load(f)


def save_score(game: dict, away_xr: float, home_xr: float) -> None:
    """Append a game score to data/scores.json.

    Uses the game_date from the API response (not today's date) so backfills
    and after-midnight games get the correct date. Deduplicates by gamePk.
    """
    scores = load_scores()

    # Prevent duplicate entries
    existing_pks = {s["gamePk"] for s in scores}
    if game["gamePk"] in existing_pks:
        return

    scores.append({
        "gamePk": game["gamePk"],
        "date": game.get("game_date", date.today().isoformat()),
        "away_team": game["away_team"],
        "home_team": game["home_team"],
        "away_abbr": game.get("away_abbr", ""),
        "home_abbr": game.get("home_abbr", ""),
        "away_score": game["away_score"],
        "home_score": game["home_score"],
        "away_xr": away_xr,
        "home_xr": home_xr,
    })
    os.makedirs(os.path.dirname(SCORES_PATH), exist_ok=True)
    with open(SCORES_PATH, "w") as f:
        json.dump(scores, f, indent=2)


def regenerate_site() -> None:
    """Regenerate docs/index.html from scores data."""
    scores = load_scores()

    # Group by date, most recent first
    by_date: dict[str, list] = {}
    for s in scores:
        by_date.setdefault(s["date"], []).append(s)

    # Compute summary stats
    total_games = len(scores)
    mismatch_count = 0
    for s in scores:
        if s["away_score"] != s["home_score"] and s["away_xr"] != s["home_xr"]:
            actual_away_wins = s["away_score"] > s["home_score"]
            xr_away_wins = s["away_xr"] > s["home_xr"]
            if actual_away_wins != xr_away_wins:
                mismatch_count += 1
    mismatch_pct = (mismatch_count / total_games * 100) if total_games else 0

    # Build table rows
    rows_html = ""
    for game_date in sorted(by_date.keys(), reverse=True):
        rows_html += f'<tr class="date-header"><td colspan="5">{game_date}</td></tr>\n'
        for g in by_date[game_date]:
            mismatch = ""
            if g["away_score"] != g["home_score"] and g["away_xr"] != g["home_xr"]:
                actual_away_wins = g["away_score"] > g["home_score"]
                xr_away_wins = g["away_xr"] > g["home_xr"]
                if actual_away_wins != xr_away_wins:
                    mismatch = ' class="mismatch"'

            rows_html += (
                f"<tr{mismatch}>"
                f'<td class="team away">{g["away_team"]}</td>'
                f'<td class="xr">{g["away_xr"]:.2f}</td>'
                f'<td class="score">{g["away_score"]} &ndash; {g["home_score"]}</td>'
                f'<td class="xr">{g["home_xr"]:.2f}</td>'
                f'<td class="team home">{g["home_team"]}</td>'
                f"</tr>\n"
            )

    # Summary line
    if total_games:
        stats_html = (
            f'<div class="stats">{total_games} games'
            f' &middot; {mismatch_count} xR mismatches ({mismatch_pct:.1f}%)</div>'
        )
    else:
        stats_html = ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>xR Philosophy</title>
<style>
:root {{
  --bg: #ffffff;
  --surface: #f5f5f5;
  --text: #111111;
  --text-secondary: #666666;
  --border: #e0e0e0;
  --red: #dc2f1f;
  --red-bg: #fff0f0;
  --accent: #333333;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0d0d0d;
    --surface: #1a1a1a;
    --text: #e8e8e8;
    --text-secondary: #999999;
    --border: #2a2a2a;
    --red: #ef4432;
    --red-bg: #2a1010;
    --accent: #cccccc;
  }}
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem;
  line-height: 1.5;
}}
header {{
  text-align: center;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--red);
  padding-bottom: 1.5rem;
}}
h1 {{
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}}
h1 span {{ color: var(--red); }}
.subtitle {{
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-top: 0.25rem;
}}
.stats {{
  color: var(--text-secondary);
  font-size: 0.8rem;
  margin-top: 0.5rem;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 2rem;
}}
thead {{
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--bg);
}}
th {{
  text-align: left;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  padding: 0.5rem 0.4rem;
  border-bottom: 1px solid var(--border);
}}
td {{
  padding: 0.6rem 0.4rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.95rem;
}}
.date-header td {{
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--text-secondary);
  background: var(--surface);
  padding: 0.4rem;
}}
.score {{
  font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
  text-align: center;
  font-weight: 700;
  white-space: nowrap;
}}
.xr {{
  font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.85rem;
}}
.team {{ font-weight: 500; }}
.team.away {{ text-align: right; }}
.team.home {{ text-align: left; }}
tr.mismatch {{
  background: var(--red-bg);
}}
tr.mismatch .score::after {{
  content: " \\1f534";
  font-size: 0.7rem;
}}
footer {{
  color: var(--text-secondary);
  font-size: 0.8rem;
  border-top: 1px solid var(--border);
  padding-top: 1rem;
  line-height: 1.6;
}}
footer strong {{ color: var(--text); }}
</style>
</head>
<body>
<header>
  <h1><span>x</span>R Philosophy</h1>
  <div class="subtitle">Expected Runs | MLB {date.today().year}</div>
  {stats_html}
</header>
<table>
  <thead>
    <tr>
      <th style="text-align:right">Away</th>
      <th style="text-align:center">xR</th>
      <th style="text-align:center">Score</th>
      <th style="text-align:center">xR</th>
      <th>Home</th>
    </tr>
  </thead>
  <tbody>
    {rows_html if rows_html else '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:2rem">No games recorded yet.</td></tr>'}
  </tbody>
</table>
<footer>
  <p><strong>What is xR?</strong> Expected Runs (xR) measures how many runs a team's
  events &mdash; hits, walks, outs &mdash; typically produce in each base-out context,
  based on historical MLB averages. Unlike actual runs, xR is independent of
  sequencing luck. A red row means the team with higher xR lost the game.</p>
  <p style="margin-top:0.5rem">Data from MLB Stats API. Updated automatically.</p>
</footer>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(html)

    print(f"  Site regenerated: docs/index.html ({total_games} games, {mismatch_count} mismatches)")
