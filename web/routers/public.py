"""Public read-only API endpoints – no authentication required.

These are designed for embedding data on external sites (e.g. WordPress)
via JavaScript fetch() calls.

All responses include CORS headers (handled globally in app.py).

Endpoints:
    GET /api/public/leaderboard       – ranked team standings
    GET /api/public/stats             – season summary stats
    GET /api/public/match-history     – list of processed matches
    GET /api/public/scoresheet        – full master scoresheet (teams × matches)
    GET /api/public/player-scores/{match_id} – per-player scores for one match
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web.services import (
    get_leaderboard_data,
    get_dashboard_stats,
    get_match_history_data,
    get_master_scoresheet_data,
)

router = APIRouter()

_CACHE_HEADER = {"Cache-Control": "public, max-age=300"}  # 5-minute browser cache


@router.get("/leaderboard")
async def public_leaderboard():
    """
    Current leaderboard – team rankings and cumulative points.

    Example response:
        [
          {"rank": 1, "team": "Alpha XI", "points": 842.5},
          {"rank": 2, "team": "Beta Warriors", "points": 810.0},
          ...
        ]
    """
    data = get_leaderboard_data()
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/stats")
async def public_stats():
    """
    Season summary statistics.

    Example response:
        {
          "total_matches": 38,
          "total_teams": 10,
          "top_scorer": {"team": "Alpha XI", "points": 842.5},
          "avg_points": 720.3,
          "points_distribution": [...]
        }
    """
    data = get_dashboard_stats()
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/match-history")
async def public_match_history():
    """
    List of all processed matches (most recent first).

    Each item contains match_id, description, date, and per-team points
    earned in that match.
    """
    data = get_match_history_data()
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/scoresheet")
async def public_scoresheet():
    """
    Full master scoresheet: every team's cumulative and per-match breakdown.

    Useful for building a detailed grid/table on a WordPress page.
    """
    data = get_master_scoresheet_data()
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/player-scores/{match_id}")
async def public_player_scores(match_id: int):
    """
    Per-player fantasy scores for a single match.

    Returns the cached scoring sheet entry for match_id, or 404 if not found.
    """
    from storage import load_scoring_sheet
    sheet = load_scoring_sheet()
    entry = next((m for m in sheet if m.get("match_id") == match_id), None)
    if entry is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No scoring data found for match {match_id}"},
        )
    return JSONResponse(content=entry, headers=_CACHE_HEADER)
