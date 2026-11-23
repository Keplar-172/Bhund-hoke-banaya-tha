"""Public read-only API endpoints – no authentication required.

These are designed for embedding data on external sites (e.g. WordPress)
via JavaScript fetch() calls.

All responses include CORS headers (handled globally in app.py).

All endpoints accept ?league=<tournament id> (e.g. wpl-2027); default ipl-2026.

Endpoints:
    GET /api/public/leaderboard       – ranked team standings
    GET /api/public/stats             – season summary stats
    GET /api/public/match-history     – list of processed matches
    GET /api/public/scoresheet        – full master scoresheet (teams × matches)
    GET /api/public/player-scores/{match_id} – per-player scores for one match
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

import tournaments

from web.services import (
    get_leaderboard_data,
    get_dashboard_stats,
    get_match_history_data,
    get_master_scoresheet_data,
)

router = APIRouter()

_CACHE_HEADER = {"Cache-Control": "public, max-age=300"}  # 5-minute browser cache


def _t(league: str | None):
    """Tournament from ?league=<id> (e.g. wpl-2027); default ipl-2026."""
    t = tournaments.get(league) if league else tournaments.default()
    if t is None:
        raise HTTPException(status_code=404, detail=f"Unknown tournament '{league}'")
    return t


@router.get("/leaderboard")
async def public_leaderboard(league: str | None = None):
    """
    Current leaderboard – team rankings and cumulative points.

    Example response:
        [
          {"rank": 1, "team": "Alpha XI", "points": 842.5},
          {"rank": 2, "team": "Beta Warriors", "points": 810.0},
          ...
        ]
    """
    data = get_leaderboard_data(_t(league))
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/stats")
async def public_stats(league: str | None = None):
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
    data = get_dashboard_stats(_t(league))
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/match-history")
async def public_match_history(league: str | None = None):
    """
    List of all processed matches (most recent first).

    Each item contains match_id, description, date, and per-team points
    earned in that match.
    """
    data = get_match_history_data(_t(league))
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/scoresheet")
async def public_scoresheet(league: str | None = None):
    """
    Full master scoresheet: every team's cumulative and per-match breakdown.

    Useful for building a detailed grid/table on a WordPress page.
    """
    data = get_master_scoresheet_data(_t(league))
    return JSONResponse(content=data, headers=_CACHE_HEADER)


@router.get("/player-scores/{match_id}")
async def public_player_scores(match_id: int, league: str | None = None):
    """
    Per-player fantasy scores for a single match.

    Returns the cached scoring sheet entry for match_id, or 404 if not found.
    """
    from storage import load_scoring_sheet
    sheet = load_scoring_sheet(_t(league))
    entry = next((m for m in sheet.get("matches", []) if m.get("match_id") == match_id), None)
    if entry is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No scoring data found for match {match_id}"},
        )
    return JSONResponse(content=entry, headers=_CACHE_HEADER)
