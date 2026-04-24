"""
IPL Fantasy Premier League 2026 – Scoring Rules Engine.

Rules as provided by the league commissioner.
"""


# ══════════════════════════════════════════════════════════════════════════════
# BATTING POINTS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_batting_points(runs: int, balls: int, fours: int, sixes: int,
                              is_not_out: bool, role: str) -> float:
    """
    Args:
        role: one of "Batsman", "Bowler", "Allrounder", "Wicketkeeper"
              Duck penalty applies only to Batsman, Allrounder, Wicketkeeper.
    """
    pts = 0.0

    # Per-run, boundary, six
    pts += runs * 1           # +1 per run
    pts += fours * 1          # +1 bonus per four
    pts += sixes * 2          # +2 bonus per six

    # Milestone bonuses (highest matching tier only)
    if runs >= 150:
        pts += 30
    elif runs >= 125:
        pts += 25
    elif runs >= 100:
        pts += 20
    elif runs >= 75:
        pts += 15
    elif runs >= 50:
        pts += 10
    elif runs >= 30:
        pts += 5

    # Duck: -5 (only for batsman, allrounders, wicketkeepers)
    if runs == 0 and not is_not_out and balls > 0:
        if role in ("Batsman", "Allrounder", "Wicketkeeper"):
            pts -= 5

    # Strike-rate bonus/penalty (min 10 balls)
    if balls >= 10:
        sr = (runs / balls) * 100
        if sr > 200:
            pts += 12
        elif sr > 150:
            pts += 8
        elif sr >= 120:
            pts += 4
        elif sr >= 80:
            pts += 0
        else:
            pts -= 4

    return pts


# ══════════════════════════════════════════════════════════════════════════════
# BOWLING POINTS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_bowling_points(overs: float, maidens: int, runs_conceded: int,
                              wickets: int, dot_balls: int,
                              bowled_lbw_wickets: int = 0) -> float:
    """
    Args:
        dot_balls:          Number of dot balls bowled.
        bowled_lbw_wickets: Count of wickets that were bowled, hit-wicket, or LBW
                            (each gets +10 bonus on top of the base +25).
    """
    pts = 0.0

    # Base wicket points
    pts += wickets * 25

    # Bowled / Hit-wicket / LBW bonus
    pts += bowled_lbw_wickets * 10

    # Wicket-haul bonus (highest matching tier only)
    if wickets >= 5:
        pts += 32
    elif wickets >= 4:
        pts += 24
    elif wickets >= 3:
        pts += 16
    elif wickets >= 2:
        pts += 8

    # Maiden over bonus
    pts += maidens * 8

    # Dot-ball bonus
    pts += dot_balls * 0.5

    # Economy rate (minimum 1 over bowled)
    if overs >= 1:
        economy = runs_conceded / overs
        if economy >= 12:
            pts -= 8
        elif economy >= 9:
            pts -= 4
        elif economy > 7.5:
            pts += 0
        elif economy > 6:
            pts += 4
        elif economy <= 5:
            pts += 16
        else:  # 5 < economy <= 6
            pts += 8

    return pts


# ══════════════════════════════════════════════════════════════════════════════
# FIELDING POINTS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_fielding_points(catches: int, stumpings: int,
                               run_out_shared: int,
                               run_out_solo: int) -> float:
    """
    Args:
        run_out_shared: Run-outs where 2 fielders involved (+10 each).
        run_out_solo:   Run-outs where only 1 fielder named (+20).
    """
    pts = 0.0
    pts += catches * 10
    pts += stumpings * 10
    pts += run_out_shared * 10
    pts += run_out_solo * 20
    return pts


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC POINTS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_generic_points(played: bool, is_mom: bool) -> float:
    """Playing-11 and Man-of-the-Match bonuses."""
    pts = 0.0
    if played:
        pts += 4       # Selection in playing 11
    if is_mom:
        pts += 30      # Man of the match
    return pts

# Note: Impact sub (+4), Orange cap (+100), Purple cap (+100), Hatrick (+25),
# and Mankad (+20) are rare/manual events – they can be added via manual
# adjustment when needed.


# ══════════════════════════════════════════════════════════════════════════════
# CAPTAIN / VICE-CAPTAIN MULTIPLIER
# ══════════════════════════════════════════════════════════════════════════════

def apply_captain_bonus(points: float, is_captain: bool,
                         is_vice_captain: bool) -> float:
    if is_captain:
        return points * 1.5
    if is_vice_captain:
        return points * 1.25
    return points


# ══════════════════════════════════════════════════════════════════════════════
# TOTAL PLAYER SCORE FOR A MATCH
# ══════════════════════════════════════════════════════════════════════════════

def calculate_player_match_score(
    # Batting
    runs: int = 0, balls: int = 0, fours: int = 0, sixes: int = 0,
    is_not_out: bool = True, role: str = "Batsman",
    # Bowling
    overs: float = 0, maidens: int = 0, runs_conceded: int = 0,
    wickets: int = 0, dot_balls: int = 0, bowled_lbw_wickets: int = 0,
    # Fielding
    catches: int = 0, stumpings: int = 0,
    run_out_shared: int = 0, run_out_solo: int = 0,
    # Generic
    played: bool = False, is_mom: bool = False,
    # Captain/VC
    is_captain: bool = False, is_vice_captain: bool = False,
) -> dict:
    """Calculate total fantasy points for a player in one match.

    Returns dict with breakdown and total.
    """
    bat_pts = calculate_batting_points(runs, balls, fours, sixes, is_not_out, role)
    bowl_pts = calculate_bowling_points(overs, maidens, runs_conceded, wickets,
                                         dot_balls, bowled_lbw_wickets)
    field_pts = calculate_fielding_points(catches, stumpings,
                                           run_out_shared, run_out_solo)
    generic_pts = calculate_generic_points(played, is_mom)

    base_total = bat_pts + bowl_pts + field_pts + generic_pts
    final_total = apply_captain_bonus(base_total, is_captain, is_vice_captain)

    return {
        "batting": bat_pts,
        "bowling": bowl_pts,
        "fielding": field_pts,
        "generic": generic_pts,
        "base_total": base_total,
        "multiplier": 1.5 if is_captain else (1.25 if is_vice_captain else 1.0),
        "total": final_total,
    }
