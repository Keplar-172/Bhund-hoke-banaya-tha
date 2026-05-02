"""Service layer - convert storage data to web-friendly view models."""
import re
from datetime import datetime, timezone
from typing import Dict, List, Any

from storage import (
    load_scores,
    load_match_history,
    load_master_scoresheet,
    get_cached_scorecard,
)
from calculator import calculate_match_scores


def get_leaderboard_data() -> List[Dict[str, Any]]:
    """Get current leaderboard standings."""
    scores = load_scores()
    
    # Sort by score descending
    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    leaderboard = []
    for rank, (team, points) in enumerate(sorted_teams, 1):
        leaderboard.append({
            "rank": rank,
            "team": team,
            "points": round(points, 1)
        })
    
    return leaderboard


def get_dashboard_stats() -> Dict[str, Any]:
    """Calculate dashboard statistics summary."""
    history = load_match_history()
    scores = load_scores()
    master = load_master_scoresheet()
    
    if not scores:
        return {
            "total_matches": 0,
            "top_scorer": {"team": "N/A", "points": 0},
            "avg_points": 0,
            "total_teams": 0,
            "points_distribution": []
        }
    
    # Sort teams by score
    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_scorer = {"team": sorted_teams[0][0], "points": round(sorted_teams[0][1], 1)}
    
    # Calculate average points
    avg_points = round(sum(scores.values()) / len(scores), 1) if scores else 0
    
    # Prepare points distribution for chart
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


def get_match_history_data() -> List[Dict[str, Any]]:
    """Get processed match history, sorted by IPL match number (chronological order)."""
    history = load_match_history()

    enriched = []
    for entry in history:
        meta = _build_match_meta(entry["match_id"])
        enriched.append({**entry, **meta})

    return sorted(enriched, key=lambda x: x["match_number"] if x["match_number"] else 0)


def _build_match_description(match_id: int) -> str:
    """Build human-readable description like 'SRH vs RCB' from scorecard data."""
    data = get_cached_scorecard(match_id)
    if data:
        innings = data.get("scorecard", [])
        if len(innings) >= 2:
            t1 = innings[0].get("batteamsname", "")
            t2 = innings[1].get("batteamsname", "")
            if t1 and t2:
                return f"{t1} vs {t2}"
    return f"Match {match_id}"


def _build_match_meta(match_id: int) -> Dict[str, Any]:
    """
    Extract match number, date and description from a cached scorecard.
    Returns:
        match_id, description, match_number (int), match_number_label (str), date_str
    """
    description = f"Match {match_id}"
    match_number = 0          # used for sorting; 0 = unknown
    match_number_label = ""   # e.g. "M38"
    date_str = ""             # e.g. "26 Apr 2026"

    data = get_cached_scorecard(match_id)
    if data:
        # Description from innings teams
        innings = data.get("scorecard", [])
        if len(innings) >= 2:
            t1 = innings[0].get("batteamsname", "")
            t2 = innings[1].get("batteamsname", "")
            if t1 and t2:
                description = f"{t1} vs {t2}"

        # Match number from SEO title e.g. "38th Match,Indian Premier League 2026"
        title = data.get("appindex", {}).get("seotitle", "")
        m = re.search(r"(\d+)(?:st|nd|rd|th)\s+Match", title, re.I)
        if m:
            match_number = int(m.group(1))
            match_number_label = f"M{match_number}"

        # Approximate date from the last-updated Unix timestamp
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


def get_master_scoresheet_data() -> Dict[str, Any]:
    """Get master scoresheet with all matches and cumulative data."""
    master = load_master_scoresheet()

    # Build match list with meta, sorted by match number
    raw_matches = [
        _build_match_meta(m.get("match_id"))
        for m in master.get("match_list", [])
    ]
    raw_matches.sort(key=lambda x: x["match_number"] if x["match_number"] else float("inf"))

    # Sort teams by cumulative total
    teams_list = []
    for owner, tdata in master.get("teams", {}).items():
        teams_list.append({
            "owner": owner,
            "total": tdata.get("cumulative_total", 0),
            "players": tdata.get("players", {})
        })

    teams_list.sort(key=lambda x: x["total"], reverse=True)

    for rank, team in enumerate(teams_list, 1):
        team["rank"] = rank

    return {
        "matches": raw_matches,
        "teams": teams_list,
        "num_matches": len(raw_matches),
    }


def get_match_detail_data(match_id: int) -> Dict[str, Any]:
    """Get detailed scoring data for a specific match."""
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        raise FileNotFoundError(f"No data for match {match_id}")
    
    match_results = calculate_match_scores(scorecard_data)
    
    # Build description
    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"
    
    # Sort teams by match total
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
