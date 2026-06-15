"""
Fantasy Cricket Scoring Rules Engine.

Supports league-specific rules via the ScoringRules dataclass.
IPL and WWC rules differ in several areas; see ScoringRules for details.
"""
from dataclasses import dataclass


@dataclass
class ScoringRules:
    """Per-league scoring configuration. Passed to all scoring functions."""
    # Batting
    run_milestone_first: int = 30       # runs for first +5 milestone; IPL=30, WWC=25
    sr_250_bonus: bool = False          # extra +20 tier for SR > 250 (WWC only)
    duck_roles: tuple = ("Batsman", "Allrounder", "Wicketkeeper")
    # Bowling
    dot_ball_pts: float = 0.5          # per dot ball; IPL=0.5, WWC=1.0
    over_bowled_pts: float = 0.0       # flat bonus per complete over (IPL: 0, unused when tiered)
    over_bowled_tiered: bool = False   # WWC: tiered bonus based on total overs bowled


IPL_RULES = ScoringRules()

WWC_RULES = ScoringRules(
    run_milestone_first=25,
    sr_250_bonus=True,
    duck_roles=("Batsman", "Allrounder"),
    dot_ball_pts=1.0,
    over_bowled_pts=0.0,        # unused — tiered system used instead
    over_bowled_tiered=True,    # >3 overs=20, >2=15, >1=10, 0-1=5
)


def get_scoring_rules(cfg=None) -> ScoringRules:
    """Return the ScoringRules for the given league config (defaults to IPL)."""
    if cfg is not None and cfg.short_name == "wwc":
        return WWC_RULES
    return IPL_RULES


# ══════════════════════════════════════════════════════════════════════════════
# BATTING POINTS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_batting_points(runs: int, balls: int, fours: int, sixes: int,
                              is_not_out: bool, role: str,
                              rules: ScoringRules = None) -> float:
    """
    Args:
        role:  one of "Batsman", "Bowler", "Allrounder", "Wicketkeeper"
        rules: league-specific scoring rules (defaults to IPL_RULES)
    """
    r = rules if rules is not None else IPL_RULES
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
    elif runs >= r.run_milestone_first:   # 30 for IPL, 25 for WWC
        pts += 5

    # Duck: -5 (role-dependent; WK excluded in WWC)
    if runs == 0 and not is_not_out and balls > 0:
        if role in r.duck_roles:
            pts -= 5

    # Strike-rate bonus/penalty (min 10 balls faced)
    if balls >= 10:
        sr = (runs / balls) * 100
        if r.sr_250_bonus and sr > 250:   # WWC only
            pts += 20
        elif sr > 200:
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
                              bowled_lbw_wickets: int = 0,
                              rules: ScoringRules = None) -> float:
    """
    Args:
        dot_balls:          Number of dot balls bowled.
        bowled_lbw_wickets: Count of wickets that were bowled, hit-wicket, or LBW
                            (each gets +10 bonus on top of the base +25).
        rules:              League-specific scoring rules (defaults to IPL_RULES).
    """
    r = rules if rules is not None else IPL_RULES
    pts = 0.0

    # Overs bowled bonus
    if r.over_bowled_tiered:
        # WWC tiered: flat bonus based on total overs bowled
        if overs > 3:
            pts += 20
        elif overs > 2:
            pts += 15
        elif overs > 1:
            pts += 10
        elif overs > 0:
            pts += 5
    else:
        pts += int(overs) * r.over_bowled_pts

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

    # Dot-ball bonus (IPL: +0.5; WWC: +1)
    pts += dot_balls * r.dot_ball_pts

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

# Note: Hat-trick (+25) requires ball-by-ball data — apply as a manual
# adjustment when it occurs. Orange/Purple cap bonuses are also manual.


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
    # Rules
    rules: ScoringRules = None,
) -> dict:
    """Calculate total fantasy points for a player in one match.

    Returns dict with breakdown and total.
    """
    bat_pts = calculate_batting_points(runs, balls, fours, sixes, is_not_out, role, rules)
    bowl_pts = calculate_bowling_points(overs, maidens, runs_conceded, wickets,
                                         dot_balls, bowled_lbw_wickets, rules)
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
