"""Squad history: which owner had which players, from when.

teams_data.json is always the CURRENT squads. Once squads change mid-season
(trades, admin changes), every version is also kept in squad_history.json:

    {"versions": [
        {"version": 1, "effective_from": null,  "reason": "Squads before the first change", "teams": {...}},
        {"version": 2, "effective_from": "2027-04-02T10:15:00+00:00", "reason": "Trade #4", "teams": {...}}
    ]}

A match is scored with the version in force when it started (start time from
the saved schedule). So points earned before a trade stay with the old owner,
even when the match is rescored later. With no history file, scoring uses the
current squads, exactly as before.
"""
import copy
import json
import os
from datetime import datetime, timezone

from storage import load_match_history, load_teams, save_teams


def _path(t) -> str:
    return os.path.join(t.data_dir, "squad_history.json")


def load_history(t) -> list:
    try:
        with open(_path(t)) as f:
            return json.load(f).get("versions", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_history(t, versions: list) -> None:
    tmp = _path(t) + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"versions": versions}, f, indent=1)
    os.replace(tmp, _path(t))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_change(t, new_teams: dict, reason: str, effective_from: str | None = None) -> int:
    """Save new current squads and remember the change. Returns the new version.

    new_teams is the full {"owner": team} mapping (same shape as teams_data["teams"]).
    effective_from defaults to now: matches starting after it use the new squads.
    """
    versions = load_history(t)
    current = load_teams(t)
    if not versions:
        versions.append({"version": 1, "effective_from": None,
                         "reason": "Squads before the first change",
                         "teams": copy.deepcopy(current.get("teams", {}))})
    version = versions[-1]["version"] + 1
    versions.append({"version": version, "effective_from": effective_from or _now_iso(),
                     "reason": reason, "teams": copy.deepcopy(new_teams)})
    _save_history(t, versions)
    current["teams"] = new_teams
    save_teams(current, t)
    return version


def _start_iso(t, match_id: int) -> str | None:
    """Match start time (UTC ISO) from the saved schedule, if known."""
    try:
        import match_schedule
        e = match_schedule.load(t).get("matches", {}).get(str(match_id), {})
        ms = e.get("start_ms")
        if ms:
            return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds")
    except Exception:
        pass
    return None


def version_for_match(t, match_id: int, versions: list | None = None) -> dict | None:
    """The squad version a match should be scored with, or None (= current)."""
    versions = versions if versions is not None else load_history(t)
    if not versions:
        return None
    start = _start_iso(t, match_id)
    if start:
        chosen = versions[0]
        for v in versions:
            if v["effective_from"] is None or v["effective_from"] <= start:
                chosen = v
        return chosen
    # No start time: reuse the version the match was first scored with.
    for m in load_match_history(t):
        if m.get("match_id") == match_id and m.get("squad_version"):
            for v in versions:
                if v["version"] == m["squad_version"]:
                    return v
    return versions[-1]


def teams_for_match(t, match_id: int) -> tuple[dict, int | None]:
    """(teams_data-shaped dict, version number or None) for scoring a match."""
    v = version_for_match(t, match_id)
    if v is None:
        return load_teams(t), None
    return {"teams": copy.deepcopy(v["teams"])}, v["version"]
