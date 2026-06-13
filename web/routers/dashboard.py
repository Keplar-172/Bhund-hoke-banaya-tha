"""Dashboard routes - main views for scores and analytics."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from config import LeagueConfig, IPL_CONFIG, WWC_CONFIG
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


def _get_league(request: Request) -> LeagueConfig:
    """Pick the correct league config based on the URL path prefix."""
    return WWC_CONFIG if request.url.path.startswith("/wwc") else IPL_CONFIG


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    leaderboard = get_leaderboard_data(league)
    stats = get_dashboard_stats(league)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "leaderboard": leaderboard,
            "stats": stats,
            "page": "home",
            "league": league,
        }
    )


@router.get("/history", response_class=HTMLResponse)
async def match_history(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    history = get_match_history_data(league)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "user": user,
            "history": history,
            "page": "history",
            "league": league,
        }
    )


@router.get("/master", response_class=HTMLResponse)
async def master_scoresheet(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    master = get_master_scoresheet_data(league)
    return templates.TemplateResponse(
        request=request,
        name="master.html",
        context={
            "user": user,
            "master": master,
            "page": "master",
            "league": league,
        }
    )


@router.get("/match/{match_id}", response_class=HTMLResponse)
async def match_detail(
    request: Request,
    match_id: int,
    user: User = Depends(require_auth)
):
    league = _get_league(request)
    try:
        detail = get_match_detail_data(match_id, league)
        return templates.TemplateResponse(
            request=request,
            name="match_detail.html",
            context={
                "user": user,
                "detail": detail,
                "match_id": match_id,
                "page": "match",
                "league": league,
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
    league = _get_league(request)
    analytics = get_analytics_summary(league)
    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "user": user,
            "analytics": analytics,
            "page": "analytics",
            "league": league,
        }
    )
