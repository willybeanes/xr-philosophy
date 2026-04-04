"""Render cumulative xR charts as PNG images using Pillow.

Produces the same chart as the inline SVG but as a raster image
suitable for uploading to Bluesky.
"""

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from src.bluesky_poster import TEAM_ABBR

# Chart dimensions (2x for retina sharpness)
W = 1440
H = 680
SCALE = 2  # internal scale factor
PL = 84; PR = 80; PT = 50; PB = 72
PW = W - PL - PR
PH = H - PT - PB

# Colors
BLUE = (37, 99, 235)       # #2563eb
RED = (220, 38, 38)        # #dc2626
GRID = (229, 231, 235)     # #e5e7eb
LABEL = (156, 163, 175)    # #9ca3af
AXIS = (209, 213, 219)     # #d1d5db
BG = (255, 255, 255)
BLUE_FAINT = (37, 99, 235, 140)   # 55% opacity
RED_FAINT = (220, 38, 38, 140)


def _get_abbr(name: str) -> str:
    return TEAM_ABBR.get(name, name.split()[-1][:3].upper())


def _sx(pa, max_pa):
    return PL + int((pa / max_pa) * PW)


def _sy(val, max_y):
    return PT + PH - int((val / max_y) * PH)


def _draw_step_line(draw, points, key, max_pa, max_y, color, width, dash=None):
    """Draw a step function line (horizontal then vertical segments)."""
    coords = []
    for p in points:
        x = _sx(p["pa"], max_pa)
        y = _sy(p[key], max_y)
        if coords:
            # Horizontal to new x, then vertical to new y
            prev_x, prev_y = coords[-1]
            coords.append((x, prev_y))
        coords.append((x, y))

    if not dash:
        for i in range(len(coords) - 1):
            draw.line([coords[i], coords[i + 1]], fill=color, width=width)
    else:
        # Draw dashed line manually
        dash_len, gap_len = dash
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            # Each segment is either horizontal or vertical
            if x1 == x2:  # vertical
                total = abs(y2 - y1)
                direction = 1 if y2 > y1 else -1
                drawn = 0
                while drawn < total:
                    seg_end = min(drawn + dash_len, total)
                    draw.line(
                        [(x1, y1 + direction * drawn), (x1, y1 + direction * seg_end)],
                        fill=color, width=width
                    )
                    drawn = seg_end + gap_len
            else:  # horizontal
                total = abs(x2 - x1)
                direction = 1 if x2 > x1 else -1
                drawn = 0
                while drawn < total:
                    seg_end = min(drawn + dash_len, total)
                    draw.line(
                        [(x1 + direction * drawn, y1), (x1 + direction * seg_end, y1)],
                        fill=color, width=width
                    )
                    drawn = seg_end + gap_len


def render_chart_png(game: dict) -> bytes | None:
    """Render a cumulative xR chart as PNG bytes.

    Args:
        game: Score dict with chart_data, team names, scores, xR values.

    Returns:
        PNG image bytes, or None if no chart data.
    """
    cd = game.get("chart_data")
    if not cd:
        return None

    away_abbr = _get_abbr(game["away_team"])
    home_abbr = _get_abbr(game["home_team"])

    # Build point series
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

    max_pa = max(p["pa"] for p in points) or 1
    max_y = max(
        max((p["a_xr"] for p in points), default=1),
        max((p["h_xr"] for p in points), default=1),
        max((p["a_r"] for p in points), default=1),
        max((p["h_r"] for p in points), default=1),
        1
    ) * 1.15

    # Create image
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # Try to load a nice font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except (OSError, IOError):
        try:
            # GitHub Actions Ubuntu
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_sm = font
            font_bold = font

    # Y gridlines
    step = 2 if max_y > 6 else 1
    for v in range(0, int(max_y) + 1, step):
        y = _sy(v, max_y)
        draw.line([(PL, y), (W - PR, y)], fill=GRID, width=1)
        draw.text((PL - 12, y - 10), str(v), fill=LABEL, font=font_sm, anchor="ra")

    # Inning dividers + labels
    for inn, pa_start in inning_starts.items():
        x = _sx(pa_start, max_pa)
        # Dashed vertical line
        for yy in range(PT, PT + PH, 12):
            draw.line([(x, yy), (x, min(yy + 6, PT + PH))], fill=GRID, width=1)
        next_start = inning_starts.get(inn + 1, max_pa)
        mid = _sx((pa_start + next_start) / 2, max_pa)
        draw.text((mid, PT + PH + 8), str(inn), fill=LABEL, font=font_sm, anchor="ma")

    # Draw lines: dashed actuals first (behind), then solid xR
    _draw_step_line(draw, points, "a_r", max_pa, max_y, BLUE_FAINT, 3, dash=(12, 8))
    _draw_step_line(draw, points, "h_r", max_pa, max_y, RED_FAINT, 3, dash=(12, 8))
    _draw_step_line(draw, points, "a_xr", max_pa, max_y, BLUE, 5)
    _draw_step_line(draw, points, "h_xr", max_pa, max_y, RED, 5)

    # Axes
    draw.line([(PL, PT), (PL, PT + PH)], fill=AXIS, width=2)
    draw.line([(PL, PT + PH), (W - PR, PT + PH)], fill=AXIS, width=2)

    # End labels
    last = points[-1]
    end_x = W - PR + 8
    for key, color, fmt in [
        ("a_xr", BLUE, f'{last["a_xr"]:.1f}'),
        ("a_r", BLUE_FAINT, f'{last["a_r"]}'),
        ("h_xr", RED, f'{last["h_xr"]:.1f}'),
        ("h_r", RED_FAINT, f'{last["h_r"]}'),
    ]:
        y = _sy(last[key], max_y)
        draw.text((end_x, y - 10), fmt, fill=color, font=font_bold)

    # Legend
    ly = PT + 2
    lx = PL + 12
    # Away xR (solid)
    draw.line([(lx, ly + 8), (lx + 32, ly + 8)], fill=BLUE, width=5)
    draw.text((lx + 38, ly), f"{away_abbr} xR", fill=BLUE, font=font_bold)
    # Away actual (dashed)
    lx2 = lx + 130
    for dx in range(0, 32, 12):
        draw.line([(lx2 + dx, ly + 8), (lx2 + dx + 6, ly + 8)], fill=BLUE_FAINT, width=3)
    draw.text((lx2 + 38, ly), f"{away_abbr} actual", fill=BLUE_FAINT, font=font_sm)
    # Home xR (solid)
    lx3 = lx + 320
    draw.line([(lx3, ly + 8), (lx3 + 32, ly + 8)], fill=RED, width=5)
    draw.text((lx3 + 38, ly), f"{home_abbr} xR", fill=RED, font=font_bold)
    # Home actual (dashed)
    lx4 = lx + 450
    for dx in range(0, 32, 12):
        draw.line([(lx4 + dx, ly + 8), (lx4 + dx + 6, ly + 8)], fill=RED_FAINT, width=3)
    draw.text((lx4 + 38, ly), f"{home_abbr} actual", fill=RED_FAINT, font=font_sm)

    # Export as PNG bytes
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
