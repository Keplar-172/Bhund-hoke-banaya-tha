"""Cricbuzz API client via RapidAPI – fetch matches & scorecards."""
import re
import requests
from config import RAPIDAPI_KEY, RAPIDAPI_HOST, BASE_URL

# Change this each season to avoid matching Women's IPL or previous seasons
IPL_SEASON_YEAR = "2026"


def _is_ipl_series(series_name: str) -> bool:
    """Return True only for the target IPL season (e.g. IPL 2026)."""
    return "IPL" in series_name and IPL_SEASON_YEAR in series_name


HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}


def _get(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


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
        "series_name": series_name,
    }


def get_recent_matches() -> list:
    """Return list of recent/current IPL 2026 matches (last ~10 from the API)."""
    data = _get("/matches/v1/recent")
    matches = []
    for type_match in data.get("typeMatches", []):
        for series in type_match.get("seriesMatches", []):
            series_info = series.get("seriesAdWrapper", {})
            if not series_info:
                continue
            series_name = series_info.get("seriesName", "")
            if not _is_ipl_series(series_name):
                continue
            for match in series_info.get("matches", []):
                info = match.get("matchInfo", {})
                matches.append(_parse_match_info(info, series_name))
    return matches


def get_ipl_series_id() -> int | None:
    """
    Find the IPL 2026 series ID by scanning the recent-matches endpoint.
    Filters by both 'IPL' and the season year to avoid Women's IPL or old seasons.
    Returns the series ID, or None if not found.
    """
    data = _get("/matches/v1/recent")
    for type_match in data.get("typeMatches", []):
        for series in type_match.get("seriesMatches", []):
            series_info = series.get("seriesAdWrapper", {})
            if series_info and _is_ipl_series(series_info.get("seriesName", "")):
                return series_info.get("seriesId")
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


def get_all_ipl_matches() -> list:
    """
    Return ALL IPL matches for the current season.
    Fetches the series ID first, then all matches for that series.
    Falls back to get_recent_matches() if series ID cannot be found.
    """
    series_id = get_ipl_series_id()
    if series_id:
        matches = get_series_matches(series_id)
        if matches:
            return matches
    # Fallback: only returns recent matches window (~10 matches)
    return get_recent_matches()


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
