"""
Score calculator – maps scorecard data to fantasy team scores.

Uses Cricbuzz player IDs as the primary matching mechanism.
Fuzzy matching is only used internally for scorecard name
deduplication (canonical names, dismissal text), never for
matching scorecard players to fantasy rosters.
"""
from rapidfuzz import fuzz, process

from cricbuzz_api import parse_scorecard
from scoring import (
    calculate_batting_points,
    calculate_bowling_points,
    calculate_fielding_points,
    calculate_generic_points,
    apply_captain_bonus,
)
from storage import load_teams


# ── Roster Lookups ───────────────────────────────────────────────────────────

def _build_roster_lookup(teams_data: dict) -> tuple[dict, dict]:
    """Build lookups for matching roster players to scorecard players.

    Returns:
        id_lookup:   {cricbuzz_id: (team_owner, player_info)}
        name_lookup: {player_name: (team_owner, player_info)}
    """
    id_lookup = {}
    name_lookup = {}
    for owner, team in teams_data["teams"].items():
        for p in team["players"]:
            name_lookup[p["name"]] = (owner, p)
            cb_id = p.get("cricbuzz_id")
            if cb_id:
                id_lookup[int(cb_id)] = (owner, p)
    return id_lookup, name_lookup


def _fuzzy_match(scorecard_name: str, roster_names: list[str],
                 threshold: int = 75) -> str | None:
    """Return best roster name matching the scorecard name, or None."""
    result = process.extractOne(scorecard_name, roster_names,
                                scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        return result[0]
    return None


def _remap_keys(mapping: dict, full_names: list[str]) -> dict:
    """Remap short names from dismissal text to full scorecard names."""
    remapped: dict = {}
    for key, value in mapping.items():
        if key in full_names:
            remapped[key] = value
        else:
            matched = _fuzzy_match(key, full_names, threshold=70)
            if matched:
                # Merge if already present (e.g. same player from both innings)
                if matched in remapped and isinstance(value, dict):
                    for k, v in value.items():
                        remapped[matched][k] = remapped[matched].get(k, 0) + v
                elif matched in remapped and isinstance(value, (int, float)):
                    remapped[matched] += value
                else:
                    remapped[matched] = value
            else:
                remapped[key] = value  # keep as-is
    return remapped


def _build_canonical_names(names: set[str]) -> dict[str, str]:
    """Map short API names to their longer canonical form.

    E.g. if names contains both "Jamieson" and "Kyle Jamieson",
    returns {"Jamieson": "Kyle Jamieson"}.
    """
    sorted_names = sorted(names, key=len, reverse=True)  # longest first
    canonical: dict[str, str] = {}
    used: set[str] = set()
    for short in sorted(names, key=len):
        if short in used:
            continue
        for long in sorted_names:
            if long == short or long in used:
                continue
            score = fuzz.token_sort_ratio(short, long)
            if score >= 75 and short.lower() in long.lower():
                canonical[short] = long
                used.add(short)
                used.add(long)
                break
    return canonical


def _merge_bat(existing: dict, new: dict) -> dict:
    """Merge two batting aggregate dicts."""
    existing["runs"] += new["runs"]
    existing["balls"] += new["balls"]
    existing["fours"] += new["fours"]
    existing["sixes"] += new["sixes"]
    if not new["is_not_out"]:
        existing["is_not_out"] = False
        existing["dismissal"] = new["dismissal"]
    return existing


def _merge_bowl(existing: dict, new: dict) -> dict:
    """Merge two bowling aggregate dicts."""
    for k in ("overs", "maidens", "runs", "wickets", "dot_balls"):
        existing[k] += new[k]
    return existing


def _remap_agg(agg: dict, canonical: dict, merge_fn) -> dict:
    """Remap aggregate dict keys using canonical name map, merging as needed."""
    remapped: dict = {}
    for key, value in agg.items():
        canon = canonical.get(key, key)
        if canon in remapped:
            merge_fn(remapped[canon], value)
        else:
            remapped[canon] = value
    return remapped


# ── Per-Player Scoring ───────────────────────────────────────────────────────

def calculate_match_scores(scorecard_data: dict) -> dict:
    """
    Given raw Cricbuzz scorecard data, compute fantasy points for every
    player across all 11 fantasy teams.

    Returns:
        {
            "team_owner": {
                "total": float,
                "players": {
                    "Player Name": {
                        "batting": float, "bowling": float, "fielding": float,
                        "generic": float, "base_total": float,
                        "multiplier": float, "total": float
                    },
                    ...
                }
            },
            ...
        }
    """
    teams_data = load_teams()
    id_lookup, name_lookup = _build_roster_lookup(teams_data)

    parsed = parse_scorecard(scorecard_data)
    batting_list = parsed["batting"]
    bowling_list = parsed["bowling"]
    fielding_map = parsed["fielding"]
    bowled_lbw_map = parsed["bowled_lbw_map"]
    players_in_match = parsed["players_in_match"]
    mom_name = parsed.get("man_of_the_match")
    id_map = parsed.get("id_map", {})  # cricbuzz_id -> scorecard_name

    # Build scorecard_name -> roster_name mapping using IDs first
    name_map: dict[str, str] = {}
    for cb_id, sc_name in id_map.items():
        if cb_id in id_lookup:
            roster_name = id_lookup[cb_id][1]["name"]
            name_map[sc_name] = roster_name

    # Aggregate batting per player (across innings if needed)
    bat_agg: dict[str, dict] = {}
    for b in batting_list:
        name = b["name"]
        if name not in bat_agg:
            bat_agg[name] = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0,
                             "is_not_out": True, "dismissal": ""}
        bat_agg[name]["runs"] += b["runs"]
        bat_agg[name]["balls"] += b["balls"]
        bat_agg[name]["fours"] += b["fours"]
        bat_agg[name]["sixes"] += b["sixes"]
        if not b["is_not_out"]:
            bat_agg[name]["is_not_out"] = False
            bat_agg[name]["dismissal"] = b["dismissal"]

    # Aggregate bowling per player
    bowl_agg: dict[str, dict] = {}
    for b in bowling_list:
        name = b["name"]
        if name not in bowl_agg:
            bowl_agg[name] = {"overs": 0, "maidens": 0, "runs": 0,
                              "wickets": 0, "dot_balls": 0}
        bowl_agg[name]["overs"] += b["overs"]
        bowl_agg[name]["maidens"] += b["maidens"]
        bowl_agg[name]["runs"] += b["runs"]
        bowl_agg[name]["wickets"] += b["wickets"]
        bowl_agg[name]["dot_balls"] += b["dot_balls"]

    # All scorecard player names (from batting/bowling arrays)
    all_scorecard_names = set(bat_agg.keys()) | set(bowl_agg.keys()) | players_in_match

    # The API often uses short names in one context and full names in another
    # (e.g. batting: "Kyle Jamieson", bowling: "Jamieson").
    # Build a canonical name map: short → long, then remap all aggregates.
    canonical = _build_canonical_names(all_scorecard_names)
    bat_agg = _remap_agg(bat_agg, canonical, _merge_bat)
    bowl_agg = _remap_agg(bowl_agg, canonical, _merge_bowl)
    players_in_match = {canonical.get(n, n) for n in players_in_match}

    # Rebuild after canonicalization
    all_scorecard_names = set(bat_agg.keys()) | set(bowl_agg.keys()) | players_in_match

    # Normalise fielding & bowled_lbw maps: dismissal text often uses
    # short names ("Jamieson") but bat/bowl arrays have full names
    # ("Kyle Jamieson").  Remap short keys → full scorecard names.
    full_sc_names = list(all_scorecard_names)
    fielding_map = _remap_keys(fielding_map, full_sc_names)
    bowled_lbw_map = _remap_keys(bowled_lbw_map, full_sc_names)

    all_scorecard_names |= set(fielding_map.keys())

    # Exact name fallback for any scorecard names not already mapped by ID
    for sc_name in all_scorecard_names:
        if sc_name in name_map:
            continue
        if sc_name in name_lookup:
            name_map[sc_name] = sc_name

    # Map MoM — use name_map (ID-based) since MoM always played in the match
    mom_roster_name = None
    if mom_name:
        canon_mom = canonical.get(mom_name, mom_name)
        if canon_mom in name_map:
            mom_roster_name = name_map[canon_mom]
        elif mom_name in name_map:
            mom_roster_name = name_map[mom_name]
        elif mom_name in name_lookup:
            mom_roster_name = mom_name

    # Calculate points per fantasy team
    results: dict[str, dict] = {}
    for owner, team in teams_data["teams"].items():
        captain = team.get("captain")
        vice_captain = team.get("vice_captain")
        team_total = 0.0
        player_scores = {}

        for p in team["players"]:
            pname = p["name"]
            role = p["role"]

            # Find this player in the scorecard
            sc_name = None
            for sc, roster in name_map.items():
                if roster == pname:
                    sc_name = sc
                    break

            bat_pts = 0.0
            bowl_pts = 0.0
            field_pts = 0.0
            generic_pts = 0.0
            played = False

            if sc_name:
                played = sc_name in players_in_match or \
                         sc_name in bat_agg or sc_name in bowl_agg

                # Batting
                if sc_name in bat_agg:
                    ba = bat_agg[sc_name]
                    bat_pts = calculate_batting_points(
                        ba["runs"], ba["balls"], ba["fours"], ba["sixes"],
                        ba["is_not_out"], role
                    )

                # Bowling
                if sc_name in bowl_agg:
                    bo = bowl_agg[sc_name]
                    blw = bowled_lbw_map.get(sc_name, 0)
                    bowl_pts = calculate_bowling_points(
                        bo["overs"], bo["maidens"], bo["runs"],
                        bo["wickets"], bo["dot_balls"], blw
                    )

                # Fielding
                if sc_name in fielding_map:
                    fm = fielding_map[sc_name]
                    field_pts = calculate_fielding_points(
                        fm.get("catches", 0), fm.get("stumpings", 0),
                        fm.get("run_out_shared", 0), fm.get("run_out_solo", 0)
                    )
                # Also check roster name in fielding (names may differ)
                elif pname in fielding_map:
                    fm = fielding_map[pname]
                    field_pts = calculate_fielding_points(
                        fm.get("catches", 0), fm.get("stumpings", 0),
                        fm.get("run_out_shared", 0), fm.get("run_out_solo", 0)
                    )

                is_mom = (mom_roster_name == pname)
                generic_pts = calculate_generic_points(played, is_mom)

            base_total = bat_pts + bowl_pts + field_pts + generic_pts
            is_captain = (captain == pname)
            is_vc = (vice_captain == pname)
            final_total = apply_captain_bonus(base_total, is_captain, is_vc)

            # Build raw stats for detailed view
            raw_stats = {}
            if sc_name and sc_name in bat_agg:
                ba = bat_agg[sc_name]
                raw_stats["bat"] = {
                    "runs": ba["runs"], "balls": ba["balls"],
                    "fours": ba["fours"], "sixes": ba["sixes"],
                    "is_not_out": ba["is_not_out"],
                    "sr": round(ba["runs"] / ba["balls"] * 100, 1) if ba["balls"] else 0,
                }
            if sc_name and sc_name in bowl_agg:
                bo = bowl_agg[sc_name]
                raw_stats["bowl"] = {
                    "overs": bo["overs"], "maidens": bo["maidens"],
                    "runs": bo["runs"], "wickets": bo["wickets"],
                    "dot_balls": bo["dot_balls"],
                    "econ": round(bo["runs"] / bo["overs"], 1) if bo["overs"] else 0,
                    "bowled_lbw": bowled_lbw_map.get(sc_name, 0),
                }
            fm_data = None
            if sc_name and sc_name in fielding_map:
                fm_data = fielding_map[sc_name]
            elif pname in fielding_map:
                fm_data = fielding_map[pname]
            if fm_data:
                raw_stats["field"] = {
                    "catches": fm_data.get("catches", 0),
                    "stumpings": fm_data.get("stumpings", 0),
                    "run_out_shared": fm_data.get("run_out_shared", 0),
                    "run_out_solo": fm_data.get("run_out_solo", 0),
                }

            player_scores[pname] = {
                "batting": bat_pts,
                "bowling": bowl_pts,
                "fielding": field_pts,
                "generic": generic_pts,
                "base_total": base_total,
                "multiplier": 1.5 if is_captain else (1.25 if is_vc else 1.0),
                "total": final_total,
                "played": played,
                "role": role,
                "raw": raw_stats,
            }
            if played or base_total != 0:
                team_total += final_total

        results[owner] = {
            "total": round(team_total, 2),
            "players": player_scores,
        }

    return results
