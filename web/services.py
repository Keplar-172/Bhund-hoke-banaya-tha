"""Service layer - convert storage data to web-friendly view models."""
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
from leaderboard import match_order_from_title


def get_leaderboard_data(cfg: LeagueConfig = None) -> List[Dict[str, Any]]:
    """Get current leaderboard standings."""
    scores = load_scores(cfg)
    sorted_teams = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard = []
    for rank, (team, points) in enumerate(sorted_teams, 1):
        leaderboard.append({
            "rank": rank,
            "team": team,
            "points": round(points, 2)
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
    top_scorer = {"team": sorted_teams[0][0], "points": round(sorted_teams[0][1], 2)}
    avg_points = round(sum(scores.values()) / len(scores), 1) if scores else 0
    points_distribution = [
        {"team": team, "points": round(points, 2)}
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
        match_number, match_number_label = match_order_from_title(title)

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
    from storage import load_teams
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

    # Build owner → (captain, vc) lookup live from teams config
    captain_lookup: Dict[str, str] = {}
    vc_lookup: Dict[str, str] = {}
    try:
        teams_db = load_teams(cfg)
        for owner, team in teams_db.get("teams", {}).items():
            captain_lookup[owner] = team.get("captain", "")
            vc_lookup[owner] = team.get("vice_captain", "")
    except Exception:
        pass

    raw_matches = [
        _build_match_meta(m.get("match_id"), cfg)
        for m in master.get("match_list", [])
    ]
    # Newest first, same ordering as the History page
    raw_matches.sort(key=lambda x: (x["match_number"] or 0, x["match_id"] or 0), reverse=True)

    teams_list = []
    for owner, tdata in master.get("teams", {}).items():
        players = tdata.get("players", {})
        cap = captain_lookup.get(owner, "")
        vc = vc_lookup.get(owner, "")
        for pname, pdata in players.items():
            pdata["team_short"] = team_short_lookup.get(pname, "")
            # Always derive from live teams config so display is never stale
            pdata["is_captain"] = (pname == cap)
            pdata["is_vice_captain"] = (pname == vc)
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

    # Match facts for the page heading (additive; older keys unchanged)
    meta = _build_match_meta(match_id, cfg)
    innings = []
    for inn in scorecard_data.get("scorecard", []) or []:
        innings.append({
            "team": inn.get("batteamname") or inn.get("batteamsname") or "",
            "short": inn.get("batteamsname") or "",
            "score": inn.get("score"),
            "wickets": inn.get("wickets"),
            "overs": inn.get("overs"),
        })
    if desc == f"Match {match_id}" and meta.get("description"):
        desc = meta["description"]

    return {
        "match_id": match_id,
        "description": desc,
        "teams": teams_list,
        "label": meta.get("match_number_label", ""),
        "fixture": meta.get("description", ""),
        "date": meta.get("date_str", ""),
        "result": scorecard_data.get("status") or (header.get("status", "") if header else ""),
        "player_of_match": scorecard_data.get("man_of_the_match", ""),
        "innings": innings,
    }


def _place(scores: Dict[str, float], team: str) -> int:
    """Finishing place with shared places for ties (1, 2, 2, 4...)."""
    mine = scores.get(team, 0)
    return 1 + sum(1 for v in scores.values() if v > mine)


def get_season_form(cfg: LeagueConfig = None, last_n: int = 5,
                    checkpoints: int = 8) -> Dict[str, Any]:
    """Form guide, match wins and positions over the season, for the redesign.

    Uses get_match_history_data() so matches are in true match order
    (match_history.json itself is not stored in order).

    Returns:
        labels      short labels of the last N matches, oldest first ("M70", "Q1"...)
        teams       {team: {"form": [{place, points, win, label}], "move": int, "wins": int}}
        wins        [{"team", "wins"}] most wins first (a shared top score counts for each)
        positions   {"labels": [match count...], "teams": {team: [place...]}}
        total_matches
    """
    history = list(reversed(get_match_history_data(cfg)))  # oldest first
    scores = load_scores(cfg)
    names = list(scores.keys())
    for m in history:
        for t in m.get("team_scores", {}):
            if t not in names:
                names.append(t)

    def _label(m):
        return m.get("match_number_label") or m.get("description") or f"Match {m.get('match_id')}"

    # Cumulative places after each match
    running = {t: 0.0 for t in names}
    places_after: List[Dict[str, int]] = []
    wins = {t: 0 for t in names}
    for m in history:
        ts = m.get("team_scores", {})
        for t in names:
            running[t] += ts.get(t, 0) or 0
        places_after.append({t: _place(running, t) for t in names})
        if ts:
            top = max(ts.values())
            for t, v in ts.items():
                if v == top:
                    wins[t] = wins.get(t, 0) + 1

    recent = history[-last_n:] if last_n else []
    teams: Dict[str, Any] = {}
    for t in names:
        form = []
        for m in recent:
            ts = m.get("team_scores", {})
            place = _place(ts, t) if t in ts else None
            form.append({
                "place": place,
                "points": round(ts.get(t, 0) or 0, 2),
                "win": place == 1,
                "label": _label(m),
            })
        move = 0
        if len(history) > len(recent) and places_after:
            before = places_after[len(history) - len(recent) - 1].get(t)
            now = places_after[-1].get(t)
            if before and now:
                move = before - now  # positive = climbed
        teams[t] = {"form": form, "move": move, "wins": wins.get(t, 0)}

    # Evenly spaced checkpoints for the positions chart
    n = len(history)
    idx = sorted({max(1, round(n * (i + 1) / checkpoints)) for i in range(checkpoints)}) if n else []
    positions = {
        "labels": idx,
        "teams": {t: [places_after[i - 1][t] for i in idx] for t in names},
    }

    return {
        "labels": [_label(m) for m in recent],
        "teams": teams,
        "wins": sorted(({"team": t, "wins": w} for t, w in wins.items()),
                       key=lambda x: (-x["wins"], x["team"])),
        "positions": positions,
        "total_matches": n,
    }


def get_team_page_data(cfg: LeagueConfig, owner: str) -> Dict[str, Any] | None:
    """One fantasy team: standing, squad with points, and every match result."""
    from storage import load_teams
    team_cfg = load_teams(cfg).get("teams", {}).get(owner)
    if team_cfg is None:
        return None

    board = get_leaderboard_data(cfg)
    me = next((r for r in board if r["team"] == owner), None)
    lead = board[0]["points"] if board else 0
    form = get_season_form(cfg)
    tf = form["teams"].get(owner, {"form": [], "move": 0, "wins": 0})

    # Squad, with season points from the master sheet
    master_players = load_master_scoresheet(cfg).get("teams", {}).get(owner, {}).get("players", {})
    short = {}
    try:
        for pdata in load_players(cfg).get("players", {}).values():
            short[pdata.get("name", "")] = pdata.get("ipl_team_short", "")
    except Exception:
        pass
    cap, vc = team_cfg.get("captain", ""), team_cfg.get("vice_captain", "")
    squad = []
    for p in team_cfg.get("players", []):
        name = p.get("name", "")
        scores = master_players.get(name, {}).get("match_scores", {})
        played = [v for v in scores.values() if v.get("played")]
        total = round(sum(v.get("total", 0) or 0 for v in scores.values()), 2)
        squad.append({
            "name": name, "role": p.get("role", ""), "country": p.get("country", ""),
            "team_short": short.get(name, ""), "price": p.get("price", 0),
            "is_captain": name == cap, "is_vice_captain": name == vc,
            "points": total, "played": len(played),
            "avg": round(total / len(played), 1) if played else 0,
            "best": max((v.get("total", 0) or 0 for v in played), default=0),
        })
    squad.sort(key=lambda x: (-x["points"], x["name"]))

    # Match by match (newest first, true match order)
    matches = []
    for m in get_match_history_data(cfg):
        ts = m.get("team_scores", {})
        if owner not in ts:
            continue
        place = _place(ts, owner)
        matches.append({
            "match_id": m.get("match_id"), "label": m.get("match_number_label") or "",
            "description": m.get("description", ""), "date_str": m.get("date_str", ""),
            "points": round(ts[owner] or 0, 2), "place": place, "win": place == 1,
            "of": len(ts), "top": round(max(ts.values()), 2) if ts else 0,
        })
    best = max(matches, key=lambda x: x["points"], default=None)

    return {
        "owner": owner,
        "rank": me["rank"] if me else None,
        "points": me["points"] if me else 0,
        "behind": round(lead - me["points"], 2) if me and me["rank"] != 1 else 0,
        "teams_count": len(board),
        "wins": tf.get("wins", 0), "move": tf.get("move", 0), "form": tf.get("form", []),
        "captain": cap, "vice_captain": vc, "budget": team_cfg.get("budget"),
        "spent": sum(p["price"] or 0 for p in squad),
        "squad": squad, "matches": matches, "best": best,
        "top_player": squad[0] if squad and squad[0]["points"] else None,
    }
