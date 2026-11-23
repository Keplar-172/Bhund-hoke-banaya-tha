"""Cricbuzz API client via RapidAPI – fetch matches & scorecards."""
import json
import os
import re
import threading
from datetime import datetime, timezone

import requests
from config import RAPIDAPI_KEY, RAPIDAPI_HOST

# ── Call budget (free tier) ──────────────────────────────────────────────────
# Every API call is counted in data/api_usage.json. Key 1 (the main listing,
# free Basic plan = 200 calls/month) is capped at API_MONTHLY_CAP. When it is
# used up, an optional second key (RAPIDAPI_KEY_2, e.g. the cricbuzz-cricket2
# listing, free plan = 100/day) takes over, capped at API2_DAILY_CAP per day.
# When both are used up, calls are refused instead of being billed.

API_MONTHLY_CAP = int(os.environ.get("API_MONTHLY_CAP", "180"))
API2_DAILY_CAP = int(os.environ.get("API2_DAILY_CAP", "90"))
RAPIDAPI_KEY_2 = os.environ.get("RAPIDAPI_KEY_2")
RAPIDAPI_HOST_2 = os.environ.get("RAPIDAPI_HOST_2", "cricbuzz-cricket2.p.rapidapi.com")

_usage_lock = threading.Lock()


class ApiBudgetExceeded(RuntimeError):
    """Raised instead of making a call that would go over the free-tier cap."""


def _usage_file() -> str:
    return os.path.join(os.environ.get("DATA_ROOT", "data"), "api_usage.json")


def _now():
    return datetime.now(timezone.utc)


def load_usage() -> dict:
    try:
        with open(_usage_file()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"months": {}, "days": {}, "log": []}


def usage_summary() -> dict:
    """Counts for this month/day, for the admin page and /api/usage."""
    u = load_usage()
    month, day = _now().strftime("%Y-%m"), _now().strftime("%Y-%m-%d")
    m = u.get("months", {}).get(month, {})
    d = u.get("days", {}).get(day, {})
    return {
        "month": month,
        "key1_used": m.get("key1", 0),
        "key1_cap": API_MONTHLY_CAP,
        "key2_configured": bool(RAPIDAPI_KEY_2),
        "key2_used_today": d.get("key2", 0),
        "key2_used_month": m.get("key2", 0),
        "key2_daily_cap": API2_DAILY_CAP,
        "refused_month": m.get("refused", 0),
        "recent": u.get("log", [])[-20:][::-1],
    }


def _pick_key() -> tuple:
    """Return (slot, key, host) for the next call, or raise ApiBudgetExceeded."""
    u = load_usage()
    month, day = _now().strftime("%Y-%m"), _now().strftime("%Y-%m-%d")
    used1 = u.get("months", {}).get(month, {}).get("key1", 0)
    if RAPIDAPI_KEY and used1 < API_MONTHLY_CAP:
        return "key1", RAPIDAPI_KEY, RAPIDAPI_HOST
    used2 = u.get("days", {}).get(day, {}).get("key2", 0)
    if RAPIDAPI_KEY_2 and used2 < API2_DAILY_CAP:
        return "key2", RAPIDAPI_KEY_2, RAPIDAPI_HOST_2
    raise ApiBudgetExceeded(
        f"API budget used up ({used1}/{API_MONTHLY_CAP} this month on key 1"
        + (f", {used2}/{API2_DAILY_CAP} today on key 2" if RAPIDAPI_KEY_2 else "")
        + "). Upload the scorecard by hand or raise API_MONTHLY_CAP.")


def _record(slot: str, endpoint: str, ok: bool) -> None:
    with _usage_lock:
        u = load_usage()
        month, day = _now().strftime("%Y-%m"), _now().strftime("%Y-%m-%d")
        m = u.setdefault("months", {}).setdefault(month, {})
        m[slot] = m.get(slot, 0) + 1
        if slot != "refused":
            d = u.setdefault("days", {}).setdefault(day, {})
            d[slot] = d.get(slot, 0) + 1
            # keep ~2 months of daily counters
            for old in sorted(u["days"])[:-62]:
                u["days"].pop(old, None)
        u.setdefault("log", []).append({
            "at": _now().isoformat(timespec="seconds"),
            "key": slot, "endpoint": endpoint, "ok": ok,
        })
        u["log"] = u["log"][-100:]
        path = _usage_file()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(u, f, indent=1)
        os.replace(tmp, path)


def _get(endpoint: str) -> dict:
    try:
        slot, key, host = _pick_key()
    except ApiBudgetExceeded:
        _record("refused", endpoint, False)
        raise
    url = f"https://{host}{endpoint}"
    headers = {"x-rapidapi-key": key, "x-rapidapi-host": host}
    ok = False
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        ok = True
        return resp.json()
    finally:
        _record(slot, endpoint, ok)  # RapidAPI bills failed calls too


# ── Match Listing ────────────────────────────────────────────────────────────

def _parse_match_info(info: dict, series_name: str = "") -> dict:
    """Convert raw matchInfo dict into a normalised match record."""
    return {
        "match_id": info.get("matchId"),
        "description": info.get("matchDesc", ""),
        "status": info.get("status", ""),
        "team1": info.get("team1", {}).get("teamSName", ""),
        "team2": info.get("team2", {}).get("teamSName", ""),
        "state": info.get("state", ""),
        "start_ms": int(info.get("startDate") or 0),
        "series_name": series_name,
    }


def _recent_series(data: dict):
    """Yield (series_id, series_name, matches) from a /matches/v1/recent response."""
    for type_match in data.get("typeMatches", []):
        for series in type_match.get("seriesMatches", []):
            info = series.get("seriesAdWrapper", {})
            if info:
                yield info.get("seriesId"), info.get("seriesName", ""), info.get("matches", [])


def get_recent_matches(tournament) -> list:
    """Recent matches (Cricbuzz's ~last 10 window) belonging to one tournament."""
    data = _get("/matches/v1/recent")
    matches = []
    for _sid, series_name, series_matches in _recent_series(data):
        if not tournament.matches_series(series_name):
            continue
        for match in series_matches:
            matches.append(_parse_match_info(match.get("matchInfo", {}), series_name))
    return matches


def get_series_id(tournament) -> int | None:
    """Find a tournament's Cricbuzz series ID via the recent-matches endpoint."""
    data = _get("/matches/v1/recent")
    for sid, series_name, _m in _recent_series(data):
        if tournament.matches_series(series_name):
            return sid
    return None


def get_series_matches(series_id: int) -> list:
    """
    Fetch ALL matches for a given series (full season).
    Uses the /series/v1/{seriesId}/matches endpoint.
    """
    data = _get(f"/series/v1/{series_id}/matches")
    matches = []
    for group in data.get("matchDetails", []):
        for match in group.get("matchDetailsMap", {}).get("match", []):
            info = match.get("matchInfo", {})
            matches.append(_parse_match_info(info))
    return matches


def get_all_matches(tournament) -> list:
    """
    All available matches for a tournament.
    Tries the full-season series endpoint first; falls back to the recent-matches
    window (~10 most recent matches), enough for day-to-day automation.
    """
    series_id = get_series_id(tournament)
    if series_id:
        try:
            matches = get_series_matches(series_id)
            if matches:
                return matches
        except Exception:
            pass  # endpoint not available on this plan – use fallback below
    return get_recent_matches(tournament)


def get_scorecard(match_id: int) -> dict:
    """Fetch full scorecard for a completed match."""
    return _get(f"/mcenter/v1/{match_id}/hscard")


def get_match_mom(match_id: int) -> str | None:
    """Fetch Man of the Match from the commentary endpoint."""
    try:
        data = _get(f"/mcenter/v1/{match_id}/comm")
        mh = data.get("matchheaders", {})
        mom_data = mh.get("momplayers", {})
        players = mom_data.get("player", [])
        if players:
            return players[0].get("name")
    except Exception:
        pass
    return None


def get_match_info(match_id: int) -> dict:
    """Fetch match info including Man of the Match."""
    return _get(f"/mcenter/v1/{match_id}")


# ── Scorecard Parsing ────────────────────────────────────────────────────────

def parse_scorecard(scorecard_data: dict) -> dict:
    """
    Parse raw scorecard API response into structured batting/bowling/fielding data.
    Supports both API response formats (lowercase list-based and camelCase dict-based).

    Returns:
        {
            "players_in_match": set of player names who played,
            "batting": [
                {"name": str, "runs": int, "balls": int, "fours": int,
                 "sixes": int, "is_not_out": bool, "dismissal": str},
                ...
            ],
            "bowling": [
                {"name": str, "overs": float, "maidens": int,
                 "runs": int, "wickets": int, "dot_balls": int,
                 "no_balls": int, "wides": int},
                ...
            ],
            "fielding": {
                "Player Name": {"catches": int, "stumpings": int,
                                "run_out_shared": int, "run_out_solo": int},
                ...
            },
            "bowled_lbw_map": {
                "Bowler Name": count_of_bowled_lbw_hitwicket_dismissals,
                ...
            },
            "man_of_the_match": str or None,
        }
    """
    batting = []
    bowling = []
    fielding = {}
    bowled_lbw_map = {}
    players_in_match = set()
    id_map = {}  # cricbuzz_id -> scorecard_name

    # Detect API format: lowercase "scorecard" (list of innings with "batsman" lists)
    # vs camelCase "scoreCard" (list of innings with nested "batTeamDetails" dicts)
    scorecard = scorecard_data.get("scorecard") or scorecard_data.get("scoreCard", [])

    for innings in scorecard:
        # ── Batting ──
        batsmen = _get_batsmen(innings)
        for bat_info in batsmen:
            name = bat_info.get("name") or bat_info.get("batName", "")
            runs = bat_info.get("runs") or bat_info.get("r", 0)
            balls = bat_info.get("balls") or bat_info.get("b", 0)
            fours = bat_info.get("fours") or bat_info.get("4s", 0)
            sixes = bat_info.get("sixes") or bat_info.get("6s", 0)
            out_desc = bat_info.get("outdec") or bat_info.get("outDesc", "")
            is_not_out = "not out" in out_desc.lower() if out_desc else True

            player_id = bat_info.get("id")
            players_in_match.add(name)
            if player_id:
                id_map[int(player_id)] = name
            batting.append({
                "name": name,
                "id": int(player_id) if player_id else None,
                "runs": int(runs) if runs else 0,
                "balls": int(balls) if balls else 0,
                "fours": int(fours) if fours else 0,
                "sixes": int(sixes) if sixes else 0,
                "is_not_out": is_not_out,
                "dismissal": out_desc,
            })

            _parse_fielding(out_desc, fielding)
            _track_bowled_lbw(out_desc, bowled_lbw_map)

        # ── Bowling ──
        bowlers = _get_bowlers(innings)
        for bowl_info in bowlers:
            name = bowl_info.get("name") or bowl_info.get("bowlName", "")
            overs_raw = bowl_info.get("overs") or bowl_info.get("o", 0)
            overs = float(overs_raw) if overs_raw else 0
            dots = bowl_info.get("dots", 0)

            player_id = bowl_info.get("id")
            players_in_match.add(name)
            if player_id:
                id_map[int(player_id)] = name
            bowling.append({
                "name": name,
                "id": int(player_id) if player_id else None,
                "overs": overs,
                "maidens": int(bowl_info.get("maidens") or bowl_info.get("m", 0)),
                "runs": int(bowl_info.get("runs") or bowl_info.get("r", 0)),
                "wickets": int(bowl_info.get("wickets") or bowl_info.get("w", 0)),
                "dot_balls": int(dots) if dots else 0,
                "no_balls": int(bowl_info.get("noBalls") or bowl_info.get("noballs", 0)),
                "wides": int(bowl_info.get("wides") or 0),
            })

    # Man of the match — try multiple locations
    mom = _extract_mom(scorecard_data)

    return {
        "players_in_match": players_in_match,
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "bowled_lbw_map": bowled_lbw_map,
        "man_of_the_match": mom,
        "id_map": id_map,
    }


def _get_batsmen(innings: dict) -> list:
    """Extract batsmen list from either API format."""
    # Format 1: list-based (lowercase keys)
    if "batsman" in innings:
        return innings["batsman"]
    # Format 2: dict-based (camelCase)
    bat_team = innings.get("batTeamDetails", {})
    data = bat_team.get("batsmenData", {})
    return list(data.values()) if isinstance(data, dict) else data


def _get_bowlers(innings: dict) -> list:
    """Extract bowlers list from either API format."""
    if "bowler" in innings:
        return innings["bowler"]
    bowl_team = innings.get("bowlTeamDetails", {})
    data = bowl_team.get("bowlersData", {})
    return list(data.values()) if isinstance(data, dict) else data


def _extract_mom(scorecard_data: dict) -> str | None:
    """Extract Man of the Match from various API response formats."""
    # Format 1: matchHeader.playersOfTheMatch (old API format)
    header = scorecard_data.get("matchHeader", {})
    mom_list = header.get("playersOfTheMatch", [])
    if mom_list:
        return mom_list[0].get("fullName") or mom_list[0].get("name")
    mom_obj = header.get("playerOfTheMatch", {})
    if mom_obj:
        return mom_obj.get("fullName") or mom_obj.get("name")

    # Format 2: man_of_the_match key (merged from comm endpoint)
    mom_name = scorecard_data.get("man_of_the_match")
    if mom_name:
        return mom_name

    return None


def _track_bowled_lbw(dismissal: str, bowled_lbw_map: dict):
    """Count bowled/lbw/hit-wicket wickets per bowler for bonus points."""
    if not dismissal:
        return
    desc = dismissal.lower()

    bowler_name = None
    if desc.startswith("b "):
        # "b BowlerName"
        bowler_name = dismissal[2:].strip()
    elif "lbw" in desc:
        # "lbw b BowlerName"
        parts = dismissal.lower().split(" b ")
        if len(parts) >= 2:
            bowler_name = dismissal[dismissal.lower().index(" b ") + 3:].strip()
    elif "hit wicket" in desc:
        parts = dismissal.lower().split(" b ")
        if len(parts) >= 2:
            bowler_name = dismissal[dismissal.lower().index(" b ") + 3:].strip()

    if bowler_name:
        bowled_lbw_map[bowler_name] = bowled_lbw_map.get(bowler_name, 0) + 1


def _parse_fielding(dismissal: str, fielding: dict):
    """Extract catch/stumping/run-out info from dismissal string."""
    if not dismissal:
        return
    desc = dismissal.lower()

    if desc.startswith("c "):
        # "c Fielder b Bowler" or "c & b Bowler" or "c and b Bowler"
        if "c & b" in desc or "c and b" in desc:
            # Caught and bowled — bowler gets the catch credit
            sep = "c & b " if "c & b" in desc else "c and b "
            bowler = dismissal.split(sep)[-1].strip()
            _add_fielding(fielding, bowler, "catches")
        else:
            parts = dismissal.split(" b ")
            if len(parts) >= 2:
                catcher = parts[0].replace("c ", "").strip()
                catcher = catcher.replace("†", "").strip()
                # Remove (sub) prefix: "c (sub)Manoj Bhandage" -> "Manoj Bhandage"
                catcher = re.sub(r"^\(sub\)", "", catcher).strip()
                _add_fielding(fielding, catcher, "catches")

    elif "st " in desc:
        # "st †Keeper b Bowler"
        parts = dismissal.split(" b ")
        if parts:
            keeper = parts[0].replace("st ", "").replace("†", "").strip()
            _add_fielding(fielding, keeper, "stumpings")

    elif "run out" in desc:
        # "run out (Fielder)" or "run out (Fielder/Fielder2)"
        match = re.search(r"run out.*?\(([^)]+)\)", dismissal)
        if match:
            fielders_str = match.group(1)
            fielders = [f.replace("†", "").strip() for f in fielders_str.split("/") if f.strip()]
            if len(fielders) == 1:
                _add_fielding(fielding, fielders[0], "run_out_solo")
            else:
                for f in fielders:
                    _add_fielding(fielding, f, "run_out_shared")


def _add_fielding(fielding: dict, name: str, field_type: str):
    if name not in fielding:
        fielding[name] = {"catches": 0, "stumpings": 0,
                          "run_out_shared": 0, "run_out_solo": 0}
    fielding[name][field_type] += 1
