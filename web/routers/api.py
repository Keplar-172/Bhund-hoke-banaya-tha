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
    """Score new completed matches for every tournament whose status is 'live'.

    Completed and upcoming tournaments are skipped, so they cost no API calls.
    """
    import tournaments
    from scoring_service import auto_score

    result = {"started_at": datetime.utcnow().isoformat(), "tournaments": {}}
    for t in tournaments.all_tournaments():
        if t.is_live:
            result["tournaments"][t.id] = auto_score(t)
    if not result["tournaments"]:
        result["note"] = "No live tournaments – nothing fetched."
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


def _tournament_or_404(tid: str):
    import tournaments
    t = tournaments.get(tid)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Unknown tournament '{tid}'")
    return t


@router.post("/t/{tid}/rescore/{match_id}")
async def rescore_match_endpoint(
    tid: str,
    match_id: int,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Rescore one processed match with the current rules and teams. Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from scoring_service import rescore_match
    t = _tournament_or_404(tid)
    try:
        results = rescore_match(match_id, t)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return JSONResponse({
        "status": "rescored",
        "tournament": t.id,
        "match_id": match_id,
        "match_scores": {owner: d["total"] for owner, d in results.items()},
    })


@router.post("/t/{tid}/rescore-all")
async def rescore_all_endpoint(
    tid: str,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Rescore every processed match of a tournament. Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from scoring_service import rescore_all
    t = _tournament_or_404(tid)
    results = rescore_all(t)
    if not results:
        return JSONResponse({"status": "nothing_to_rescore", "matches": []})
    return JSONResponse({"status": "done", "tournament": t.id, "matches": results})


@router.get("/usage")
async def api_usage(request: Request, x_api_key: str | None = Header(default=None)):
    """Cricbuzz API calls used this month (free-tier budget). Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    from cricbuzz_api import usage_summary
    return JSONResponse(usage_summary())


@router.post("/t/{tid}/auto-score")
async def auto_score_one(tid: str, request: Request, x_api_key: str | None = Header(default=None)):
    """Run auto-score now for one tournament, whatever its status. Admin-only.
    Only due matches are fetched, so this is cheap to press."""
    _verify_auto_score_caller(request, x_api_key)
    from scoring_service import auto_score
    t = _tournament_or_404(tid)
    with _job_lock:
        if _job_state["running"]:
            raise HTTPException(status_code=409, detail="Auto-score is already running")
        _job_state["running"] = True
    try:
        import asyncio
        return JSONResponse(await asyncio.to_thread(auto_score, t))
    finally:
        with _job_lock:
            _job_state["running"] = False


@router.post("/t/{tid}/schedule/refresh")
async def refresh_schedule(tid: str, request: Request, x_api_key: str | None = Header(default=None)):
    """Re-fetch the fixture list (1-2 API calls). Admin-only."""
    _verify_auto_score_caller(request, x_api_key)
    import match_schedule
    t = _tournament_or_404(tid)
    try:
        sched = match_schedule.refresh(t, force=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch the schedule: {exc}")
    if not sched.get("matches"):
        raise HTTPException(status_code=404, detail=(
            "No fixtures found. Cricbuzz may not list this series yet; "
            "add \"series_id\" to tournament.json if you know it."))
    return JSONResponse({"status": "ok", "series_id": sched.get("series_id"),
                         "matches": len(sched["matches"])})


@router.post("/t/{tid}/upload-scorecard")
async def upload_scorecard(tid: str, request: Request, x_api_key: str | None = Header(default=None)):
    """Score a scorecard pasted or uploaded by an admin (no API calls).

    Body: multipart form with match_id, optional mom, and either a 'file'
    (.json) or 'json' text field. Replaces any earlier score for the match.
    """
    _verify_auto_score_caller(request, x_api_key)
    import json as _json
    from scoring_service import score_uploaded
    t = _tournament_or_404(tid)
    form = await request.form()
    try:
        match_id = int(str(form.get("match_id", "")).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Enter the Cricbuzz match ID (a number).")
    raw = form.get("file")
    text = ""
    if raw is not None and hasattr(raw, "read"):
        text = (await raw.read()).decode("utf-8", errors="replace")
    if not text.strip():
        text = str(form.get("json", ""))
    if not text.strip():
        raise HTTPException(status_code=400, detail="Choose a .json file or paste the scorecard JSON.")
    try:
        data = _json.loads(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"That isn't valid JSON: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object (the hscard response).")
    try:
        results = score_uploaded(match_id, t, data, mom=(form.get("mom") or None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"status": "scored", "tournament": t.id, "match_id": match_id,
                         "match_scores": {o: d["total"] for o, d in results.items()},
                         "mom": data.get("man_of_the_match")})


@router.get("/export-data")
async def export_data(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Download all tournament data (every folder under data/tournaments) as a zip."""
    _verify_auto_score_caller(request, x_api_key)
    from tournaments import DATA_ROOT, TOURNAMENTS_DIR

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(TOURNAMENTS_DIR):
            for fname in files:
                path = os.path.join(root, fname)
                # stored as data/tournaments/... so `main.py sync-data` restores in place
                zf.write(path, os.path.join("data", os.path.relpath(path, DATA_ROOT)))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=railway_data.zip"},
    )
