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


def save_score(game: dict, away_xr: float, home_xr: float,
               chart_data: list | None = None) -> None:
    """Append a game score to data/scores.json."""
    scores = load_scores()

    existing_pks = {s["gamePk"] for s in scores}
    if game["gamePk"] in existing_pks:
        return

    entry = {
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
    }
    if chart_data is not None:
        entry["chart_data"] = chart_data

    scores.append(entry)
    os.makedirs(os.path.dirname(SCORES_PATH), exist_ok=True)
    with open(SCORES_PATH, "w") as f:
        json.dump(scores, f, indent=2)


def _generate_chart_svg(g: dict) -> str:
    """Generate an inline SVG chart for a game showing cumulative xR vs actual runs."""
    cd = g.get("chart_data")
    if not cd:
        return ""

    away_abbr = g.get("away_abbr") or g["away_team"].split()[-1][:3].upper()
    home_abbr = g.get("home_abbr") or g["home_team"].split()[-1][:3].upper()

    # Build point series from chart_data (already has cumulative values per PA)
    points = [{"pa": 0, "a_xr": 0, "h_xr": 0, "a_r": 0, "h_r": 0, "inn": 1}]
    for p in cd:
        points.append({
            "pa": p["pa"],
            "a_xr": p["a_xr"],
            "h_xr": p["h_xr"],
            "a_r": p["a_r"],
            "h_r": p["h_r"],
            "inn": p["inn"],
        })

    # Inning boundaries
    inning_starts = {}
    for p in cd:
        if p["inn"] not in inning_starts:
            inning_starts[p["inn"]] = p["pa"]

    # Chart dimensions
    W = 720; H = 340
    PL = 42; PR = 40; PT = 14; PB = 36
    PW = W - PL - PR; PH = H - PT - PB

    max_pa = max(p["pa"] for p in points) or 1
    max_y = max(
        max((p["a_xr"] for p in points), default=1),
        max((p["h_xr"] for p in points), default=1),
        max((p["a_r"] for p in points), default=1),
        max((p["h_r"] for p in points), default=1),
        1
    ) * 1.15

    def sx(pa):
        return PL + (pa / max_pa) * PW

    def sy(val):
        return PT + PH - (val / max_y) * PH

    def step_path(pts, key):
        parts = []
        for i, p in enumerate(pts):
            x = sx(p["pa"]); y = sy(p[key])
            if i == 0:
                parts.append(f"M {x:.1f} {y:.1f}")
            else:
                parts.append(f"H {x:.1f} V {y:.1f}")
        return " ".join(parts)

    # Y gridlines
    step = 2 if max_y > 6 else 1
    y_grid = ""
    for v in range(0, int(max_y) + 1, step):
        y = sy(v)
        y_grid += f'<line x1="{PL}" y1="{y:.0f}" x2="{W-PR}" y2="{y:.0f}" stroke="var(--chart-grid)" stroke-width="0.5"/>'
        y_grid += f'<text x="{PL-6}" y="{y+4:.0f}" text-anchor="end" fill="var(--chart-label)" font-size="10">{v}</text>'

    # Inning dividers + labels
    inn_svg = ""
    for inn, pa_start in inning_starts.items():
        x = sx(pa_start)
        inn_svg += f'<line x1="{x:.0f}" y1="{PT}" x2="{x:.0f}" y2="{PT+PH}" stroke="var(--chart-grid)" stroke-width="0.5" stroke-dasharray="3,3"/>'
        next_start = inning_starts.get(inn + 1, max_pa)
        mid = sx((pa_start + next_start) / 2)
        inn_svg += f'<text x="{mid:.0f}" y="{PT+PH+14}" text-anchor="middle" fill="var(--chart-label)" font-size="10">{inn}</text>'

    # End labels
    last = points[-1]
    labels = ""
    # Offset overlapping labels
    positions = [
        ("a_xr", "#2563eb", f'{last["a_xr"]:.1f}'),
        ("a_r", "#2563eb", f'{last["a_r"]}'),
        ("h_xr", "#dc2626", f'{last["h_xr"]:.1f}'),
        ("h_r", "#dc2626", f'{last["h_r"]}'),
    ]
    used_y = []
    for key, color, text in positions:
        y = sy(last[key])
        # Push away from nearby labels
        for uy in used_y:
            if abs(y - uy) < 12:
                y = uy - 12 if y < uy else uy + 12
        used_y.append(y)
        opacity = "0.5" if key.endswith("_r") else "1"
        dash = " (actual)" if key.endswith("_r") else ""
        labels += f'<text x="{W-PR+4}" y="{y+4:.0f}" fill="{color}" font-size="10" font-weight="600" opacity="{opacity}">{text}</text>'

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;font-family:system-ui,sans-serif">
{y_grid}{inn_svg}
<path d="{step_path(points, 'a_r')}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.65"/>
<path d="{step_path(points, 'h_r')}" fill="none" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.65"/>
<path d="{step_path(points, 'a_xr')}" fill="none" stroke="#2563eb" stroke-width="2.5"/>
<path d="{step_path(points, 'h_xr')}" fill="none" stroke="#dc2626" stroke-width="2.5"/>
{labels}
<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+PH}" stroke="var(--chart-axis)" stroke-width="1"/>
<line x1="{PL}" y1="{PT+PH}" x2="{W-PR}" y2="{PT+PH}" stroke="var(--chart-axis)" stroke-width="1"/>
<text x="{PL+6}" y="{PT+10}" fill="#2563eb" font-size="10" font-weight="600">{away_abbr} xR</text>
<line x1="{PL+40}" y1="{PT+7}" x2="{PL+56}" y2="{PT+7}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.65"/>
<text x="{PL+58}" y="{PT+10}" fill="#2563eb" font-size="10" opacity="0.5">actual</text>
<text x="{PL+105}" y="{PT+10}" fill="#dc2626" font-size="10" font-weight="600">{home_abbr} xR</text>
<line x1="{PL+139}" y1="{PT+7}" x2="{PL+155}" y2="{PT+7}" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.65"/>
<text x="{PL+157}" y="{PT+10}" fill="#dc2626" font-size="10" opacity="0.5">actual</text>
</svg>"""


def regenerate_site() -> None:
    """Regenerate docs/index.html from scores data."""
    scores = load_scores()

    # Group by date, most recent first
    by_date: dict[str, list] = {}
    for s in scores:
        by_date.setdefault(s["date"], []).append(s)

    # Summary stats
    total_games = len(scores)
    mismatch_count = 0
    for s in scores:
        if s["away_score"] != s["home_score"] and s["away_xr"] != s["home_xr"]:
            if (s["away_score"] > s["home_score"]) != (s["away_xr"] > s["home_xr"]):
                mismatch_count += 1
    mismatch_pct = (mismatch_count / total_games * 100) if total_games else 0

    # Build rows
    rows_html = ""
    for game_date in sorted(by_date.keys(), reverse=True):
        rows_html += f'<tr class="date-header"><td colspan="5">{game_date}</td></tr>\n'
        for g in by_date[game_date]:
            gpk = g["gamePk"]
            mismatch = ""
            if g["away_score"] != g["home_score"] and g["away_xr"] != g["home_xr"]:
                if (g["away_score"] > g["home_score"]) != (g["away_xr"] > g["home_xr"]):
                    mismatch = ' class="mismatch"'

            has_chart = "chart_data" in g and g["chart_data"]
            click = f' onclick="toggle({gpk})"' if has_chart else ""
            arrow = ' <span class="arrow">&#9656;</span>' if has_chart else ""

            rows_html += (
                f'<tr{mismatch}{click} data-gpk="{gpk}">'
                f'<td class="team away">{g["away_team"]}{arrow}</td>'
                f'<td class="xr">{g["away_xr"]:.2f}</td>'
                f'<td class="score">{g["away_score"]} &ndash; {g["home_score"]}</td>'
                f'<td class="xr">{g["home_xr"]:.2f}</td>'
                f'<td class="team home">{g["home_team"]}</td>'
                f"</tr>\n"
            )

            if has_chart:
                svg = _generate_chart_svg(g)
                rows_html += (
                    f'<tr class="chart-row" id="chart-{gpk}" style="display:none">'
                    f'<td colspan="5" class="chart-cell">{svg}</td>'
                    f"</tr>\n"
                )

    stats_html = (
        f'<div class="stats">{total_games} games'
        f' &middot; {mismatch_count} xR mismatches ({mismatch_pct:.1f}%)</div>'
    ) if total_games else ""

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
  --chart-grid: #e5e7eb;
  --chart-label: #9ca3af;
  --chart-axis: #d1d5db;
  --chart-bg: #fafafa;
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
    --chart-grid: #333333;
    --chart-label: #666666;
    --chart-axis: #444444;
    --chart-bg: #141414;
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
h1 {{ font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; }}
h1 span {{ color: var(--red); }}
.subtitle {{ color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem; }}
.stats {{ color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
thead {{ position: sticky; top: 0; z-index: 1; background: var(--bg); }}
th {{
  text-align: left; font-size: 0.75rem; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-secondary);
  padding: 0.5rem 0.4rem; border-bottom: 1px solid var(--border);
}}
td {{ padding: 0.6rem 0.4rem; border-bottom: 1px solid var(--border); font-size: 0.95rem; }}
.date-header td {{
  font-weight: 700; font-size: 0.85rem; color: var(--text-secondary);
  background: var(--surface); padding: 0.4rem;
}}
.score {{
  font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
  text-align: center; font-weight: 700; white-space: nowrap;
}}
.xr {{
  font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
  text-align: center; color: var(--text-secondary); font-size: 0.85rem;
}}
.team {{ font-weight: 500; }}
.team.away {{ text-align: right; }}
.team.home {{ text-align: left; }}
tr.mismatch {{ background: var(--red-bg); }}
tr.mismatch .score::after {{ content: " \\1f534"; font-size: 0.7rem; }}
tr[onclick] {{ cursor: pointer; }}
tr[onclick]:hover {{ background: var(--surface); }}
tr.mismatch[onclick]:hover {{ background: var(--red-bg); }}
.arrow {{ font-size: 0.7rem; color: var(--text-secondary); transition: transform 0.15s; display: inline-block; }}
tr.expanded .arrow {{ transform: rotate(90deg); }}
.chart-row {{ border-bottom: 1px solid var(--border); }}
.chart-cell {{
  padding: 0.5rem 0; background: var(--chart-bg);
  text-align: center;
}}
footer {{
  color: var(--text-secondary); font-size: 0.8rem;
  border-top: 1px solid var(--border); padding-top: 1rem; line-height: 1.6;
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
  <p><strong>What is xR?</strong> Expected Runs (xR) uses Statcast exit velocity and
  launch angle to estimate how many runs each team's batted balls <em>deserved</em>
  to produce, independent of where the ball landed. For walks, strikeouts, and
  other non-batted events, xR uses historical run values. A red row means the
  team with higher xR lost. Click any game to see the cumulative xR chart.</p>
  <p style="margin-top:0.5rem">Data from MLB Stats API &amp; Statcast. Updated automatically.</p>
</footer>
<script>
function toggle(gpk) {{
  var chart = document.getElementById('chart-' + gpk);
  var row = document.querySelector('tr[data-gpk="' + gpk + '"]');
  if (chart.style.display === 'none') {{
    chart.style.display = '';
    row.classList.add('expanded');
  }} else {{
    chart.style.display = 'none';
    row.classList.remove('expanded');
  }}
}}
</script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(html)

    print(f"  Site regenerated: docs/index.html ({total_games} games, {mismatch_count} mismatches)")
