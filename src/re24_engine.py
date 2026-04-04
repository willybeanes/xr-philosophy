"""Statcast-enhanced xR (expected runs) engine — the baseball analog of soccer's xG.

For batted ball events, xR uses exit velocity and launch angle to compute the
PROBABILITY DISTRIBUTION over outcomes (single, double, triple, HR, out), then
credits the probability-weighted average run value. A 110mph lineout gets mostly
hit-value credit; a bloop single gets mostly out-value credit.

For non-batted-ball events (walks, HBP, strikeouts), xR uses the historical
average run value for that event type in the base-out context.

This fully decouples quality of contact from results — measuring what the
batted ball DESERVED to produce, not what it actually produced.
"""

import json
import os

# Standard MLB Run Expectancy Matrix (2010-2019 averages)
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

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Load event run value table (235K PAs across 10 seasons)
_RV_TABLE = {}
_rv_path = os.path.join(_DATA_DIR, "event_run_values.json")
if os.path.exists(_rv_path):
    with open(_rv_path) as _f:
        _RV_TABLE = json.load(_f)

# Load batted ball probability table (33K batted balls with Statcast data)
# Maps (ev_bucket, la_bucket) -> {probs: {single: p, double: p, ...}, n: count}
_BB_PROBS = {}
_bb_path = os.path.join(_DATA_DIR, "batted_ball_probs.json")
if os.path.exists(_bb_path):
    with open(_bb_path) as _f:
        _BB_PROBS = json.load(_f)

# Events that involve a batted ball (have hitData in the API)
_BATTED_BALL_EVENTS = {
    'single', 'double', 'triple', 'home_run',
    'field_out', 'force_out', 'grounded_into_double_play', 'double_play',
    'fielders_choice', 'fielders_choice_out', 'field_error',
    'sac_fly', 'sac_bunt', 'sac_fly_double_play', 'sac_bunt_double_play',
    'triple_play',
}

# Events that don't involve a batted ball (use fixed run values)
_NON_BATTED_EVENTS = {
    'strikeout', 'walk', 'hit_by_pitch', 'intent_walk',
    'catcher_interf', 'caught_stealing_2b', 'caught_stealing_3b',
    'caught_stealing_home', 'stolen_base_2b', 'stolen_base_3b',
    'stolen_base_home', 'wild_pitch', 'passed_ball', 'balk',
    'pickoff_1b', 'pickoff_2b', 'pickoff_3b',
    'strikeout_double_play',
}


def bases_to_string(occupied: set) -> str:
    """Convert a set of occupied bases (1, 2, 3) to a bases string like '1_3'."""
    return "".join(str(b) if b in occupied else "_" for b in (1, 2, 3))


def _ev_bucket(speed: float) -> int:
    """Bucket exit velo into 2mph bins."""
    return (max(50, min(120, int(speed))) // 2) * 2


def _la_bucket(angle: float) -> int:
    """Bucket launch angle into 5-degree bins."""
    a = max(-60, min(80, round(angle)))
    if a >= 0:
        return (a // 5) * 5
    else:
        return -((-a + 4) // 5) * 5


def _lookup_run_value(event_type: str, bases_str: str, outs: int) -> float:
    """Look up average run value for an event in context (non-batted-ball events)."""
    key1 = f"{event_type}|{bases_str}|{outs}"
    entry = _RV_TABLE.get(key1)
    if entry and entry["n"] >= 3:
        return entry["avg_rv"]

    key2 = f"{event_type}||{outs}"
    entry = _RV_TABLE.get(key2)
    if entry and entry["n"] >= 5:
        return entry["avg_rv"]

    key3 = f"{event_type}||"
    entry = _RV_TABLE.get(key3)
    if entry:
        return entry["avg_rv"]

    return 0.0


def _statcast_run_value(
    launch_speed: float, launch_angle: float, bases_str: str, outs: int
) -> float:
    """Compute probability-weighted run value from batted ball Statcast data.

    Looks up P(single), P(double), P(triple), P(HR), P(out) for this exit
    velocity and launch angle, then computes:
        xR = sum( P(outcome) * avg_run_value(outcome, bases, outs) )

    Falls back to the event-based lookup if the EV/LA bucket is too sparse.
    """
    evb = _ev_bucket(launch_speed)
    lab = _la_bucket(launch_angle)
    key = f"{evb}|{lab}"

    entry = _BB_PROBS.get(key)
    if not entry or entry["n"] < 5:
        return None  # Signal to fall back to event-based

    probs = entry["probs"]
    weighted_rv = 0.0

    for outcome, prob in probs.items():
        # Map probability-table outcomes to event_type for run value lookup
        # "out" in prob table covers field_out, force_out, GIDP, sac_fly, etc.
        # Use field_out as the representative out type for run value
        if outcome == "out":
            rv = _lookup_run_value("field_out", bases_str, outs)
        elif outcome == "fielders_choice":
            rv = _lookup_run_value("fielders_choice", bases_str, outs)
        elif outcome == "field_error":
            rv = _lookup_run_value("field_error", bases_str, outs)
        else:
            rv = _lookup_run_value(outcome, bases_str, outs)

        weighted_rv += prob * rv

    return weighted_rv


def _get_hit_data(play: dict) -> dict | None:
    """Extract hitData (launchSpeed, launchAngle) from a play's events."""
    for ev in play.get("playEvents", []):
        hd = ev.get("hitData")
        if hd and hd.get("launchSpeed") is not None and hd.get("launchAngle") is not None:
            return hd
    return None


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
    """Calculate Statcast-enhanced xR for each team.

    For each plate appearance:
    - If it's a batted ball with Statcast data: use probability-weighted run
      value based on exit velocity and launch angle
    - If it's a non-batted-ball event (walk, K, HBP): use historical average
      run value for that event type in context
    - If Statcast data is missing: fall back to event-based run value

    Args:
        plays: List of play dicts from MLB API (liveData.plays.allPlays).

    Returns:
        dict with away_xr, home_xr, away_actual, home_actual, cumulative
    """
    away_rv = 0.0
    home_rv = 0.0
    away_actual = 0
    home_actual = 0
    away_innings = 0
    home_innings = 0
    cumulative = []  # per-PA snapshots for chart generation
    pa_index = 0

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
        run_value = None

        # Try Statcast-based calculation for batted ball events
        if event_type in _BATTED_BALL_EVENTS:
            hit_data = _get_hit_data(play)
            if hit_data:
                run_value = _statcast_run_value(
                    hit_data["launchSpeed"],
                    hit_data["launchAngle"],
                    bases_str,
                    current_outs,
                )

        # Fall back to event-based run value if no Statcast data or sparse bucket
        if run_value is None:
            run_value = _lookup_run_value(event_type, bases_str, current_outs)

        if is_top:
            away_rv += run_value
        else:
            home_rv += run_value

        # Track ACTUAL state changes for subsequent PA context
        bases_after, actual_runs = _apply_runners(current_bases, runners)

        if is_top:
            away_actual += actual_runs
        else:
            home_actual += actual_runs

        # Record cumulative snapshot for charts
        pa_index += 1
        cumulative.append({
            "pa": pa_index,
            "inn": about.get("inning", 1),
            "top": is_top,
            "a_xr": round(max(0.0, away_rv + away_innings * RE_EMPTY_ZERO), 2),
            "h_xr": round(max(0.0, home_rv + home_innings * RE_EMPTY_ZERO), 2),
            "a_r": away_actual,
            "h_r": home_actual,
        })

        outs_after = count.get("outs", current_outs)
        if outs_after >= 3:
            current_outs = 0
            current_bases = set()
        else:
            current_outs = outs_after
            current_bases = bases_after

    away_xr = max(0.0, away_rv + away_innings * RE_EMPTY_ZERO)
    home_xr = max(0.0, home_rv + home_innings * RE_EMPTY_ZERO)

    return {
        "away_xr": round(away_xr, 2),
        "home_xr": round(home_xr, 2),
        "away_actual": away_actual,
        "home_actual": home_actual,
        "cumulative": cumulative,
    }
