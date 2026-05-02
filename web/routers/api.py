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


def _run_auto_score_job() -> dict:
    """
    Core logic: fetch all IPL matches, find unprocessed completed ones, score them.
    Returns a result dict that is stored in _job_state.
    """
    from cricbuzz_api import get_all_ipl_matches
    from storage import is_match_processed
    from main import cmd_score

    result = {
        "started_at": datetime.utcnow().isoformat(),
        "matches_found": 0,
        "matches_completed": 0,
        "matches_processed": [],
        "matches_skipped": 0,
        "errors": [],
    }

    matches = get_all_ipl_matches()
    result["matches_found"] = len(matches)

    completed = [
        m for m in matches
        if m.get("state", "").lower() == "complete" and m.get("match_id")
    ]
    result["matches_completed"] = len(completed)

    new_matches = [m for m in completed if not is_match_processed(m["match_id"])]
    result["matches_skipped"] = len(completed) - len(new_matches)

    for m in new_matches:
        try:
            cmd_score(m["match_id"])
            result["matches_processed"].append({
                "match_id": m["match_id"],
                "description": f"{m['team1']} vs {m['team2']}",
            })
        except Exception as exc:
            result["errors"].append({
                "match_id": m["match_id"],
                "error": str(exc),
            })

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


@router.get("/export-data")
async def export_data(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Download all data files as a zip archive. Auth: X-Api-Key header or admin session."""
    _verify_auto_score_caller(request, x_api_key)
    from config import DATA_DIR, SCORECARD_CACHE_DIR
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ("cumulative_scores.json", "match_history.json",
                      "scoring_sheet.json", "master_scoresheet.json"):
            path = os.path.join(DATA_DIR, fname)
            if os.path.exists(path):
                zf.write(path, os.path.join("data", fname))
        if os.path.isdir(SCORECARD_CACHE_DIR):
            for sc in os.listdir(SCORECARD_CACHE_DIR):
                path = os.path.join(SCORECARD_CACHE_DIR, sc)
                if os.path.isfile(path):
                    zf.write(path, os.path.join("data", "scorecards", sc))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=railway_data.zip"},
    )
