"""Service layer - convert storage data to web-friendly view models."""
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
    """Get processed match history."""
    history = load_match_history()
    
    # Reverse to show most recent first
    return list(reversed(history))


def get_master_scoresheet_data() -> Dict[str, Any]:
    """Get master scoresheet with all matches and cumulative data."""
    master = load_master_scoresheet()
    
    # Sort teams by cumulative total
    teams_list = []
    for owner, tdata in master.get("teams", {}).items():
        teams_list.append({
            "owner": owner,
            "total": tdata.get("cumulative_total", 0),
            "players": tdata.get("players", {})
        })
    
    teams_list.sort(key=lambda x: x["total"], reverse=True)
    
    # Add ranks
    for rank, team in enumerate(teams_list, 1):
        team["rank"] = rank
    
    return {
        "matches": master.get("match_list", []),
        "teams": teams_list,
        "num_matches": len(master.get("match_list", []))
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
