"""Persistence layer – load/save cumulative scores, match history, scorecard cache, and scoring sheet."""
import json
import os
from config import (
    SCORES_FILE, MATCH_HISTORY_FILE, DATA_DIR, TEAMS_FILE,
    SCORECARD_CACHE_DIR, SCORING_SHEET_FILE, MASTER_SCORESHEET_FILE,
    PLAYERS_FILE, LeagueConfig, IPL_CONFIG,
)


def _c(cfg):
    """Return cfg if provided, else the default IPL config."""
    return cfg if cfg is not None else IPL_CONFIG


# ── Teams ────────────────────────────────────────────────────────────────────

def load_teams(cfg: LeagueConfig = None) -> dict:
    with open(_c(cfg).teams_file, "r") as f:
        return json.load(f)


def save_teams(data: dict, cfg: LeagueConfig = None):
    with open(_c(cfg).teams_file, "w") as f:
        json.dump(data, f, indent=2)


# ── Players Database ────────────────────────────────────────────────────────

def load_players(cfg: LeagueConfig = None) -> dict:
    with open(_c(cfg).players_file, "r") as f:
        return json.load(f)


def save_players(data: dict, cfg: LeagueConfig = None):
    with open(_c(cfg).players_file, "w") as f:
        json.dump(data, f, indent=2)


# ── Cumulative Scores ────────────────────────────────────────────────────────

def load_scores(cfg: LeagueConfig = None) -> dict:
    """Return {team_name: total_points} dict. Initialises to 0 if missing."""
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    if os.path.exists(c.scores_file):
        with open(c.scores_file, "r") as f:
            return json.load(f)
    teams = load_teams(c)
    return {name: 0.0 for name in teams["teams"]}


def save_scores(scores: dict, cfg: LeagueConfig = None):
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    with open(c.scores_file, "w") as f:
        json.dump(scores, f, indent=2)


# ── Match History ────────────────────────────────────────────────────────────

def load_match_history(cfg: LeagueConfig = None) -> list:
    """Return list of processed match entries."""
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    if os.path.exists(c.match_history_file):
        with open(c.match_history_file, "r") as f:
            return json.load(f)
    return []


def save_match_history(history: list, cfg: LeagueConfig = None):
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    with open(c.match_history_file, "w") as f:
        json.dump(history, f, indent=2)


def is_match_processed(match_id: int, cfg: LeagueConfig = None) -> bool:
    history = load_match_history(cfg)
    return any(m["match_id"] == match_id for m in history)


def record_match(match_id: int, description: str, team_scores: dict,
                 cfg: LeagueConfig = None):
    """Append a match entry to history."""
    history = load_match_history(cfg)
    history.append({
        "match_id": match_id,
        "description": description,
        "team_scores": team_scores,
    })
    save_match_history(history, cfg)


# ── Scorecard Cache ──────────────────────────────────────────────────────────

def get_cached_scorecard(match_id: int, cfg: LeagueConfig = None) -> dict | None:
    """Return cached raw scorecard JSON, or None if not cached."""
    c = _c(cfg)
    os.makedirs(c.scorecard_cache_dir, exist_ok=True)
    path = os.path.join(c.scorecard_cache_dir, f"{match_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def cache_scorecard(match_id: int, data: dict, cfg: LeagueConfig = None):
    """Save raw scorecard JSON locally."""
    c = _c(cfg)
    os.makedirs(c.scorecard_cache_dir, exist_ok=True)
    path = os.path.join(c.scorecard_cache_dir, f"{match_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Scoring Sheet ────────────────────────────────────────────────────────────

def load_scoring_sheet(cfg: LeagueConfig = None) -> dict:
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    if os.path.exists(c.scoring_sheet_file):
        with open(c.scoring_sheet_file, "r") as f:
            return json.load(f)
    return {"matches": []}


def save_scoring_sheet(sheet: dict, cfg: LeagueConfig = None):
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    with open(c.scoring_sheet_file, "w") as f:
        json.dump(sheet, f, indent=2)


def append_to_scoring_sheet(match_id: int, description: str,
                             match_results: dict, cumulative_scores: dict,
                             cfg: LeagueConfig = None):
    """Add a match entry to the scoring sheet with full player detail."""
    sheet = load_scoring_sheet(cfg)

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
    save_scoring_sheet(sheet, cfg)


# ── Master Scoresheet ────────────────────────────────────────────────────────

def load_master_scoresheet(cfg: LeagueConfig = None) -> dict:
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    if os.path.exists(c.master_scoresheet_file):
        with open(c.master_scoresheet_file, "r") as f:
            return json.load(f)
    return {"match_list": [], "teams": {}}


def save_master_scoresheet(master: dict, cfg: LeagueConfig = None):
    c = _c(cfg)
    os.makedirs(c.data_dir, exist_ok=True)
    with open(c.master_scoresheet_file, "w") as f:
        json.dump(master, f, indent=2)


def update_master_scoresheet(match_id: int, description: str,
                              match_results: dict, cumulative_scores: dict,
                              cfg: LeagueConfig = None):
    """Update master scoresheet with a new match's results."""
    master = load_master_scoresheet(cfg)
    teams_data = load_teams(cfg)

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

    save_master_scoresheet(master, cfg)


def unprocess_match(match_id: int, cfg: LeagueConfig = None) -> dict:
    """Remove a match from history. Returns the old team_scores dict (or {})."""
    history = load_match_history(cfg)
    old_scores = {}
    new_history = []
    for m in history:
        if m["match_id"] == match_id:
            old_scores = m.get("team_scores", {})
        else:
            new_history.append(m)
    save_match_history(new_history, cfg)
    return old_scores


def remove_match_from_scoring_sheet(match_id: int, cfg: LeagueConfig = None):
    """Remove a match entry from the scoring sheet."""
    sheet = load_scoring_sheet(cfg)
    sheet["matches"] = [m for m in sheet["matches"] if m["match_id"] != match_id]
    save_scoring_sheet(sheet, cfg)


def remove_match_from_master(match_id: int, cfg: LeagueConfig = None):
    """Remove a match's contribution from the master scoresheet and recompute player cumulatives."""
    master = load_master_scoresheet(cfg)
    mid = str(match_id)

    master["match_list"] = [m for m in master["match_list"] if m["match_id"] != match_id]

    for owner, team in master.get("teams", {}).items():
        for pname, pdata in team.get("players", {}).items():
            pdata.get("match_scores", {}).pop(mid, None)
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

    save_master_scoresheet(master, cfg)


def rebuild_master_scoresheet(cfg: LeagueConfig = None):
    """Rebuild the master scoresheet from existing scoring_sheet.json data."""
    sheet = load_scoring_sheet(cfg)
    teams_data = load_teams(cfg)
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

    save_master_scoresheet(master, cfg)
