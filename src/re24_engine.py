"""Event-based xR (expected runs) engine — the baseball analog of soccer's xG.

For each plate appearance, xR credits the team with the AVERAGE RUN VALUE of
that event type (single, double, HR, walk, etc.) in that base-out context.

Run value = runs_scored + RE_after - RE_before, averaged across historical
occurrences of that event in that context. This credits both direct run
production AND state improvement (e.g., a walk improves RE by ~0.33 even
though no run scores).

Because we use the AVERAGE run value rather than the ACTUAL outcome, xR can
diverge from actual runs — measuring what events typically produce, not what
they produced in this specific game.
"""

import json
import os

# Standard MLB Run Expectancy Matrix (2010-2019 averages)
# Used for supplementary RE24 calculation and fallback estimates
RE_MATRIX = {
    ("___", 0): 0.481, ("___", 1): 0.254, ("___", 2): 0.098,
    ("1__", 0): 0.859, ("1__", 1): 0.509, ("1__", 2): 0.224,
    ("_2_", 0): 1.100, ("_2_", 1): 0.664, ("_2_", 2): 0.319,
    ("__3", 0): 1.350, ("__3", 1): 0.950, ("__3", 2): 0.350,
    ("12_", 0): 1.437, ("12_", 1): 0.884, ("12_", 2): 0.429,
    ("1_3", 0): 1.784, ("1_3", 1): 1.130, ("1_3", 2): 0.478,
    ("_23", 0): 1.964, ("_23", 1): 1.376, ("_23", 2): 0.580,
    ("123", 0): 2.292, ("123", 1): 1.541, ("123", 2): 0.752,
}

RE_EMPTY_ZERO = RE_MATRIX[("___", 0)]

BASE_MAP = {"1B": 1, "2B": 2, "3B": 3}

# Load event run value table (built from ~5000 PAs of real MLB data)
# Each entry: avg run value = avg(runs_scored + RE_after - RE_before) for that event+context
_RV_TABLE = {}
_rv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "event_run_values.json")
if os.path.exists(_rv_path):
    with open(_rv_path) as _f:
        _RV_TABLE = json.load(_f)


def bases_to_string(occupied: set) -> str:
    """Convert a set of occupied bases (1, 2, 3) to a bases string like '1_3'."""
    return "".join(str(b) if b in occupied else "_" for b in (1, 2, 3))


def _lookup_run_value(event_type: str, bases_str: str, outs: int) -> float:
    """Look up average run value for an event in context.

    Run value = avg(runs_scored + RE_after - RE_before) for historical
    occurrences of this event in this base-out context.

    Uses hierarchical fallback:
      1. Full context: (event_type, bases, outs) — most specific
      2. Event + outs: (event_type, *, outs) — when base state is rare
      3. Event only: (event_type, *, *) — broadest fallback
      4. Zero — truly unknown event types
    """
    # Level 1: full context
    key1 = f"{event_type}|{bases_str}|{outs}"
    entry = _RV_TABLE.get(key1)
    if entry and entry["n"] >= 3:
        return entry["avg_rv"]

    # Level 2: event + outs
    key2 = f"{event_type}||{outs}"
    entry = _RV_TABLE.get(key2)
    if entry and entry["n"] >= 5:
        return entry["avg_rv"]

    # Level 3: event only
    key3 = f"{event_type}||"
    entry = _RV_TABLE.get(key3)
    if entry:
        return entry["avg_rv"]

    return 0.0


def _apply_runners(current_bases: set, runners: list) -> tuple[set, int]:
    """Apply runner movements to compute post-play base state and actual runs scored."""
    vacated = set()
    new_occupied = set()
    runs_scored = 0

    for runner in runners:
        movement = runner.get("movement", {})
        details = runner.get("details", {})
        origin = movement.get("originBase")
        end = movement.get("end")
        is_out = movement.get("isOut", False)

        if origin in BASE_MAP:
            vacated.add(BASE_MAP[origin])

        if is_out:
            continue

        if details.get("isScoringEvent", False):
            runs_scored += 1
        elif end in BASE_MAP:
            new_occupied.add(BASE_MAP[end])

    bases_after = (current_bases - vacated) | new_occupied
    return bases_after, runs_scored


def calculate_xr(plays: list) -> dict:
    """Calculate event-based xR for each team from play-by-play data.

    For each plate appearance:
    - Look up the average run value (runs_scored + RE_after - RE_before)
      for that event type in that base-out context
    - Credit that average to the batting team (this is the xR contribution)
    - Track actual base-out state changes for subsequent PA context
    - Add the per-inning baseline (RE at empty/0 outs) so xR is on an
      absolute scale comparable to actual runs

    This means xR can diverge from actual runs — it measures what the
    team's events typically produce, not what they produced in this game.

    Args:
        plays: List of play dicts from MLB API (liveData.plays.allPlays).

    Returns:
        dict with keys:
            away_xr, home_xr: event-based expected runs (rounded to 1 decimal)
            away_actual, home_actual: actual runs scored (for comparison)
    """
    away_rv = 0.0   # sum of run values (RE24-style, centered around 0)
    home_rv = 0.0
    away_actual = 0
    home_actual = 0
    away_innings = 0
    home_innings = 0

    prev_half_inning = None
    current_outs = 0
    current_bases = set()

    for play in plays:
        result = play.get("result", {})
        about = play.get("about", {})
        count = play.get("count", {})
        runners = play.get("runners", [])

        if result.get("type") != "atBat":
            continue

        is_top = about.get("isTopInning", True)
        half_inning_key = (about.get("inning"), is_top)

        # Reset state at half-inning boundaries
        if half_inning_key != prev_half_inning:
            current_outs = 0
            current_bases = set()
            prev_half_inning = half_inning_key
            if is_top:
                away_innings += 1
            else:
                home_innings += 1

        event_type = result.get("eventType", "")
        bases_str = bases_to_string(current_bases)

        # Look up average run value for this event in this context
        run_value = _lookup_run_value(event_type, bases_str, current_outs)

        if is_top:
            away_rv += run_value
        else:
            home_rv += run_value

        # Track ACTUAL state changes (so next PA has correct context)
        bases_after, actual_runs = _apply_runners(current_bases, runners)

        if is_top:
            away_actual += actual_runs
        else:
            home_actual += actual_runs

        outs_after = count.get("outs", current_outs)
        if outs_after >= 3:
            current_outs = 0
            current_bases = set()
        else:
            current_outs = outs_after
            current_bases = bases_after

    # Convert from run value (centered ~0) to absolute xR by adding baseline
    # Each half-inning starts with RE(empty, 0 outs) of expected runs
    away_xr = max(0.0, away_rv + away_innings * RE_EMPTY_ZERO)
    home_xr = max(0.0, home_rv + home_innings * RE_EMPTY_ZERO)

    return {
        "away_xr": round(away_xr, 2),
        "home_xr": round(home_xr, 2),
        "away_actual": away_actual,
        "home_actual": home_actual,
    }
