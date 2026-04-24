"""Persistence layer – load/save cumulative scores, match history, scorecard cache, and scoring sheet."""
import json
import os
from config import (
    SCORES_FILE, MATCH_HISTORY_FILE, DATA_DIR, TEAMS_FILE,
    SCORECARD_CACHE_DIR, SCORING_SHEET_FILE, MASTER_SCORESHEET_FILE,
    PLAYERS_FILE,
)


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ── Teams ────────────────────────────────────────────────────────────────────

def load_teams() -> dict:
    with open(TEAMS_FILE, "r") as f:
        return json.load(f)


def save_teams(data: dict):
    with open(TEAMS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Players Database ────────────────────────────────────────────────────────

def load_players() -> dict:
    with open(PLAYERS_FILE, "r") as f:
        return json.load(f)


def save_players(data: dict):
    with open(PLAYERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Cumulative Scores ────────────────────────────────────────────────────────

def load_scores() -> dict:
    """Return {team_name: total_points} dict. Initialises to 0 if missing."""
    _ensure_data_dir()
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    teams = load_teams()
    return {name: 0.0 for name in teams["teams"]}


def save_scores(scores: dict):
    _ensure_data_dir()
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f, indent=2)


# ── Match History ────────────────────────────────────────────────────────────

def load_match_history() -> list:
    """Return list of processed match entries."""
    _ensure_data_dir()
    if os.path.exists(MATCH_HISTORY_FILE):
        with open(MATCH_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_match_history(history: list):
    _ensure_data_dir()
    with open(MATCH_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def is_match_processed(match_id: int) -> bool:
    history = load_match_history()
    return any(m["match_id"] == match_id for m in history)


def record_match(match_id: int, description: str, team_scores: dict):
    """Append a match entry to history."""
    history = load_match_history()
    history.append({
        "match_id": match_id,
        "description": description,
        "team_scores": team_scores,
    })
    save_match_history(history)


# ── Scorecard Cache ──────────────────────────────────────────────────────────

def _ensure_cache_dir():
    os.makedirs(SCORECARD_CACHE_DIR, exist_ok=True)


def get_cached_scorecard(match_id: int) -> dict | None:
    """Return cached raw scorecard JSON, or None if not cached."""
    _ensure_cache_dir()
    path = os.path.join(SCORECARD_CACHE_DIR, f"{match_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def cache_scorecard(match_id: int, data: dict):
    """Save raw scorecard JSON locally."""
    _ensure_cache_dir()
    path = os.path.join(SCORECARD_CACHE_DIR, f"{match_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Scoring Sheet ────────────────────────────────────────────────────────────

def load_scoring_sheet() -> dict:
    """
    Return the full scoring sheet:
    {
        "matches": [
            {
                "match_id": int,
                "description": str,
                "team_results": {
                    "Owner": {
                        "match_points": float,
                        "cumulative_points": float,
                        "players": { "Player": {breakdown...}, ... }
                    }
                }
            },
            ...
        ]
    }
    """
    _ensure_data_dir()
    if os.path.exists(SCORING_SHEET_FILE):
        with open(SCORING_SHEET_FILE, "r") as f:
            return json.load(f)
    return {"matches": []}


def save_scoring_sheet(sheet: dict):
    _ensure_data_dir()
    with open(SCORING_SHEET_FILE, "w") as f:
        json.dump(sheet, f, indent=2)


def append_to_scoring_sheet(match_id: int, description: str,
                             match_results: dict, cumulative_scores: dict):
    """Add a match entry to the scoring sheet with full player detail."""
    sheet = load_scoring_sheet()

    team_results = {}
    for owner, data in match_results.items():
        team_results[owner] = {
            "match_points": data["total"],
            "cumulative_points": round(cumulative_scores.get(owner, 0), 2),
            "players": data["players"],
        }

    sheet["matches"].append({
        "match_id": match_id,
        "description": description,
        "team_results": team_results,
    })
    save_scoring_sheet(sheet)


# ── Master Scoresheet ────────────────────────────────────────────────────────

def load_master_scoresheet() -> dict:
    """
    Return the master scoresheet:
    {
        "match_list": [
            {"match_id": int, "description": str}
        ],
        "teams": {
            "Owner": {
                "cumulative_total": float,
                "players": {
                    "Player Name": {
                        "role": str,
                        "is_captain": bool,
                        "is_vice_captain": bool,
                        "match_scores": {
                            "<match_id>": {
                                "batting": float, "bowling": float,
                                "fielding": float, "generic": float,
                                "total": float, "played": bool
                            }
                        },
                        "cumulative": {
                            "batting": float, "bowling": float,
                            "fielding": float, "generic": float,
                            "total": float, "matches_played": int
                        }
                    }
                }
            }
        }
    }
    """
    _ensure_data_dir()
    if os.path.exists(MASTER_SCORESHEET_FILE):
        with open(MASTER_SCORESHEET_FILE, "r") as f:
            return json.load(f)
    return {"match_list": [], "teams": {}}


def save_master_scoresheet(master: dict):
    _ensure_data_dir()
    with open(MASTER_SCORESHEET_FILE, "w") as f:
        json.dump(master, f, indent=2)


def update_master_scoresheet(match_id: int, description: str,
                              match_results: dict, cumulative_scores: dict):
    """Update master scoresheet with a new match's results."""
    master = load_master_scoresheet()
    teams_data = load_teams()

    # Add match to list if not already there
    existing_ids = {m["match_id"] for m in master["match_list"]}
    if match_id not in existing_ids:
        master["match_list"].append({
            "match_id": match_id,
            "description": description,
        })

    mid = str(match_id)

    for owner, data in match_results.items():
        team_info = teams_data["teams"].get(owner, {})
        captain = team_info.get("captain", "")
        vice_captain = team_info.get("vice_captain", "")

        if owner not in master["teams"]:
            master["teams"][owner] = {
                "cumulative_total": 0.0,
                "players": {},
            }

        master["teams"][owner]["cumulative_total"] = round(
            cumulative_scores.get(owner, 0), 2
        )

        for pname, pd in data["players"].items():
            players = master["teams"][owner]["players"]
            if pname not in players:
                players[pname] = {
                    "role": pd.get("role", ""),
                    "is_captain": pname == captain,
                    "is_vice_captain": pname == vice_captain,
                    "match_scores": {},
                    "cumulative": {
                        "batting": 0.0, "bowling": 0.0,
                        "fielding": 0.0, "generic": 0.0,
                        "total": 0.0, "matches_played": 0,
                    },
                }

            played = pd.get("played", pd["total"] != 0)
            players[pname]["match_scores"][mid] = {
                "batting": pd["batting"],
                "bowling": pd["bowling"],
                "fielding": pd["fielding"],
                "generic": pd["generic"],
                "total": pd["total"],
                "played": played,
            }

            # Recalculate cumulative from all match scores
            cum = {"batting": 0.0, "bowling": 0.0, "fielding": 0.0,
                   "generic": 0.0, "total": 0.0, "matches_played": 0}
            for _mid, ms in players[pname]["match_scores"].items():
                cum["batting"] += ms["batting"]
                cum["bowling"] += ms["bowling"]
                cum["fielding"] += ms["fielding"]
                cum["generic"] += ms["generic"]
                cum["total"] += ms["total"]
                if ms.get("played"):
                    cum["matches_played"] += 1
            for k in ("batting", "bowling", "fielding", "generic", "total"):
                cum[k] = round(cum[k], 2)
            players[pname]["cumulative"] = cum

    save_master_scoresheet(master)


def unprocess_match(match_id: int) -> dict:
    """Remove a match from history. Returns the old team_scores dict (or {})."""
    history = load_match_history()
    old_scores = {}
    new_history = []
    for m in history:
        if m["match_id"] == match_id:
            old_scores = m.get("team_scores", {})
        else:
            new_history.append(m)
    save_match_history(new_history)
    return old_scores


def remove_match_from_scoring_sheet(match_id: int):
    """Remove a match entry from the scoring sheet."""
    sheet = load_scoring_sheet()
    sheet["matches"] = [m for m in sheet["matches"] if m["match_id"] != match_id]
    save_scoring_sheet(sheet)


def remove_match_from_master(match_id: int):
    """Remove a match's contribution from the master scoresheet and recompute player cumulatives."""
    master = load_master_scoresheet()
    mid = str(match_id)

    master["match_list"] = [m for m in master["match_list"] if m["match_id"] != match_id]

    for owner, team in master.get("teams", {}).items():
        for pname, pdata in team.get("players", {}).items():
            pdata.get("match_scores", {}).pop(mid, None)
            # Recalculate cumulative from remaining matches
            cum = {"batting": 0.0, "bowling": 0.0, "fielding": 0.0,
                   "generic": 0.0, "total": 0.0, "matches_played": 0}
            for ms in pdata.get("match_scores", {}).values():
                cum["batting"] += ms["batting"]
                cum["bowling"] += ms["bowling"]
                cum["fielding"] += ms["fielding"]
                cum["generic"] += ms["generic"]
                cum["total"] += ms["total"]
                if ms.get("played"):
                    cum["matches_played"] += 1
            for k in ("batting", "bowling", "fielding", "generic", "total"):
                cum[k] = round(cum[k], 2)
            pdata["cumulative"] = cum

    save_master_scoresheet(master)


def rebuild_master_scoresheet():
    """Rebuild the master scoresheet from existing scoring_sheet.json data."""
    sheet = load_scoring_sheet()
    teams_data = load_teams()
    master = {"match_list": [], "teams": {}}

    for match_entry in sheet.get("matches", []):
        mid = str(match_entry["match_id"])
        master["match_list"].append({
            "match_id": match_entry["match_id"],
            "description": match_entry["description"],
        })

        for owner, tr in match_entry["team_results"].items():
            team_info = teams_data["teams"].get(owner, {})
            captain = team_info.get("captain", "")
            vice_captain = team_info.get("vice_captain", "")

            if owner not in master["teams"]:
                master["teams"][owner] = {
                    "cumulative_total": 0.0,
                    "players": {},
                }

            master["teams"][owner]["cumulative_total"] = round(
                tr.get("cumulative_points", 0), 2
            )

            for pname, pd in tr.get("players", {}).items():
                players = master["teams"][owner]["players"]
                if pname not in players:
                    players[pname] = {
                        "role": pd.get("role", ""),
                        "is_captain": pname == captain,
                        "is_vice_captain": pname == vice_captain,
                        "match_scores": {},
                        "cumulative": {
                            "batting": 0.0, "bowling": 0.0,
                            "fielding": 0.0, "generic": 0.0,
                            "total": 0.0, "matches_played": 0,
                        },
                    }

                played = pd.get("played", pd.get("total", 0) != 0)
                players[pname]["match_scores"][mid] = {
                    "batting": pd.get("batting", 0),
                    "bowling": pd.get("bowling", 0),
                    "fielding": pd.get("fielding", 0),
                    "generic": pd.get("generic", 0),
                    "total": pd.get("total", 0),
                    "played": played,
                }

    # Recalculate all cumulative totals
    for owner, team in master["teams"].items():
        for pname, pdata in team["players"].items():
            cum = {"batting": 0.0, "bowling": 0.0, "fielding": 0.0,
                   "generic": 0.0, "total": 0.0, "matches_played": 0}
            for _mid, ms in pdata["match_scores"].items():
                cum["batting"] += ms["batting"]
                cum["bowling"] += ms["bowling"]
                cum["fielding"] += ms["fielding"]
                cum["generic"] += ms["generic"]
                cum["total"] += ms["total"]
                if ms.get("played"):
                    cum["matches_played"] += 1
            for k in ("batting", "bowling", "fielding", "generic", "total"):
                cum[k] = round(cum[k], 2)
            pdata["cumulative"] = cum

    save_master_scoresheet(master)
