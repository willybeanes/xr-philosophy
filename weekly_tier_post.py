#!/usr/bin/env python3
"""Post the weekly xR vs xRA tier chart to Bluesky on Monday mornings."""

import os
from datetime import date, timedelta, timezone, datetime
from io import BytesIO
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont
from atproto import Client

from src.site_updater import load_scores
from src.bluesky_poster import TEAM_ABBR, TEAM_COLORS, TEAM_IDS

# ET timezone
ET = timezone(timedelta(hours=-4))


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def build_tier_chart(scores: list) -> bytes:
    """Render the xR vs xRA tier scatter plot as PNG."""
    # Aggregate team stats
    teams = defaultdict(lambda: {"games": 0, "xr": 0.0, "xr_allowed": 0.0})
    for s in scores:
        for side, opp in [("away", "home"), ("home", "away")]:
            name = s[f"{side}_team"]
            teams[name]["games"] += 1
            teams[name]["xr"] += s[f"{side}_xr"]
            teams[name]["xr_allowed"] += s[f"{opp}_xr"]

    points = []
    for name, t in teams.items():
        g = t["games"]
        if g == 0:
            continue
        points.append({
            "name": name,
            "abbr": TEAM_ABBR.get(name, "???"),
            "x": t["xr"] / g,
            "y": t["xr_allowed"] / g,
        })

    # Chart dimensions
    W = 1200; H = 1200
    PL = 80; PR = 60; PT = 100; PB = 70
    PW = W - PL - PR; PH = H - PT - PB

    all_x = [p["x"] for p in points]
    all_y = [p["y"] for p in points]
    pad = 0.4
    x_min = min(all_x) - pad; x_max = max(all_x) + pad
    y_min = min(all_y) - pad; y_max = max(all_y) + pad

    def sx(v): return PL + (v - x_min) / (x_max - x_min) * PW
    def sy(v): return PT + PH - (v - y_min) / (y_max - y_min) * PH

    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_sm = font; font_title = font; font_sub = font

    # Title
    yesterday = (datetime.now(ET) - timedelta(days=1)).date()
    title = "xR vs xRA Tiers"
    subtitle = f"Season through {yesterday.isoformat()}"
    draw.text((W // 2, 24), title, fill=(17, 17, 17), font=font_title, anchor="ma")
    draw.text((W // 2, 64), subtitle, fill=(120, 120, 120), font=font_sub, anchor="ma")

    # Grid
    import math
    step = 0.5 if (x_max - x_min) < 5 else 1.0
    v = math.ceil(x_min / step) * step
    while v <= x_max:
        x = sx(v)
        draw.line([(x, PT), (x, PT + PH)], fill=(240, 240, 240), width=1)
        draw.text((x, PT + PH + 8), f"{v:.1f}", fill=(170, 170, 170), font=font_sm, anchor="ma")
        v += step
    v = math.ceil(y_min / step) * step
    while v <= y_max:
        y = sy(v)
        draw.line([(PL, y), (PL + PW, y)], fill=(240, 240, 240), width=1)
        draw.text((PL - 8, y), f"{v:.1f}", fill=(170, 170, 170), font=font_sm, anchor="ra")
        v += step

    # Tier lines (y = x + offset, spaced at 1.0)
    tier_step = 1.0
    min_offset = math.floor((y_min - x_max) / tier_step) * tier_step
    max_offset = math.ceil((y_max - x_min) / tier_step) * tier_step
    offset = min_offset
    while offset <= max_offset:
        lx1 = max(x_min, y_min - offset)
        lx2 = min(x_max, y_max - offset)
        if lx1 < lx2:
            ly1 = lx1 + offset; ly2 = lx2 + offset
            w = 2 if abs(offset) < 0.01 else 1
            # Dashed line
            x1p, y1p = sx(lx1), sy(ly1)
            x2p, y2p = sx(lx2), sy(ly2)
            length = ((x2p - x1p)**2 + (y2p - y1p)**2)**0.5
            if length > 0:
                dx = (x2p - x1p) / length
                dy = (y2p - y1p) / length
                d = 0
                while d < length:
                    seg_end = min(d + 10, length)
                    draw.line([
                        (x1p + dx * d, y1p + dy * d),
                        (x1p + dx * seg_end, y1p + dy * seg_end)
                    ], fill=(200, 200, 200), width=w)
                    d = seg_end + 8
        offset += tier_step

    # Axes
    draw.line([(PL, PT), (PL, PT + PH)], fill=(200, 200, 200), width=2)
    draw.line([(PL, PT + PH), (PL + PW, PT + PH)], fill=(200, 200, 200), width=2)

    # Axis labels
    draw.text((PL + PW // 2, H - 12), "xR/G", fill=(150, 150, 150), font=font, anchor="ma")
    img_txt = Image.new("RGBA", (200, 30), (255, 255, 255, 0))
    txt_draw = ImageDraw.Draw(img_txt)
    txt_draw.text((100, 15), "xRA/G", fill=(150, 150, 150), font=font, anchor="ma")
    img_txt = img_txt.rotate(90, expand=True)
    img.paste(img_txt, (4, PT + PH // 2 - 100), img_txt)

    # Team abbreviations as markers (colored)
    for p in points:
        x = int(sx(p["x"]))
        y = int(sy(p["y"]))
        color = _hex_to_rgb(TEAM_COLORS.get(p["name"], "#333333"))
        draw.text((x, y), p["abbr"], fill=color, font=font, anchor="mm")

    # Watermark
    draw.text((W - 12, H - 12), "xR Philosophy", fill=(200, 200, 200), font=font_sm, anchor="rb")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main():
    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        print("ERROR: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set")
        return

    scores = load_scores()
    if not scores:
        print("No scores to chart")
        return

    yesterday = (datetime.now(ET) - timedelta(days=1)).date()
    print(f"Generating xR vs xRA tier chart (through {yesterday})...")

    png = build_tier_chart(scores)
    print(f"Chart: {len(png) // 1024} KB")

    text = f"xR vs xRA Tiers - Season through {yesterday.isoformat()}"

    client = Client()
    client.login(handle, app_password)
    response = client.send_image(
        text=text,
        image=png,
        image_alt=f"Scatter plot of MLB team xR/G vs xRA/G through {yesterday}",
    )
    print(f"Posted: {response.uri}")


if __name__ == "__main__":
    main()
