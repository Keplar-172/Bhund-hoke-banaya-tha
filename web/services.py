"""Service layer - convert storage data to web-friendly view models."""
import re
from datetime import datetime, timezone
from typing import Dict, List, Any

from config import LeagueConfig
from storage import (
    load_scores,
    load_match_history,
    load_master_scoresheet,
    load_players,
    get_cached_scorecard,
)
from calculator import calculate_match_scores


def get_leaderboard_data(cfg: LeagueConfig = None) -> List[Dict[str, Any]]:
    """Get current leaderboard standings."""
    scores = load_scores(cfg)
    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard = []
    for rank, (team, points) in enumerate(sorted_teams, 1):
        leaderboard.append({
            "rank": rank,
            "team": team,
            "points": round(points, 1)
        })
    return leaderboard


def get_dashboard_stats(cfg: LeagueConfig = None) -> Dict[str, Any]:
    """Calculate dashboard statistics summary."""
    history = load_match_history(cfg)
    scores = load_scores(cfg)

    if not scores:
        return {
            "total_matches": 0,
            "top_scorer": {"team": "N/A", "points": 0},
            "avg_points": 0,
            "total_teams": 0,
            "points_distribution": []
        }

    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_scorer = {"team": sorted_teams[0][0], "points": round(sorted_teams[0][1], 1)}
    avg_points = round(sum(scores.values()) / len(scores), 1) if scores else 0
    points_distribution = [
        {"team": team, "points": round(points, 1)}
        for team, points in sorted_teams
    ]

    return {
        "total_matches": len(history),
        "top_scorer": top_scorer,
        "avg_points": avg_points,
        "total_teams": len(scores),
        "points_distribution": points_distribution
    }


def get_match_history_data(cfg: LeagueConfig = None) -> List[Dict[str, Any]]:
    """Get processed match history, newest first."""
    history = load_match_history(cfg)
    enriched = []
    for entry in history:
        meta = _build_match_meta(entry["match_id"], cfg)
        enriched.append({**entry, **meta})

    def _sort_key(x):
        mn = x.get("match_number", 0) or 0
        mid = x.get("match_id", 0) or 0
        # Prefer match_number (IPL has it); fall back to match_id (WWC uses Cricbuzz IDs)
        return (mn, mid)

    return sorted(enriched, key=_sort_key, reverse=True)


def _build_match_meta(match_id: int,
                      cfg: LeagueConfig = None) -> Dict[str, Any]:
    """Extract match number, date and description from a cached scorecard."""
    description = f"Match {match_id}"
    match_number = 0
    match_number_label = ""
    date_str = ""

    data = get_cached_scorecard(match_id, cfg)
    if data:
        innings = data.get("scorecard", [])
        if len(innings) >= 2:
            t1 = innings[0].get("batteamsname", "")
            t2 = innings[1].get("batteamsname", "")
            if t1 and t2:
                description = f"{t1} vs {t2}"

        title = data.get("appindex", {}).get("seotitle", "")
        m = re.search(r"(\d+)(?:st|nd|rd|th)\s+Match", title, re.I)
        if m:
            match_number = int(m.group(1))
            match_number_label = f"M{match_number}"

        ts = data.get("responselastupdated", 0)
        if ts:
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%-d %b %Y")

    return {
        "match_id": match_id,
        "description": description,
        "match_number": match_number,
        "match_number_label": match_number_label,
        "date_str": date_str,
    }


def get_master_scoresheet_data(cfg: LeagueConfig = None) -> Dict[str, Any]:
    """Get master scoresheet with all matches and cumulative data."""
    master = load_master_scoresheet(cfg)

    # Build name → team_short lookup from players database
    team_short_lookup: Dict[str, str] = {}
    try:
        players_db = load_players(cfg)
        for pdata in players_db.get("players", {}).values():
            name = pdata.get("name", "")
            short = pdata.get("ipl_team_short", "")
            if name and short:
                team_short_lookup[name] = short
    except Exception:
        pass

    raw_matches = [
        _build_match_meta(m.get("match_id"), cfg)
        for m in master.get("match_list", [])
    ]
    raw_matches.sort(key=lambda x: x["match_number"] if x["match_number"] else float("inf"))

    teams_list = []
    for owner, tdata in master.get("teams", {}).items():
        players = tdata.get("players", {})
        # Inject team_short into each player entry
        for pname, pdata in players.items():
            pdata["team_short"] = team_short_lookup.get(pname, "")
        teams_list.append({
            "owner": owner,
            "total": tdata.get("cumulative_total", 0),
            "players": players,
        })

    teams_list.sort(key=lambda x: x["total"], reverse=True)
    for rank, team in enumerate(teams_list, 1):
        team["rank"] = rank

    return {
        "matches": raw_matches,
        "teams": teams_list,
        "num_matches": len(raw_matches),
    }


def get_match_detail_data(match_id: int,
                          cfg: LeagueConfig = None) -> Dict[str, Any]:
    """Get detailed scoring data for a specific match."""
    scorecard_data = get_cached_scorecard(match_id, cfg)
    if not scorecard_data:
        raise FileNotFoundError(f"No data for match {match_id}")

    match_results = calculate_match_scores(scorecard_data, cfg)

    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"

    teams_list = []
    for owner, data in match_results.items():
        teams_list.append({
            "owner": owner,
            "total": data["total"],
            "players": data["players"]
        })

    teams_list.sort(key=lambda x: x["total"], reverse=True)
    for rank, team in enumerate(teams_list, 1):
        team["rank"] = rank

    return {
        "match_id": match_id,
        "description": desc,
        "teams": teams_list
    }
