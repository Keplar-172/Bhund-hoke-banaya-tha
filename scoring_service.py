"""Scoring workflow shared by the web API and the CLI, for any tournament.

    score_match(match_id, t)     fetch (or use cached) scorecard, score, save
    rescore_match(match_id, t)   undo a processed match and score it again
    rescore_all(t)               rescore every processed match, oldest first
    auto_score(t)                score due matches using the saved schedule
    score_uploaded(match_id, t, data)  score a hand-uploaded scorecard (no API)
"""
import match_schedule as sched_mod
from calculator import calculate_match_scores
from cricbuzz_api import get_match_mom, get_scorecard
from storage import (
    append_to_scoring_sheet, cache_scorecard, get_cached_scorecard,
    is_match_processed, load_match_history, load_scores, record_match,
    remove_match_from_master, remove_match_from_scoring_sheet, save_scores,
    unprocess_match, update_master_scoresheet,
)


def _describe(scorecard_data: dict, match_id: int) -> str:
    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"
    return desc


def score_match(match_id: int, t, scorecard_data: dict | None = None,
                fetch_mom: bool = True) -> dict:
    """Score one match for tournament t. Returns {owner: match_result}.

    Uses the cached scorecard when present (no API call); otherwise fetches it.
    Raises ValueError if the match was already processed.
    """
    if is_match_processed(match_id, t):
        raise ValueError(f"Match {match_id} already processed in {t.id}")

    scorecard_data = scorecard_data or get_cached_scorecard(match_id, t)
    if not scorecard_data:
        scorecard_data = get_scorecard(match_id)

    if fetch_mom and not scorecard_data.get("man_of_the_match"):
        mom = get_match_mom(match_id)
        if mom:
            scorecard_data["man_of_the_match"] = mom

    cache_scorecard(match_id, scorecard_data, t)

    match_results = calculate_match_scores(scorecard_data, t)
    desc = _describe(scorecard_data, match_id)

    scores = load_scores(t)
    team_scores = {}
    for owner, data in match_results.items():
        scores[owner] = round(scores.get(owner, 0) + data["total"], 2)
        team_scores[owner] = data["total"]

    save_scores(scores, t)
    record_match(match_id, desc, team_scores, t)
    append_to_scoring_sheet(match_id, desc, match_results, scores, t)
    update_master_scoresheet(match_id, desc, match_results, scores, t)
    return match_results


def _unscore(match_id: int, t) -> None:
    old = unprocess_match(match_id, t)
    scores = load_scores(t)
    for owner, pts in old.items():
        scores[owner] = round(scores.get(owner, 0) - pts, 2)
    save_scores(scores, t)
    remove_match_from_scoring_sheet(match_id, t)
    remove_match_from_master(match_id, t)


def rescore_match(match_id: int, t) -> dict:
    """Undo a processed match and score it again with current rules/teams."""
    if not is_match_processed(match_id, t):
        raise ValueError(f"Match {match_id} not processed in {t.id}")
    _unscore(match_id, t)
    # From cache; MoM lookups are left to auto_score's retry, so rescores are free.
    return score_match(match_id, t, fetch_mom=False)


def rescore_all(t) -> list:
    """Rescore every processed match in order. Returns per-match status."""
    match_ids = [m["match_id"] for m in load_match_history(t)]
    results = []
    for mid in match_ids:
        try:
            rescore_match(mid, t)
            results.append({"match_id": mid, "status": "ok"})
        except Exception as exc:
            results.append({"match_id": mid, "status": "error", "error": str(exc)})
    return results


def _is_abandoned(sc: dict) -> bool:
    status = (sc.get("status") or "").lower()
    has_balls = any((inn.get("batsman") or inn.get("batTeamDetails")) for inn in
                    (sc.get("scorecard") or sc.get("scoreCard") or []))
    return ("abandon" in status or "no result" in status) and not has_balls


_RESULT_WORDS = (" won by ", " won the super over", "match tied", "match drawn",
                 "won on dls", "won via")


def _is_complete(sc: dict) -> bool:
    """Finished with a result. Cricbuzz sometimes leaves ismatchcomplete False
    on finished matches (4 of 33 WWC 2026 scorecards), so the status text counts too."""
    if sc.get("ismatchcomplete"):
        return True
    if (sc.get("matchHeader", {}).get("state") or "").lower() == "complete":
        return True
    status = " " + (sc.get("status") or sc.get("matchHeader", {}).get("status") or "").lower()
    return any(w in status for w in _RESULT_WORDS)


def auto_score(t) -> dict:
    """Score due matches of tournament t, spending as few API calls as possible.

    1. Fixture list comes from schedule.json (refreshed weekly: 1-2 calls).
    2. Only matches that started MATCH_HOURS ago and aren't scored are fetched.
    3. Man of the Match is retried on later runs if it wasn't announced yet.
    A run with nothing due makes no API calls.
    """
    from cricbuzz_api import ApiBudgetExceeded
    result = {"tournament": t.id, "due": [], "matches_processed": [],
              "waiting": [], "abandoned": [], "mom_found": [], "errors": []}
    try:
        sched = sched_mod.refresh(t)
    except Exception as exc:
        result["errors"].append({"match_id": None, "error": f"Schedule refresh failed: {exc}"})
        sched = sched_mod.load(t)

    processed = {m["match_id"] for m in load_match_history(t)}
    due = sched_mod.due_matches(sched, processed)
    result["due"] = due

    try:
        for mid in due:
            e = sched_mod.entry(sched, mid)
            e["attempts"] = e.get("attempts", 0) + 1
            e["last_try"] = sched_mod.stamp()
            try:
                sc = get_scorecard(mid)
            except ApiBudgetExceeded:
                e["attempts"] -= 1          # not the match's fault
                raise
            except Exception as exc:
                result["errors"].append({"match_id": mid, "error": str(exc)})
                continue
            if _is_abandoned(sc):
                e.update(done=True, note=sc.get("status") or "Abandoned")
                result["abandoned"].append(mid)
                continue
            if not _is_complete(sc):
                e["note"] = sc.get("status") or "Not finished yet"
                result["waiting"].append(mid)
                continue
            try:
                score_match(mid, t, scorecard_data=sc)
            except Exception as exc:
                result["errors"].append({"match_id": mid, "error": str(exc)})
                continue
            cached = get_cached_scorecard(mid, t) or {}
            e.update(done=True, note=sc.get("status", ""),
                     mom_pending=not cached.get("man_of_the_match"))
            result["matches_processed"].append({"match_id": mid, "description": e.get("title", "")})

        # Man of the Match announced late: one 'comm' call, then rescore from cache.
        for mid in sched_mod.mom_due(sched):
            e = sched_mod.entry(sched, mid)
            e["mom_tries"] = e.get("mom_tries", 0) + 1
            e["mom_last_try"] = sched_mod.stamp()
            mom = get_match_mom(mid)
            if not mom:
                continue
            sc = get_cached_scorecard(mid, t)
            if sc is None:
                continue
            sc["man_of_the_match"] = mom
            cache_scorecard(mid, sc, t)
            if is_match_processed(mid, t):
                rescore_match(mid, t)
            e["mom_pending"] = False
            result["mom_found"].append({"match_id": mid, "mom": mom})
    except ApiBudgetExceeded as exc:
        result["errors"].append({"match_id": None, "error": str(exc)})
    finally:
        sched_mod.save(t, sched)
    return result


def score_uploaded(match_id: int, t, scorecard_data: dict, mom: str | None = None) -> dict:
    """Score a scorecard uploaded by hand (no API calls). Replaces any earlier
    score for the same match. Returns {owner: match_result}."""
    sc_list = scorecard_data.get("scorecard") or scorecard_data.get("scoreCard")
    if not isinstance(sc_list, list) or not sc_list:
        raise ValueError("This doesn't look like a Cricbuzz scorecard "
                         "(no 'scorecard' list of innings).")
    if mom:
        scorecard_data["man_of_the_match"] = mom.strip()
    if is_match_processed(match_id, t):
        _unscore(match_id, t)
    # cache first so score_match never calls the API for the scorecard
    cache_scorecard(match_id, scorecard_data, t)
    # No 'comm' call here: a missing MoM is picked up by the MoM retry.
    results = score_match(match_id, t, scorecard_data=scorecard_data, fetch_mom=False)

    sched = sched_mod.load(t)
    e = sched_mod.entry(sched, match_id)
    e.update(done=True, note="Uploaded by admin",
             mom_pending=not scorecard_data.get("man_of_the_match"))
    sched_mod.save(t, sched)
    return results

