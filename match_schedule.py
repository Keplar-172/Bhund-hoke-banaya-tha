"""Season schedule cache: decide which matches are due without calling the API.

data/tournaments/<id>/schedule.json holds the fixture list (fetched once, then
refreshed weekly) plus per-match progress:

    {"series_id": 9237, "fetched_at": "...",
     "matches": {"<match_id>": {"title": "MI vs CSK, 3rd Match", "team1": "MI",
                                "team2": "CSK", "start_ms": 1789..., "state": "...",
                                "attempts": 0, "last_try": null,
                                "done": false, "note": "",
                                "mom_pending": false, "mom_tries": 0}}}

A match is "due" when it started at least MATCH_HOURS ago, isn't scored yet and
isn't marked done. Runs with nothing due make no API calls at all.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from cricbuzz_api import get_recent_matches, get_series_id, get_series_matches

MATCH_HOURS = float(os.environ.get("MATCH_HOURS", "4"))   # T20 ≈ 3h30 + buffer
REFRESH_DAYS = 7
EMPTY_RETRY_HOURS = 12   # when Cricbuzz doesn't list the series yet
MAX_ATTEMPTS = 4          # scorecard fetches per match before giving up
RETRY_GAP_MIN = 90        # wait between retries of the same match
MOM_MAX_TRIES = 3         # extra 'comm' calls to find Man of the Match


def _now():
    return datetime.now(timezone.utc)


def load(t) -> dict:
    try:
        with open(t.schedule_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"series_id": None, "fetched_at": None, "matches": {}}


def save(t, sched: dict) -> None:
    os.makedirs(os.path.dirname(t.schedule_file), exist_ok=True)
    tmp = t.schedule_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sched, f, indent=1)
    os.replace(tmp, t.schedule_file)


def _stale(sched: dict) -> bool:
    if not sched.get("fetched_at"):
        return True
    age = _now() - datetime.fromisoformat(sched["fetched_at"])
    if not sched.get("matches"):
        # Series not listed yet: look again twice a day, not on every run.
        return age > timedelta(hours=EMPTY_RETRY_HOURS)
    return age > timedelta(days=REFRESH_DAYS)


def refresh(t, sched: dict | None = None, force: bool = False) -> dict:
    """Fetch the fixture list if missing/stale (1–2 API calls). Keeps progress."""
    sched = sched or load(t)
    if not force and not _stale(sched):
        return sched

    series_id = t.series_id or sched.get("series_id")
    if not series_id:
        series_id = get_series_id(t)                      # 1 call
    fixtures = get_series_matches(series_id) if series_id else []   # 1 call
    if not fixtures:
        # Series endpoint unavailable: use the recent window (1 call). No
        # start times there, so these are treated as due once 'complete'.
        fixtures = get_recent_matches(t)

    old = sched.get("matches", {})
    matches = {}
    for m in fixtures:
        mid = m.get("match_id")
        if not mid:
            continue
        entry = old.get(str(mid), {})
        entry.update({
            "title": f"{m.get('team1')} vs {m.get('team2')}, {m.get('description', '')}".strip(", "),
            "team1": m.get("team1"), "team2": m.get("team2"),
            "start_ms": m.get("start_ms") or entry.get("start_ms") or 0,
            "state": m.get("state", ""),
        })
        matches[str(mid)] = entry
    # keep entries we were tracking that dropped out of the response
    for mid, entry in old.items():
        matches.setdefault(mid, entry)

    sched.update({"series_id": series_id,
                  "fetched_at": _now().isoformat(timespec="seconds"),
                  "matches": matches})
    save(t, sched)
    return sched


def _started_long_enough(entry: dict) -> bool:
    start = entry.get("start_ms") or 0
    if not start:
        return entry.get("state", "").lower() == "complete"
    started = datetime.fromtimestamp(start / 1000, timezone.utc)
    return _now() >= started + timedelta(hours=MATCH_HOURS)


def _retry_ok(entry: dict) -> bool:
    if entry.get("attempts", 0) >= MAX_ATTEMPTS:
        return False
    last = entry.get("last_try")
    if not last:
        return True
    return _now() - datetime.fromisoformat(last) >= timedelta(minutes=RETRY_GAP_MIN)


def due_matches(sched: dict, processed: set) -> list:
    """Match ids worth fetching now, oldest first."""
    out = []
    for mid, e in sched.get("matches", {}).items():
        if e.get("done") or int(mid) in processed:
            continue
        if _started_long_enough(e) and _retry_ok(e):
            out.append((e.get("start_ms") or 0, int(mid)))
    return [mid for _s, mid in sorted(out)]


def mom_due(sched: dict) -> list:
    out = []
    for mid, e in sched.get("matches", {}).items():
        if e.get("mom_pending") and e.get("mom_tries", 0) < MOM_MAX_TRIES:
            last = e.get("mom_last_try")
            if not last or _now() - datetime.fromisoformat(last) >= timedelta(minutes=RETRY_GAP_MIN):
                out.append(int(mid))
    return out


def entry(sched: dict, match_id: int) -> dict:
    return sched.setdefault("matches", {}).setdefault(str(match_id), {})


def stamp() -> str:
    return _now().isoformat(timespec="seconds")


def summary(t) -> dict:
    """For the admin page: what's next, what's stuck."""
    sched = load(t)
    rows = []
    for mid, e in sched.get("matches", {}).items():
        rows.append({"match_id": int(mid), **e})
    rows.sort(key=lambda r: (r.get("start_ms") or 0, r["match_id"]))
    now_ms = _now().timestamp() * 1000
    upcoming = [r for r in rows if (r.get("start_ms") or 0) > now_ms][:3]
    stuck = [r for r in rows if not r.get("done") and r.get("attempts", 0) >= MAX_ATTEMPTS]
    mom = [r for r in rows if r.get("mom_pending")]
    return {"series_id": sched.get("series_id"), "fetched_at": sched.get("fetched_at"),
            "total": len(rows), "upcoming": upcoming, "stuck": stuck, "mom_pending": mom}
