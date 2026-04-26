"""Analytics calculations for fantasy league insights."""
from typing import Dict, List, Any
from collections import defaultdict

from storage import load_master_scoresheet, load_match_history, load_teams


def calculate_player_consistency(master_data: Dict) -> List[Dict[str, Any]]:
    """Calculate consistency score for each player based on variance in match scores."""
    player_performances = []
    
    for owner, team_data in master_data.get("teams", {}).items():
        for player_name, player_data in team_data.get("players", {}).items():
            cumulative = player_data.get("cumulative", {})
            matches_played = cumulative.get("matches_played", 0)
            cumulative_total = cumulative.get("total", 0)
            
            if matches_played > 0:
                avg_score = cumulative_total / matches_played
                
                player_performances.append({
                    "name": player_name,
                    "owner": owner,
                    "matches": matches_played,
                    "total_points": round(cumulative_total, 1),
                    "avg_points": round(avg_score, 1),
                    "consistency_score": round(avg_score, 1)  # Simplified - could use variance
                })
    
    # Sort by total points
    player_performances.sort(key=lambda x: x["total_points"], reverse=True)
    return player_performances[:20]  # Top 20


def calculate_team_performance_trend(master_data: Dict, history: List[Dict]) -> List[Dict[str, Any]]:
    """Calculate performance trend for each team across matches."""
    team_trends = []
    
    for owner, team_data in master_data.get("teams", {}).items():
        cumulative = team_data.get("cumulative_total", 0)
        
        # Calculate match-by-match trend from history
        match_scores = []
        for match in history:
            team_score = match.get("team_scores", {}).get(owner, 0)
            if team_score:
                match_scores.append(team_score)
        
        # Calculate trend (simple: compare first half vs second half)
        if len(match_scores) >= 2:
            midpoint = len(match_scores) // 2
            first_half_avg = sum(match_scores[:midpoint]) / midpoint
            second_half_avg = sum(match_scores[midpoint:]) / (len(match_scores) - midpoint)
            trend = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        else:
            trend = 0
        
        team_trends.append({
            "team": owner,
            "total_points": round(cumulative, 1),
            "matches": len(match_scores),
            "avg_per_match": round(cumulative / len(match_scores), 1) if match_scores else 0,
            "trend_percent": round(trend, 1),
            "trending": "📈" if trend > 5 else "📉" if trend < -5 else "➡️"
        })
    
    team_trends.sort(key=lambda x: x["total_points"], reverse=True)
    return team_trends


def calculate_captain_effectiveness(master_data: Dict, teams_data: Dict) -> List[Dict[str, Any]]:
    """Analyze captain and vice-captain performance."""
    captain_stats = []
    
    for owner, team_data in master_data.get("teams", {}).items():
        team_info = teams_data.get("teams", {}).get(owner, {})
        captain = team_info.get("captain")
        vice_captain = team_info.get("vice_captain")
        
        captain_points = 0
        vc_points = 0
        
        players = team_data.get("players", {})
        
        if captain and captain in players:
            captain_points = players[captain].get("cumulative", {}).get("total", 0)
        
        if vice_captain and vice_captain in players:
            vc_points = players[vice_captain].get("cumulative", {}).get("total", 0)
        
        captain_stats.append({
            "team": owner,
            "captain": captain or "Not set",
            "captain_points": round(captain_points, 1),
            "vice_captain": vice_captain or "Not set",
            "vc_points": round(vc_points, 1),
            "combined_points": round(captain_points + vc_points, 1)
        })
    
    captain_stats.sort(key=lambda x: x["combined_points"], reverse=True)
    return captain_stats


def calculate_value_picks(master_data: Dict) -> List[Dict[str, Any]]:
    """Identify best value players (points per match)."""
    value_players = []
    
    for owner, team_data in master_data.get("teams", {}).items():
        for player_name, player_data in team_data.get("players", {}).items():
            cumulative = player_data.get("cumulative", {})
            matches = cumulative.get("matches_played", 0)
            total = cumulative.get("total", 0)
            
            if matches >= 3:  # Min 3 matches
                ppg = total / matches
                
                value_players.append({
                    "name": player_name,
                    "owner": owner,
                    "matches": matches,
                    "total_points": round(total, 1),
                    "points_per_game": round(ppg, 1)
                })
    
    value_players.sort(key=lambda x: x["points_per_game"], reverse=True)
    return value_players[:15]  # Top 15


def calculate_match_winners_distribution(history: List[Dict]) -> Dict[str, Any]:
    """Calculate how many matches each team won."""
    winner_counts = defaultdict(int)
    runner_up_counts = defaultdict(int)
    
    for match in history:
        teams = sorted(match.get("team_scores", {}).items(), key=lambda x: x[1], reverse=True)
        if len(teams) >= 1:
            winner_counts[teams[0][0]] += 1
        if len(teams) >= 2:
            runner_up_counts[teams[1][0]] += 1
    
    distribution = []
    all_teams = set(list(winner_counts.keys()) + list(runner_up_counts.keys()))
    
    for team in all_teams:
        distribution.append({
            "team": team,
            "wins": winner_counts[team],
            "runner_ups": runner_up_counts[team],
            "podium_finishes": winner_counts[team] + runner_up_counts[team]
        })
    
    distribution.sort(key=lambda x: x["wins"], reverse=True)
    
    return {
        "distribution": distribution,
        "total_matches": len(history)
    }


def get_analytics_summary() -> Dict[str, Any]:
    """Get comprehensive analytics data for dashboard."""
    master = load_master_scoresheet()
    history = load_match_history()
    teams = load_teams()
    
    return {
        "top_performers": calculate_player_consistency(master),
        "team_trends": calculate_team_performance_trend(master, history),
        "captain_effectiveness": calculate_captain_effectiveness(master, teams),
        "value_picks": calculate_value_picks(master),
        "match_winners": calculate_match_winners_distribution(history)
    }
