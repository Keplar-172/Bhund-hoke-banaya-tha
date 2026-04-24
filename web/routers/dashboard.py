"""Dashboard routes - main views for scores and analytics."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from web.auth import require_auth, User
from web.services import (
    get_leaderboard_data,
    get_match_history_data,
    get_master_scoresheet_data,
    get_match_detail_data,
    get_dashboard_stats,
)
from web.analytics import get_analytics_summary


router = APIRouter()

templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, user: User = Depends(require_auth)):
    """Main dashboard showing current leaderboard."""
    leaderboard = get_leaderboard_data()
    stats = get_dashboard_stats()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "leaderboard": leaderboard,
            "stats": stats,
            "page": "home"
        }
    )


@router.get("/history", response_class=HTMLResponse)
async def match_history(request: Request, user: User = Depends(require_auth)):
    """Show match history."""
    history = get_match_history_data()
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "user": user,
            "history": history,
            "page": "history"
        }
    )


@router.get("/master", response_class=HTMLResponse)
async def master_scoresheet(request: Request, user: User = Depends(require_auth)):
    """Show cumulative master scoresheet."""
    master = get_master_scoresheet_data()
    return templates.TemplateResponse(
        request=request,
        name="master.html",
        context={
            "user": user,
            "master": master,
            "page": "master"
        }
    )


@router.get("/match/{match_id}", response_class=HTMLResponse)
async def match_detail(
    request: Request,
    match_id: int,
    user: User = Depends(require_auth)
):
    """Show detailed scores for a specific match."""
    try:
        detail = get_match_detail_data(match_id)
        return templates.TemplateResponse(
            request=request,
            name="match_detail.html",
            context={
                "user": user,
                "detail": detail,
                "match_id": match_id,
                "page": "match"
            }
        )
    except FileNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "user": user,
                "error": f"Match {match_id} not found or not yet processed"
            },
            status_code=404
        )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, user: User = Depends(require_auth)):
    """Show comprehensive analytics dashboard."""
    analytics = get_analytics_summary()
    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "user": user,
            "analytics": analytics,
            "page": "analytics"
        }
    )
