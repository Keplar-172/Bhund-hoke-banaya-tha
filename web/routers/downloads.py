"""Download routes - export files in various formats."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from datetime import date
import os
import tempfile

from web.auth import require_auth, User
from leaderboard import (
    export_summary_to_excel,
    export_detailed_to_excel,
    export_master_to_excel,
    export_scorecard_to_excel,
    export_team_points_to_excel,
    export_teams_to_excel,
    export_analytics_to_excel,
)
from calculator import calculate_match_scores
from storage import get_cached_scorecard


router = APIRouter()

MATCH_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "Match data")


@router.get("/master")
async def download_master(user: User = Depends(require_auth)):
    """Download master scoresheet Excel."""
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_master_scoresheet.xlsx")
    
    # Generate fresh export
    export_master_to_excel(filename)
    
    if not os.path.exists(filename):
        raise HTTPException(status_code=500, detail="Export generation failed")
    
    return FileResponse(
        path=filename,
        filename=f"{today}_master_scoresheet.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/match/{match_id}/team-points")
async def download_team_points(match_id: int, user: User = Depends(require_auth)):
    """Download team points for a specific match."""
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    
    match_results = calculate_match_scores(scorecard_data)
    
    # Build description
    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"
    
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_team_points_{match_id}.xlsx")
    
    export_team_points_to_excel(match_results, desc, filename)
    
    if not os.path.exists(filename):
        raise HTTPException(status_code=500, detail="Export generation failed")
    
    return FileResponse(
        path=filename,
        filename=f"{today}_team_points_{match_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/match/{match_id}/scorecard")
async def download_scorecard(match_id: int, user: User = Depends(require_auth)):
    """Download cricket scorecard for a specific match."""
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_scorecard_{match_id}.xlsx")
    
    export_scorecard_to_excel(scorecard_data, filename, match_id)
    
    if not os.path.exists(filename):
        raise HTTPException(status_code=500, detail="Export generation failed")
    
    return FileResponse(
        path=filename,
        filename=f"{today}_scorecard_{match_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/teams")
async def download_teams(user: User = Depends(require_auth)):
    """Download all team rosters."""
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_teams.xlsx")
    
    export_teams_to_excel(filename)
    
    if not os.path.exists(filename):
        raise HTTPException(status_code=500, detail="Export generation failed")
    
    return FileResponse(
        path=filename,
        filename=f"{today}_teams.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/analytics")
async def download_analytics(user: User = Depends(require_auth)):
    """Download analytics dashboard."""
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_analytics.xlsx")
    
    export_analytics_to_excel(filename)
    
    if not os.path.exists(filename):
        raise HTTPException(status_code=500, detail="Export generation failed")
    
    return FileResponse(
        path=filename,
        filename=f"{today}_analytics.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
