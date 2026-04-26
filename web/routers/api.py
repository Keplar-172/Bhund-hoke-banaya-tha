"""API routes – machine-readable endpoints for automation and integrations."""
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from web.auth import require_auth, User

router = APIRouter()

# ── Shared state for tracking the running auto-score job ─────────────────────
_job_lock = threading.Lock()
_job_state: dict = {"running": False, "last_run": None, "last_result": None}


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
    background_tasks: BackgroundTasks,
    user: User = Depends(require_auth),
):
    """
    Trigger an auto-score run in the background.
    Fetches all IPL matches, finds unprocessed completed ones, and scores them.
    Only one run at a time is allowed. Admin login required.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

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
async def auto_score_status(user: User = Depends(require_auth)):
    """Return the status and result of the last auto-score run."""
    with _job_lock:
        return JSONResponse({
            "running": _job_state["running"],
            "last_run": _job_state["last_run"],
            "last_result": _job_state["last_result"],
        })
