"""API routes – machine-readable endpoints for automation and integrations."""
import io
import os
import threading
import zipfile
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from web.auth import require_auth, User

router = APIRouter()

# ── Shared state for tracking the running auto-score job ─────────────────────
_job_lock = threading.Lock()
_job_state: dict = {"running": False, "last_run": None, "last_result": None}


def _get_api_key() -> str | None:
    from config import AUTOSCORE_API_KEY
    return AUTOSCORE_API_KEY


def _verify_auto_score_caller(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """
    Allow the request if EITHER:
      1. A valid browser session exists (admin user), OR
      2. The X-Api-Key header matches AUTOSCORE_API_KEY env var.
    Raises 403 if neither is satisfied.
    """
    # Check API key header first (used by GitHub Actions / cron)
    api_key = _get_api_key()
    if api_key and x_api_key and x_api_key == api_key:
        return

    # Fall back to session-based admin check
    username = request.session.get("username") if hasattr(request, "session") else None
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: provide X-Api-Key header or log in as admin",
        )
    from config import USERS_DB
    user_data = USERS_DB.get(username, {})
    if user_data.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def _score_league(league_name: str, get_matches_fn, cfg, score_fn) -> dict:
    """Score all new completed matches for one league. Returns per-league result."""
    from storage import is_match_processed

    result = {
        "league": league_name,
        "matches_found": 0,
        "matches_completed": 0,
        "matches_processed": [],
        "matches_skipped": 0,
        "errors": [],
    }

    try:
        matches = get_matches_fn()
    except Exception as exc:
        result["errors"].append({"match_id": None, "error": f"Failed to fetch matches: {exc}"})
        return result

    result["matches_found"] = len(matches)
    completed = [m for m in matches
                 if m.get("state", "").lower() == "complete" and m.get("match_id")]
    result["matches_completed"] = len(completed)

    new_matches = [m for m in completed if not is_match_processed(m["match_id"], cfg)]
    result["matches_skipped"] = len(completed) - len(new_matches)

    for m in new_matches:
        try:
            score_fn(m["match_id"])
            result["matches_processed"].append({
                "match_id": m["match_id"],
                "description": f"{m['team1']} vs {m['team2']}",
            })
        except Exception as exc:
            result["errors"].append({"match_id": m["match_id"], "error": str(exc)})

    return result


def _run_auto_score_job() -> dict:
    """
    Score new completed matches for all active leagues (IPL + WWC).
    Returns a combined result dict.
    """
    from cricbuzz_api import get_all_ipl_matches, get_all_wwc_matches
    from config import IPL_CONFIG, WWC_CONFIG
    from main import cmd_score
    from main import _wwc_score

    result = {
        "started_at": datetime.utcnow().isoformat(),
        "leagues": {},
    }

    result["leagues"]["ipl"] = _score_league(
        "IPL", get_all_ipl_matches, IPL_CONFIG, cmd_score
    )
    result["leagues"]["wwc"] = _score_league(
        "Women's T20 World Cup", get_all_wwc_matches, WWC_CONFIG,
        lambda mid: _wwc_score(mid)
    )

    result["finished_at"] = datetime.utcnow().isoformat()
    return result


def _background_auto_score():
    """Wrapper that sets/clears the running flag around the job."""
    global _job_state
    try:
        result = _run_auto_score_job()
        with _job_lock:
            _job_state["last_result"] = result
    except Exception as exc:
        with _job_lock:
            _job_state["last_result"] = {"error": str(exc)}
    finally:
        with _job_lock:
            _job_state["running"] = False
            _job_state["last_run"] = datetime.utcnow().isoformat()


@router.post("/auto-score")
async def trigger_auto_score(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
):
    """
    Trigger an auto-score run in the background.
    Auth: X-Api-Key header (for GitHub Actions) OR admin browser session.
    Only one run at a time is allowed.
    """
    _verify_auto_score_caller(request, x_api_key)

    with _job_lock:
        if _job_state["running"]:
            return JSONResponse(
                status_code=409,
                content={"status": "already_running", "message": "Auto-score is already in progress"},
            )
        _job_state["running"] = True

    background_tasks.add_task(_background_auto_score)
    return JSONResponse(
        status_code=202,
        content={
            "status": "started",
            "message": "Auto-score job started. Call GET /api/auto-score/status to check progress.",
        },
    )


@router.get("/auto-score/status")
async def auto_score_status(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Return the status and result of the last auto-score run."""
    _verify_auto_score_caller(request, x_api_key)
    with _job_lock:
        return JSONResponse({
            "running": _job_state["running"],
            "last_run": _job_state["last_run"],
            "last_result": _job_state["last_result"],
        })


@router.post("/wwc/rescore/{match_id}")
async def rescore_wwc_match(
    match_id: int,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Rescore a single WWC match with the current scoring rules. Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from config import WWC_CONFIG
    from storage import (
        is_match_processed, unprocess_match, load_scores, save_scores,
        remove_match_from_scoring_sheet, remove_match_from_master, load_match_history,
    )
    from main import _wwc_score

    cfg = WWC_CONFIG
    if not is_match_processed(match_id, cfg):
        raise HTTPException(status_code=404, detail=f"Match {match_id} not yet processed in WWC")

    old = unprocess_match(match_id, cfg)
    scores = load_scores(cfg)
    for owner, pts in old.items():
        scores[owner] = round(scores.get(owner, 0) - pts, 2)
    save_scores(scores, cfg)
    remove_match_from_scoring_sheet(match_id, cfg)
    remove_match_from_master(match_id, cfg)

    _wwc_score(match_id, cfg)

    history = load_match_history(cfg)
    last = next((m for m in reversed(history) if m["match_id"] == match_id), None)
    return JSONResponse({
        "status": "rescored",
        "match_id": match_id,
        "match_scores": last["team_scores"] if last else {},
    })


@router.post("/wwc/rescore-all")
async def rescore_all_wwc_matches(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Rescore every processed WWC match with the current scoring rules. Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from config import WWC_CONFIG
    from storage import (
        is_match_processed, unprocess_match, load_scores, save_scores,
        remove_match_from_scoring_sheet, remove_match_from_master, load_match_history,
    )
    from main import _wwc_score

    cfg = WWC_CONFIG
    history = load_match_history(cfg)
    match_ids = [m["match_id"] for m in history]

    if not match_ids:
        return JSONResponse({"status": "nothing_to_rescore", "matches": []})

    results = []
    for mid in match_ids:
        try:
            old = unprocess_match(mid, cfg)
            scores = load_scores(cfg)
            for owner, pts in old.items():
                scores[owner] = round(scores.get(owner, 0) - pts, 2)
            save_scores(scores, cfg)
            remove_match_from_scoring_sheet(mid, cfg)
            remove_match_from_master(mid, cfg)
            _wwc_score(mid, cfg)
            results.append({"match_id": mid, "status": "ok"})
        except Exception as exc:
            results.append({"match_id": mid, "status": "error", "error": str(exc)})

    return JSONResponse({"status": "done", "matches": results})


@router.post("/wwc/refresh-captains")
async def refresh_wwc_captains(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Re-sync is_captain/is_vice_captain in WWC master scoresheet from teams config. Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from config import WWC_CONFIG
    from storage import load_master_scoresheet, save_master_scoresheet, load_teams

    cfg = WWC_CONFIG
    master = load_master_scoresheet(cfg)
    teams_data = load_teams(cfg)

    changes = []
    for owner, tdata in master.get("teams", {}).items():
        team_info = teams_data.get("teams", {}).get(owner, {})
        cap = team_info.get("captain", "")
        vc = team_info.get("vice_captain", "")
        for pname, pdata in tdata.get("players", {}).items():
            new_c = (pname == cap)
            new_vc = (pname == vc)
            if pdata.get("is_captain") != new_c or pdata.get("is_vice_captain") != new_vc:
                changes.append({"owner": owner, "player": pname, "captain": new_c, "vc": new_vc})
            pdata["is_captain"] = new_c
            pdata["is_vice_captain"] = new_vc

    save_master_scoresheet(master, cfg)
    return JSONResponse({"status": "done", "changes": changes, "total_updated": len(changes)})


@router.get("/export-data")
async def export_data(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Download all data files (IPL + WWC) as a zip archive."""
    _verify_auto_score_caller(request, x_api_key)
    from config import IPL_CONFIG, WWC_CONFIG

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cfg in (IPL_CONFIG, WWC_CONFIG):
            for fname in ("cumulative_scores.json", "match_history.json",
                          "scoring_sheet.json", "master_scoresheet.json"):
                path = os.path.join(cfg.data_dir, fname)
                if os.path.exists(path):
                    zf.write(path, path)
            if os.path.isdir(cfg.scorecard_cache_dir):
                for sc in os.listdir(cfg.scorecard_cache_dir):
                    path = os.path.join(cfg.scorecard_cache_dir, sc)
                    if os.path.isfile(path):
                        zf.write(path, path)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=railway_data.zip"},
    )
