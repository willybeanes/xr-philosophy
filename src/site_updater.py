"""Regenerate the GitHub Pages dashboard from scores data."""

import json
import os
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta

from src.bluesky_poster import TEAM_ABBR, TEAM_COLORS, TEAM_IDS

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
SCORES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scores.json")


def load_scores() -> list[dict]:
    if not os.path.exists(SCORES_PATH):
        return []
    with open(SCORES_PATH) as f:
        return json.load(f)


def save_score(game: dict, away_xr: float, home_xr: float,
               chart_data: list | None = None) -> None:
    scores = load_scores()
    existing_pks = {s["gamePk"] for s in scores}
    if game["gamePk"] in existing_pks:
        return
    entry = {
        "gamePk": game["gamePk"],
        "date": game.get("game_date", date.today().isoformat()),
        "away_team": game["away_team"],
        "home_team": game["home_team"],
        "away_abbr": TEAM_ABBR.get(game["away_team"], game.get("away_abbr", "")),
        "home_abbr": TEAM_ABBR.get(game["home_team"], game.get("home_abbr", "")),
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


def _get_abbr(g: dict, side: str) -> str:
    name = g[f"{side}_team"]
    abbr = g.get(f"{side}_abbr", "")
    return TEAM_ABBR.get(name, abbr or name.split()[-1][:3].upper())


def _get_color(team_name: str, fallback: str) -> str:
    return TEAM_COLORS.get(team_name, fallback)


def _generate_chart_svg(g: dict) -> str:
    cd = g.get("chart_data")
    if not cd:
        return ""

    away_abbr = _get_abbr(g, "away")
    home_abbr = _get_abbr(g, "home")
    away_color = _get_color(g["away_team"], "#2563eb")
    home_color = _get_color(g["home_team"], "#dc2626")

    points = [{"pa": 0, "a_xr": 0, "h_xr": 0, "a_r": 0, "h_r": 0, "inn": 1}]
    for p in cd:
        points.append({
            "pa": p["pa"], "a_xr": p["a_xr"], "h_xr": p["h_xr"],
            "a_r": p["a_r"], "h_r": p["h_r"], "inn": p["inn"],
        })

    inning_starts = {}
    for p in cd:
        if p["inn"] not in inning_starts:
            inning_starts[p["inn"]] = p["pa"]

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

    def sx(pa): return PL + (pa / max_pa) * PW
    def sy(val): return PT + PH - (val / max_y) * PH

    def step_path(pts, key):
        parts = []
        for i, p in enumerate(pts):
            x = sx(p["pa"]); y = sy(p[key])
            parts.append(f"M {x:.1f} {y:.1f}" if i == 0 else f"H {x:.1f} V {y:.1f}")
        return " ".join(parts)

    step = 2 if max_y > 6 else 1
    y_grid = ""
    for v in range(0, int(max_y) + 1, step):
        y = sy(v)
        y_grid += f'<line x1="{PL}" y1="{y:.0f}" x2="{W-PR}" y2="{y:.0f}" stroke="#e5e7eb" stroke-width="0.5"/>'
        y_grid += f'<text x="{PL-6}" y="{y+4:.0f}" text-anchor="end" fill="#9ca3af" font-size="10">{v}</text>'

    inn_svg = ""
    for inn, pa_start in inning_starts.items():
        x = sx(pa_start)
        inn_svg += f'<line x1="{x:.0f}" y1="{PT}" x2="{x:.0f}" y2="{PT+PH}" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="3,3"/>'
        next_start = inning_starts.get(inn + 1, max_pa)
        mid = sx((pa_start + next_start) / 2)
        inn_svg += f'<text x="{mid:.0f}" y="{PT+PH+14}" text-anchor="middle" fill="#9ca3af" font-size="10">{inn}</text>'

    last = points[-1]
    positions = [
        ("a_xr", away_color, f'{last["a_xr"]:.1f}', "1"),
        ("a_r", away_color, f'{last["a_r"]}', "0.6"),
        ("h_xr", home_color, f'{last["h_xr"]:.1f}', "1"),
        ("h_r", home_color, f'{last["h_r"]}', "0.6"),
    ]
    labels = ""
    used_y = []
    for key, color, text, opacity in positions:
        y = sy(last[key])
        for uy in used_y:
            if abs(y - uy) < 12:
                y = uy - 12 if y < uy else uy + 12
        used_y.append(y)
        labels += f'<text x="{W-PR+4}" y="{y+4:.0f}" fill="{color}" font-size="10" font-weight="600" opacity="{opacity}">{text}</text>'

    FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;font-family:{FONT}">
{y_grid}{inn_svg}
<path d="{step_path(points, 'a_r')}" fill="none" stroke="{away_color}" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.65"/>
<path d="{step_path(points, 'h_r')}" fill="none" stroke="{home_color}" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.65"/>
<path d="{step_path(points, 'a_xr')}" fill="none" stroke="{away_color}" stroke-width="2.5"/>
<path d="{step_path(points, 'h_xr')}" fill="none" stroke="{home_color}" stroke-width="2.5"/>
{labels}
<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+PH}" stroke="#d1d5db" stroke-width="1"/>
<line x1="{PL}" y1="{PT+PH}" x2="{W-PR}" y2="{PT+PH}" stroke="#d1d5db" stroke-width="1"/>
<line x1="{PL+6}" y1="{PT+7}" x2="{PL+22}" y2="{PT+7}" stroke="{away_color}" stroke-width="2.5"/>
<text x="{PL+25}" y="{PT+10}" fill="{away_color}" font-size="10" font-weight="600">{away_abbr} xR</text>
<line x1="{PL+72}" y1="{PT+7}" x2="{PL+88}" y2="{PT+7}" stroke="{away_color}" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.65"/>
<text x="{PL+91}" y="{PT+10}" fill="{away_color}" font-size="10" opacity="0.5">{away_abbr} actual</text>
<line x1="{PL+160}" y1="{PT+7}" x2="{PL+176}" y2="{PT+7}" stroke="{home_color}" stroke-width="2.5"/>
<text x="{PL+179}" y="{PT+10}" fill="{home_color}" font-size="10" font-weight="600">{home_abbr} xR</text>
<line x1="{PL+226}" y1="{PT+7}" x2="{PL+242}" y2="{PT+7}" stroke="{home_color}" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.65"/>
<text x="{PL+245}" y="{PT+10}" fill="{home_color}" font-size="10" opacity="0.5">{home_abbr} actual</text>
</svg>"""


def _is_mismatch(g: dict) -> bool:
    if g["away_score"] == g["home_score"] or g["away_xr"] == g["home_xr"]:
        return False
    return (g["away_score"] > g["home_score"]) != (g["away_xr"] > g["home_xr"])


def _build_teams_table(scores: list) -> str:
    """Build the Teams tab HTML with sortable per-team stats."""
    teams = defaultdict(lambda: {
        "games": 0, "xr": 0.0, "xr_allowed": 0.0,
        "runs": 0, "runs_allowed": 0,
    })

    for s in scores:
        # Away team
        aw = s["away_team"]
        teams[aw]["games"] += 1
        teams[aw]["xr"] += s["away_xr"]
        teams[aw]["xr_allowed"] += s["home_xr"]
        teams[aw]["runs"] += s["away_score"]
        teams[aw]["runs_allowed"] += s["home_score"]

        # Home team
        hm = s["home_team"]
        teams[hm]["games"] += 1
        teams[hm]["xr"] += s["home_xr"]
        teams[hm]["xr_allowed"] += s["away_xr"]
        teams[hm]["runs"] += s["home_score"]
        teams[hm]["runs_allowed"] += s["away_score"]

    rows = ""
    for name in sorted(teams.keys()):
        t = teams[name]
        g = t["games"]
        if g == 0:
            continue
        xr_pg = t["xr"] / g
        xra_pg = t["xr_allowed"] / g
        r_pg = t["runs"] / g
        ra_pg = t["runs_allowed"] / g
        diff_bat = xr_pg - r_pg    # positive = underperforming (xR > R)
        diff_pitch = xra_pg - ra_pg  # positive = pitching overperforming (xRA > RA)
        rows += (
            f'<tr>'
            f'<td class="team-name">{name}</td>'
            f'<td class="num">{g}</td>'
            f'<td class="num">{xr_pg:.2f}</td>'
            f'<td class="num">{xra_pg:.2f}</td>'
            f'<td class="num">{r_pg:.2f}</td>'
            f'<td class="num">{ra_pg:.2f}</td>'
            f'<td class="num diff">{diff_bat:+.2f}</td>'
            f'<td class="num diff">{diff_pitch:+.2f}</td>'
            f'</tr>\n'
        )
    return rows


def _build_scatter_svg(scores: list, x_key: str, y_key: str,
                       x_label: str, y_label: str, title: str,
                       invert_y: bool = False) -> str:
    """Build an SVG scatter plot with team logos as markers."""
    teams = defaultdict(lambda: {"games": 0, "xr": 0.0, "xr_allowed": 0.0,
                                  "runs": 0, "runs_allowed": 0})
    for s in scores:
        for side, opp in [("away", "home"), ("home", "away")]:
            name = s[f"{side}_team"]
            teams[name]["games"] += 1
            teams[name]["xr"] += s[f"{side}_xr"]
            teams[name]["xr_allowed"] += s[f"{opp}_xr"]
            teams[name]["runs"] += s[f"{side}_score"]
            teams[name]["runs_allowed"] += s[f"{opp}_score"]

    points = []
    for name, t in teams.items():
        g = t["games"]
        if g == 0:
            continue
        vals = {
            "xr_pg": t["xr"] / g, "xra_pg": t["xr_allowed"] / g,
            "r_pg": t["runs"] / g, "ra_pg": t["runs_allowed"] / g,
        }
        team_id = TEAM_IDS.get(name, 0)
        abbr = TEAM_ABBR.get(name, "???")
        points.append({"name": name, "abbr": abbr, "id": team_id,
                        "x": vals[x_key], "y": vals[y_key]})

    if not points:
        return ""

    W = 680; H = 580
    PL = 52; PR = 20; PT = 36; PB = 44
    PW = W - PL - PR; PH = H - PT - PB
    LOGO = 28  # logo size

    all_x = [p["x"] for p in points]
    all_y = [p["y"] for p in points]
    pad = 0.3
    x_min = min(all_x) - pad; x_max = max(all_x) + pad
    y_min = min(all_y) - pad; y_max = max(all_y) + pad

    def sx(v): return PL + (v - x_min) / (x_max - x_min) * PW
    if invert_y:
        def sy(v): return PT + (v - y_min) / (y_max - y_min) * PH  # lower values at top
    else:
        def sy(v): return PT + PH - (v - y_min) / (y_max - y_min) * PH

    FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'

    # Grid lines
    import math
    grid = ""
    step = 0.5 if (x_max - x_min) < 5 else 1.0
    v = math.ceil(x_min / step) * step
    while v <= x_max:
        x = sx(v)
        grid += f'<line x1="{x:.0f}" y1="{PT}" x2="{x:.0f}" y2="{PT+PH}" stroke="#eee" stroke-width="0.5"/>'
        grid += f'<text x="{x:.0f}" y="{PT+PH+16}" text-anchor="middle" fill="#aaa" font-size="10">{v:.1f}</text>'
        v += step

    v = math.ceil(y_min / step) * step
    while v <= y_max:
        y = sy(v)
        grid += f'<line x1="{PL}" y1="{y:.0f}" x2="{PL+PW}" y2="{y:.0f}" stroke="#eee" stroke-width="0.5"/>'
        grid += f'<text x="{PL-6}" y="{y+4:.0f}" text-anchor="end" fill="#aaa" font-size="10">{v:.1f}</text>'
        v += step

    # Diagonal reference line (x = y)
    diag_start_x = max(x_min, y_min)
    diag_end_x = min(x_max, y_max)
    diag = ""
    if diag_start_x < diag_end_x:
        diag = (
            f'<line x1="{sx(diag_start_x):.0f}" y1="{sy(diag_start_x):.0f}" '
            f'x2="{sx(diag_end_x):.0f}" y2="{sy(diag_end_x):.0f}" '
            f'stroke="#ddd" stroke-width="1" stroke-dasharray="4,4"/>'
        )

    # Team logos
    logos = ""
    for p in points:
        x = sx(p["x"]) - LOGO / 2
        y = sy(p["y"]) - LOGO / 2
        logo_url = f"https://www.mlbstatic.com/team-logos/{p['id']}.svg"
        logos += (
            f'<image href="{logo_url}" x="{x:.0f}" y="{y:.0f}" '
            f'width="{LOGO}" height="{LOGO}"/>'
        )

    return f"""<div class="scatter-wrap">
<div class="scatter-title">{title}</div>
<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;font-family:{FONT}">
{grid}{diag}{logos}
<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+PH}" stroke="#d1d5db" stroke-width="1"/>
<line x1="{PL}" y1="{PT+PH}" x2="{PL+PW}" y2="{PT+PH}" stroke="#d1d5db" stroke-width="1"/>
<text x="{PL+PW/2}" y="{H-4}" text-anchor="middle" fill="#999" font-size="11">{x_label}</text>
<text x="12" y="{PT+PH/2}" text-anchor="middle" fill="#999" font-size="11" transform="rotate(-90,12,{PT+PH/2})">{y_label}</text>
</svg></div>"""


def regenerate_site() -> None:
    scores = load_scores()

    by_date: dict[str, list] = {}
    for s in scores:
        by_date.setdefault(s["date"], []).append(s)

    total_games = len(scores)
    mismatch_count = sum(1 for s in scores if _is_mismatch(s))
    mismatch_pct = (mismatch_count / total_games * 100) if total_games else 0

    # ── Games tab rows ──
    games_rows = ""
    sorted_dates = sorted(by_date.keys(), reverse=True)
    for date_idx, game_date in enumerate(sorted_dates):
        collapsed = date_idx >= 2
        date_id = game_date.replace("-", "")
        arrow_char = "&#9656;" if collapsed else "&#9662;"
        game_count = len(by_date[game_date])
        count_label = f' <span class="date-count">({game_count})</span>' if collapsed else ""

        games_rows += (
            f'<tr class="date-header" onclick="toggleDate(\'{date_id}\')">'
            f'<td colspan="5"><span class="date-arrow" id="arrow-{date_id}">{arrow_char}</span> '
            f'{game_date}{count_label}</td></tr>\n'
        )

        hide = ' style="display:none"' if collapsed else ""
        for g in by_date[game_date]:
            gpk = g["gamePk"]
            mismatch_cls = " mismatch" if _is_mismatch(g) else ""
            has_chart = "chart_data" in g and g["chart_data"]
            click = f' onclick="event.stopPropagation();toggle({gpk})"' if has_chart else ""
            arrow = ' <span class="arrow">&#9656;</span>' if has_chart else ""

            games_rows += (
                f'<tr class="date-group date-{date_id}{mismatch_cls}"{click} data-gpk="{gpk}"{hide}>'
                f'<td class="team away">{g["away_team"]}{arrow}</td>'
                f'<td class="xr">{g["away_xr"]:.2f}</td>'
                f'<td class="score">{g["away_score"]} &ndash; {g["home_score"]}</td>'
                f'<td class="xr">{g["home_xr"]:.2f}</td>'
                f'<td class="team home">{g["home_team"]}</td>'
                f"</tr>\n"
            )
            if has_chart:
                svg = _generate_chart_svg(g)
                games_rows += (
                    f'<tr class="chart-row date-group date-{date_id}" id="chart-{gpk}" style="display:none">'
                    f'<td colspan="5" class="chart-cell">{svg}</td></tr>\n'
                )

    # ── Teams tab rows ──
    teams_rows = _build_teams_table(scores)

    # ── Graphs tab ──
    scatter_xr = _build_scatter_svg(scores, "xr_pg", "r_pg", "xR/G", "R/G", "xR vs Actual Runs")
    scatter_xra = _build_scatter_svg(scores, "xra_pg", "ra_pg", "xRA/G", "RA/G", "xRA vs Actual Runs Allowed")
    scatter_xr_xra = _build_scatter_svg(scores, "xr_pg", "xra_pg", "xR/G", "xRA/G", "xR vs xRA")

    stats_html = (
        f'<div class="stats">{total_games} games'
        f' &middot; {mismatch_count} xR mismatches ({mismatch_pct:.1f}%)</div>'
    ) if total_games else ""

    # Timestamp in ET
    et = timezone(timedelta(hours=-4))
    now_et = datetime.now(et).strftime("%b %d, %Y %I:%M %p ET")
    updated_html = f'<div class="last-updated">Last updated: {now_et}</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>xR Philosophy</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='80' font-size='80'>&#9918;</text></svg>">
<style>
:root {{
  --bg: #ffffff; --surface: #f5f5f5; --text: #111111;
  --text-secondary: #666666; --border: #e0e0e0;
  --red: #dc2f1f; --red-bg: #fff0f0; --accent: #333;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  max-width: 720px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.5;
}}
header {{
  text-align: center; margin-bottom: 1rem;
  border-bottom: 2px solid var(--red); padding-bottom: 1.5rem;
}}
h1 {{ font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; }}
h1 span {{ color: var(--red); }}
.subtitle {{ color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem; }}
.stats {{ color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem; }}

/* Tabs */
.tabs {{
  display: flex; gap: 0; margin-bottom: 0.75rem; border-bottom: 1px solid var(--border);
}}
.tab {{
  padding: 0.5rem 1.2rem; cursor: pointer; font-size: 0.9rem; font-weight: 600;
  color: var(--text-secondary); border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--text); border-bottom-color: var(--red); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Expand all */
.toolbar {{
  display: flex; justify-content: flex-end; margin-bottom: 0.5rem;
}}
.expand-btn {{
  background: none; border: 1px solid var(--border); border-radius: 4px;
  padding: 0.25rem 0.6rem; font-size: 0.75rem; color: var(--text-secondary);
  cursor: pointer;
}}
.expand-btn:hover {{ background: var(--surface); color: var(--text); }}

/* Games table */
table {{ width: 100%; border-collapse: collapse; margin-bottom: 1rem; }}
thead {{ position: sticky; top: 0; z-index: 1; background: var(--bg); }}
th {{
  text-align: left; font-size: 0.75rem; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-secondary);
  padding: 0.5rem 0.4rem; border-bottom: 1px solid var(--border);
}}
td {{ padding: 0.6rem 0.4rem; border-bottom: 1px solid var(--border); font-size: 0.95rem; }}
.date-header {{ cursor: pointer; }}
.date-header:hover {{ background: #eee; }}
.date-header td {{
  font-weight: 700; font-size: 0.85rem; color: var(--text-secondary);
  background: var(--surface); padding: 0.4rem;
}}
.date-arrow {{ display: inline-block; font-size: 0.7rem; width: 1em; transition: transform 0.15s; }}
.date-count {{ font-weight: 400; font-size: 0.8rem; }}
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
tr[onclick] {{ cursor: pointer; }}
tr[onclick]:hover {{ background: var(--surface); }}
tr.mismatch[onclick]:hover {{ background: var(--red-bg); }}
.arrow {{ font-size: 0.7rem; color: var(--text-secondary); transition: transform 0.15s; display: inline-block; }}
tr.expanded .arrow {{ transform: rotate(90deg); }}
.chart-row {{ border-bottom: 1px solid var(--border); }}
.chart-cell {{ padding: 0.5rem 0; background: var(--surface); text-align: center; }}

/* Teams table */
#teams-tab table {{ margin-top: 0.5rem; }}
#teams-tab th {{ cursor: pointer; user-select: none; }}
#teams-tab th:hover {{ color: var(--text); }}
#teams-tab th.sorted-asc::after {{ content: " \\25B2"; font-size: 0.6rem; }}
#teams-tab th.sorted-desc::after {{ content: " \\25BC"; font-size: 0.6rem; }}
.team-name {{ font-weight: 600; }}
.diff {{ font-weight: 600; }}

/* Graphs tab */
.scatter-grid {{ display: flex; flex-direction: column; gap: 2rem; }}
.scatter-wrap {{ text-align: center; }}
.scatter-title {{ font-weight: 700; font-size: 1rem; margin-bottom: 0.5rem; }}
.scatter-note {{ color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem; text-align: center; }}
.last-updated {{ color: var(--text-secondary); font-size: 0.75rem; text-align: right; margin-top: 1rem; }}
.num {{
  font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
  text-align: center; font-size: 0.85rem;
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

<div class="tabs">
  <div class="tab active" onclick="switchTab('games',this)">Games</div>
  <div class="tab" onclick="switchTab('teams',this)">Teams</div>
  <div class="tab" onclick="switchTab('graphs',this)">Graphs</div>
</div>

<div id="games-tab" class="tab-content active">
  <div class="toolbar">
    <button class="expand-btn" onclick="expandAll()">Expand all</button>
  </div>
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
      {games_rows if games_rows else '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:2rem">No games recorded yet.</td></tr>'}
    </tbody>
  </table>
</div>

<div id="teams-tab" class="tab-content">
  <table id="teams-table">
    <thead>
      <tr>
        <th onclick="sortTeams(0)" class="sorted-asc">Team</th>
        <th onclick="sortTeams(1)" style="text-align:center">G</th>
        <th onclick="sortTeams(2)" style="text-align:center">xR/G</th>
        <th onclick="sortTeams(3)" style="text-align:center">xRA/G</th>
        <th onclick="sortTeams(4)" style="text-align:center">R/G</th>
        <th onclick="sortTeams(5)" style="text-align:center">RA/G</th>
        <th onclick="sortTeams(6)" style="text-align:center">xR-R/G</th>
        <th onclick="sortTeams(7)" style="text-align:center">xRA-RA/G</th>
      </tr>
    </thead>
    <tbody>
      {teams_rows}
    </tbody>
  </table>
  {updated_html}
</div>

<div id="graphs-tab" class="tab-content">
  <div class="scatter-grid">
    {scatter_xr}
    {scatter_xra}
    {scatter_xr_xra}
  </div>
  <p class="scatter-note">First two charts: dashed line = xR matches actual. Third chart: top-left = best (high xR, low xRA).</p>
  {updated_html}
</div>

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
    chart.style.display = ''; row.classList.add('expanded');
  }} else {{
    chart.style.display = 'none'; row.classList.remove('expanded');
  }}
}}
function toggleDate(dateId) {{
  var rows = document.querySelectorAll('.date-' + dateId + ':not(.chart-row)');
  var arrow = document.getElementById('arrow-' + dateId);
  var isHidden = rows.length > 0 && rows[0].style.display === 'none';
  rows.forEach(function(r) {{ r.style.display = isHidden ? '' : 'none'; }});
  if (!isHidden) {{
    document.querySelectorAll('.date-' + dateId + '.chart-row').forEach(function(c) {{ c.style.display = 'none'; }});
    document.querySelectorAll('.date-' + dateId + '[data-gpk]').forEach(function(r) {{ r.classList.remove('expanded'); }});
  }}
  arrow.innerHTML = isHidden ? '&#9662;' : '&#9656;';
}}
function expandAll() {{
  var btn = document.querySelector('.expand-btn');
  var expanding = btn.textContent === 'Expand all';
  document.querySelectorAll('.date-header').forEach(function(hdr) {{
    var dateId = hdr.querySelector('.date-arrow').id.replace('arrow-', '');
    var rows = document.querySelectorAll('.date-' + dateId + ':not(.chart-row)');
    var arrow = document.getElementById('arrow-' + dateId);
    if (expanding) {{
      rows.forEach(function(r) {{ r.style.display = ''; }});
      arrow.innerHTML = '&#9662;';
    }} else {{
      rows.forEach(function(r) {{ r.style.display = 'none'; }});
      document.querySelectorAll('.date-' + dateId + '.chart-row').forEach(function(c) {{ c.style.display = 'none'; }});
      document.querySelectorAll('.date-' + dateId + '[data-gpk]').forEach(function(r) {{ r.classList.remove('expanded'); }});
      arrow.innerHTML = '&#9656;';
    }}
  }});
  btn.textContent = expanding ? 'Collapse all' : 'Expand all';
}}
function switchTab(tab, el) {{
  document.querySelectorAll('.tab').forEach(function(t) {{ t.classList.remove('active'); }});
  document.querySelectorAll('.tab-content').forEach(function(c) {{ c.classList.remove('active'); }});
  document.querySelector('#' + tab + '-tab').classList.add('active');
  if (el) el.classList.add('active');
}}
var sortDir = {{}};
function sortTeams(col) {{
  var table = document.getElementById('teams-table');
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var ths = table.querySelectorAll('th');
  sortDir[col] = sortDir[col] === 'asc' ? 'desc' : 'asc';
  var dir = sortDir[col];
  ths.forEach(function(th) {{ th.classList.remove('sorted-asc', 'sorted-desc'); }});
  ths[col].classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
  rows.sort(function(a, b) {{
    var aVal = a.cells[col].textContent.trim();
    var bVal = b.cells[col].textContent.trim();
    var aNum = parseFloat(aVal); var bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {{
      return dir === 'asc' ? aNum - bNum : bNum - aNum;
    }}
    return dir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  }});
  rows.forEach(function(r) {{ tbody.appendChild(r); }});
}}
</script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(html)
    print(f"  Site regenerated: docs/index.html ({total_games} games, {mismatch_count} mismatches)")
