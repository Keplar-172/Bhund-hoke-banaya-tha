"""Scoring workflow shared by the web API and the CLI, for any tournament.

    score_match(match_id, t)     fetch (or use cached) scorecard, score, save
    rescore_match(match_id, t)   undo a processed match and score it again
    rescore_all(t)               rescore every processed match, oldest first
    auto_score(t)                score all completed, not-yet-processed matches
"""
from calculator import calculate_match_scores
from cricbuzz_api import get_all_matches, get_match_mom, get_scorecard
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


def score_match(match_id: int, t) -> dict:
    """Score one match for tournament t. Returns {owner: match_result}.

    Uses the cached scorecard when present (no API call); otherwise fetches it.
    Raises ValueError if the match was already processed.
    """
    if is_match_processed(match_id, t):
        raise ValueError(f"Match {match_id} already processed in {t.id}")

    scorecard_data = get_cached_scorecard(match_id, t)
    if not scorecard_data:
        scorecard_data = get_scorecard(match_id)

    if not scorecard_data.get("man_of_the_match"):
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
    return score_match(match_id, t)


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


def auto_score(t) -> dict:
    """Score all completed matches of tournament t that aren't processed yet."""
    result = {
        "tournament": t.id,
        "matches_found": 0,
        "matches_completed": 0,
        "matches_processed": [],
        "matches_skipped": 0,
        "errors": [],
    }
    try:
        matches = get_all_matches(t)
    except Exception as exc:
        result["errors"].append({"match_id": None, "error": f"Failed to fetch matches: {exc}"})
        return result

    result["matches_found"] = len(matches)
    completed = [m for m in matches
                 if m.get("state", "").lower() == "complete" and m.get("match_id")]
    result["matches_completed"] = len(completed)
    new = [m for m in completed if not is_match_processed(m["match_id"], t)]
    result["matches_skipped"] = len(completed) - len(new)

    for m in new:
        try:
            score_match(m["match_id"], t)
            result["matches_processed"].append({
                "match_id": m["match_id"],
                "description": f"{m['team1']} vs {m['team2']}",
            })
        except Exception as exc:
            result["errors"].append({"match_id": m["match_id"], "error": str(exc)})
    return result
